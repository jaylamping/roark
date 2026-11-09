# Read first

This repo is the robot's software, built fresh for the **whole robot**. Every change is for the finished robot, never for the
limb currently on the bench (tenet 0).

1. [TENETS.md](TENETS.md): the rules every change is judged by.
2. [PLAN.md](PLAN.md): what to build, in order. Milestone 1 is the left arm online.
3. [conventions/](conventions/): read the page for the area you touch before writing code.
   [architecture.md](conventions/architecture.md) is the map of processes, crates and seams;
   [rust.md](conventions/rust.md) is how the Rust is written; [testing.md](conventions/testing.md) is what earns a test.
4. The reference repo, [jaylamping/marengo](https://github.com/jaylamping/marengo), is **read-only from here**. It holds the
   hardware (designs, electrical, [STATUS.md](https://github.com/jaylamping/marengo/blob/main/hardware/STATUS.md), RobStride
   manuals) and the legacy software. Mine the legacy code for facts and bench lessons
   ([RECONCILIATION.md](https://github.com/jaylamping/marengo/blob/main/review/sw-foundation-20261108/RECONCILIATION.md)),
   never as patterns. Nothing in this repo depends on or copies its structure.
   CAD files are the exception that moves here: they live in [cad/](cad/), brought over from marengo only when work needs
   them ([conventions/cad.md](conventions/cad.md)).
5. **Linux work** (`vcan`, SocketCAN, the sim suite, anything macOS can't run) goes to the dev box: run
   `scripts/devbox.sh doctor`, then `scripts/devbox.sh run <command>`. How it works and how to fix it: [docs/dev-box.md](docs/dev-box.md).

Work on branches and open PRs. No tests written just for coverage.

**Real hardware:** no Enable, motion, Set Zero, set-ID or parameter write to a real drive unless Joey is present and has
said go for that session ([PLAN.md, Real hardware rule](PLAN.md#real-hardware-rule)). `vcan` is always fine.

Commits and PR descriptions describe the change only ([conventions/git.md](conventions/git.md) section 2): no AI attribution
(no `Co-Authored-By` for AI, no session links, no "Generated with" footers), no "who asked", no retelling of the chat.
