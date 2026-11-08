//! (rt) One bus's thread on Linux: the socket, the absolute-deadline loop around [`BusTick`], and the recording.

use std::io;
use std::os::fd::AsFd;
use std::process::Command;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::thread::JoinHandle;
use std::time::{Duration, Instant, SystemTime};

use nix::time::{ClockId, ClockNanosleepFlags, clock_gettime, clock_nanosleep};
use robstride::{DeviceId, Frame};
use rtrb::{Consumer, Producer};
use socketcan::{CanDataFrame, CanSocket, EmbeddedFrame, ExtendedId, Socket, SocketOptions};
use telemetry::{BusRecorder, Epoch, TickBatch};

use crate::error_frame::BusError;
use crate::sys::{self, SO_RCVBUFFORCE, SO_RXQ_OVFL, SO_TIMESTAMPNS_NEW};
use crate::tick::BusTick;
use crate::types::{BusState, CommandBatch, SendOutcome, Snapshot, Timing, TooManyDrives};

/// The most frames read before a tick's send. More than that queued means the thread can't tell what the bus said, so
/// it stops (1 Mbit/s carries about 8,000 frames a second: 32 a tick at 250 Hz).
pub const DRAIN_MAX: usize = 256;
/// The receive buffer asked for: a second of the busiest bus, so a stall can't overflow the kernel's default.
const RCVBUF_BYTES: libc::c_int = 1 << 20;

/// What a bus thread needs.
#[derive(Clone, Debug)]
pub struct BusConfig {
    /// The interface, as the skeleton names it.
    pub name: String,
    /// The drives the skeleton puts on it, in slot order.
    pub drives: Vec<DeviceId>,
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
    /// Too many drives for the bus table.
    #[error(transparent)]
    TooManyDrives(#[from] TooManyDrives),
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
    /// The socket error that ended it, if one did.
    pub error: Option<io::Error>,
}

/// The rings and flags a bus thread runs with, all made before the first tick.
pub struct BusLinks {
    /// Command batches from control; the newest one each tick is used.
    pub commands: Consumer<CommandBatch>,
    /// Snapshots out; one dropped when control hasn't read the last.
    pub snapshots: Producer<Snapshot>,
    /// This bus's recorder ring.
    pub recorder: BusRecorder,
    /// The session's monotonic zero.
    pub epoch: Epoch,
    /// Set to end the thread: an active bus stops its drives first, then the thread returns.
    pub exit: Arc<AtomicBool>,
}

/// Open the bus and start its thread, named `bus-<name>`.
///
/// # Errors
/// [`BusRunError`] before any frame is sent.
pub fn spawn(config: BusConfig, links: BusLinks) -> Result<JoinHandle<BusExit>, BusRunError> {
    let socket = open(&config.name)?;
    let tick = BusTick::new(&config.drives, config.timing)?;
    std::thread::Builder::new()
        .name(format!("bus-{}", config.name))
        .spawn(move || run(&socket, tick, links))
        .map_err(|source| BusRunError::Socket {
            bus: config.name,
            source,
        })
}

/// Open `bus` with can.md section 2's settings: error frames on, loopback on, our own frames back (so they record as
/// `tx_echo`), every ID accepted (so unexpected senders stay visible), kernel timestamps, the overflow counter, a large
/// receive buffer, non-blocking.
fn open(bus: &str) -> Result<CanSocket, BusRunError> {
    if link_kind(bus).as_deref() != Some("vcan") {
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
    // SO_RCVBUFFORCE needs CAP_NET_ADMIN; without it the kernel caps SO_RCVBUF at rmem_max. The effective size is what
    // gets logged by the runtime.
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

/// The interface's link kind from `ip -details -json`, or `None` if it can't be read.
fn link_kind(bus: &str) -> Option<String> {
    if bus.is_empty() || bus.starts_with('-') {
        return None;
    }
    let out = Command::new("ip")
        .args(["-details", "-json", "link", "show", "dev", bus])
        .output()
        .ok()
        .filter(|o| o.status.success())?;
    let text = String::from_utf8_lossy(&out.stdout);
    let at = text.find(r#""info_kind":""#)? + r#""info_kind":""#.len();
    let rest = text.get(at..)?;
    Some(rest.get(..rest.find('"')?)?.to_owned())
}

/// The bus's clocks: the loop's schedule on `CLOCK_MONOTONIC` (absolute sleeps) and the session's epoch for stamps.
struct Clock {
    start: Instant,
    start_ts: nix::sys::time::TimeSpec,
    epoch: Epoch,
}

impl Clock {
    fn new(epoch: Epoch) -> io::Result<Self> {
        let start = Instant::now();
        let start_ts = clock_gettime(ClockId::CLOCK_MONOTONIC).map_err(io::Error::from)?;
        Ok(Self {
            start,
            start_ts,
            epoch,
        })
    }

    /// Sleep until `at` on the monotonic clock, absolute, so a slow tick never shifts the next.
    fn sleep_until(&self, at: Instant) {
        let offset = at.saturating_duration_since(self.start);
        let target = self.start_ts + nix::sys::time::TimeSpec::from_duration(offset);
        loop {
            match clock_nanosleep(
                ClockId::CLOCK_MONOTONIC,
                ClockNanosleepFlags::TIMER_ABSTIME,
                &target,
            ) {
                Err(nix::errno::Errno::EINTR) => {}
                Ok(_) | Err(_) => return,
            }
        }
    }

    fn ns(&self, at: Instant) -> u64 {
        self.epoch.ns(at)
    }
}

fn wall_ns() -> u64 {
    SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        .map_or(0, |d| u64::try_from(d.as_nanos()).unwrap_or(u64::MAX))
}

fn run(socket: &CanSocket, mut tick: BusTick, mut links: BusLinks) -> BusExit {
    let timing = tick.timing();
    let period = Duration::from_nanos(timing.period_ns);
    let mut exit = BusExit {
        recorder: links.recorder,
        last: None,
        error: None,
    };
    let clock = match Clock::new(links.epoch) {
        Ok(clock) => clock,
        Err(e) => {
            exit.error = Some(e);
            return exit;
        }
    };
    let mut n: u64 = 0;
    loop {
        let scheduled = clock.start + period.saturating_mul(u32::try_from(n).unwrap_or(u32::MAX));
        clock.sleep_until(scheduled);
        let woke = Instant::now();
        // A wake several periods late jumps to the current tick; BusTick counts the missed deadline and stops.
        let behind = woke.saturating_duration_since(scheduled).as_nanos()
            / u128::from(timing.period_ns.max(1));
        let (n_now, scheduled) = if behind > 1 {
            let skip = u64::try_from(behind).unwrap_or(0);
            (
                n + skip,
                scheduled + period.saturating_mul(u32::try_from(skip).unwrap_or(u32::MAX)),
            )
        } else {
            (n, scheduled)
        };
        n = n_now;
        let mut batch = TickBatch::new(n, clock.ns(scheduled), wall_ns());

        // Drain what arrived in the slack before anything is sent.
        if let Err(e) = drain(socket, &clock, &mut tick, &mut batch) {
            tick.lost_bus(bus_error(&e));
            exit.error = Some(e);
        }
        if links.exit.load(Ordering::Acquire) {
            match exit.last.map(|s| s.state) {
                None | Some(BusState::Idle | BusState::Stopped) => break,
                Some(BusState::Active | BusState::Stopping { .. }) => tick.request_stop(),
            }
        }
        let command = newest(&mut links.commands);
        let now = Instant::now();
        let sends = tick.begin(n, clock.ns(now), clock.ns(scheduled), command.as_ref());
        let send_by = scheduled + Duration::from_nanos(timing.send_window_ns);
        for (index, send) in sends.iter().enumerate() {
            let outcome = if Instant::now() > send_by {
                SendOutcome::Expired
            } else {
                match write(socket, &send.frame) {
                    Ok(outcome) => outcome,
                    Err(e) => {
                        tick.lost_bus(bus_error(&e));
                        exit.error = Some(e);
                        SendOutcome::Failed
                    }
                }
            };
            tick.sent(index, outcome);
        }

        // Collect until the deadline.
        let deadline = scheduled + Duration::from_nanos(timing.collect_ns);
        if let Err(e) = collect(socket, &clock, &mut tick, &mut batch, deadline) {
            tick.lost_bus(bus_error(&e));
            exit.error = Some(e);
        }
        let snap = tick.end(clock.ns(Instant::now()));
        batch.valid = matches!(snap.state, BusState::Idle | BusState::Active);
        batch.kernel_drops = snap.counters.kernel_drops;
        // A full ring drops the snapshot: control reads the newest anyway.
        let _ = links.snapshots.push(snap);
        exit.recorder.record(batch);
        exit.last = Some(snap);
        if exit.error.is_some() && snap.state == BusState::Stopped {
            break;
        }
        n += 1;
    }
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

fn drain(
    socket: &CanSocket,
    clock: &Clock,
    tick: &mut BusTick,
    batch: &mut TickBatch,
) -> io::Result<()> {
    for _ in 0..DRAIN_MAX {
        match sys::recv(socket.as_fd())? {
            Some(received) => take(clock, tick, batch, received),
            None => return Ok(()),
        }
    }
    // Still more queued: the thread can't see the bus's state in time.
    tick.backlog();
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
        let now = Instant::now();
        if now >= deadline {
            return Ok(());
        }
        if !sys::wait(socket.as_fd(), deadline - now)? {
            continue;
        }
        while let Some(received) = sys::recv(socket.as_fd())? {
            take(clock, tick, batch, received);
            if Instant::now() >= deadline {
                return Ok(());
            }
        }
    }
}

fn take(clock: &Clock, tick: &mut BusTick, batch: &mut TickBatch, received: sys::Received) {
    let read_ns = clock.ns(Instant::now());
    if let Some(drops) = received.drops {
        tick.note_kernel_drops(drops);
    }
    tick.on_frame(read_ns, &received.frame);
    // A batch past its capacity counts the frame as omitted; the recording says so.
    let _ = batch.push(received.frame);
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
        Err(e) if matches!(e.raw_os_error(), Some(libc::ENETDOWN | libc::ENODEV)) => Err(e),
        Err(_) => Ok(SendOutcome::Failed),
    }
}

fn bus_error(e: &io::Error) -> BusError {
    match e.raw_os_error() {
        Some(libc::ENODEV) => BusError::InterfaceGone,
        _ => BusError::InterfaceDown,
    }
}
