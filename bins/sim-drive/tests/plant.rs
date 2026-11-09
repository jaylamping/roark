//! The plant: MIT targets move the simulated joint (PLAN item 4 Plant), so control and the stop rules see motion on
//! `vcan` before any real drive moves.

#[expect(dead_code, reason = "each test file uses some of the shared helpers")]
mod common;

use std::time::{Duration, Instant};

use common::{host, id, ms, replies, rs03};
use robstride::{
    Inbound, MitCommand, Model, NewtonMeters, NmPerRad, NmSecPerRad, RadPerSec, Radians, Uid,
    Write, encode,
};
use sim_drive::{PLANT_DAMPING, SimDrive};

/// Drive 9, enabled and in Run by `t + 11 ms`.
fn running() -> (SimDrive, Instant) {
    let mut sim = SimDrive::new(rs03(9), Uid([9; 8]), 4);
    let t = Instant::now();
    sim.receive(t, host(encode::enable(id(9))));
    let _ = replies(&mut sim, t + ms(11));
    (sim, t + ms(11))
}

#[expect(
    clippy::unwrap_used,
    reason = "test helper; the values are in the RS03's ranges"
)]
fn mit(position: f64, kp: f64, kd: f64) -> robstride::Frame {
    let command = MitCommand {
        position: Radians::new(position).unwrap(),
        velocity: RadPerSec::new(0.0).unwrap(),
        kp: NmPerRad::new(kp).unwrap(),
        kd: NmSecPerRad::new(kd).unwrap(),
        torque: NewtonMeters::new(0.0).unwrap(),
    };
    encode::mit(rs03(9), &command).unwrap()
}

/// Send `frame` at `at` and read the joint from its status: (position, velocity, torque).
#[expect(
    clippy::unwrap_used,
    reason = "test helper; every frame sent here is answered with a status"
)]
fn joint(sim: &mut SimDrive, at: Instant, frame: robstride::Frame) -> (f64, f64, f64) {
    sim.receive(at, host(frame));
    let reply = replies(sim, at);
    let s = reply
        .iter()
        .find_map(|i| match i {
            Inbound::Status(s) => Some(s),
            _ => None,
        })
        .unwrap();
    let f = s.feedback(Model::Rs03).unwrap();
    (f.position.get(), f.velocity.get(), f.torque.get())
}

/// What a zero reads back as through the 16-bit MIT feedback encoding.
const ZERO: f64 = 0.002;

fn near(got: f64, want: f64, within: f64) -> bool {
    (got - want).abs() <= within
}

/// Guards: number - an MIT target moves the joint as a first-order plant: from rest toward the target with time
/// constant (damping + kd) / kp, settling on it, with the reported torque what the gains give (PLAN item 4 Plant;
/// the MIT law in the RobStride manual §4.1.2).
#[test]
fn an_mit_target_moves_the_joint_toward_it() {
    let (kp, kd) = (10.0, 1.0);
    let tau = Duration::from_secs_f64((PLANT_DAMPING + kd) / kp);
    let (mut sim, t) = running();
    let (p0, _, torque0) = joint(&mut sim, t, mit(1.0, kp, kd));
    assert!(near(p0, 0.0, 1e-3), "{p0}");
    // At the start the whole error drives it: kp * 1 rad, shared between damping and kd.
    assert!(
        near(torque0, kp * PLANT_DAMPING / (PLANT_DAMPING + kd), 0.05),
        "{torque0}"
    );

    let (p1, v1, _) = joint(&mut sim, t + tau, mit(1.0, kp, kd));
    assert!(
        near(p1, 1.0 - (-1.0_f64).exp(), 0.01),
        "one time constant: {p1}"
    );
    assert!(v1 > 0.0, "{v1}");
    let (p2, v2, torque2) = joint(&mut sim, t + tau * 10, mit(1.0, kp, kd));
    assert!(near(p2, 1.0, 0.01), "settled: {p2}");
    assert!(
        near(v2, 0.0, 0.05) && near(torque2, 0.0, 0.1),
        "{v2} {torque2}"
    );
}

/// Guards: safety - only a drive in Run moves: an MIT target to a drive in Reset moves nothing, a Disable stops the
/// joint where it is, and so does `canTimeout` dropping the drive to Reset (PLAN item 6: a disabled drive is limp).
#[test]
fn the_joint_moves_only_in_run() {
    let mut sim = SimDrive::new(rs03(9), Uid([9; 8]), 4);
    let t = Instant::now();
    let (p, _, torque) = joint(&mut sim, t, mit(1.0, 10.0, 1.0));
    assert!(
        near(p, 0.0, 1e-3) && near(torque, 0.0, ZERO),
        "{p} {torque}"
    );
    let (p, _, _) = joint(&mut sim, t + ms(500), mit(1.0, 10.0, 1.0));
    assert!(near(p, 0.0, 1e-3), "a drive in Reset: {p}");

    let (mut sim, t) = running();
    joint(&mut sim, t, mit(1.0, 10.0, 1.0));
    let (moved, _, _) = joint(&mut sim, t + ms(50), encode::disable(id(9)));
    assert!(moved > 0.05, "{moved}");
    // The Disable's silence is over by 100 ms.
    let (held, v, torque) = joint(&mut sim, t + ms(600), mit(1.0, 10.0, 1.0));
    assert!(
        near(held, moved, 1e-3) && near(v, 0.0, ZERO) && near(torque, 0.0, ZERO),
        "{held} {v} {torque}"
    );
}

/// Guards: safety - the caps preflight writes are the caps the joint obeys: torque never past `limit_torque` and speed
/// never past `limit_spd` (PLAN item 6 drive layer: the three caps).
#[test]
fn the_written_caps_bound_the_joint() {
    let far = |sim: &mut SimDrive, at| joint(sim, at, mit(3.0, 500.0, 0.0));
    let cap = |sim: &mut SimDrive, at, write: Result<Write, robstride::EncodeError>| {
        let w = write.unwrap();
        sim.receive(at, host(encode::param_write(&w)));
        let _ = replies(sim, at);
    };
    // The torque cap: the far target's torque stops at 5 N·m, and the joint moves at what that torque gives.
    let (mut sim, t) = running();
    let torque_cap = NewtonMeters::new(5.0).unwrap();
    cap(&mut sim, t, Write::limit_torque(rs03(9), torque_cap));
    let (_, v, torque) = far(&mut sim, t);
    assert!(
        near(torque, 5.0, 0.05) && near(v, 5.0 / PLANT_DAMPING, 0.05),
        "{v} {torque}"
    );
    // The speed cap: the joint never passes 2 rad/s, so the torque is what that speed takes.
    let (mut sim, t) = running();
    let speed_cap = RadPerSec::new(2.0).unwrap();
    cap(&mut sim, t, Write::limit_spd(rs03(9), speed_cap));
    let (_, v, torque) = far(&mut sim, t);
    assert!(
        near(v, 2.0, 0.01) && near(torque, 2.0 * PLANT_DAMPING, 0.05),
        "{v} {torque}"
    );
    let (_, v, _) = far(&mut sim, t + ms(100));
    assert!(near(v, 2.0, 0.01), "{v}");
}
