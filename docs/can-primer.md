# CAN in plain English

For anyone (Joey included) who knows web and JavaScript well and has never touched CAN. It explains enough to read
[conventions/can.md](../conventions/can.md), [logging.md section 8](../conventions/logging.md#8-can-frame-logging) and the
CAN parts of [PLAN.md](../PLAN.md), and to review a CAN PR without guessing. Facts about RobStride frames come from the
[RobStride manuals](https://github.com/jaylamping/marengo/blob/main/hardware/docs/robstride) (RS02 manual, section 4).

## 1. What a CAN bus is

A CAN bus is **two twisted wires (CAN-H and CAN-L) that every device on it is connected to**, daisy-chained, with a 120 Ω
resistor at each end. On Roark, each limb has its own bus: the Pi's USB-CAN adapter at one end, the limb's drives along it.

Think of it as **a group chat with no usernames**:

- **Everyone hears everything.** There's no "send to device 14". A message goes onto the wire and every device sees it. Each
  device decides from the message's ID whether it cares.
- **Messages have IDs, not senders or recipients.** CAN itself only knows "message with ID X". RobStride packs a target drive
  number and a message type *into* the ID (section 3), which is how "send to drive 14" is built on top.
- **Only one message at a time.** If two devices start talking at once, the one whose ID is numerically **lower** wins, without
  either message getting garbled, and the loser retries. So a lower ID means higher priority.
- **Messages are tiny.** At most **8 bytes of data**. Smaller than a tweet. That's why a whole motion command (position,
  velocity, two gains and a torque) has to be squeezed into scaled 16-bit integers.

Web analogy: it's less like HTTP (request to a specific server) and more like a single **WebSocket broadcast channel** where
every client gets every message and filters by a `type` field.

## 2. A frame

One CAN message is called a **frame**. It has:

| Part | Size | What it is |
|---|---|---|
| ID | 11 bits ("standard") or **29 bits ("extended", what RobStride uses)** | What the message is, which also sets its priority |
| Length (DLC) | 0 to 8 | How many data bytes follow |
| Data | 0 to 8 bytes | The payload |

Plus some bits the hardware handles for you: a checksum (CRC) and an **acknowledge bit**. Any device that received the frame
correctly sets the acknowledge bit. Note: that only means *someone* heard it intact, not that the drive you meant acted on it.
"Did drive 14 do it?" is answered only by drive 14's reply.

**Speed:** our buses run at **1 Mbit/s**. An extended frame with 8 data bytes is about 130 to 150 bits on the wire, so a bus
can carry at most about 6,600 frames a second. "Bus load" is how much of that we use; we aim to stay well under half.

## 3. How RobStride uses it

RobStride drives use 29-bit IDs split into three fields (manual section 4):

| Bits | Field | Example |
|---|---|---|
| 28 to 24 | **Communication type**: what kind of message | 1 = motion command, 2 = feedback reply, 3 = enable, 4 = stop, 17/18 = read/write a parameter |
| 23 to 8 | Extra data (meaning depends on the type) | the host's ID, or the torque for a motion command |
| 7 to 0 | **Target**: which drive (its CAN ID, 1 to 127) | 14 = `left_elbow_pitch` |

**The control loop, in one sentence:** 250 times a second, for every enabled drive, the Pi sends a **type 1 "motion" frame**
(target position, velocity, stiffness `kp`, damping `kd`, torque) and the drive answers with a **type 2 "feedback" frame**
(position, velocity, torque, temperature, plus fault and mode bits in the ID).

Each value is a 16-bit number scaled to a range the manual gives per model. For example, position `0..65535` means `−4π..+4π`
radians. The `robstride` codec does that conversion in one place, so nothing else ever sees raw numbers.

**The drive's safety timeout (`canTimeout`):** each drive is set to stop driving its motor (go limp) if it hasn't heard a
command for 50 ms. Web analogy: a WebSocket heartbeat where the server drops you if you miss a ping, except here "dropped"
means the arm goes limp and falls onto the foam pad. That's deliberate: if the Pi crashes, the drives stop on their own
(tenet 3).

## 4. When things go wrong

CAN hardware counts its own errors (bad checksums, nobody acknowledging, and so on) with two counters, and changes state as they
climb:

| State | Meaning |
|---|---|
| Error active | Normal |
| Error warning / error passive | Lots of errors; the device is being cautious |
| **Bus-off** | So many errors that the device has disconnected itself from the bus. Nothing in or out |

Bus-off is like a circuit breaker tripping: it protects the rest of the bus from a device that's misbehaving. For us it means
"this limb's bus is gone", so the software stops every run on that bus and stays stopped until a person clears it, even if the
adapter quietly reconnects (PLAN item 3).

Common causes on a bench: a missing or extra 120 Ω terminator, a loose connector, two drives with the same ID, or the wrong
bitrate.

## 5. CAN on Linux (SocketCAN)

Linux treats a CAN bus like a network card:

- Each bus is an interface, `can0` to `can4`, just like `eth0` or `wlan0`. `ip link` sets it up (bitrate and so on).
- Programs open a **socket** on it and read and write frames, much like a UDP socket.
- **`vcan`** is a virtual CAN interface with no hardware behind it, like `localhost`. Our simulated drive (`sim-drive`) talks on
  `vcan`, so the real runtime can run against it unchanged.
- The **USB-CAN adapter** (a candleLight board, driver `gs_usb`) is what turns USB on the Pi into CAN wires.

### `candump`: the network tab for CAN

`candump` prints every frame on a bus, like the Network tab in Chrome DevTools or `tcpdump`. With `-L` it writes a log line
per frame:

```
(1762590000.123456) can1 017FFF0E#7FFF7FFF00000000
```

| Piece | Meaning |
|---|---|
| `(1762590000.123456)` | When the frame was seen, in seconds since 1970 |
| `can1` | Which bus |
| `017FFF0E` | The 29-bit ID in hex: type `01` (motion), extra data `7FFF` (torque about 0), target `0E` = drive 14 |
| `7FFF7FFF00000000` | 8 data bytes: position about 0, velocity about 0, `kp` 0, `kd` 0. A "neutral" command that asks for no force |

We run one `candump` per bus all the time as a black box, separate from our own code.

## 6. Why CAN logging is a big deal

At 250 Hz, with about 6 drives on a bus, that's 6 commands and 6 replies every 4 ms, about **3,000 frames a second per bus** and
about **12,500 a second for the whole robot**. That's the chattiest data in the robot, and the most important for replay: from
the frames alone you can reconstruct exactly what every motor was told and what it said back.

So the rules in [logging.md section 8](../conventions/logging.md#8-can-frame-logging) exist to keep every one of those frames
without ever slowing the control loop down: the loop hands frames to a separate recorder thread through a fixed-size queue, the
recorder compresses and writes them, and if the queue ever fills, the loss is counted and reported rather than silently
ignored.

## 7. Glossary

| Term | Meaning |
|---|---|
| Bus | The pair of wires and every device on it. One per limb |
| Frame | One CAN message: ID, length, up to 8 data bytes |
| Extended ID | A 29-bit ID (RobStride's choice); standard IDs are 11 bits |
| Arbitration | How the bus decides who talks when two start at once: lower ID wins |
| Bus load | Share of the bus's capacity in use |
| Termination | A 120 Ω resistor at each end of the bus; without it signals reflect and errors pile up |
| Error frame | A special frame that reports a bus error; we turn on receiving them explicitly |
| Bus-off | A device has disconnected itself after too many errors |
| SocketCAN | Linux's CAN support: buses as network interfaces, frames through sockets |
| `vcan` | A virtual CAN bus in software, for simulation and tests |
| gs_usb / candleLight | The driver and firmware of our USB-CAN adapters |
| `candump` | Prints or logs every frame on a bus |
| MIT mode | RobStride's "motion control" mode (type 1 frames): position, velocity, `kp`, `kd`, torque in one frame |
| `canTimeout` | Drive setting: go limp after this long without a command (we use 50 ms) |
| Codec | Our code that turns frames into typed values and back (`robstride` crate) |
| MCAP | The file format our recorder writes; Foxglove opens it |
