//! The plant (PLAN item 4): a first-order joint, so MIT targets move something. The motor's MIT torque
//! `kp (p_t - p) + kd (v_t - v) + t_ff` drives a damper, `damping * v = torque`, with no inertia and no gravity yet.
//! The torque stops at `limit_torque` and the speed at `limit_spd`, and both at what the model's MIT feedback can carry.
//! That the drive holds those two caps in MIT mode is a sim assumption: no bench capture shows it yet (PLAN item 6).

use std::time::Duration;

use robstride::{MitCommand, NewtonMeters, RadPerSec, Radians};

/// The sim joint's damping, N·m·s/rad. A sim value, not a measurement: with `kd` it sets how fast a target is reached,
/// a time constant of `(damping + kd) / kp`.
const DAMPING: f64 = 1.0;

/// What bounds the joint: the torque and speed each as a magnitude, and the position range.
#[derive(Clone, Copy, Debug)]
pub(crate) struct Limits {
    pub(crate) torque: NewtonMeters,
    pub(crate) speed: RadPerSec,
    pub(crate) position: (Radians, Radians),
}

/// The joint's velocity and torque at one moment.
#[derive(Clone, Copy, Debug)]
pub(crate) struct Motion {
    pub(crate) velocity: RadPerSec,
    pub(crate) torque: NewtonMeters,
}

/// The joint: where it is, and the MIT command it follows (only while the drive is in Run). Velocity and torque follow
/// from those, so a reply built at any moment shows the joint as it is then. The drive keeps the time.
#[derive(Clone, Copy, Debug)]
pub(crate) struct Plant {
    position: Radians,
    target: Option<MitCommand>,
}

impl Plant {
    /// A joint at rest at `position`, following nothing.
    pub(crate) const fn resting_at(position: Radians) -> Self {
        Self {
            position,
            target: None,
        }
    }

    /// The same joint, at rest where it is, following nothing: a drive leaving Run, or rebooting, doesn't move it.
    pub(crate) const fn at_rest(self) -> Self {
        Self::resting_at(self.position)
    }

    /// Where the joint is.
    pub(crate) const fn position(&self) -> Radians {
        self.position
    }

    /// The joint now reads `position` where it stands (a Set Zero), still following what it followed.
    pub(crate) const fn set_position(&mut self, position: Radians) {
        self.position = position;
    }

    /// Move the joint on by `dt`. Only a drive in Run drives it; otherwise it rests where it is and forgets its target.
    pub(crate) fn advance(&mut self, dt: Duration, running: bool, limits: Limits) {
        let Some(command) = self.target.filter(|_| running) else {
            self.target = None;
            return;
        };
        self.step(&command, dt.as_secs_f64(), limits);
    }

    /// A new MIT command, taken where the joint was last advanced to.
    pub(crate) const fn command(&mut self, command: MitCommand) {
        self.target = Some(command);
    }

    /// Velocity and torque now: zero at rest, or out of Run. `None` if a value isn't finite.
    pub(crate) fn motion(&self, running: bool, limits: Limits) -> Option<Motion> {
        let (velocity, torque) = self.target.filter(|_| running).map_or((0.0, 0.0), |c| {
            let (velocity, torque, _) = self.rate(&c, limits);
            (velocity, torque)
        });
        Some(Motion {
            velocity: RadPerSec::new(velocity)?,
            torque: NewtonMeters::new(torque)?,
        })
    }

    /// The torque the joint can't pass: the torque cap, or what the speed cap allows through the damping.
    fn torque_cap(limits: Limits) -> f64 {
        limits.torque.get().min(limits.speed.get() * DAMPING)
    }

    /// Velocity and torque at the current position under `c`, and whether a cap binds.
    fn rate(&self, c: &MitCommand, limits: Limits) -> (f64, f64, bool) {
        let (kp, kd) = (c.kp.get(), c.kd.get());
        let drive =
            kp * (c.position.get() - self.position.get()) + kd * c.velocity.get() + c.torque.get();
        let free = DAMPING * drive / (DAMPING + kd);
        let cap = Self::torque_cap(limits);
        let torque = free.clamp(-cap, cap);
        (torque / DAMPING, torque, free.abs() > cap)
    }

    /// Move `dt` seconds under `c`, in one step: exact for the linear law; a straight line while a cap binds, up to
    /// where it stops binding and exact from there. The free torque only falls once the cap stops binding, so a cap
    /// never binds again within the step and one step of any length is exact.
    fn step(&mut self, c: &MitCommand, dt: f64, limits: Limits) {
        let (velocity, _, capped) = self.rate(c, limits);
        let (kp, kd) = (c.kp.get(), c.kd.get());
        let position = self.position.get();
        let settles_at = c.position.get() + (kd * c.velocity.get() + c.torque.get()) / kp;
        let exact = |from: f64, dt: f64| {
            settles_at + (from - settles_at) * (-kp * dt / (DAMPING + kd)).exp()
        };
        let next = if kp <= 0.0 || (capped && velocity == 0.0) {
            // No spring, or a zero cap holding the joint still.
            position + velocity * dt
        } else if capped {
            // The cap stops binding where the free torque falls to it: kp (settles_at - p) = ±cap (damping + kd) / damping.
            let edge = settles_at
                - velocity.signum() * Self::torque_cap(limits) * (DAMPING + kd) / (DAMPING * kp);
            let reach = (edge - position) / velocity;
            if (0.0..dt).contains(&reach) {
                exact(edge, dt - reach)
            } else {
                position + velocity * dt
            }
        } else {
            exact(position, dt)
        };
        let (lo, hi) = limits.position;
        // Every input is finite, so the step is; were it not, the joint would stay where it is.
        if let Some(next) = Radians::new(next.clamp(lo.get(), hi.get())) {
            self.position = next;
        }
    }
}
