//! The far end: stands in for a limb's drives. Every request to one of its slots is answered at once with a reply that
//! echoes the request's data, so the host can match it to its tick. It answers faster and more evenly than a drive
//! does (a drive's own reply time isn't measured yet, PLAN step 8), so what the host measures is the interfaces, the
//! wire and the two computers, which is the part this bench compares.

use std::time::Duration;

use socketcan::{CanDataFrame, CanFrame, EmbeddedFrame, ExtendedId, Frame, Socket};

use crate::frames;
use crate::link::{self, ENOBUFS};

/// How long one wait blocks, so a long quiet spell still loops.
const WAIT: Duration = Duration::from_secs(1);

/// Answer requests on `bus` for slots `0..slots` until the process is stopped.
pub(crate) fn run(bus: &str, slots: usize) -> Result<(), String> {
    if slots == 0 || slots > frames::MAX_SLOTS {
        return Err(format!("--slots must be 1 to {}", frames::MAX_SLOTS));
    }
    let _runtime_lock = link::claim_runtime_lock()?;
    let socket = link::open(bus).map_err(|e| format!("{bus}: {e}"))?;
    link::check_quiet(&socket, bus)?;
    let replies: Vec<ExtendedId> = (0..slots)
        .map(|s| frames::reply_id(s).and_then(ExtendedId::new))
        .collect::<Option<_>>()
        .ok_or("reply ID out of range")?;
    loop {
        link::wait(&socket, WAIT).map_err(|e| format!("{bus}: {e}"))?;
        while let Some(frame) = link::read(&socket).map_err(|e| format!("{bus}: {e}"))? {
            let CanFrame::Data(request) = frame else {
                continue;
            };
            let Some(id) = frames::request_slot(request.raw_id()).and_then(|s| replies.get(s))
            else {
                continue;
            };
            let reply = CanDataFrame::new(*id, request.data()).ok_or("frame build")?;
            match socket.write_frame(&CanFrame::Data(reply)) {
                Ok(()) => {}
                // A full queue drops the reply; the host counts it missing.
                Err(e) if e.raw_os_error() == Some(ENOBUFS) => {}
                Err(e) => return Err(format!("{bus}: write: {e}")),
            }
        }
    }
}
