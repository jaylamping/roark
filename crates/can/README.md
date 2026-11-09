# can

The bus layer: one thread per CAN bus that sends control's commands on a fixed tick, reads every frame the socket
delivers, and publishes what each drive last said and how fresh it is (PLAN item 3, can.md section 2). The drives on
a bus are grouped into **limbs**, each its own index on that bus, and a stop names its scope: one limb or the whole bus.

## What it does

Each tick, on the monotonic clock:

1. **Wake** at the tick's scheduled start (`clock_nanosleep`, absolute). Tick numbers count from one origin the runtime
   gives every bus thread and the control thread (`BusLinks::start`), so tick n is the same instant on every bus; a
   thread started after the origin begins at the first tick not yet due. Waking later than the send window is a missed
   deadline and stops the bus; ticks a stall slept through are skipped, each counted as a missed deadline, and stop the
   bus the same way.
2. **Drain** the socket to empty, so what is read after the send came after the backlog. It is not a strict barrier:
   a frame landing between the drain and the write counts as after it, which is still evidence of the drive then.
3. **Check** what the drain read, before anything is sent: a drive of an idle or active limb that shows a fault, has
   left Run after it was seen in Run (latched when read, so a later Run status can't hide it), or has left
   `silence_misses` (3) commands in a row unanswered stops its limb now (`DriveFault`, `DriveMode`, `DriveSilent`, each
   naming the slot), so no command, Enable included, goes to it this tick. A Disable from control isn't leaving Run:
   its Reset answer is expected. A drive this host never enabled isn't watched for mode: preflight refuses one found
   already in Run.
4. **Plan** with `BusTick::begin`: the newest `CommandBatch` from control, only if it is for this tick and unexpired.
   A stale or missing batch sends nothing; two silent ticks while a limb runs stop the bus. A batch carries only motion,
   Enable, Disable and the enable sequence's reporting off and `run_mode` = MIT write; anything else (Set Zero, set-ID,
   other parameter traffic) is a bad batch and stops the bus. An MIT frame to a drive whose fresh status is older than
   three periods is refused and stops its limb. A batch's frames for a stopping or stopped limb are dropped and counted
   (`refused_frames`); the other limbs' frames still go.
5. **Send** each planned frame once and feed the outcome back (`sent`). A command goes out only before the send
   window closes; a Disable or reporting off goes out even late, whoever planned it, since late it is still the right
   one. A full queue drops the frame and counts it; it is never retried within the tick.
6. **Collect** until the collect deadline (about 60 % of the period), feeding each frame to `on_frame`.
7. **Publish** the `Snapshot` (`end`) to control and hand every frame of the tick to the recorder.

A drive's status read after a command the socket took is its **fresh** status, and it **answered** the tick if read by
the collect deadline. That is evidence the drive is there and what state it was in, never an acknowledgement: there
are no sequence numbers to prove which command a status answers. Faults are never filtered: a status or report
updates what the drive was seen saying, and any status, report, version reply or type-21 fault report with a fault set
latches `fault_seen`. Missing replies aren't counted toward a drive's silence for an Enable or Disable, for anything
sent to a drive this host hasn't enabled (which covers the post-Disable silence, however long), or for the first
`ENABLE_TO_RUN_NS` (50 ms) after an Enable while the drive hasn't shown Run: the drive may take 10 ms to reach Run, and
goes silent after a Disable (PLAN item 2 Silence windows). `silent_ticks` and `silence_misses` must be at least one and
must fire before the drives' own timeout, or the bus is refused at startup. Each drive's last echo of this host's frame
to it (`last_echo`: its kind and when it was read) is kept, for the enable sequence's "reporting-off echo plus one
tick".

A limb stop (`stop_limb`, named `LimbRequested`; the check above; expired feedback) stops that limb; a bus stop (`request_stop`, control
silent, a late wake, a bad batch, or a backlog) stops every limb. A stopping limb sends Disable to each of its drives,
re-sends it each tick to every drive that hasn't confirmed, and sends active reporting off to each confirmed drive once
its post-Disable silence is over (50 ms after its confirmation), again each tick until the socket takes it. A drive
confirms with a Reset-mode status read after the stop's Disable; one that never confirms is still getting a Disable
every tick of the 100 ms confirm window, so it gets no reporting off. Every Disable goes out ahead of every reporting
off. The limb is `Stopped` once every drive has confirmed and taken its reporting off, or once the window has passed
and no confirmed drive still waits for its reporting off (at most the window, the 50 ms silence and a period). The
first reason a limb stopped for stays in its `LimbView`.

A late wake, ticks a stall slept through, or a backlog stop every active limb; an idle limb has nothing enabled, so
it only counts the missed deadline. A late tick sends no batch.

A latched bus error (bus-off, interface down or gone, another socket error) sends nothing: there is no bus to send on, so every limb is
`Stopped` at once and the drives time out on their own (`canTimeout`). The first such error stays in every snapshot's
`bus_error`, even if a stop was already under way; `healthy` is false while there is one or the controller is
error-passive.

Only the operator's clear undoes a stop: `rearm(limb, now)` makes a `Stopped` limb idle again, with a new
`generation`, its drives' stop outcomes, fault history (`fault_seen`) and miss counts started afresh. It is refused
while the bus has a latched error (that bus is rebuilt instead), while the limb is running or still stopping, and until
every drive in it is known disabled: confirmed in Reset by the stop, or sent nothing for longer than the drives' 50 ms
timeout plus a period since the socket took its last frame (stamped when it was written, so a late Disable counts from
when it went). Each drive needs a fresh preflight before it is enabled again; that is the safety layer's.

`BusTick` holds all of that as plain values with time passed in, so it runs and is tested without a socket. It refuses
a drive table past `MAX_DRIVES`, a drive listed twice, a limb index past the table, and timing that breaks its
promises (`Timing::check`: for one, three periods must fit inside the drives' 50 ms timeout, so the rate is at least
61 Hz). The Linux shell (`spawn`) owns the socket: it
opens only `vcan` until the real adapter is supported (PLAN step 8), takes every ID (no kernel filter), and reads each
frame with its kernel timestamp, its direction and the overflow count in one `recvmsg`. `bus_info` is the session's
record of that socket, from the same constants `open` applies, and `spawn` returns the receive buffer the kernel
actually gave (`Spawned::receive_buffer_bytes`) for the runtime's startup log. Each tick's recorded batch is `valid`
while the bus is healthy, the exit tick's included, and a snapshot control's full ring can't take is counted
(`snapshots_dropped`). Any write error but a full queue loses the bus, as a read error does. Setting `exit` while a
limb is running or stopping stops the bus first.

Not yet: the `/can/<bus>/tx_intent` record of every frame handed to the socket or not sent, with the reason
(logging.md section 8.2), and the per-run tick duration and jitter (rust.md section 6). Both come with the runtime,
which owns the recording's channels and the metrics, before step 8 measures latency and jitter on the real adapter.

## Must never

Send a command late, retry one, or re-send a stale batch. Treat a TX echo or any traffic as proof a drive is alive.
Allocate, lock, log or wait without a deadline in the tick, or take a lock shared with non-realtime code. Let anyone
but the runtime transmit. Undo a stop on its own: a stopping or stopped limb gets none of control's frames until the
operator's `rearm`, and a latched bus error stays latched. Open an interface that isn't `vcan` before the real
adapter's checks exist (PLAN step 8).

## Talks to

`robstride` for the frames (it builds them, this crate only sends `Frame`s) and `telemetry` for the recording: each
tick's frames go to a `BusRecorder`. Control is on the other side of two `rtrb` queues, batches in and snapshots out.
The runtime that wires those up doesn't exist yet; the sim suite drives the shell against `sim-drive` on `vcan`. See
the [map](https://github.com/jaylamping/roark/blob/main/conventions/architecture.md).

## Using it

Build a `BusTick` with the bus's drives in slot order, each with its limb, then per tick: empty the socket, feeding
each frame to `on_frame`, and report how the drain went with `drained`; `begin`, write each send and report it with
`sent`; feed every frame read with `on_frame`; and `end` for the snapshot. `request_stop` and `stop_limb` ask for a stop
at the next `begin`, `skipped` counts ticks a stall slept through, and `lost_bus` latches every limb stopped when the
socket fails. On Linux, `spawn` runs exactly that on a socket.

```rust
use can::{BusDrive, BusTick, CommandBatch, LimbState, SendOutcome, Timing};
use robstride::drive;
use robstride::{
    Celsius, DeviceId, Drive, Feedback, Mode, Model, NewtonMeters, RadPerSec, Radians, StatusFaults, encode,
};
use telemetry::{Direction, FrameRecord};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let device = DeviceId::new(101)?;
    let timing = Timing::at_hz(250);
    let mut bus = BusTick::new(&[BusDrive { device, limb: 0 }], timing)?;

    // Tick 0 starts at 0 ns. Control's batch enables the drive and is good until the next tick.
    let mut batch = CommandBatch::new(0, timing.period_ns);
    assert!(batch.set(0, encode::enable(device)));
    let sends = bus.begin(0, 0, 0, Some(&batch));
    assert_eq!(sends.len(), 1);
    bus.sent(0, SendOutcome::Sent, 0);

    // 1 ms later the drive's status arrives: Run mode, no faults.
    let at_rest = Feedback {
        position: Radians::new(0.0).ok_or("position")?,
        velocity: RadPerSec::new(0.0).ok_or("velocity")?,
        torque: NewtonMeters::new(0.0).ok_or("torque")?,
        temperature: Celsius::new(25.0).ok_or("temperature")?,
    };
    let status = drive::status(Drive::new(device, Model::Rs03), Mode::Run, StatusFaults::default(), &at_rest)?;
    let read = FrameRecord {
        id: status.id(),
        extended: true,
        error: false,
        remote: false,
        len: 8,
        data: status.data(),
        stamp_ns: 0,
        direction: Direction::Rx,
    };
    bus.on_frame(1_000_000, &read);

    let snap = bus.end(timing.collect_ns);
    assert_eq!(snap.limb(0).ok_or("limb 0")?.state, LimbState::Active);
    let view = snap.drive(0).ok_or("slot 0")?;
    assert!(view.answered);
    assert_eq!(view.fresh_ns, Some(1_000_000));
    Ok(())
}
```

The `vcan` run against `sim-drive`, with its recording checked frame by frame against `candump`, is in the sim suite
(`crates/sim-suite/tests/bus.rs`).
