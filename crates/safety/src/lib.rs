#![doc = include_str!("../README.md")]
#![warn(clippy::wildcard_enum_match_arm, clippy::as_conversions)]

mod enable;
mod preflight;
mod refusal;
mod rule;
mod state;

pub use enable::{EnableFailure, Enabling, Next, RUN_WITHIN_NS};
pub use preflight::{
    ANSWER_WITHIN_NS, Exchange, Preflight, PreflightPassed, Register, Step, Target,
};
pub use refusal::{CapKind, JointFact, Refusal, Unanswered};
pub use rule::{Cause, RuleId};
pub use state::{DriveEvent, DriveState, LimbEvent, LimbState};
