//! The parameter table against the manuals: every register's index and value type (§4.1.13), reads and writes byte for
//! byte (§4.1.6, §4.1.7, §4.1.14), typed read-backs, and the writes the codec refuses to build or accept from the bus.

#[expect(dead_code, reason = "this file uses only common::id")]
mod common;

use common::id;
use robstride::{
    Amps, CanTimeout, DecodeError, EchoKind, EncodeError, Inbound, Model, NewtonMeters, Param,
    ParamOutcome, ParamType, ParamValue, RadPerSec, RadPerSecSq, Radians, RunMode, Volts, Write,
    ZeroSta, decode, encode,
};

/// Guards: protocol - all 29 registers of the parameter table, index and value type, identical in the RS00, RS02, RS03 and RS04 manuals §4.1.13.
#[test]
fn parameter_table_matches_the_manuals() {
    use ParamType::{F32, U8, U16, U32};
    let rows = [
        (Param::RunMode, 0x7005, U8),
        (Param::IqRef, 0x7006, F32),
        (Param::SpdRef, 0x700A, F32),
        (Param::LimitTorque, 0x700B, F32),
        (Param::CurKp, 0x7010, F32),
        (Param::CurKi, 0x7011, F32),
        (Param::CurFiltGain, 0x7014, F32),
        (Param::LocRef, 0x7016, F32),
        (Param::LimitSpd, 0x7017, F32),
        (Param::LimitCur, 0x7018, F32),
        (Param::MechPos, 0x7019, F32),
        (Param::Iqf, 0x701A, F32),
        (Param::MechVel, 0x701B, F32),
        (Param::Vbus, 0x701C, F32),
        (Param::LocKp, 0x701E, F32),
        (Param::SpdKp, 0x701F, F32),
        (Param::SpdKi, 0x7020, F32),
        (Param::SpdFiltGain, 0x7021, F32),
        (Param::AccRad, 0x7022, F32),
        (Param::VelMax, 0x7024, F32),
        (Param::AccSet, 0x7025, F32),
        (Param::EpScanTime, 0x7026, U16),
        (Param::CanTimeout, 0x7028, U32),
        (Param::ZeroSta, 0x7029, U8),
        (Param::Damper, 0x702A, U8),
        (Param::AddOffset, 0x702B, F32),
        (Param::CoggingCompensation, 0x702C, U8),
        (Param::IqTest, 0x702D, U8),
        (Param::DccSet, 0x702E, F32),
    ];
    assert_eq!(Param::ALL.len(), rows.len());
    for ((param, index, kind), listed) in rows.into_iter().zip(Param::ALL) {
        assert_eq!(param, listed, "Param::ALL order");
        assert_eq!(
            (param.index(), param.value_type()),
            (index, kind),
            "{param:?}"
        );
    }
}

/// Guards: protocol - type-17 reads and type-18 writes byte for byte: index and value little-endian, bytes 2 and 3 zero (RobStride manuals §4.1.6, §4.1.7, §4.1.14 worked example).
#[test]
fn parameter_frames_match_the_manuals() {
    let rows: Vec<(&str, robstride::Frame, u32, [u8; 8])> = vec![
        // §4.1.14 worked example: read loc_kp from ID 0x7F.
        (
            "read loc_kp, §4.1.14",
            encode::param_read(id(0x7F), Param::LocKp),
            0x1100_FD7F,
            [0x1E, 0x70, 0, 0, 0, 0, 0, 0],
        ),
        (
            "read canTimeout",
            encode::param_read(id(12), Param::CanTimeout),
            0x1100_FD0C,
            [0x28, 0x70, 0, 0, 0, 0, 0, 0],
        ),
        // A 1-byte value sits in byte 4.
        (
            "write run_mode MIT",
            encode::param_write(id(12), &Write::mit_mode()),
            0x1200_FD0C,
            [0x05, 0x70, 0, 0, 0, 0, 0, 0],
        ),
        // PLAN item 6: 1000 × 50 µs = 50 ms.
        (
            "write canTimeout 50 ms",
            encode::param_write(id(12), &Write::can_timeout(CanTimeout::from_ticks(1000))),
            0x1200_FD0C,
            [0x28, 0x70, 0, 0, 0xE8, 0x03, 0, 0],
        ),
        // 30.0 is the §4.1.14 example's f32, 00 00 F0 41.
        (
            "write limit_torque 30 N·m, RS03",
            encode::param_write(
                id(0x7F),
                &Write::limit_torque(Model::Rs03, nm(30.0)).unwrap(),
            ),
            0x1200_FD7F,
            [0x0B, 0x70, 0, 0, 0x00, 0x00, 0xF0, 0x41],
        ),
        (
            "write limit_spd 10 rad/s, RS02",
            encode::param_write(id(14), &Write::limit_spd(Model::Rs02, rps(10.0)).unwrap()),
            0x1200_FD0E,
            [0x17, 0x70, 0, 0, 0x00, 0x00, 0x20, 0x41],
        ),
        (
            "write limit_cur 12.5 A, RS04",
            encode::param_write(id(3), &Write::limit_cur(Model::Rs04, amps(12.5)).unwrap()),
            0x1200_FD03,
            [0x18, 0x70, 0, 0, 0x00, 0x00, 0x48, 0x41],
        ),
        (
            "write spd_ref −1.5 rad/s, RS03",
            encode::param_write(id(1), &Write::spd_ref(Model::Rs03, rps(-1.5)).unwrap()),
            0x1200_FD01,
            [0x0A, 0x70, 0, 0, 0x00, 0x00, 0xC0, 0xBF],
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

/// Guards: safety - a host-set limit or speed target outside the model's range is refused, never clamped (PLAN items 3 and 6, model caps §4.1.13).
#[test]
fn parameter_writes_refuse_rather_than_clamp() {
    // (what, the attempt, register, value, min, max)
    type Row = (
        &'static str,
        Result<Write, EncodeError>,
        Param,
        f64,
        f64,
        f64,
    );
    let rows: Vec<Row> = vec![
        (
            "RS02 limit_torque past 14 N·m",
            Write::limit_torque(Model::Rs02, nm(14.01)),
            Param::LimitTorque,
            14.01,
            0.0,
            14.0,
        ),
        (
            "negative limit_torque",
            Write::limit_torque(Model::Rs03, nm(-0.5)),
            Param::LimitTorque,
            -0.5,
            0.0,
            60.0,
        ),
        (
            "RS04 limit_spd past 15 rad/s",
            Write::limit_spd(Model::Rs04, rps(15.5)),
            Param::LimitSpd,
            15.5,
            0.0,
            15.0,
        ),
        (
            "RS03 limit_cur past 43 A",
            Write::limit_cur(Model::Rs03, amps(43.5)),
            Param::LimitCur,
            43.5,
            0.0,
            43.0,
        ),
        (
            "RS00 spd_ref past −33 rad/s",
            Write::spd_ref(Model::Rs00, rps(-33.5)),
            Param::SpdRef,
            -33.5,
            -33.0,
            33.0,
        ),
    ];
    for (what, got, param, value, min, max) in rows {
        assert_eq!(
            got,
            Err(EncodeError::ParamOutOfRange {
                param,
                value,
                min,
                max
            }),
            "{what}"
        );
    }
}

/// Guards: safety - what the codec writes is exactly what a read-back of the same register decodes to, so preflight's "read back as written" check compares like with like (PLAN item 6).
#[test]
fn written_values_read_back_equal() {
    let writes = [
        Write::mit_mode(),
        Write::can_timeout(CanTimeout::from_ticks(1000)),
        // 1/3 isn't an f32, so the write holds it rounded, and the read-back must match that.
        Write::limit_torque(Model::Rs03, nm(1.0 / 3.0)).unwrap(),
        Write::limit_spd(Model::Rs02, rps(33.0)).unwrap(),
        Write::limit_cur(Model::Rs04, amps(0.0)).unwrap(),
        Write::spd_ref(Model::Rs03, rps(0.0)).unwrap(),
    ];
    for write in writes {
        let [i0, i1, _, _, b4, b5, b6, b7] = encode::param_write(id(12), &write).data();
        // The drive's reply to a read of the same register, carrying the bytes that were written.
        let reply = decode(0x1100_0CFD, &[i0, i1, 0, 0, b4, b5, b6, b7]);
        assert_eq!(
            reply,
            Ok(Inbound::Param {
                device: id(12),
                param: write.param(),
                outcome: ParamOutcome::Read(write.value()),
            }),
            "{write:?}"
        );
    }
}

/// Guards: protocol - type-17 replies decode to typed values, RobStride manuals §4.1.6, §4.1.13 and the §4.1.14 worked example.
#[test]
fn parameter_replies_decode_typed() {
    let rows: Vec<(&str, u32, [u8; 8], Param, ParamValue)> = vec![
        // §4.1.14: reading loc_kp from 0x7F returns 30.0.
        (
            "loc_kp, §4.1.14",
            0x1100_7FFD,
            [0x1E, 0x70, 0, 0, 0x00, 0x00, 0xF0, 0x41],
            Param::LocKp,
            ParamValue::Gain(30.0),
        ),
        (
            "VBUS 24 V",
            0x1100_0CFD,
            [0x1C, 0x70, 0, 0, 0x00, 0x00, 0xC0, 0x41],
            Param::Vbus,
            ParamValue::Volts(Volts::new(24.0).unwrap()),
        ),
        (
            "iqf −1.5 A",
            0x1100_0CFD,
            [0x1A, 0x70, 0, 0, 0x00, 0x00, 0xC0, 0xBF],
            Param::Iqf,
            ParamValue::Amps(amps(-1.5)),
        ),
        (
            "canTimeout 1000",
            0x1100_0CFD,
            [0x28, 0x70, 0, 0, 0xE8, 0x03, 0, 0],
            Param::CanTimeout,
            ParamValue::CanTimeout(CanTimeout::from_ticks(1000)),
        ),
        (
            "run_mode CSP (5)",
            0x1100_0CFD,
            [0x05, 0x70, 0, 0, 5, 0, 0, 0],
            Param::RunMode,
            ParamValue::RunMode(RunMode::Csp),
        ),
        (
            "zero_sta −π..π (1)",
            0x1100_0CFD,
            [0x29, 0x70, 0, 0, 1, 0, 0, 0],
            Param::ZeroSta,
            ParamValue::ZeroSta(ZeroSta::MinusPiToPi),
        ),
        (
            "damper on",
            0x1100_0CFD,
            [0x2A, 0x70, 0, 0, 1, 0, 0, 0],
            Param::Damper,
            ParamValue::Switch(true),
        ),
        (
            "EPScan_time 1 (10 ms)",
            0x1100_0CFD,
            [0x26, 0x70, 0, 0, 1, 0, 0, 0],
            Param::EpScanTime,
            ParamValue::ReportTicks(1),
        ),
    ];
    for (what, frame_id, data, param, value) in rows {
        assert_eq!(
            decode(frame_id, &data),
            Ok(Inbound::Param {
                device: id(frame_id.to_be_bytes()[2]),
                param,
                outcome: ParamOutcome::Read(value),
            }),
            "{what}"
        );
    }
}

/// Guards: protocol - the host's own parameter frames read back as typed echoes, and a write the codec can't build means another sender is on the bus (PLAN item 2: never write 0x7029, 0x702A, 0x702B).
#[test]
fn parameter_echoes_decode_or_name_a_foreign_write() {
    let echo = |frame_id: u32, data: [u8; 8]| match decode(frame_id, &data) {
        Ok(Inbound::Echo(e)) => Ok(e.kind),
        other => Err(other),
    };
    assert_eq!(
        echo(0x1100_FD7F, [0x1E, 0x70, 0, 0, 0, 0, 0, 0]),
        Ok(EchoKind::ParamRead(Param::LocKp))
    );
    assert_eq!(
        echo(0x1200_FD7F, [0x0B, 0x70, 0, 0, 0x00, 0x00, 0xF0, 0x41]),
        Ok(EchoKind::ParamWrite {
            param: Param::LimitTorque,
            value: ParamValue::NewtonMeters(nm(30.0)),
        })
    );
    let foreign = [
        ("zero_sta", 0x7029_u16, [1, 0, 0, 0]),
        ("damper", 0x702A, [1, 0, 0, 0]),
        ("add_offset", 0x702B, [0x00, 0x00, 0x00, 0x3F]),
        ("VBUS, read-only", 0x701C, [0x00, 0x00, 0xC0, 0x41]),
        ("loc_kp", 0x701E, [0x00, 0x00, 0xF0, 0x41]),
        ("run_mode velocity", 0x7005, [2, 0, 0, 0]),
    ];
    for (what, index, [v0, v1, v2, v3]) in foreign {
        let [i0, i1] = index.to_le_bytes();
        assert_eq!(
            decode(0x1200_FD0C, &[i0, i1, 0, 0, v0, v1, v2, v3]),
            Err(DecodeError::ForeignWrite {
                index,
                id: 0x1200_FD0C
            }),
            "{what}"
        );
    }
}

/// Guards: protocol - a parameter frame the manual doesn't allow is refused: unknown index, value outside its type, non-finite float, non-zero filler (RobStride manuals §4.1.6, §4.1.13, §4.1.14).
#[test]
fn malformed_parameter_frames_are_refused() {
    let unexpected = |frame_id: u32| DecodeError::UnexpectedData {
        kind: frame_id.to_be_bytes()[0],
        id: frame_id,
    };
    let rows: Vec<(&str, u32, [u8; 8], DecodeError)> = vec![
        (
            "reply for 0x7027, not in the table",
            0x1100_0CFD,
            [0x27, 0x70, 0, 0, 0, 0, 0, 0],
            DecodeError::UnknownParam {
                index: 0x7027,
                id: 0x1100_0CFD,
            },
        ),
        (
            "read of 0x2007, a function-code index",
            0x1100_FD0C,
            [0x07, 0x20, 0, 0, 0, 0, 0, 0],
            DecodeError::UnknownParam {
                index: 0x2007,
                id: 0x1100_FD0C,
            },
        ),
        (
            "write to an index outside the table",
            0x1200_FD0C,
            [0xFF, 0x70, 0, 0, 0, 0, 0, 0],
            DecodeError::ForeignWrite {
                index: 0x70FF,
                id: 0x1200_FD0C,
            },
        ),
        (
            "run_mode 4, which the manual doesn't list",
            0x1100_0CFD,
            [0x05, 0x70, 0, 0, 4, 0, 0, 0],
            unexpected(0x1100_0CFD),
        ),
        (
            "damper 2",
            0x1100_0CFD,
            [0x2A, 0x70, 0, 0, 2, 0, 0, 0],
            unexpected(0x1100_0CFD),
        ),
        (
            "1-byte value with filler set",
            0x1100_0CFD,
            [0x05, 0x70, 0, 0, 0, 0, 0, 1],
            unexpected(0x1100_0CFD),
        ),
        (
            "2-byte value with filler set",
            0x1100_0CFD,
            [0x26, 0x70, 0, 0, 1, 0, 1, 0],
            unexpected(0x1100_0CFD),
        ),
        (
            "VBUS NaN",
            0x1100_0CFD,
            [0x1C, 0x70, 0, 0, 0x00, 0x00, 0xC0, 0x7F],
            unexpected(0x1100_0CFD),
        ),
        // §4.1.14: a read request's bytes 2 to 7 are all 00.
        (
            "read request with byte 4 set",
            0x1100_FD0C,
            [0x1C, 0x70, 0, 0, 0xAA, 0, 0, 0],
            unexpected(0x1100_FD0C),
        ),
        (
            "read request with byte 7 set",
            0x1100_FD0C,
            [0x1C, 0x70, 0, 0, 0, 0, 0, 1],
            unexpected(0x1100_FD0C),
        ),
        (
            "write of run_mode with filler set",
            0x1200_FD0C,
            [0x05, 0x70, 0, 0, 0, 1, 0, 0],
            unexpected(0x1200_FD0C),
        ),
        (
            "write of a NaN limit",
            0x1200_FD0C,
            [0x0B, 0x70, 0, 0, 0x00, 0x00, 0xC0, 0x7F],
            unexpected(0x1200_FD0C),
        ),
    ];
    for (what, frame_id, data, want) in rows {
        assert_eq!(decode(frame_id, &data), Err(want), "{what}");
    }
}

/// Guards: protocol - a type-17 reply for every register decodes to its value in its unit: f32 as SI, u8 as its enum or switch, u16 and u32 as counts (RobStride manuals §4.1.6 and §4.1.13).
#[test]
#[expect(clippy::too_many_lines, reason = "one table, one row per register")]
fn every_register_reply_decodes() {
    // f32 1.5 is 00 00 C0 3F; canTimeout 20000 (1 s) is 20 4E 00 00.
    let rows: Vec<(Param, [u8; 4], ParamValue)> = vec![
        (
            Param::RunMode,
            [0, 0, 0, 0],
            ParamValue::RunMode(RunMode::Mit),
        ),
        (
            Param::IqRef,
            [0x00, 0x00, 0xC0, 0x3F],
            ParamValue::Amps(amps(1.5)),
        ),
        (
            Param::SpdRef,
            [0x00, 0x00, 0xC0, 0x3F],
            ParamValue::RadPerSec(rps(1.5)),
        ),
        (
            Param::LimitTorque,
            [0x00, 0x00, 0xC0, 0x3F],
            ParamValue::NewtonMeters(nm(1.5)),
        ),
        (
            Param::CurKp,
            [0x00, 0x00, 0xC0, 0x3F],
            ParamValue::Gain(1.5),
        ),
        (
            Param::CurKi,
            [0x00, 0x00, 0xC0, 0x3F],
            ParamValue::Gain(1.5),
        ),
        (
            Param::CurFiltGain,
            [0x00, 0x00, 0xC0, 0x3F],
            ParamValue::Gain(1.5),
        ),
        (
            Param::LocRef,
            [0x00, 0x00, 0xC0, 0x3F],
            ParamValue::Radians(Radians::new(1.5).unwrap()),
        ),
        (
            Param::LimitSpd,
            [0x00, 0x00, 0xC0, 0x3F],
            ParamValue::RadPerSec(rps(1.5)),
        ),
        (
            Param::LimitCur,
            [0x00, 0x00, 0xC0, 0x3F],
            ParamValue::Amps(amps(1.5)),
        ),
        (
            Param::MechPos,
            [0x00, 0x00, 0xC0, 0x3F],
            ParamValue::Radians(Radians::new(1.5).unwrap()),
        ),
        (
            Param::Iqf,
            [0x00, 0x00, 0xC0, 0x3F],
            ParamValue::Amps(amps(1.5)),
        ),
        (
            Param::MechVel,
            [0x00, 0x00, 0xC0, 0x3F],
            ParamValue::RadPerSec(rps(1.5)),
        ),
        (
            Param::Vbus,
            [0x00, 0x00, 0xC0, 0x3F],
            ParamValue::Volts(Volts::new(1.5).unwrap()),
        ),
        (
            Param::LocKp,
            [0x00, 0x00, 0xC0, 0x3F],
            ParamValue::Gain(1.5),
        ),
        (
            Param::SpdKp,
            [0x00, 0x00, 0xC0, 0x3F],
            ParamValue::Gain(1.5),
        ),
        (
            Param::SpdKi,
            [0x00, 0x00, 0xC0, 0x3F],
            ParamValue::Gain(1.5),
        ),
        (
            Param::SpdFiltGain,
            [0x00, 0x00, 0xC0, 0x3F],
            ParamValue::Gain(1.5),
        ),
        (
            Param::AccRad,
            [0x00, 0x00, 0xC0, 0x3F],
            ParamValue::RadPerSecSq(RadPerSecSq::new(1.5).unwrap()),
        ),
        (
            Param::VelMax,
            [0x00, 0x00, 0xC0, 0x3F],
            ParamValue::RadPerSec(rps(1.5)),
        ),
        (
            Param::AccSet,
            [0x00, 0x00, 0xC0, 0x3F],
            ParamValue::RadPerSecSq(RadPerSecSq::new(1.5).unwrap()),
        ),
        (
            Param::EpScanTime,
            [0x03, 0x00, 0, 0],
            ParamValue::ReportTicks(3),
        ),
        (
            Param::CanTimeout,
            [0x20, 0x4E, 0, 0],
            ParamValue::CanTimeout(CanTimeout::from_ticks(20000)),
        ),
        (
            Param::ZeroSta,
            [0, 0, 0, 0],
            ParamValue::ZeroSta(ZeroSta::ZeroToTwoPi),
        ),
        (Param::Damper, [0, 0, 0, 0], ParamValue::Switch(false)),
        (
            Param::AddOffset,
            [0x00, 0x00, 0xC0, 0x3F],
            ParamValue::Radians(Radians::new(1.5).unwrap()),
        ),
        (
            Param::CoggingCompensation,
            [1, 0, 0, 0],
            ParamValue::Switch(true),
        ),
        (Param::IqTest, [0, 0, 0, 0], ParamValue::Switch(false)),
        (
            Param::DccSet,
            [0x00, 0x00, 0xC0, 0x3F],
            ParamValue::RadPerSecSq(RadPerSecSq::new(1.5).unwrap()),
        ),
    ];
    assert_eq!(rows.len(), Param::ALL.len());
    for (param, [v0, v1, v2, v3], want) in rows {
        let [i0, i1] = param.index().to_le_bytes();
        assert_eq!(
            decode(0x1100_0CFD, &[i0, i1, 0, 0, v0, v1, v2, v3]),
            Ok(Inbound::Param {
                device: id(12),
                param,
                outcome: ParamOutcome::Read(want),
            }),
            "{param:?}"
        );
    }
}

/// Guards: protocol - every parameter frame the host builds reads back as the echo of what it built, decode(encode(x)) == x (can.md section 1, "Tests").
#[test]
fn parameter_frames_round_trip() {
    let echo = |frame: robstride::Frame| match decode(frame.id(), &frame.data()) {
        Ok(Inbound::Echo(e)) if e.target == id(12) => Some(e.kind),
        _ => None,
    };
    for param in Param::ALL {
        assert_eq!(
            echo(encode::param_read(id(12), param)),
            Some(EchoKind::ParamRead(param)),
            "{param:?}"
        );
    }
    let writes = [
        Write::mit_mode(),
        Write::can_timeout(CanTimeout::from_ticks(1000)),
        Write::can_timeout(CanTimeout::OFF),
        Write::spd_ref(Model::Rs02, rps(-33.0)).unwrap(),
        Write::limit_torque(Model::Rs04, nm(120.0)).unwrap(),
        Write::limit_spd(Model::Rs03, rps(0.1)).unwrap(),
        Write::limit_cur(Model::Rs00, amps(16.0)).unwrap(),
    ];
    for write in writes {
        assert_eq!(
            echo(encode::param_write(id(12), &write)),
            Some(EchoKind::ParamWrite {
                param: write.param(),
                value: write.value(),
            }),
            "{write:?}"
        );
    }
}

#[expect(
    clippy::expect_used,
    reason = "test helper for finite literals; clippy allows expect only inside #[test] bodies"
)]
fn nm(v: f64) -> NewtonMeters {
    NewtonMeters::new(v).expect("finite")
}

#[expect(
    clippy::expect_used,
    reason = "test helper for finite literals; clippy allows expect only inside #[test] bodies"
)]
fn rps(v: f64) -> RadPerSec {
    RadPerSec::new(v).expect("finite")
}

#[expect(
    clippy::expect_used,
    reason = "test helper for finite literals; clippy allows expect only inside #[test] bodies"
)]
fn amps(v: f64) -> Amps {
    Amps::new(v).expect("finite")
}
