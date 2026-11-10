//! The simulated drive against what the real ones do (PLAN items 2 and 4): its replies to each host frame, the timing
//! windows the bus layer and safety must survive, and `canTimeout`. Time is passed in; nothing sleeps (testing.md rule 6).

mod common;

use std::time::Instant;

use common::{ask, host, id, mode_of, ms, neutral, replies, rs03};
use robstride::{
    CanTimeout, Inbound, Mode, Param, ParamOutcome, ParamValue, Reporting, Uid, Write, encode,
};
use sim_drive::SimDrive;

/// Guards: protocol - the simulated drive answers each host frame the way the manuals say a drive does: identity to
/// type 0, a type-2 status to MIT, enable, disable, set zero and type-18 writes, a type-17 reply holding the value last
/// written, and nothing to a frame for another drive (RobStride manuals §4.1.1 to §4.1.7, §4.1.11).
#[test]
fn answers_each_host_frame_as_a_drive_does() {
    let d = rs03(3);
    let uid = Uid([9, 8, 7, 6, 5, 4, 3, 2]);
    let mut sim = SimDrive::new(d, uid, 1);
    let t = Instant::now();

    assert_eq!(
        ask(&mut sim, t, encode::get_id(id(3))),
        [Inbound::Identity { device: id(3), uid }]
    );
    assert_eq!(
        ask(&mut sim, t, encode::get_id(id(4))),
        [],
        "a frame for drive 4"
    );

    let read = |sim: &mut SimDrive, param| ask(sim, t, encode::param_read(id(3), param));
    let value = |v| {
        vec![Inbound::Param {
            device: id(3),
            param: Param::CanTimeout,
            outcome: ParamOutcome::Read(v),
        }]
    };
    assert_eq!(
        read(&mut sim, Param::CanTimeout),
        value(ParamValue::CanTimeout(CanTimeout::OFF))
    );
    let written = ask(&mut sim, t, encode::param_write(&Write::can_timeout(d)));
    assert_eq!(
        written.iter().map(mode_of).collect::<Vec<_>>(),
        [Some(Mode::Reset)],
        "a write gets a status"
    );
    assert_eq!(
        read(&mut sim, Param::CanTimeout),
        value(ParamValue::CanTimeout(CanTimeout::RUNTIME))
    );

    for (name, frame) in [
        ("mit", neutral(3)),
        ("set zero", encode::set_zero(id(3))),
        ("disable", encode::disable(id(3))),
    ] {
        let got: Vec<_> = ask(&mut sim, t + ms(200), frame)
            .iter()
            .map(mode_of)
            .collect();
        assert_eq!(got, [Some(Mode::Reset)], "{name}");
    }
    for (name, frame) in [
        (
            "reporting on",
            encode::active_reporting(id(3), Reporting::On),
        ),
        (
            "reporting off",
            encode::active_reporting(id(3), Reporting::Off),
        ),
        ("version", encode::version_query(id(3))),
    ] {
        assert_eq!(
            ask(&mut sim, t + ms(300), frame),
            [],
            "{name}: no reply known from the manuals or a capture"
        );
    }
}

/// Guards: number - the timing windows the bus layer and safety must survive (PLAN item 2): Run within 0 to 11 ms of
/// enable and never before, nothing answered for up to 50 ms after a Disable, a Set Zero on an enabled drive going silent
/// 511 to 614 ms later for 45 to 66 ms, and active reports every 10 ms by default (§4.1.11).
#[test]
fn timing_windows_match_the_bench() {
    let mit = neutral(1);
    let mut longest_quiet = 0;
    let mut slowest_run = 0;
    for seed in 0..200 {
        let mut sim = SimDrive::new(rs03(1), Uid([0; 8]), seed);
        let t = Instant::now();

        // Enable: one status, in Run, between 0 and 11 ms later.
        sim.receive(t, host(encode::enable(id(1))));
        let run = (0..=11).find(|&n| !replies(&mut sim, t + ms(n)).is_empty());
        assert!(run.is_some(), "seed {seed}: no Run reply by 11 ms");
        let run = run.unwrap();
        slowest_run = slowest_run.max(run);
        assert_eq!(
            mode_of(&ask(&mut sim, t + ms(run), mit)[0]),
            Some(Mode::Run),
            "seed {seed}"
        );

        // Disable: answered, then silent; by 50 ms it answers again.
        let off = t + ms(20);
        assert_eq!(
            ask(&mut sim, off, encode::disable(id(1))).len(),
            1,
            "seed {seed}"
        );
        let quiet =
            (1..=51).find(|&n| !ask(&mut sim, off + ms(n), encode::get_id(id(1))).is_empty());
        assert!(
            quiet.is_some(),
            "seed {seed}: still silent 51 ms after Disable"
        );
        let quiet = quiet.unwrap();
        longest_quiet = longest_quiet.max(quiet);

        // Set Zero while enabled: the blackout starts 511 to 614 ms later and lasts 45 to 66 ms.
        let on = t + ms(100);
        sim.receive(on, host(encode::enable(id(1))));
        replies(&mut sim, on + ms(11));
        let zero = on + ms(20);
        assert_eq!(
            ask(&mut sim, zero, encode::set_zero(id(1))).len(),
            1,
            "seed {seed}"
        );
        let answered: Vec<bool> = (0..=700)
            .map(|n| !ask(&mut sim, zero + ms(n), encode::get_id(id(1))).is_empty())
            .collect();
        let start = answered.iter().position(|a| !a);
        assert!(start.is_some(), "seed {seed}: no blackout");
        let start = start.unwrap();
        let len = answered[start..].iter().position(|a| *a).unwrap();
        // Probed once a millisecond, so each edge can read up to 1 ms late.
        assert!(
            (511..=615).contains(&start),
            "seed {seed}: blackout began at {start} ms"
        );
        assert!(
            (44..=67).contains(&len),
            "seed {seed}: blackout lasted {len} ms"
        );
    }
    assert!(
        slowest_run > 5,
        "no seed in 200 took more than {slowest_run} ms to reach Run"
    );
    assert!(
        longest_quiet > 25,
        "no seed in 200 went quiet after Disable for more than {longest_quiet} ms"
    );

    // Reports: every 10 ms while on, none after off.
    let mut sim = SimDrive::new(rs03(2), Uid([0; 8]), 7);
    let t = Instant::now();
    sim.receive(t, host(encode::active_reporting(id(2), Reporting::On)));
    let reports = (1..=50)
        .filter(|&n| !replies(&mut sim, t + ms(n)).is_empty())
        .count();
    assert_eq!(reports, 5, "reports in 50 ms");
    sim.receive(
        t + ms(50),
        host(encode::active_reporting(id(2), Reporting::Off)),
    );
    assert!(
        (51..=100).all(|n| replies(&mut sim, t + ms(n)).is_empty()),
        "a report after reporting off"
    );
}

/// Guards: safety - `canTimeout` 1000 drops an enabled drive to Reset 50 ms after its last command, 0 never does, and a
/// power cycle puts it back to 0, which is why the runtime rewrites it after any reboot (PLAN item 6, drive layer; item 4).
#[test]
fn can_timeout_drops_an_enabled_drive_to_reset() {
    let d = rs03(5);
    let get_id = encode::get_id(id(5));
    let enabled = |timeout: bool| {
        let mut sim = SimDrive::new(d, Uid([0; 8]), 3);
        let t = Instant::now();
        if timeout {
            ask(&mut sim, t, encode::param_write(&Write::can_timeout(d)));
        }
        sim.receive(t, host(encode::enable(id(5))));
        replies(&mut sim, t + ms(11));
        // The enable is the last command; canTimeout counts from it.
        (sim, t)
    };
    let mode = |sim: &mut SimDrive, at| mode_of(&ask(sim, at, neutral(5))[0]);

    // Fed every 49 ms it stays in Run; 50 ms of silence drops it to Reset.
    let (mut sim, t) = enabled(true);
    ask(&mut sim, t + ms(49), get_id);
    assert_eq!(mode(&mut sim, t + ms(98)), Some(Mode::Run));
    let (mut sim, t) = enabled(true);
    assert_eq!(mode(&mut sim, t + ms(50)), Some(Mode::Reset));
    // canTimeout 0: no timeout at all.
    let (mut sim, t) = enabled(false);
    assert_eq!(mode(&mut sim, t + ms(10_000)), Some(Mode::Run));

    // A power cycle: Reset, and canTimeout back to 0.
    let (mut sim, t) = enabled(true);
    let up = t + ms(11);
    sim.inject(up, sim_drive::Fault::Reboot).unwrap();
    let read = ask(&mut sim, up, encode::param_read(id(5), Param::CanTimeout));
    let off = ParamOutcome::Read(ParamValue::CanTimeout(CanTimeout::OFF));
    assert_eq!(
        read,
        [Inbound::Param {
            device: id(5),
            param: Param::CanTimeout,
            outcome: off
        }]
    );
}
