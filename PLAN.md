# Roark software plan

**Status:** rev 4, 2026-11-08, sharpened by a seven-reviewer panel
([reviews](https://github.com/jaylamping/marengo/tree/main/review/roark-docs-20261108/reviews)). Joey owns this page. Where it
gives a default for an open question, the default applies until Joey answers (see [Open with Joey](#open-with-joey)).

**Every change is for the finished robot** ([tenet 0](TENETS.md#0-every-change-is-for-the-finished-robot)). **We are building
the robot, not a limb.** The software is written once, for the whole robot: five limbs (left arm, right arm, left leg, right
leg, waist) on five buses, as described by one skeleton file. Each hardware step only brings more drives online. The left arm
is **milestone 1** because it's the next limb on the bench, not because the code is about it. Nothing in the code, the docs or
the folder layout is named after the current step. Earlier code was written "for the right arm" and "for the torso", and that
is how it ended up the way the review found it (Joey, 2026-11-08).

**The approach (Joey, 2026-11-07/08):** a **fresh, lean stack** that follows the [tenets](TENETS.md), built in this repo. The
legacy code stays read-only in [jaylamping/marengo](https://github.com/jaylamping/marengo) until milestone 2 is done (left arm
passing, right arm moved onto this stack); then it is deleted there. A six-reviewer panel judged every legacy crate, bin and
tool against the tenets:
[RECONCILIATION.md](https://github.com/jaylamping/marengo/blob/main/review/sw-foundation-20261108/RECONCILIATION.md). The CAN
layer choice comes from a cross-industry deep dive:
[can-stack-for-marengo.md](https://github.com/jaylamping/marengo/blob/main/hardware/docs/research/can-stack-for-marengo.md).

## Which file wins

| Question | Source of truth |
|---|---|
| How to judge any change | [TENETS.md](TENETS.md) |
| Joint facts (IDs, buses, directions, limits, caps) | `config/skeleton.yaml` |
| Other hardware facts | [STATUS.md](https://github.com/jaylamping/marengo/blob/main/hardware/STATUS.md) and the docs it links. Check it before acting on any number here |
| Protocol facts | The [RobStride manuals](https://github.com/jaylamping/marengo/blob/main/hardware/docs/robstride), then bench captures |
| What to build, in what order | This plan |
| How code is written and laid out | [conventions/](conventions/) |
| Legacy code, ADRs, `AGENTS.md` | Never wins. Facts and bench lessons only |

## Real hardware rule

No agent sends Enable, motion, Set Zero, set-ID or a parameter write to a **real** drive unless Joey is present and has said go
for that session. `vcan` is free to use at any time. Every joint's first motion is attended. The legacy `marengo-pi-mcp` tools
stop the service and start their own CAN owner: never use them on a bus this runtime owns. There are no spare actuators.

## Milestones

Milestones 1, 2, 3 and 5 are "these drives come online and pass their tests" and add no code path of their own. Milestone 4
adds the power board interface (item 10).

| # | Milestone | Done when |
|---|---|---|
| 1 | **Left arm online**: loose drives on the bench, then the actuator test stand, then the printed arm on the torso with the camera calibration loop | (a) every §6 rule has a passing `vcan` fault test; (b) three loose drives scanned, IDs 11 to 13 set, preflight passes, and a deliberately wrong `canTimeout` is refused; (c) a 1 h idle soak with no error frames or RX overflow, and latency and jitter recorded in the repo; (d) `kill -9` while enabled leaves the drives limp within 50 ms and the `ExecStopPost` disable shows in candump; (e) a drive power-cycled while enabled (pull its drop fuse) can't be enabled again until preflight passes again; (f) all five joints sign-checked and zeroed (calibration stage C1); (g) the elbow rig has passed before the forearm is powered; (h) test stand files exist for RS03 and RS02; (i) calibration stages C0 to C2 pass attended, plus one clean unattended C3 |
| 2 | **Right arm moved to this stack**, then the legacy code deleted | Both arms enable from one runtime and one skeleton; silence on one drive stops only its limb; the right arm's taught limits and directions are moved and re-checked; legacy tree deleted from marengo |
| 3 | Waist | The waist enables on its own bus with no new code path. Waits on the waist hardware, which is parked |
| 4 | Power board and battery | Stopping the heartbeat drops the motor latch within its window; port-fault decode names the port; self-test runs only under its conditions (item 10) |
| 5 | Legs | Five buses at 250 Hz with measured bus load under 70 % per bus; legs run on the support gantry |

## Start here

1. **Joey, now, in parallel with the code:** order one isolated STM32F0 adapter running mainline candleLight (item 5), and the
   luggage scale for the test stand.
2. **Read** the tenets, this plan and [conventions/](conventions/).
3. **Skeleton** (item 1): the `skeleton` crate and `config/skeleton.yaml` with all five limbs, including the right arm's
   existing values. Putting two limbs in from day one exercises "no per-limb code" in sim long before milestone 2.
4. **Lift the legacy knowledge** into notes and test vectors (item 2).
5. **Codec** (`robstride`) against the manual test vectors.
6. **Bus loop and sim drive together** (items 3 and 4) on `vcan` interfaces named after the skeleton buses, with MCAP and
   `candump -L` recording from the first run (see [Observability](#observability-tenet-8)).
7. **Safety** (item 6) on `vcan` until every stop rule has a passing fault test. Add the systemd unit, the watchdog and the
   `ExecStopPost` disable.
8. **On the real adapter, no Enable yet:** name it by serial, scan, set IDs, soak, measure latency and jitter (item 5); run the zero
   persistence test (item 1) and the caps-in-mode test (item 6).
9. **First attended Enable** of the loose drives with Joey: preflight, sign check, unloaded jog.
10. Then the test stand (item 7), the elbow rig result into item 8's limits, and the camera loop (item 9).

Create each crate when an item first needs it. The crate table below is the naming target, not a to-do list.

## When the hardware is ready

| Hardware | State on 2026-11-08 | Software needed by then |
|---|---|---|
| Left shoulder and upper-arm drives (RS03 ×2, RS02), loose on the bench, 24 V supply | **Ready now** (drives owned, bench harness planned) | Items 1 to 6 |
| USB-CAN adapter | Not bought. Buy **one** isolated STM32F0 board running mainline candleLight (Openlight CANable Pro class, ~$60), pre-flashed or flashed before use; not a "CANable 2.0 Pro" G431 clone, which ships with slcan firmware | Item 5 |
| Actuator test stand, RS03 waist unit first | Designed for all four sizes, waiting for Joey's review and print; luggage scale to buy | Item 7 |
| Upper arm (printed) | Being redone as clamshells | Item 8 before it moves under power |
| Elbow dummy-output rig | 6808 bearings arrive Mon 2026-11-09; rig is hand-loaded | **None.** No drive is used |
| Forearm and RS00 | Designed, not printed | Item 8, after the elbow rig passes; the RS00 scale question (item 2) settled first |
| Camera rig (Logitech BRIO, AprilTag plates) | Plan approved; camera owned; plates not printed | Item 9 |
| Arm on the robot torso | Waits for Joey's rebuilt torso frame | Items 8 and 9 on the real geometry |
| Power board (rev B5) | Being routed; review, then fab | Item 10. The bench uses the 24 V supply and a physical E-stop until then |

The test stand's first unit is the waist RS03. It runs alone on a skeleton bus, keeps its skeleton ID, and the runner refuses
if any other drive answers on that bus. Milestone 1 does not wait on waist hardware.

## Names and crate layout (Joey, 2026-11-08)

Plain names that say what each piece does (tenet 7). No crate, binary, service, path or config key carries the robot's name;
it lives once, as `name:` in the skeleton. The architecture map, with owners and seams, is
[conventions/architecture.md](conventions/architecture.md).

| Crate | Does | Legacy code to mine for facts (never copy) |
|---|---|---|
| `skeleton` | Loads and checks the skeleton YAML | marengo-config, config/*.yaml |
| `robstride` | RobStride codec, no I/O | the codec half of robstride |
| `can` | Bus threads, tick schedule, drive scan and set-ID | the bus half of robstride, Davout's CAN code, motor-repl |
| `safety` | Drive preflight, states and the host rule list (tenet 3) | Davout |
| `control` | The control modes the tests need | Berthier |
| `dynamics` | Kinematics, gravity, calibration fits | armee-kinematics, armee-dynamics |
| `telemetry` | MCAP recording, metrics export, logging setup | none worth copying |
| `api` | The one interface to the realtime process | Chappe, armee-proto (as a warning) |
| `runtime` (bin) | The one realtime process | marengo-pi |
| `sim-drive` (bin) | Simulated drives on `vcan` | `davout/tests/physical_firmware/` |
| `robot-cli` (bin) | A client of `api` for scan, set-ID and checks; plus the independent `disable` | motor-repl `stop.rs` |
| `mcp/` | Agent tools, a client of `api` (item 9 needs it) | marengo-pi-mcp (as a warning) |
| `ui/` | Operator screen, a client of `api`; built when a test needs one. Milestone 1 uses the CLI and agent tools | Consul |

## Repo, toolchain, CI and deploy

- **Layout:** one Cargo workspace: `crates/`, `bins/`, `config/skeleton.yaml`, `config/dynamics.yaml`, `deploy/` (systemd units,
  CAN link files), `docs/`, `conventions/`.
- **Toolchain and lints:** per [conventions/rust.md](conventions/rust.md). Target `aarch64-unknown-linux-gnu`, 64-bit Raspberry
  Pi OS, kernel 6.1 or newer (gs_usb hardware timestamps).
- **File size limit:** no file of 100 MB (100,000,000 bytes) or more in git, LFS files included (Joey, 2026-11-08).
  `tools/check_file_sizes.py` holds it as `MAX_FILE_BYTES`; [cad.md](conventions/cad.md) rule 5 says how it's checked.
- **CI on every PR:** the gates in rust.md, including the `vcan` fault tests. If hosted runners can't load `vcan`, those tests run
  on a self-hosted runner or the Pi, never skipped silently. No hardware in CI.
- **Deploy:** cross-build, install to `/opt/robot/releases/<rev>` with an atomic `current` symlink; config in `/etc/robot`;
  data in `/var/lib/robot` on its own partition. Details in [deploy.md](conventions/deploy.md). No self-update
  machinery (`marengo-deploy` is deleted, not rebuilt).
- **Units:** `runtime.service` (`Type=notify`, `WatchdogSec`, `LimitRTPRIO`, `LimitMEMLOCK=infinity`,
  `ExecStopPost=robot-cli disable`, `Restart=always`, which is safe only because of the no-auto-enable rule in item 3);
  `candump@<bus>.service` per bus.
- **Merging:** Joey merges; CI must be green. Changes to `robstride`, `can`, `safety` or skeleton values need his review.

## 1. The skeleton YAML (tenets 1 and 2)

One file, `config/skeleton.yaml`, describes the whole robot. The software owns the schema and the loader; the hardware side owns
the values. When hardware changes, the hardware side opens one PR here that touches only the skeleton and adds a change-log
line to STATUS.md the same day. The runtime never writes it; tools that teach limits produce a proposed diff for a PR.

Shape (the builder may adjust field names; the content is required):

```yaml
schema: 1
name: roark                     # the only place the robot's name appears
power: { source: bench_24v, vbus_min_v: 22, vbus_max_v: 26 }
buses:
  can1: { bitrate: 1000000, sample_point: 0.75, adapter_serial: "<USB serial, for its link file>" }
limbs:
  left_arm:
    joints:
      - name: left_shoulder_pitch
        actuator: rs03          # model only; MIT scales live in the codec
        bus: can1
        id: 11
        uid: null               # MCU UID from the type-0 reply, filled at commissioning
        direction: null         # +1 or -1 after the sign check; null refuses enable
        zero_rad: null          # see "Zero convention"; null refuses enable
        reference_pose: "<how the link is placed for referencing>"
        hard_rad: [-0.87, 3.14] # from STATUS.md
        soft_rad: null          # optional; tighter than the derived inset
        torque_cap_nm: null     # null refuses enable
        current_cap_a: null
        speed_cap_rad_s: null
```

- **Units:** SI and radians, output-joint space. Current means drive phase current (Iq) unless a field says otherwise.
- **Conversion:** `q_joint = direction × (q_motor − zero_rad)`, `τ_joint = direction × τ_motor`; commands use the inverse. Joint
  positive directions follow STATUS.md (pitch raises forward, roll abducts, yaw rotates outward, elbow flexes).
- **Loader refuses:** duplicate joint names; a duplicate (bus, ID); an unknown actuator model; non-finite numbers; reversed
  bounds; soft limits outside hard limits; a cap above the model's range; a hard window that contains the drive's position wrap
  point; currents that can be enabled together summing above 90 A (STATUS.md). The error names the joint and field.
- **Null is not permission.** A joint with any required field null loads fine, shows as offline or uncommissioned, and is
  refused at enable. Placeholders never become numbers.
- **Soft limits** default to 3° inside hard limits for supervised runs and 5° for unattended runs, unless `soft_rad` is tighter.
- **Left arm:** `can1`, IDs 11 to 15: `left_shoulder_pitch`, `left_shoulder_roll`, `left_upper_arm_yaw`, `left_elbow_pitch`,
  `left_lower_arm_yaw` (14 and 15 are marked "proposal" in STATUS.md; use them). **Right arm:** `can0`, IDs 1 to 5. Unbuilt
  limbs are listed with `bus: null` and IDs from the ADR 0001 blocks (right leg 21 to 30, left leg 31 to 40, waist 41 and up);
  ID 16 on `can1` stays reserved for a hand. The parked head and neck (STS3215 servos, not on CAN) stay out until they exist.
- It replaces `motors.yaml`, `control.yaml`, `robot.yaml`, `homing.yaml` and the humanoid templates (whose bus and ID numbers
  are wrong; don't copy them).

**Dynamics data.** Link masses, centres of mass and friction fits live in a second committed file, `config/dynamics.yaml`,
keyed by skeleton joint name and the skeleton revision it was fitted against. Tools write it from logged sessions; the runtime
reads it. It never holds limits or addresses. A URDF seeds it once and is never read at runtime.

**Zero convention.** The drive reports output position inside one turn after power-on. The host never writes 0x7029 or
0x702B and never saves parameters (type 22). Whether a Set Zero (type 6) survives a power cycle is unknown, so before milestone 1
motion, run the **persistence test** on one loose drive of each model: mark a pose, read position, power-cycle, read again;
repeat after one Set Zero.
- If the reading repeats within 0.5°: `zero_rad` is a skeleton fact and normal startup never sends Set Zero.
- If not: every power-up needs an attended reference at `reference_pose`; until it's done the joint counts as unzeroed and is
  refused at enable.
Record the result in STATUS.md (via the hardware side) and here.

## 2. Lift the hard-won knowledge first

The legacy code holds real bench lessons. Copy them into the codec's docs and test vectors first. The list, with paths, is in
[RECONCILIATION.md, "Hard-won knowledge"](https://github.com/jaylamping/marengo/blob/main/review/sw-foundation-20261108/RECONCILIATION.md#hard-won-knowledge-to-lift-before-deleting-anything).
**Done when** every fact there is a codec test vector, or a comment citing its manual section or bench capture.

**Sequences the code must honour** (from the legacy code and
[robstride-firmware-behavior.md](https://github.com/jaylamping/marengo/blob/main/docs/commissioning/firmware/robstride-firmware-behavior.md)):

- **Enable one drive:** preflight read-backs pass → active reporting (type 24) off → wait for its echo plus one tick → no Set
  Zero to this drive in the last 800 ms → Enable (type 3) → expect a reply in Run mode (measured 1.4 to 10.3 ms; refuse after
  50 ms) → write RunMode 0x7005 = 0 (MIT) → its echo and a later fresh Run status within 50 ms → no non-neutral MIT
  frame before Run is seen.
- **Stop:** Disable (type 4, fault-clear byte unset) to every affected drive on every reachable bus, without waiting for one
  drive's answer before the next, then active reporting off. A lost bus never delays stops on healthy buses. Pre-steps
  (SpeedTarget 0x700A = 0, a neutral MIT frame) are allowed only if they don't delay Disable. Each stop records what was
  achieved per drive: sent, confirmed by a fresh reply, or unconfirmed. A stop is bounded: Disables for 100 ms, a
  Reset read up to a period and a send window after that still confirms (the reply to the last Disable, read by a
  next tick that may wake late inside its send window), each confirmed drive's reporting off goes once its
  post-Disable silence is over, and the stop ends at the latest two periods and a send window after the last
  confirmation's silence could end (164 ms at 250 Hz, `can::Timing::stop_max_ns`). The period of reply allowance is
  provisional until Disable-to-Reset latency is measured on the real adapter (step 8).
- **Exit:** Stop, then active reporting off to every drive; reporting persists across host processes otherwise.
- **Set Zero:** only with the limb stopped. After a Set Zero on an enabled drive, it goes silent 511 to 614 ms later for 45 to 66 ms
  and drops every frame in that window. Send nothing that matters to that drive for 800 ms.
- **Silence windows:** don't count missed replies during the enable-to-Run window, or for 100 ms after a Disable to an
  enabling or enabled drive (post-Disable silences up to 48.7 ms are measured); a Disable sent again keeps the first
  one's window. A drive never enabled, or seen in Reset after its Disable, is disabled, and a silent disabled drive is
  `offline` (item 6 Silence row): nothing sent to it is counted until its next Enable, and another Disable doesn't
  change that. For a drive that was enabling or enabled, with no Reset read after its Disable, counting resumes after
  the 100 ms, so a lost Disable can't leave a running drive uncounted.

**Transmit allowlist:** types 0, 1, 3, 4, 6, 17, 18, 24. Type 7 (set ID) only from the set-ID command with exactly one drive
answering on that bus. Never 22, 23 or 25; never write 0x7029, 0x702B or 0x702A; never type 4 with the fault-clear byte set.

**Don't copy** `scripts/can-up.sh` link settings: `restart-ms 100` and `txqueuelen 1000` were MCP2515 workarounds and contradict
item 3.

**Open fact: RS00 MIT scales.** The legacy code uses ±50 rad/s and ±17 N·m; every RS00 manual says ±33 and ±14. A built RS00 is
on the bench already (right arm, `right_lower_arm_yaw`, ID 5, `can0`). Settle it with a candump capture of a small known motion
on that drive or a loose RS00, with Joey present, before any RS00 motion on this stack. Until then the codec refuses to command
an RS00.

## 3. The new CAN layer (tenet 5)

Per [can-stack-for-marengo.md](https://github.com/jaylamping/marengo/blob/main/hardware/docs/research/can-stack-for-marengo.md):

- **One realtime process** owns every bus, with one blocking thread per bus at realtime priority. Each tick: send every command,
  collect replies until a deadline inside the period (start at about 60 %, tune by measurement), publish a snapshot with each
  joint's reply age. Parameter traffic only in the slack. **250 Hz default** per bus, a runtime argument rather than a skeleton
  fact; 300 Hz only if measured.
- **Timing is a worst-case budget.** At 250 Hz three periods are 12 ms, inside the drives' 50 ms timeout. Any wake past its
  send window, or a backlog in the drain (more frames queued than it may read before the send), stops every active limb
  on the bus at once; it doesn't wait for the feedback to expire. Neither stops an idle limb: that tick it gets only
  Disables and reporting off and the rest is held, and the batch checks (a bad batch, motion on stale feedback) still
  stop it. Missed deadlines are counted, never skipped silently.
- **Rust:** `socketcan` 4.0 (blocking socket, netlink, candump log format). No async runtime in the loop. Realtime rules are in
  [rust.md](conventions/rust.md).
- **Codec:** our own, no I/O, a typed frame table transcribed from the manuals, per-model scales as constants in `robstride`
  each citing its manual section (the skeleton names the model only), test vectors from the manuals, cross-checked against the
  `motorcom` crate. Stay in the drive's default private protocol with active reporting off. Refuse out-of-range or non-finite
  values; never clamp.
- **Linux:** bitrate and sample point set explicitly, error frames on, short TX queue. PREEMPT_RT only if the Pi 5 measurement
  misses its budget, but expect it to: published Pi 5 numbers show a stock kernel past 9 ms worst case under stress against
  about 100 to 225 µs with PREEMPT_RT, and Raspberry Pi ships no RT kernel. Measure with 1 h of `cyclictest` or `rtla` under
  `stress-ng` memory load ([deploy.md](conventions/deploy.md)). Pin a kernel that includes the fix for CVE-2023-53523 (gs_usb timestamp init).
- **Bus-off is latched in software.** Current candleLight firmware restarts the bus by itself about 100 ms after bus-off unless
  the host claims recovery (`GS_CAN_FEATURE_BUS_OFF_RECOVERY`, `CAN_BUS_OFF_RESTART_DELAY_MS` in `src/can_common.c`), and
  mainline gs_usb never claims it, so `restart-ms` and `ip link restart` don't control it. The runtime latches a stop on the
  first bus-off error frame and stays stopped after the adapter recovers. Whether older firmware on shipped adapters behaves
  the same is unverified; item 5 checks it.
- **TX echo** from gs_usb means the frame reached the adapter's controller, not that it went out on the wire. Don't use it as
  proof of delivery.
- **Stable bus names.** gs_usb adapters get `canN` names in plug-in order, and the MCP2515 HAT already provides `can0` and
  `can1`. Pin each adapter to its skeleton bus name by its USB serial (a systemd-networkd `.link` file, with bitrate in a `.network`
  file, per [deploy.md](conventions/deploy.md)); disable the HAT's `can1` before the
  adapter takes that name. At start, check each interface's driver against the skeleton.
- **Only the realtime process transmits.** Scan, set-ID and parameter reads are runtime commands through `api`; `robot-cli` is
  a client. The one exception is `robot-cli disable`: it reads only (bus, ID) pairs from the skeleton, opens the sockets itself,
  sends Disable then active reporting off to every ID, depends on nothing else, and runs only after the runtime has exited
  (systemd `ExecStopPost`).
- **A hung control thread must let the drives time out.** Each command batch carries a tick number and an expiry. A bus thread
  sends only a fresh batch and never re-sends a stale one. If control hasn't published for two ticks, the bus thread stops its
  limbs. The systemd watchdog is fed only when the control loop and every bus in an active run are making progress.
- **Crash and restart.** The runtime starts with every drive disabled and never enables on its own: not at start, not after a
  restart, not when a drive comes back. A panic anywhere ends the process. The stop path disables drives before it flushes any
  log.
- **Scan and identity.** A scan lists every ID answering on a bus and reads each drive's MCU UID (type 0). Once commissioned, the
  skeleton stores the UID; a mismatch refuses enable on that limb. An ID the skeleton puts on a different bus refuses enable on
  both buses. Set-ID runs one drive at a time, only while every limb on that bus is disabled. The left drives may hold old IDs
  (12 on `can1`, 11 to 14 on `can0`).

### 3a. The runtime interface (`api`)

- **Transport:** local to the Pi (default: one Unix-domain socket), with socket permissions limiting who can command motion.
  Encoding is the builder's call. A slow or dead client never blocks the loop. The UI bridge never exposes an unauthenticated
  remote motion endpoint (one way to do it: [remote-access.md](conventions/remote-access.md)).
- **Reads:** a decimated snapshot (per joint: position, velocity, torque, temperature, mode, fault bits, reply age; per bus:
  state and error counters; limb and robot state), the scan table, and the event stream.
- **Requests:** `stop(scope)` is always accepted from any client and jumps the queue. `enable(joints)` runs preflight first.
  `run_plan(file)` runs a finite plan inside the runtime with every stop rule; one plan per joint at a time. `clear(scope)`,
  `scan(bus)`, `set_id(bus, old, new)`, `read_param(bus, id, index)`. Every mutating request names the client and the skeleton
  revision it expects; a reconnect may fetch a result but never repeats a physical action.
- **Motion authority:** a human at the CLI or UI may `enable` and `clear`. Agents may plan, run anything on `vcan`, start
  approved plans and stop. Nothing streams live targets from outside the runtime
  ([CALIBRATION_LOOP §10.3](https://github.com/jaylamping/marengo/blob/main/hardware/designs/left-arm/testing/CALIBRATION_LOOP.md)).
- **Client loss** doesn't change motion (tenet 5). The physical E-stop is the operator's backstop.

## 4. Simulated drives on `vcan`

One `sim-drive` process speaks the RobStride protocol through the same codec. **The `vcan` interfaces take the skeleton's bus
names** (`ip link add dev can1 type vcan`), so the runtime runs literally unchanged.

- **Plant:** a simple per-joint model (inertia, friction, gravity load from `config/dynamics.yaml`). No physics engine, so CI can
  run it. A MuJoCo-coupled mode is added when a test needs coupled dynamics (calibration C6, replay).
- **Behaviour:** `canTimeout` firing drops the drive to reset; a simulated reboot reverts parameters to defaults (`canTimeout` 0);
  enable-to-Run delay 0 to 11 ms; the Set Zero blackout; post-Disable silence up to 50 ms; mode and fault bits.
- **Fault injection:** silent drive, late, dropped, duplicated and delayed frames, fault bits, wrong mode, VBUS out of range,
  reboot mid-run, duplicate IDs, parameter read-back mismatch, bus-off, interface gone.
- **Done when** every §6 rule has a seeded `vcan` test that injects its trigger and checks the stop frames are on the bus within
  one tick and the drive state is `faulted`. There are no spare actuators, so every stop rule is proven here first.

## 5. Bench bring-up (milestone 1: `can1`)

- Confirm the adapter: `dmesg` shows `gs_usb` (not slcan); write its link file; `ip -details link show can1` lists it.
- Bench harness per [left-shoulder-bench-harness.md](https://github.com/jaylamping/marengo/blob/main/hardware/electrical/wiring/left-shoulder-bench-harness.md):
  120 Ω at each end (the adapter's termination jumper replaces the HAT end), about 60 Ω across CAN_H/CAN_L with power off, one
  ground tie.
- Scan, set IDs one drive at a time, then a 1 h idle soak (error frames, RX overflow, error counters, bus load). Then measure
  round-trip latency and per-tick jitter at 250 Hz. Record the adapter's firmware version and check its bus-off behaviour
  (item 3) by shorting CAN_H to CAN_L with no drive enabled. **Done when** the soak is clean and the numbers are committed. Only then buy
  adapters for the other buses.

## 6. Safety: the three layers (tenet 3)

The panel found the **drive layer doesn't exist** in the old code. This stack builds it before the first real enable.

### States

- **Drive:** `offline` (no reply) → `seen` (answers; UID matches once commissioned) → `checked` (preflight passed since this
  power-up) → `enabled` (Run mode seen) → `faulted` (latched). Silence, a reset-mode reply or a reboot drops the drive back to
  `seen` and drops its preflight.
- **Limb:** `idle` → `enabling` (preflight and the enable sequence) → `enabled` → `stopping` → `faulted`. **Robot:** bus-off or a lost bus faults every active run.
- Every transition is an event with its cause.
- **Enable is per joint set.** An operator enables named joints. Each must be `checked`; joints not named stay offline and block
  nothing (tenet 1). Joints mechanically carried by an enabled joint are named too. Losing a named joint after enable stops the
  run; it never quietly becomes optional.
- **Preflight is dropped**, and must pass again before any enable, when a drive misses 3 consecutive replies, shows a mode other
  than Run while enabled, sets a fault bit, its bus goes bus-off or disappears, or the runtime restarts.

### Rules

Each rule names what it protects and the failure it covers. A rule that protects nothing nameable goes.

| Layer | ID | Rule | Protects | Failure covered |
|---|---|---|---|---|
| Drive | `drive.can_timeout` | `canTimeout` 0x7028: write 1000 (50 ms; unit 50 µs, 20000 = 1 s, 0 = off) at every runtime start and after any reboot; read back before every enable; refuse unless it reads exactly 1000. The right-arm drives read 600 today; rewrite them | Every drive and its limb | Pi crash, hang, killed process, lost bus: the drive goes limp 50 ms after the last command. It does not hold position; the arm drops onto the pad |
| Drive | `drive.caps` | `limit_torque` 0x700B, `limit_cur` 0x7018, `limit_spd` 0x7017: write min(skeleton cap, plan or test cap), read back before enable | Drive and the printed parts on that joint | Host bug commanding too much. **Caveat:** the manuals describe `limit_spd` as a position-mode limit and `limit_cur` as a velocity/position-mode limit. Whether any of the three bounds MIT mode is unproven: test on a loose drive before relying on it, and until then treat it as host-only in that mode |
| Drive | `drive.damper` | Damper 0x702A: read only, never written. The default 0 means the post-power-off anti-backdrive protection is **on**; 1 turns it off. Refuse enable unless it reads 0 | Drive and gearbox | Arm back-driving the drive when power is off |
| Host | `host.preflight` | Preflight: VBUS 0x701C inside the skeleton's window (bench 22 to 26 V; this is a bench window, not the battery's), no fault bits, the drive in Reset (not Run or Calibration), the three caps and `canTimeout` read back as written, the joint's `direction`, `zero_rad` and `hard_rad` set (item 1: unverified is null, and null refuses enable), and its model's MIT scales settled (item 2). Preflight and the enable sequence both report under this ID a view of another drive than theirs (another ID, or the same ID from another bus: IDs are unique only per bus), a runtime bug (Joey, 2026-11-10); and a limb that stopped or was cleared since preflight began, which voids the proof | Every drive | Wrong settings, wrong supply, drive already faulted, drive put in another mode by another controller; an enable acting on another drive's state, or on a proof a stop has voided |
| Host | `host.vbus` | VBUS while running: read 0x701C in the slack at least once a second per drive; stop outside the window | Drives and supply | Supply sag or regen overvoltage |
| Host | `host.silence` | Silence: while a limb is enabled, stop it after 3 consecutive missed replies (12 ms at 250 Hz) or when any reply age passes 12 ms. A silent disabled drive (never enabled, or seen in Reset after its Disable) is `offline`, not a fault. For a drive that was enabling or enabled when its Disable went, with no Reset read since, counting resumes after 100 ms (item 2 Silence windows) | The limb's drives and parts | Lost drive, cable, power cycle |
| Host | `host.fault` | Faults: stop on any fault bit. A fault on any drive of a limb, idle or running, stops the whole limb, a drive of that limb not named in the enable included: a deliberate limit on tenet 1's "joints not named block nothing" for drives that share a limb (Joey, 2026-11-10), revisited when the runtime passes the enabled joint set to the bus. A latched stop clears only by an operator `clear` through `api`; a drive fault bit clears only by power-cycling that drive, then full preflight | Everything on that limb | Drive fault; never auto-clear and retry |
| Host | `host.mode` | Mode: a drive seen in Run after its Enable that reports any other mode by itself, or that shows no fresh Run status within 50 ms of its Enable or of its `run_mode` = MIT write (item 2), stops its limb and drops its preflight | The limb's drives and parts | A drive dropping to Reset mid-run (`canTimeout` fired, a reboot or brown-out) or never reaching Run |
| Host | `host.identity` | Identity: once commissioned, a drive whose UID (type 0) isn't the skeleton's is refused enable on that limb (item 3, Scan and identity). An ID the skeleton puts on another bus joins this row with the scan (step 8) | Every drive on that limb | A swapped or re-IDed drive answering on the expected ID |
| Host | `host.soft_limit`, `host.total_torque` | Limits: soft limits inside every hard stop (§1). Total commanded torque per joint, kp·(q_des − q) + kd·(dq_des − dq) + τ_ff, is predicted from the latest reply and refused above the joint's torque cap; backed by the drive's own limit once proven in MIT mode | Printed parts, hard stops | Bad target, gain or feed-forward |
| Host | `host.sign` | Sign: no gravity feed-forward on a joint until its direction is verified by a small torque-only pulse with the link supported, checked against the skeleton. Feed-forward runs only on a chain whose every joint answers with a verified direction | Arm and parts | Feed-forward pushing the wrong way |
| Host | `host.temperature` | Temperature: pause at 60 °C (rest pose, torque off if the pose allows) until 45 °C; stop at 75 °C | Drive windings | Overheating (drive's own protection is far higher) |
| Host | `host.hang` | Hang: see item 3 (stale or malformed batches, a late wake, watchdog, no auto-enable) | All drives | Hung control thread keeping drives fed |
| Host | `host.bus` | Bus-off (latched on the first error frame, even if the adapter restarts itself), any socket read or write failure other than a full queue (interface down or gone, `ENETDOWN`, `ENODEV`, included), or more frames queued than a tick can read: stop every active run; the drives on that bus time out. An enable's reporting-off or `run_mode` write not read back from the socket within 50 ms ends that enable, stopping its limb once the Enable has gone | All limbs; for an enable, its limb | Lost bus, wiring fault or unplugged adapter |
| Host | `host.pi_health` | Pi health: read `vcgencmd get_throttled` once a second; refuse enable while under-voltage or throttling is active, and log it if it starts during a run | Control timing | A browned-out or throttled Pi missing ticks |
| Host | `host.logging` | Logging: if the session log can't open or the disk is full, refuse the next enable; never stop a running motion for it | The record (tenet 6) | Disk full or slow |

**Done when** preflight refuses an enable for each of: `canTimeout` ≠ 1000, a cap mismatch, damper ≠ 0, VBUS outside the window,
any fault bit, a drive not in Reset, a null `direction`, `zero_rad` or `hard_rad`, a model without settled MIT scales;
proven on `vcan` and once on a real drive.

## 7. Actuator test stand tooling (T1 to T6)

Runner, logger and fitting scripts for [sim-to-real-loop.md](https://github.com/jaylamping/marengo/blob/main/hardware/docs/sim-to-real-loop.md)
section 2.3: one drive alone on its bus at the runtime's rate (250 Hz; the source doc says about 1 kHz, measure before raising
it), logging command, position, velocity, current (`iqf` 0x701A), temperature and kernel timestamps; T1 friction and inertia, T2
reported vs real torque (operator types the luggage-scale reading), T3 backlash, T4 latency, T5 thermal, T6 excitation. Output:
one file per actuator type, ready for MJCF `frictionloss`, `damping`, `armature`, plus its raw MCAP logs.

Limits: T2 and T5 stop at min(test step, stall rating) (RS03 13 N·m, RS02 6 N·m; RS00 and RS04 to look up before their turn).
T5 stops at 60 °C. Torque cap = test maximum + 10 %, speed cap 1 rad/s except T1's speed passes. Modes other than MIT need the
caps-in-mode test (§6) first. Order: RS03 (waist unit), RS02, RS00, RS04.

## 8. Limits for the left arm under power (milestone 1)

| Rule | Value | Source |
|---|---|---|
| Elbow torque cap | The lowest of the RS02 duty rating, the rig result and the plan's cap. 17 N·m is the printed stop's design load and the RS02 peak, **not** an operating cap. A failed rig needs a hardware fix and retest; a lower software cap doesn't release it | [ELBOW_DUMMY_OUTPUT_TEST.md](https://github.com/jaylamping/marengo/blob/main/hardware/designs/left-arm/testing/ELBOW_DUMMY_OUTPUT_TEST.md) |
| Elbow soft limits | 3° inside the 0° and 124° stops supervised, 5° unattended | same, and §1 |
| Never | run into a hard stop, hold a stall, or seek a hard stop under power to teach it | same |

Operator rule, not software: keep side pushes at the hand under about 40 N until the rig's test 7 has run.
**Done when** the five left joints' caps and soft limits are in the skeleton with the source of each number.

## 9. Camera calibration loop

Spec: [CALIBRATION_LOOP.md section 11](https://github.com/jaylamping/marengo/blob/main/hardware/designs/left-arm/testing/CALIBRATION_LOOP.md#11-spec-for-the-software-project).
Order: camera service and stage C0 (arm unpowered), then the stage runner with section 9's stop rules tested on `vcan`, then C1
and C2 attended with Joey. Any unattended stage first passes attended with the same code, config and hardware; C5 stays
attended. The stage runner can't change limits, flash firmware, power-cycle drives or Set Zero outside the reference workflow.
Camera timestamps use the runtime's clock. Calibration summaries are committed to this repo's `docs/calibrations/`; raw MCAP
stays on the Pi or storage, referenced by hash. **Done when** C0 to C2 pass attended and one C3 run passes unattended.

## 10. Power board interface (milestone 4)

Not built before milestone 4; when it is, the sim drive gains a power-board model first. Requirements:
[STATUS.md, power board section](https://github.com/jaylamping/marengo/blob/main/hardware/STATUS.md#power-board-and-battery-what-software-must-do) and
[REV_B_PARTS.md](hardware/power-board/REV_B_PARTS.md#accepted-risks-and-software-requirements-joey-2026-11-07-rev-b5-rows-marked):

- Heartbeat toggled every 50 to 100 ms from the same health decision that feeds the systemd watchdog, never from its own timer;
  a falling edge at least every 270 ms or the latch drops and needs a manual reset.
- E-stop input is information only; software never sits in or delays the hardware E-stop path.
- Port-fault reporting that names the port; INA237 meters on one I²C controller (limb shunts 2 mΩ).
- Refuse enable while the BMS shows charge current or its telemetry is stale; no drive load until the bus is above 45 V; shut
  compute down at min cell ≤ 3.0 V, filtered pack ≤ 38 V, or BMS telemetry lost for more than 5 s.
- Self-test only with VBUS below 3 V, at least 5 s after the last stop, pack at least 40 V; tell the operator to wait for VBUS below
  3 V before pressing reset.
- Brake clamp caps: 30 W average over 60 s until the heat test, 3 kJ per burst. Brown-out budget per STATUS.md.
- **Power-fail warning:** `PWR_FAIL_N` (J21 pin 8, active low, open drain, pulled up to the Pi's 3.3 V) goes low when the pack
  falls under 31.4 V and re-arms at 34.4 V. Read it as an edge-triggered GPIO. On assert, run the one shutdown path in
  [deploy.md](conventions/deploy.md): stop the motors, record the event, close the recording, sync, remount data read-only,
  power off. There is no hold-up capacitance, so a sudden total loss (pulled plug, BMS trip) gives only about 70 µs: the
  software low-pack rules above act first on a draining pack, and `PWR_FAIL_N` is the backstop. ext4 journaling covers the
  rest. Prove the shutdown order on `vcan`.
- The battery's VBUS window replaces the bench one through the skeleton's `power` block.

## Observability (tenet 8)

**Decided now, needed from the first `vcan` run:**

- **One session** is one runtime start to stop, in one directory `/var/lib/robot/sessions/<UTC start>/`: one MCAP file (raw frames per bus
  `{bus, id, dlc, data, t_kernel, t_mono, dir}`, decoded joint state, commands, injected faults, events: state changes, stops,
  limit hits, operator actions with the client's identity) and `session.json` (skeleton file and hash, git revision, operator,
  stage).
- **Black box:** `candump -L` per bus as its own systemd service, to `/var/lib/robot/candump/<bus>-<UTC>.log`, independent of the runtime.
- **Logging runs inside the runtime on a non-realtime thread**, fed by a lock-free ring. When full it drops and counts. It can
  fail without affecting motion (tenet 5); see the logging row in §6.
- **One clock:** the Pi disciplined by chrony; MCAP carries kernel CAN timestamps and monotonic time; the Jetson joins via chrony
  when it exists.

**Deferred until the test stand soak needs dashboards:** a metrics exporter (missed replies, latency, bus errors, temperatures)
to Prometheus and Grafana, with node_exporter for host metrics. Foxglove reads MCAP as is. Sentry, OpenTelemetry and Rerun are
evaluated only against a named need.

## Rules that hold for every item

- **No spare actuators.** Nothing overloads, overheats or stalls a real drive. Destructive tests use printed dummies.
- **Stationary and supported** until legs exist. The arm may drop onto the foam pad when a run stops hard; that's accepted.
- **The bench supply has no current limit.** 3 A fuse for first power-up, 10 A after.
- **No pointless tests** (tenet 6); see [conventions/testing.md](conventions/testing.md).
- Every item has a "Done when". An item without one isn't finished being specified; ask before building it.

## Before the legacy code is deleted (milestone 2)

1. Add the right arm to the skeleton: `can0`, IDs 1 to 5, directions from `marengo/config/motors.yaml` (sign-checked
   2026-08-11), hard limits from its bench envelopes. The envelopes are relative to the legacy reference, so re-reference
   before trusting them.
2. Don't carry the `control.yaml` gains: the RS03 gains were tuned while the drive saw 0.4 × the commanded velocity. Friction
   fits move to `config/dynamics.yaml` only after a re-check. `right_lower_arm_yaw`'s URDF axis is wrong (`kinematics.md`).
3. Give `can0` its own adapter with its own link file and retire the HAT; rewrite `canTimeout` from 600 to 1000; run the sign check
   and C1 again.
4. Keep the `gravity-fit` and `firmware-timing` tools' logic and the commissioning docs. Then Joey (or an agent he assigns in
   marengo) deletes per the
   [reconciled table](https://github.com/jaylamping/marengo/blob/main/review/sw-foundation-20261108/RECONCILIATION.md#verdict-per-component-majority-of-six)
   and sweeps stale references to deleted crates and old names from marengo's docs.

## Open with Joey

Defaults apply until Joey answers.

1. **Zero persistence and reference poses.** Default: treat the drive zero as volatile until the persistence test (§1) says
   otherwise; reference poses documented per joint in the skeleton.
2. **HAT during milestone 1.** Default: keep the HAT fitted for the right arm on `can0`; disable its `can1` and give that name
   to the USB adapter.
3. **Right arm at milestone 2.** Default: its own adapter; retire the HAT.
4. **Bus names for the waist and legs.** Default: ADR 0001 ID blocks; buses `can2` to `can4` named by the hardware ADR when it
   lands.
5. **Who may enable and clear.** Default: a human at the CLI or UI; agents plan, run on `vcan`, start approved plans and stop.
6. **Real fault tests at milestone 1** (pull a drop fuse, unplug the adapter while enabled). Default: yes, attended, loose drives,
   neutral MIT.
7. **Fault recovery.** Default: power-cycle only; no type-4 fault-clear.
8. **One legacy-stack capture for the RS00 scales on the right arm.** Default: yes, candump only, Joey present.
9. **Realtime budget.** Default: 0.5 ms tick-start jitter, 99.9 % of replies before the collect deadline, 1 h soak.
10. **Operator UI at milestone 1.** Default: none; CLI and agent tools only.
