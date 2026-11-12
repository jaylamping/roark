# CAN layer and codec conventions

**Status:** proposed for Joey's review, 2026-11-08.

CAN is the most important data stream in the robot, so it should be the most trusted code (tenet 5). What the layer does
(threads, tick, timing budget, stable bus names, who transmits, scan and identity) is in
[PLAN item 3](../PLAN.md#3-the-new-can-layer-tenet-5). The sequences and the transmit allowlist are in
[PLAN item 2](../PLAN.md#2-lift-the-hard-won-knowledge-first). The stack choice comes from
[can-stack-for-marengo.md](https://github.com/jaylamping/marengo/blob/main/hardware/docs/research/can-stack-for-marengo.md).
Realtime rules for any loop are in [rust.md section 6](rust.md#6-the-realtime-loop-rt).

New to CAN? Read [docs/can-primer.md](../docs/can-primer.md) first.

This page is **how the code in `robstride` and `can` is written and reviewed**. It draws on how other maintained projects do it
(listed at the end).

## 1. The codec (`robstride`)

### Shape

- **Sans-IO, no allocation, no clock.** Functions take bytes or typed values and return the other. No sockets, no threads, no
  `Instant::now()`, no logging. **Why:** the codec is then a pure function you can test exhaustively, fuzz, and run unchanged
  in the runtime, `sim-drive`, `robot-cli` and replay tools. mjbots' `moteus-protocol` crate and Foxglove's MCAP reader are
  built the same way.
- **Build a frame separately from sending it.** `encode_enable(id) -> Frame`, never `enable(socket, id)`. The bus thread
  batches the frames for one tick and sends them.
- **One typed table per manual table.** Communication types, parameter indexes (0x70xx), fault bits and per-model scales are
  each one table, written with a `macro_rules!` table macro if that reads better (rust.md section 11). Each row cites the
  manual and section it came from.
- **State the protocol rules once,** at the top of the crate: byte order, the 29-bit ID layout, what reserved bits must be on
  transmit (zero) and how they're treated on receive (ignored), how a reply is matched to a request.

### Strict both ways

- **Encode refuses, never clamps.** An out-of-range or non-finite value is an error naming the field and the range (PLAN
  item 3). **Why:** a silent clamp turns a bug upstream into a different motion than anyone asked for.
- **Decode never panics.** Any 8 bytes and any ID decode to a typed frame or a typed error (`UnknownType`, `BadLength`,
  `ReservedBitsSet`, ...). No indexing that can go out of bounds, no `unwrap`. **Why:** everything on the bus is outside
  input; a panic in the bus thread stops the robot.
- **Replies are matched by bus, device ID and communication type,** and checked against the drive the skeleton expects (UID
  once commissioned). Never by device ID alone. **Why:** the K-Scale RobStride crate matched by ID only, which mixes up two
  drives with the same ID on different buses.
- **Per-model scales are constants** with their manual citation. A model the codec can't vouch for (RS00 until its scales are
  settled, PLAN item 2) is refused at encode.

### Tests (per [testing.md](testing.md))

- **Exact-byte vectors from the manuals:** one table-driven test per frame type, each row `(input, expected bytes)` with the
  manual page. Bench captures are added as rows with their session ID.
- **Round-trip property test:** for any valid typed frame, `decode(encode(x)) == x`.
- **Malformed-input test:** a table of bad frames (wrong length, unknown type, reserved bits set) and the error each must give.
- **Fuzz target** on decode: never panics, never hangs. Run before each milestone (zenoh runs codec fuzzing on a schedule).

## 2. The bus layer (`can`)

### Socket setup

Every socket is opened by one function that sets, and logs at startup, all of:

- **Error frames on** (`CAN_RAW_ERR_FILTER` with the full mask). They're off by default, and without them bus-off and error
  counters are invisible.
- **No kernel ID filter.** The socket takes every ID, so a frame from another host or from an ID the skeleton doesn't have
  is seen, counted and recorded instead of dropped unseen by the kernel. The session records the empty filter list.
  **Why:** a duplicate sender is exactly the frame a filter would hide (see Transmit).
- **Loopback left on.** It's how the `candump` black box sees what the runtime sent. Turning it off blinds the black box.
- **Kernel timestamps** on every frame (`SO_TIMESTAMPNS_NEW`, 64-bit time), recorded with it, and the overflow counter
  (`SO_RXQ_OVFL`). Hardware timestamps are requested once the real adapter is supported (PLAN step 8); the startup check
  logs whether the adapter provides them. Reply ages and matching use the monotonic time the bus thread read the frame,
  never the recorded wall-clock stamp, which can step.

Interface settings (bitrate, sample point, TX queue length, restart) are applied by `deploy/` link setup, not by the runtime,
and the runtime **checks** them at start (driver, bitrate, sample point, state) against the skeleton and refuses to run a bus
that doesn't match. **Why:** bit timing left to defaults is the classic cause of an error-prone bus (kernel SocketCAN docs).

### Transmit

- **Every frame has a deadline** (its tick). A frame that can't go out by then is dropped and counted, never sent late.
  **Why:** a late motion command is a wrong motion command. ArduPilot's and libcanard's CAN drivers follow the same rule.
  Disable and active reporting off are the exception, whether a stop or control planned them: they go out late rather
  than not at all, because a late Disable is still the right one. The deadline bounds handing the frame to the kernel,
  not its transmission: a frame the socket took can still wait in the adapter's queue. Measure that wait on the real
  adapter before the first Enable (PLAN step 8).
- **No busy retry.** On `ENOBUFS` or `EAGAIN` the frame is dropped and counted, and the tick goes on. Never loop on
  `write` in the bus thread. Never raise `txqueuelen` to make `ENOBUFS` go away: it hides a bus problem (a linux-can thread
  traced exactly this to a duplicate sender).
- **Only frames on the allowlist** (PLAN item 2) can be built for transmit; the check lives in the codec so nothing else can
  bypass it. `can-bench` is outside this rule: it never links the codec and sends only its own frames, which no drive
  acts on, on a bus with no drive.
- **A TX echo isn't proof the frame reached the wire** (PLAN item 3). Latency in the recording is measured from the
  kernel RX timestamps of replies, and liveness from replies, never from echoes.

### Receive

- **Receive with a deadline,** and a timeout is its own typed result, separate from I/O errors. **Why:** "no reply yet" is
  normal and counted; "socket gone" is a stop.
- **Bounded everything.** RX buffers, queues to the non-realtime side and `sim-drive`'s queues are fixed-size. When one fills,
  the drop is counted and reported; nothing grows. **Why:** an unbounded queue hides overload until memory runs out (python-can's
  virtual bus is unbounded by default; ours isn't).
- **Liveness comes from replies to commands,** not from any traffic on the bus. A drive is alive if it answered this tick's
  command.
- **The tick matches replies and ages feedback on the monotonic time the bus thread read the frame;** the recording
  carries the kernel RX stamp. **Why:** the kernel's stamp is wall-clock and can step.

### Errors and bus-off

- **Bus errors are a typed enum** (`BusOff`, `ErrorPassive`, `ErrorWarning`, `RxOverflow`, `TxTimeout`, `InterfaceDown`,
  `InterfaceGone`, ...), matched exhaustively.
- **Latch on the first bus-off error frame, or any socket read or write failure other than a full queue,** and stop every
  run on that bus, as [PLAN item 3](../PLAN.md#3-the-new-can-layer-tenet-5) and item 6 say. The latch lives in software because the adapter may bring the bus back by itself (PLAN item 3 has the
  details and sources). Code never treats "the interface is up again" as permission to continue.
- **Error counters and drops are metrics** (per bus: bus errors, error-passive, bus-off count, RX overflow, TX drops, late
  ticks), exported every second and shown in the UI.

### Stops and the schedule

- **A stop names its scope.** A fault, a drop out of Run, a silent drive or motion on expired feedback stops that
  drive's limb; a bad batch, a stop order naming a limb the bus doesn't have, control going silent, an operator's bus
  stop or a bus error stops every limb on the bus not already stopping or stopped; a late wake or a backlog stops every
  active limb on the bus (an idle limb has nothing running to stop). **Why:** the affected limb stops
  ([architecture.md](architecture.md)), and the other arm on the same bus has done nothing wrong; a batch or a bus that
  can't be trusted is trusted for no limb.
- **Check before every send.** What the drain read before the send is checked before the tick's commands go out, so a
  fault read in the slack stops its limb on that tick, not the next ([safety.md section 3](safety.md#3-how-a-rule-is-written)).
- **Only an operator clear re-arms,** and only a stopped limb whose drives are known disabled (confirmed in Reset, or sent
  nothing for longer than the drive timeout). A latched bus error is never re-armed in place: the bus thread and socket
  are rebuilt. Nothing in the bus layer re-arms itself.
- **Slow requests ride in the slack,** one in flight per bus, sent after the collect deadline only when the reply fits
  before the next tick starts, never on a tick whose reads can't be trusted, never to a limb the veto would stop or
  while control is silent, and writes only to an idle limb's drive with no command of that tick unanswered. A request
  waits queued only a bounded number of ticks. The bus produces exactly one result for every request, including when the
  thread ends, and retries none; a result control's full ring can't take is dropped and counted, and the requester times
  out. **Why:** a parameter read must not crowd out a command. A write's answer is a plain status, like a command's, so
  a write goes only where the two are least likely to be mixed up; a late status can still be taken for the other (both
  ways are in the [`can` README](../crates/can/README.md), Slow requests), so a write's result proves nothing about the
  value and preflight reads every write back. Since `canTimeout` counts from any frame, slow traffic must never keep a
  stopped drive alive.
- **One schedule for every bus.** Every bus thread and the control thread tick from the one origin the runtime picks, so
  tick n is the same instant everywhere.

### Logging

- **Every frame in and out goes to the recorder** through the bus thread's ring; the bus thread never writes files. How frames
  are batched, buffered, written, rotated and checked against `candump` is in
  [logging.md section 8](logging.md#8-can-frame-logging).
- **Injected faults are logged as such** in sim, so a replay shows what was real and what was injected.

## 3. Simulation and tests

- **`sim-drive` uses the same codec** and the same bus names (PLAN item 4), so the runtime runs unchanged.
- **Faults are seeded and deterministic** ([testing.md rule 6](testing.md#rule-6-no-sleeping-no-wall-clock)). A failing sim
  test prints its seed and commit so it replays exactly (TigerBeetle's simulator does the same).
- **`vcan` doesn't model the physical bus:** no arbitration, no error counters, no real bus-off. `sim-drive` injects those
  faults itself (a bus-off error frame, an interface going down). Real bus behaviour is checked on the bench soak (PLAN item 5).
- **`vcan` tests run in CI.** If a hosted runner can't load `vcan`, they run on a self-hosted runner or the Pi, never skipped
  (PLAN). (socketcan-rs keeps its `vcan` tests out of CI; we don't.)
- Hand fault tools from `can-utils` (`canerrsim`, `cansend` of error frames, `canbusload`) are fine for exploring on `vcan`;
  anything worth keeping becomes a `sim-drive` fault.

## 4. Review checklist for a CAN or codec PR

- Does any codec function do I/O, allocate, read the clock or panic on input?
- Does encode clamp anything? Does decode index without a bounds check?
- Is every new frame or parameter in its table with a manual citation and a byte vector?
- Can anything send a frame without a deadline, retry in a loop, or block the bus thread?
- Is every queue bounded, and every drop counted?
- Is any bus-off or interface error handled by anything other than stop and latch?
- Does every new stop name its scope (the limb or the whole bus), and can anything but an operator clear re-arm one?
- Are error frames on, loopback on, and the (empty) filter list recorded?

## Sources

How other projects handle the same problems, read 2026-11-08:

- mjbots `moteus-protocol` (sans-IO, `no_std`, exact-byte tests, build vs send): https://docs.rs/moteus-protocol/latest/moteus_protocol/
- Linux SocketCAN docs (error frames off by default, loopback, bit timing, bus-off): https://docs.kernel.org/networking/can.html
- candleLight firmware (bus-off auto-restart after 100 ms, echo timing): https://github.com/candle-usb/candleLight_fw
- Linux `gs_usb` driver (10 TX URBs, no host bus-off recovery): https://github.com/torvalds/linux/blob/master/drivers/net/can/usb/gs_usb.c
- socketcan-rs (error filter, timestamps in one `recvmsg`, `vcan` tests out of CI): https://github.com/socketcan-rs/socketcan-rs
- ODrive CANSimple (byte order and reserved fields stated once; watchdog fed only by setpoints): https://docs.odriverobotics.com/v/latest/manual/can-protocol.html
- ArduPilot CAN driver roadmap (TX deadlines): https://ardupilot.org/dev/docs/can-bus-driver-roadmap.html
- cantools strict encoding: https://cantools.readthedocs.io/en/latest/
- Autoware ros2_socketcan (candump-syntax filters, typed receive timeout): https://github.com/autowarefoundation/ros2_socketcan
- zenoh codec fuzz targets and malformed-input tests: https://github.com/eclipse-zenoh/zenoh/tree/main/commons/zenoh-codec
- linux-can thread on `txqueuelen` hiding a bus-off cause: https://lore.kernel.org/all/CAFoRp-PSPtdenVSihp+Ar-1xfsOQd1M6rrUN6kgMOGd2egCcoA@mail.gmail.com/T/
