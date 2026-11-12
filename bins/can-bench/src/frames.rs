//! The bench's own frames. They are built so no RobStride drive can act on them: communication types 30 (request) and
//! 31 (reply), which no RobStride manual defines (§4 lists 0 to 25), sent to addresses 0x80 and up, above any drive ID
//! (1 to 127, manual §4). They are 8-byte extended frames like a drive's MIT command and status, so each one takes as
//! long on the wire, and a request wins arbitration over a reply as a command (type 1) does over a status (type 2).

/// The communication type of a request from the host under test.
pub(crate) const REQUEST_TYPE: u32 = 30;
/// The communication type of a reply from the responder.
pub(crate) const REPLY_TYPE: u32 = 31;
/// The address of slot 0; slot `n` is this plus `n`. Above every drive ID.
pub(crate) const FIRST_ADDRESS: u32 = 0x80;
/// The most slots one run may have: 16 fake drives, more than any limb.
pub(crate) const MAX_SLOTS: usize = 16;
/// The host's address, as in a RobStride frame (`robstride::frame::HOST_ID`).
const HOST: u32 = 0xFD;

/// The ID of the request to `slot`.
pub(crate) fn request_id(slot: usize) -> Option<u32> {
    if slot >= MAX_SLOTS {
        return None;
    }
    let slot = u32::try_from(slot).ok()?;
    Some((REQUEST_TYPE << 24) | (HOST << 8) | (FIRST_ADDRESS + slot))
}

/// The ID of `slot`'s reply.
pub(crate) fn reply_id(slot: usize) -> Option<u32> {
    if slot >= MAX_SLOTS {
        return None;
    }
    let slot = u32::try_from(slot).ok()?;
    Some((REPLY_TYPE << 24) | ((FIRST_ADDRESS + slot) << 8) | HOST)
}

/// The slot a request is for, if `id` is one of this bench's requests.
pub(crate) fn request_slot(id: u32) -> Option<usize> {
    (0..MAX_SLOTS).find(|&s| request_id(s) == Some(id))
}

/// The slot a reply is from, if `id` is one of this bench's replies.
pub(crate) fn reply_slot(id: u32) -> Option<usize> {
    (0..MAX_SLOTS).find(|&s| reply_id(s) == Some(id))
}

/// A request's data: the tick it was sent in, then a running count, both little-endian. The reply echoes it.
pub(crate) fn payload(tick: u32, count: u32) -> [u8; 8] {
    let t = tick.to_le_bytes();
    let c = count.to_le_bytes();
    [t[0], t[1], t[2], t[3], c[0], c[1], c[2], c[3]]
}

/// The tick a reply's data names.
pub(crate) fn payload_tick(data: &[u8]) -> Option<u32> {
    let bytes: [u8; 4] = data.get(..4)?.try_into().ok()?;
    Some(u32::from_le_bytes(bytes))
}

#[cfg(test)]
mod tests {
    use super::{MAX_SLOTS, reply_id, reply_slot, request_id, request_slot};

    /// Guards: safety - no drive can act on a bench frame (README "Must never"): every request and reply has a
    /// communication type no RobStride manual defines (above 25) and both address bytes above every drive ID (above
    /// 127), and each ID maps back to its own slot only. Every request's ID is below every reply's, so a host's
    /// requests win arbitration over the replies to the tick before.
    #[test]
    fn no_drive_can_act_on_a_bench_frame() {
        for slot in 0..MAX_SLOTS {
            for (id, back) in [
                (request_id(slot), request_id(slot).and_then(request_slot)),
                (reply_id(slot), reply_id(slot).and_then(reply_slot)),
            ] {
                let id = id.unwrap_or(0);
                assert!(id >> 24 > 25 && id <= 0x1FFF_FFFF, "type of {id:08X}");
                assert!(
                    [id & 0xFF, (id >> 8) & 0xFF].iter().all(|&a| a > 127),
                    "addresses of {id:08X}"
                );
                assert_eq!(back, Some(slot));
            }
            assert_eq!(request_id(slot).and_then(reply_slot), None);
            assert_eq!(reply_id(slot).and_then(request_slot), None);
            for other in 0..MAX_SLOTS {
                assert!(
                    request_id(slot) < reply_id(other),
                    "request {slot} after reply {other}"
                );
            }
        }
        assert_eq!(request_id(MAX_SLOTS), None);
        assert_eq!(reply_id(MAX_SLOTS), None);
    }
}
