# Read first

This repo is the robot's software, built fresh for the **whole robot**. Every change is for the finished robot, never for the
limb currently on the bench (tenet 0).

1. [TENETS.md](TENETS.md): the rules every change is judged by.
2. [PLAN.md](PLAN.md): what to build, in order. Milestone 1 is the left arm online.
3. The reference repo, [jaylamping/marengo](https://github.com/jaylamping/marengo), is **read-only from here**. It holds the
   hardware (designs, electrical, [STATUS.md](https://github.com/jaylamping/marengo/blob/main/hardware/STATUS.md), RobStride
   manuals) and the legacy software. Mine the legacy code for facts and bench lessons
   ([RECONCILIATION.md](https://github.com/jaylamping/marengo/blob/main/review/sw-foundation-20261108/RECONCILIATION.md)),
   never as patterns. Nothing in this repo depends on or copies its structure.

Work on branches and open PRs. No tests written just for coverage.

**Real hardware:** no Enable, motion, Set Zero, set-ID or parameter write to a real drive unless Joey is present and has
said go for that session ([PLAN.md, Real hardware rule](PLAN.md#real-hardware-rule)). `vcan` is always fine.
