//! `robot-cli disable`, the independent stop, as systemd runs it: the real binaries on `vcan` against `sim-drive`, with
//! the runtime's test robot (`bins/runtime/tests/skeleton.yaml`). It refuses while a runtime is alive, runs once the
//! runtime is killed with `kill -9`, and leaves every answering drive in Reset with reporting off, on every bus, even
//! when one of the skeleton's buses is gone.
//!
//! The binaries come from the build `scripts/sim.sh` makes before it runs the suite.
#![cfg(target_os = "linux")]

#[expect(dead_code, reason = "each test file uses some of the shared helpers")]
mod common;

use std::collections::BTreeSet;
use std::path::{Path, PathBuf};
use std::process::{Command, Output, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

use common::{binary, scratch};
use robstride::drive::{self, Command as HostCommand};
use robstride::{DeviceId, Inbound, Mode, Reporting, Uid, decode, encode};
use sim_drive::{SimDrive, ensure_vcan, serve};
use skeleton::Skeleton;
use socketcan::{CanDataFrame, CanFrame, CanSocket, EmbeddedFrame, ExtendedId, Id, Socket};

/// The runtime's test robot, never the live skeleton (testing.md rule 3).
fn skeleton_path() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../../bins/runtime/tests/skeleton.yaml")
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

/// Run `robot-cli disable` and return its output and how long it took.
#[expect(
    clippy::unwrap_used,
    reason = "test helper: the binary must run for the test to mean anything"
)]
fn disable(skeleton: &Path, lock: &Path) -> (Output, Duration) {
    let start = Instant::now();
    let out = Command::new(binary("robot-cli"))
        .arg("disable")
        .arg("--skeleton")
        .arg(skeleton)
        .arg("--lock")
        .arg(lock)
        .output()
        .unwrap();
    (out, start.elapsed())
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

/// What `disable` sent on one bus, and what the drives did after it, from the watcher's frames after `from`.
struct Bus {
    disabled: BTreeSet<u8>,
    reporting_off: BTreeSet<u8>,
    /// Host commands other than Disable and reporting off.
    other: Vec<HostCommand>,
    /// Drives that reported after `quiet`.
    reported_after: BTreeSet<u8>,
    /// Each drive's last mode seen.
    last_mode: Vec<(u8, Mode)>,
}

fn bus(seen: &[Seen], from: Instant, quiet: Instant) -> Bus {
    let mut b = Bus {
        disabled: BTreeSet::new(),
        reporting_off: BTreeSet::new(),
        other: Vec::new(),
        reported_after: BTreeSet::new(),
        last_mode: Vec::new(),
    };
    for s in seen.iter().filter(|s| s.at >= from) {
        if let Some(h) = s.host {
            match h.command {
                HostCommand::Disable => {
                    b.disabled.insert(h.target.get());
                }
                HostCommand::Reporting(Reporting::Off) => {
                    b.reporting_off.insert(h.target.get());
                }
                other => b.other.push(other),
            }
        }
        if let Some(Inbound::Status(st) | Inbound::Report(st)) = s.drive {
            let n = st.header.device.get();
            b.last_mode.retain(|(d, _)| *d != n);
            b.last_mode.push((n, st.header.mode));
            if s.at > quiet && matches!(s.drive, Some(Inbound::Report(_))) {
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
    // Every bus the skeleton names, so a bus added to it is checked before anything opens it.
    let names: Vec<&str> = skeleton.buses.iter().map(|b| b.name.as_str()).collect();
    for name in names.iter().copied() {
        ensure_vcan(name).unwrap();
    }
    let dir = scratch("disable");
    let lock = dir.join("runtime.lock");
    // Drive 31 is never served: it stands for a drive that is off.
    let silent = [31];
    let stop = AtomicBool::new(false);
    let (seen, refused, run, (out, took), from, quiet) = std::thread::scope(|scope| {
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
        let (refused, _) = disable(&path, &lock);
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
        let done = disable(&path, &lock);
        // Every report on its way when reporting off went has been read by now.
        let quiet = Instant::now();
        let end = quiet + Duration::from_millis(100);
        while Instant::now() < end {
            std::thread::yield_now();
        }
        stop.store(true, Ordering::Release);
        let seen: Vec<Vec<Seen>> = watchers.into_iter().map(|w| w.join().unwrap()).collect();
        (seen, refused, run, done, from, quiet)
    });
    let _ = std::fs::remove_dir_all(&dir);

    assert_eq!(refused.status.code(), Some(2), "{refused:?}");
    assert!(
        String::from_utf8_lossy(&refused.stderr).contains("is held"),
        "{refused:?}"
    );
    assert!(run, "the drives never reached Run with reporting on");
    let stdout = String::from_utf8_lossy(&out.stdout);
    assert_eq!(out.status.code(), Some(0), "{out:?}");
    assert!(took < Duration::from_secs(1), "disable took {took:?}");
    for (name, seen) in names.iter().zip(&seen) {
        let wired = ids(&skeleton, name);
        let b = bus(seen, from, quiet);
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
        for n in &wired {
            let want = if silent.contains(n) {
                ": silent"
            } else {
                ": stopped"
            };
            assert!(
                stdout
                    .lines()
                    .any(|l| l.starts_with(&format!("{name} {n} ")) && l.contains(want)),
                "{name} {n} should be{want}: {stdout}"
            );
        }
    }
}

/// Guards: safety - a lost bus never delays stops on healthy buses (PLAN item 2, Stop; PLAN item 6, `host.bus`): with
/// one of the skeleton's buses missing, `disable` still stops every drive on the other on time, reports the missing
/// bus's drives as needing a person and exits with failure.
#[test]
fn a_missing_bus_fails_its_drives_and_the_other_bus_still_stops() {
    let text = std::fs::read_to_string(skeleton_path()).unwrap();
    // can0 becomes a bus with no interface: the vcan buses are can0 to can4.
    let skeleton_text = text.replace("can0", "can9");
    let skeleton = skeleton::parse(&skeleton_text).unwrap();
    assert!(
        ensure_vcan("can9").is_err(),
        "can9 must not exist for this test"
    );
    // Every other bus the edited skeleton names is checked before anything opens it.
    for bus in skeleton
        .buses
        .iter()
        .map(|b| b.name.as_str())
        .filter(|&b| b != "can9")
    {
        ensure_vcan(bus).unwrap();
    }
    let dir = scratch("disable-missing");
    let path = dir.join("skeleton.yaml");
    std::fs::write(&path, &skeleton_text).unwrap();
    let stop = AtomicBool::new(false);
    let (out, took) = std::thread::scope(|scope| {
        let _end = End(&stop);
        let mut sim = drives(&skeleton, "can1", &[]);
        let stop = &stop;
        scope.spawn(move || serve("can1", &mut sim, stop, &mut |_| {}));
        assert!(run_and_report("can1", &ids(&skeleton, "can1")));
        disable(&path, &dir.join("runtime.lock"))
    });
    let _ = std::fs::remove_dir_all(&dir);

    let stdout = String::from_utf8_lossy(&out.stdout);
    assert_eq!(out.status.code(), Some(1), "{out:?}");
    assert!(took < Duration::from_secs(1), "disable took {took:?}");
    assert!(stdout.contains("can9: FAILED: can't open can9"), "{stdout}");
    for n in ids(&skeleton, "can9") {
        assert!(
            stdout
                .lines()
                .any(|l| l.starts_with(&format!("can9 {n} ")) && l.contains("FAILED")),
            "{stdout}"
        );
    }
    for n in ids(&skeleton, "can1") {
        assert!(
            stdout
                .lines()
                .any(|l| l.starts_with(&format!("can1 {n} ")) && l.contains(": stopped")),
            "{stdout}"
        );
    }
}
