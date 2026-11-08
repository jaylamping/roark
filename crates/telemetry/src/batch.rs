//! What a bus thread hands the recorder each tick: plain `Copy` data in a fixed-size slot, so handing it over never
//! allocates.

use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

/// The most frames one tick's batch holds. Sized for every drive on a bus answering twice (command echo and reply) with
/// room for late replies, parameter traffic and error frames; frames past it are counted in [`TickBatch::omitted`].
pub const MAX_FRAMES_PER_TICK: usize = 64;

/// Where a frame came from, from the kernel's flags on the receiving socket (logging.md section 8.2).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum Direction {
    /// From another node on the bus: a drive.
    Rx,
    /// Our own frame coming back from the kernel (`MSG_CONFIRM`), which marks that it left this socket.
    TxEcho,
    /// Sent by another program on this host (`MSG_DONTROUTE` without `MSG_CONFIRM`). Never on the robot; on `vcan`,
    /// every simulated drive's reply.
    TxOther,
}

/// One CAN frame as the bus thread saw it, with the fields the ASAM MDF4 bus-logging standard keeps.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct FrameRecord {
    /// The raw 29-bit or 11-bit ID.
    pub id: u32,
    /// A 29-bit ID.
    pub extended: bool,
    /// An error frame (the ID holds the error class).
    pub error: bool,
    /// A remote frame.
    pub remote: bool,
    /// Data length, 0 to 8.
    pub len: u8,
    /// Data; bytes past `len` are ignored.
    pub data: [u8; 8],
    /// The kernel's receive timestamp, nanoseconds since the Unix epoch.
    pub stamp_ns: u64,
    /// Where it came from.
    pub direction: Direction,
}

impl FrameRecord {
    /// An empty slot.
    const EMPTY: Self = Self {
        id: 0,
        extended: false,
        error: false,
        remote: false,
        len: 0,
        data: [0; 8],
        stamp_ns: 0,
        direction: Direction::Rx,
    };

    /// The data bytes `len` covers.
    #[must_use]
    pub fn payload(&self) -> &[u8] {
        let len = usize::from(self.len).min(self.data.len());
        self.data.get(..len).unwrap_or_default()
    }
}

/// Batches a bus lost before the recorder got them: the ring was full, so the bus thread dropped them rather than wait.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct Loss {
    /// Batches dropped.
    pub batches: u64,
    /// Frames in them, counting each batch's omitted frames.
    pub frames: u64,
    /// The first dropped batch's tick.
    pub first_tick: u64,
    /// The last dropped batch's tick.
    pub last_tick: u64,
}

impl Loss {
    pub(crate) fn add(&mut self, batch: &TickBatch) {
        if self.batches == 0 {
            self.first_tick = batch.tick;
        }
        self.batches += 1;
        self.frames += batch.frames().len() as u64 + u64::from(batch.omitted);
        self.last_tick = batch.tick;
    }

    pub(crate) fn is_empty(&self) -> bool {
        self.batches == 0
    }
}

/// One bus's tick: every frame the bus thread read or sent in it, in order, plus the tick's own clocks.
#[derive(Clone, Copy, Debug)]
pub struct TickBatch {
    /// The tick number, counting from the bus thread's start.
    pub tick: u64,
    /// The tick's start on the monotonic clock, nanoseconds since the session's [`Epoch`](crate::Epoch).
    pub mono_ns: u64,
    /// The tick's start on the wall clock, nanoseconds since the Unix epoch. The recording's envelope times.
    pub wall_ns: u64,
    /// False while the bus is unhealthy (error passive, bus-off, interface down).
    pub valid: bool,
    /// The socket's overflow counter (`SO_RXQ_OVFL`): frames the kernel dropped before the bus thread read them.
    pub kernel_drops: u32,
    omitted: u32,
    len: usize,
    frames: [FrameRecord; MAX_FRAMES_PER_TICK],
    pub(crate) lost_before: Loss,
}

impl TickBatch {
    /// An empty batch for a healthy bus.
    #[must_use]
    pub fn new(tick: u64, mono_ns: u64, wall_ns: u64) -> Self {
        Self {
            tick,
            mono_ns,
            wall_ns,
            valid: true,
            kernel_drops: 0,
            omitted: 0,
            len: 0,
            frames: [FrameRecord::EMPTY; MAX_FRAMES_PER_TICK],
            lost_before: Loss::default(),
        }
    }

    /// Add a frame. A full batch keeps the frames it has and counts this one in [`Self::omitted`]; returns whether it
    /// was kept.
    pub fn push(&mut self, frame: FrameRecord) -> bool {
        if let Some(slot) = self.frames.get_mut(self.len) {
            *slot = frame;
            self.len += 1;
            true
        } else {
            self.omitted = self.omitted.saturating_add(1);
            false
        }
    }

    /// The frames kept, in order.
    #[must_use]
    pub fn frames(&self) -> &[FrameRecord] {
        self.frames.get(..self.len).unwrap_or_default()
    }

    /// Frames that arrived after the batch was full.
    #[must_use]
    pub fn omitted(&self) -> u32 {
        self.omitted
    }
}
