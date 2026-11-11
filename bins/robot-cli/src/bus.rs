//! `disable` on the real sockets: one thread per bus, each running its bus's `BusStop` against its own socket, so a
//! bus that is gone or slow never delays the stop on another (PLAN item 2, Stop: "A lost bus never delays stops on
//! healthy buses").

use std::io;
use std::os::fd::AsFd;
use std::time::Instant;

use nix::poll::{PollFd, PollFlags, PollTimeout, poll};
use robstride::{DeviceId, Frame, decode};
use socketcan::{CanDataFrame, CanFrame, CanSocket, EmbeddedFrame, ExtendedId, Id, Socket};

use crate::BusTargets;
use crate::stop::{BusStop, DriveStop, END_NS, Outcome, RESEND_NS, SendError};

/// `ENOBUFS`: the interface's queue is full.
const ENOBUFS: i32 = 105;

/// One bus's result.
#[derive(Clone, Debug)]
pub struct BusReport {
    /// The interface.
    pub bus: String,
    /// Why the bus failed, if it did (couldn't be opened, or a write failed).
    pub failure: Option<String>,
    /// Each drive: its joint name, record and outcome, in skeleton order.
    pub drives: Vec<(String, DriveStop, Outcome)>,
}

impl BusReport {
    /// True when no drive on this bus needs a person.
    #[must_use]
    pub fn ok(&self) -> bool {
        self.drives.iter().all(|(_, _, o)| o.ok())
    }
}

/// Stop every drive in `targets`, each bus on its own thread, and return when every bus is done (at most
/// `stop::END_NS` after it began, plus the time to open its socket).
#[must_use]
pub fn disable(targets: &[BusTargets]) -> Vec<BusReport> {
    std::thread::scope(|scope| {
        let threads: Vec<_> = targets
            .iter()
            .map(|t| (t, scope.spawn(|| run(t))))
            .collect();
        threads
            .into_iter()
            .map(|(t, thread)| {
                thread.join().unwrap_or_else(|_| {
                    // Panics abort the process (Cargo.toml), so a join error can't come back; report it anyway.
                    report(t, &failed(t, "the bus thread panicked".to_owned()))
                })
            })
            .collect()
    })
}

fn ids(t: &BusTargets) -> impl Iterator<Item = DeviceId> + '_ {
    t.drives.iter().map(|(id, _)| *id)
}

fn failed(t: &BusTargets, error: String) -> BusStop {
    let mut stop = BusStop::new(ids(t));
    stop.fail(error);
    stop
}

fn report(t: &BusTargets, stop: &BusStop) -> BusReport {
    BusReport {
        bus: t.bus.clone(),
        failure: stop.failure().map(str::to_owned),
        drives: t
            .drives
            .iter()
            .zip(stop.outcomes())
            .map(|((_, name), (drive, outcome))| (name.clone(), drive, outcome))
            .collect(),
    }
}

fn run(t: &BusTargets) -> BusReport {
    let socket = match CanSocket::open(&t.bus).and_then(|s| s.set_nonblocking(true).map(|()| s)) {
        Ok(s) => s,
        Err(e) => return report(t, &failed(t, format!("can't open {}: {e}", t.bus))),
    };
    let mut stop = BusStop::new(ids(t));
    let start = Instant::now();
    let since = || u64::try_from(start.elapsed().as_nanos()).unwrap_or(u64::MAX);
    let mut deaf = false;
    let mut send = |frame: Frame| write(&socket, frame);
    loop {
        if !deaf && let Err(e) = drain(&socket, &mut stop, since) {
            stop.deafen(e.to_string());
            deaf = true;
        }
        let now = since();
        stop.step(now, &mut send);
        let Some(next) = stop.next_ns(now) else {
            break;
        };
        // Wake at the next due time, or a tick later at most, or on a frame.
        let millis = next
            .saturating_sub(now)
            .clamp(1, RESEND_NS)
            .div_ceil(1_000_000);
        let mut fds = [PollFd::new(socket.as_fd(), PollFlags::POLLIN)];
        // An error or interruption here only cuts the wait short; the loop reads and steps again.
        let _ = poll(
            &mut fds,
            PollTimeout::from(u16::try_from(millis).unwrap_or(u16::MAX)),
        );
        if since() >= END_NS.saturating_add(RESEND_NS) {
            // `next_ns` never passes `END_NS`, so this is only reached if steps stop being taken in time.
            break;
        }
    }
    report(t, &stop)
}

/// Read every frame queued, handing each decoded one to the stop.
fn drain(socket: &CanSocket, stop: &mut BusStop, since: impl Fn() -> u64) -> io::Result<()> {
    loop {
        match socket.read_frame() {
            Ok(CanFrame::Data(frame)) => {
                if let Id::Extended(id) = frame.id()
                    && let Ok(inbound) = decode(id.as_raw(), frame.data())
                {
                    stop.heard(since(), &inbound);
                }
            }
            // Error and remote frames carry no drive's word.
            Ok(_) => {}
            Err(e) if e.kind() == io::ErrorKind::WouldBlock => return Ok(()),
            Err(e) if e.kind() == io::ErrorKind::Interrupted => {}
            Err(e) => return Err(e),
        }
    }
}

fn write(socket: &CanSocket, frame: Frame) -> Result<(), SendError> {
    let Some(id) = ExtendedId::new(frame.id()) else {
        return Err(SendError::Failed(format!(
            "{:#x} is not a 29-bit ID",
            frame.id()
        )));
    };
    let Some(data) = CanDataFrame::new(id, &frame.data()) else {
        return Err(SendError::Failed("frame not built".to_owned()));
    };
    match socket.write_frame(&data) {
        Ok(()) => Ok(()),
        Err(e) if e.kind() == io::ErrorKind::WouldBlock || e.raw_os_error() == Some(ENOBUFS) => {
            Err(SendError::Full)
        }
        Err(e) => Err(SendError::Failed(e.to_string())),
    }
}
