//! What preflight and the enable sequence are stepped with: one drive as its bus's latest snapshot shows it, and the
//! address that says which drive that must be. CAN IDs are unique only per bus (the skeleton allows the same ID on two
//! buses), so a drive is its bus and its ID together; a view of the right ID from another bus's snapshot is another
//! drive.

use core::fmt;

use can::{DriveView, LimbView, Snapshot};
use robstride::DeviceId;
use skeleton::BusName;

/// The longest bus name: the kernel's interface name limit, which the skeleton holds every bus name to.
const BUS_NAME_MAX: usize = 15;

/// A drive by its bus and its CAN ID. `Copy`, with no allocation, so preflight and the enable sequence can carry it
/// through the control thread's tick (rust.md section 6).
#[derive(Clone, Copy, PartialEq, Eq)]
pub struct DriveAddress {
    bus: [u8; BUS_NAME_MAX],
    bus_len: usize,
    id: DeviceId,
}

impl DriveAddress {
    /// Drive `id` on `bus`, or `None` for a bus name longer than the skeleton allows.
    #[must_use]
    pub fn new(bus: &BusName, id: DeviceId) -> Option<Self> {
        let name = bus.as_str().as_bytes();
        let mut bytes = [0; BUS_NAME_MAX];
        bytes.get_mut(..name.len())?.copy_from_slice(name);
        Some(Self {
            bus: bytes,
            bus_len: name.len(),
            id,
        })
    }

    /// Drive `id` on `bus` for the operator's line, the name cut to the skeleton's limit (which no parsed bus name
    /// passes). Never compared: [`Self::is`] compares the whole name.
    pub(crate) fn naming(bus: &BusName, id: DeviceId) -> Self {
        let name = bus.as_str().as_bytes();
        let len = name.len().min(BUS_NAME_MAX);
        let mut bytes = [0; BUS_NAME_MAX];
        if let (Some(to), Some(from)) = (bytes.get_mut(..len), name.get(..len)) {
            to.copy_from_slice(from);
        }
        Self {
            bus: bytes,
            bus_len: len,
            id,
        }
    }

    /// Whether drive `id` on `bus` is this one: the same ID and the whole bus name the same.
    pub(crate) fn is(&self, bus: &BusName, id: DeviceId) -> bool {
        self.id == id && Some(bus.as_str().as_bytes()) == self.bus.get(..self.bus_len)
    }

    /// The bus's name.
    #[must_use]
    pub fn bus(&self) -> &str {
        self.bus
            .get(..self.bus_len)
            .and_then(|b| core::str::from_utf8(b).ok())
            .unwrap_or("?")
    }

    /// The CAN ID.
    #[must_use]
    pub const fn id(&self) -> DeviceId {
        self.id
    }
}

impl fmt::Display for DriveAddress {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "drive {} on {}", self.id.get(), self.bus())
    }
}

impl fmt::Debug for DriveAddress {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("DriveAddress")
            .field("bus", &self.bus())
            .field("id", &self.id.get())
            .finish_non_exhaustive()
    }
}

/// One drive as the latest snapshot of a bus shows it: the bus that snapshot came from, the drive's view and its
/// limb's. Preflight and the enable sequence take only this, so each checks that it is its own drive on its own bus
/// and that the limb hasn't stopped or been cleared since it began.
#[derive(Clone, Copy, Debug)]
pub struct Seen<'a> {
    /// The bus whose snapshot this is.
    pub bus: &'a BusName,
    /// The drive.
    pub view: &'a DriveView,
    /// The drive's limb.
    pub limb: &'a LimbView,
}

impl<'a> Seen<'a> {
    /// Slot `slot` of `snapshot`, the latest from `bus`, with that drive's limb from the same snapshot; `None` if the
    /// snapshot has no drive in that slot or no limb for it.
    #[must_use]
    pub fn of(bus: &'a BusName, snapshot: &'a Snapshot, slot: usize) -> Option<Self> {
        let view = snapshot.drive(slot)?;
        let limb = snapshot.limb(view.limb)?;
        Some(Self { bus, view, limb })
    }

    /// The address of the drive seen.
    pub(crate) fn address(&self) -> DriveAddress {
        DriveAddress::naming(self.bus, self.view.device)
    }
}
