//! Helpers shared by the codec's test files.

use robstride::{DeviceId, Drive, Header, Mode, Model, StatusFault};

#[expect(
    clippy::unwrap_used,
    reason = "test helper for known-good IDs; clippy allows unwrap only inside #[test] bodies"
)]
pub(crate) fn id(n: u8) -> DeviceId {
    DeviceId::new(u64::from(n)).unwrap()
}

pub(crate) fn header(device: u8, mode: Mode, faults: &[StatusFault]) -> Header {
    Header {
        device: id(device),
        mode,
        faults: faults.iter().copied().collect(),
    }
}

/// Drive `n`, a `model`.
pub(crate) fn drive(model: Model, n: u8) -> Drive {
    Drive::new(id(n), model)
}
