# Roark software tenets

**Agreed by Joey, 2026-11-08.** These are the rules the robot software is judged against. The left arm is brought up on a
fresh, lean stack that follows them. Legacy code that doesn't honour them is not carried over, and once milestone 2 is done
(left arm passing, right arm moved onto the new stack) the legacy code in the marengo repo is deleted. A reviewer, human or agent, can cite a tenet by
number as the reason for a change.

## 0. Every change is for the finished robot

We write, update and delete code for the **finished robot**: five limbs, every drive, the power board, the battery, the legs.
Never for the current iteration of one limb. The limb on the bench decides what gets *tested* next, not what the code is *for*.

Before any change, ask: **"Is this still right when the whole robot is built?"** If the answer is "only for this limb" or "only
for now", it's the wrong change. This applies to code, config, docs, tests and folder names alike.

## 1. A fixed robot, not a kit

The robot has a fixed set of limbs: two arms, two legs and the waist. Each has pre-assigned RobStride actuators on a fixed bus
with fixed IDs. Our design process is built around the actuators, so once one is in place, it stays. When a drive answers it is
registered and addressed; when it doesn't, it shows as offline. Nothing else.

- No mix-and-match of actuator types per limb, no plugin layers, no generic "any limb, any motor" abstractions.
- A limb that isn't built yet is just a limb whose drives are all offline. It needs no separate code path.
- **Enable is per joint set.** Every joint named in an enable must answer and pass preflight; joints not named stay offline and
  block nothing. There is no "all joints must be online" gate.
- Adding a limb (a hand, the neck) is a skeleton change Joey agrees, not a plugin. The parked head and neck stay out of the
  skeleton until they exist.
- **We are building the robot, not a limb.** The limb on the bench is the current milestone, not the scope. No code, doc, file
  or folder is named after the current step ("right arm", "torso", "left arm") unless it is truly limb-specific hardware data.

## 2. One skeleton file is the contract

One hand-agreed file (YAML) describes the whole robot: every limb, every joint in it, its actuator type, bus, device ID,
direction, zero, soft and hard limits, and torque, current and speed caps. The runtime reads that file and nothing else about
the hardware's identity, wiring and limits. **The software never reads CAD or design files.**

- When the hardware changes, the hardware side opens one PR in this repo that touches only the skeleton, and adds a change-log
  line to [STATUS.md](https://github.com/jaylamping/marengo/blob/main/hardware/STATUS.md) the same day. A missing value stays
  empty and refuses the motion that needs it (PLAN item 1); placeholders never become numbers.
- Measured dynamics (masses, centres of mass, friction fits) live in one second committed file that tools write from logged
  sessions and the runtime reads. It never holds limits or addresses.
- A URDF or MJCF for sim and visualisation may be generated from CAD or from the skeleton, but the runtime doesn't depend on it.
- One fact lives in one place. If a joint name, limit or ID appears in two files, one of them is wrong.

## 3. Layered safety, each layer with a job

We will never catch everything, so safety is layered, and each layer covers a failure the others can't.

1. **Hardware:** physical E-stop in motor power; power board heartbeat watchdog; fuses and port breakers.
2. **Drives** (still acts when the Pi is dead): CAN host-loss timeout of 50 ms, after which the drive goes limp (it does not
   hold position; a supported arm drops onto its pad); torque, current and speed caps; the anti-backdrive damper left on
   (never written).
3. **Host, a short fixed list:** check the drive settings above before every enable and refuse on any mismatch; soft limits
   inside every hard stop; a bound on *total* commanded torque (not only feed-forward); stop on any fault and never auto-clear
   it; stop when a drive goes silent. The runtime never enables a drive on its own, at start, after a restart or when a drive
   comes back.

Every safety rule names the hardware it protects and the failure it covers. A rule that duplicates another layer, or protects
nothing nameable, goes. **Safety that stops the robot being tested has failed too:** a refusal is a cost, a rule is built
before the test that needs it and not before, and nothing blocks an attended, low-cap bench test unless it protects a
named motor or part. There are no spare actuators, so motors come first, then printed parts, then the frame.

## 4. Build only what's needed now

Code exists only if a bench or sim test on the current milestone's checklist needs it. Safety and the simulated drive come
before the first real enable because that test needs them. No scaffolding for features that may come later.

- ADRs, docs and version files describe what exists and what was decided, not what might be built. Speculative code, ADRs and
  docs are deleted, so no agent is afraid to touch anything.
- If something is needed later, it gets built later, against the real need.

## 5. The CAN layer is the foundation

CAN is the most important data stream in the robot, so it is the most trusted code, not the most feared. **It is rewritten from
scratch**, small and readable:

- one realtime process on the Pi owns every CAN bus;
- the RobStride protocol is implemented from the vendor manuals ([hardware/docs/robstride/](https://github.com/jaylamping/marengo/blob/main/hardware/docs/robstride)) and checked
  against real drives;
- every frame in and out is logged with timestamps by default;
- it runs unchanged against a simulated drive on `vcan`, so faults can be injected without risking a motor;
- bus names come from the skeleton, so moving a limb from the HAT to a USB-CAN adapter is a config change.

Everything else (UI, storage, agent tools) talks to the realtime process through one interface, and can crash without
affecting motion. Logging runs inside the runtime on a non-realtime thread fed by a lock-free queue, so it too can fail without
affecting motion, and a stop never waits for it.

## 6. Measure, automate, close the loop

- Every tuned number comes from a logged test, and every session (one runtime start to stop) is logged so sim can replay it.
- Anything we'd do more than twice becomes a script or loop an agent can run and judge on its own. A feedback loop beats
  debugging by hand every time.
- **No pointless tests.** A test exists only if it guards a real failure: a bug we actually hit, a safety rule, a protocol
  contract, or a number a loop depends on. No tests written for coverage or just because a file was touched. The rules and
  tools are in [conventions/testing.md](conventions/testing.md).

## 7. Any agent can learn it fast

An agent (or a person) new to the repo should know within minutes what every layer does, what it owns, who it talks to, and
where the seams are: between crates, and between the big pieces (Pi runtime, CAN, UI front end, back end, storage, agent tools).

- One short architecture map, [conventions/architecture.md](conventions/architecture.md), changed in the same PR as any seam
  move.
- Each crate or app starts with a few lines: what it is for, what it must never do, what it talks to.
- Names say what things do.

## 8. Observability everywhere

Detailed, concise, timely logs at every step, because the real-to-sim loop runs on them.

- Structured, timestamped events and metrics from every layer, on one clock: the Pi disciplined by chrony, with the Jetson
  joining the same way when it exists.
- Every motion command, drive reply, fault, limit hit, state change and operator action is recorded.
- Off-the-shelf formats and viewers instead of home-grown logging: MCAP and `candump` for frames and events, Prometheus and
  Grafana for metrics, Foxglove to view. Add another tool only for a named need.
