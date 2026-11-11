//! (rt) One bus's thread on Linux: the socket, the absolute-deadline loop around [`BusTick`], and the recording.

use std::io;
use std::os::fd::AsFd;
use std::process::Command;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::thread::JoinHandle;
use std::time::{Duration, Instant};

use robstride::Frame;
use rtrb::{Consumer, Producer};
use socketcan::{CanDataFrame, CanSocket, EmbeddedFrame, ExtendedId, Socket, SocketOptions};
use telemetry::{BusInfo, BusRecorder, Epoch, TickBatch, TimestampSource};

use crate::clock::{Clock, mono_now, sleep_relative, wall_ns};
use crate::error_frame::BusError;
use crate::exit_wait::{ExitWait, Pushed};
use crate::order::{Order, Rearmed};
use crate::slow::{SlowRequest, SlowResult};
use crate::tick::BusTick;
use crate::timing::Timing;
use crate::types::{
    BusDrive, CommandBatch, ConfigError, Counters, Drain, SendList, SendOutcome, Snapshot,
};
use crate::{bus_orders, slack, sys};

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
    /// Slow results control's ring couldn't take over the thread's whole run: `last`'s
    /// `counters.slow_results_dropped` and those dropped after it, when the ending thread gave every request it still
    /// held, or found in its ring, its one result.
    pub slow_results_dropped: u64,
    /// Slow requests that expired unsent over the thread's whole run: `last`'s `counters.slow_expired` and those that
    /// expired after it, in the slack of the tick that made it, which no later snapshot carries when the thread leaves
    /// at the next drain.
    pub slow_expired: u64,
    /// The thread's counters as it ended, after the last snapshot: the re-arm answers its ring couldn't take
    /// (`rearms_dropped`) and the bad stop orders (`bad_orders`) over the whole run included, those after `last` too.
    pub counters: Counters,
    /// The first socket or clock error the thread met, if any. Most end the thread; one after the snapshot that
    /// decided its exit ([`BusLinks::exit`]), in the sleep or drain of the tick it returns at, is reported too, though
    /// it returns there all the same. No snapshot is made after it, so `last` is then the
    /// snapshot with every limb stopped that decided the exit, made before the error and healthy as far as it knew.
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
    /// (`Counters::slow_results_dropped`, and in all at the end [`BusExit::slow_results_dropped`]), and the requester
    /// times out.
    pub results: Producer<SlowResult>,
    /// Control's orders: stop a limb, stop the bus, re-arm a stopped limb. Every order in the ring is taken at the next
    /// tick's start, before its drain, in the order control pushed them. A re-arm has its own refusals (`RearmRefused`); on
    /// a bus exiting it is refused at the least `StopPending` (the exit's stop is asked first), and one left when the
    /// thread ends is answered `Ended`.
    pub orders: Consumer<Order>,
    /// Each re-arm order's one answer. When the ring is full the answer is dropped and counted
    /// (`Counters::rearms_dropped`); control still sees the limb's state and generation in the snapshots. A re-arm still
    /// in `orders` when the thread ends is answered `RearmRefused::Ended` (a drop then counts in `BusExit::counters`).
    pub rearmed: Producer<Rearmed>,
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
    /// socket are recorded and the reply to a slow request sent in the last slack still answers it; then every slow
    /// request the thread holds or finds in its ring gets its one result. The last snapshot made is [`BusExit::last`]
    /// in every case. A socket or clock error ends
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

#[expect(
    clippy::too_many_lines,
    reason = "the tick's steps in their order, in one loop; each step is its own function"
)]
fn run(socket: &CanSocket, mut tick: BusTick, mut links: BusLinks) -> BusExit {
    let timing = tick.timing();
    let mut outcome = BusExit {
        recorder: links.recorder,
        last: None,
        slow_results_dropped: 0,
        slow_expired: 0,
        counters: Counters::default(),
        error: None,
    };
    let clock = match Clock::new(links.epoch, links.start) {
        Ok(clock) => clock,
        Err(e) => {
            outcome.error = Some(e);
            return finish(
                tick,
                &mut links.requests,
                &mut links.results,
                &mut links.orders,
                &mut links.rearmed,
                outcome,
            );
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

        let exiting = links.exit.load(Ordering::Acquire);
        if exiting {
            // Every limb not already stopping or stopped is stopped first; the exit is decided once a snapshot with
            // every limb stopped is published. Asked before the orders, so a clear can't undo it (`StopPending`).
            tick.request_stop();
        }
        // Ending this tick: after the stop, or told to exit with nothing ever enabled. Only the drain can change it (a
        // lost bus latches every limb stopped, so the thread goes on to publish that), which is why it is asked again.
        let ending = leaving || (exiting && tick.all_idle());
        // Control's orders, before the drain: a stop goes out in this tick's sends, and a frame the drain reads after a
        // clear latches afresh and is checked before the send. Not on the way out: every order left is answered at the
        // end.
        if !ending && bus_orders::take(&clock, &mut tick, &mut links.orders, &mut links.rearmed) {
            exit_wait.rearmed();
        }
        // Drain what arrived in the slack before anything is sent.
        if let Err(e) = drain(socket, &clock, &mut tick, &mut batch) {
            lose(&mut tick, &mut outcome, e);
        }
        let ending = ending && (leaving || tick.all_idle());
        if ending {
            // The frames this drain read are still recorded, with the health they left the bus in: for a bus leaving
            // after its stop, the echoes of a last send the previous tick wrote after its collect deadline, which only
            // reach the recording by being read back.
            batch.valid = tick.healthy();
            outcome.recorder.record(batch);
            break;
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
        // The slack after the collect deadline: control's slow requests, one exchange at a time.
        slack::slow(
            socket,
            &clock,
            &mut tick,
            &mut links.requests,
            &mut links.results,
            &mut outcome,
        );
        let pushed = Pushed {
            stopped: snap.stopped(),
            taken,
        };
        leaving = exit_wait.done(pushed, exiting, links.snapshots.is_abandoned());
        n += 1;
    }
    finish(
        tick,
        &mut links.requests,
        &mut links.results,
        &mut links.orders,
        &mut links.rearmed,
        outcome,
    )
}

/// The thread is ending: every slow request and re-arm still held or queued gets its one result, and the outcome takes
/// the counts no snapshot carries.
fn finish(
    mut tick: BusTick,
    requests: &mut Consumer<SlowRequest>,
    results: &mut Producer<SlowResult>,
    orders: &mut Consumer<Order>,
    rearmed: &mut Producer<Rearmed>,
    mut outcome: BusExit,
) -> BusExit {
    outcome.slow_results_dropped = slack::end_slow(&mut tick, requests, results);
    outcome.slow_expired = tick.counters.slow_expired;
    bus_orders::end(&mut tick, orders, rearmed);
    outcome.counters = tick.counters;
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
pub(crate) fn lose(tick: &mut BusTick, outcome: &mut BusExit, e: io::Error) {
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
pub(crate) fn write(socket: &CanSocket, frame: &Frame) -> io::Result<SendOutcome> {
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
