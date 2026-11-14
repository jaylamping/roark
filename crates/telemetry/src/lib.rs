#![doc = include_str!("../README.md")]

mod batch;
mod bus;
mod event;
mod file;
mod recording;
mod session;
pub mod wire;

pub use batch::{Direction, FrameRecord, Loss, MAX_FRAMES_PER_TICK, TickBatch};
pub use bus::{BusRecorder, RING_BATCHES};
pub use event::{Event, EventKind, EventRecorder, Level, RING_EVENTS};
pub use recording::{Epoch, Health, Recorder, Recording};
pub use session::{
    BusInfo, CanFilter, Session, SessionInfo, Sink, SkeletonRef, Stage, TimestampSource,
};

/// Why recording failed.
#[derive(Debug, thiserror::Error)]
pub enum RecordError {
    /// A file or directory operation failed.
    #[error("recording: {0}")]
    Io(#[from] std::io::Error),
    /// The MCAP writer failed.
    #[error("recording: MCAP: {0}")]
    Mcap(#[from] mcap::McapError),
    /// A message didn't serialize.
    #[error("recording: JSON: {0}")]
    Json(#[from] serde_json::Error),
    /// A batch named a bus the session doesn't have.
    #[error("recording: no bus {0} in the session")]
    NoSuchBus(usize),
    /// An earlier write failed, so the file is incomplete.
    #[error("recording failed earlier: {0}")]
    Failed(String),
    /// The recorder thread panicked.
    #[error("recording: the recorder thread panicked")]
    Panicked,
}
