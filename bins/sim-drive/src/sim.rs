//! One simulated drive: what it answers, when, and the windows in which it answers nothing. Sans-IO: frames in, frames
//! out, and the time passed in by the caller (testing.md rule 6).

use std::time::{Duration, Instant};

use robstride::drive::{self as wire, Command, DriveFrame, HostFrame};
use robstride::{
    Amps, Celsius, Damper, DeviceId, Drive, Feedback, Gain, Mode, NewtonMeters, Param, ParamValue,
    RadPerSec, RadPerSecSq, Radians, ReportInterval, Reporting, RunMode, StatusFaults, Uid, Volts,
    ZeroSta,
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
/// Frames waiting for their due time. A drive has at most one reply and one report in flight, so 8 is ample; a full
/// outbox drops the frame and counts it.
const OUTBOX: usize = 8;

/// One simulated RobStride drive.
#[derive(Debug)]
pub struct SimDrive {
    drive: Drive,
    uid: Uid,
    mode: Mode,
    params: [(Param, ParamValue); Param::ALL.len()],
    position: Radians,
    /// The next active report, while reporting is on.
    next_report: Option<Instant>,
    last_command: Option<Instant>,
    /// When an enable reaches Run.
    run_at: Option<Instant>,
    /// Windows in which every frame is dropped: post-Disable silence, then the Set Zero blackout.
    silence: Option<(Instant, Instant)>,
    blackout: Option<(Instant, Instant)>,
    outbox: [Option<(Instant, DriveFrame)>; OUTBOX],
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
            position: lit(Radians::new(0.0)),
            next_report: None,
            last_command: None,
            run_at: None,
            silence: None,
            blackout: None,
            outbox: [None; OUTBOX],
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

    /// A host frame arrives at `now`. Frames for other drives, and frames inside a silence window, change nothing.
    pub fn receive(&mut self, now: Instant, frame: HostFrame) {
        if frame.target != self.id() {
            return;
        }
        self.advance(now);
        if in_window(self.silence, now) || in_window(self.blackout, now) {
            return;
        }
        self.last_command = Some(now);
        match frame.command {
            Command::GetId => self.send(now, Some(wire::identity(self.id(), self.uid))),
            // The plant holds position: an MIT target moves nothing until a test needs motion.
            Command::Mit(_) => self.send(now, self.status(self.mode)),
            Command::Enable => match (self.mode, self.run_at) {
                (Mode::Run, _) | (_, Some(_)) => self.send(now, self.status(self.mode)),
                (Mode::Reset | Mode::Calibration, None) => {
                    let at = now + self.rng.between(ENABLE_DELAY_US);
                    self.run_at = Some(at);
                    self.send(at, self.status(Mode::Run));
                }
            },
            Command::Disable | Command::FaultClear => {
                self.mode = Mode::Reset;
                self.run_at = None;
                self.send(now, self.status(Mode::Reset));
                self.silence = Some((now, now + self.rng.between(DISABLE_SILENCE_US)));
            }
            Command::SetZero => {
                self.position = lit(Radians::new(0.0));
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
                if let Some(slot) = self.params.iter_mut().find(|(p, _)| *p == param) {
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

    /// The next frame due by `now`, earliest first.
    pub fn pop_due(&mut self, now: Instant) -> Option<DriveFrame> {
        self.advance(now);
        let slot = self
            .outbox
            .iter_mut()
            .filter(|s| s.is_some_and(|(due, _)| due <= now))
            .min_by_key(|s| s.map(|(due, _)| due))?;
        slot.take().map(|(_, frame)| frame)
    }

    /// When something next happens without a frame arriving: a reply or report falls due, or an enable reaches Run.
    /// The caller waits at most until then.
    #[must_use]
    pub fn next_event(&self) -> Option<Instant> {
        let due = self.outbox.iter().flatten().map(|(due, _)| *due);
        due.chain(self.next_report)
            .chain(self.run_at)
            .chain(self.timeout_at())
            .min()
    }

    /// Power off and on: Reset, every parameter back to its default (`canTimeout` 0), reporting off, nothing in flight
    /// (PLAN item 4).
    pub fn power_cycle(&mut self) {
        *self = Self {
            rng: Rng(self.rng.next()),
            dropped: self.dropped,
            ..Self::new(self.drive, self.uid, 0)
        };
    }

    /// Bring the drive's state up to `now`: an enable reaching Run, `canTimeout` firing, reports falling due.
    fn advance(&mut self, now: Instant) {
        if self.run_at.is_some_and(|at| at <= now) {
            self.run_at = None;
            self.mode = Mode::Run;
        }
        if self.timeout_at().is_some_and(|at| at <= now) {
            self.mode = Mode::Reset;
        }
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
        Feedback {
            position: self.position,
            velocity: lit(RadPerSec::new(0.0)),
            torque: lit(NewtonMeters::new(0.0)),
            temperature: lit(Celsius::new(TEMPERATURE_C)),
        }
    }

    /// A type-2 status in `mode`, or `None` for a model the codec can't encode a status for.
    fn status(&self, mode: Mode) -> Option<DriveFrame> {
        wire::status(self.drive, mode, StatusFaults::default(), &self.feedback()).ok()
    }

    fn report(&self) -> Option<DriveFrame> {
        wire::report(
            self.drive,
            self.mode,
            StatusFaults::default(),
            &self.feedback(),
        )
        .ok()
    }

    /// Queue `frame` to go out at `due`; a frame that can't be built or queued is dropped and counted.
    fn send(&mut self, due: Instant, frame: Option<DriveFrame>) {
        let free = self.outbox.iter_mut().find(|s| s.is_none());
        match (frame, free) {
            (Some(frame), Some(slot)) => *slot = Some((due, frame)),
            (None, _) | (Some(_), None) => self.dropped += 1,
        }
    }
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
