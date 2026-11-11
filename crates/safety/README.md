# safety

The host's half of PLAN item 6 (tenet 3) as plain functions and plain state: no I/O, time passed in. The runtime's
control thread runs it; the bus layer (`can`) does the pre-send veto, and this crate names its stops.

## What it does

- **Rule IDs** (`RuleId`): one per rule in PLAN item 6's table (the limits row holds two), the same string in the table, the code, the tests'
  `Guards:` lines and every event (safety.md section 2). `RuleId::of_stop` names the rule behind each of the bus
  layer's own stops; a requested stop carries its asker's `Cause`.
- **Preflight** (`Preflight`): for one drive, over its bus's slow requests one at a time (each an `Exchange` on a
  `Register`): get-ID and the UID check, write `canTimeout` 1000 and the skeleton's three caps, then read all four back
  with the damper and VBUS. Fault bits in the latest status since it began, any mode but Reset in a status or version
  reply since it began, a fault latched since the last clear, no status at all, another drive's view (another ID, or the
  same ID in another bus's snapshot: a drive is its bus and its ID, `DriveAddress`), a limb that isn't idle or that
  stopped or was cleared since preflight began, or a request with no result within `ANSWER_WITHIN_NS` (1 s) refuses.
  Only a pass makes a `PreflightPassed`, which proves the drive was right then; the runtime runs every named drive's
  preflight, enables them together from their proofs, drops the proofs on any event that voids them, and runs preflight
  again for every enable. Each `Refusal` names its rule, the measured and the expected value, and what the operator does
  about it (safety.md section 5). A null cap, a cap the drive's model can't take, a null `direction`, `zero_rad` or
  `hard_rad`, a model whose MIT scales aren't settled, or an unwired joint refuses before anything is sent.
- **The enable sequence** (`Enabling`): takes a `PreflightPassed` by value, so an enable without a preflight doesn't
  compile and one preflight enables once. Reporting off, its echo plus one tick, Enable, a fresh Run status within 50 ms,
  then `run_mode` = MIT, its echo and a later fresh Run status within 50 ms, one frame per tick in control's batch.
  A reply counts only if it was read inside its step's window (`RUN_WITHIN_NS`), and a status only if it is the fresh
  one (the first after a command the socket took) and no later status contradicts its mode, so one status never
  answers two frames. A drive seen out of Run after the Enable's answer ends the sequence, and so do, at any step,
  another drive's view, a fault, and the limb stopping, stopped or cleared since preflight (`LimbStopped`), even
  where the drive's own replies would have enabled it. Only `Next::Enabled` lets control command the drive. A failure
  after the Enable is planned means the limb must be stopped (`Enabling::enable_planned`), not just refused; each
  `EnableFailure` has its operator line and remedy too.
- **States** (`DriveState`, `LimbState`): PLAN item 6's machines as transition functions. An event a state doesn't
  take returns `None` and changes nothing.

Not here yet: the per-tick rules that need the skeleton (soft limits, total torque, temperature, VBUS while running)
come with their sim tests (step 7 design, PR 5).

## Must never

- Do I/O, read a clock, or keep hidden state: every input is an argument (safety.md section 3).
- Allow on an unknown: an unanswered or late request, an answer of the wrong kind, a null value or a stale status
  refuses.
- Offer a way past a rule: no flag, mode or setting skips preflight or a check (safety.md section 4).

## Talks to

- `can`: reads each snapshot's drive and limb views (`Seen`) and its slow results, names its `StopReason`s, and builds
  the `SlowKind`s preflight asks.
- `robstride`: the frames and writes the enable sequence and preflight use, and the values they compare.
- `skeleton`: each joint's caps, UID and bus, and the VBUS window.

Its place among the other crates is in the [map](https://github.com/jaylamping/roark/blob/main/conventions/architecture.md).

## Using it

A refusal says what was measured and what was expected, under its rule's ID; a stop the bus layer made is named by
its rule.

```rust
use robstride::CanTimeout;
use safety::{Refusal, RuleId};

let refusal = Refusal::CanTimeout { read: CanTimeout::from_ticks(0) };
assert_eq!(refusal.rule(), RuleId::DriveCanTimeout);
assert_eq!(
    refusal.message("left_elbow_pitch"),
    "refused (drive.can_timeout): left_elbow_pitch canTimeout reads 0, expected 1000"
);
assert_eq!(
    RuleId::of_stop(can::StopReason::DriveFault { slot: 0 }),
    Some(RuleId::HostFault)
);
```

The control thread runs one `Preflight` per named drive: `poll` with what the drive's bus last showed of it (`Seen::of`,
with the name of the bus the snapshot came from) gives a `Step`; it submits each `Step::Submit` to the drive's bus and
hands the result to `answered`, until `Step::Passed` (or `Step::Refused`). The `PreflightPassed` goes to
`Enabling::new`, whose `step` gives each tick's frame for the batch until `Next::Enabled`.
