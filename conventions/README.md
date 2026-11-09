# Conventions

How code, config, tests and procedures are written and reviewed in this repo. They apply the [tenets](../TENETS.md) to
day-to-day work. Values (IDs, limits, thresholds, sequences) are not kept here: they live in [PLAN.md](../PLAN.md),
`config/skeleton.yaml` and [STATUS.md](https://github.com/jaylamping/marengo/blob/main/hardware/STATUS.md), and these pages
link to them.

Read the page for the area you're touching before you write code. New to CAN? Start with
[docs/can-primer.md](../docs/can-primer.md).

| Page | Covers |
|---|---|
| [architecture.md](architecture.md) | The map: processes, crates, seams, data flows, what changes the shape |
| [rust.md](rust.md) | How the Rust is written: lints, types, errors, the realtime loop, dependencies, CI gates |
| [can.md](can.md) | How the CAN layer and the RobStride codec are written |
| [safety.md](safety.md) | How safety rules are written, proven, changed and reviewed |
| [units-and-frames.md](units-and-frames.md) | Units, signs, frames, limits and names |
| [skeleton.md](skeleton.md) | How `config/skeleton.yaml` is written, changed and reviewed |
| [logging.md](logging.md) | Recordings, log lines, events and metrics: names, shapes and how they're used |
| [testing.md](testing.md) | When a test is worth writing, and the tools for each language |
| [bench.md](bench.md) | How procedures on real drives are written, run and recorded |
| [deploy.md](deploy.md) | The Pi: storage, file layout, deploying, services, realtime tuning, the OS |
| [remote-access.md](remote-access.md) | Connecting over Tailscale: tags, policy in git, SSH, agent keys, the UI, offline fallback |
| [typescript.md](typescript.md) | The operator UI and other TypeScript clients |
| [git.md](git.md) | Branches, commits, pull requests and review |
| [cad.md](cad.md) | CAD files in git: what is versioned, Git LFS, the size limit, folder layout and names |
| [part-lifecycle.md](part-lifecycle.md) | Printed parts: the requirements spec, the pre-print gate and the print log |
| [joey-pc.md](joey-pc.md) | Sharing Joey-PC between threads: worktrees, claims, heartbeats, the FEA queue, what needs Joey at the keyboard |
| [docs.md](docs.md) | Which doc holds what, and how docs are written and kept true |

Each page explains the reason behind its rules. If a rule is wrong, change it on purpose in a PR, with the reason. Don't work
around it.
