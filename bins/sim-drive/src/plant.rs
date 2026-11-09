//! The plant (PLAN item 4): a first-order joint, so MIT targets move something. The motor's MIT torque
//! `kp (p_t - p) + kd (v_t - v) + t_ff` drives a damper, `damping * v = torque`, with no inertia and no gravity yet (those
//! come from `config/dynamics.yaml` when a test needs them). The torque stops at `limit_torque` and the speed at
//! `limit_spd`, the caps preflight writes, and both at what the model's MIT feedback can carry.

use std::time::{Duration, Instant};

use robstride::{MitCommand, NmSecPerRad};

/// The sim joint's damping, N·m·s/rad. A sim value, not a measurement: with `kd` it sets how fast a target is reached,
/// a time constant of `(damping + kd) / kp`.
const DAMPING: f64 = 1.0;

/// The sim joint's damping, 1 N·m·s/rad, for tests that check the plant's response.
#[must_use]
pub fn plant_damping() -> NmSecPerRad {
    NmSecPerRad::new(DAMPING).unwrap_or_else(unreachable_damping)
}

#[expect(clippy::panic, reason = "a finite constant is always a gain")]
fn unreachable_damping() -> NmSecPerRad {
    panic!("the plant's damping isn't finite")
}
/// The longest integration step.
const STEP: Duration = Duration::from_millis(1);

/// What bounds the joint: each as a magnitude, plus the position range.
#[derive(Clone, Copy, Debug)]
pub(crate) struct Limits {
    pub(crate) torque: f64,
    pub(crate) speed: f64,
    pub(crate) position: (f64, f64),
}

#[derive(Clone, Copy, Debug)]
pub(crate) struct Plant {
    pub(crate) position: f64,
    pub(crate) velocity: f64,
    pub(crate) torque: f64,
    target: Option<MitCommand>,
    at: Option<Instant>,
}

impl Plant {
    pub(crate) const AT_ZERO: Self = Self {
        position: 0.0,
        velocity: 0.0,
        torque: 0.0,
        target: None,
        at: None,
    };

    /// The same joint, at rest where it is (a reboot doesn't move it).
    pub(crate) const fn at_rest(self) -> Self {
        Self {
            position: self.position,
            ..Self::AT_ZERO
        }
    }

    /// Move the joint up to `now`. Only a drive in Run drives it; otherwise it rests where it is and forgets its target.
    pub(crate) fn advance(&mut self, now: Instant, running: bool, limits: Limits) {
        let from = self.at.map_or(now, |at| at.min(now));
        self.at = Some(now.max(from));
        let Some(command) = self.target.filter(|_| running) else {
            self.target = None;
            self.velocity = 0.0;
            self.torque = 0.0;
            return;
        };
        let mut at = from;
        while at < now {
            let dt = STEP.min(now - at);
            self.step(&command, dt.as_secs_f64(), limits);
            at += dt;
        }
        self.rate(&command, limits);
    }

    /// A new MIT command taken at the time last advanced to.
    pub(crate) fn command(&mut self, command: MitCommand, limits: Limits) {
        self.target = Some(command);
        self.rate(&command, limits);
    }

    /// The torque the joint can't pass: the torque cap, or what the speed cap allows through the damping.
    fn torque_cap(limits: Limits) -> f64 {
        limits.torque.min(limits.speed * DAMPING)
    }

    /// Velocity and torque at the current position; whether a cap bound.
    fn rate(&mut self, c: &MitCommand, limits: Limits) -> bool {
        let (kp, kd) = (c.kp.get(), c.kd.get());
        let drive =
            kp * (c.position.get() - self.position) + kd * c.velocity.get() + c.torque.get();
        let free = drive / (DAMPING + kd);
        let torque_cap = Self::torque_cap(limits);
        let torque = (DAMPING * free).clamp(-torque_cap, torque_cap);
        self.torque = torque;
        self.velocity = torque / DAMPING;
        (DAMPING * free).abs() > torque_cap
    }

    /// One step of `dt` seconds: exact for the linear law; a straight line while a cap binds, up to where it stops
    /// binding and exact from there, so a stiff gain settles instead of overshooting.
    fn step(&mut self, c: &MitCommand, dt: f64, limits: Limits) {
        let capped = self.rate(c, limits);
        let (kp, kd) = (c.kp.get(), c.kd.get());
        let settles_at = c.position.get() + (kd * c.velocity.get() + c.torque.get()) / kp;
        let exact = |from: f64, dt: f64| {
            settles_at + (from - settles_at) * (-kp * dt / (DAMPING + kd)).exp()
        };
        let next = if kp <= 0.0 || (capped && self.velocity == 0.0) {
            // No spring, or a zero cap holding the joint still.
            self.position + self.velocity * dt
        } else if capped {
            // The cap stops binding where the free torque falls to it: kp (settles_at - p) = ±cap (damping + kd) / damping.
            let edge = settles_at
                - self.velocity.signum() * Self::torque_cap(limits) * (DAMPING + kd)
                    / (DAMPING * kp);
            let reach = (edge - self.position) / self.velocity;
            if (0.0..dt).contains(&reach) {
                exact(edge, dt - reach)
            } else {
                self.position + self.velocity * dt
            }
        } else {
            exact(self.position, dt)
        };
        self.position = next.clamp(limits.position.0, limits.position.1);
    }
}
