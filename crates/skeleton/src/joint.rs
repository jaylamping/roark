//! Reading one joint, and the checks that need only that joint: caps inside the model's range, soft limits inside hard
//! limits, and the hard window clear of the drive's power-on wrap point (PLAN item 1, "Loader refuses").

use robstride::{Amps, DeviceId, Model, NewtonMeters, RadPerSec, Radians};

use crate::error::ProblemKind;
use crate::read::{Fields, Reader, integer, number, positive, range, text};
use crate::types::{BusName, Direction, Joint, JointName, Uid, Window};
use crate::yaml::Node;

/// A joint and the lines its cross-joint checks report against.
pub(crate) struct Site {
    pub(crate) joint: Joint,
    pub(crate) path: String,
    pub(crate) line: usize,
}

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

    let joint = (|| {
        Some(Joint {
            name: name?,
            actuator: actuator?,
            bus: bus?,
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
    if let Some(joint) = &joint {
        check_joint(r, &f, joint);
    }
    let (path, line) = (f.path.clone(), f.line);
    f.finish(r);
    joint.map(|joint| Site { joint, path, line })
}

fn check_joint(r: &mut Reader, f: &Fields<'_>, j: &Joint) {
    let line = f.line;
    let max = j.actuator.ranges();
    let caps = [
        (
            "torque_cap_nm",
            j.torque_cap_nm.map(NewtonMeters::get),
            max.torque_max.get(),
        ),
        (
            "current_cap_a",
            j.current_cap_a.map(Amps::get),
            max.current_max.get(),
        ),
        (
            "speed_cap_rad_s",
            j.speed_cap_rad_s.map(RadPerSec::get),
            max.speed_max.get(),
        ),
    ];
    for (key, cap, max) in caps {
        if cap.is_some_and(|c| c > max) {
            r.report(line, f.path_of(key), ProblemKind::CapAboveModel { max });
        }
    }
    if let (Some(hard), Some(soft)) = (j.hard_rad, j.soft_rad)
        && (soft.lower < hard.lower || soft.upper > hard.upper)
    {
        r.report(line, f.path_of("soft_rad"), ProblemKind::SoftOutsideHard);
    }
    if let (Some(hard), Some(direction), Some(zero)) = (j.hard_rad, j.direction, j.zero_rad)
        && let Some(wrap_rad) = wrap_inside(j.actuator, hard, direction, zero)
    {
        r.report(
            line,
            f.path_of("hard_rad"),
            ProblemKind::HardWindowContainsWrap { wrap_rad },
        );
    }
}

/// The first drive position inside the hard window (ends included) where the drive's power-on reading folds over, if
/// any. Drive position is `zero_rad + direction × q_joint`, the inverse of PLAN item 1's conversion.
fn wrap_inside(
    model: Model,
    hard: Window<Radians>,
    direction: Direction,
    zero: Radians,
) -> Option<f64> {
    let (start, length) = model.power_on_window();
    let (start, length) = (start.get(), length.get());
    let a = zero.get() + direction.sign() * hard.lower.get();
    let b = zero.get() + direction.sign() * hard.upper.get();
    let (low, high) = if a <= b { (a, b) } else { (b, a) };
    let fold = start + ((low - start) / length).ceil() * length;
    (fold <= high).then_some(fold)
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
    match text(node) {
        Ok("1" | "+1") => Ok(Direction::Same),
        Ok("-1") => Ok(Direction::Reversed),
        Ok(_) | Err(_) => Err(ProblemKind::Expected("1 or -1")),
    }
}

fn uid(node: &Node) -> Result<Uid, ProblemKind> {
    let t = text(node)?;
    let hex = t.strip_prefix("0x").unwrap_or(t);
    let mut out = [0_u8; 8];
    let ok = hex.len() == 16
        && hex.is_ascii()
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
