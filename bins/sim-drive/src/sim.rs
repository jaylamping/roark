//! One simulated drive: what it answers, when, and the windows in which it answers nothing. Sans-IO: frames in, frames
//! out, and the time passed in by the caller (testing.md rule 6).

use std::time::{Duration, Instant};

use robstride::drive::{self as wire, Command, DriveFrame, HostFrame};

use crate::fault::{Active, Fault, FaultRefused, Injected, Plan, Trigger};
use crate::plant::{Limits, Plant};
use robstride::{
    Amps, Celsius, Damper, DeviceId, Drive, Feedback, Gain, Mode, NewtonMeters, Param, ParamValue,
    RadPerSec, RadPerSecSq, Radians, ReportInterval, Reporting, RunMode, Uid, Volts, ZeroSta,
};

/// Enable to Run (PLAN item 4: 0 to 11 ms; item 2 measured 1.4 to 10.3 ms).
const ENABLE_DELAY_US: (u64, u64) = (0, 11_000);
/// After a Disable the drive answers nothing for up to 50 ms (PLAN item 4; item 2 measured up to 48.7 ms).
const DISABLE_SILENCE_US: (u64, u64) = (0, 50_000);
/// A Set Zero on an enabled drive: silent 511 to 614 ms later, for 45 to 66 ms (PLAN item 2).
const ZERO_BLACKOUT_START_US: (u64, u64) = (511_000, 614_000);
const ZERO_BLACKOUT_LEN_US: (u64, u64) = (45_000, 66_000);
/// The temperature every status reports. A sim value, not a measurement.
const TEMPERATURE_C: f64 = 25.0;
/// Frames waiting for their due time: [`crate::MAX_LATE`] of command replies at the 250 Hz tick with reports on every
/// 10 ms, and room to spare. A full outbox drops the frame and counts it.
const OUTBOX: usize = 64;

/// One simulated RobStride drive.
#[derive(Debug)]
pub struct SimDrive {
    drive: Drive,
    uid: Uid,
    mode: Mode,
    params: [(Param, ParamValue); Param::ALL.len()],
    plant: Plant,
    /// Injected faults in effect now; a reboot clears them.
    active: Active,
    /// Scheduled faults and the record of injections; a reboot keeps them.
    plan: Plan,
    /// The next active report, while reporting is on.
    next_report: Option<Instant>,
    last_command: Option<Instant>,
    /// When an enable reaches Run.
    run_at: Option<Instant>,
    /// Windows in which every frame is dropped: post-Disable silence, then the Set Zero blackout.
    silence: Option<(Instant, Instant)>,
    blackout: Option<(Instant, Instant)>,
    outbox: [Option<Queued>; OUTBOX],
    /// The second copy of a duplicated frame, given by the next `pop_due`.
    repeat: Option<DriveFrame>,
    /// The time the drive was last brought up to.
    stepped: Option<Instant>,
    rng: Rng,
    dropped: u64,
}

impl SimDrive {
    /// A powered-up drive in Reset with every parameter at its default. `seed` picks its delays, so a run replays
    /// exactly (can.md section 3).
    #[must_use]
    pub fn new(drive: Drive, uid: Uid, seed: u64) -> Self {
        Self {
            drive,
            uid,
            mode: Mode::Reset,
            params: defaults(drive),
            plant: Plant::AT_ZERO,
            active: Active::default(),
            plan: Plan::EMPTY,
            next_report: None,
            last_command: None,
            run_at: None,
            silence: None,
            blackout: None,
            outbox: [None; OUTBOX],
            repeat: None,
            stepped: None,
            rng: Rng(seed),
            dropped: 0,
        }
    }

    /// The drive's CAN ID now (a set-ID changes it).
    #[must_use]
    pub const fn id(&self) -> DeviceId {
        self.drive.id()
    }

    /// Frames this drive had to drop because its outbox was full, or couldn't build (no status for an RS00, whose MIT
    /// scales aren't settled).
    #[must_use]
    pub const fn dropped(&self) -> u64 {
        self.dropped
    }

    /// Inject `fault` now, at `now`, and record it.
    ///
    /// # Errors
    /// [`FaultRefused`] for a fault the drive can't honour; nothing is recorded then.
    pub fn inject(&mut self, now: Instant, fault: Fault) -> Result<(), FaultRefused> {
        self.check(fault)?;
        self.advance(now);
        self.apply(now, fault);
        Ok(())
    }

    /// Schedule `fault` to fire on `trigger`.
    ///
    /// # Errors
    /// [`FaultRefused`] for a fault the drive can't honour, `OnMit(0)`, or a full plan ([`crate::FAULT_PLAN`]).
    pub fn schedule(&mut self, trigger: Trigger, fault: Fault) -> Result<(), FaultRefused> {
        self.check(fault)?;
        self.plan.schedule(trigger, fault)
    }

    fn check(&self, fault: Fault) -> Result<(), FaultRefused> {
        fault.check()?;
        match fault {
            Fault::Param(param, value) if wire::param_value(self.id(), param, value).is_err() => {
                Err(FaultRefused::WrongType(param))
            }
            _ => Ok(()),
        }
    }

    /// The oldest injection not yet taken.
    pub fn take_injected(&mut self) -> Option<Injected> {
        self.plan.take()
    }

    /// Injections the record had no room for because they weren't taken.
    #[must_use]
    pub const fn injections_lost(&self) -> u64 {
        self.plan.lost
    }

    /// A host frame arrives at `now`. Frames for other drives, and frames inside a silence window, change nothing.
    pub fn receive(&mut self, now: Instant, frame: HostFrame) {
        if frame.target != self.id() {
            return;
        }
        self.advance(now);
        if in_window(self.silence, now) || in_window(self.blackout, now) {
            return;
        }
        // A lost Disable is lost before the drive sees it: no reply, no change, and `canTimeout` doesn't restart.
        if frame.command == Command::Disable && self.active.ignored_disables > 0 {
            self.active.ignored_disables -= 1;
            return;
        }
        self.last_command = Some(now);
        match frame.command {
            Command::GetId => self.send(now, Some(wire::identity(self.id(), self.uid))),
            Command::Mit(codes) => {
                self.plan.mits = self.plan.mits.saturating_add(1);
                self.fire_due(now);
                // A model whose MIT scales aren't settled has no command to take: the joint stays put.
                if self.mode == Mode::Run
                    && let Ok(command) = codes.command(self.drive.model())
                {
                    let limits = self.limits();
                    self.plant.command(command, limits);
                }
                self.send(now, self.status(self.mode));
            }
            Command::Enable => match (self.mode, self.run_at) {
                (Mode::Run, _) | (_, Some(_)) => self.send(now, self.status(self.mode)),
                // The Run status is built when Run is reached (`advance`), with the faults in effect then.
                (Mode::Reset | Mode::Calibration, None) => {
                    self.run_at = Some(now + self.rng.between(ENABLE_DELAY_US));
                }
            },
            Command::Disable | Command::FaultClear => {
                self.mode = Mode::Reset;
                self.run_at = None;
                self.send(now, self.status(Mode::Reset));
                self.silence = Some((now, now + self.rng.between(DISABLE_SILENCE_US)));
            }
            Command::SetZero => {
                self.plant.position = 0.0;
                self.send(now, self.status(self.mode));
                if self.mode == Mode::Run {
                    let start = now + self.rng.between(ZERO_BLACKOUT_START_US);
                    self.blackout = Some((start, start + self.rng.between(ZERO_BLACKOUT_LEN_US)));
                }
            }
            // No capture or manual line says what a drive answers to these, so the sim answers nothing.
            Command::SetId { new } => self.drive = Drive::new(new, self.drive.model()),
            Command::VersionQuery => {}
            Command::ParamRead(param) => {
                let reply = self
                    .param(param)
                    .and_then(|v| wire::param_value(self.id(), param, v).ok());
                self.send(
                    now,
                    Some(reply.unwrap_or_else(|| wire::param_refused(self.id(), param))),
                );
            }
            Command::ParamWrite { param, value } => {
                if !self.active.ignores_write(param)
                    && let Some(slot) = self.params.iter_mut().find(|(p, _)| *p == param)
                {
                    slot.1 = value;
                }
                self.send(now, self.status(self.mode));
            }
            Command::Reporting(Reporting::On) => {
                self.next_report = self.report_interval().map(|i| now + i);
            }
            Command::Reporting(Reporting::Off) => self.next_report = None,
        }
    }

    /// The next frame due by `now`, earliest first. Injected transport faults apply here, as each frame falls due, so
    /// they reach frames already waiting: a silent drive sends nothing, a late one delays each frame once more by its
    /// lateness, and lost or doubled frames go by count.
    pub fn pop_due(&mut self, now: Instant) -> Option<DriveFrame> {
        self.advance(now);
        if let Some(frame) = self.repeat.take() {
            return Some(frame);
        }
        loop {
            let slot = self
                .outbox
                .iter_mut()
                .filter(|s| s.is_some_and(|q| q.due <= now))
                .min_by_key(|s| s.map(|q| q.due))?;
            let queued = slot.take()?;
            if self.active.silent {
                continue;
            }
            if !queued.delayed && !self.active.late.is_zero() {
                *slot = Some(Queued {
                    due: queued.due + self.active.late,
                    frame: queued.frame,
                    delayed: true,
                });
                continue;
            }
            if self.active.drop > 0 {
                self.active.drop -= 1;
                continue;
            }
            if self.active.duplicate > 0 {
                self.active.duplicate -= 1;
                self.repeat = Some(queued.frame);
            }
            return Some(queued.frame);
        }
    }

    /// When something next happens without a frame arriving: a reply or report falls due, an enable reaches Run,
    /// `canTimeout` fires, or a scheduled fault's time comes. The caller waits at most until then.
    #[must_use]
    pub fn next_event(&self) -> Option<Instant> {
        let due = self.outbox.iter().flatten().map(|q| q.due);
        due.chain(self.next_report)
            .chain(self.run_at)
            .chain(self.timeout_at())
            .chain(self.plan.next_at())
            .min()
    }

    /// Power off and on: Reset, every parameter back to its default (`canTimeout` 0), reporting off, nothing in flight,
    /// every injected fault cleared (PLAN item 4). The joint stays where it is, and the fault plan and its record are
    /// the test's, so they stay too.
    pub fn power_cycle(&mut self) {
        *self = Self {
            rng: Rng(self.rng.next()),
            dropped: self.dropped,
            plant: self.plant.at_rest(),
            plan: self.plan,
            stepped: self.stepped,
            ..Self::new(self.drive, self.uid, 0)
        };
    }

    /// Bring the drive's state up to `now`, each event at its own time and in time order: an enable reaching Run (its
    /// status sent then), `canTimeout` firing, a scheduled fault's time, with the joint moving in between; then reports
    /// falling due.
    fn advance(&mut self, now: Instant) {
        // Each pass handles one event and clears it, so this ends; the bound only makes that plain.
        for _ in 0..crate::FAULT_PLAN + 2 {
            let since = self.stepped.unwrap_or(now);
            let due = |at: Option<Instant>| at.filter(|at| *at <= now).map(|at| at.max(since));
            let (run, timeout, fault) = (
                due(self.run_at),
                due(self.timeout_at()),
                due(self.plan.next_at()),
            );
            let Some(at) = [run, timeout, fault].into_iter().flatten().min() else {
                break;
            };
            let limits = self.limits();
            self.plant.advance(at, self.mode == Mode::Run, limits);
            self.stepped = Some(at);
            if run == Some(at) {
                self.run_at = None;
                self.mode = Mode::Run;
                self.send(at, self.status(Mode::Run));
            } else if timeout == Some(at) {
                self.mode = Mode::Reset;
            } else {
                self.fire_due(at);
            }
        }
        let limits = self.limits();
        self.plant.advance(now, self.mode == Mode::Run, limits);
        self.stepped = Some(now);
        self.fire_due(now);
        while let Some(at) = self.next_report.filter(|at| *at <= now) {
            let report = self.report();
            if !in_window(self.blackout, at) {
                self.send(at, report);
            }
            self.next_report = self.report_interval().map(|i| at + i);
        }
    }

    /// When `canTimeout` drops an enabled drive to Reset (PLAN item 6: the drive goes limp after the last command).
    fn timeout_at(&self) -> Option<Instant> {
        if self.mode != Mode::Run {
            return None;
        }
        let timeout = match self.param(Param::CanTimeout)? {
            ParamValue::CanTimeout(t) => t.duration()?,
            _ => return None,
        };
        Some(self.last_command? + timeout)
    }

    /// Fire every scheduled fault now due.
    fn fire_due(&mut self, now: Instant) {
        while let Some((at, fault)) = self.plan.due(now) {
            self.apply(at, fault);
        }
    }

    /// Put `fault` in effect, recorded at `at`.
    fn apply(&mut self, at: Instant, fault: Fault) {
        self.plan.record(Injected {
            at,
            device: self.id(),
            fault,
        });
        let a = &mut self.active;
        match fault {
            Fault::Silent => a.silent = true,
            Fault::Late(by) => a.late = by,
            Fault::Drop(n) => a.drop = a.drop.saturating_add(n),
            Fault::Duplicate(n) => a.duplicate = a.duplicate.saturating_add(n),
            Fault::FaultBits(faults) => a.faults = faults,
            Fault::Temperature(c) => a.temperature = Some(c),
            Fault::IgnoreWrites(param) => a.ignore_writes(param),
            Fault::IgnoreDisables(n) => a.ignored_disables = a.ignored_disables.saturating_add(n),
            Fault::Mode(mode) => {
                self.mode = mode;
                self.run_at = None;
            }
            Fault::Param(param, value) => {
                if let Some(slot) = self.params.iter_mut().find(|(p, _)| *p == param) {
                    slot.1 = value;
                }
            }
            Fault::Reboot => self.power_cycle(),
        }
    }

    /// The joint's bounds: the caps written to the drive (a negative one, which only an injected register can hold,
    /// as zero), and what its MIT feedback can carry. The registers keep what was written, for read-back.
    fn limits(&self) -> Limits {
        let ranges = self.drive.model().ranges();
        let torque = match self.param(Param::LimitTorque) {
            Some(ParamValue::NewtonMeters(t)) => t.get(),
            _ => ranges.torque_max.get(),
        }
        .max(0.0);
        let speed = match self.param(Param::LimitSpd) {
            Some(ParamValue::RadPerSec(v)) => v.get(),
            _ => ranges.speed_max.get(),
        }
        .max(0.0);
        match self.drive.model().mit_scales() {
            Ok(s) => Limits {
                torque: torque.min(s.torque.max()),
                speed: speed.min(s.velocity.max()),
                position: (s.position.min(), s.position.max()),
            },
            // No status for a model whose scales aren't settled, so the joint never moves either.
            Err(_) => Limits {
                torque: 0.0,
                speed: 0.0,
                position: (0.0, 0.0),
            },
        }
    }

    fn report_interval(&self) -> Option<Duration> {
        match self.param(Param::EpScanTime)? {
            ParamValue::ReportInterval(r) => r.duration(),
            _ => None,
        }
    }

    fn param(&self, param: Param) -> Option<ParamValue> {
        self.params
            .iter()
            .find(|(p, _)| *p == param)
            .map(|(_, v)| *v)
    }

    fn feedback(&self) -> Feedback {
        let running = self.mode == Mode::Run;
        let (velocity, torque) = if running {
            (self.plant.velocity, self.plant.torque)
        } else {
            (0.0, 0.0)
        };
        Feedback {
            position: lit(Radians::new(self.plant.position)),
            velocity: lit(RadPerSec::new(velocity)),
            torque: lit(NewtonMeters::new(torque)),
            temperature: self
                .active
                .temperature
                .unwrap_or_else(|| lit(Celsius::new(TEMPERATURE_C))),
        }
    }

    /// A type-2 status in `mode`, or `None` for a model the codec can't encode a status for.
    fn status(&self, mode: Mode) -> Option<DriveFrame> {
        wire::status(self.drive, mode, self.active.faults, &self.feedback()).ok()
    }

    fn report(&self) -> Option<DriveFrame> {
        wire::report(self.drive, self.mode, self.active.faults, &self.feedback()).ok()
    }

    /// Queue `frame` to go out at `due`; a frame that can't be built or queued is dropped and counted. Transport faults
    /// apply when it falls due ([`Self::pop_due`]).
    fn send(&mut self, due: Instant, frame: Option<DriveFrame>) {
        let free = self.outbox.iter_mut().find(|s| s.is_none());
        match (frame, free) {
            (Some(frame), Some(slot)) => {
                *slot = Some(Queued {
                    due,
                    frame,
                    delayed: false,
                });
            }
            (None, _) | (Some(_), None) => self.dropped += 1,
        }
    }
}

/// A frame waiting to go out.
#[derive(Clone, Copy, Debug)]
struct Queued {
    due: Instant,
    frame: DriveFrame,
    /// Already delayed by `Late` once.
    delayed: bool,
}

fn in_window(window: Option<(Instant, Instant)>, now: Instant) -> bool {
    window.is_some_and(|(start, end)| start <= now && now < end)
}

/// The register values of a drive just powered up. Only `canTimeout`, `damper` and `zero_sta` are facts (PLAN items 4 and
/// 6, §4.1.13); the rest are sim values a test can overwrite, chosen so preflight's window checks pass on the bench supply.
fn defaults(drive: Drive) -> [(Param, ParamValue); Param::ALL.len()] {
    let caps = drive.model().ranges();
    Param::ALL.map(|param| {
        let value = match param {
            Param::RunMode => ParamValue::RunMode(RunMode::Mit),
            Param::ZeroSta => ParamValue::ZeroSta(ZeroSta::ZeroToTwoPi),
            Param::Damper => ParamValue::Damper(Damper::ProtectionOn),
            Param::CoggingCompensation | Param::IqTest => ParamValue::Switch(false),
            // 1: 10 ms, the interval §4.1.11 gives for reporting turned on.
            Param::EpScanTime => ParamValue::ReportInterval(ReportInterval::from_ticks(1)),
            Param::CanTimeout => ParamValue::CanTimeout(robstride::CanTimeout::OFF),
            Param::LimitTorque => ParamValue::NewtonMeters(caps.torque_max),
            Param::LimitSpd => ParamValue::RadPerSec(caps.speed_max),
            Param::LimitCur => ParamValue::Amps(caps.current_max),
            // The bench supply (skeleton `power.source: bench_24v`).
            Param::Vbus => ParamValue::Volts(lit(Volts::new(24.0))),
            Param::IqRef | Param::Iqf => ParamValue::Amps(lit(Amps::new(0.0))),
            Param::SpdRef | Param::MechVel | Param::VelMax => {
                ParamValue::RadPerSec(lit(RadPerSec::new(0.0)))
            }
            Param::LocRef | Param::MechPos | Param::AddOffset => {
                ParamValue::Radians(lit(Radians::new(0.0)))
            }
            Param::AccRad | Param::AccSet | Param::DccSet => {
                ParamValue::RadPerSecSq(lit(RadPerSecSq::new(0.0)))
            }
            Param::CurKp
            | Param::CurKi
            | Param::CurFiltGain
            | Param::LocKp
            | Param::SpdKp
            | Param::SpdKi
            | Param::SpdFiltGain => ParamValue::Gain(lit(Gain::new(0.0))),
        };
        (param, value)
    })
}

/// A unit value from a finite literal.
#[expect(
    clippy::expect_used,
    reason = "called only with finite literals, which every unit accepts"
)]
fn lit<T>(value: Option<T>) -> T {
    value.expect("a finite literal")
}

/// `SplitMix64`: small, seeded, and the same on every machine, so a sim run replays exactly.
#[derive(Debug)]
struct Rng(u64);

impl Rng {
    fn next(&mut self) -> u64 {
        self.0 = self.0.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut z = self.0;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        z ^ (z >> 31)
    }

    /// A span between `lo` and `hi` microseconds, inclusive.
    fn between(&mut self, (lo, hi): (u64, u64)) -> Duration {
        Duration::from_micros(lo + self.next() % (hi - lo + 1))
    }
}
