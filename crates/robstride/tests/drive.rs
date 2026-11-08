//! The drive's side of the protocol (`robstride::drive`, used by `sim-drive`): every host command reads back in full, and
//! every drive frame it builds decodes on the host as what it was built from.

mod common;

use common::{drive, header, id};
use robstride::drive::{self, Command, DriveError, StatusField};
use robstride::{
    Amps, Celsius, Damper, Feedback, Gain, Inbound, MitCommand, Mode, Model, NewtonMeters,
    NmPerRad, NmSecPerRad, Param, ParamOutcome, ParamValue, RadPerSec, RadPerSecSq, Radians,
    ReportInterval, Reporting, RunMode, StatusFault, StatusFaults, Uid, Volts, Write, ZeroSta,
    decode, encode,
};

#[expect(
    clippy::unwrap_used,
    reason = "test helper for finite literals; clippy allows unwrap only inside #[test] bodies"
)]
fn feedback(position: f64, velocity: f64, torque: f64, celsius: f64) -> Feedback {
    Feedback {
        position: Radians::new(position).unwrap(),
        velocity: RadPerSec::new(velocity).unwrap(),
        torque: NewtonMeters::new(torque).unwrap(),
        temperature: Celsius::new(celsius).unwrap(),
    }
}

/// `got` is `want` to within half of one 16-bit code step of `span`.
fn near(got: f64, want: f64, span: f64) -> bool {
    (got - want).abs() <= span / 65535.0 / 2.0 + 1e-12
}

/// A value each register can hold, of its own type.
#[expect(
    clippy::unwrap_used,
    reason = "test helper for finite literals; clippy allows unwrap only inside #[test] bodies"
)]
fn sample(param: Param) -> ParamValue {
    match param {
        Param::RunMode => ParamValue::RunMode(RunMode::Mit),
        Param::ZeroSta => ParamValue::ZeroSta(ZeroSta::MinusPiToPi),
        Param::Damper => ParamValue::Damper(Damper::ProtectionOn),
        Param::CoggingCompensation | Param::IqTest => ParamValue::Switch(true),
        Param::EpScanTime => ParamValue::ReportInterval(ReportInterval::from_ticks(3)),
        Param::CanTimeout => ParamValue::CanTimeout(robstride::CanTimeout::RUNTIME),
        Param::IqRef | Param::LimitCur | Param::Iqf => ParamValue::Amps(Amps::new(2.5).unwrap()),
        Param::SpdRef | Param::LimitSpd | Param::MechVel | Param::VelMax => {
            ParamValue::RadPerSec(RadPerSec::new(-1.5).unwrap())
        }
        Param::LimitTorque => ParamValue::NewtonMeters(NewtonMeters::new(12.0).unwrap()),
        Param::LocRef | Param::MechPos | Param::AddOffset => {
            ParamValue::Radians(Radians::new(0.25).unwrap())
        }
        Param::AccRad | Param::AccSet | Param::DccSet => {
            ParamValue::RadPerSecSq(RadPerSecSq::new(20.0).unwrap())
        }
        Param::Vbus => ParamValue::Volts(Volts::new(24.0).unwrap()),
        Param::CurKp
        | Param::CurKi
        | Param::CurFiltGain
        | Param::LocKp
        | Param::SpdKp
        | Param::SpdKi
        | Param::SpdFiltGain => ParamValue::Gain(Gain::new(0.125).unwrap()),
    }
}

/// Guards: protocol - a frame `sim-drive` builds is the frame the host decodes: status and report in the drive's MIT
/// scales with temperature in tenths, identity, and a type-17 reply of every register's value or a refusal (RobStride
/// manuals §4.1.1, §4.1.2, §4.1.6, §4.1.11, §4.1.13).
#[test]
fn drive_frames_decode_as_built() {
    let rs03 = drive(Model::Rs03, 1);
    let fb = feedback(1.0, -2.0, 3.0, 25.5);
    let faults: StatusFaults = [StatusFault::Overtemperature].into_iter().collect();
    for (kind, frame) in [
        (
            "status",
            drive::status(rs03, Mode::Run, faults, &fb).unwrap(),
        ),
        (
            "report",
            drive::report(rs03, Mode::Run, faults, &fb).unwrap(),
        ),
    ] {
        let inbound = decode(frame.id(), &frame.data()).unwrap();
        let status = match (kind, inbound) {
            ("status", Inbound::Status(s)) | ("report", Inbound::Report(s)) => Some(s),
            _ => None,
        };
        let status = status.expect(kind);
        assert_eq!(
            status.header,
            header(1, Mode::Run, &[StatusFault::Overtemperature]),
            "{kind}"
        );
        let got = status.feedback(Model::Rs03).unwrap();
        // RS03 manual 261013 §4.1.2: position ±12.57 rad, velocity ±20 rad/s, torque ±60 N·m.
        assert!(near(got.position.get(), 1.0, 25.14), "{kind}: {got:?}");
        assert!(near(got.velocity.get(), -2.0, 40.0), "{kind}: {got:?}");
        assert!(near(got.torque.get(), 3.0, 120.0), "{kind}: {got:?}");
        assert_eq!(got.temperature, fb.temperature, "{kind}");
    }

    let uid = Uid([1, 2, 3, 4, 5, 6, 7, 8]);
    let frame = drive::identity(id(5), uid);
    assert_eq!(
        decode(frame.id(), &frame.data()).unwrap(),
        Inbound::Identity { device: id(5), uid }
    );

    for param in Param::ALL {
        let value = sample(param);
        let frame = drive::param_value(id(7), param, value).unwrap();
        let read = ParamOutcome::Read(value);
        assert_eq!(
            decode(frame.id(), &frame.data()).unwrap(),
            Inbound::Param {
                device: id(7),
                param,
                outcome: read
            },
            "{param:?}"
        );
        let frame = drive::param_refused(id(7), param);
        assert_eq!(
            decode(frame.id(), &frame.data()).unwrap(),
            Inbound::Param {
                device: id(7),
                param,
                outcome: ParamOutcome::Refused
            },
            "{param:?} refused"
        );
    }
}

/// Guards: protocol - every frame the host can build reads back on the drive side as the command it is, an MIT command
/// with its fields in the model's scales, and a drive's own frame isn't a command (RobStride manuals §4.1.1 to §4.1.11).
#[test]
fn host_commands_read_back_in_full() {
    let rs03 = drive(Model::Rs03, 4);
    let t = id(4);
    let mut cases = vec![
        ("get_id", encode::get_id(t), Command::GetId),
        ("enable", encode::enable(t), Command::Enable),
        ("disable", encode::disable(t), Command::Disable),
        ("version", encode::version_query(t), Command::VersionQuery),
        ("set_zero", encode::set_zero(t), Command::SetZero),
        (
            "set_id",
            encode::set_id(t, id(9)),
            Command::SetId { new: id(9) },
        ),
        (
            "reporting on",
            encode::active_reporting(t, Reporting::On),
            Command::Reporting(Reporting::On),
        ),
        (
            "reporting off",
            encode::active_reporting(t, Reporting::Off),
            Command::Reporting(Reporting::Off),
        ),
    ];
    for param in Param::ALL {
        cases.push((
            "read",
            encode::param_read(t, param),
            Command::ParamRead(param),
        ));
    }
    for write in [
        Write::mit_mode(rs03),
        Write::can_timeout(rs03),
        Write::speed_target_zero(rs03),
        Write::limit_torque(rs03, NewtonMeters::new(30.0).unwrap()).unwrap(),
        Write::limit_spd(rs03, RadPerSec::new(4.0).unwrap()).unwrap(),
        Write::limit_cur(rs03, Amps::new(20.0).unwrap()).unwrap(),
    ] {
        let command = Command::ParamWrite {
            param: write.param(),
            value: write.value(),
        };
        cases.push(("write", encode::param_write(&write), command));
    }
    for (name, frame, command) in cases {
        let host = drive::command(frame.id(), &frame.data()).unwrap().unwrap();
        assert_eq!((host.target, host.command), (t, command), "{name}");
    }

    let sent = MitCommand {
        position: Radians::new(-3.0).unwrap(),
        velocity: RadPerSec::new(1.25).unwrap(),
        kp: NmPerRad::new(40.0).unwrap(),
        kd: NmSecPerRad::new(2.0).unwrap(),
        torque: NewtonMeters::new(-7.5).unwrap(),
    };
    let frame = encode::mit(rs03, &sent).unwrap();
    let host = drive::command(frame.id(), &frame.data()).unwrap().unwrap();
    let codes = match host.command {
        Command::Mit(codes) => Some(codes),
        _ => None,
    };
    let codes = codes.expect("an MIT frame reads back as an MIT command");
    let got = codes.command(Model::Rs03).unwrap();
    assert_eq!(host.target, t);
    // RS03 manual 261013 §4.1.2 and §4.4: Kp 0 to 5000, Kd 0 to 100.
    assert!(near(got.position.get(), -3.0, 25.14), "{got:?}");
    assert!(near(got.velocity.get(), 1.25, 40.0), "{got:?}");
    assert!(near(got.kp.get(), 40.0, 5000.0), "{got:?}");
    assert!(near(got.kd.get(), 2.0, 100.0), "{got:?}");
    assert!(near(got.torque.get(), -7.5, 120.0), "{got:?}");

    let status = drive::status(
        rs03,
        Mode::Reset,
        StatusFaults::default(),
        &feedback(0.0, 0.0, 0.0, 30.0),
    )
    .unwrap();
    let identity = drive::identity(t, Uid([0; 8]));
    for frame in [status, identity] {
        assert_eq!(
            drive::command(frame.id(), &frame.data()).unwrap(),
            None,
            "{frame:?}"
        );
    }
}

/// Guards: protocol - the drive side refuses what it can't encode rather than clamp it: a field outside the model's MIT
/// range or not finite, a temperature outside 0 to 6553.5 °C, a model whose scales aren't settled, and a value of the
/// wrong type for its register (RobStride manuals §4.1.2, §4.1.13; PLAN item 3).
#[test]
fn drive_frames_refuse_rather_than_clamp() {
    let rs03 = drive(Model::Rs03, 1);
    let none = StatusFaults::default();
    let cases = [
        (feedback(12.6, 0.0, 0.0, 25.0), StatusField::Position),
        (
            feedback(0.0, f64::from(f32::MAX), 0.0, 25.0),
            StatusField::Velocity,
        ),
        (feedback(0.0, 0.0, -60.1, 25.0), StatusField::Torque),
        (feedback(0.0, 0.0, 0.0, -0.1), StatusField::Temperature),
        (feedback(0.0, 0.0, 0.0, 6553.6), StatusField::Temperature),
    ];
    for (fb, field) in cases {
        let err = drive::status(rs03, Mode::Run, none, &fb).unwrap_err();
        assert!(
            matches!(err, DriveError::OutOfRange { field: got, .. } if got == field),
            "{fb:?}: {err:?}"
        );
    }
    assert_eq!(
        drive::status(
            drive(Model::Rs00, 1),
            Mode::Run,
            none,
            &feedback(0.0, 0.0, 0.0, 25.0)
        ),
        Err(DriveError::UnvouchedModel(Model::Rs00))
    );
    let wrong_type = ParamValue::Volts(Volts::new(24.0).unwrap());
    assert_eq!(
        drive::param_value(id(1), Param::CanTimeout, wrong_type),
        Err(DriveError::WrongValue {
            param: Param::CanTimeout
        })
    );
    let too_big = ParamValue::NewtonMeters(NewtonMeters::new(1e39).unwrap());
    assert_eq!(
        drive::param_value(id(1), Param::LimitTorque, too_big),
        Err(DriveError::WrongValue {
            param: Param::LimitTorque
        })
    );
}
