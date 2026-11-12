//! `disable` on the real sockets: one named thread per bus, each running its bus's `BusStop` against its own socket, so
//! a bus that is gone or slow never delays the stop on another (PLAN item 2, Stop: "A lost bus never delays stops on
//! healthy buses").

use std::io;
use std::os::fd::AsFd;
use std::time::{Duration, Instant};

use nix::errno::Errno;
use nix::poll::{PollFd, PollFlags, PollTimeout, poll};
use robstride::{DeviceId, Frame, decode};
use socketcan::{
    CanDataFrame, CanFrame, CanSocket, EmbeddedFrame, ExtendedId, Id, Socket, SocketOptions,
};

use crate::BusTargets;
use crate::stop::{BusFault, BusStop, Drain, DriveStop, OsError, Outcome, RESEND, SendError, Wait};

/// The most frames one wake reads before it steps the stop. A 1 Mbit/s bus carries about 8 frames a millisecond and a
/// wake is at most `RESEND` (4 ms) after the last, so this is twice a full bus's worth: a flooded bus still gets its
/// Disables on time (rust.md section 4: every loop has a bound). A drain that hits it says so; before `END` the queue
/// is read again before any wait, and at `END` every drive that would be ok is reported `unread`.
const MAX_DRAIN: usize = 64;

/// One bus's result.
#[derive(Clone, Debug)]
pub struct BusReport {
    /// The interface.
    pub bus: String,
    /// How the bus failed, if it did.
    pub fault: Option<BusFault>,
    /// Error frames read on it, of any class.
    pub error_frames: u32,
    /// One of them was bus-off.
    pub bus_off: bool,
    /// One of them was an RX overflow: frames were lost.
    pub frames_lost: bool,
    /// Why the socket couldn't be asked for error frames, if it couldn't.
    pub errors_unseen: Option<OsError>,
    /// The read failure, if reads failed, also when `fault` is a later write failure.
    pub read_fault: Option<OsError>,
    /// Each drive's joint name, record and outcome, in skeleton order.
    pub drives: Vec<DriveReport>,
}

/// One drive's result.
#[derive(Clone, Debug)]
pub struct DriveReport {
    /// The joint the drive turns.
    pub joint: String,
    /// What was sent to it and read from it.
    pub record: DriveStop,
    /// What that adds up to.
    pub outcome: Outcome,
}

impl BusReport {
    /// True when no drive on this bus needs a person.
    #[must_use]
    pub fn ok(&self) -> bool {
        self.drives.iter().all(|d| d.outcome.ok())
    }
}

/// Stop every drive in `targets`, each bus on its own thread, and return when every bus is done: at most `stop::END`
/// after it began, plus the time to open its socket.
#[must_use]
pub fn disable(targets: &[BusTargets]) -> Vec<BusReport> {
    std::thread::scope(|scope| {
        let threads: Vec<_> = targets
            .iter()
            .map(|t| {
                let thread = std::thread::Builder::new()
                    .name(format!("disable-{}", t.bus))
                    .spawn_scoped(scope, || run(t));
                (t, thread)
            })
            .collect();
        threads
            .into_iter()
            .map(|(t, thread)| match thread {
                Ok(thread) => thread.join().unwrap_or_else(|_| {
                    // Panics abort the process (Cargo.toml), so a join error can't come back; report it anyway.
                    report(t, &failed(t, BusFault::Spawn(OsError::EIO)), Duration::ZERO)
                }),
                Err(e) => report(
                    t,
                    &failed(t, BusFault::Spawn(OsError::from(&e))),
                    Duration::ZERO,
                ),
            })
            .collect()
    })
}

fn ids(t: &BusTargets) -> impl Iterator<Item = DeviceId> + '_ {
    t.drives.iter().map(|(id, _)| *id)
}

fn failed(t: &BusTargets, fault: BusFault) -> BusStop {
    let mut stop = BusStop::new(ids(t));
    stop.fail(fault);
    stop
}

fn report(t: &BusTargets, stop: &BusStop, end: Duration) -> BusReport {
    BusReport {
        bus: t.bus.clone(),
        fault: stop.fault(),
        error_frames: stop.error_frames(),
        bus_off: stop.bus_off(),
        frames_lost: stop.frames_lost(),
        errors_unseen: stop.errors_unseen(),
        read_fault: stop.read_fault(),
        drives: t
            .drives
            .iter()
            .zip(stop.outcomes(end))
            .map(|((_, joint), (record, outcome))| DriveReport {
                joint: joint.clone(),
                record,
                outcome,
            })
            .collect(),
    }
}

fn run(t: &BusTargets) -> BusReport {
    let socket = match CanSocket::open(&t.bus).and_then(|s| s.set_nonblocking(true).map(|()| s)) {
        Ok(s) => s,
        Err(e) => {
            return report(
                t,
                &failed(t, BusFault::Open(OsError::from(&e))),
                Duration::ZERO,
            );
        }
    };
    let mut stop = BusStop::new(ids(t));
    // Bus-off tells a bus that is down from drives that are off. A socket that can't be asked for error frames can't
    // tell the two apart, so its silent drives are reported silent_errors_unseen; the stop itself goes on.
    if let Err(e) = socket.set_error_filter_accept_all() {
        stop.cant_see_errors(OsError::from(&e));
    }
    let start = Instant::now();
    let mut send = |frame: Frame| write(&socket, frame);
    loop {
        if stop.reading() {
            match drain(&socket, &mut stop, start) {
                Ok(drain) => stop.drained(drain),
                Err(e) => stop.fail(BusFault::Read(e)),
            }
        }
        let now = start.elapsed();
        stop.step(now, &mut send);
        let next = match stop.wait(now) {
            Wait::Done => return report(t, &stop, now),
            Wait::DrainAgain => continue,
            Wait::Until(next) => next,
        };
        // Wake at the next due time, a tick later at most, or on a frame.
        let wait = next
            .saturating_sub(now)
            .clamp(Duration::from_millis(1), RESEND);
        if !stop.reading() {
            // Nothing to wait on but the time: a broken socket would end every poll at once.
            std::thread::sleep(wait);
            continue;
        }
        let millis = u16::try_from(wait.as_millis()).unwrap_or(u16::MAX);
        let mut fds = [PollFd::new(socket.as_fd(), PollFlags::POLLIN)];
        match poll(&mut fds, PollTimeout::from(millis)) {
            // A signal only cuts the wait short.
            Ok(_) | Err(Errno::EINTR) => {}
            Err(e) => stop.fail(BusFault::Read(OsError(e as i32))),
        }
        let broken = PollFlags::POLLERR | PollFlags::POLLHUP | PollFlags::POLLNVAL;
        if stop.reading() && fds[0].revents().is_some_and(|r| r.intersects(broken)) {
            // The socket can't be waited on: the drain reads its error, or this ends the reads.
            let e = match drain(&socket, &mut stop, start) {
                Err(e) => e,
                Ok(_) => OsError::EIO,
            };
            stop.fail(BusFault::Read(e));
        }
    }
}

/// Read the frames queued, at most `MAX_DRAIN`, handing each to the stop. After that many, a poll that doesn't wait
/// tells a queue still holding frames from an emptied one, without taking a frame.
fn drain(socket: &CanSocket, stop: &mut BusStop, start: Instant) -> Result<Drain, OsError> {
    for _ in 0..MAX_DRAIN {
        match socket.read_frame() {
            Ok(frame) => heard(stop, start, &frame),
            Err(e) if e.kind() == io::ErrorKind::WouldBlock => return Ok(Drain::Emptied),
            Err(e) if e.kind() == io::ErrorKind::Interrupted => {}
            Err(e) => return Err(OsError::from(&e)),
        }
    }
    let mut fds = [PollFd::new(socket.as_fd(), PollFlags::POLLIN)];
    match poll(&mut fds, PollTimeout::ZERO) {
        Ok(0) => Ok(Drain::Emptied),
        Ok(_) | Err(Errno::EINTR) => Ok(Drain::Capped),
        Err(e) => Err(OsError(e as i32)),
    }
}

/// Hand one frame read to the stop.
fn heard(stop: &mut BusStop, start: Instant, frame: &CanFrame) {
    match frame {
        CanFrame::Data(frame) => {
            if let Id::Extended(id) = frame.id()
                && let Ok(inbound) = decode(id.as_raw(), frame.data())
            {
                stop.heard(start.elapsed(), &inbound);
            }
        }
        CanFrame::Error(frame) => {
            let controller = frame.data().get(1).copied().unwrap_or(0);
            stop.heard_error_frame(frame.error_bits(), controller);
        }
        // A remote frame carries no drive's word.
        CanFrame::Remote(_) => {}
    }
}

fn write(socket: &CanSocket, frame: Frame) -> Result<(), SendError> {
    // Both are always built: a `Frame` carries a 29-bit ID and 8 bytes (robstride's `Frame`).
    let data = ExtendedId::new(frame.id()).and_then(|id| CanDataFrame::new(id, &frame.data()));
    let Some(data) = data else {
        return Err(SendError::Failed(OsError(Errno::EINVAL as i32)));
    };
    match socket.write_frame(&data) {
        Ok(()) => Ok(()),
        Err(e)
            if e.kind() == io::ErrorKind::WouldBlock
                || e.raw_os_error() == Some(Errno::ENOBUFS as i32) =>
        {
            Err(SendError::Full)
        }
        Err(e) => Err(SendError::Failed(OsError::from(&e))),
    }
}
