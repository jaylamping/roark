//! (rt) One bus's thread on Linux: the socket, the absolute-deadline loop around [`BusTick`], and the recording.

use std::io;
use std::os::fd::AsFd;
use std::process::Command;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::thread::JoinHandle;
use std::time::{Duration, Instant, SystemTime};

use nix::sys::time::TimeSpec;
use nix::time::{ClockId, ClockNanosleepFlags, clock_gettime, clock_nanosleep};
use robstride::Frame;
use rtrb::{Consumer, Producer};
use socketcan::{CanDataFrame, CanSocket, EmbeddedFrame, ExtendedId, Socket, SocketOptions};
use telemetry::{BusInfo, BusRecorder, Epoch, TickBatch, TimestampSource};

use crate::error_frame::BusError;
use crate::sys;
use crate::tick::BusTick;
use crate::timing::Timing;
use crate::types::{BusDrive, CommandBatch, ConfigError, Drain, SendList, SendOutcome, Snapshot};

/// The most frames a tick's drain may find before the send. More than that queued means the thread can't tell what the
/// bus said in time, so it stops (1 Mbit/s carries about 8,000 frames a second: 32 a tick at 250 Hz).
const DRAIN_MAX: usize = 256;
/// The most frames a drain reads. A real bus can't refill the socket faster than it is read, so a drain empties it
/// long before this; only a flood on `vcan` reaches it, and then the tick's reads may predate its sends.
const DRAIN_LIMIT: usize = 8 * DRAIN_MAX;
/// The receive buffer asked for. The kernel charges each queued frame its whole buffer (about 0.6 to 1 KiB, not 16
/// bytes), so this holds about a third of a second of a saturated bus; without `CAP_NET_ADMIN` it is capped at
/// `rmem_max`. An overflow is counted (`SO_RXQ_OVFL`), and [`DRAIN_MAX`] stops the bus long before either limit.
const RCVBUF_BYTES: libc::c_int = 1 << 20;

/// The error classes the socket reports: every one (`CAN_ERR_MASK`).
const ERROR_FILTER: u32 = libc::CAN_ERR_MASK;

/// The session's record of the socket [`spawn`] opens on `bus`: the settings `open` applies. The error filter comes from
/// the same constant; the timestamp source and the empty receive filter are stated here and must change with `open`.
/// `bitrate` is the skeleton's.
#[must_use]
pub fn bus_info(bus: &str, bitrate: u32) -> BusInfo {
    BusInfo {
        name: bus.to_owned(),
        bitrate,
        // Kernel stamps until the real adapter's hardware stamps are supported (PLAN step 8).
        timestamps: TimestampSource::Software,
        // Every ID: a kernel filter would hide a duplicate sender (can.md section 2).
        receive_filters: Vec::new(),
        error_filter: ERROR_FILTER,
        adapter_firmware: None,
    }
}

/// What a bus thread needs.
#[derive(Clone, Debug)]
pub struct BusConfig {
    /// The interface, as the skeleton names it.
    pub name: String,
    /// The drives the skeleton puts on it, in slot order, each with its limb's index on this bus.
    pub drives: Vec<BusDrive>,
    /// The tick.
    pub timing: Timing,
}

/// Why a bus can't start or stopped running.
#[derive(Debug, thiserror::Error)]
pub enum BusRunError {
    /// The interface isn't `vcan`. Real adapters come with their driver and bitrate checks (PLAN step 8).
    #[error(
        "{bus} is not a vcan interface; the bus layer runs only on vcan until the real adapter's checks exist"
    )]
    NotVcan {
        /// The interface.
        bus: String,
    },
    /// The interface's kind couldn't be read, so it isn't opened.
    #[error("{bus}: can't tell what kind of interface it is: {reason}")]
    Unchecked {
        /// The interface.
        bus: String,
        /// Why not.
        reason: String,
    },
    /// The drive table or timing is one the tick refuses.
    #[error("{bus}: {source}")]
    Config {
        /// The interface.
        bus: String,
        /// What the tick refused.
        source: ConfigError,
    },
    /// Opening or setting up the socket failed.
    #[error("{bus}: {source}")]
    Socket {
        /// The interface.
        bus: String,
        /// What failed.
        source: io::Error,
    },
    /// The bus thread couldn't be started.
    #[error("{bus}: can't start the bus thread: {source}")]
    Thread {
        /// The interface.
        bus: String,
        /// What failed.
        source: io::Error,
    },
}

/// What a bus thread hands back when it ends.
#[derive(Debug)]
pub struct BusExit {
    /// The recorder producer, for `telemetry::Recording::close`.
    pub recorder: BusRecorder,
    /// The last snapshot made, whether or not control's ring took it; `None` if the thread ended before its first. One
    /// the ring couldn't take counts itself in `counters.snapshots_dropped`, so a control that stopped reading still
    /// learns from here that it never got it.
    pub last: Option<Snapshot>,
    /// The first socket or clock error the thread met, if any. Most end the thread; one in the sleep or drain of the
    /// tick it returns at after deciding its exit ([`BusLinks::exit`]) is reported too, though it returns there all the
    /// same. That tick makes no snapshot, so `last` is then the snapshot with every limb stopped that decided the
    /// exit, made before the error and healthy as far as it knew.
    pub error: Option<io::Error>,
}

/// A started bus thread.
#[derive(Debug)]
pub struct Spawned {
    /// The thread, named `bus-<name>`; joining it gives its [`BusExit`].
    pub thread: JoinHandle<BusExit>,
    /// The socket's receive buffer as the kernel reports it (`SO_RCVBUF`, which Linux doubles for its bookkeeping),
    /// for the runtime's startup log: without `CAP_NET_ADMIN` the kernel caps it at `rmem_max`.
    pub receive_buffer_bytes: usize,
}

/// The rings and flags a bus thread runs with, all made before the first tick.
pub struct BusLinks {
    /// Command batches from control; the newest one each tick is used.
    pub commands: Consumer<CommandBatch>,
    /// Snapshots out. When control falls behind and the ring is full, the newest is dropped and counted
    /// (`Counters::snapshots_dropped`), so control must keep up.
    pub snapshots: Producer<Snapshot>,
    /// This bus's recorder ring.
    pub recorder: BusRecorder,
    /// The session's monotonic zero.
    pub epoch: Epoch,
    /// Tick 0's start, shared by every bus thread and the control thread so their tick numbers name the same instant.
    /// A thread started after it begins at the first tick not yet due.
    pub start: Instant,
    /// Set to end the thread. A bus whose limbs are all idle returns at once. Any other is stopped first: every limb
    /// not already stopping or stopped is stopped (an idle one too, so every drive gets its Disable and reporting off,
    /// PLAN.md item 2 Exit), a stopping one finishes its stop. Then the thread returns at the first of three: control's
    /// ring has taken a snapshot with every limb stopped ([`Snapshot::stopped`]); control has dropped its end of the
    /// ring; or one stop window (`Timing::stop_confirm_ns`) of such snapshots, in ticks, has gone untaken (a control
    /// that stopped reading must not hold the join). It returns at the next tick's drain, so the frames still in the
    /// socket are recorded, and the last snapshot made is [`BusExit::last`] in every case. A socket or clock error ends
    /// the thread without `exit`, once a snapshot with every limb stopped is made, taken or not; a clock that can't be
    /// read at the start ends it before any snapshot.
    pub exit: Arc<AtomicBool>,
}

/// Open the bus and start its thread, named `bus-<name>`.
///
/// # Errors
/// [`BusRunError`] before any frame is sent.
pub fn spawn(config: BusConfig, links: BusLinks) -> Result<Spawned, BusRunError> {
    let tick =
        BusTick::new(&config.drives, config.timing).map_err(|source| BusRunError::Config {
            bus: config.name.clone(),
            source,
        })?;
    let socket = open(&config.name)?;
    let receive_buffer_bytes =
        sys::receive_buffer(socket.as_fd()).map_err(|source| BusRunError::Socket {
            bus: config.name.clone(),
            source,
        })?;
    let thread = std::thread::Builder::new()
        .name(format!("bus-{}", config.name))
        .spawn(move || run(&socket, tick, links))
        .map_err(|source| BusRunError::Thread {
            bus: config.name,
            source,
        })?;
    Ok(Spawned {
        thread,
        receive_buffer_bytes,
    })
}

/// Open `bus` with can.md section 2's settings: error frames on, loopback on, our own frames back (so they record as
/// `tx_echo`), every ID accepted (so unexpected senders stay visible), kernel timestamps, the overflow counter, a large
/// receive buffer, non-blocking. [`bus_info`] records the same settings.
fn open(bus: &str) -> Result<CanSocket, BusRunError> {
    let vcan = is_vcan(bus).map_err(|reason| BusRunError::Unchecked {
        bus: bus.to_owned(),
        reason,
    })?;
    if !vcan {
        return Err(BusRunError::NotVcan {
            bus: bus.to_owned(),
        });
    }
    let err = |source| BusRunError::Socket {
        bus: bus.to_owned(),
        source,
    };
    let socket = CanSocket::open(bus).map_err(err)?;
    socket.set_error_filter(ERROR_FILTER).map_err(err)?;
    socket.set_loopback(true).map_err(err)?;
    socket.set_recv_own_msgs(true).map_err(err)?;
    socket.set_filter_accept_all().map_err(err)?;
    socket
        .set_socket_option_int(libc::SOL_SOCKET, libc::SO_TIMESTAMPNS_NEW, 1)
        .map_err(err)?;
    socket
        .set_socket_option_int(libc::SOL_SOCKET, libc::SO_RXQ_OVFL, 1)
        .map_err(err)?;
    // SO_RCVBUFFORCE needs CAP_NET_ADMIN; without it the kernel caps SO_RCVBUF at rmem_max. `spawn` reads back what
    // the kernel gave, for the runtime to log.
    if socket
        .set_socket_option_int(libc::SOL_SOCKET, libc::SO_RCVBUFFORCE, RCVBUF_BYTES)
        .is_err()
    {
        socket
            .set_socket_option_int(libc::SOL_SOCKET, libc::SO_RCVBUF, RCVBUF_BYTES)
            .map_err(err)?;
    }
    socket.set_nonblocking(true).map_err(err)?;
    Ok(socket)
}

/// Whether `bus` is a `vcan` interface, from `ip -details -json`, or why that can't be read. `ip ... show dev` prints
/// one link with at most one `info_kind`, so the pair appearing is the answer; a plain device such as `lo` has none.
fn is_vcan(bus: &str) -> Result<bool, String> {
    if bus.is_empty() || bus.starts_with('-') {
        return Err(format!("{bus:?} is not an interface name"));
    }
    let out = Command::new("ip")
        .args(["-details", "-json", "link", "show", "dev", bus])
        .output()
        .map_err(|e| format!("can't run ip: {e}"))?;
    if !out.status.success() {
        return Err(String::from_utf8_lossy(&out.stderr).trim().to_owned());
    }
    Ok(String::from_utf8_lossy(&out.stdout).contains(r#""info_kind":"vcan""#))
}

/// The bus's clocks: the loop's schedule on `CLOCK_MONOTONIC` (absolute sleeps) and the session's epoch for stamps.
struct Clock {
    start: Instant,
    start_ts: TimeSpec,
    epoch: Epoch,
}

impl Clock {
    /// The schedule from `start`, read against `CLOCK_MONOTONIC` (which `Instant` is on Linux) once, now.
    fn new(epoch: Epoch, start: Instant) -> io::Result<Self> {
        // Two reads of one clock: the sleep base first, so the gap between them makes every wake measure early, never
        // late.
        let now_ts = clock_gettime(ClockId::CLOCK_MONOTONIC).map_err(io::Error::from)?;
        let now = mono_now();
        let start_ts = if start >= now {
            now_ts + TimeSpec::from_duration(start.duration_since(now))
        } else {
            now_ts - TimeSpec::from_duration(now.duration_since(start))
        };
        Ok(Self {
            start,
            start_ts,
            epoch,
        })
    }

    /// Sleep until `at` on the monotonic clock, absolute, so a slow tick never shifts the next.
    fn sleep_until(&self, at: Instant) -> io::Result<()> {
        let offset = at.saturating_duration_since(self.start);
        let target = self.start_ts + TimeSpec::from_duration(offset);
        loop {
            match clock_nanosleep(
                ClockId::CLOCK_MONOTONIC,
                ClockNanosleepFlags::TIMER_ABSTIME,
                &target,
            ) {
                Err(nix::errno::Errno::EINTR) => {}
                Ok(_) => return Ok(()),
                Err(e) => return Err(e.into()),
            }
        }
    }

    /// The tick whose period `now` falls in: its start has passed, the next one's hasn't.
    fn tick_at(&self, now: Instant, period_ns: u64) -> u64 {
        let elapsed = now.saturating_duration_since(self.start).as_nanos();
        u64::try_from(elapsed / u128::from(period_ns)).unwrap_or(u64::MAX)
    }

    /// The first tick whose start hasn't passed: 0 when the thread starts before the schedule does.
    fn first_due(&self, period_ns: u64) -> u64 {
        let behind = mono_now().saturating_duration_since(self.start).as_nanos();
        u64::try_from(behind.div_ceil(u128::from(period_ns))).unwrap_or(u64::MAX)
    }

    /// Tick `n`'s scheduled start.
    fn at(&self, n: u64, period_ns: u64) -> Instant {
        self.start + Duration::from_nanos(n.saturating_mul(period_ns))
    }

    fn ns(&self, at: Instant) -> u64 {
        self.epoch.ns(at)
    }
}

/// The monotonic clock, read only here and in [`wall_ns`]: the tick itself is handed time (clippy.toml).
#[expect(
    clippy::disallowed_methods,
    reason = "the shell is where the bus reads its clock"
)]
fn mono_now() -> Instant {
    Instant::now()
}

/// The wall clock, for the recording's `wall_ns` only.
#[expect(
    clippy::disallowed_methods,
    reason = "the recording stamps each tick with wall time (logging.md)"
)]
fn wall_ns() -> u64 {
    SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        .map_or(0, |d| u64::try_from(d.as_nanos()).unwrap_or(u64::MAX))
}

/// Sleep for `span`, relative: only when the monotonic clock itself failed, so the stop still has ticks to run in.
#[expect(
    clippy::disallowed_methods,
    reason = "the fallback when the absolute sleep can't read the clock"
)]
fn sleep_relative(span: Duration) {
    std::thread::sleep(span);
}

/// A bus told to exit waits for control's ring to take a snapshot with every limb stopped, but not for ever.
struct ExitWait {
    /// The all-stopped snapshots made after `exit` that the ring may leave untaken before the thread returns anyway:
    /// one stop window (`Timing::stop_confirm_ns`, 100 ms by default) in ticks of this bus, rounded up; `Timing::check`
    /// makes the window at least a period, so at least one. The shutdown already gives the drives that window to
    /// confirm their Disables; a control that is alive reads its ring well inside one more, and one that isn't must not
    /// hold the join (and the recorder's close). Provisional, like the stop window itself: tuned with the rest of the
    /// timing on the real adapter (PLAN step 8).
    limit: u64,
    /// Those made so far.
    untaken: u64,
    /// Whether the ring has taken an all-stopped snapshot, before `exit` or after.
    took_stopped: bool,
}

impl ExitWait {
    fn new(timing: Timing) -> Self {
        Self {
            limit: timing.stop_confirm_ns.div_ceil(timing.period_ns),
            untaken: 0,
            took_stopped: false,
        }
    }

    /// After each snapshot's push (`taken` if the ring took it): whether a bus told to exit is done, because the ring
    /// has taken a snapshot with every limb stopped, control has dropped the ring, or `limit` such snapshots have gone
    /// untaken.
    fn done(&mut self, snap: &Snapshot, taken: bool, exiting: bool, abandoned: bool) -> bool {
        if !snap.stopped() {
            return false;
        }
        self.took_stopped |= taken;
        if !exiting {
            return false;
        }
        if self.took_stopped || abandoned {
            return true;
        }
        self.untaken += 1;
        self.untaken >= self.limit
    }
}

fn run(socket: &CanSocket, mut tick: BusTick, mut links: BusLinks) -> BusExit {
    let timing = tick.timing();
    let mut outcome = BusExit {
        recorder: links.recorder,
        last: None,
        error: None,
    };
    let clock = match Clock::new(links.epoch, links.start) {
        Ok(clock) => clock,
        Err(e) => {
            outcome.error = Some(e);
            return outcome;
        }
    };
    let mut n = clock.first_due(timing.period_ns);
    let mut exit_wait = ExitWait::new(timing);
    // Set once the exit is decided, after a tick's snapshot is published; the thread returns at the next tick's drain.
    let mut leaving = false;
    loop {
        let due = clock.at(n, timing.period_ns);
        if let Err(e) = clock.sleep_until(due) {
            // No clock to keep the schedule: stop the drives, sleeping relative to get there. The socket is still
            // there, so the stop's frames are written as usual.
            tick.request_stop();
            outcome.error.get_or_insert(e);
            sleep_relative(due.saturating_duration_since(mono_now()));
        }
        // A stall (in the sleep, or the last tick overrunning) may have carried the thread past whole ticks: run the
        // one now in progress, and count the ones between as missed deadlines; `begin` judges whether this one is late.
        let current = clock.tick_at(mono_now(), timing.period_ns);
        if current > n {
            tick.skipped(current - n);
            n = current;
        }
        let scheduled = clock.at(n, timing.period_ns);
        let mut batch = TickBatch::new(n, clock.ns(scheduled), wall_ns());
        // The overflow count is the last one seen; a frame read this tick may update it.
        batch.kernel_drops = outcome.last.map_or(0, |s| s.counters.kernel_drops);

        // Drain what arrived in the slack before anything is sent.
        if let Err(e) = drain(socket, &clock, &mut tick, &mut batch) {
            lose(&mut tick, &mut outcome, e);
        }
        let exiting = links.exit.load(Ordering::Acquire);
        if leaving || (exiting && tick.all_idle()) {
            // The frames this drain read are still recorded, with the health they left the bus in: for a bus leaving
            // after its stop, the echoes of a last send the previous tick wrote after its collect deadline, which only
            // reach the recording by being read back.
            batch.valid = tick.healthy();
            outcome.recorder.record(batch);
            break;
        }
        if exiting {
            // Every limb not already stopping or stopped is stopped first; the exit is decided once a snapshot with
            // every limb stopped is published.
            tick.request_stop();
        }
        let command = newest(&mut links.commands);
        // Planned against the tick's own schedule: a wake past its send window is a missed deadline.
        let sends = tick.begin(
            n,
            clock.ns(mono_now()),
            clock.ns(scheduled),
            command.as_ref(),
        );
        let send_by = scheduled + Duration::from_nanos(timing.send_window_ns);
        send_all(socket, &clock, &mut tick, &mut outcome, &sends, send_by);

        // Collect until the deadline.
        let deadline = scheduled + Duration::from_nanos(timing.collect_ns);
        if let Err(e) = collect(socket, &clock, &mut tick, &mut batch, deadline) {
            lose(&mut tick, &mut outcome, e);
        }
        let mut snap = tick.end(clock.ns(mono_now()));
        batch.valid = snap.healthy;
        let taken = links.snapshots.push(snap).is_ok();
        if !taken {
            // Control's ring is full: it keeps its older snapshots and this one is lost, and says so itself.
            tick.snapshot_dropped(&mut snap);
        }
        outcome.recorder.record(batch);
        outcome.last = Some(snap);
        if outcome.error.is_some() && snap.stopped() {
            // A socket or clock error ends the thread once a snapshot with every limb stopped is made, taken or not:
            // there is no bus left to wait on.
            break;
        }
        leaving = exit_wait.done(&snap, taken, exiting, links.snapshots.is_abandoned());
        n += 1;
    }
    outcome
}

/// Write each planned send once, in order, and report it to the tick. Once the bus is lost (a write or read failed, or
/// a bus-off) the rest aren't tried: there is no bus to send on. A failed clock alone doesn't stop the writes.
fn send_all(
    socket: &CanSocket,
    clock: &Clock,
    tick: &mut BusTick,
    outcome: &mut BusExit,
    sends: &SendList,
    send_by: Instant,
) {
    for (index, send) in sends.iter().enumerate() {
        // A Disable or reporting off never expires: late, it is still the right one (can.md section 2).
        let result = if tick.bus_lost() {
            SendOutcome::Failed
        } else if send.expires && mono_now() > send_by {
            SendOutcome::Expired
        } else {
            match write(socket, &send.frame) {
                Ok(result) => result,
                Err(e) => {
                    lose(tick, outcome, e);
                    SendOutcome::Failed
                }
            }
        };
        tick.sent(index, result, clock.ns(mono_now()));
    }
}

/// The socket failed: the tick latches the bus lost, and the first error is kept for [`BusExit`].
fn lose(tick: &mut BusTick, outcome: &mut BusExit, e: io::Error) {
    tick.lost_bus(bus_error(&e));
    outcome.error.get_or_insert(e);
}

fn newest(commands: &mut Consumer<CommandBatch>) -> Option<CommandBatch> {
    let mut newest = None;
    for _ in 0..commands.buffer().capacity() {
        match commands.pop() {
            Ok(b) => newest = Some(b),
            Err(_) => break,
        }
    }
    newest
}

/// Empty the socket before the send, so what is read after it came after the backlog, and tell the tick how it went:
/// past [`DRAIN_MAX`] frames the bus stops; past `DRAIN_LIMIT` the socket is left unemptied and the tick's reads are
/// unordered until a drain empties it.
fn drain(
    socket: &CanSocket,
    clock: &Clock,
    tick: &mut BusTick,
    batch: &mut TickBatch,
) -> io::Result<()> {
    for read in 0..DRAIN_LIMIT {
        let received = match sys::recv(socket.as_fd()) {
            Ok(received) => received,
            // Interrupted twice: frames may still be queued, so this drain didn't empty the socket.
            Err(e) if e.kind() == io::ErrorKind::Interrupted => {
                tick.drained(Drain::Unemptied);
                return Ok(());
            }
            Err(e) => return Err(e),
        };
        let Some(received) = received else {
            tick.drained(if read > DRAIN_MAX {
                Drain::Backlog
            } else {
                Drain::Emptied
            });
            return Ok(());
        };
        take(clock, tick, batch, received);
    }
    tick.drained(Drain::Unemptied);
    Ok(())
}

fn collect(
    socket: &CanSocket,
    clock: &Clock,
    tick: &mut BusTick,
    batch: &mut TickBatch,
    deadline: Instant,
) -> io::Result<()> {
    loop {
        let now = mono_now();
        if now >= deadline {
            return Ok(());
        }
        if !sys::wait(socket.as_fd(), deadline - now)? {
            continue;
        }
        loop {
            let received = match sys::recv(socket.as_fd()) {
                Ok(Some(received)) => received,
                // Interrupted twice: wait and read again; nothing here depends on having emptied the socket.
                Ok(None) => break,
                Err(e) if e.kind() == io::ErrorKind::Interrupted => break,
                Err(e) => return Err(e),
            };
            take(clock, tick, batch, received);
            if mono_now() >= deadline {
                return Ok(());
            }
        }
    }
}

fn take(clock: &Clock, tick: &mut BusTick, batch: &mut TickBatch, received: sys::Received) {
    let read_ns = clock.ns(mono_now());
    if let Some(drops) = received.drops {
        tick.note_kernel_drops(drops);
        batch.kernel_drops = drops;
    }
    tick.on_frame(read_ns, &received.frame);
    // A batch past its capacity counts the frame as omitted; the recording says so.
    let _ = batch.push(received.frame);
}

/// Write one frame, once. A full queue drops it (never retried, can.md section 2). Any other failure is an error that
/// loses the bus: the socket can't be trusted to carry the stop either, and the errno is kept for [`BusExit`].
fn write(socket: &CanSocket, frame: &Frame) -> io::Result<SendOutcome> {
    let Some(id) = ExtendedId::new(frame.id()) else {
        return Ok(SendOutcome::Failed);
    };
    let Some(data) = CanDataFrame::new(id, &frame.data()) else {
        return Ok(SendOutcome::Failed);
    };
    match socket.write_frame(&data) {
        Ok(()) => Ok(SendOutcome::Sent),
        Err(e)
            if e.raw_os_error() == Some(libc::ENOBUFS) || e.kind() == io::ErrorKind::WouldBlock =>
        {
            Ok(SendOutcome::QueueFull)
        }
        Err(e) => Err(e),
    }
}

fn bus_error(e: &io::Error) -> BusError {
    match e.raw_os_error() {
        Some(libc::ENETDOWN) => BusError::InterfaceDown,
        Some(libc::ENODEV | libc::ENXIO) => BusError::InterfaceGone,
        errno => BusError::Socket(errno.unwrap_or(0)),
    }
}
