//! Reading one joint, and the checks that need only that joint: caps inside the model's range, soft limits inside hard
//! limits, and the hard window inside one turn of the drive's power-on reading (PLAN item 1, "Loader refuses").

use robstride::{Amps, DeviceId, Model, NewtonMeters, RadPerSec, Radians};

use crate::commissioning::Caps;
use crate::error::ProblemKind;
use crate::read::{Fields, Reader, integer, number, plain, positive, range, text};
use crate::types::{BusName, Direction, Joint, JointName, Uid, Window};
use crate::yaml::Node;

/// One joint entry as read: the whole joint if every field parsed, the fields the cross-joint checks need each on
/// its own (so one broken field doesn't hide a duplicate name, address or budget share), and the lines to report at.
/// Outer `None` on a field means it didn't parse and was reported.
#[expect(
    clippy::option_option,
    reason = "outer None is a reported problem, inner None is a written `null`"
)]
pub(crate) struct Site {
    pub(crate) joint: Option<Joint>,
    pub(crate) name: Option<JointName>,
    pub(crate) bus: Option<Option<BusName>>,
    pub(crate) id: Option<DeviceId>,
    /// The current it is enabled at, for the budget: `Joint::caps`'s rule (`Caps::enabled_at`), even when a field
    /// didn't parse. Without a model there is no rule, so its written cap, or 0 A if null or unparsed.
    pub(crate) current_a: f64,
    pub(crate) path: String,
    pub(crate) line: usize,
    pub(crate) bus_line: usize,
    pub(crate) id_line: usize,
}

/// The fields the single-joint checks read, each as parsed: outer `None` is a reported problem, inner `None` a `null`.
#[expect(
    clippy::option_option,
    reason = "outer None is a reported problem, inner None is a written `null`"
)]
struct Checked {
    actuator: Option<Model>,
    direction: Option<Option<Direction>>,
    zero_rad: Option<Option<Radians>>,
    hard_rad: Option<Option<Window<Radians>>>,
    soft_rad: Option<Option<Window<Radians>>>,
    torque_cap_nm: Option<Option<NewtonMeters>>,
    current_cap_a: Option<Option<Amps>>,
    speed_cap_rad_s: Option<Option<RadPerSec>>,
}

/// `None` only when the entry isn't a mapping at all.
pub(crate) fn read_joint(
    r: &mut Reader,
    node: &Node,
    limb_path: &str,
    index: usize,
) -> Option<Site> {
    let mut f = r.fields(node, &format!("{limb_path}[{index}]"))?;
    let name = r.required(&mut f, "name", joint_name);
    if let Some(name) = &name {
        f.path = format!("{limb_path}.{name}");
    }
    let actuator = r.required(&mut f, "actuator", |n| {
        let t = text(n)?;
        Model::from_name(t).map_err(|_| ProblemKind::UnknownActuator(t.to_owned()))
    });
    let bus = r.nullable(&mut f, "bus", bus_name);
    let id = r.required(&mut f, "id", |n| {
        DeviceId::new(integer(n)?).map_err(|_| ProblemKind::OutOfRange("1 to 127"))
    });
    let uid = r.nullable(&mut f, "uid", uid);
    let direction = r.nullable(&mut f, "direction", direction);
    let zero_rad = r.nullable(&mut f, "zero_rad", |n| {
        Radians::new(number(n)?).ok_or(ProblemKind::NonFinite)
    });
    let reference_pose = r.nullable(&mut f, "reference_pose", |n| text(n).map(str::to_owned));
    let hard_rad = r.nullable(&mut f, "hard_rad", window);
    let soft_rad = r.nullable(&mut f, "soft_rad", window);
    let torque_cap_nm = r.nullable(&mut f, "torque_cap_nm", positive(NewtonMeters::new));
    let current_cap_a = r.nullable(&mut f, "current_cap_a", positive(Amps::new));
    let speed_cap_rad_s = r.nullable(&mut f, "speed_cap_rad_s", positive(RadPerSec::new));

    let checked = Checked {
        actuator,
        direction,
        zero_rad,
        hard_rad,
        soft_rad,
        torque_cap_nm,
        current_cap_a,
        speed_cap_rad_s,
    };
    check_joint(r, &f, &checked);
    let joint = (|| {
        Some(Joint {
            name: name.clone()?,
            actuator: actuator?,
            bus: bus.clone()?,
            id: id?,
            uid: uid?,
            direction: direction?,
            zero_rad: zero_rad?,
            reference_pose: reference_pose?,
            hard_rad: hard_rad?,
            soft_rad: soft_rad?,
            torque_cap_nm: torque_cap_nm?,
            current_cap_a: current_cap_a?,
            speed_cap_rad_s: speed_cap_rad_s?,
        })
    })();
    let current_a = actuator.map_or_else(
        || current_cap_a.flatten().map_or(0.0, Amps::get),
        |model| {
            Caps::enabled_at(
                model,
                [
                    direction.map(|v| v.map(drop)),
                    zero_rad.map(|v| v.map(drop)),
                    hard_rad.map(|v| v.map(drop)),
                ],
                (torque_cap_nm, current_cap_a, speed_cap_rad_s),
            )
            .current
            .get()
        },
    );
    let site = Site {
        joint,
        name,
        bus,
        id,
        current_a,
        path: f.path.clone(),
        line: f.line,
        bus_line: f.line_of("bus"),
        id_line: f.line_of("id"),
    };
    f.finish(r);
    Some(site)
}

/// Each check runs when the fields it reads parsed, whatever else in the joint is broken (skeleton.md section 5).
fn check_joint(r: &mut Reader, f: &Fields<'_>, j: &Checked) {
    if let Some(model) = j.actuator {
        let max = model.ranges();
        let caps = [
            (
                "torque_cap_nm",
                j.torque_cap_nm.flatten().map(NewtonMeters::get),
                max.torque_max.get(),
            ),
            (
                "current_cap_a",
                j.current_cap_a.flatten().map(Amps::get),
                max.current_max.get(),
            ),
            (
                "speed_cap_rad_s",
                j.speed_cap_rad_s.flatten().map(RadPerSec::get),
                max.speed_max.get(),
            ),
        ];
        for (key, cap, max) in caps {
            if cap.is_some_and(|c| c > max) {
                r.report(
                    f.line_of(key),
                    f.path_of(key),
                    ProblemKind::CapAboveModel { max },
                );
            }
        }
    }
    let hard = j.hard_rad.flatten();
    if let (Some(hard), Some(soft)) = (hard, j.soft_rad.flatten())
        && (soft.lower < hard.lower || soft.upper > hard.upper)
    {
        r.report(
            f.line_of("soft_rad"),
            f.path_of("soft_rad"),
            ProblemKind::SoftOutsideHard,
        );
    }
    // A direction or zero that didn't parse is treated as unknown: only the window's width is checked.
    if let (Some(model), Some(hard)) = (j.actuator, hard)
        && let Some(kind) =
            outside_power_on_turn(model, hard, j.direction.flatten(), j.zero_rad.flatten())
    {
        r.report(f.line_of("hard_rad"), f.path_of("hard_rad"), kind);
    }
}

/// The drive reports its output position inside one turn after power-on (manual §4.2.2). A hard window must fit inside
/// that turn, or a reading after power-up can't say which turn the joint is in. Without a zero and a direction only
/// the width can be checked; with them, the window seen from the drive, `zero_rad + direction × q_joint` (the inverse
/// of PLAN item 1's conversion), must lie in `[start, start + turn)`.
fn outside_power_on_turn(
    model: Model,
    hard: Window<Radians>,
    direction: Option<Direction>,
    zero: Option<Radians>,
) -> Option<ProblemKind> {
    let (start, turn) = model.power_on_window();
    let (start, turn) = (start.get(), turn.get());
    if hard.upper.get() - hard.lower.get() >= turn {
        return Some(ProblemKind::HardWindowTooWide { max_rad: turn });
    }
    let (direction, zero) = (direction?, zero?);
    let a = zero.get() + direction.sign() * hard.lower.get();
    let b = zero.get() + direction.sign() * hard.upper.get();
    let (low, high) = if a <= b { (a, b) } else { (b, a) };
    (low < start || high >= start + turn).then_some(ProblemKind::HardWindowOutsidePowerOnTurn {
        drive_rad: [low, high],
        turn_rad: [start, start + turn],
    })
}

fn window(node: &Node) -> Result<Window<Radians>, ProblemKind> {
    range(Radians::new)(node).map(|(lower, upper)| Window { lower, upper })
}

fn joint_name(node: &Node) -> Result<JointName, ProblemKind> {
    let t = text(node)?;
    let mut bytes = t.bytes();
    let ok = bytes.next().is_some_and(|b| b.is_ascii_lowercase())
        && bytes.all(|b| b.is_ascii_lowercase() || b.is_ascii_digit() || b == b'_');
    if ok {
        Ok(JointName(t.to_owned()))
    } else {
        Err(ProblemKind::Expected("a snake_case joint name"))
    }
}

pub(crate) fn bus_name(node: &Node) -> Result<BusName, ProblemKind> {
    let t = text(node)?;
    // 15 bytes: IFNAMSIZ (16) less the terminating NUL, linux/if.h.
    let ok = (1..=15).contains(&t.len())
        && t.bytes()
            .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit());
    if ok {
        Ok(BusName(t.to_owned()))
    } else {
        Err(ProblemKind::Expected("an interface name such as can1"))
    }
}

fn direction(node: &Node) -> Result<Direction, ProblemKind> {
    match plain(node) {
        Some("1" | "+1") => Ok(Direction::Same),
        Some("-1") => Ok(Direction::Reversed),
        Some(_) | None => Err(ProblemKind::Expected("1 or -1, unquoted")),
    }
}

fn uid(node: &Node) -> Result<Uid, ProblemKind> {
    let t = text(node)?;
    let hex = t.strip_prefix("0x").unwrap_or(t);
    let mut out = [0_u8; 8];
    // Checked digit by digit: `from_str_radix` alone would accept a sign, so "+1+2+3+4+5+6+7+8" would load.
    let ok = hex.len() == 16
        && hex.bytes().all(|b| b.is_ascii_hexdigit())
        && out.iter_mut().enumerate().all(|(i, byte)| {
            hex.get(2 * i..2 * i + 2)
                .and_then(|pair| u8::from_str_radix(pair, 16).ok())
                .map(|v| *byte = v)
                .is_some()
        });
    if ok {
        Ok(Uid(out))
    } else {
        Err(ProblemKind::Expected("16 hex digits"))
    }
}
