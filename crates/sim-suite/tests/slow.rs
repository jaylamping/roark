//! Slow requests on `vcan` (PLAN item 3): get-ID, a write and its read-back, carried in the slack after the collect
//! deadline to a simulated drive and back.
#![cfg(target_os = "linux")]

#[expect(dead_code, reason = "each test file uses some of the shared helpers")]
mod common;

use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

use can::{
    BusConfig, BusLinks, CommandBatch, SlowKind, SlowOutcome, SlowRefusal, SlowRequest, SlowResult,
};
use common::{HZ, Shutdown, drive, id, info, next_snapshot, soon, timing};
use robstride::{Drive, Model, Uid};
use sim_drive::{SimDrive, ensure_vcan, serve};
use telemetry::{Recorder, Recording, Session};

/// Guards: protocol - slow requests reach a drive on `vcan` and come back in the slack while control's empty batches
/// keep the bus alive: get-ID returns the drive's UID, an allowlisted write is answered, and reading it back returns
/// the value written (PLAN.md item 3: parameter traffic only in the slack; item 6: preflight reads every write back).
#[test]
fn slow_requests_reach_a_drive_on_vcan_and_come_back() {
    const SLOW_BUS: &str = "can0";
    ensure_vcan(SLOW_BUS).unwrap();
    let root = std::env::temp_dir().join(format!("sim-suite-slow-{}", std::process::id()));
    let uid = Uid([9; 8]);
    let stop_sim = AtomicBool::new(false);
    let exit = Arc::new(AtomicBool::new(false));
    std::thread::scope(|scope| {
        let _shutdown = Shutdown(&stop_sim, Arc::clone(&exit));
        let sim = scope.spawn(|| {
            let mut drives = [SimDrive::new(Drive::new(id(101), Model::Rs03), uid, 7)];
            serve(SLOW_BUS, &mut drives, &stop_sim, &mut |_| {})
        });
        let info = info(SLOW_BUS);
        let session = Session::start(&root, info, 1_000_000_000).unwrap();
        let (recording, mut buses) = Recording::new(session, telemetry::RING_BATCHES);
        let epoch = recording.epoch();
        let recorder = Recorder::spawn(recording).unwrap();
        let (mut commands_tx, commands) = rtrb::RingBuffer::new(4);
        let (snapshots_tx, mut snapshots) = rtrb::RingBuffer::new(64);
        let (mut requests_tx, requests) = rtrb::RingBuffer::new(4);
        let (results_tx, mut results) = rtrb::RingBuffer::new(4);
        let bus = can::spawn(
            BusConfig {
                name: SLOW_BUS.to_owned(),
                drives: vec![drive(101, 0)],
                timing: timing(),
            },
            BusLinks {
                commands,
                snapshots: snapshots_tx,
                recorder: buses.remove(0),
                requests,
                results: results_tx,
                orders: rtrb::RingBuffer::new(1).1,
                rearmed: rtrb::RingBuffer::new(1).0,
                epoch,
                start: soon(),
                exit: Arc::clone(&exit),
            },
        )
        .unwrap();

        let write = robstride::Write::can_timeout(Drive::new(id(101), Model::Rs03));
        let steps = [
            (SlowKind::GetId, SlowOutcome::Identity(uid)),
            (SlowKind::Write(write), SlowOutcome::WriteAnswered),
            (
                SlowKind::Read(write.param()),
                SlowOutcome::Read(robstride::ParamOutcome::Read(write.value())),
            ),
        ];
        let end = Instant::now() + Duration::from_secs(10);
        let period = 1_000_000_000 / HZ;
        let mut step = 0;
        let mut asked = false;
        let mut tag = 0;
        let mut retries = 0;
        while step < steps.len() {
            // Play control: an empty batch for the tick after the newest snapshot, so a late wake of this thread never
            // answers an old tick.
            let mut snap = next_snapshot(&mut snapshots, end).unwrap();
            // At most the ring's worth: the bus publishes once a period, so this never chases it.
            for _ in 0..snapshots.buffer().capacity() {
                let Ok(newer) = snapshots.pop() else { break };
                snap = newer;
            }
            let batch = CommandBatch::new(snap.tick + 1, epoch.ns(Instant::now()) + 3 * period);
            assert!(commands_tx.push(batch).is_ok());
            let (kind, expected) = steps[step];
            if !asked {
                tag += 1;
                assert!(requests_tx.push(SlowRequest { tag, slot: 0, kind }).is_ok());
                asked = true;
            }
            if let Ok(SlowResult {
                tag: got,
                slot,
                outcome,
            }) = results.pop()
            {
                assert_eq!((got, slot), (tag, 0));
                asked = false;
                // Until the drive is up a get-ID may time out, and a stall of this thread can leave control silent for
                // a tick at any step; ask again, a few times at most in the whole run.
                let retry = retries < 5
                    && (outcome == SlowOutcome::Refused(SlowRefusal::ControlSilent)
                        || (step == 0 && outcome == SlowOutcome::TimedOut));
                if retry {
                    retries += 1;
                } else {
                    assert_eq!(outcome, expected, "step {step}");
                    step += 1;
                }
            }
        }
        exit.store(true, Ordering::Release);
        let done = bus.thread.join().unwrap();
        assert!(done.error.is_none(), "{:?}", done.error);
        recorder.close(vec![done.recorder]).unwrap();
        stop_sim.store(true, Ordering::Release);
        sim.join().unwrap().unwrap();
    });
    let _ = std::fs::remove_dir_all(&root);
}
