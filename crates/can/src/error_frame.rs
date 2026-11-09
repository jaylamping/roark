//! SocketCAN error frames as a typed bus error (can.md section 2). The class bits and data bytes are the kernel's
//! (`include/uapi/linux/can/error.h`).

/// Something wrong with the bus itself, from an error frame or the socket.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum BusError {
    /// The controller went bus-off (`CAN_ERR_BUSOFF`). Latched: the adapter may recover by itself (PLAN.md item 3).
    BusOff,
    /// The controller is error-passive (`CAN_ERR_CRTL_RX_PASSIVE` or `_TX_PASSIVE`).
    ErrorPassive,
    /// The controller passed the error-warning level (`CAN_ERR_CRTL_RX_WARNING` or `_TX_WARNING`).
    ErrorWarning,
    /// The controller is back to error-active (`CAN_ERR_CRTL_ACTIVE`): not an error, it ends `ErrorPassive`.
    ErrorActive,
    /// The controller's receive buffer overflowed (`CAN_ERR_CRTL_RX_OVERFLOW`).
    RxOverflow,
    /// A transmit timed out (`CAN_ERR_TX_TIMEOUT`).
    TxTimeout,
    /// The interface is down (`ENETDOWN`). Latched.
    InterfaceDown,
    /// The interface is gone (`ENODEV`). Latched.
    InterfaceGone,
    /// Any other error class, as its bits.
    Other(u32),
}

impl BusError {
    /// Whether this error stops the bus for good (PLAN.md item 6 Bus-off row).
    #[must_use]
    pub const fn latches(self) -> bool {
        matches!(
            self,
            Self::BusOff | Self::InterfaceDown | Self::InterfaceGone
        )
    }
}

const TX_TIMEOUT: u32 = 0x0001;
const CRTL: u32 = 0x0004;
const BUSOFF: u32 = 0x0040;
const CRTL_RX_OVERFLOW: u8 = 0x01;
const CRTL_RX_WARNING: u8 = 0x04;
const CRTL_TX_WARNING: u8 = 0x08;
const CRTL_RX_PASSIVE: u8 = 0x10;
const CRTL_TX_PASSIVE: u8 = 0x20;
const CRTL_ACTIVE: u8 = 0x40;

/// Whether an error frame says the controller is error-passive (true) or below it, warning or active (false); `None`
/// when it says nothing about the controller's state (no controller class, or only an overflow bit). Read apart from
/// [`classify`], since one frame can carry a state change beside a more severe flag.
#[must_use]
pub(crate) fn controller_passive(class: u32, data: [u8; 8]) -> Option<bool> {
    let [_, crtl, ..] = data;
    if class & CRTL == 0 {
        None
    } else if crtl & (CRTL_RX_PASSIVE | CRTL_TX_PASSIVE) != 0 {
        Some(true)
    } else if crtl & (CRTL_RX_WARNING | CRTL_TX_WARNING | CRTL_ACTIVE) != 0 {
        Some(false)
    } else {
        None
    }
}

/// The most severe error an error frame carries: `class` is its ID without `CAN_ERR_FLAG`, `data` its bytes.
#[must_use]
pub fn classify(class: u32, data: &[u8; 8]) -> BusError {
    let [_, crtl, ..] = *data;
    if class & BUSOFF != 0 {
        BusError::BusOff
    } else if class & CRTL != 0 && crtl & (CRTL_RX_PASSIVE | CRTL_TX_PASSIVE) != 0 {
        BusError::ErrorPassive
    } else if class & CRTL != 0 && crtl & CRTL_RX_OVERFLOW != 0 {
        BusError::RxOverflow
    } else if class & CRTL != 0 && crtl & (CRTL_RX_WARNING | CRTL_TX_WARNING) != 0 {
        BusError::ErrorWarning
    } else if class & CRTL != 0 && crtl & CRTL_ACTIVE != 0 {
        BusError::ErrorActive
    } else if class & TX_TIMEOUT != 0 {
        BusError::TxTimeout
    } else {
        BusError::Other(class)
    }
}
