//! The codec against the manuals and the bench: exact bytes out, typed frames in, and the refusals (can.md section 1,
//! "Tests"). Manual citations are section numbers; every manual has the same section layout. Bench rows cite their capture.
#![expect(
    clippy::unwrap_used,
    reason = "the table helpers build known-good values; clippy allows unwrap only inside #[test] bodies"
)]

use robstride::{
    Celsius, DecodeError, DeviceId, Echo, EchoKind, EncodeError, Frame, Header, Inbound,
    MitCommand, MitField, Mode, Model, NewtonMeters, NmPerRad, NmSecPerRad, ParamOutcome,
    RadPerSec, Radians, Reporting, Status, StatusFault, Uid, UnvouchedModel, decode, encode,
};

fn id(n: u8) -> DeviceId {
    DeviceId::new(u64::from(n)).unwrap()
}

fn mit(position: f64, velocity: f64, kp: f64, kd: f64, torque: f64) -> MitCommand {
    MitCommand {
        position: Radians::new(position).unwrap(),
        velocity: RadPerSec::new(velocity).unwrap(),
        kp: NmPerRad::new(kp).unwrap(),
        kd: NmSecPerRad::new(kd).unwrap(),
        torque: NewtonMeters::new(torque).unwrap(),
    }
}

fn header(device: u8, mode: Mode, faults: &[StatusFault]) -> Header {
    Header {
        device: id(device),
        mode,
        faults: faults.iter().copied().collect(),
    }
}

/// Guards: protocol - every frame the host sends, byte for byte, RobStride manuals §4.1.1 to §4.1.11 and bench captures.
#[test]
fn encoded_frames_match_the_manuals() {
    let rows: Vec<(&str, Frame, u32, [u8; 8])> = vec![
        // §4.1.1; bench candump `0000FD01#0000000000000000`, firmware 0.3.1.42.
        ("get ID", encode::get_id(id(1)), 0x0000_FD01, [0; 8]),
        (
            "enable, §4.1.3",
            encode::enable(id(12)),
            0x0300_FD0C,
            [0; 8],
        ),
        // §4.1.4: "when the motor is running normally, 0 must be cleared in the data field". Byte 0 = 1 would clear faults.
        (
            "disable, §4.1.4",
            encode::disable(id(12)),
            0x0400_FD0C,
            [0; 8],
        ),
        (
            "set zero, §4.1.5",
            encode::set_zero(id(12)),
            0x0600_FD0C,
            [1, 0, 0, 0, 0, 0, 0, 0],
        ),
        (
            "version query, §4.1.4",
            encode::version_query(id(5)),
            0x0400_FD05,
            [0, 0xC4, 0, 0, 0, 0, 0, 0],
        ),
        (
            "set ID 1 to 11, §4.1.5 type 7",
            encode::set_id(id(1), id(11)),
            0x070B_FD01,
            [0; 8],
        ),
        (
            "active reporting on, §4.1.11",
            encode::active_reporting(id(12), Reporting::On),
            0x1800_FD0C,
            [1, 2, 3, 4, 5, 6, 1, 0],
        ),
        (
            "active reporting off, §4.1.11",
            encode::active_reporting(id(3), Reporting::Off),
            0x1800_FD03,
            [1, 2, 3, 4, 5, 6, 0, 0],
        ),
        // §4.1.2: torque in ID bits 23..8; position, velocity, Kp, Kd big-endian in bytes 0..8. Zero is half a code above
        // the middle of the signed ranges: 32767.5 rounds to 0x8000.
        (
            "MIT, all zero, RS03",
            encode::mit(Model::Rs03, id(1), &mit(0.0, 0.0, 0.0, 0.0, 0.0)).unwrap(),
            0x0180_0001,
            [0x80, 0x00, 0x80, 0x00, 0, 0, 0, 0],
        ),
        (
            "MIT, every field at its range end, RS02",
            encode::mit(Model::Rs02, id(14), &mit(12.57, -44.0, 500.0, 5.0, 17.0)).unwrap(),
            0x01FF_FF0E,
            [0xFF, 0xFF, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0xFF],
        ),
        (
            // round((1.25 + 20) × 65535 / 40) = round(34815.47) = 0x87FF. Under the old ±50 scale the drive read this frame's predecessor
            // (0x8332) as 0.50 rad/s; see the RS03 velocity test below.
            "MIT, RS03 cruise 1.25 rad/s",
            encode::mit(Model::Rs03, id(1), &mit(0.0, 1.25, 0.0, 0.0, 0.0)).unwrap(),
            0x0180_0001,
            [0x80, 0x00, 0x87, 0xFF, 0, 0, 0, 0],
        ),
    ];
    for (what, frame, want_id, want_data) in rows {
        assert_eq!(
            (frame.id(), frame.data()),
            (want_id, want_data),
            "{what}: got {:08X}#{:02X?}",
            frame.id(),
            frame.data()
        );
    }
}

/// Guards: protocol - every frame the host reads, typed, RobStride manuals §4.1.1 to §4.1.14 and bench captures.
#[test]
#[expect(
    clippy::too_many_lines,
    reason = "one table, one row per received frame shape"
)]
fn decoded_frames_match_the_manuals() {
    let bench_status = [0x7e, 0x28, 0x75, 0x10, 0x7d, 0x99, 0x00, 0xe6];
    let bench_codes = Status {
        header: header(1, Mode::Run, &[]),
        position: 0x7e28,
        velocity: 0x7510,
        torque: 0x7d99,
        temperature: Celsius::new(23.0).unwrap(),
    };
    let echo = |kind, target| {
        Inbound::Echo(Echo {
            kind,
            target: id(target),
        })
    };
    let rows: Vec<(&str, u32, [u8; 8], Inbound)> = vec![
        (
            // §4.1.1; bench candump on the Pi, firmware 0.3.1.42.
            "identity reply",
            0x0000_01FE,
            [0x45, 0x7B, 0x30, 0x02, 0x0C, 0x32, 0x38, 0x17],
            Inbound::Identity {
                device: id(1),
                uid: Uid([0x45, 0x7B, 0x30, 0x02, 0x0C, 0x32, 0x38, 0x17]),
            },
        ),
        (
            // §4.1.2 type 2; bench capture cd-20261003T145133Z, right_shoulder_pitch (RS03, ID 1) during a ramp.
            "status reply, Run, no faults",
            0x0280_01FD,
            bench_status,
            Inbound::Status(bench_codes),
        ),
        (
            // §4.1.2: fault bits 21..16, mode bits 23..22. Bits 16 (undervoltage) and 21 (uncalibrated), Reset mode.
            "status reply with faults",
            0x0221_01FD,
            bench_status,
            Inbound::Status(Status {
                header: header(
                    1,
                    Mode::Reset,
                    &[StatusFault::Undervoltage, StatusFault::Uncalibrated],
                ),
                ..bench_codes
            }),
        ),
        (
            "status reply, every fault bit, calibration mode",
            0x027F_01FD,
            bench_status,
            Inbound::Status(Status {
                header: header(1, Mode::Calibration, &StatusFault::ALL),
                ..bench_codes
            }),
        ),
        (
            "active report, §4.1.11",
            0x1880_01FD,
            bench_status,
            Inbound::Report(bench_codes),
        ),
        (
            // §4.1.4: a type-2 reply starting 00 C4 56 answers the version query; it is not a pose. Bench firmware 0.3.1.42.
            "version reply",
            0x0280_05FD,
            [0x00, 0xC4, 0x56, 0x00, 0x03, 0x01, 0x2A, 0x00],
            Inbound::Version {
                header: header(5, Mode::Run, &[]),
                version: [0x00, 0x03, 0x01, 0x2A],
            },
        ),
        (
            // §4.1.8: bytes 0..4 faults, 4..8 warnings. The manual gives bit meanings but no byte order, so they stay raw.
            "fault report",
            0x1500_01FD,
            [0x01, 0, 0, 0, 0x01, 0, 0, 0],
            Inbound::Fault {
                device: id(1),
                faults: [0x01, 0, 0, 0],
                warnings: [0x01, 0, 0, 0],
            },
        ),
        (
            // §4.1.14 worked example: reading loc_kp (0x701E) from ID 0x7F returns 30.0 as a little-endian f32.
            "parameter read reply",
            0x1100_7FFD,
            [0x1E, 0x70, 0, 0, 0x00, 0x00, 0xF0, 0x41],
            Inbound::Param {
                device: id(0x7F),
                index: 0x701E,
                outcome: ParamOutcome::Read([0x00, 0x00, 0xF0, 0x41]),
            },
        ),
        (
            // §4.1.6: bits 23..16 are 00 on success, 01 on failure.
            "parameter read refused",
            0x1101_7FFD,
            [0x1E, 0x70, 0, 0, 0, 0, 0, 0],
            Inbound::Param {
                device: id(0x7F),
                index: 0x701E,
                outcome: ParamOutcome::Refused,
            },
        ),
        // The host's own frames come back as echoes (loopback with RECV_OWN_MSGS, can.md section 2).
        (
            "echo: get ID",
            0x0000_FD01,
            [0; 8],
            echo(EchoKind::GetId, 1),
        ),
        (
            "echo: MIT",
            0x0180_0001,
            [0x80, 0x00, 0x80, 0x00, 0, 0, 0, 0],
            echo(EchoKind::Mit, 1),
        ),
        (
            "echo: enable",
            0x0300_FD0C,
            [0; 8],
            echo(EchoKind::Enable, 12),
        ),
        (
            "echo: disable",
            0x0400_FD0C,
            [0; 8],
            echo(EchoKind::Disable, 12),
        ),
        (
            "echo: fault clear",
            0x0400_FD0C,
            [1, 0, 0, 0, 0, 0, 0, 0],
            echo(EchoKind::FaultClear, 12),
        ),
        (
            "echo: version query",
            0x0400_FD05,
            [0, 0xC4, 0, 0, 0, 0, 0, 0],
            echo(EchoKind::VersionQuery, 5),
        ),
        (
            "echo: set zero",
            0x0600_FD0C,
            [1, 0, 0, 0, 0, 0, 0, 0],
            echo(EchoKind::SetZero, 12),
        ),
        (
            "echo: set ID",
            0x070B_FD01,
            [0; 8],
            echo(EchoKind::SetId { new: id(11) }, 1),
        ),
        (
            "echo: parameter read",
            0x1100_FD7F,
            [0x1E, 0x70, 0, 0, 0, 0, 0, 0],
            echo(EchoKind::ParamRead, 0x7F),
        ),
        (
            "echo: parameter write",
            0x1200_FD7F,
            [0x05, 0x70, 0, 0, 0, 0, 0, 0],
            echo(EchoKind::ParamWrite, 0x7F),
        ),
        (
            "echo: reporting on",
            0x1800_FD0C,
            [1, 2, 3, 4, 5, 6, 1, 0],
            echo(EchoKind::Reporting(Reporting::On), 12),
        ),
        (
            "echo: reporting off",
            0x1800_FD03,
            [1, 2, 3, 4, 5, 6, 0, 0],
            echo(EchoKind::Reporting(Reporting::Off), 3),
        ),
    ];
    for (what, frame_id, data, want) in rows {
        assert_eq!(decode(frame_id, &data), Ok(want), "{what}");
    }
}

/// Guards: protocol - decode never panics and names what is wrong with a frame it can't read (can.md section 1, "Strict both ways").
#[test]
#[expect(
    clippy::too_many_lines,
    reason = "one table, one row per malformed frame"
)]
fn malformed_frames_are_refused() {
    let status = [0x7e, 0x28, 0x75, 0x10, 0x7d, 0x99, 0x00, 0xe6];
    let rows: Vec<(&str, u32, &[u8], DecodeError)> = vec![
        (
            "ID wider than 29 bits",
            0x2000_0000,
            &[0; 8],
            DecodeError::IdTooWide(0x2000_0000),
        ),
        (
            "short frame",
            0x0280_01FD,
            &status[..7],
            DecodeError::BadLength(7),
        ),
        (
            "long frame",
            0x0280_01FD,
            &[0; 9],
            DecodeError::BadLength(9),
        ),
        ("empty frame", 0x0280_01FD, &[], DecodeError::BadLength(0)),
        (
            "unknown type 5",
            0x0500_FD01,
            &[0; 8],
            DecodeError::UnknownType(5),
        ),
        (
            "unknown type 31",
            0x1F00_FD01,
            &[0; 8],
            DecodeError::UnknownType(31),
        ),
        // §4.1.9, §4.1.10, §4.1.12: save, baud rate and protocol frames. The host never sends them (PLAN item 2).
        (
            "save frame on the bus",
            0x1600_FD01,
            &[1, 2, 3, 4, 5, 6, 7, 8],
            DecodeError::ForeignType(22),
        ),
        (
            "baud rate frame on the bus",
            0x1700_FD01,
            &[1, 2, 3, 4, 5, 6, 1, 0],
            DecodeError::ForeignType(23),
        ),
        (
            "protocol frame on the bus",
            0x1900_FD01,
            &[1, 2, 3, 4, 5, 6, 0, 0],
            DecodeError::ForeignType(25),
        ),
        (
            "status addressed to another host",
            0x0280_01FE,
            &status,
            DecodeError::OtherHost(0xFE),
        ),
        (
            "status from device 0",
            0x0280_00FD,
            &status,
            DecodeError::BadDeviceId(0),
        ),
        (
            "status from device 128",
            0x0280_80FD,
            &status,
            DecodeError::BadDeviceId(128),
        ),
        (
            "status in reserved mode 3",
            0x02C0_01FD,
            &status,
            DecodeError::ReservedMode,
        ),
        (
            "command from another host",
            0x0300_FE0C,
            &[0; 8],
            DecodeError::OtherHost(0xFE),
        ),
        (
            "MIT frame to device 0",
            0x0180_0000,
            &[0; 8],
            DecodeError::BadDeviceId(0),
        ),
        (
            "identity reply from device 0",
            0x0000_00FE,
            &[0; 8],
            DecodeError::BadDeviceId(0),
        ),
        (
            "set zero without its flag byte",
            0x0600_FD0C,
            &[0; 8],
            DecodeError::UnexpectedData(6),
        ),
        (
            "disable with other bytes set",
            0x0400_FD0C,
            &[0, 0, 0, 0, 0, 0, 0, 1],
            DecodeError::UnexpectedData(4),
        ),
        (
            "reporting with an unknown switch",
            0x1800_FD0C,
            &[1, 2, 3, 4, 5, 6, 2, 0],
            DecodeError::UnexpectedData(24),
        ),
        (
            "reporting without its fixed bytes",
            0x1800_FD0C,
            &[0, 0, 0, 0, 0, 0, 1, 0],
            DecodeError::UnexpectedData(24),
        ),
        (
            "parameter reply with an unknown result",
            0x1102_7FFD,
            &[0x1E, 0x70, 0, 0, 0, 0, 0, 0],
            DecodeError::UnexpectedData(17),
        ),
        (
            "set ID to 0",
            0x0700_FD01,
            &[0; 8],
            DecodeError::BadDeviceId(0),
        ),
    ];
    for (what, frame_id, data, want) in rows {
        assert_eq!(decode(frame_id, data), Err(want), "{what}");
    }
}

/// Guards: protocol - encode refuses an out-of-range MIT field and a model whose scales aren't settled, never clamps (PLAN item 3, can.md section 1).
#[test]
fn mit_encode_refuses_rather_than_clamps() {
    let rows: Vec<(&str, Model, MitCommand, EncodeError)> = vec![
        (
            "position past +12.57 rad",
            Model::Rs03,
            mit(12.58, 0.0, 0.0, 0.0, 0.0),
            EncodeError::OutOfRange {
                field: MitField::Position,
                min: -12.57,
                max: 12.57,
            },
        ),
        (
            "RS03 velocity past 20 rad/s",
            Model::Rs03,
            mit(0.0, -20.01, 0.0, 0.0, 0.0),
            EncodeError::OutOfRange {
                field: MitField::Velocity,
                min: -20.0,
                max: 20.0,
            },
        ),
        (
            "RS02 Kp past 500",
            Model::Rs02,
            mit(0.0, 0.0, 500.1, 0.0, 0.0),
            EncodeError::OutOfRange {
                field: MitField::Kp,
                min: 0.0,
                max: 500.0,
            },
        ),
        (
            "negative Kd",
            Model::Rs04,
            mit(0.0, 0.0, 0.0, -0.1, 0.0),
            EncodeError::OutOfRange {
                field: MitField::Kd,
                min: 0.0,
                max: 100.0,
            },
        ),
        (
            "RS04 torque past 120 N·m",
            Model::Rs04,
            mit(0.0, 0.0, 0.0, 0.0, 120.5),
            EncodeError::OutOfRange {
                field: MitField::Torque,
                min: -120.0,
                max: 120.0,
            },
        ),
        (
            // PLAN item 2, "Open fact: RS00 MIT scales": the manuals and the legacy code disagree, so nothing is sent.
            "RS00 until its scales are settled",
            Model::Rs00,
            mit(0.0, 0.0, 0.0, 0.0, 0.0),
            EncodeError::UnvouchedModel(Model::Rs00),
        ),
    ];
    for (what, model, command, want) in rows {
        assert_eq!(encode::mit(model, id(1), &command), Err(want), "{what}");
    }
}

/// Guards: number - per-model MIT ranges, RobStride manuals §4.1.2 and the §4.4 sample's `#define`s (RS03 velocity ±20, measured on the bench).
#[test]
fn mit_ranges_match_the_manuals() {
    let rows = [
        // (model, position, velocity, Kp, Kd, torque)
        (Model::Rs02, 12.57, 44.0, 500.0, 5.0, 17.0),
        (Model::Rs03, 12.57, 20.0, 5000.0, 100.0, 60.0),
        (Model::Rs04, 12.57, 15.0, 5000.0, 100.0, 120.0),
    ];
    for (model, position, velocity, kp, kd, torque) in rows {
        let s = model.mit_scales().unwrap();
        let got = (
            s.position.max,
            s.velocity.max,
            s.kp.max,
            s.kd.max,
            s.torque.max,
        );
        assert_eq!(got, (position, velocity, kp, kd, torque), "{model}");
        assert_eq!(
            (
                s.position.min,
                s.velocity.min,
                s.kp.min,
                s.kd.min,
                s.torque.min
            ),
            (-position, -velocity, 0.0, 0.0, -torque),
            "{model}"
        );
    }
    assert_eq!(Model::Rs00.mit_scales(), Err(UnvouchedModel(Model::Rs00)));
}

/// Guards: number - every 16-bit MIT code survives decode then encode unchanged, so no value drifts by a code (rust.md section 7).
#[test]
fn mit_codes_round_trip() {
    for model in [Model::Rs02, Model::Rs03, Model::Rs04] {
        let s = model.mit_scales().unwrap();
        for range in [s.position, s.velocity, s.kp, s.kd, s.torque] {
            for code in 0..=u16::MAX {
                assert_eq!(
                    range.code(range.value(code)),
                    Some(code),
                    "{model} {range:?} code {code}"
                );
            }
        }
    }
}

/// Guards: bug - RS03 velocity was decoded at ±50 rad/s, 2.5x high (marengo docs/commissioning/firmware/robstride-mit-ranges.md, capture cd-20261003T145133Z).
#[test]
fn rs03_status_velocity_matches_its_position_slope() {
    // (microseconds since the first frame, payload): consecutive type-2 frames from right_shoulder_pitch (RS03, ID 1,
    // firmware 0.3.1.42) during the cruise of a downward ramp, 10.615 to 10.656 s into the capture.
    let ramp: [(u32, [u8; 8]); 9] = [
        (0, [0x7e, 0x28, 0x75, 0x10, 0x7d, 0x99, 0x00, 0xe6]),
        (5_049, [0x7e, 0x12, 0x75, 0x1f, 0x7e, 0xaf, 0x00, 0xe6]),
        (10_100, [0x7d, 0xfb, 0x74, 0x9c, 0x7e, 0x71, 0x00, 0xe6]),
        (15_149, [0x7d, 0xe4, 0x75, 0x00, 0x7d, 0x99, 0x00, 0xe6]),
        (20_199, [0x7d, 0xce, 0x75, 0x91, 0x7d, 0x5a, 0x00, 0xe6]),
        (25_249, [0x7d, 0xb8, 0x75, 0xb0, 0x7e, 0x47, 0x00, 0xe6]),
        (30_355, [0x7d, 0xa1, 0x74, 0x92, 0x7e, 0x7f, 0x00, 0xe6]),
        (35_504, [0x7d, 0x8a, 0x75, 0x22, 0x7d, 0xa4, 0x00, 0xe6]),
        (40_454, [0x7d, 0x75, 0x76, 0x72, 0x7d, 0x72, 0x00, 0xe6]),
    ];
    let samples: Vec<(f64, f64, f64)> = ramp
        .iter()
        .map(|(micros, data)| {
            let status = match decode(0x0280_01FD, data) {
                Ok(Inbound::Status(status)) => Some(status),
                Ok(_) | Err(_) => None,
            }
            .expect("captured frame must decode as status");
            let f = status.feedback(Model::Rs03).unwrap();
            (
                f64::from(*micros) * 1e-6,
                f.position.get(),
                f.velocity.get(),
            )
        })
        .collect();
    let (first, last) = (samples[0], samples[samples.len() - 1]);
    let position_change = last.1 - first.1;
    // Trapezoidal integral of the drive's own velocity over the same 40.45 ms. At ±20 the ratio is 0.996; at ±50, 2.49.
    let integrated: f64 = samples
        .windows(2)
        .map(|w| f64::midpoint(w[0].2, w[1].2) * (w[1].0 - w[0].0))
        .sum();
    let ratio = integrated / position_change;
    assert!(
        (ratio - 1.0).abs() <= 0.10,
        "velocity integrates to {ratio} of the position change"
    );
}
