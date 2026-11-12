//! A scan and a set-ID on `vcan` (PLAN.md item 3, Scan and identity): every ID probed in the slack, a drive outside the
//! bus's table found and given a new ID, against simulated drives.
#![cfg(target_os = "linux")]

#[expect(dead_code, reason = "each test file uses some of the shared helpers")]
mod common;

use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

use can::{
    BusConfig, BusLinks, CommandBatch, SlowKind, SlowOutcome, SlowRefusal, SlowRequest, Snapshot,
};
use common::{HZ, Shutdown, drive, id, info, next_snapshot, soon, timing};
use robstride::{DeviceId, Drive, Model, Uid};
use sim_drive::{SimDrive, ensure_vcan, serve};
use telemetry::{Recorder, Recording, Session};

const BUS: &str = "can0";

/// Plays control for one bus: an empty batch each tick, and slow requests asked one at a time.
struct Control<'a> {
    commands: rtrb::Producer<CommandBatch>,
    snapshots: rtrb::Consumer<Snapshot>,
    requests: rtrb::Producer<SlowRequest>,
    results: rtrb::Consumer<can::SlowResult>,
    epoch: &'a telemetry::Epoch,
    tag: u32,
    stalls: u32,
}

impl Control<'_> {
    /// Ask `kind` and keep the bus fed until its result. A stall of this thread can leave control silent for a tick, or
    /// a loaded machine can leave a drain unemptied; such a refusal or unsure window is asked again, a few times at
    /// most in the whole run.
    #[expect(
        clippy::unwrap_used,
        reason = "test helper: a bus that stops publishing fails the test"
    )]
    fn ask(&mut self, kind: SlowKind) -> SlowOutcome {
        let end = Instant::now() + Duration::from_secs(5);
        let period = 1_000_000_000 / HZ;
        self.tag += 1;
        let mut asked = false;
        loop {
            let mut snap = next_snapshot(&mut self.snapshots, end).unwrap();
            for _ in 0..self.snapshots.buffer().capacity() {
                let Ok(newer) = self.snapshots.pop() else {
                    break;
                };
                snap = newer;
            }
            let batch =
                CommandBatch::new(snap.tick + 1, self.epoch.ns(Instant::now()) + 3 * period);
            assert!(self.commands.push(batch).is_ok());
            if !asked {
                let request = SlowRequest {
                    tag: self.tag,
                    slot: 0,
                    kind,
                };
                assert!(self.requests.push(request).is_ok());
                asked = true;
            }
            if let Ok(result) = self.results.pop() {
                assert_eq!(result.tag, self.tag);
                if matches!(
                    result.outcome,
                    SlowOutcome::Refused(SlowRefusal::ControlSilent) | SlowOutcome::Unsure
                ) && self.stalls < 5
                {
                    self.stalls += 1;
                    self.tag += 1;
                    asked = false;
                    continue;
                }
                return result.outcome;
            }
        }
    }
}

/// Guards: protocol - on `vcan`, a scan finds every drive answering on the bus, one in the bus's table and ones outside
/// it, two sharing an ID among them, and nothing at the other IDs; a set-ID moves a drive outside the table to a new ID,
/// where the next probe finds it, and its old ID is silent after (RS03 manual §4.1.1 type 0, §4.1.5 type 7; PLAN.md
/// item 3, Scan and identity; item 5: scan, then set IDs one drive at a time).
#[test]
fn a_scan_finds_every_drive_and_a_set_id_moves_one() {
    ensure_vcan(BUS).unwrap();
    let root = std::env::temp_dir().join(format!("sim-suite-scan-{}", std::process::id()));
    let (known, stray, first, second) = (Uid([1; 8]), Uid([2; 8]), Uid([3; 8]), Uid([4; 8]));
    let stop_sim = AtomicBool::new(false);
    let exit = Arc::new(AtomicBool::new(false));
    std::thread::scope(|scope| {
        let _shutdown = Shutdown(&stop_sim, Arc::clone(&exit));
        let sim = scope.spawn(|| {
            let mut drives = vec![
                SimDrive::new(Drive::new(id(101), Model::Rs03), known, 1),
                SimDrive::new(Drive::new(id(127), Model::Rs03), stray, 2),
                SimDrive::new(Drive::new(id(50), Model::Rs02), first, 3),
                SimDrive::new(Drive::new(id(50), Model::Rs02), second, 4),
            ];
            serve(BUS, &mut drives, &stop_sim, &mut |_| {})
        });
        let session = Session::start(&root, info(BUS), 1_000_000_000).unwrap();
        let (recording, mut buses) = Recording::new(session, telemetry::RING_BATCHES);
        let epoch = recording.epoch();
        let recorder = Recorder::spawn(recording).unwrap();
        let (commands_tx, commands) = rtrb::RingBuffer::new(4);
        let (snapshots_tx, snapshots) = rtrb::RingBuffer::new(64);
        let (requests_tx, requests) = rtrb::RingBuffer::new(4);
        let (results_tx, results) = rtrb::RingBuffer::new(4);
        let bus = can::spawn(
            BusConfig {
                name: BUS.to_owned(),
                // Only drive 101 is the bus's; the others are what a scan is for.
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
        let mut control = Control {
            commands: commands_tx,
            snapshots,
            requests: requests_tx,
            results,
            epoch: &epoch,
            tag: 0,
            stalls: 0,
        };

        scan_and_set_id(&mut control, [known, stray, first, second]);

        exit.store(true, Ordering::Release);
        let done = bus.thread.join().unwrap();
        assert!(done.error.is_none(), "{:?}", done.error);
        recorder.close(vec![done.recorder]).unwrap();
        stop_sim.store(true, Ordering::Release);
        sim.join().unwrap().unwrap();
    });
    let _ = std::fs::remove_dir_all(&root);
}

/// The scan and the set-ID, against drive 101 (`known`), a stray drive on 127 and two drives on 50.
fn scan_and_set_id(control: &mut Control<'_>, [known, stray, first, second]: [Uid; 4]) {
    // Until the simulated drives are up a probe may time out: wait for the bus's own drive first.
    let up = Instant::now() + Duration::from_secs(5);
    while control.ask(SlowKind::Probe(id(101))) == SlowOutcome::TimedOut {
        assert!(Instant::now() < up, "the simulated drives never answered");
    }

    let found: Vec<(u8, SlowOutcome)> = (1..=DeviceId::MAX)
        .map(|n| (n, control.ask(SlowKind::Probe(id(n)))))
        .filter(|(_, outcome)| *outcome != SlowOutcome::TimedOut)
        .collect();
    // The two drives on 50 answer in either order.
    let shared = |a, b| SlowOutcome::Found {
        uid: a,
        other: Some(b),
    };
    assert!(
        found.first() == Some(&(50, shared(first, second)))
            || found.first() == Some(&(50, shared(second, first))),
        "{found:?}"
    );
    assert_eq!(
        found.get(1..),
        Some(
            &[
                (
                    101,
                    SlowOutcome::Found {
                        uid: known,
                        other: None
                    }
                ),
                (
                    127,
                    SlowOutcome::Found {
                        uid: stray,
                        other: None
                    }
                ),
            ][..]
        )
    );

    let moved = SlowOutcome::Found {
        uid: stray,
        other: None,
    };
    assert_eq!(
        control.ask(SlowKind::SetId {
            old: id(127),
            new: id(11),
        }),
        moved
    );
    assert_eq!(control.ask(SlowKind::Probe(id(11))), moved);
    assert_eq!(control.ask(SlowKind::Probe(id(127))), SlowOutcome::TimedOut);
}
