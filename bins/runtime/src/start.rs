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
use skeleton::JointName;
use telemetry::{
    BusInfo, RING_BATCHES, RecordError, Recorder, Recording, Session, SessionInfo, SkeletonRef,
    Stage,
};

use crate::clock::{Schedule, mono_now, wall_ns};
use crate::control::{self, BusEnds, ControlExit, ControlLinks, View};
use crate::dispatch::{BusOrders, StopLatch};
use crate::enable::{Enable, EnableReply, SLOW_RING, SlowEnds};
use crate::plan::{BusPlan, PlanError, offline, plan};
use crate::request::{Clear, Reply, Scope};
use crate::roster::{JointSet, Roster, TooManyJoints, UnknownJoint};

/// Ring sizes: a tick's worth of traffic with room to spare. The bus takes the newest batch, so a few are plenty.
const COMMANDS: usize = 4;
/// Snapshots from a bus: control reads every tick, so a few cover a late pass.
const SNAPSHOTS: usize = 8;
/// Orders to a bus, and re-arm answers back.
const ORDERS: usize = 16;
/// Clears and enables in, their replies and views out.
const REQUESTS: usize = 64;
/// How far out the schedule's origin is, in periods: time for every thread to be spawned and asleep before tick 0 (a
/// spawn takes far less than a period), and short enough that nobody waits on it. A thread that starts late anyway runs
/// from the tick in progress and counts the ones it missed.
const ORIGIN_PERIODS: u64 = 4;
/// `vcan` for every session: the bus layer refuses any other interface until the real adapter is supported (PLAN step
/// 8).
const STAGE: Stage = Stage::Vcan;

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
    /// The git revision the binary was built from, with `-dirty` if the tree had changes.
    pub git_revision: String,
    /// Whether anyone reads [`Runtime::views`]; without a reader control doesn't make them.
    pub views: bool,
}

/// Why the runtime didn't start. Nothing is left running when it doesn't.
#[derive(Debug, thiserror::Error)]
pub enum StartError {
    /// The skeleton didn't load.
    #[error("the skeleton didn't load: {0}")]
    Skeleton(#[from] skeleton::LoadError),
    /// The skeleton's buses can't be run.
    #[error(transparent)]
    Plan(#[from] PlanError),
    /// The skeleton has more joints than the runtime holds.
    #[error(transparent)]
    Roster(#[from] TooManyJoints),
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
    /// The monotonic clock couldn't be read for the schedule.
    #[error("the clock couldn't be read: {0}")]
    Clock(io::Error),
    /// A bus thread couldn't be started.
    #[error(transparent)]
    Bus(#[from] BusRunError),
    /// The start failed, and ending the threads already started didn't end cleanly either. They have all ended.
    #[error("{error}; ending the threads already started: {unwind}")]
    Unwound {
        /// Why the start failed.
        error: Box<StartError>,
        /// How the unwind failed.
        unwind: EndError,
    },
}

/// What the runtime started with, for its startup log (logging.md section 4: startup logs what was checked).
#[derive(Clone, Debug)]
pub struct StartInfo {
    /// The bus threads, in the order replies and views name them.
    pub plans: Vec<BusPlan>,
    /// Each bus socket's settings as the session records them (bitrate, timestamps, receive and error filters), in plan
    /// order.
    pub sockets: Vec<BusInfo>,
    /// Each bus socket's receive buffer as the kernel reports it, in plan order.
    pub receive_buffer_bytes: Vec<usize>,
    /// The joints on no bus.
    pub offline: Vec<JointName>,
    /// Every joint, where it is wired and what its preflight checks, in the order enables and their replies name them.
    pub roster: Roster,
    /// The skeleton file and the hash of exactly the bytes loaded.
    pub skeleton: SkeletonRef,
    /// The session's directory.
    pub session: PathBuf,
}

/// A running runtime: stops, clears and enables in, their replies and each bus's newest snapshot out.
pub struct Runtime {
    /// The operator's clears. Each is answered once per bus its limb is on (by the bus, or refused `Busy`, `BusEnded`
    /// or `Ending`), or once with no bus when the limb is on none (`Offline`). A clear pushed after the run has
    /// [`finished`](Runtime::finished) gets no reply: nobody takes it.
    pub clears: Producer<Clear>,
    /// The answers to clears.
    pub replies: Consumer<Reply>,
    /// The operator's enables, of joints named by [`Runtime::joints`]. Each is answered once: enabled and held, or
    /// refused. An enable pushed after the run has [`finished`](Runtime::finished) gets no reply.
    pub enables: Producer<Enable>,
    /// The answers to enables.
    pub enable_replies: Consumer<EnableReply>,
    /// Each bus's newest snapshot, once a tick, when [`RuntimeConfig::views`] asked for them.
    pub views: Option<Consumer<View>>,
    stops: Arc<StopLatch>,
    finished: Arc<AtomicBool>,
    info: StartInfo,
    threads: Threads,
}

/// How one bus thread ended.
#[derive(Debug)]
pub struct BusEnd {
    /// The interface.
    pub name: String,
    /// Its last snapshot; `None` if it ended before its first tick.
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
pub enum EndError {
    /// A thread panicked. Release builds abort on panic, so only a test build sees this.
    #[error("a thread panicked")]
    Panicked,
    /// The recording didn't close cleanly.
    #[error("the recording didn't close: {0}")]
    Record(#[from] RecordError),
}

/// Every thread the runtime started, ended in one place.
struct Threads {
    /// The run's end, which is also every bus thread's exit flag.
    end: Arc<AtomicBool>,
    control: Option<JoinHandle<ControlExit>>,
    buses: Vec<(String, JoinHandle<BusExit>)>,
    recorder: Option<Recorder>,
}

impl Runtime {
    /// Load the skeleton, start the session, and start every bus thread and the control thread on one schedule origin.
    /// Nothing is enabled: the runtime never enables on its own.
    ///
    /// # Errors
    /// The skeleton, the timing, the session, the clock or a thread failed; any thread already started is ended first.
    pub fn start(config: &RuntimeConfig) -> Result<Self, StartError> {
        // Read once: the session's hash is of exactly the bytes parsed.
        let text = skeleton::read(&config.skeleton)?;
        let skeleton = skeleton::parse(&text)?;
        let plans = plan(&skeleton)?;
        let roster = Roster::new(&skeleton, &plans)?;
        let timing = Timing::at_hz(config.hz);
        timing.check().map_err(|source| StartError::Timing {
            hz: config.hz,
            source,
        })?;
        let skeleton_ref = SkeletonRef::of(&config.skeleton, text.as_bytes());
        let sockets: Vec<BusInfo> = plans
            .iter()
            .map(|p| can::bus_info(&p.name, p.bitrate_bps))
            .collect();
        let session = start_session(config, &skeleton_ref, &sockets)?;
        let session_dir = session.dir().to_path_buf();
        let (recording, recorders) = Recording::new(session, RING_BATCHES);
        let epoch = recording.epoch();
        let mut threads = Threads {
            end: Arc::new(AtomicBool::new(false)),
            control: None,
            buses: Vec::new(),
            recorder: Some(Recorder::spawn(recording).map_err(StartError::Thread)?),
        };

        let start = mono_now() + Duration::from_nanos(ORIGIN_PERIODS * timing.period_ns);
        let mut ends = Vec::new();
        let mut orders = Vec::new();
        let mut slow = Vec::new();
        let mut receive_buffer_bytes = Vec::new();
        for (p, recorder) in plans.iter().zip(recorders) {
            match spawn_bus(p, timing, recorder, epoch, start, &threads.end) {
                Ok(bus) => {
                    threads.buses.push((p.name.clone(), bus.thread));
                    ends.push(bus.ends);
                    orders.push(bus.orders);
                    slow.push(bus.slow);
                    receive_buffer_bytes.push(bus.receive_buffer_bytes);
                }
                Err(e) => return Err(threads.unwind(e.into())),
            }
        }
        // The origin is after the epoch (the recording was made first), so tick times on the epoch are the origin's plus
        // their offset.
        let origin_ns = epoch.ns(start);
        let schedule = match Schedule::new(start, timing.period_ns) {
            Ok(s) => s,
            Err(e) => return Err(threads.unwind(StartError::Clock(e))),
        };
        let stops = Arc::new(StopLatch::default());
        let finished = Arc::new(AtomicBool::new(false));
        let (clears, clears_rx) = RingBuffer::new(REQUESTS);
        let (replies_tx, replies) = RingBuffer::new(REQUESTS);
        let (enables, enables_rx) = RingBuffer::new(REQUESTS);
        let (enable_replies_tx, enable_replies) = RingBuffer::new(REQUESTS);
        let (views_tx, views) = views(config.views);
        let links = ControlLinks {
            buses: ends,
            orders,
            stops: Arc::clone(&stops),
            clears: clears_rx,
            replies: replies_tx,
            roster: roster.clone(),
            slow,
            enables: enables_rx,
            enable_replies: enable_replies_tx,
            views: views_tx,
            end: Arc::clone(&threads.end),
            finished: Arc::clone(&finished),
        };
        let control_plans = plans.clone();
        let control = std::thread::Builder::new()
            .name("control".to_owned())
            .spawn(move || control::run(&control_plans, &schedule, origin_ns, timing, links));
        match control {
            Ok(handle) => threads.control = Some(handle),
            Err(e) => return Err(threads.unwind(StartError::Thread(e))),
        }
        Ok(Self {
            clears,
            replies,
            enables,
            enable_replies,
            views,
            stops,
            finished,
            info: StartInfo {
                plans,
                sockets,
                receive_buffer_bytes,
                offline: offline(&skeleton),
                roster,
                skeleton: skeleton_ref,
                session: session_dir,
            },
            threads,
        })
    }

    /// What the runtime started with.
    #[must_use]
    pub const fn info(&self) -> &StartInfo {
        &self.info
    }

    /// The session's directory.
    #[must_use]
    pub fn session(&self) -> &Path {
        &self.info.session
    }

    /// The joints named, for an [`Enable`].
    ///
    /// # Errors
    /// The first name the skeleton doesn't have.
    pub fn joints<'a>(
        &self,
        names: impl IntoIterator<Item = &'a str>,
    ) -> Result<JointSet, UnknownJoint> {
        self.info.roster.set(names)
    }

    /// The operator's stop of `scope`: always accepted, never waits, and taken by control ahead of any clear on its
    /// next pass (PLAN item 3a).
    pub fn stop(&self, scope: Scope) {
        self.stops.ask(scope);
    }

    /// Set once the control thread has ended: after [`Runtime::end`], or on its own when its clock failed or a bus
    /// thread ended, in which case every bus has stopped its drives and the owner should end the runtime.
    #[must_use]
    pub fn finished(&self) -> Arc<AtomicBool> {
        Arc::clone(&self.finished)
    }

    /// End the run: every bus stops its limbs and ends once control has taken a snapshot showing every limb at rest (or,
    /// should control stop reading, after its exit wait's limit), then control ends and the recording closes. Clears
    /// still queued are refused `Ending`.
    ///
    /// # Errors
    /// A thread panicked, or the recording didn't close cleanly.
    pub fn end(mut self) -> Result<RuntimeExit, EndError> {
        self.threads.end()
    }
}

impl Drop for Runtime {
    /// A runtime dropped without [`Runtime::end`] still stops its drives and ends its threads.
    fn drop(&mut self) {
        if self.threads.running() {
            // A drop has nobody to hand the error to, and every thread has ended either way (EndError says so); the
            // owner who wants the outcome calls `end`.
            let _ = self.threads.end();
        }
    }
}

impl Threads {
    fn running(&self) -> bool {
        self.control.is_some() || !self.buses.is_empty() || self.recorder.is_some()
    }

    /// End every thread after a failed start, keeping the start's error first.
    fn unwind(mut self, error: StartError) -> StartError {
        match self.end() {
            Ok(_) => error,
            Err(unwind) => StartError::Unwound {
                error: Box::new(error),
                unwind,
            },
        }
    }

    /// Ask every thread to end and join them: control (which takes the buses' last snapshots while they stop), then
    /// the buses, then the recorder. With no control thread, nobody takes the buses' snapshots; they end on their exit
    /// wait's limit.
    fn end(&mut self) -> Result<RuntimeExit, EndError> {
        self.end.store(true, Ordering::Release);
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
        for (name, handle) in self.buses.drain(..) {
            match handle.join() {
                Ok(exit) => {
                    recorders.push(exit.recorder);
                    buses.push(BusEnd {
                        name,
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
            return Err(EndError::Panicked);
        }
        Ok(RuntimeExit {
            buses,
            control,
            recording,
        })
    }
}

/// The session, recorded with what the runtime starts from.
fn start_session(
    config: &RuntimeConfig,
    skeleton: &SkeletonRef,
    sockets: &[BusInfo],
) -> Result<Session, RecordError> {
    Session::start(
        &config.sessions,
        SessionInfo {
            git_revision: config.git_revision.clone(),
            operator: config.operator.clone(),
            stage: STAGE,
            skeleton: skeleton.clone(),
            buses: sockets.to_vec(),
        },
        wall_ns(),
    )
}

/// The views' ring, when anyone reads them.
fn views(on: bool) -> (Option<Producer<View>>, Option<Consumer<View>>) {
    if on {
        let (tx, rx) = RingBuffer::new(REQUESTS);
        (Some(tx), Some(rx))
    } else {
        (None, None)
    }
}

/// A bus thread as started.
struct SpawnedBus {
    thread: JoinHandle<BusExit>,
    /// Control's ends of its rings.
    ends: BusEnds,
    orders: BusOrders,
    slow: SlowEnds,
    receive_buffer_bytes: usize,
}

/// One bus thread, control's ends of its rings, and its socket's receive buffer.
fn spawn_bus(
    p: &BusPlan,
    timing: Timing,
    recorder: telemetry::BusRecorder,
    epoch: telemetry::Epoch,
    start: std::time::Instant,
    exit: &Arc<AtomicBool>,
) -> Result<SpawnedBus, BusRunError> {
    let (commands, commands_rx) = RingBuffer::new(COMMANDS);
    let (snapshots_tx, snapshots) = RingBuffer::new(SNAPSHOTS);
    let (orders, orders_rx): (Producer<_>, Consumer<_>) = RingBuffer::new(ORDERS);
    let (rearmed_tx, rearmed) = RingBuffer::new(ORDERS);
    let (requests_tx, requests) = RingBuffer::new(SLOW_RING);
    let (results, results_rx) = RingBuffer::new(SLOW_RING);
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
            requests,
            results,
            orders: orders_rx,
            rearmed: rearmed_tx,
            epoch,
            start,
            exit: Arc::clone(exit),
        },
    )?;
    Ok(SpawnedBus {
        thread: spawned.thread,
        ends: BusEnds {
            commands,
            snapshots,
            rearmed,
        },
        orders: BusOrders::new(orders),
        slow: SlowEnds::new(requests_tx, results_rx),
        receive_buffer_bytes: spawned.receive_buffer_bytes,
    })
}
