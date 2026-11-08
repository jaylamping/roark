# robstride

The RobStride codec: typed frames to bytes and back, the per-model tables transcribed from the vendor manuals, and the SI
unit types every crate shares at the codec edge.

## What it does

- **Host frames out.** `encode` builds every frame the host may send (types 0, 1, 3, 4, 6, 7, 17, 18, 24), each returning a
  `Frame` to queue, never sending it. This list is the transmit allowlist (PLAN item 2): there is no way to build a save
  (22), baud rate (23) or protocol (25) frame, a Disable with the fault-clear byte set, or a write other than the six
  `Write` builds (`run_mode` MIT, `canTimeout` 1000, `spd_ref` 0, and the three limits checked against the drive's model).
- **Frames in.** `decode` turns any 29-bit ID and data bytes into a typed `Inbound` (status, report, identity, version,
  fault, parameter reply, or an echo of the host's own frame) or a typed `DecodeError`. It never panics.
- **Tables.** `Model` holds each actuator's MIT scales and caps, `Param` the 29 registers of §4.1.13, each row citing its
  manual section.
- **The drive's side**, for `sim-drive`: `drive::command` reads a host frame in full, and `drive::status`, `drive::report`,
  `drive::identity`, `drive::param_value` and `drive::param_refused` build what a drive sends. They return a
  `drive::DriveFrame`, never a `Frame`, so code that sends to the robot's drives can't send one.

Manuals: `hardware/docs/robstride/` in [marengo](https://github.com/jaylamping/marengo), RS00/RS02/RS04 revision 260713
and RS03 revision 261013. Citations use the manuals' own section numbers, which are the same in all four.

**Protocol rules:**

- **Frames:** CAN 2.0B extended, 1 Mbit/s, always 8 data bytes (§4). The 29-bit ID layout is in `Frame` and nowhere else.
- **Byte order:** MIT fields and status codes big-endian (§4.1.2); parameter index and value little-endian (§4.1.6).
- **Addresses:** the host is 0xFD (`HOST_ID`). A host frame carries the host in ID bits 15..8 and the target drive in
  bits 7..0; a drive's reply carries the drive in bits 15..8 and the host in bits 7..0. Type-0 replies use 0xFE in bits
  7..0 instead (§4.1.1). Type 1 has no host field: its bits 23..8 are the torque code.
- **Reserved bits:** zero on transmit; ignored on receive.
- **Matching a reply:** by bus, device ID and communication type, then against the drive the skeleton expects (its UID
  once commissioned). Never by device ID alone (can.md section 1). This crate gives the device and type; the bus layer
  knows the bus.
- **Strict both ways:** encode refuses an out-of-range value and never clamps; decode returns a typed frame or a typed
  error for any input.

## Must never

Do I/O, allocate, read the clock or panic on input (rust.md section 7, can.md section 1). It builds with `#![no_std]` to
prove it. Never clamp a value to make it fit, and never build a frame outside the allowlist.

## Talks to

Nothing: it is the leaf of the [map](https://github.com/jaylamping/roark/blob/main/conventions/architecture.md).
`skeleton` reads its model table and unit types; `sim-drive` uses `encode`, `decode` and its drive side; `can`,
`safety` and `robot-cli` will use `encode` and `decode`.

## Using it

Pair each drive's ID with its model in a `Drive`, build frames with `encode` (and `Write` for parameter writes), and read
everything that comes off the bus with `decode`. Values come out in SI only through the drive's model.

```rust
use robstride::{DeviceId, Drive, Inbound, Model, Write, decode, encode};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let elbow = Drive::new(DeviceId::new(14)?, Model::Rs02);

    // Frames to send: an enable, then the runtime's canTimeout write (1000 × 50 µs = 50 ms).
    let enable = encode::enable(elbow.id());
    assert_eq!(enable.id(), 0x0300_FD0E);
    let timeout = encode::param_write(&Write::can_timeout(elbow));
    assert_eq!(timeout.data(), [0x28, 0x70, 0, 0, 0xE8, 0x03, 0, 0]);

    // A frame off the bus: drive 14's status, in Run, mid-scale codes, 25.0 °C.
    match decode(0x0280_0EFD, &[0x80, 0x00, 0x80, 0x00, 0x80, 0x00, 0x00, 0xFA])? {
        Inbound::Status(status) => {
            let feedback = status.feedback(elbow.model())?;
            assert!(feedback.position.get().abs() < 0.001);
            assert_eq!(feedback.temperature.get(), 25.0);
        }
        other => panic!("not a status: {other:?}"),
    }
    Ok(())
}
```
