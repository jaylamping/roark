# can

The bus layer: one bus's tick, which sends control's commands on a fixed schedule, reads every frame the socket
delivers, and publishes what each drive last said and how fresh it is (PLAN item 3, can.md section 2).

## What it does

Each tick, on the monotonic clock (the steps the bus thread's shell runs around `BusTick`):

1. **Wake** at the tick's scheduled start (`clock_nanosleep`, absolute). Waking later than the send window is a missed
   deadline and stops the bus.
2. **Drain** the socket, so any frame read after the send arrived after it.
3. **Plan** with `BusTick::begin`: the newest `CommandBatch` from control, only if it is for this tick and unexpired.
   A stale or missing batch sends nothing; two silent ticks on an active bus stop it. An MIT frame to a drive whose
   fresh status is older than three periods is refused and stops the bus.
4. **Send** each planned frame once, before the send window closes, and feed the outcome back (`sent`). A full queue
   drops the frame and counts it; it is never retried.
5. **Collect** until the collect deadline (about 60 % of the period), feeding each frame to `on_frame`.
6. **Publish** the `Snapshot` (`end`) to control and hand every frame of the tick to the recorder.

A drive's status read after a command the socket took is its **fresh** status, and it **answered** the tick if read by
the collect deadline. That is evidence the drive is there and what state it was in, never an acknowledgement: there
are no sequence numbers to prove which command a status answers. Faults are never filtered: any status, report or
fault frame updates what the drive was seen saying and latches `fault_seen`.

A stop (requested, control silent, a late wake, expired feedback, a bad batch, a backlog, or a latched bus error such
as bus-off) sends Disable to every drive and active reporting off once, then re-sends Disable each tick to every drive
that hasn't confirmed. A drive confirms with a Reset-mode status read after its Disable. The bus is `Stopped` once all
have confirmed, or after 100 ms.

`BusTick` holds all of that as plain values with time passed in, so it runs and is tested without a socket. The
Linux shell that owns the socket and the clock comes next (PLAN step 6).

## Must never

Send a frame late, retry one, or re-send a stale batch. Treat a TX echo or any traffic as proof a drive is alive.
Allocate, lock, log or wait without a deadline in the tick. Let a stop be undone: a stopping bus refuses every batch,
and a latched bus error stays latched.

## Talks to

`robstride` for the frames (it builds them, this crate only sends `Frame`s) and `telemetry` for the frame records the
recorder stores. Control will sit on the other side of two queues, batches in and snapshots out; neither it nor the
socket shell exists yet, so today only the tests drive `BusTick`. See the
[map](https://github.com/jaylamping/roark/blob/main/conventions/architecture.md).

## Using it

Build a `BusTick` with the bus's drives in slot order, then per tick: `begin`, write each send and report it with
`sent`, feed every frame read with `on_frame`, and `end` for the snapshot.

```rust
use can::{BusState, BusTick, CommandBatch, SendOutcome, Timing};
use robstride::drive;
use robstride::{
    Celsius, DeviceId, Drive, Feedback, Mode, Model, NewtonMeters, RadPerSec, Radians, StatusFaults, encode,
};
use telemetry::{Direction, FrameRecord};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let shoulder = DeviceId::new(11)?;
    let timing = Timing::at_hz(250);
    let mut bus = BusTick::new(&[shoulder], timing)?;

    // Tick 0 starts at 0 ns. Control's batch enables the shoulder and is good until the next tick.
    let mut batch = CommandBatch::new(0, timing.period_ns);
    assert!(batch.set(0, encode::enable(shoulder)));
    let sends = bus.begin(0, 0, 0, Some(&batch));
    assert_eq!(sends.len(), 1);
    bus.sent(0, SendOutcome::Sent);

    // 1 ms later the drive's status arrives: Run mode, no faults.
    let at_rest = Feedback {
        position: Radians::new(0.0).ok_or("position")?,
        velocity: RadPerSec::new(0.0).ok_or("velocity")?,
        torque: NewtonMeters::new(0.0).ok_or("torque")?,
        temperature: Celsius::new(25.0).ok_or("temperature")?,
    };
    let status = drive::status(Drive::new(shoulder, Model::Rs03), Mode::Run, StatusFaults::default(), &at_rest)?;
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
    assert_eq!(snap.state, BusState::Active);
    let shoulder_view = snap.drive(0).ok_or("slot 0")?;
    assert!(shoulder_view.answered);
    assert_eq!(shoulder_view.fresh_ns, Some(1_000_000));
    Ok(())
}
```
