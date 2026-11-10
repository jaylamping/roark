# can

The bus layer: one thread per CAN bus that sends control's commands on a fixed tick, reads every frame the socket
delivers, and publishes what each drive last said and how fresh it is (PLAN item 3, can.md section 2). The drives on
a bus are grouped into **limbs**, each its own index on that bus, and a stop names its scope: one limb or the whole bus.

## What it does

Each tick, on the monotonic clock:

1. **Wake** at the tick's scheduled start (`clock_nanosleep`, absolute). Tick numbers count from one origin the runtime
   gives every bus thread and the control thread (`BusLinks::start`), so tick n is the same instant on every bus; a
   thread started after the origin begins at the first tick not yet due. Waking later than the send window is a missed
   deadline; ticks a stall slept through are skipped, each counted as a missed deadline. Either stops every active limb.
   It doesn't stop an idle limb: that tick only the batch's Disables and reporting off go and the rest is held; the
   batch checks in step 4 still apply.
2. **Drain** the socket to empty, so what is read after the send came after the backlog. It is not a strict barrier:
   a frame landing between the drain and the write counts as after it, which is still evidence of the drive then.
3. **Check** what the drain read, before anything is sent: a drive of an idle or active limb that shows a fault, has
   left Run after it was seen in Run (latched when read, so a later Run status can't hide it), or has left
   `silence_misses` (3) commands in a row unanswered stops its limb now (`DriveFault`, `DriveMode`, `DriveSilent`, each
   naming the slot), so no command, Enable included, goes to it this tick. A Disable from control isn't leaving Run:
   its Reset answer is expected. A drive this host never enabled isn't watched for mode: preflight refuses one found
   already in Run.
4. **Plan** with `BusTick::begin`: the newest `CommandBatch` from control, only if it is for this tick and unexpired.
   A batch for another tick, or a missing one, sends nothing; one for this tick past its expiry sends only its Disables
   and reporting off. Either is a silent tick, and two silent ticks while a limb runs stop the bus. A batch for this
   tick, expired or not, carries only motion, Enable, Disable and the enable sequence's reporting off and `run_mode` =
   MIT write; anything else (Set Zero, set-ID, other parameter traffic) is a bad batch and stops the bus. An MIT frame to a drive whose fresh status is older than
   three periods is refused and stops its limb. A batch's frames for a stopping or stopped limb are dropped and counted
   (`refused_frames`); the other limbs' frames still go.
5. **Send** each planned frame once and feed the outcome back (`sent`). A command goes out only before the send
   window closes; a Disable or reporting off goes out even late, whoever planned it, since late it is still the right
   one. A full queue drops the frame and counts it; it is never retried within the tick. Any other socket write
   failure goes to `lost_bus`, which latches every limb stopped, as well as to `sent` as `Failed`; `Failed` on its own
   records only that the frame wasn't taken and never latches.
6. **Collect** until the collect deadline (about 60 % of the period), feeding each frame to `on_frame`.
7. **Publish** the `Snapshot` (`end`) to control and hand every frame of the tick to the recorder.
8. **Slack:** hand control the results already held, take new requests, send at most one (`slow_send`; none on a held
   tick), then hand control the new results.

A drive's status read after a command the socket took is its **fresh** status, and it **answered** the tick if read by
the collect deadline. That is evidence the drive is there and what state it was in, never an acknowledgement: there
are no sequence numbers to prove which command a status answers. Faults are never filtered: a status or report
updates what the drive was seen saying, and any status, report, version reply or type-21 fault report with a fault set
latches `fault_seen`. Missing replies aren't counted toward a drive's silence for an Enable or Disable, or inside the
Silence windows of PLAN item 2, which say which drives and Disables they cover: the enable-to-Run window
(`ENABLE_TO_RUN_NS`, 50 ms, while the drive hasn't shown Run), the post-Disable window (`stop_confirm_ns`, 100 ms),
and a drive that is offline (here: never enabled since start or its limb's clear, or seen in Reset after this host's
Disable).
Each drive's last echo of this host's frames to it of a kind a batch carries (`last_echo`: its kind and when it was
read) is kept, for the enable sequence's "reporting-off echo plus one tick".

A limb stop (`stop_limb`, named `LimbRequested`; the check above; expired feedback) stops that limb; a bus stop
(`request_stop`, control silent, or a bad batch) stops every limb not already stopping or stopped; a late wake, a stall
or a backlog stops every active limb (below). A stopping limb follows PLAN item 2 Stop, every bound from `Timing`:

- Disable to each of its drives not yet confirmed, every tick of the confirm window (`stop_confirm_ns`, 100 ms).
- A drive confirms with a Reset-mode status read after the stop's Disable, inside the reply allowance
  (`stop_replies_ns`: the window, a period and the send window, so the reply to the window's last Disable still
  counts when the next tick's drain reads it, however late inside their send windows that tick and the stop's first
  woke). A Reset read later confirms nothing: that drive stays unconfirmed and gets no reporting off,
  as does one that never answers. A status, report or version reply in any other mode read after a confirmation
  withdraws it: the drive counts as unconfirmed for the stop's end and the re-arm, and gets Disable again while the
  limb is still stopping and the window lasts. Once the limb is `Stopped` nothing is sent to it: the drive's own
  timeout (`canTimeout`) takes it down, the re-arm treats it as unconfirmed (the quiet wait below applies), and an
  enable needs preflight to read it in Reset (PLAN item 6 `host.preflight`).
- Active reporting off to each confirmed drive once its post-Disable silence is over (`disable_silence_ns`, 50 ms after
  its confirmation), every tick until the socket takes it or the stop ends. Every Disable, a stop's or one in
  control's batch, goes out ahead of every reporting off, so a queue that fills after the first frames costs a
  reporting off before it costs a Disable.
- The limb is `Stopped` once every drive has confirmed and the socket took its reporting off; otherwise not before the
  reply allowance closes, and after it as soon as no confirmed drive's reporting off is unsent, or at the latest at
  `stop_max_ns` (the allowance, the silence, two periods and the send window; PLAN item 2 Stop gives it at 250 Hz),
  which gives the last drive that can confirm at least two tries on ticks that wake inside their send windows. A
  reporting off never taken is recorded unsent (`reporting_off_sent`), as is one taken before its drive's
  confirmation was withdrawn.

The first reason a limb stopped for stays in its `LimbView`.

A late wake, ticks a stall slept through, or a backlog (a drain that read past its limit or left frames queued) stop
every active limb; an idle limb has nothing enabled to stop. That tick only the batch's Disables and reporting off go,
right late or not, and the rest is held back (`held_batches`), so nothing is enabled on a tick whose reads can't be
trusted; the batch checks still apply. That held tick then clears the freshness its own drain stamped for the drives
of every limb still idle (`fresh_ns` and `fresh_status`), and a status read after its sends counts again;
`BusTick::begin` states the rule in full.

A latched bus error (bus-off in an error frame, or any socket failure) sends nothing: there is no bus to send on, so every
limb is `Stopped` at once and the drives time out on their own (`canTimeout`). The first such error stays in every snapshot's
`bus_error`, even if a stop was already under way; `healthy` is false while there is one or the controller is
error-passive.

Only the operator's clear undoes a stop: `rearm(limb, now)` makes a `Stopped` limb idle again, with a new `generation`,
its drives' stop outcomes, fault history (`fault_seen`) and miss counts started afresh. It is refused while the bus has
a latched error (that bus is rebuilt instead), while the limb is running or still stopping, and until every drive in it
is known disabled: confirmed in Reset by the stop and not seen in another mode since, or sent nothing for longer than
the drives' 50 ms timeout plus a period since the socket took its last frame (stamped when it was written, so a late
Disable counts from when it went). Each drive needs a fresh preflight before it is enabled again; that is the safety
layer's.

**Slow requests** (`submit`) are parameter reads, the codec's allowlisted writes and get-ID, for preflight and the
once-a-second reads; they never ride in a batch. A bus holds `SLOW_SLOTS` of them and has at most one in flight, sent
after the collect deadline and only while its reply fits before the next tick starts (`Timing::slow_reply_ns`, a
quarter period by default, provisional until the real adapter is measured), so the next drain reads the reply and it
never lands among the tick's command replies. A held tick (a late wake, a stall or a backlog, above) sends none: its
reads can't be trusted and its slack isn't known, so a queued request waits for a trusted tick. A read is answered by
its drive's reply naming its register, get-ID by its type-0 reply, and a write by any status from the drive while the
write is in flight; a fault or mode that status shows counts like any status's.

A write's answer proves nothing about the value, and preflight reads every write back, because a status names no
register and can't be told from a command's reply. Writes go only where a mix-up is least likely: to drives of an idle
limb (`LimbNotIdle`) with no command of the tick still unanswered (`CommandUnanswered`: an idle limb's batch may carry
a Disable or the `run_mode` write; an earlier tick's command is late or lost and doesn't hold writes off). A late
status can still land either way. A command's reply more than a tick late, read while the write is in flight, is taken
for the write's answer. A write's own status read after its timeout (the next tick's start) is taken for that tick's
command's reply, as fresh evidence of the drive from just before that tick's sends; it can't wrongly confirm a stop
(`on_status` in `read.rs` has the argument).

The `run_mode` = MIT write goes only in control's batch (`BatchOnly`), so a slow frame's echo is never of a kind kept as
the drive's `last_echo`. Each request gets exactly one result: its answer, `TimedOut` (no reply by the next tick's
start), `NotSent`, or `Refused`, including when the thread ends with it pending (`end_slow`: `Ended`, or `BusFailed`).
Nothing is retried. A request for a drive whose limb is stopping, stopped or due to stop (a stop asked for and not yet
taken, or what the veto stops on, on any drive of the limb: a fault, a drop out of Run, too many misses), while control
has been silent for the silent-tick limit (counted with every limb idle too), or on a failed bus is refused, and one
already queued is cancelled before it goes, so slow traffic never keeps a drive alive past a stop (`canTimeout` counts
from any frame).

`BusTick` holds all of that as plain values with time passed in, so it runs and is tested without a socket. It refuses
a drive table past `MAX_DRIVES`, a drive listed twice, a limb index past the table, and timing that breaks its
promises (`Timing::check`, whose doc lists every rule). For one, the feedback limit plus the write slack (the send
window: how long after its check a frame may go out) plus the most a read trails arrival must stay under the drives'
50 ms timeout; and each silence count must be at least one, and its span (the silent ticks; the missed replies plus
the tick that stops on them) plus the write slack must stay under that timeout. With the default timing the last sets
the slowest rate: three misses, the stopping tick and a quarter-period send window, 4.25 periods, so at least 86 Hz.
The Linux shell (`spawn`) owns the socket: it
opens only `vcan` until the real adapter is supported (PLAN step 8), takes every ID (no kernel filter), and reads each
frame with its kernel timestamp, its direction and the overflow count in one `recvmsg`. `bus_info` is the session's
record of that socket, from the same constants `open` applies, and `spawn` returns the receive buffer the kernel
actually gave (`Spawned::receive_buffer_bytes`) for the runtime's startup log. Each tick's recorded batch is `valid`
while the bus is healthy, the exit tick's included, and a snapshot control's full ring can't take is counted
(`snapshots_dropped`). Any write error but a full queue loses the bus, as a read error does. Setting `exit` on a bus
whose limbs are all idle ends the thread at once; on any other it stops every limb first, then ends the thread once
control has a snapshot with every limb stopped, or can't or won't take it (`BusLinks::exit` says when), with the last
snapshot in `BusExit::last`; the next tick's drain is still recorded, so the stop's last echoes are in the recording.
As it ends, every slow request it holds or finds in its ring gets its result, and `BusExit::slow_results_dropped`
counts every result control's ring couldn't take, those after the last snapshot included.
A socket or clock error ends the thread as soon as a snapshot with every limb stopped is made, without waiting for
control.

Open: a Reset read in order after a Disable puts its drive offline, and a later Disable leaves it there, which assumes
a Reset read after the Disable was sent after it; a drive wrongly offline is not counted silent until its next Enable,
while motion to it still stops its limb on stale feedback (`BusTick::drained` has the detail). Checked on the real
adapter at PLAN step 8. Also to check on the bench, since the re-arm relies on the drive's timeout (`BusTick::rearm`):
a drive that stays in Run past its `canTimeout`.

Not yet: the `/can/<bus>/tx_intent` record of every frame handed to the socket or not sent, with the reason
(logging.md section 8.2), and the per-run tick duration and jitter (rust.md section 6). Both come with the runtime,
which owns the recording's channels and the metrics, before step 8 measures latency and jitter on the real adapter.

## Must never

Send a command late, retry one, or re-send a stale batch. Treat a TX echo or any traffic as proof a drive is alive.
Allocate, lock, log or wait without a deadline in the tick, or take a lock shared with non-realtime code. Let anyone
but the runtime transmit. Retry a slow request, or send one to a stopped limb or while control is silent. Undo a stop
on its own: a stopping or stopped limb gets none of control's frames until the operator's `rearm`, and a latched bus
error stays latched. Open an interface that isn't `vcan` before the real adapter's checks exist (PLAN step 8).

## Talks to

`robstride` for the frames (it builds them, this crate only sends `Frame`s) and `telemetry` for the recording: each
tick's frames go to a `BusRecorder`. Control is on the other side of `rtrb` queues: batches and slow requests in, snapshots and slow
results out; a full outgoing ring drops and counts (`snapshots_dropped`, `slow_results_dropped`).
The runtime that wires those up doesn't exist yet; the sim suite drives the shell against `sim-drive` on `vcan`. See
the [map](https://github.com/jaylamping/roark/blob/main/conventions/architecture.md).

## Using it

Build a `BusTick` with the bus's drives in slot order, each with its limb, then per tick: empty the socket, feeding
each frame to `on_frame`, and report how the drain went with `drained`; `begin`, write each send and report it with
`sent`; feed every frame read with `on_frame`; and `end` for the snapshot. In the slack after `end`: take the results
already held with `take_slow_result`, `submit` new requests while `slow_room` allows, send what `slow_send` returns and
report it with `slow_sent`, then take the new results; when the thread ends, `end_slow` and take what is left.
`request_stop` and `stop_limb` ask for a stop at the next `begin`, `skipped` counts ticks a stall slept through, and
`lost_bus` latches every limb stopped when the socket fails. On Linux, `spawn` runs exactly that on a socket.

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
