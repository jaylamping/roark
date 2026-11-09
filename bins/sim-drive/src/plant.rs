//! The plant (PLAN item 4): a first-order joint, so MIT targets move something. The motor's MIT torque
//! `kp (p_t - p) + kd (v_t - v) + t_ff` drives a damper, `damping * v = torque`, with no inertia and no gravity yet (those
//! come from `config/dynamics.yaml` when a test needs them). The torque stops at `limit_torque` and the speed at
//! `limit_spd`, the caps preflight writes, and both at what the model's MIT feedback can carry.

use std::time::{Duration, Instant};

use robstride::MitCommand;

/// The sim joint's damping, N·m·s/rad. A sim value, not a measurement: with `kd` it sets how fast a target is reached,
/// a time constant of `(PLANT_DAMPING + kd) / kp`.
pub const PLANT_DAMPING: f64 = 1.0;
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

    /// Velocity and torque at the current position; whether a cap bound.
    fn rate(&mut self, c: &MitCommand, limits: Limits) -> bool {
        let (kp, kd) = (c.kp.get(), c.kd.get());
        let drive =
            kp * (c.position.get() - self.position) + kd * c.velocity.get() + c.torque.get();
        let free = drive / (PLANT_DAMPING + kd);
        let torque_cap = limits.torque.min(limits.speed * PLANT_DAMPING);
        let torque = (PLANT_DAMPING * free).clamp(-torque_cap, torque_cap);
        self.torque = torque;
        self.velocity = torque / PLANT_DAMPING;
        (PLANT_DAMPING * free).abs() > torque_cap
    }

    /// One step of `dt` seconds: exact for the linear law, a straight line while a cap binds.
    fn step(&mut self, c: &MitCommand, dt: f64, limits: Limits) {
        let capped = self.rate(c, limits);
        let (kp, kd) = (c.kp.get(), c.kd.get());
        let next = if capped || kp <= 0.0 {
            self.position + self.velocity * dt
        } else {
            let settles_at = c.position.get() + (kd * c.velocity.get() + c.torque.get()) / kp;
            settles_at + (self.position - settles_at) * (-kp * dt / (PLANT_DAMPING + kd)).exp()
        };
        self.position = next.clamp(limits.position.0, limits.position.1);
    }
}
