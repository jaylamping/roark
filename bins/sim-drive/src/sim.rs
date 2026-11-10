//! One simulated drive: what it answers, when, and the windows in which it answers nothing. Sans-IO: frames in, frames
//! out, and the time passed in by the caller (testing.md rule 6).

use std::time::{Duration, Instant};

use robstride::drive::{self as wire, Command, DriveFrame, HostFrame};

use crate::fault::{Active, Fault, FaultRefused, Injected, Plan, Trigger, flag, flagged};
use crate::outbox::{OUTBOX, Outbox};
use crate::plant::{Limits, Motion, Plant};
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
/// The most events besides reports that one step of the drive can meet: each scheduled fault fires once
/// ([`crate::FAULT_PLAN`]); Run is reached once without a fault (the drive is in Run already, or reaches it from the one
/// Enable pending, which only a frame sets and only out of Run) and once per `Mode(Run)` fault; and each stay in Run
/// times out at most once. So `FAULT_PLAN` faults, one Run, and `FAULT_PLAN + 1` timeouts.
const STEP_EVENTS: usize = 2 * crate::FAULT_PLAN + 2;
/// The temperature every status reports. A sim value, not a measurement.
const TEMPERATURE_C: f64 = 25.0;

/// One simulated RobStride drive.
#[derive(Debug)]
pub struct SimDrive {
    drive: Drive,
    uid: Uid,
    mode: Mode,
    params: [(Param, ParamValue); Param::ALL.len()],
    plant: Plant,
    /// Injected faults in effect now, but for the transport faults (the outbox's); a reboot clears them.
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
    outbox: Outbox,
    /// The latest time the drive has been brought up to: its one clock, the plant's too.
    stepped: Option<Instant>,
    rng: Rng,
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
            plant: Plant::resting_at(lit(Radians::new(0.0))),
            active: Active::default(),
            plan: Plan::default(),
            next_report: None,
            last_command: None,
            run_at: None,
            silence: None,
            blackout: None,
            outbox: Outbox::EMPTY,
            stepped: None,
            rng: Rng(seed),
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
        self.outbox.dropped()
    }

    /// Inject `fault` at `now`, and record it: the drive is brought up to just before `now`, the fault applied, then
    /// whatever falls due at `now` happens with the fault in effect.
    ///
    /// # Errors
    /// [`FaultRefused`] for a fault the drive can't honour, or a `now` the drive has already been stepped past; nothing
    /// is recorded then.
    pub fn inject(&mut self, now: Instant, fault: Fault) -> Result<(), FaultRefused> {
        self.check(fault)?;
        self.check_time(now)?;
        self.advance_to(now, false);
        self.apply(now, fault);
        self.advance(now);
        Ok(())
    }

    /// Schedule `fault` to fire on `trigger`.
    ///
    /// # Errors
    /// [`FaultRefused`] for a fault the drive can't honour, `OnMit(0)`, an `At` the drive has already been stepped
    /// past, or a full plan ([`crate::FAULT_PLAN`]).
    pub fn schedule(&mut self, trigger: Trigger, fault: Fault) -> Result<(), FaultRefused> {
        self.check(fault)?;
        if let Trigger::At(at) = trigger {
            self.check_time(at)?;
        }
        self.plan.schedule(trigger, fault)
    }

    /// Refuse a time the drive has already been stepped past: a fault can't take effect then any more.
    fn check_time(&self, at: Instant) -> Result<(), FaultRefused> {
        match self.stepped {
            Some(stepped) if at < stepped => Err(FaultRefused::Past),
            _ => Ok(()),
        }
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

    /// Injections the record had no room for because they weren't taken ([`crate::INJECTED_LOG`]).
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
                while let Some((at, fault)) = self.plan.due(now) {
                    self.apply(at, fault);
                }
                // A model whose MIT scales aren't settled has no command to take: the joint stays put.
                if self.mode == Mode::Run
                    && let Ok(command) = codes.command(self.drive.model())
                {
                    self.plant.command(command);
                }
                self.send(now, self.status());
            }
            Command::Enable => match (self.mode, self.run_at) {
                (Mode::Run, _) | (_, Some(_)) => self.send(now, self.status()),
                // The Run status is built when Run is reached (`advance`), with the faults in effect then.
                (Mode::Reset | Mode::Calibration, None) => {
                    self.run_at = Some(now + self.rng.between(ENABLE_DELAY_US));
                }
            },
            Command::Disable | Command::FaultClear => {
                self.set_mode(now, Mode::Reset);
                self.send(now, self.status());
                self.silence = Some((now, now + self.rng.between(DISABLE_SILENCE_US)));
            }
            Command::SetZero => {
                self.plant.set_position(lit(Radians::new(0.0)));
                self.send(now, self.status());
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
                    .read(param)
                    .and_then(|v| wire::param_value(self.id(), param, v).ok());
                self.send(
                    now,
                    Some(reply.unwrap_or_else(|| wire::param_refused(self.id(), param))),
                );
            }
            Command::ParamWrite { param, value } => {
                if !flagged(&self.active.ignored_writes, param)
                    && let Some(slot) = self.params.iter_mut().find(|(p, _)| *p == param)
                {
                    slot.1 = value;
                }
                self.send(now, self.status());
            }
            Command::Reporting(Reporting::On) => {
                self.next_report = self.report_interval().map(|i| now + i);
            }
            Command::Reporting(Reporting::Off) => self.next_report = None,
        }
    }

    /// The next frame gone out by `now`, earliest first. Injected transport faults apply to each frame as it falls due,
    /// so they reach frames already waiting and never one due before they took effect, however seldom the host reads: a
    /// silent drive sends nothing, a late one holds each frame once more by its lateness, lost frames go by count, and a
    /// doubled frame's second copy goes out with the first and isn't doubled again.
    pub fn pop_due(&mut self, now: Instant) -> Option<DriveFrame> {
        self.advance(now);
        self.outbox.pop(now)
    }

    /// When something next happens without a frame arriving: a reply or report falls due, an enable reaches Run,
    /// `canTimeout` fires, or a scheduled fault's time comes. The caller waits at most until then.
    #[must_use]
    pub fn next_event(&self) -> Option<Instant> {
        self.outbox
            .next_due()
            .into_iter()
            .chain(self.next_report)
            .chain(self.run_at)
            .chain(self.timeout_at())
            .chain(self.plan.next_at())
            .min()
    }

    /// Power off and on at `at`: Reset, every parameter back to its default (`canTimeout` 0), reporting off, every
    /// injected fault cleared (PLAN item 4). Frames due by `at` went out before the power went, as the transport faults
    /// in effect let them; the rest are lost. The joint stays where it is, and the fault plan and its record are the
    /// test's, so they stay too.
    fn reboot(&mut self, at: Instant) {
        self.outbox.power_off(at);
        *self = Self {
            rng: Rng(self.rng.next()),
            plant: self.plant.at_rest(),
            plan: self.plan,
            stepped: self.stepped,
            outbox: self.outbox,
            ..Self::new(self.drive, self.uid, 0)
        };
    }

    /// Bring the drive up to `now`, with everything due at `now` too.
    fn advance(&mut self, now: Instant) {
        self.advance_to(now, true);
    }

    /// Bring the drive's state up to `now`, each event at its own time, in time order, with the joint moving in
    /// between: a scheduled fault's time, an enable reaching Run (its status sent then), `canTimeout` firing, a report
    /// falling due (built with the joint as it is then); and the outbox settled up to each, so a transport fault reaches
    /// only frames due at or after its time. Tied events go in that order, so a fault due with Run shows in the Run
    /// status. Events at `now` itself happen only if `inclusive`.
    fn advance_to(&mut self, now: Instant, inclusive: bool) {
        // Other events are at most `STEP_EVENTS`. Reports go one at a time while the outbox has room, at most `OUTBOX` of them a step reaching it;
        // past that, the reports before the next other event are skipped in one go and counted, as the full outbox
        // would drop them. A report in the Set Zero blackout reaches nothing and takes no room, and there are at most
        // the blackout's length over the report interval, plus one, of those.
        let mut events = 0;
        let mut reports = 0;
        while let Some((at, event)) = self.next_due(now, inclusive, true) {
            self.outbox.settle(at, false);
            if matches!(event, Event::Report) {
                if let Some(interval) = self.report_interval()
                    && (reports >= OUTBOX || self.outbox.is_full())
                {
                    let until = self
                        .next_due(now, inclusive, false)
                        .map_or((now, inclusive), |(next, _)| (next, false));
                    self.skip_reports(at, interval, until);
                    continue;
                }
                if !in_window(self.blackout, at) {
                    reports += 1;
                }
            } else {
                events += 1;
                assert!(
                    events <= STEP_EVENTS,
                    "a step met more than {STEP_EVENTS} events besides reports"
                );
            }
            self.step_to(at);
            match event {
                Event::Fault => {
                    if let Some((_, fault)) = self.plan.due(at) {
                        self.apply(at, fault);
                    }
                }
                Event::Run => {
                    self.run_at = None;
                    self.mode = Mode::Run;
                    self.send(at, self.status());
                }
                Event::Timeout => self.set_mode(at, Mode::Reset),
                Event::Report => {
                    if !in_window(self.blackout, at) {
                        self.send(at, self.report());
                    }
                    self.next_report = self.report_interval().map(|i| at + i);
                }
            }
        }
        self.outbox.settle(now, inclusive);
        self.step_to(now);
    }

    /// Move the joint up to `at` and mark the drive stepped there. A time behind the last step moves nothing and leaves
    /// the mark where it is: the drive keeps one clock, and it only goes forward.
    fn step_to(&mut self, at: Instant) {
        let dt = self
            .stepped
            .map_or(Duration::ZERO, |s| at.saturating_duration_since(s));
        let limits = self.limits();
        self.plant.advance(dt, self.mode == Mode::Run, limits);
        self.stepped = Some(self.stepped.map_or(at, |s| s.max(at)));
    }

    /// Skip the reports every `interval` from `first` to before `until` (or at it, if inclusive): each one not in the
    /// Set Zero blackout is counted dropped, as a full outbox would drop it, and the next report falls after them.
    fn skip_reports(
        &mut self,
        first: Instant,
        interval: Duration,
        (until, inclusive): (Instant, bool),
    ) {
        let step = interval.as_nanos().max(1);
        // How many of the reports fall before `t`.
        let before = |t: Instant| -> u128 {
            t.checked_duration_since(first)
                .map_or(0, |d| d.as_nanos().div_ceil(step))
        };
        let count = match until.checked_duration_since(first) {
            Some(d) if inclusive => d.as_nanos() / step + 1,
            Some(_) => before(until),
            None => 0,
        };
        let silent = self.blackout.map_or(0, |(start, end)| {
            before(end).min(count) - before(start).min(count)
        });
        self.outbox
            .count_dropped(u64::try_from(count - silent).unwrap_or(u64::MAX));
        let skipped = u64::try_from(step * count).unwrap_or(u64::MAX);
        self.next_report = first.checked_add(Duration::from_nanos(skipped));
    }

    /// The earliest event due by `now` (before it, unless `inclusive`), and when, at the earliest the time last stepped to
    /// (a drive never stepped takes each at its own time); reports only if `reports`.
    fn next_due(&self, now: Instant, inclusive: bool, reports: bool) -> Option<(Instant, Event)> {
        let due = |at: Option<Instant>| {
            at.filter(|at| *at < now || (inclusive && *at == now))
                .map(|at| self.stepped.map_or(at, |stepped| at.max(stepped)))
        };
        [
            (due(self.plan.next_at()), Event::Fault),
            (due(self.run_at), Event::Run),
            (due(self.timeout_at()), Event::Timeout),
            (due(self.next_report.filter(|_| reports)), Event::Report),
        ]
        .into_iter()
        .filter_map(|(at, event)| Some((at?, event)))
        // `min_by_key` keeps the first of equals: the order above breaks ties.
        .min_by_key(|(at, _)| *at)
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

    /// The drive is in `mode` from `at`, whatever put it there. Any pending Enable is forgotten; leaving Run leaves the
    /// joint at rest, and reaching Run starts `canTimeout` counting from `at`.
    fn set_mode(&mut self, at: Instant, mode: Mode) {
        self.run_at = None;
        if mode != Mode::Run {
            self.plant = self.plant.at_rest();
        } else if self.mode != Mode::Run {
            self.last_command = Some(at);
        }
        self.mode = mode;
    }

    /// Put `fault` in effect, recorded at `at`.
    fn apply(&mut self, at: Instant, fault: Fault) {
        self.plan.record(Injected {
            at,
            device: self.id(),
            fault,
        });
        let (a, t) = (&mut self.active, &mut self.outbox.faults);
        match fault {
            Fault::Silent => t.silent = true,
            Fault::Late(by) => t.late = by,
            Fault::Drop(n) => t.drop = t.drop.saturating_add(n),
            Fault::Duplicate(n) => t.duplicate = t.duplicate.saturating_add(n),
            Fault::FaultBits(faults) => a.faults = faults,
            Fault::Temperature(c) => a.temperature = Some(c),
            Fault::IgnoreWrites(param) => flag(&mut a.ignored_writes, param),
            Fault::IgnoreDisables(n) => a.ignored_disables = a.ignored_disables.saturating_add(n),
            Fault::Mode(mode) => self.set_mode(at, mode),
            Fault::Param(param, value) => {
                flag(&mut a.injected_params, param);
                if let Some(slot) = self.params.iter_mut().find(|(p, _)| *p == param) {
                    slot.1 = value;
                }
            }
            Fault::Reboot => self.reboot(at),
        }
    }

    /// The joint's bounds: the caps written to the drive (a negative one, which only an injected register can hold,
    /// as zero), and what its MIT feedback can carry. The registers keep what was written, for read-back. A model whose
    /// MIT scales aren't settled has no status, so its joint never moves either.
    fn limits(&self) -> Limits {
        self.caps().unwrap_or_else(|| {
            let zero = lit(Radians::new(0.0));
            Limits {
                torque: lit(NewtonMeters::new(0.0)),
                speed: lit(RadPerSec::new(0.0)),
                position: (zero, zero),
            }
        })
    }

    /// The joint's bounds, or `None` for a model whose MIT scales aren't settled.
    fn caps(&self) -> Option<Limits> {
        let ranges = self.drive.model().ranges();
        let scales = self.drive.model().mit_scales().ok()?;
        let torque = match self.param(Param::LimitTorque) {
            Some(ParamValue::NewtonMeters(t)) => t,
            _ => ranges.torque_max,
        };
        let speed = match self.param(Param::LimitSpd) {
            Some(ParamValue::RadPerSec(v)) => v,
            _ => ranges.speed_max,
        };
        Some(Limits {
            torque: NewtonMeters::new(torque.get().max(0.0).min(scales.torque.max()))?,
            speed: RadPerSec::new(speed.get().max(0.0).min(scales.velocity.max()))?,
            position: (
                Radians::new(scales.position.min())?,
                Radians::new(scales.position.max())?,
            ),
        })
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

    /// What a read of `param` answers: the joint's position and speed as they are now, unless a value was injected;
    /// every other register as it holds.
    fn read(&self, param: Param) -> Option<ParamValue> {
        if flagged(&self.active.injected_params, param) {
            return self.param(param);
        }
        match param {
            Param::MechPos => Some(ParamValue::Radians(self.plant.position())),
            Param::MechVel => self.motion().map(|m| ParamValue::RadPerSec(m.velocity)),
            _ => self.param(param),
        }
    }

    /// The joint's velocity and torque now: zero out of Run. `None` if a value isn't finite.
    fn motion(&self) -> Option<Motion> {
        self.plant.motion(self.mode == Mode::Run, self.limits())
    }

    /// The joint as a status carries it, or `None` if a value isn't finite.
    fn feedback(&self) -> Option<Feedback> {
        let motion = self.motion()?;
        Some(Feedback {
            position: self.plant.position(),
            velocity: motion.velocity,
            torque: motion.torque,
            temperature: self
                .active
                .temperature
                .unwrap_or_else(|| lit(Celsius::new(TEMPERATURE_C))),
        })
    }

    /// A type-2 status in the drive's mode now, or `None` for a model the codec can't encode a status for.
    fn status(&self) -> Option<DriveFrame> {
        wire::status(self.drive, self.mode, self.active.faults, &self.feedback()?).ok()
    }

    fn report(&self) -> Option<DriveFrame> {
        wire::report(self.drive, self.mode, self.active.faults, &self.feedback()?).ok()
    }

    /// Queue `frame` to go out at `due`; a frame that can't be built or queued is dropped and counted.
    fn send(&mut self, due: Instant, frame: Option<DriveFrame>) {
        self.outbox.send(due, frame);
    }
}

/// What [`SimDrive::advance_to`] handles next, in the order ties go.
#[derive(Clone, Copy, Debug)]
enum Event {
    Fault,
    Run,
    Timeout,
    Report,
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
