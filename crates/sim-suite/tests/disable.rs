//! `robot-cli disable`, the independent stop, as systemd runs it: the real binaries on `vcan` against `sim-drive`, with
//! the runtime's test robot (`bins/runtime/tests/skeleton.yaml`). It refuses while a runtime is alive, runs once the
//! runtime is killed with `kill -9`, and leaves every answering drive in Reset with reporting off, on every bus, even
//! when one of the skeleton's buses is gone.
//!
//! The binaries come from the build `scripts/sim.sh` makes before it runs the suite.
#![cfg(target_os = "linux")]

use std::collections::{BTreeMap, BTreeSet};
use std::path::{Path, PathBuf};
use std::process::{Command, ExitStatus, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

use robstride::drive::{self, Command as HostCommand};
use robstride::{DeviceId, Inbound, Mode, Reporting, Uid, decode, encode};
use sim_drive::{SimDrive, ensure_vcan, serve};
use skeleton::Skeleton;
use socketcan::{CanDataFrame, CanFrame, CanSocket, EmbeddedFrame, ExtendedId, Id, Socket};

/// The runtime's test robot, never the live skeleton (testing.md rule 3).
fn skeleton_path() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../../bins/runtime/tests/skeleton.yaml")
}

/// A workspace binary from the same build as this test: `target/<profile>/<name>`, next to this test's `deps/`.
#[expect(clippy::unwrap_used, reason = "test helper: a test binary has a path")]
fn binary(name: &str) -> PathBuf {
    let exe = std::env::current_exe().unwrap();
    let path = exe.parent().and_then(Path::parent).unwrap().join(name);
    assert!(
        path.is_file(),
        "{} is missing: run the suite with scripts/sim.sh, which builds the binaries first",
        path.display()
    );
    path
}

/// A scratch directory for this test.
#[expect(
    clippy::unwrap_used,
    reason = "test helper: the temp directory is writable"
)]
fn scratch(test: &str) -> PathBuf {
    let dir = std::env::temp_dir().join(format!("sim-suite-{test}-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    dir
}

/// The simulated drives for the skeleton's joints on `bus`, but for `silent`.
fn drives(skeleton: &Skeleton, bus: &str, silent: &[u8]) -> Vec<SimDrive> {
    skeleton
        .limbs
        .iter()
        .flat_map(|limb| &limb.joints)
        .filter(|joint| joint.bus.as_ref().is_some_and(|b| b.as_str() == bus))
        .filter(|joint| !silent.contains(&joint.id.get()))
        .map(|joint| {
            let id = joint.id.get();
            SimDrive::new(
                robstride::Drive::new(joint.id, joint.actuator),
                Uid([b's', b'i', b'm', 0, id, 0, 0, 0]),
                u64::from(id),
            )
        })
        .collect()
}

/// The skeleton's wired drive IDs on `bus`.
fn ids(skeleton: &Skeleton, bus: &str) -> BTreeSet<u8> {
    skeleton
        .limbs
        .iter()
        .flat_map(|limb| &limb.joints)
        .filter(|joint| joint.bus.as_ref().is_some_and(|b| b.as_str() == bus))
        .map(|joint| joint.id.get())
        .collect()
}

/// One frame seen on a bus, decoded both ways, and when.
#[derive(Clone, Debug)]
struct Seen {
    at: Instant,
    host: Option<drive::HostFrame>,
    drive: Option<Inbound>,
}

/// Every frame on `bus` until `stop`.
#[expect(
    clippy::unwrap_used,
    reason = "test helper: the monitor must open for the test to mean anything"
)]
fn watch(bus: &str, stop: &AtomicBool) -> Vec<Seen> {
    let socket = CanSocket::open(bus).unwrap();
    socket.set_read_timeout(Duration::from_millis(5)).unwrap();
    let mut seen = Vec::new();
    while !stop.load(Ordering::Acquire) {
        if let Ok(CanFrame::Data(frame)) = socket.read_frame()
            && let Id::Extended(id) = frame.id()
        {
            seen.push(Seen {
                at: Instant::now(),
                host: drive::command(id.as_raw(), frame.data()).ok().flatten(),
                drive: decode(id.as_raw(), frame.data()).ok(),
            });
        }
    }
    seen
}

/// Put each drive in `ids` in Run with active reporting on, from a socket of the test's own, and wait until each
/// reports in Run: the state a killed runtime leaves an enabled limb in, short of the 50 ms `canTimeout` (off on a
/// fresh `sim-drive`, so they stay in Run). Returns false if they don't all get there in time.
#[expect(
    clippy::unwrap_used,
    reason = "test helper: the socket must work for the test to mean anything"
)]
fn run_and_report(bus: &str, ids: &BTreeSet<u8>) -> bool {
    let socket = CanSocket::open(bus).unwrap();
    socket.set_read_timeout(Duration::from_millis(5)).unwrap();
    let send = |frame: robstride::Frame| {
        let data = CanDataFrame::new(ExtendedId::new(frame.id()).unwrap(), &frame.data()).unwrap();
        socket.write_frame(&data).unwrap();
    };
    let mut running = BTreeSet::new();
    let end = Instant::now() + Duration::from_secs(2);
    let mut next = Instant::now();
    while running != *ids && Instant::now() < end {
        // Sent again every 50 ms to a drive not yet reporting in Run: a sim that hasn't opened its socket yet misses
        // them, and both frames are harmless to repeat.
        if Instant::now() >= next {
            for &n in ids.difference(&running) {
                let id = DeviceId::new(u64::from(n)).unwrap();
                send(encode::enable(id));
                send(encode::active_reporting(id, Reporting::On));
            }
            next += Duration::from_millis(50);
        }
        if let Ok(CanFrame::Data(frame)) = socket.read_frame()
            && let Id::Extended(id) = frame.id()
            && let Ok(Inbound::Report(s)) = decode(id.as_raw(), frame.data())
            && s.header.mode == Mode::Run
        {
            running.insert(s.header.device.get());
        }
    }
    running == *ids
}

/// What one `robot-cli disable --json` run said.
#[derive(Debug)]
struct Disabled {
    status: ExitStatus,
    stderr: String,
    /// Each drive's outcome by (bus, ID), from the JSON on stdout (empty when it refused).
    outcomes: BTreeMap<(String, u8), String>,
    /// Each bus's fault kind, if any.
    faults: BTreeMap<String, Option<String>>,
    took: Duration,
}

/// Run `robot-cli disable --json` and read what it said.
#[expect(
    clippy::unwrap_used,
    reason = "test helper: the binary must run and print JSON for the test to mean anything"
)]
fn disable(skeleton: &Path, lock: &Path) -> Disabled {
    let start = Instant::now();
    let out = Command::new(binary("robot-cli"))
        .arg("disable")
        .arg("--skeleton")
        .arg(skeleton)
        .arg("--lock")
        .arg(lock)
        .arg("--json")
        .output()
        .unwrap();
    let took = start.elapsed();
    let mut outcomes = BTreeMap::new();
    let mut faults = BTreeMap::new();
    if !out.stdout.is_empty() {
        let doc: serde_json::Value = serde_json::from_slice(&out.stdout).unwrap();
        for bus in doc.get("buses").unwrap().as_array().unwrap() {
            let name = bus.get("bus").unwrap().as_str().unwrap().to_owned();
            faults.insert(
                name.clone(),
                bus.get("fault")
                    .unwrap()
                    .get("kind")
                    .and_then(serde_json::Value::as_str)
                    .map(str::to_owned),
            );
            for d in bus.get("drives").unwrap().as_array().unwrap() {
                let id = u8::try_from(d.get("id").unwrap().as_u64().unwrap()).unwrap();
                outcomes.insert(
                    (name.clone(), id),
                    d.get("outcome").unwrap().as_str().unwrap().to_owned(),
                );
            }
        }
    }
    Disabled {
        status: out.status,
        stderr: String::from_utf8_lossy(&out.stderr).into_owned(),
        outcomes,
        faults,
        took,
    }
}

/// Read the runtime's stderr until it says it has started (its "nothing enabled" line): true then, false if it ends
/// first. It takes its lock before anything else, so it holds it by then.
fn started(stderr: std::process::ChildStderr) -> bool {
    use std::io::BufRead as _;
    std::io::BufReader::new(stderr)
        .lines()
        .map_while(Result::ok)
        .any(|line| line.contains("nothing enabled"))
}

/// Sets the flag when dropped, so a failed assert still ends the sims and watchers and the scope can join them.
struct End<'a>(&'a AtomicBool);

impl Drop for End<'_> {
    fn drop(&mut self) {
        self.0.store(true, Ordering::Release);
    }
}

/// A report read this long after a drive's last reporting off means reporting is still on. Twice `disable`'s own
/// grace, because the watcher stamps a frame when it reads it, not when it arrived.
const REPORTED_AFTER: Duration = Duration::from_millis(30);

/// What `disable` sent on one bus, and what the drives did, from the watcher's frames after `from`.
struct Bus {
    disabled: BTreeSet<u8>,
    reporting_off: BTreeSet<u8>,
    /// Host commands other than Disable and reporting off.
    other: Vec<HostCommand>,
    /// Drives that reported more than `REPORTED_AFTER` after their last reporting off.
    reported_after: BTreeSet<u8>,
    /// Each drive's last mode seen.
    last_mode: Vec<(u8, Mode)>,
}

fn bus(seen: &[Seen], from: Instant) -> Bus {
    let mut b = Bus {
        disabled: BTreeSet::new(),
        reporting_off: BTreeSet::new(),
        other: Vec::new(),
        reported_after: BTreeSet::new(),
        last_mode: Vec::new(),
    };
    let mut last_off: BTreeMap<u8, Instant> = BTreeMap::new();
    for s in seen.iter().filter(|s| s.at >= from) {
        if let Some(h) = s.host {
            match h.command {
                HostCommand::Disable => {
                    b.disabled.insert(h.target.get());
                }
                HostCommand::Reporting(Reporting::Off) => {
                    b.reporting_off.insert(h.target.get());
                    last_off.insert(h.target.get(), s.at);
                }
                other => b.other.push(other),
            }
        }
    }
    for s in seen.iter().filter(|s| s.at >= from) {
        if let Some(Inbound::Status(st) | Inbound::Report(st)) = s.drive {
            let n = st.header.device.get();
            b.last_mode.retain(|(d, _)| *d != n);
            b.last_mode.push((n, st.header.mode));
            if matches!(s.drive, Some(Inbound::Report(_)))
                && last_off
                    .get(&n)
                    .is_some_and(|off| s.at > *off + REPORTED_AFTER)
            {
                b.reported_after.insert(n);
            }
        }
    }
    b.last_mode.sort_unstable_by_key(|(n, _)| *n);
    b
}

/// Guards: safety - a dead runtime stops the robot (architecture.md section 2; milestone 1 (d), on `vcan`): `robot-cli
/// disable` refuses while the runtime holds its lock, and once the runtime is killed with `kill -9` it sends only
/// Disable and reporting off, to every drive the skeleton wires, leaving every answering drive in Reset and silent,
/// with a silent drive reported but not failed.
#[test]
#[expect(clippy::too_many_lines, reason = "one run, start to end")]
fn after_kill_9_disable_leaves_every_drive_in_reset_with_reporting_off() {
    let path = skeleton_path();
    let skeleton = skeleton::load(&path).unwrap();
    let names = ["can0", "can1"];
    for name in names {
        ensure_vcan(name).unwrap();
    }
    let dir = scratch("disable");
    let lock = dir.join("runtime.lock");
    // Drive 31 is never served: it stands for a drive that is off.
    let silent = [31];
    let stop = AtomicBool::new(false);
    let (seen, refused, run, done, from) = std::thread::scope(|scope| {
        let _end = End(&stop);
        let watchers: Vec<_> = names
            .iter()
            .map(|name| scope.spawn(|| watch(name, &stop)))
            .collect();
        let _sims: Vec<_> = names
            .iter()
            .map(|name| {
                let mut sim = drives(&skeleton, name, &silent);
                let stop = &stop;
                scope.spawn(move || serve(name, &mut sim, stop, &mut |_| {}))
            })
            .collect();

        let mut runtime = Command::new(binary("runtime"))
            .arg("--skeleton")
            .arg(&path)
            .arg("--sessions")
            .arg(dir.join("sessions"))
            .arg("--lock")
            .arg(&lock)
            .stdout(Stdio::null())
            .stderr(Stdio::piped())
            .spawn()
            .unwrap();
        // A runtime that never starts and never ends is cut off by the test's 60 s limit (.config/nextest.toml).
        let stderr = runtime.stderr.take().unwrap();
        let up = started(stderr);
        let refused = disable(&path, &lock);
        runtime.kill().unwrap();
        runtime.wait().unwrap();
        assert!(up, "the runtime never took its lock");

        // The drives as a killed runtime leaves an enabled limb, then the stop systemd runs.
        let run = names.iter().all(|name| {
            run_and_report(
                name,
                &(&ids(&skeleton, name) - &silent.into_iter().collect()),
            )
        });
        let from = Instant::now();
        // `disable` returns only after watching each drive for reports past its last reporting off.
        let done = disable(&path, &lock);
        stop.store(true, Ordering::Release);
        let seen: Vec<Vec<Seen>> = watchers.into_iter().map(|w| w.join().unwrap()).collect();
        (seen, refused, run, done, from)
    });
    let _ = std::fs::remove_dir_all(&dir);

    assert_eq!(refused.status.code(), Some(2), "{refused:?}");
    assert_eq!(
        refused.stderr.lines().last(),
        Some(
            format!(
                "robot-cli: {} is held: a runtime (or another disable) is running; refusing (stop the runtime with \
                 systemctl, which runs this after it exits)",
                lock.display()
            )
            .as_str()
        ),
        "{refused:?}"
    );
    assert!(refused.outcomes.is_empty(), "{refused:?}");
    assert!(run, "the drives never reached Run with reporting on");
    assert_eq!(done.status.code(), Some(0), "{done:?}");
    assert!(done.took < Duration::from_secs(1), "{done:?}");
    for (name, seen) in names.iter().zip(&seen) {
        let wired = ids(&skeleton, name);
        let b = bus(seen, from);
        assert_eq!(b.disabled, wired, "{name}: a Disable to every wired drive");
        assert_eq!(
            b.reporting_off, wired,
            "{name}: reporting off to every wired drive"
        );
        assert!(
            b.other.is_empty(),
            "{name}: nothing else sent: {:?}",
            b.other
        );
        assert!(
            b.reported_after.is_empty(),
            "{name}: still reporting: {:?}",
            b.reported_after
        );
        let answering: Vec<(u8, Mode)> = wired
            .iter()
            .filter(|n| !silent.contains(n))
            .map(|&n| (n, Mode::Reset))
            .collect();
        assert_eq!(
            b.last_mode, answering,
            "{name}: every answering drive ends in Reset"
        );
        assert_eq!(done.faults.get(*name), Some(&None), "{done:?}");
        for n in wired {
            let want = if silent.contains(&n) {
                "silent"
            } else {
                "stopped"
            };
            assert_eq!(
                done.outcomes
                    .get(&((*name).to_owned(), n))
                    .map(String::as_str),
                Some(want),
                "{name} {n}: {done:?}"
            );
        }
    }
}

/// Guards: safety - a lost bus never delays stops on healthy buses (PLAN item 2, Stop; PLAN item 6, `host.bus`): with
/// one of the skeleton's buses missing, `disable` still stops every drive on the other on time, reports the missing
/// bus's drives as needing a person and exits with failure. And a lock it can't check makes it refuse (exit 2, no
/// report).
#[test]
fn a_missing_bus_fails_its_drives_and_the_other_bus_still_stops() {
    let text = std::fs::read_to_string(skeleton_path()).unwrap();
    // can0 becomes a bus with no interface: the vcan buses are can0 to can4.
    let skeleton_text = text.replace("can0", "can9");
    let skeleton = skeleton::parse(&skeleton_text).unwrap();
    // Absent, not merely not a vcan: on a machine with a real can9, this test would send to it.
    assert!(
        !Path::new("/sys/class/net/can9").exists(),
        "can9 must not exist for this test"
    );
    ensure_vcan("can1").unwrap();
    let dir = scratch("disable-missing");
    let path = dir.join("skeleton.yaml");
    std::fs::write(&path, &skeleton_text).unwrap();
    // A lock that can't be checked (a path under a regular file) refuses.
    let unknown = disable(&path, &path.join("runtime.lock"));
    let stop = AtomicBool::new(false);
    let done = std::thread::scope(|scope| {
        let _end = End(&stop);
        let mut sim = drives(&skeleton, "can1", &[]);
        let stop = &stop;
        scope.spawn(move || serve("can1", &mut sim, stop, &mut |_| {}));
        assert!(run_and_report("can1", &ids(&skeleton, "can1")));
        disable(&path, &dir.join("runtime.lock"))
    });
    let _ = std::fs::remove_dir_all(&dir);

    assert_eq!(unknown.status.code(), Some(2), "{unknown:?}");
    assert_eq!(
        unknown.stderr.lines().last(),
        Some(
            format!(
                "robot-cli: {}: Not a directory (os error 20); can't tell whether a runtime holds it, refusing",
                path.join("runtime.lock").display()
            )
            .as_str()
        ),
        "{unknown:?}"
    );
    assert!(unknown.outcomes.is_empty(), "{unknown:?}");
    assert_eq!(done.status.code(), Some(1), "{done:?}");
    assert!(done.took < Duration::from_secs(1), "{done:?}");
    assert_eq!(
        done.faults.get("can9"),
        Some(&Some("open".to_owned())),
        "{done:?}"
    );
    assert_eq!(done.faults.get("can1"), Some(&None), "{done:?}");
    for n in ids(&skeleton, "can9") {
        assert_eq!(
            done.outcomes
                .get(&("can9".to_owned(), n))
                .map(String::as_str),
            Some("bus_failed"),
            "{done:?}"
        );
    }
    for n in ids(&skeleton, "can1") {
        assert_eq!(
            done.outcomes
                .get(&("can1".to_owned(), n))
                .map(String::as_str),
            Some("stopped"),
            "{done:?}"
        );
    }
}
