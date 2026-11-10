//! (rt) The bus thread's slack on Linux, after the collect deadline: control's slow requests in, at most one sent, and
//! every result back. A full result ring drops the result and counts it; the requester times out.

use rtrb::{Consumer, Producer};
use socketcan::CanSocket;

use crate::bus::{BusExit, Clock, lose, mono_now, write};
use crate::slow::{SlowOutcome, SlowRefusal, SlowRequest, SlowResult};
use crate::tick::BusTick;
use crate::types::SendOutcome;

/// Open the slack (cancelling and expiring queued requests), hand back the results the tick holds (freeing their
/// slots), queue the slow requests that fit, send one if the tick allows, and hand every new result back. A failed
/// write loses the bus, as in the tick's sends.
pub(crate) fn slow(
    socket: &CanSocket,
    clock: &Clock,
    tick: &mut BusTick,
    requests: &mut Consumer<SlowRequest>,
    results: &mut Producer<SlowResult>,
    outcome: &mut BusExit,
) {
    tick.open_slack();
    hand_back(tick, results);
    // Bounded by the ring: a refused request takes no slot, so room alone wouldn't end the loop.
    for _ in 0..requests.buffer().capacity() {
        if tick.slow_room() == 0 {
            break;
        }
        let Ok(request) = requests.pop() else {
            break;
        };
        if let Err(refusal) = tick.submit(request) {
            refuse(tick, results, request, refusal);
        }
    }
    // Read once the slack's own work is done, so whether the reply still fits is judged as near the write as can be.
    let now_ns = clock.ns(mono_now());
    if let Some(frame) = tick.slow_send(now_ns) {
        let result = match write(socket, &frame) {
            Ok(result) => result,
            Err(e) => {
                lose(tick, outcome, e);
                SendOutcome::Failed
            }
        };
        tick.slow_sent(result, clock.ns(mono_now()));
    }
    hand_back(tick, results);
}

/// Every result the tick holds, onto control's ring; a full ring drops the result and counts it.
fn hand_back(tick: &mut BusTick, results: &mut Producer<SlowResult>) {
    while let Some(result) = tick.take_slow_result() {
        if results.push(result).is_err() {
            tick.slow_result_dropped();
        }
    }
}

/// The thread is ending: every slow request still held or still in the ring gets its one result (crates/can/README.md,
/// Slow requests). Returns every result dropped over the thread's run, these included, for [`BusExit`]: no snapshot
/// comes after these; the requester times out.
pub(crate) fn end_slow(
    tick: &mut BusTick,
    requests: &mut Consumer<SlowRequest>,
    results: &mut Producer<SlowResult>,
) -> u64 {
    let refusal = tick.end_slow();
    hand_back(tick, results);
    for _ in 0..requests.buffer().capacity() {
        let Ok(request) = requests.pop() else {
            break;
        };
        refuse(tick, results, request, refusal);
    }
    tick.counters.slow_results_dropped
}

/// Request `request`'s one result, a refusal, onto control's ring; a full ring drops it and counts it.
fn refuse(
    tick: &mut BusTick,
    results: &mut Producer<SlowResult>,
    request: SlowRequest,
    refusal: SlowRefusal,
) {
    let refused = SlowResult {
        tag: request.tag,
        slot: request.slot,
        outcome: SlowOutcome::Refused(refusal),
    };
    if results.push(refused).is_err() {
        tick.slow_result_dropped();
    }
}
