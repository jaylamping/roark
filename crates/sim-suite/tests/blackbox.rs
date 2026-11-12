//! The black box on `vcan`: `candump-rotate` running `candump` the way `candump@<bus>.service` does, read back the way a
//! person would (logging.md section 8.6).
#![cfg(target_os = "linux")]

use std::io::Read as _;
use std::os::unix::process::CommandExt as _;
use std::path::{Path, PathBuf};
use std::process::{Child, Command};
use std::time::{Duration, Instant};

use nix::sys::signal::{Signal, kill, killpg};
use nix::unistd::Pid;
use sim_drive::ensure_vcan;
use socketcan::{CanDataFrame, CanSocket, EmbeddedFrame, Socket, StandardId};

/// A bus no test outside the `can0` group uses; this file is in that group (`.config/nextest.toml`).
const BUS: &str = "can3";
/// Sent until the black box has it, so it is known to be capturing before the counted frames start.
const MARKER: u16 = 0x7AB;
/// The counted frames: data is a big-endian `u32` counter.
const COUNTED: u16 = 0x7AC;
/// One counted frame every this long.
const PACE: Duration = Duration::from_millis(1);

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

/// An empty scratch directory for this test.
#[expect(
    clippy::unwrap_used,
    reason = "test helper: the temp directory is writable"
)]
fn scratch(test: &str) -> PathBuf {
    let dir = std::env::temp_dir().join(format!("sim-suite-{test}-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    dir
}

/// `candump-rotate` and its `candump`, in their own process group so a test can end both.
struct BlackBox(Child);

impl BlackBox {
    fn pid(&self) -> Pid {
        Pid::from_raw(i32::try_from(self.0.id()).unwrap_or(i32::MAX))
    }
}

impl Drop for BlackBox {
    fn drop(&mut self) {
        let _ = killpg(self.pid(), Signal::SIGKILL);
        let _ = self.0.wait();
    }
}

/// Start the black box on `BUS` into `dir`, cutting every `cut_secs`, with the unit's `candump` flags but `-r`: the unit
/// grants `CAP_NET_ADMIN` for it, and the test runs without that capability.
#[expect(clippy::unwrap_used, reason = "test helper: the black box must start")]
fn start(dir: &Path, cut_secs: u32) -> BlackBox {
    ensure_vcan(BUS).unwrap();
    let child = Command::new(binary("candump-rotate"))
        .args(["--bus", BUS, "--dir"])
        .arg(dir)
        .args([
            "--cut-secs",
            &cut_secs.to_string(),
            "--keep-days",
            "7",
            "--",
        ])
        .args(["candump", "-L", "-x", "-d", "-D"])
        .arg(format!("{BUS},0:0,#FFFFFFFF"))
        .process_group(0)
        .spawn()
        .unwrap();
    BlackBox(child)
}

#[expect(clippy::unwrap_used, reason = "test helper: the frame must go out")]
fn send(socket: &CanSocket, id: u16, data: &[u8]) {
    let frame = CanDataFrame::new(StandardId::new(id).unwrap(), data).unwrap();
    socket.write_frame(&frame).unwrap();
}

/// The black box's files for `BUS` in `dir`, oldest first: the UTC start in each name sorts them.
#[expect(clippy::unwrap_used, reason = "test helper: the directory is readable")]
fn files(dir: &Path) -> Vec<PathBuf> {
    let mut files: Vec<PathBuf> = std::fs::read_dir(dir)
        .unwrap()
        .map(|e| e.unwrap().path())
        .filter(|p| {
            p.file_name()
                .and_then(|n| n.to_str())
                .is_some_and(|n| n.starts_with(&format!("{BUS}-")) && n.ends_with(".log.zst"))
        })
        .collect();
    files.sort();
    files
}

/// Every whole line a file reads back, and whether the file ended cleanly. A file cut off mid-write gives what came
/// before its last complete zstd block.
#[expect(clippy::unwrap_used, reason = "test helper: the file exists")]
fn read(path: &Path) -> (Vec<String>, bool) {
    let mut out = Vec::new();
    let clean = zstd::stream::read::Decoder::new(std::fs::File::open(path).unwrap())
        .and_then(|mut d| d.read_to_end(&mut out))
        .is_ok();
    let text = String::from_utf8_lossy(&out);
    let whole = text.rfind('\n').map_or("", |end| &text[..=end]);
    (whole.lines().map(str::to_owned).collect(), clean)
}

/// The counters of the counted frames in `lines`, in order. Each must be a `candump -L -x` line from `BUS`, marked
/// sent from this host: `(<seconds>.<micros>) can3 7AC#0000002A T`.
#[expect(clippy::unwrap_used, reason = "test helper: a bad line fails the test")]
fn counters(lines: &[String]) -> Vec<u32> {
    lines
        .iter()
        .filter_map(|line| {
            let mut parts = line.split(' ');
            let (stamp, bus, frame, dir) =
                (parts.next()?, parts.next()?, parts.next()?, parts.next());
            assert!(stamp.starts_with('(') && stamp.ends_with(')'), "{line}");
            assert_eq!(bus, BUS, "{line}");
            assert_eq!(dir, Some("T"), "{line}");
            let (id, data) = frame.split_once('#').unwrap();
            (id == format!("{COUNTED:03X}")).then(|| u32::from_str_radix(data, 16).unwrap())
        })
        .collect()
}

/// Every counter read back from all of `dir`'s files so far, and whether every file ended cleanly.
fn read_all(dir: &Path) -> (Vec<u32>, bool) {
    let mut all = Vec::new();
    let mut clean = true;
    for file in files(dir) {
        let (lines, ok) = read(&file);
        all.extend(counters(&lines));
        clean &= ok;
    }
    (all, clean)
}

/// Send the marker until the black box has written it to a file, so everything after is captured.
#[expect(clippy::unwrap_used, reason = "test helper: the bus is up")]
fn wait_until_capturing(dir: &Path) -> CanSocket {
    let socket = CanSocket::open(BUS).unwrap();
    let marker = format!(" {MARKER:03X}#");
    let end = Instant::now() + Duration::from_secs(10);
    let mut next = Instant::now();
    loop {
        if files(dir)
            .iter()
            .any(|f| read(f).0.iter().any(|l| l.contains(&marker)))
        {
            return socket;
        }
        assert!(Instant::now() < end, "the black box never wrote the marker");
        if Instant::now() >= next {
            send(&socket, MARKER, &[0; 8]);
            next += Duration::from_millis(50);
        }
        // Waiting on an outside process with a deadline (testing.md rule 6), not a fixed nap.
        std::thread::yield_now();
    }
}

/// Send counted frames one per `PACE` from `first` until `done(sent so far)` holds; returns the next counter.
fn send_until(
    socket: &CanSocket,
    first: u32,
    what: &str,
    mut done: impl FnMut(u32) -> bool,
) -> u32 {
    let end = Instant::now() + Duration::from_secs(20);
    let mut n = first;
    let mut next = Instant::now();
    while !done(n) {
        assert!(Instant::now() < end, "timed out waiting for {what}");
        if Instant::now() >= next {
            send(socket, COUNTED, &n.to_be_bytes());
            n += 1;
            next += PACE;
        }
        std::thread::yield_now();
    }
    n
}

/// Guards: safety - the black box keeps every frame the kernel saw across its file cuts, and stopping it closes its
/// last file cleanly, so the record has no gap a fault could hide in (logging.md section 8.6: restarting candump to
/// cut a file leaves gaps).
#[test]
fn every_frame_lands_once_across_cuts_and_a_stop_closes_cleanly() {
    let dir = scratch("blackbox-cuts");
    let mut black_box = start(&dir, 1);
    let socket = wait_until_capturing(&dir);

    // Frames for at least two cuts after the marker's file.
    let sent = send_until(&socket, 0, "two cuts", |_| files(&dir).len() >= 3);
    // Everything sent is in a file before the stop: candump drops what it hasn't read when it ends.
    let end = Instant::now() + Duration::from_secs(10);
    while read_all(&dir).0.len() < usize::try_from(sent).unwrap_or(usize::MAX) {
        assert!(
            Instant::now() < end,
            "the black box never wrote frame {}",
            sent - 1
        );
        std::thread::yield_now();
    }

    // SIGTERM to candump-rotate alone: it passes it on to candump, then closes its file when candump ends.
    kill(black_box.pid(), Signal::SIGTERM).unwrap();
    let end = Instant::now() + Duration::from_secs(10);
    let status = loop {
        if let Some(status) = black_box.0.try_wait().unwrap() {
            break status;
        }
        assert!(Instant::now() < end, "the black box didn't stop on SIGTERM");
        std::thread::yield_now();
    };
    assert!(status.success(), "{status:?}");

    let (counters, clean) = read_all(&dir);
    assert!(clean, "a file didn't end cleanly: {:?}", files(&dir));
    assert!(files(&dir).len() >= 3, "{:?}", files(&dir));
    assert_eq!(
        counters,
        (0..sent).collect::<Vec<_>>(),
        "frames lost, repeated or out of order"
    );
    let _ = std::fs::remove_dir_all(&dir);
}

/// Guards: safety - a black box killed mid-file (a crash) leaves a file that reads back up to its last one-second block,
/// so it covers what the runtime's recording lost in the same crash (logging.md section 8.4). A power cut also needs
/// the sync after each block, which this can't show.
#[test]
fn a_killed_black_box_leaves_a_file_that_reads_back() {
    let dir = scratch("blackbox-kill");
    let black_box = start(&dir, 3600);
    let socket = wait_until_capturing(&dir);

    let mut seen = 0;
    send_until(&socket, 0, "a block with 100 frames", |_| {
        seen = read_all(&dir).0.len();
        seen >= 100
    });
    killpg(black_box.pid(), Signal::SIGKILL).unwrap();
    drop(black_box);

    let (counters, clean) = read_all(&dir);
    assert!(
        !clean,
        "the file ended cleanly though its writer was killed"
    );
    assert!(
        counters.len() >= seen,
        "{} frames read back, {seen} before the kill",
        counters.len()
    );
    assert_eq!(
        counters,
        (0..u32::try_from(counters.len()).unwrap_or(u32::MAX)).collect::<Vec<_>>(),
        "frames lost, repeated or out of order"
    );
    let _ = std::fs::remove_dir_all(&dir);
}
