//! The recorder's side: drain every bus's ring into the session's file, and the thread that does it.

use std::fs::File;
use std::io::BufWriter;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::thread::JoinHandle;
use std::time::{Duration, Instant, SystemTime};

use crate::RecordError;
use crate::bus::{self, BusDrain, BusRecorder};
use crate::event::{self, EventDrain, EventRecorder};
use crate::file::CHUNK_NS;
use crate::session::{Session, Sink};
use crate::wire::End;

/// How often the recorder thread drains the rings. A ring holds two seconds, so this is far inside it.
const DRAIN_PERIOD: Duration = Duration::from_millis(10);

/// The monotonic clock's zero for a session: every monotonic time in the file is nanoseconds since it. Bus threads
/// stamp their ticks with [`Self::ns`].
#[derive(Clone, Copy, Debug)]
pub struct Epoch(Instant);

impl Epoch {
    /// Nanoseconds from the epoch to `at` (0 for a time before it).
    #[must_use]
    pub fn ns(&self, at: Instant) -> u64 {
        u64::try_from(at.saturating_duration_since(self.0).as_nanos()).unwrap_or(u64::MAX)
    }
}

/// Whether the recording still works, for the enable gate (PLAN.md, safety's Logging row: refuse the next enable, never
/// stop a running motion for it). Set on the first write error and never cleared.
#[derive(Clone, Debug, Default)]
pub struct Health(Arc<AtomicBool>);

impl Health {
    /// True once any write has failed.
    #[must_use]
    pub fn failed(&self) -> bool {
        self.0.load(Ordering::Acquire)
    }

    fn fail(&self) {
        self.0.store(true, Ordering::Release);
    }
}

/// A session being recorded: every bus's ring, drained into the session's file. [`Recorder`] runs one on a thread;
/// tests step one by hand.
pub struct Recording<W: Sink = BufWriter<File>> {
    session: Session<W>,
    drains: Vec<BusDrain>,
    events: Option<EventDrain>,
    /// The two clocks as last read together: maps an event's monotonic time to the wall clock.
    clocks: Option<(u64, u64)>,
    health: Health,
    epoch: Epoch,
    failure: Option<String>,
    last_clock_ns: Option<u64>,
}

impl<W: Sink> Recording<W> {
    /// Make a ring of `capacity` batches (normally [`RING_BATCHES`](crate::RING_BATCHES)) for each of the session's
    /// buses. Each [`BusRecorder`] goes to its bus's thread; its index is the bus's place in the session's bus table.
    #[must_use]
    pub fn new(session: Session<W>, capacity: usize) -> (Self, Vec<BusRecorder>) {
        let (buses, drains) = (0..session.info().buses.len())
            .map(|bus| bus::ring(bus, capacity))
            .unzip();
        let recording = Self {
            session,
            drains,
            events: None,
            clocks: None,
            health: Health::default(),
            epoch: Epoch(Instant::now()),
            failure: None,
            last_clock_ns: None,
        };
        (recording, buses)
    }

    /// The session's monotonic zero, for the bus threads' tick stamps.
    #[must_use]
    pub fn epoch(&self) -> Epoch {
        self.epoch
    }

    /// The recording's health, for the enable gate.
    #[must_use]
    pub fn health(&self) -> Health {
        self.health.clone()
    }

    /// Make the ring of `capacity` events (normally [`RING_EVENTS`](crate::RING_EVENTS)) for the control thread, its
    /// events naming joints by their index in `joints`. One per session: a second call replaces the first ring.
    pub fn events(&mut self, joints: Vec<String>, capacity: usize) -> EventRecorder {
        let (recorder, drain) = event::ring(joints, capacity);
        self.events = Some(drain);
        recorder
    }

    /// Drain every ring into the file, write `/clock` once a second, and close the chunk once a second. `mono_ns`
    /// (since the [`Epoch`]) and `wall_ns` are the two clocks read together.
    ///
    /// # Errors
    /// A write failed. The recording is then failed: its [`Health`] says so, later batches are drained and discarded,
    /// and [`Self::close`] returns the error.
    pub fn step(&mut self, mono_ns: u64, wall_ns: u64) -> Result<(), RecordError> {
        let result = self.write_due(mono_ns, wall_ns);
        self.check(result)
    }

    fn write_due(&mut self, mono_ns: u64, wall_ns: u64) -> Result<(), RecordError> {
        self.clocks = Some((mono_ns, wall_ns));
        if let Some(reason) = &self.failure {
            for drain in &mut self.drains {
                while drain.consumer.pop().is_ok() {}
            }
            if let Some(drain) = &mut self.events {
                while drain.consumer.pop().is_ok() {}
            }
            return Err(RecordError::Failed(reason.clone()));
        }
        self.drain()?;
        if self
            .last_clock_ns
            .is_none_or(|last| mono_ns.saturating_sub(last) >= CHUNK_NS)
        {
            self.last_clock_ns = Some(mono_ns);
            self.session.file.clock(mono_ns, wall_ns)?;
        }
        self.session.file.poll(mono_ns)
    }

    fn drain(&mut self) -> Result<(), RecordError> {
        for (bus, drain) in self.drains.iter_mut().enumerate() {
            // Bounded: the ring holds at most its capacity, and the bus thread can't outpace a drain by a whole ring.
            for _ in 0..drain.consumer.buffer().capacity() {
                let Ok(batch) = drain.consumer.pop() else {
                    break;
                };
                self.session.file.batch(bus, &batch)?;
            }
        }
        if let Some(drain) = &mut self.events {
            for _ in 0..drain.consumer.buffer().capacity() {
                let Ok(event) = drain.consumer.pop() else {
                    break;
                };
                // Before the first clock reading there is no mapping; the wall time is then left at 0.
                let wall_ns = self
                    .clocks
                    .map_or(0, |(mono, wall)| to_wall(event.mono_ns, mono, wall));
                self.session.file.event(&event, &drain.joints, wall_ns)?;
            }
            self.session
                .file
                .events_lost(drain.lost.load(Ordering::Relaxed));
        }
        Ok(())
    }

    fn check(&mut self, result: Result<(), RecordError>) -> Result<(), RecordError> {
        if let Err(e) = &result {
            self.health.fail();
            if self.failure.is_none() {
                self.failure = Some(e.to_string());
            }
        }
        result
    }

    /// Stop recording: drain every ring (control's events with them), write a gap for each bus's batches dropped since
    /// its last accepted one, write the end marker, finish and `fsync` the file, and only then remove its lock. Taking
    /// the [`BusRecorder`]s back means no bus can record after this starts; call it once the drives are disabled and
    /// control has ended (logging.md section 8.4), so no event comes after it.
    ///
    /// # Errors
    /// The recording failed earlier, or any of these steps did. The lock then stays, marking the file as not closed
    /// cleanly.
    pub fn close(mut self, buses: Vec<BusRecorder>, wall_ns: u64) -> Result<End, RecordError> {
        let result = self.finish_buses(buses, wall_ns);
        self.check(result)?;
        let health = self.health.clone();
        self.session.close(wall_ns).inspect_err(|_| health.fail())
    }

    fn finish_buses(&mut self, buses: Vec<BusRecorder>, wall_ns: u64) -> Result<(), RecordError> {
        if let Some(reason) = &self.failure {
            return Err(RecordError::Failed(reason.clone()));
        }
        self.drain()?;
        for bus in buses {
            self.session.file.gap(bus.bus(), bus.pending(), wall_ns)?;
        }
        Ok(())
    }
}

/// A [`Recording`] on its own named thread, at normal priority, draining every 10 ms until closed.
pub struct Recorder<W: Sink + 'static = BufWriter<File>> {
    stop: Arc<AtomicBool>,
    health: Health,
    thread: JoinHandle<Recording<W>>,
}

impl<W: Sink + 'static> Recorder<W> {
    /// Start the thread.
    ///
    /// # Errors
    /// The thread can't be spawned.
    pub fn spawn(mut recording: Recording<W>) -> std::io::Result<Self> {
        let stop = Arc::new(AtomicBool::new(false));
        let health = recording.health();
        let thread = std::thread::Builder::new()
            .name("recorder".to_owned())
            .spawn({
                let stop = Arc::clone(&stop);
                move || {
                    while !stop.load(Ordering::Acquire) {
                        let (mono_ns, wall_ns) = clocks(recording.epoch);
                        // A failure is kept in the recording and its health; the thread keeps draining so the
                        // rings stay empty, and close returns the error.
                        let _ = recording.step(mono_ns, wall_ns);
                        std::thread::sleep(DRAIN_PERIOD);
                    }
                    recording
                }
            })?;
        Ok(Self {
            stop,
            health,
            thread,
        })
    }

    /// The recording's health, for the enable gate.
    #[must_use]
    pub fn health(&self) -> Health {
        self.health.clone()
    }

    /// Stop the thread and [`Recording::close`] the session.
    ///
    /// # Errors
    /// As [`Recording::close`], or the thread panicked.
    pub fn close(self, buses: Vec<BusRecorder>) -> Result<End, RecordError> {
        self.stop.store(true, Ordering::Release);
        let recording = self.thread.join().map_err(|_| {
            self.health.fail();
            RecordError::Panicked
        })?;
        let mut recording = recording;
        // A last step reads the clocks afresh for what is drained at the end (control's last events among it); a
        // failure is kept in the recording, and close returns it.
        let (mono_ns, wall_ns) = clocks(recording.epoch);
        let _ = recording.step(mono_ns, wall_ns);
        recording.close(buses, wall_ns)
    }
}

/// `mono_ns` on the wall clock, given the two clocks read together as `mono` and `wall`: the same offset either side of
/// the reading, saturating only at the ends of the range.
fn to_wall(mono_ns: u64, mono: u64, wall: u64) -> u64 {
    let ns = i128::from(wall) + i128::from(mono_ns) - i128::from(mono);
    u64::try_from(ns.max(0)).unwrap_or(u64::MAX)
}

/// The monotonic clock since `epoch` and the wall clock, read together.
fn clocks(epoch: Epoch) -> (u64, u64) {
    let mono = epoch.ns(Instant::now());
    let wall = SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        .map_or(0, |d| u64::try_from(d.as_nanos()).unwrap_or(u64::MAX));
    (mono, wall)
}
