//! One MCAP file: its schemas and channels, the header and end marker, and chunks closed every second.

use std::collections::BTreeMap;
use std::io::{Seek, Write};

use mcap::records::MessageHeader;
use schemars::JsonSchema;
use serde::Serialize;

use crate::RecordError;
use crate::batch::{Loss, TickBatch};
use crate::session::SessionInfo;
use crate::wire::{BusTotals, Clock, End, Frames, Gap, Header, SessionRecord, Stamp};

/// A chunk is closed after this long even if it hasn't reached [`CHUNK_BYTES`], so a crash loses about a second
/// (logging.md section 8.4).
pub(crate) const CHUNK_NS: u64 = 1_000_000_000;
/// The uncompressed size at which a chunk is closed (Foxglove recommends 1 to 4 MB).
const CHUNK_BYTES: u64 = 4 << 20;

pub(crate) struct McapFile<W: Write + Seek> {
    mcap: mcap::Writer<W>,
    info: SessionInfo,
    frames: Vec<u16>,
    gap: u16,
    clock: u16,
    session: u16,
    sequence: u32,
    totals: Vec<BusTotals>,
    chunk_started_ns: Option<u64>,
}

impl<W: Write + Seek> McapFile<W> {
    /// Open the file on `sink` and write its header.
    pub(crate) fn new(
        sink: W,
        session: String,
        file: u32,
        info: SessionInfo,
        wall_ns: u64,
    ) -> Result<Self, RecordError> {
        let mut mcap = mcap::WriteOptions::new()
            .compression(Some(mcap::Compression::Zstd))
            .chunk_size(Some(CHUNK_BYTES))
            .calculate_chunk_crcs(true)
            // zstd's default spawns a worker per core; the recorder compresses on its own thread, off the bus
            // threads' cores.
            .compression_threads(0)
            .library(concat!("roark-telemetry/", env!("CARGO_PKG_VERSION")))
            .create(sink)?;
        let frames_schema = schema::<Frames>(&mut mcap, "roark.can.Frames")?;
        let frames = info
            .buses
            .iter()
            .map(|bus| {
                channel(
                    &mut mcap,
                    frames_schema,
                    &format!("/can/{}/frames", bus.name),
                )
            })
            .collect::<Result<_, _>>()?;
        let gap_schema = schema::<Gap>(&mut mcap, "roark.recorder.Gap")?;
        let gap = channel(&mut mcap, gap_schema, "/recorder/gap")?;
        let clock_schema = schema::<Clock>(&mut mcap, "roark.Clock")?;
        let clock = channel(&mut mcap, clock_schema, "/clock")?;
        let session_schema = schema::<SessionRecord>(&mut mcap, "roark.Session")?;
        let session_channel = channel(&mut mcap, session_schema, "/session")?;
        let totals = info
            .buses
            .iter()
            .map(|bus| BusTotals {
                name: bus.name.clone(),
                ..BusTotals::default()
            })
            .collect();
        let mut this = Self {
            mcap,
            info,
            frames,
            gap,
            clock,
            session: session_channel,
            sequence: 0,
            totals,
            chunk_started_ns: None,
        };
        let header = SessionRecord::Header(Header {
            session,
            file,
            info: this.info.clone(),
        });
        this.write(this.session, wall_ns, &header)?;
        Ok(this)
    }

    pub(crate) fn info(&self) -> &SessionInfo {
        &self.info
    }

    /// Write bus `bus`'s batch, after a gap record for any batches it lost before this one.
    pub(crate) fn batch(&mut self, bus: usize, batch: &TickBatch) -> Result<(), RecordError> {
        let channel = *self.frames.get(bus).ok_or(RecordError::NoSuchBus(bus))?;
        self.gap(bus, batch.lost_before, batch.wall_ns)?;
        self.write(channel, batch.wall_ns, &Frames::from(batch))?;
        if let Some(totals) = self.totals.get_mut(bus) {
            totals.batches += 1;
            totals.frames += batch.frames().len() as u64;
            totals.frames_omitted += u64::from(batch.omitted());
        }
        Ok(())
    }

    /// Write a gap record for `loss` on bus `bus`, if it lost anything.
    pub(crate) fn gap(&mut self, bus: usize, loss: Loss, wall_ns: u64) -> Result<(), RecordError> {
        if loss.is_empty() {
            return Ok(());
        }
        let totals = self
            .totals
            .get_mut(bus)
            .ok_or(RecordError::NoSuchBus(bus))?;
        totals.batches_lost += loss.batches;
        totals.frames_lost += loss.frames;
        let gap = Gap {
            bus: totals.name.clone(),
            batches: loss.batches,
            frames: loss.frames,
            first_tick: loss.first_tick,
            last_tick: loss.last_tick,
        };
        self.write(self.gap, wall_ns, &gap)
    }

    /// Write the two clocks read together.
    pub(crate) fn clock(&mut self, mono_ns: u64, wall_ns: u64) -> Result<(), RecordError> {
        let clock = Clock {
            monotonic: Stamp::from_ns(mono_ns),
            wall: Stamp::from_ns(wall_ns),
        };
        self.write(self.clock, wall_ns, &clock)
    }

    /// Close the open chunk once it is a second old.
    pub(crate) fn poll(&mut self, mono_ns: u64) -> Result<(), RecordError> {
        match self.chunk_started_ns {
            None => self.chunk_started_ns = Some(mono_ns),
            Some(started) if mono_ns.saturating_sub(started) >= CHUNK_NS => {
                self.chunk_started_ns = Some(mono_ns);
                self.mcap.flush()?;
            }
            Some(_) => {}
        }
        Ok(())
    }

    /// Write the end marker and finish the file: the last chunk, the index and the footer. Returns the sink, not yet
    /// synced.
    pub(crate) fn finish(mut self, wall_ns: u64) -> Result<(W, End), RecordError> {
        let end = End {
            buses: std::mem::take(&mut self.totals),
        };
        self.write(self.session, wall_ns, &SessionRecord::End(end.clone()))?;
        self.mcap.finish()?;
        Ok((self.mcap.into_inner(), end))
    }

    fn write(
        &mut self,
        channel: u16,
        wall_ns: u64,
        message: &impl Serialize,
    ) -> Result<(), RecordError> {
        let data = serde_json::to_vec(message)?;
        self.sequence = self.sequence.wrapping_add(1);
        let header = MessageHeader {
            channel_id: channel,
            sequence: self.sequence,
            // Both the source time, so Foxglove (which plays by log_time) replays ticks as they happened rather than as
            // the disk drained them (logging.md section 3).
            log_time: wall_ns,
            publish_time: wall_ns,
        };
        self.mcap.write_to_known_channel(&header, &data)?;
        Ok(())
    }
}

fn schema<T: JsonSchema>(
    mcap: &mut mcap::Writer<impl Write + Seek>,
    name: &str,
) -> Result<u16, RecordError> {
    let schema = serde_json::to_vec(&schemars::schema_for!(T))?;
    Ok(mcap.add_schema(name, "jsonschema", &schema)?)
}

fn channel(
    mcap: &mut mcap::Writer<impl Write + Seek>,
    schema: u16,
    topic: &str,
) -> Result<u16, RecordError> {
    Ok(mcap.add_channel(schema, topic, "json", &BTreeMap::new())?)
}
