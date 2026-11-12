# Safety code conventions

**Status:** proposed for Joey's review, 2026-11-08.

[Tenet 3](../TENETS.md#3-layered-safety-each-layer-with-a-job) sets the layers. The drive, limb and robot states, the rule
table (with what each rule protects and the failure it covers) and recovery are in
[PLAN item 6](../PLAN.md#6-safety-the-three-layers-tenet-3); the enable, stop and Set Zero sequences are in
[PLAN item 2](../PLAN.md#2-lift-the-hard-won-knowledge-first). This page is **how safety rules are written, changed and
reviewed in code**. There are no spare actuators, so this is the code held to the highest bar.

## 1. What makes something a safety rule

A safety rule is a row in PLAN item 6's table. To add one, it needs all of:

- **Protects:** a named piece of hardware (a drive, a gearbox, a printed part, the supply).
- **Failure covered:** a specific thing that goes wrong (Pi hangs, wrong sign, drive goes silent).
- **Layer:** the lowest layer that can enforce it. If the drive can enforce it (a timeout, a cap), the drive does, and the host
  only checks the drive's setting. **Why:** the drive layer holds even when the Pi crashes; host code doesn't.
- **Not already covered.** If another rule or layer already covers that failure for that hardware, the new rule goes
  (tenet 3: duplicated protection is complexity that hides bugs).

- **What it blocks.** Every refusal and stop also stops a test. The rule says which attended bench tests it can block,
  and it is built before the first test that needs it, not earlier (PLAN item 6, "Which rules a test waits for").
  **Why:** the last build's safeguards grew until the robot couldn't be tested at all (Joey, 2026-11-11). A review
  finding that asks for a new refusal has to name the motor or part it protects, like any other rule.

A rule that can't fill in those lines is not added. "Seems safer" is not a reason.

## 2. Each rule has a stable ID

Every rule gets a short ID such as `drive.can_timeout`, `host.silence`, `host.total_torque`, `host.temperature`. The same ID
appears in the PLAN table, the code, the test's `Guards:` line, every log event the rule emits, and the UI's fault display.

**Why:** when the arm stops at 2 a.m., the log line says `host.silence` and you can find the rule, its reason, its code and its
test with one search. It's the same idea as an error code in an API.

## 3. How a rule is written

- **Rules are plain functions** in the `safety` crate: they take the current state, the proposed command and the current time
  (passed in, per [architecture.md section 9](architecture.md#9-testing-seams)) and return a verdict. No I/O, no globals, no
  hidden state. **Why:** a pure function can be unit-tested exhaustively and reasoned about by reading it.
- **The verdict is an enum,** for example `Allow`, `Clamp(value)`, `Stop(RuleId, reason)`. There is no "warn and continue" for
  anything that moves a motor. The `match` on it has no `_` arm.
- **Fail closed.** Unknown, missing, stale or unparseable means refuse or stop, never allow. A `null` in the skeleton refuses
  the motion that needs it (PLAN item 1); a reply too old to trust stops the limb; an error inside a check is a `Stop`.
- **Every check runs every tick, before transmit,** for every enabled joint. No sampling, no "check every N ticks to save
  time". If the tick can't afford the checks, the tick budget is the problem.
- **Enable needs proof.** The enable path takes a value only preflight can create (`PreflightPassed`, rust.md section 3), so
  an enable without a preflight doesn't compile.
- **Each rule's doc comment** gives its ID, the PLAN row, what it protects and the failure it covers, in one or two lines.

## 4. Faults latch; nothing bypasses

- **A stop latches.** It clears only through the operator `clear` described in PLAN item 6, which is logged with who and
  when. Software never clears a fault and retries. A limb's stop is latched in its bus thread (`can`'s `BusTick`), the
  only place that sees every frame; `clear` reaches it through `BusTick::rearm`, which refuses until every drive in the
  limb is known disabled.
- **No bypass switches.** No `--force`, `--skip-preflight`, `SAFETY_OFF` env var, debug build that skips checks, or "bench
  mode" that loosens a rule. **Why:** a bypass that exists will be used at the worst moment, often by an agent trying to get
  a run to pass. A test that needs a different limit uses a skeleton fixture; a test that needs faults uses `sim-drive`.
  The commissioning caps (PLAN item 1) aren't a bypass: they follow from the skeleton's nulls, they can't be asked for,
  and every rule that is built still runs under them.
- **No catching and continuing.** A panic or error in the realtime path ends with drives timing out (50 ms) by design. Don't
  wrap safety code in recovery logic that keeps drives fed.

- **No config value turns a protection off.** No `0 = infinite` timeout, no `null = no limit`, no "skip checks" setting. The
  loader refuses such values (PLAN item 6 already refuses `canTimeout` 0). **Why:** ArduPilot ships a setting to skip its
  arming checks and has to warn people never to use it; moteus and ODRI both let a value disable their watchdog.

## 5. Every refusal tells the operator what to do

Each preflight refusal and stop has an operator-facing message with three parts, kept next to the rule:

| Message | Cause | What to do |
|---|---|---|
| `refused: left_elbow_pitch canTimeout reads 0, expected 1000` | The drive rebooted and lost its setting | Run preflight again; the runtime rewrites it |

The message names the joint, the measured value and the expected value. **Why:** a refusal that just says "preflight failed"
gets worked around. ArduPilot documents every pre-arm check this way (message, cause, solution), and its users fix the cause
instead of disabling the check.

## 6. Every rule is proven twice

1. **Unit test** of the rule's function, `Guards: safety - <rule ID>`, a table of inputs at, just inside and just outside the
   threshold.
2. **Sim test** on `vcan`: inject the failure in `sim-drive` (silent drive, fault bit, VBUS out of window, reboot) and check the
   runtime stops the right limb within the deadline and logs the rule ID.

Where PLAN's "Done when" asks for it, the rule is also shown once on a real drive, attended, per [bench.md](bench.md).

## 7. Changing a rule

A PR that adds, removes or changes a safety rule:

- updates the PLAN item 6 row, the code and both tests **in the same PR** (one fact, one place: the PR keeps them in step);
- says in its description which hardware and failure the change affects, and whether any threshold got looser;
- gets Joey's review (PLAN: changes to `safety` need it);
- never loosens a threshold to make a run pass. If a rule stops a run that should have passed, find out why before touching
  the rule.

## 8. Logging

Every verdict other than `Allow` is an event: rule ID, joint, limb, the measured value, the threshold and the time
([rust.md section 12](rust.md#12-logging-in-code-tenet-8) for field names). Every enable, refused enable, stop and clear is an
event too. The realtime thread doesn't log directly; it hands events to the logger through the non-realtime queue.

## Review checklist

- Does the rule name its hardware and failure, and is it in the lowest layer that can enforce it?
- Which attended bench tests can it block, and is that worth what it protects?
- Is it a pure function with an enum verdict and no `_` arm?
- Does every unknown or stale input lead to refuse or stop?
- Is there any path, flag or mode that skips it?
- Unit test and sim test both present, both citing the rule ID?
- PLAN row, code and tests changed together?

## Sources

- ArduPilot pre-arm checks (message, cause, solution; "never disable arming checks"):
  https://github.com/ArduPilot/ardupilot_wiki/blob/master/common/source/docs/common-prearm-safety-checks.rst
- moteus timeout mode (latched until an explicit stop): https://mjbots.github.io/moteus/reference/configuration/
- ODRI master board (command timeout, session ID so only one program controls the robot):
  https://github.com/open-dynamic-robot-initiative/master-board/blob/master/documentation/masterboard_communication.md
- PX4 contribution rules ("PX4 is safety-critical": evidence for every change): https://github.com/PX4/PX4-Autopilot/blob/main/CONTRIBUTING.md
- rerun CODE_STYLE ("an error should never happen in silence"; invalid configuration is an error, not a silent fallback):
  https://github.com/rerun-io/rerun/blob/main/CODE_STYLE.md
