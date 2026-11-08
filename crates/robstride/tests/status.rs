//! Status frames (types 2 and 24) against the manuals and the bench: header bits, fault flags, SI conversion per model,
//! and the RS03 velocity scale measured on the bench.

#[expect(dead_code, reason = "this file uses only common::header")]
mod common;

use common::header;
use robstride::{
    Celsius, DecodeError, Inbound, Mode, Model, Status, StatusFault, UnvouchedModel, decode,
};

/// Payload of a status frame from the bench: §4.1.2 type 2, capture cd-20261003T145133Z, `right_shoulder_pitch` (RS03,
/// ID 1) during a ramp, 23.0 °C.
const BENCH_STATUS: [u8; 8] = [0x7e, 0x28, 0x75, 0x10, 0x7d, 0x99, 0x00, 0xe6];

/// The status a type-2 frame (or, with `report`, a type-24 frame) decodes to, or what it decoded to instead.
fn decode_status(
    frame_id: u32,
    data: [u8; 8],
    report: bool,
) -> Result<Status, Result<Inbound, DecodeError>> {
    match (report, decode(frame_id, &data)) {
        (false, Ok(Inbound::Status(s))) | (true, Ok(Inbound::Report(s))) => Ok(s),
        (_, other) => Err(other),
    }
}

/// Guards: protocol - type-2 and type-24 headers: device, mode bits 23..22, fault bits 21..16, RobStride manuals §4.1.2 and §4.1.11.
#[test]
fn status_frames_carry_their_header() {
    let rows = [
        (
            "status reply, Run, no faults",
            0x0280_01FD,
            false,
            header(1, Mode::Run, &[]),
        ),
        // Bits 16 (undervoltage) and 21 (uncalibrated), Reset mode.
        (
            "status reply with faults",
            0x0221_01FD,
            false,
            header(
                1,
                Mode::Reset,
                &[StatusFault::Undervoltage, StatusFault::Uncalibrated],
            ),
        ),
        (
            "status reply, every fault bit, calibration mode",
            0x027F_01FD,
            false,
            header(1, Mode::Calibration, &StatusFault::ALL),
        ),
        (
            "active report, §4.1.11",
            0x1880_01FD,
            true,
            header(1, Mode::Run, &[]),
        ),
    ];
    for (what, frame_id, report, want) in rows {
        let status = decode_status(frame_id, BENCH_STATUS, report).unwrap();
        assert_eq!(status.header, want, "{what}");
        assert_eq!(status.temperature, Celsius::new(23.0).unwrap(), "{what}");
    }
}

/// Guards: safety - each status fault flag reads its own ID bit, 16 to 21 (RobStride manuals §4.1.2); the safety crate acts on them.
#[test]
fn status_fault_flags_read_their_own_bits() {
    let clean = decode_status(0x0280_01FD, BENCH_STATUS, false)
        .unwrap()
        .header
        .faults;
    assert!(clean.is_empty());
    assert!(StatusFault::ALL.iter().all(|&f| !clean.contains(f)));
    for (bit, fault) in (16..).zip(StatusFault::ALL) {
        let faults = decode_status(0x0280_01FD | 1 << bit, BENCH_STATUS, false)
            .unwrap()
            .header
            .faults;
        assert!(!faults.is_empty(), "bit {bit}");
        for other in StatusFault::ALL {
            assert_eq!(
                faults.contains(other),
                other == fault,
                "bit {bit}, {other:?}"
            );
        }
    }
}

/// Guards: number - status codes to SI with each model's MIT ranges, `min + code × (max − min) / 65535` (RobStride manuals §4.1.2 and the §4.4 sample's `uint_to_float`); RS00 decodes nothing.
#[test]
fn status_feedback_uses_the_models_ranges() {
    // Position 0xFFFF, velocity 0x4000, torque 0xC000, temperature 0x02EE = 750 tenths of a degree. No field is code 0
    // and no two share a code, so a dropped, swapped or mis-scaled field changes the result.
    let data = [0xFF, 0xFF, 0x40, 0x00, 0xC0, 0x00, 0x02, 0xEE];
    let status = decode_status(0x0280_01FD, data, false).unwrap();
    let manual = |code: u16, max: f64| -max + f64::from(code) * (2.0 * max) / 65535.0;
    let rows = [
        // (model, velocity max rad/s, torque max N·m)
        (Model::Rs02, 44.0, 17.0),
        (Model::Rs03, 20.0, 60.0),
        (Model::Rs04, 15.0, 120.0),
    ];
    for (model, velocity, torque) in rows {
        let f = status.feedback(model).unwrap();
        assert_eq!(
            (
                f.position.get(),
                f.velocity.get(),
                f.torque.get(),
                f.temperature
            ),
            (
                manual(0xFFFF, 12.57),
                manual(0x4000, velocity),
                manual(0xC000, torque),
                Celsius::new(75.0).unwrap()
            ),
            "{model}"
        );
    }
    assert_eq!(
        status.feedback(Model::Rs00),
        Err(UnvouchedModel(Model::Rs00))
    );
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
