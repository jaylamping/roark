# Bench procedure conventions

**Status:** proposed for Joey's review, 2026-11-08.

Anything that sends Enable, motion, Set Zero, set-ID or a parameter write to a **real** drive is a bench procedure. Who may run
one is set by PLAN's [Real hardware rule](../PLAN.md#real-hardware-rule): Joey present and has said go for that session.
The limits that apply on the bench are in [PLAN "Rules that hold for every item"](../PLAN.md#rules-that-hold-for-every-item)
and the per-item sections. This page is **how a procedure is written, run and recorded**, so every session on real hardware
is safe, repeatable and replayable (tenet 6).

[testing.md rule 8](testing.md#rule-8-the-bench-is-not-a-test-suite) says why these are never `cargo test`.

## 1. A procedure is written down before it runs

Each procedure is a short Markdown page plus the plan file `robot-cli` (or the test-stand runner) executes. The page has these
sections, in this order:

| Section | What it says |
|---|---|
| Purpose | One line: what question this answers or what it commissions, and which PLAN item asks for it |
| Hardware | Which drives, on which bus, mounted how (loose, test stand, in the arm), what's attached to the output |
| Preconditions | The checklist below, plus anything specific |
| Limits | Torque, speed and position limits for this run and where each number comes from. Never above the skeleton's caps |
| Steps | Numbered. Each step that moves anything says what should happen and what makes you stop |
| Stop conditions | What the software stops on (rule IDs from [safety.md](safety.md)) and what the operator stops on (noise, smell, heat, contact) |
| Data | What's logged, and the script that judges pass or fail from the log |
| After | What gets recorded where (section 4), and the state the hardware is left in |

**Why:** a written procedure is reviewed when everyone is calm, not invented at the bench. It also lets an agent prepare the
run and judge the result without improvising on hardware.

## 2. Standard preconditions

Every procedure's checklist starts with these (PLAN holds the numbers; check them there):

- [ ] Joey present and has said go for this session.
- [ ] The same plan file passed on `vcan` against `sim-drive`, with the same commit and skeleton, today.
- [ ] Physical E-stop in reach and tested (press, confirm motor power drops, release).
- [ ] Supply and fuse as PLAN says for this stage.
- [ ] Mechanical setup as the procedure says; foam pad under anything that can drop; nothing in the swept volume.
- [ ] Preflight passes for every named joint (PLAN item 6).
- [ ] Session logging is recording (MCAP and `candump`), and the session ID is noted.

## 3. Running it

- **Start small.** A joint's first ever motion is one joint, attended, at reduced limits, before any multi-joint run.
- **Run the plan file, not hand-typed commands.** Ad-hoc commands on a real drive are for diagnosis with the drive disabled
  (reads, scans). Anything that moves goes in a plan file first.
- **Don't edit the procedure or plan mid-session.** If something needs changing, stop, change it, re-run on `vcan`, then
  resume. **Why:** a tweak made at the bench skips every review that made the procedure safe.
- **A stop is information, not an obstacle.** After any software stop or E-stop, find out why from the log before running
  again. Never loosen a limit or a rule to get past one ([safety.md section 7](safety.md#7-changing-a-rule)).
- **One operator action per step,** logged as an event: start, pause, stop, clear, with who did it.

## 4. What the runner enforces

The procedure runner (`robot-cli` or the test-stand runner) makes the rules above mechanical:

- **It refuses to start without an expected build.** The plan file names the git commit and skeleton hash it was dry-run
  with; the runner compares them with what's running and refuses on a mismatch.
- **Steps that move anything need an explicit flag or confirm** (for example `--allow-motion`), separate from starting the
  procedure. Reads and scans don't.
- **Every step has a timeout,** and a timeout fails the run naming the step and what it was waiting for. Nothing waits forever.
- **The result is `PASS` or `FAIL` per step and overall,** written with the evidence (log, plan, versions, operator notes) to
  one folder per session.

**Why:** PX4's bench-test tool works exactly this way (named timeouts, PASS/FAIL, an evidence folder with the firmware hash, and
a separate `--allow-arming` for the one step that can spin motors). Rules in a doc get skipped when people are tired; rules in
the runner don't.

## 5. Recording results

- **Every session is logged with:** git commit, skeleton file hash, procedure name, plan file, operator, the hardware setup,
  and the result. The binaries stamp the commit automatically ([architecture.md section 8](architecture.md#8-observability-is-part-of-the-design)).
- **Numbers that come out of a session** (a measured scale, a fitted friction, a verified direction) carry the session ID as
  their source when they land in the skeleton or `dynamics.yaml` ([skeleton.md](skeleton.md) section 2).
- **Hardware facts learned on the bench** (a zero that persists, a cap that's lower than planned) go to the hardware side for
  STATUS.md, so the fact lives in one place.
- **Failures are recorded too,** with the log. A failure on the bench is the most valuable data we get, and the first input to
  a `Guards: bug` test ([testing.md rule 7](testing.md#rule-7-a-bug-gets-its-test-before-its-fix)).

## 6. Agents and the bench

- Agents write procedures and plan files, run them on `vcan`, and judge logs. They don't start a run on real hardware unless
  Joey has said go for that session (PLAN's Real hardware rule and "Open with Joey" item 5 for enable and clear).
- An agent never uses a tool that stops the runtime and opens the bus itself (PLAN: the legacy `marengo-pi-mcp` tools).
- An agent asked to "just try it" on real hardware without a written procedure writes the procedure first.

## Sources

- PX4 bench testing (named timeouts, PASS/FAIL, evidence folder, `--allow-arming`):
  https://github.com/PX4/PX4-Autopilot/blob/main/docs/en/test_and_ci/bench_testing.md
- PX4 test cards (a preflight section with expected parameter values, then checkbox steps):
  https://github.com/PX4/PX4-Autopilot/blob/main/docs/en/test_cards/mc_04_failsafe_testing.md
- ArduPilot bug reports ("facts only", logs attached): https://github.com/ArduPilot/ardupilot/blob/master/.github/CONTRIBUTING.md
