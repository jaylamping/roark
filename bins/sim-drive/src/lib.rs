//! Simulated RobStride drives on `vcan` (PLAN item 4), so the runtime, the bus layer and every stop rule run unchanged
//! against something that answers like the real drives before any real drive is enabled.
//!
//! Must never: open an interface that isn't `vcan` (a bus named `can1` may be the robot's real one), or be linked into
//! `runtime` (architecture.md section 1).
//! Talks to: `robstride` for every frame in and out (its drive side, `robstride::drive`), `skeleton` for which drives sit
//! on which bus, and `vcan` sockets.

mod sim;

pub use sim::SimDrive;

#[cfg(target_os = "linux")]
mod bus;

#[cfg(target_os = "linux")]
pub use bus::{NotVcan, ServeError, ensure_vcan, serve};
