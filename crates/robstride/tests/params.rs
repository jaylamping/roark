//! The parameter table against the manuals: every register's index and value type (§4.1.13), reads and writes byte for
//! byte (§4.1.6, §4.1.7, §4.1.14), typed read-backs, and the writes the codec refuses to build or accept from the bus.

#[expect(dead_code, reason = "this file uses only common::id and common::drive")]
mod common;

use common::{drive, id};
use core::time::Duration;
use robstride::{
    Amps, CanTimeout, Damper, DecodeError, EchoKind, EncodeError, Gain, Inbound, Model,
    NewtonMeters, Param, ParamOutcome, ParamType, ParamValue, RadPerSec, RadPerSecSq, Radians,
    ReportInterval, RunMode, Volts, Write, ZeroSta, decode, encode,
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
            encode::param_write(&Write::mit_mode(drive(Model::Rs03, 12))),
            0x1200_FD0C,
            [0x05, 0x70, 0, 0, 0, 0, 0, 0],
        ),
        // PLAN item 6: 1000 × 50 µs = 50 ms.
        (
            "write canTimeout 50 ms",
            encode::param_write(&Write::can_timeout(drive(Model::Rs03, 12))),
            0x1200_FD0C,
            [0x28, 0x70, 0, 0, 0xE8, 0x03, 0, 0],
        ),
        // 30.0 is the §4.1.14 example's f32, 00 00 F0 41.
        (
            "write limit_torque 30 N·m, RS03",
            encode::param_write(&Write::limit_torque(drive(Model::Rs03, 0x7F), nm(30.0)).unwrap()),
            0x1200_FD7F,
            [0x0B, 0x70, 0, 0, 0x00, 0x00, 0xF0, 0x41],
        ),
        (
            "write limit_spd 10 rad/s, RS02",
            encode::param_write(&Write::limit_spd(drive(Model::Rs02, 14), rps(10.0)).unwrap()),
            0x1200_FD0E,
            [0x17, 0x70, 0, 0, 0x00, 0x00, 0x20, 0x41],
        ),
        (
            "write limit_cur 12.5 A, RS04",
            encode::param_write(&Write::limit_cur(drive(Model::Rs04, 3), amps(12.5)).unwrap()),
            0x1200_FD03,
            [0x18, 0x70, 0, 0, 0x00, 0x00, 0x48, 0x41],
        ),
        // PLAN, Stop: the SpeedTarget 0x700A = 0 pre-step.
        (
            "write spd_ref 0",
            encode::param_write(&Write::speed_target_zero(drive(Model::Rs03, 1))),
            0x1200_FD01,
            [0x0A, 0x70, 0, 0, 0, 0, 0, 0],
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
            Write::limit_torque(drive(Model::Rs02, 12), nm(14.01)),
            Param::LimitTorque,
            14.01,
            0.0,
            14.0,
        ),
        (
            "negative limit_torque",
            Write::limit_torque(drive(Model::Rs03, 12), nm(-0.5)),
            Param::LimitTorque,
            -0.5,
            0.0,
            60.0,
        ),
        (
            "RS04 limit_spd past 15 rad/s",
            Write::limit_spd(drive(Model::Rs04, 12), rps(15.5)),
            Param::LimitSpd,
            15.5,
            0.0,
            15.0,
        ),
        (
            "RS03 limit_cur past 43 A",
            Write::limit_cur(drive(Model::Rs03, 12), amps(43.5)),
            Param::LimitCur,
            43.5,
            0.0,
            43.0,
        ),
        (
            "negative limit_spd",
            Write::limit_spd(drive(Model::Rs03, 12), rps(-0.1)),
            Param::LimitSpd,
            -0.1,
            0.0,
            20.0,
        ),
        (
            "negative limit_cur",
            Write::limit_cur(drive(Model::Rs03, 12), amps(-0.1)),
            Param::LimitCur,
            -0.1,
            0.0,
            43.0,
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

/// Guards: safety - the codec writes canTimeout only as 1000 (50 ms), and reads it back in ticks, in nanoseconds and as a span, 0 as no timeout; the drive report interval converts in the codec too (PLAN item 6, units-and-frames.md "drive encodings never leave the codec").
#[test]
fn drive_spans_convert_in_the_codec() {
    assert_eq!(CanTimeout::RUNTIME.ticks(), 1000);
    assert_eq!(CanTimeout::RUNTIME.nanos(), Some(50_000_000));
    assert_eq!(CanTimeout::OFF.nanos(), None);
    assert_eq!(
        CanTimeout::RUNTIME.duration(),
        Some(Duration::from_millis(50))
    );
    assert_eq!(
        CanTimeout::from_ticks(20_000).duration(),
        Some(Duration::from_secs(1))
    );
    // 0 is no timeout at all, never an immediate one.
    assert_eq!(CanTimeout::OFF.duration(), None);
    assert_eq!(
        Write::can_timeout(drive(Model::Rs03, 12)).value(),
        ParamValue::CanTimeout(CanTimeout::RUNTIME)
    );
    // EPScan_time: 1 is 10 ms, each step adds 5 ms; 0 isn't defined.
    assert_eq!(
        ReportInterval::from_ticks(1).duration(),
        Some(Duration::from_millis(10))
    );
    assert_eq!(
        ReportInterval::from_ticks(3).duration(),
        Some(Duration::from_millis(20))
    );
    assert_eq!(ReportInterval::from_ticks(0).duration(), None);
}

/// Guards: safety - what the codec writes is exactly what a read-back of the same register decodes to, so preflight's "read back as written" check compares like with like (PLAN item 6).
#[test]
fn written_values_read_back_equal() {
    let writes = [
        Write::mit_mode(drive(Model::Rs03, 12)),
        Write::can_timeout(drive(Model::Rs03, 12)),
        // 1/3 isn't an f32, so the write holds it rounded, and the read-back must match that.
        Write::limit_torque(drive(Model::Rs03, 12), nm(1.0 / 3.0)).unwrap(),
        Write::limit_spd(drive(Model::Rs02, 12), rps(33.0)).unwrap(),
        Write::limit_cur(drive(Model::Rs04, 12), amps(0.0)).unwrap(),
        Write::speed_target_zero(drive(Model::Rs03, 12)),
    ];
    // A reversed joint's zero, −0.0, is written as +0.0, so two zero caps are the same write.
    assert_eq!(
        Write::limit_spd(drive(Model::Rs03, 12), rps(-0.0)),
        Write::limit_spd(drive(Model::Rs03, 12), rps(0.0))
    );
    for write in writes {
        let [i0, i1, _, _, b4, b5, b6, b7] = encode::param_write(&write).data();
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

/// Guards: protocol - a type-17 reply for every register decodes to its value in its unit: f32 as SI, u8 as its enum or switch, u16 and u32 as counts; a refusal's value bytes aren't read (RobStride manuals §4.1.6, §4.1.13 and the §4.1.14 worked example).
#[test]
#[rustfmt::skip]
fn parameter_replies_decode_typed() {
    use Param as P;
    use ParamValue as V;
    // Index and value little-endian, bytes 2 and 3 zero. f32 1.5 is 00 00 C0 3F.
    let reply = |param: Param, [v0, v1, v2, v3]: [u8; 4]| {
        let [i0, i1] = param.index().to_le_bytes();
        [i0, i1, 0, 0, v0, v1, v2, v3]
    };
    let f = [0x00, 0x00, 0xC0, 0x3F];
    let rad = || V::Radians(Radians::new(1.5).unwrap());
    let acc = || V::RadPerSecSq(RadPerSecSq::new(1.5).unwrap());
    let rows: Vec<(&str, Param, [u8; 4], ParamValue)> = vec![
        ("run_mode 0, MIT", P::RunMode, [0, 0, 0, 0], V::RunMode(RunMode::Mit)),
        ("run_mode 1, PP", P::RunMode, [1, 0, 0, 0], V::RunMode(RunMode::Position)),
        ("run_mode 2", P::RunMode, [2, 0, 0, 0], V::RunMode(RunMode::Velocity)),
        ("run_mode 3", P::RunMode, [3, 0, 0, 0], V::RunMode(RunMode::Current)),
        ("run_mode 5, CSP", P::RunMode, [5, 0, 0, 0], V::RunMode(RunMode::Csp)),
        ("iq_ref", P::IqRef, f, V::Amps(amps(1.5))),
        ("spd_ref", P::SpdRef, f, V::RadPerSec(rps(1.5))),
        ("limit_torque", P::LimitTorque, f, V::NewtonMeters(nm(1.5))),
        ("cur_kp", P::CurKp, f, V::Gain(gain(1.5))),
        ("cur_ki", P::CurKi, f, V::Gain(gain(1.5))),
        ("cur_filt_gain", P::CurFiltGain, f, V::Gain(gain(1.5))),
        ("loc_ref", P::LocRef, f, rad()),
        ("limit_spd", P::LimitSpd, f, V::RadPerSec(rps(1.5))),
        ("limit_cur", P::LimitCur, f, V::Amps(amps(1.5))),
        ("mechPos", P::MechPos, f, rad()),
        ("iqf −1.5 A", P::Iqf, [0x00, 0x00, 0xC0, 0xBF], V::Amps(amps(-1.5))),
        ("mechVel", P::MechVel, f, V::RadPerSec(rps(1.5))),
        ("VBUS 24 V", P::Vbus, [0x00, 0x00, 0xC0, 0x41], V::Volts(Volts::new(24.0).unwrap())),
        // §4.1.14: reading loc_kp returns 30.0, 00 00 F0 41.
        ("loc_kp 30, §4.1.14", P::LocKp, [0x00, 0x00, 0xF0, 0x41], V::Gain(gain(30.0))),
        ("spd_kp", P::SpdKp, f, V::Gain(gain(1.5))),
        ("spd_ki", P::SpdKi, f, V::Gain(gain(1.5))),
        ("spd_filt_gain", P::SpdFiltGain, f, V::Gain(gain(1.5))),
        ("acc_rad", P::AccRad, f, acc()),
        ("vel_max", P::VelMax, f, V::RadPerSec(rps(1.5))),
        ("acc_set", P::AccSet, f, acc()),
        ("EPScan_time 1, 10 ms", P::EpScanTime, [1, 0, 0, 0], V::ReportInterval(ReportInterval::from_ticks(1))),
        ("EPScan_time 3", P::EpScanTime, [3, 0, 0, 0], V::ReportInterval(ReportInterval::from_ticks(3))),
        // PLAN item 6: 1000 is the runtime value, 0 the reboot default (off), 600 what the right arm holds today.
        ("canTimeout 1000", P::CanTimeout, [0xE8, 0x03, 0, 0], V::CanTimeout(CanTimeout::RUNTIME)),
        ("canTimeout 0, off", P::CanTimeout, [0, 0, 0, 0], V::CanTimeout(CanTimeout::OFF)),
        ("canTimeout 600", P::CanTimeout, [0x58, 0x02, 0, 0], V::CanTimeout(CanTimeout::from_ticks(600))),
        ("canTimeout 20000, 1 s", P::CanTimeout, [0x20, 0x4E, 0, 0], V::CanTimeout(CanTimeout::from_ticks(20_000))),
        ("zero_sta 0", P::ZeroSta, [0, 0, 0, 0], V::ZeroSta(ZeroSta::ZeroToTwoPi)),
        ("zero_sta 1", P::ZeroSta, [1, 0, 0, 0], V::ZeroSta(ZeroSta::MinusPiToPi)),
        // PLAN item 6: damper 0 keeps the post-power-off anti-backdrive protection on, 1 turns it off.
        ("damper 0, protection on", P::Damper, [0, 0, 0, 0], V::Damper(Damper::ProtectionOn)),
        ("damper 1, protection off", P::Damper, [1, 0, 0, 0], V::Damper(Damper::ProtectionOff)),
        ("add_offset", P::AddOffset, f, rad()),
        ("cogging compensation on", P::CoggingCompensation, [1, 0, 0, 0], V::Switch(true)),
        ("iq_test off", P::IqTest, [0, 0, 0, 0], V::Switch(false)),
        ("dcc_set", P::DccSet, f, acc()),
    ];
    for param in Param::ALL {
        assert!(rows.iter().any(|row| row.1 == param), "no row for {param:?}");
    }
    for (what, param, value, want) in rows {
        let got = decode(0x1100_0CFD, &reply(param, value));
        assert_eq!(got, Ok(Inbound::Param { device: id(12), param, outcome: ParamOutcome::Read(want) }), "{what}");
    }
    // §4.1.14's frame comes from drive 0x7F.
    assert_eq!(
        decode(0x1100_7FFD, &reply(P::LocKp, [0x00, 0x00, 0xF0, 0x41])),
        Ok(Inbound::Param { device: id(0x7F), param: P::LocKp, outcome: ParamOutcome::Read(V::Gain(gain(30.0))) })
    );
    // A refusal's value bytes aren't defined (§4.1.6), so they aren't read: NaN there is still a refusal.
    assert_eq!(
        decode(0x1101_0CFD, &reply(P::Vbus, [0x00, 0x00, 0xC0, 0x7F])),
        Ok(Inbound::Param { device: id(12), param: P::Vbus, outcome: ParamOutcome::Refused })
    );
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
        // Values outside what any model's Write accepts.
        ("canTimeout 0, off", 0x7028, [0, 0, 0, 0]),
        ("canTimeout 600, 30 ms", 0x7028, [0x58, 0x02, 0, 0]),
        ("limit_spd −10 rad/s", 0x7017, [0x00, 0x00, 0x20, 0xC1]),
        ("limit_torque 1000 N·m", 0x700B, [0x00, 0x00, 0x7A, 0x44]),
        ("limit_cur 91 A", 0x7018, [0x00, 0x00, 0xB6, 0x42]),
        ("spd_ref 34 rad/s", 0x700A, [0x00, 0x00, 0x08, 0x42]),
        // The host writes only spd_ref 0 and caps of +0.0, never −0.0 or a non-zero target.
        ("spd_ref 1.5 rad/s", 0x700A, [0x00, 0x00, 0xC0, 0x3F]),
        ("limit_torque −0.0", 0x700B, [0x00, 0x00, 0x00, 0x80]),
        ("spd_ref −0.0", 0x700A, [0x00, 0x00, 0x00, 0x80]),
        // A register Write never targets is foreign whatever its value bytes hold.
        ("zero_sta 2", 0x7029, [2, 0, 0, 0]),
        ("damper with filler set", 0x702A, [1, 0xFF, 0, 0]),
        ("add_offset NaN", 0x702B, [0x00, 0x00, 0xC0, 0x7F]),
    ];
    for (what, index, [v0, v1, v2, v3]) in foreign {
        let [i0, i1] = index.to_le_bytes();
        assert_eq!(
            decode(0x1200_FD0C, &[i0, i1, 0, 0, v0, v1, v2, v3]),
            Err(DecodeError::ForeignWrite {
                index,
                value: [v0, v1, v2, v3],
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
    let bad = |index: u16, value: [u8; 4], id: u32| DecodeError::BadParamValue { index, value, id };
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
                value: [0, 0, 0, 0],
                id: 0x1200_FD0C,
            },
        ),
        (
            "run_mode 4, which the manual doesn't list",
            0x1100_0CFD,
            [0x05, 0x70, 0, 0, 4, 0, 0, 0],
            bad(0x7005, [4, 0, 0, 0], 0x1100_0CFD),
        ),
        (
            "damper 2",
            0x1100_0CFD,
            [0x2A, 0x70, 0, 0, 2, 0, 0, 0],
            bad(0x702A, [2, 0, 0, 0], 0x1100_0CFD),
        ),
        (
            "1-byte value with filler set",
            0x1100_0CFD,
            [0x05, 0x70, 0, 0, 0, 0, 0, 1],
            bad(0x7005, [0, 0, 0, 1], 0x1100_0CFD),
        ),
        (
            "2-byte value with filler set",
            0x1100_0CFD,
            [0x26, 0x70, 0, 0, 1, 0, 1, 0],
            bad(0x7026, [1, 0, 1, 0], 0x1100_0CFD),
        ),
        (
            "VBUS NaN",
            0x1100_0CFD,
            [0x1C, 0x70, 0, 0, 0x00, 0x00, 0xC0, 0x7F],
            bad(0x701C, [0x00, 0x00, 0xC0, 0x7F], 0x1100_0CFD),
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
            bad(0x7005, [0, 1, 0, 0], 0x1200_FD0C),
        ),
        (
            "write of a NaN limit",
            0x1200_FD0C,
            [0x0B, 0x70, 0, 0, 0x00, 0x00, 0xC0, 0x7F],
            bad(0x700B, [0x00, 0x00, 0xC0, 0x7F], 0x1200_FD0C),
        ),
        (
            "write of run_mode 4",
            0x1200_FD0C,
            [0x05, 0x70, 0, 0, 4, 0, 0, 0],
            bad(0x7005, [4, 0, 0, 0], 0x1200_FD0C),
        ),
    ];
    for (what, frame_id, data, want) in rows {
        assert_eq!(decode(frame_id, &data), Err(want), "{what}");
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
        Write::mit_mode(drive(Model::Rs03, 12)),
        Write::can_timeout(drive(Model::Rs03, 12)),
        Write::speed_target_zero(drive(Model::Rs03, 12)),
        Write::limit_torque(drive(Model::Rs04, 12), nm(120.0)).unwrap(),
        Write::limit_spd(drive(Model::Rs03, 12), rps(0.1)).unwrap(),
        Write::limit_cur(drive(Model::Rs00, 12), amps(16.0)).unwrap(),
    ];
    for write in writes {
        assert_eq!(
            echo(encode::param_write(&write)),
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

#[expect(
    clippy::expect_used,
    reason = "test helper for finite literals; clippy allows expect only inside #[test] bodies"
)]
fn gain(v: f64) -> Gain {
    Gain::new(v).expect("finite")
}
