//! The bench's own frames. They are built so no RobStride drive can act on them: communication types 31 (request) and
//! 30 (reply), which no RobStride manual defines (§4 lists 0 to 25), sent to addresses 0x80 and up, above any drive ID
//! (1 to 127, manual §4). They are 8-byte extended frames like a drive's MIT command and status, so each one takes as
//! long on the wire.

/// The communication type of a request from the host under test.
pub(crate) const REQUEST_TYPE: u32 = 31;
/// The communication type of a reply from the responder.
pub(crate) const REPLY_TYPE: u32 = 30;
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

/// Whether `id` is any frame of this bench's.
pub(crate) fn is_bench(id: u32) -> bool {
    request_slot(id).is_some() || reply_slot(id).is_some()
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
