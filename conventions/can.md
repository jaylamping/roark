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
- **Kernel filters** for the IDs that bus expects, written once and logged in candump syntax so a person can read them.
- **Loopback left on.** It's how the `candump` black box sees what the runtime sent. Turning it off blinds the black box.
- **Hardware timestamps** requested; the startup check logs whether the adapter provides them.

Interface settings (bitrate, sample point, TX queue length, restart) are applied by `deploy/` link setup, not by the runtime,
and the runtime **checks** them at start (driver, bitrate, sample point, state) against the skeleton and refuses to run a bus
that doesn't match. **Why:** bit timing left to defaults is the classic cause of an error-prone bus (kernel SocketCAN docs).

### Transmit

- **Every frame has a deadline** (its tick). A frame that can't go out by then is dropped and counted, never sent late.
  **Why:** a late motion command is a wrong motion command. ArduPilot's and libcanard's CAN drivers follow the same rule.
  Disable and active reporting off are the exception, whether a stop or control planned them: they go out late rather
  than not at all, because a late Disable is still the right one.
- **No busy retry.** On `ENOBUFS` or `EAGAIN` the frame is dropped and counted, and the tick goes on. Never loop on
  `write` in the bus thread. Never raise `txqueuelen` to make `ENOBUFS` go away: it hides a bus problem (a linux-can thread
  traced exactly this to a duplicate sender).
- **Only frames on the allowlist** (PLAN item 2) can be built for transmit; the check lives in the codec so nothing else can
  bypass it.
- **A TX echo isn't proof the frame reached the wire** (PLAN item 3). Latency is measured from RX timestamps of replies, and
  liveness from replies, never from echoes.

### Receive

- **Receive with a deadline,** and a timeout is its own typed result, separate from I/O errors. **Why:** "no reply yet" is
  normal and counted; "socket gone" is a stop.
- **Bounded everything.** RX buffers, queues to the non-realtime side and `sim-drive`'s queues are fixed-size. When one fills,
  the drop is counted and reported; nothing grows. **Why:** an unbounded queue hides overload until memory runs out (python-can's
  virtual bus is unbounded by default; ours isn't).
- **Liveness comes from replies to commands,** not from any traffic on the bus. A drive is alive if it answered this tick's
  command.

### Errors and bus-off

- **Bus errors are a typed enum** (`BusOff`, `ErrorPassive`, `ErrorWarning`, `RxOverflow`, `TxTimeout`, `InterfaceDown`,
  `InterfaceGone`, ...), matched exhaustively.
- **Latch on the first bus-off error frame** and stop every run on that bus, as [PLAN item 3](../PLAN.md#3-the-new-can-layer-tenet-5)
  and item 6 say. The latch lives in software because the adapter may bring the bus back by itself (PLAN item 3 has the
  details and sources). Code never treats "the interface is up again" as permission to continue.
- **Error counters and drops are metrics** (per bus: bus errors, error-passive, bus-off count, RX overflow, TX drops, late
  ticks), exported every second and shown in the UI.

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
- Are error frames on, loopback on, and filters logged?

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
