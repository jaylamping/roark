# can

The bus layer: one bus's tick, which sends control's commands on a fixed schedule, reads every frame the socket
delivers, and publishes what each drive last said and how fresh it is (PLAN item 3, can.md section 2).

## What it does

Each tick, on the monotonic clock (the steps the bus thread's shell runs around `BusTick`):

1. **Wake** at the tick's scheduled start (`clock_nanosleep`, absolute). Waking later than the send window is a missed
   deadline: it stops an active bus. It doesn't stop an idle bus, which sends only its batch's Disables and reporting
   off that tick and holds the rest; the batch checks in step 3 still apply.
2. **Drain** the socket to empty, so what is read after the send came after the backlog. It is not a strict barrier:
   a frame landing between the drain and the write counts as after it, which is still evidence of the drive then.
3. **Plan** with `BusTick::begin`: the newest `CommandBatch` from control, only if it is for this tick and unexpired.
   A stale or missing batch sends nothing; two silent ticks on an active bus stop it. A batch carries only motion,
   Enable, Disable and the enable sequence's reporting off and `run_mode` = MIT write; anything else (Set Zero, set-ID,
   other parameter traffic) is a bad batch and stops the bus. An MIT frame to a drive whose fresh status is older than
   three periods is refused and stops the bus.
4. **Send** each planned frame once and feed the outcome back (`sent`). A command goes out only before the send
   window closes; a Disable or reporting off goes out even late, whoever planned it, since late it is still the right
   one. A full queue drops the frame and counts it; it is never retried within the tick. Any other socket write
   failure goes to `lost_bus`, which latches the bus stopped, as well as to `sent` as `Failed`; `Failed` on its own
   records only that the frame wasn't taken and never latches.
5. **Collect** until the collect deadline (about 60 % of the period), feeding each frame to `on_frame`.
6. **Publish** the `Snapshot` (`end`) to control and hand every frame of the tick to the recorder.

A drive's status read after a command the socket took is its **fresh** status, and it **answered** the tick if read by
the collect deadline. That is evidence the drive is there and what state it was in, never an acknowledgement: there
are no sequence numbers to prove which command a status answers. Faults are never filtered: a status or report
updates what the drive was seen saying, and any status, report, version reply or type-21 fault report with a fault set
latches `fault_seen`. Missing replies to Enable and Disable aren't counted as unanswered: the drive may take 10 ms to
reach Run, and goes silent after a Disable (PLAN item 2 Silence windows).

A drain that reads past its limit or leaves frames queued is a backlog: what it said can't be known in time, so it
stops an active bus. As for a late wake, it doesn't stop an idle bus, which sends only its batch's Disables and
reporting off that tick (`held_batches`); the batch checks still apply. On such a held tick no drive's status counts
as fresh, so motion waits for a status read on a tick that can be trusted.

A stop (requested, control silent, a late wake, expired feedback, a bad batch, or a backlog) sends Disable to every
drive, re-sends it each tick to every drive that hasn't confirmed, and sends active reporting off to each confirmed
drive once its post-Disable silence is over (50 ms after its confirmation). A drive confirms with a Reset-mode status
read after the stop's Disable, at any point while the bus is still stopping; one that never confirms is still getting
a Disable every tick, so it gets no reporting off. Disables go out for 100 ms, and inside them a reporting off the
socket refuses is tried again each tick. After them the stop runs on only while a confirmed drive's reporting off is
untried, or tried but less than a period past its due time; so one that falls due after the 100 ms is tried only
until a period past its due time, typically once, and one the socket refuses is recorded unsent. The bus is `Stopped`
once every drive has confirmed and taken its reporting off, or once the 100 ms have passed and no confirmed drive's
reporting off is still untried or inside that period.

A latched bus error (bus-off in an error frame, or any socket failure) sends nothing: there is no bus to send on, so the bus is
`Stopped` at once and the drives time out on their own (`canTimeout`). The first such error stays in every snapshot's
`bus_error`, even if a stop was already under way; `healthy` is false while there is one or the controller is
error-passive.

`BusTick` holds all of that as plain values with time passed in, so it runs and is tested without a socket. It refuses
a drive table past `MAX_DRIVES` and timing that breaks its promises (`Timing::check`: for one, the three-period
feedback limit plus the most a read trails arrival must stay under the drives' 50 ms timeout, so the default timing
needs at least 74 Hz; and the silent ticks that stop a bus must span less than that timeout). The Linux shell that
owns the socket and the clock comes next (PLAN step 6).

## Must never

Send a command late, retry one, or re-send a stale batch. Treat a TX echo or any traffic as proof a drive is alive.
Allocate, lock, log or wait without a deadline in the tick, or take a lock shared with non-realtime code. Let anyone
but the runtime transmit. Let a stop be undone: a stopping bus refuses every batch, and a latched bus error stays
latched.

## Talks to

`robstride` for the frames (it builds them, this crate only sends `Frame`s) and `telemetry` for the frame records the
recorder stores. Control will sit on the other side of two queues, batches in and snapshots out; neither it nor the
socket shell exists yet, so today only the tests drive `BusTick`. See the
[map](https://github.com/jaylamping/roark/blob/main/conventions/architecture.md).

## Using it

Build a `BusTick` with the bus's drives in slot order, then per tick: empty the socket, feeding each frame to `on_frame`,
and report how the drain went with `drained`; `begin`, write each send and report it with `sent`; feed every frame read
with `on_frame`; and `end` for the snapshot. `request_stop` asks for a stop at the next `begin`, and `lost_bus` latches
the bus stopped when the socket fails.

```rust
use can::{BusState, BusTick, CommandBatch, SendOutcome, Timing};
use robstride::drive;
use robstride::{
    Celsius, DeviceId, Drive, Feedback, Mode, Model, NewtonMeters, RadPerSec, Radians, StatusFaults, encode,
};
use telemetry::{Direction, FrameRecord};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let device = DeviceId::new(101)?;
    let timing = Timing::at_hz(250);
    let mut bus = BusTick::new(&[device], timing)?;

    // Tick 0 starts at 0 ns. Control's batch enables the drive and is good until the next tick.
    let mut batch = CommandBatch::new(0, timing.period_ns);
    assert!(batch.set(0, encode::enable(device)));
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
    assert_eq!(snap.state, BusState::Active);
    let view = snap.drive(0).ok_or("slot 0")?;
    assert!(view.answered);
    assert_eq!(view.fresh_ns, Some(1_000_000));
    Ok(())
}
```
