//! The 29-bit extended ID layout, built and parsed here and nowhere else (rust.md section 7).
//!
//! ```text
//! bits 28..24  communication type
//! bits 23..8   data area 2: usually bits 15..8 = the sender (host or drive), bits 23..16 = type-specific;
//!              type 1 carries the torque code in all 16 bits
//! bits 7..0    destination: the target drive, the host (0xFD) or the identity marker (0xFE)
//! ```
//!
//! Manual §4 (all four manuals), "the extended frame format is adopted as follows".

/// The host's CAN ID in every frame it sends and every reply addressed to it. 0xFD is the vendor tools' default (manual
/// §4.1.14 example) and above any drive ID (1 to 127).
pub const HOST_ID: u8 = 0xFD;

/// The low byte of every type-0 reply (manual §4.1.1).
pub(crate) const IDENTITY_MARKER: u8 = 0xFE;

/// Highest valid 29-bit extended ID.
const EXTENDED_ID_MAX: u32 = 0x1FFF_FFFF;

/// One CAN 2.0B extended data frame, always 8 data bytes. Built only by [`crate::encode`], so its ID fits in 29 bits.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Frame {
    id: u32,
    data: [u8; 8],
}

impl Frame {
    /// `kind` must be below 32; every caller passes a constant communication type.
    pub(crate) const fn new(
        kind: u8,
        area_hi: u8,
        area_lo: u8,
        destination: u8,
        data: [u8; 8],
    ) -> Self {
        assert!(kind < 32, "communication type is 5 bits");
        Self {
            id: u32::from_be_bytes([kind, area_hi, area_lo, destination]),
            data,
        }
    }

    /// The 29-bit extended ID.
    #[must_use]
    pub const fn id(&self) -> u32 {
        self.id
    }

    /// The 8 data bytes.
    #[must_use]
    pub const fn data(&self) -> [u8; 8] {
        self.data
    }
}

/// An ID split into its fields: communication type, data area 2 high and low bytes, destination. Keeps the whole ID too,
/// for errors that name the frame.
pub(crate) struct Parts {
    pub(crate) id: u32,
    pub(crate) kind: u8,
    pub(crate) area_hi: u8,
    pub(crate) area_lo: u8,
    pub(crate) destination: u8,
}

/// `None` if the ID is wider than 29 bits.
pub(crate) const fn parts(id: u32) -> Option<Parts> {
    if id > EXTENDED_ID_MAX {
        return None;
    }
    let [kind, area_hi, area_lo, destination] = id.to_be_bytes();
    Some(Parts {
        id,
        kind,
        area_hi,
        area_lo,
        destination,
    })
}
