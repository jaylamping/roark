//! Starting and ending the runtime on Linux: the session, one bus thread per planned bus and the control thread, all on
//! one schedule origin, wired with bounded rings made before the first tick.

use std::io;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::thread::JoinHandle;
use std::time::Duration;

use can::{BusConfig, BusExit, BusLinks, BusRunError, Counters, Snapshot, Timing, TimingError};
use rtrb::{Consumer, Producer, RingBuffer};
use telemetry::{
    RING_BATCHES, RecordError, Recorder, Recording, Session, SessionInfo, SkeletonRef, Stage,
};

use crate::clock::{Schedule, mono_now, wall_ns};
use crate::control::{self, BusEnds, ControlExit, ControlLinks, View};
use crate::plan::{BusPlan, PlanError, plan};
use crate::request::{Reply, Request};

/// Ring sizes: a tick's worth of traffic with room to spare. The bus takes the newest batch, so a few are plenty.
const COMMANDS: usize = 4;
/// Snapshots from a bus: control reads every tick, so a few cover a late pass.
const SNAPSHOTS: usize = 8;
/// Orders to a bus, and re-arm answers back.
const ORDERS: usize = 16;
/// Requests in, replies and views out.
const REQUESTS: usize = 64;

/// How the runtime is started.
#[derive(Clone, Debug)]
pub struct RuntimeConfig {
    /// The skeleton file (`config/skeleton.yaml`).
    pub skeleton: PathBuf,
    /// Where sessions are recorded (`/var/lib/robot/sessions` on the Pi).
    pub sessions: PathBuf,
    /// Ticks a second, every bus alike (250 by default, PLAN item 3).
    pub hz: u64,
    /// Who started it, for the session's header.
    pub operator: String,
    /// The git revision the binary was built from.
    pub git_revision: String,
}

/// Why the runtime didn't start. Nothing is left running when it doesn't.
#[derive(Debug, thiserror::Error)]
pub enum StartError {
    /// The skeleton didn't load.
    #[error("the skeleton didn't load: {0}")]
    Skeleton(#[from] skeleton::LoadError),
    /// The skeleton file couldn't be read for its hash.
    #[error("the skeleton file couldn't be read: {0}")]
    SkeletonFile(io::Error),
    /// The skeleton's buses can't be run.
    #[error(transparent)]
    Plan(#[from] PlanError),
    /// The tick rate gives timing the bus layer refuses.
    #[error("{hz} Hz: {source}")]
    Timing {
        /// The rate asked for.
        hz: u64,
        /// Why it's refused.
        source: TimingError,
    },
    /// The session couldn't be started or recorded.
    #[error("the session couldn't start: {0}")]
    Record(#[from] RecordError),
    /// A thread couldn't be started.
    #[error("a thread couldn't start: {0}")]
    Thread(io::Error),
    /// A bus thread couldn't be started.
    #[error(transparent)]
    Bus(#[from] BusRunError),
}

/// A running runtime: requests in, replies and each bus's newest snapshot out.
pub struct Runtime {
    /// The operator's requests.
    pub requests: Producer<Request>,
    /// One reply per clear and bus, or one refusal.
    pub replies: Consumer<Reply>,
    /// Each bus's newest snapshot, once a tick.
    pub views: Consumer<View>,
    plans: Vec<BusPlan>,
    session: PathBuf,
    end: Arc<AtomicBool>,
    bus_exit: Arc<AtomicBool>,
    control: Option<JoinHandle<ControlExit>>,
    buses: Vec<JoinHandle<BusExit>>,
    recorder: Option<Recorder>,
}

/// How one bus thread ended.
#[derive(Debug)]
pub struct BusEnd {
    /// The interface.
    pub name: String,
    /// Its last snapshot.
    pub last: Option<Snapshot>,
    /// Its counters as it ended.
    pub counters: Counters,
    /// The first socket or clock error it met.
    pub error: Option<io::Error>,
}

/// How the runtime ended.
#[derive(Debug)]
pub struct RuntimeExit {
    /// Each bus thread, in plan order.
    pub buses: Vec<BusEnd>,
    /// The control thread.
    pub control: ControlExit,
    /// The recording's totals.
    pub recording: telemetry::wire::End,
}

/// Why the runtime didn't end cleanly. Every thread has ended either way.
#[derive(Debug, thiserror::Error)]
pub enum StopError {
    /// A thread panicked. Release builds abort on panic, so only a test build sees this.
    #[error("a thread panicked")]
    Panicked,
    /// The recording didn't close cleanly.
    #[error("the recording didn't close: {0}")]
    Record(#[from] RecordError),
}

impl Runtime {
    /// Load the skeleton, start the session, and start every bus thread and the control thread on one schedule origin.
    /// Nothing is enabled: the runtime never enables on its own.
    ///
    /// # Errors
    /// The skeleton, the timing, the session or a thread failed; any thread already started is ended first.
    pub fn start(config: &RuntimeConfig) -> Result<Self, StartError> {
        let skeleton = skeleton::load(&config.skeleton)?;
        let plans = plan(&skeleton)?;
        let timing = Timing::at_hz(config.hz);
        timing.check().map_err(|source| StartError::Timing {
            hz: config.hz,
            source,
        })?;
        let info = SessionInfo {
            git_revision: config.git_revision.clone(),
            operator: config.operator.clone(),
            stage: stage(&plans),
            skeleton: SkeletonRef::read(&config.skeleton).map_err(StartError::SkeletonFile)?,
            buses: plans
                .iter()
                .map(|p| can::bus_info(&p.name, p.bitrate_bps))
                .collect(),
        };
        let session = Session::start(&config.sessions, info, wall_ns())?;
        let session_dir = session.dir().to_path_buf();
        let (recording, recorders) = Recording::new(session, RING_BATCHES);
        let epoch = recording.epoch();
        let recorder = Recorder::spawn(recording).map_err(StartError::Thread)?;

        // One origin for every thread, a few ticks out so each is waiting before tick 0.
        let start = mono_now() + Duration::from_nanos(4 * timing.period_ns);
        let end = Arc::new(AtomicBool::new(false));
        let bus_exit = Arc::new(AtomicBool::new(false));
        let mut runtime = Self {
            requests: RingBuffer::new(REQUESTS).0,
            replies: RingBuffer::new(REQUESTS).1,
            views: RingBuffer::new(REQUESTS).1,
            plans: plans.clone(),
            session: session_dir,
            end: Arc::clone(&end),
            bus_exit: Arc::clone(&bus_exit),
            control: None,
            buses: Vec::new(),
            recorder: Some(recorder),
        };
        let mut ends = Vec::new();
        for (p, recorder) in plans.iter().zip(recorders) {
            match spawn_bus(p, timing, recorder, epoch, start, &bus_exit) {
                Ok((thread, bus_ends)) => {
                    runtime.buses.push(thread);
                    ends.push(bus_ends);
                }
                Err(e) => {
                    let _ = runtime.end_threads();
                    return Err(e.into());
                }
            }
        }
        let (requests, requests_rx) = RingBuffer::new(REQUESTS);
        let (replies_tx, replies) = RingBuffer::new(REQUESTS);
        let (views_tx, views) = RingBuffer::new(REQUESTS);
        let links = ControlLinks {
            buses: ends,
            requests: requests_rx,
            replies: replies_tx,
            views: views_tx,
            end,
            bus_exit,
        };
        let schedule = match Schedule::new(start, timing.period_ns) {
            Ok(s) => s,
            Err(e) => {
                let _ = runtime.end_threads();
                return Err(StartError::Thread(e));
            }
        };
        let control = std::thread::Builder::new()
            .name("control".to_owned())
            .spawn(move || control::run(&plans, &schedule, epoch, timing, links));
        match control {
            Ok(handle) => runtime.control = Some(handle),
            Err(e) => {
                let _ = runtime.end_threads();
                return Err(StartError::Thread(e));
            }
        }
        runtime.requests = requests;
        runtime.replies = replies;
        runtime.views = views;
        Ok(runtime)
    }

    /// The bus threads, in the order replies and views name them.
    #[must_use]
    pub fn plans(&self) -> &[BusPlan] {
        &self.plans
    }

    /// The session's directory.
    #[must_use]
    pub fn session(&self) -> &Path {
        &self.session
    }

    /// End the run: every bus stops its limbs and ends once control has taken a snapshot showing every limb stopped,
    /// then control ends and the recording closes.
    ///
    /// # Errors
    /// A thread panicked, or the recording didn't close cleanly.
    pub fn stop(mut self) -> Result<RuntimeExit, StopError> {
        self.end_threads()
    }

    /// Ask every thread to end and join them: control (which takes the buses' last snapshots while they stop), then
    /// the buses, then the recorder.
    fn end_threads(&mut self) -> Result<RuntimeExit, StopError> {
        self.end.store(true, Ordering::Release);
        // With no control thread, nobody takes the buses' snapshots; they end on their exit wait's limit.
        self.bus_exit.store(true, Ordering::Release);
        let mut panicked = false;
        let control = match self.control.take().map(JoinHandle::join) {
            Some(Ok(exit)) => exit,
            Some(Err(_)) => {
                panicked = true;
                ControlExit::default()
            }
            None => ControlExit::default(),
        };
        let mut buses = Vec::new();
        let mut recorders = Vec::new();
        for (handle, p) in self.buses.drain(..).zip(&self.plans) {
            match handle.join() {
                Ok(exit) => {
                    recorders.push(exit.recorder);
                    buses.push(BusEnd {
                        name: p.name.clone(),
                        last: exit.last,
                        counters: exit.counters,
                        error: exit.error,
                    });
                }
                Err(_) => panicked = true,
            }
        }
        let recording = match self.recorder.take() {
            Some(r) => r.close(recorders)?,
            None => telemetry::wire::End { buses: Vec::new() },
        };
        if panicked {
            return Err(StopError::Panicked);
        }
        Ok(RuntimeExit {
            buses,
            control,
            recording,
        })
    }
}

impl Drop for Runtime {
    /// A runtime dropped without [`Runtime::stop`] still stops its drives and ends its threads.
    fn drop(&mut self) {
        if self.control.is_some() || !self.buses.is_empty() || self.recorder.is_some() {
            let _ = self.end_threads();
        }
    }
}

/// One bus thread and control's ends of its rings.
fn spawn_bus(
    p: &BusPlan,
    timing: Timing,
    recorder: telemetry::BusRecorder,
    epoch: telemetry::Epoch,
    start: std::time::Instant,
    exit: &Arc<AtomicBool>,
) -> Result<(JoinHandle<BusExit>, BusEnds), BusRunError> {
    let (commands, commands_rx) = RingBuffer::new(COMMANDS);
    let (snapshots_tx, snapshots) = RingBuffer::new(SNAPSHOTS);
    let (orders, orders_rx) = RingBuffer::new(ORDERS);
    let (rearmed_tx, rearmed) = RingBuffer::new(ORDERS);
    let spawned = can::spawn(
        BusConfig {
            name: p.name.clone(),
            drives: p.drives.clone(),
            timing,
        },
        BusLinks {
            commands: commands_rx,
            snapshots: snapshots_tx,
            recorder,
            // No slow requests yet: preflight comes with the control step that runs it (4b-2).
            requests: RingBuffer::new(1).1,
            results: RingBuffer::new(1).0,
            orders: orders_rx,
            rearmed: rearmed_tx,
            epoch,
            start,
            exit: Arc::clone(exit),
        },
    )?;
    Ok((
        spawned.thread,
        BusEnds {
            commands,
            snapshots,
            orders,
            rearmed,
        },
    ))
}

/// `vcan` for interfaces named so in sim: the bus layer refuses any other until the real adapter is supported (PLAN step
/// 8), so every session today runs on `vcan`.
const fn stage(_plans: &[BusPlan]) -> Stage {
    Stage::Vcan
}
