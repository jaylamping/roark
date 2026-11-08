//! The sim suite (testing.md, "Where tests live"): tests that put frames on `vcan` against `sim-drive`, the same way the
//! runtime runs. Its tests are in `tests/`; this library is empty.
//!
//! Must never: open an interface without checking it is `vcan` first (`sim_drive::ensure_vcan`).
//! Runs with `scripts/sim.sh` (nextest profile `sim`) on Linux with `vcan` `can0` to `can4` up; the portable test run
//! leaves it out.
