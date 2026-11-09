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
use telemetry::{BusRecorder, Epoch, TickBatch};

use crate::error_frame::BusError;
use crate::slow::{SlowOutcome, SlowRequest, SlowResult};
use crate::sys::{self, SO_RCVBUFFORCE, SO_RXQ_OVFL, SO_TIMESTAMPNS_NEW};
use crate::tick::BusTick;
use crate::types::{BusDrive, CommandBatch, ConfigError, Drain, SendOutcome, Snapshot, Timing};

/// The most frames a tick's drain may find before the send. More than that queued means the thread can't tell what the
/// bus said in time, so it stops (1 Mbit/s carries about 8,000 frames a second: 32 a tick at 250 Hz).
pub const DRAIN_MAX: usize = 256;
/// The most frames a drain reads. A real bus can't refill the socket faster than it is read, so a drain empties it
/// long before this; only a flood on `vcan` reaches it, and then the tick's reads may predate its sends.
const DRAIN_LIMIT: usize = 8 * DRAIN_MAX;
/// The receive buffer asked for: a second of the busiest bus, so a stall can't overflow the kernel's default.
const RCVBUF_BYTES: libc::c_int = 1 << 20;

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
    #[error(transparent)]
    Config(#[from] ConfigError),
    /// Opening or setting up the socket failed.
    #[error("{bus}: {source}")]
    Socket {
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
    /// The last snapshot.
    pub last: Option<Snapshot>,
    /// The socket or clock error that ended it, if one did.
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
    /// Slow requests from control (parameter reads, allowlisted writes, get-ID), queued as room frees up.
    pub requests: Consumer<SlowRequest>,
    /// Each slow request's one result. When the ring is full the result is dropped and counted
    /// (`Counters::slow_results_dropped`), and the requester times out.
    pub results: Producer<SlowResult>,
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
    /// Set to end the thread: an active bus stops its drives first, then the thread returns.
    pub exit: Arc<AtomicBool>,
}

/// Open the bus and start its thread, named `bus-<name>`.
///
/// # Errors
/// [`BusRunError`] before any frame is sent.
pub fn spawn(config: BusConfig, links: BusLinks) -> Result<Spawned, BusRunError> {
    let tick = BusTick::new(&config.drives, config.timing)?;
    let socket = open(&config.name)?;
    let receive_buffer_bytes =
        sys::receive_buffer(socket.as_fd()).map_err(|source| BusRunError::Socket {
            bus: config.name.clone(),
            source,
        })?;
    let thread = std::thread::Builder::new()
        .name(format!("bus-{}", config.name))
        .spawn(move || run(&socket, tick, links))
        .map_err(|source| BusRunError::Socket {
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
/// receive buffer, non-blocking.
fn open(bus: &str) -> Result<CanSocket, BusRunError> {
    let kind = link_kind(bus).map_err(|reason| BusRunError::Unchecked {
        bus: bus.to_owned(),
        reason,
    })?;
    if kind != "vcan" {
        return Err(BusRunError::NotVcan {
            bus: bus.to_owned(),
        });
    }
    let err = |source| BusRunError::Socket {
        bus: bus.to_owned(),
        source,
    };
    let socket = CanSocket::open(bus).map_err(err)?;
    socket.set_error_filter_accept_all().map_err(err)?;
    socket.set_loopback(true).map_err(err)?;
    socket.set_recv_own_msgs(true).map_err(err)?;
    socket.set_filter_accept_all().map_err(err)?;
    socket
        .set_socket_option_int(libc::SOL_SOCKET, SO_TIMESTAMPNS_NEW, 1)
        .map_err(err)?;
    socket
        .set_socket_option_int(libc::SOL_SOCKET, SO_RXQ_OVFL, 1)
        .map_err(err)?;
    // SO_RCVBUFFORCE needs CAP_NET_ADMIN; without it the kernel caps SO_RCVBUF at rmem_max. `spawn` reads back what
    // the kernel gave, for the runtime to log.
    if socket
        .set_socket_option_int(libc::SOL_SOCKET, SO_RCVBUFFORCE, RCVBUF_BYTES)
        .is_err()
    {
        socket
            .set_socket_option_int(libc::SOL_SOCKET, libc::SO_RCVBUF, RCVBUF_BYTES)
            .map_err(err)?;
    }
    socket.set_nonblocking(true).map_err(err)?;
    Ok(socket)
}

/// The interface's link kind from `ip -details -json`, or why it can't be read. An interface with no kind (a plain
/// device such as `lo`) is the empty string.
fn link_kind(bus: &str) -> Result<String, String> {
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
    let text = String::from_utf8_lossy(&out.stdout);
    let key = r#""info_kind":""#;
    let Some(at) = text.find(key).map(|at| at + key.len()) else {
        return Ok(String::new());
    };
    let rest = text.get(at..).unwrap_or_default();
    rest.get(..rest.find('"').unwrap_or_default())
        .map(str::to_owned)
        .ok_or_else(|| "ip's output has no link kind".to_owned())
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
        let now = mono_now();
        let now_ts = clock_gettime(ClockId::CLOCK_MONOTONIC).map_err(io::Error::from)?;
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

fn run(socket: &CanSocket, mut tick: BusTick, mut links: BusLinks) -> BusExit {
    let timing = tick.timing();
    let mut exit = BusExit {
        recorder: links.recorder,
        last: None,
        error: None,
    };
    let clock = match Clock::new(links.epoch, links.start) {
        Ok(clock) => clock,
        Err(e) => {
            exit.error = Some(e);
            end_slow(&mut tick, &mut links.requests, &mut links.results);
            return exit;
        }
    };
    let mut n = clock.first_due(timing.period_ns);
    loop {
        let scheduled = clock.at(n, timing.period_ns);
        if let Err(e) = clock.sleep_until(scheduled) {
            // No clock to keep the schedule: stop the drives, sleeping relative to get there.
            tick.request_stop();
            exit.error.get_or_insert(e);
            sleep_relative(scheduled.saturating_duration_since(mono_now()));
        }
        let mut batch = TickBatch::new(n, clock.ns(scheduled), wall_ns());
        // The overflow count is the last one seen; a frame read this tick may update it.
        batch.kernel_drops = exit.last.map_or(0, |s| s.counters.kernel_drops);

        // Drain what arrived in the slack before anything is sent.
        if let Err(e) = drain(socket, &clock, &mut tick, &mut batch) {
            tick.lost_bus(bus_error(&e));
            exit.error.get_or_insert(e);
        }
        if links.exit.load(Ordering::Acquire) {
            if exit.last.is_none_or(|s| s.settled()) {
                // The frames this drain read are still recorded.
                batch.valid = exit.last.is_none_or(|s| s.healthy);
                exit.recorder.record(batch);
                break;
            }
            tick.request_stop();
        }
        let command = newest(&mut links.commands);
        // Planned against the tick's own schedule, so a wake any number of periods late is a missed deadline.
        let sends = tick.begin(
            n,
            clock.ns(mono_now()),
            clock.ns(scheduled),
            command.as_ref(),
        );
        let send_by = scheduled + Duration::from_nanos(timing.send_window_ns);
        for (index, send) in sends.iter().enumerate() {
            // A Disable or reporting off never expires: late, it is still the right one (can.md section 2).
            let outcome = if send.expires && mono_now() > send_by {
                SendOutcome::Expired
            } else {
                match write(socket, &send.frame) {
                    Ok(outcome) => outcome,
                    Err(e) => {
                        tick.lost_bus(bus_error(&e));
                        exit.error.get_or_insert(e);
                        SendOutcome::Failed
                    }
                }
            };
            tick.sent(index, outcome, clock.ns(mono_now()));
        }

        // Collect until the deadline.
        let deadline = scheduled + Duration::from_nanos(timing.collect_ns);
        if let Err(e) = collect(socket, &clock, &mut tick, &mut batch, deadline) {
            tick.lost_bus(bus_error(&e));
            exit.error.get_or_insert(e);
        }
        let snap = tick.end(clock.ns(mono_now()));
        batch.valid = snap.healthy;
        if links.snapshots.push(snap).is_err() {
            // Control's ring is full: it keeps its older snapshots and this one is lost, counted in the next.
            tick.snapshot_dropped();
        }
        exit.recorder.record(batch);
        exit.last = Some(snap);
        if exit.error.is_some() && snap.stopped() {
            break;
        }
        // The slack after the collect deadline: control's slow requests, one exchange at a time.
        if let Err(e) = slow(
            socket,
            &clock,
            &mut tick,
            &mut links.requests,
            &mut links.results,
        ) {
            tick.lost_bus(bus_error(&e));
            exit.error.get_or_insert(e);
        }
        // The next tick is the first not yet due; any skipped were missed deadlines, and this late tick has already
        // stopped the bus.
        let due = mono_now().saturating_duration_since(clock.start).as_nanos()
            / u128::from(timing.period_ns);
        let next = u64::try_from(due).unwrap_or(u64::MAX).max(n + 1);
        tick.skipped(next - n - 1, clock.ns(mono_now()));
        n = next;
    }
    end_slow(&mut tick, &mut links.requests, &mut links.results);
    exit
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
        let Some(received) = sys::recv(socket.as_fd())? else {
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
        while let Some(received) = sys::recv(socket.as_fd())? {
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

/// Queue the slow requests that fit, send one if the tick allows, and hand every result back. A full result ring
/// drops the result and counts it; the requester times out.
fn slow(
    socket: &CanSocket,
    clock: &Clock,
    tick: &mut BusTick,
    requests: &mut Consumer<SlowRequest>,
    results: &mut Producer<SlowResult>,
) -> io::Result<()> {
    // Bounded by the ring: a refused request takes no slot, so room alone wouldn't end the loop.
    for _ in 0..requests.buffer().capacity() {
        if tick.slow_room() == 0 {
            break;
        }
        let Ok(request) = requests.pop() else {
            break;
        };
        if let Err(refusal) = tick.submit(request) {
            let refused = SlowResult {
                tag: request.tag,
                slot: request.slot,
                outcome: SlowOutcome::Refused(refusal),
            };
            if results.push(refused).is_err() {
                tick.slow_result_dropped();
            }
        }
    }
    let mut failed = Ok(());
    if let Some(frame) = tick.slow_send(clock.ns(mono_now())) {
        let outcome = write(socket, &frame).unwrap_or_else(|e| {
            failed = Err(e);
            SendOutcome::Failed
        });
        tick.slow_sent(outcome, clock.ns(mono_now()));
    }
    hand_back(tick, results);
    failed
}

/// Every result the tick holds, onto control's ring; a full ring drops the result and counts it.
fn hand_back(tick: &mut BusTick, results: &mut Producer<SlowResult>) {
    while let Some(result) = tick.take_slow_result() {
        if results.push(result).is_err() {
            tick.slow_result_dropped();
        }
    }
}

/// The thread is ending: every slow request still held or still in the ring gets its one result (can.md section 2:
/// none goes unanswered). A drop here can't be counted in a snapshot; the requester times out.
fn end_slow(
    tick: &mut BusTick,
    requests: &mut Consumer<SlowRequest>,
    results: &mut Producer<SlowResult>,
) {
    let refusal = tick.end_slow();
    hand_back(tick, results);
    for _ in 0..requests.buffer().capacity() {
        let Ok(request) = requests.pop() else {
            break;
        };
        let refused = SlowResult {
            tag: request.tag,
            slot: request.slot,
            outcome: SlowOutcome::Refused(refusal),
        };
        if results.push(refused).is_err() {
            tick.slow_result_dropped();
        }
    }
}

/// Write one frame, once. A full queue drops it (never retried, can.md section 2); a lost interface is an error.
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
        Err(e)
            if matches!(
                e.raw_os_error(),
                Some(libc::ENETDOWN | libc::ENODEV | libc::ENXIO)
            ) =>
        {
            Err(e)
        }
        Err(_) => Ok(SendOutcome::Failed),
    }
}

fn bus_error(e: &io::Error) -> BusError {
    match e.raw_os_error() {
        Some(libc::ENETDOWN) => BusError::InterfaceDown,
        Some(libc::ENODEV | libc::ENXIO) => BusError::InterfaceGone,
        errno => BusError::Socket(errno.unwrap_or(0)),
    }
}
