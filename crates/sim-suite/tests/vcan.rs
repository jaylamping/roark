//! `sim-drive` on a real `vcan` socket: the refusal that keeps it off real buses, and a drive answering host frames
//! through the kernel the way the runtime will see it.
#![cfg(target_os = "linux")]

use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

use robstride::{DeviceId, Drive, Inbound, Mode, Model, Uid, decode, encode};
use sim_drive::{NotVcan, ServeError, SimDrive, ensure_vcan, serve};
use socketcan::{CanDataFrame, CanFrame, CanSocket, EmbeddedFrame, ExtendedId, Id, Socket};

/// A bus the skeleton doesn't use yet, so nothing else on a dev box is talking on it.
const BUS: &str = "can4";

#[expect(
    clippy::unwrap_used,
    reason = "test helper; clippy allows unwrap only inside #[test] bodies"
)]
fn id(n: u8) -> DeviceId {
    DeviceId::new(u64::from(n)).unwrap()
}

/// The host's end of `bus`, opened only once `bus` is known to be `vcan`.
#[expect(
    clippy::unwrap_used,
    reason = "test helper; clippy allows unwrap only inside #[test] bodies"
)]
fn host_socket(bus: &str) -> CanSocket {
    ensure_vcan(bus).unwrap();
    let socket = CanSocket::open(bus).unwrap();
    socket.set_read_timeout(Duration::from_millis(5)).unwrap();
    socket
}

#[expect(
    clippy::unwrap_used,
    reason = "test helper; clippy allows unwrap only inside #[test] bodies"
)]
fn send(socket: &CanSocket, frame: robstride::Frame) {
    let data = CanDataFrame::new(ExtendedId::new(frame.id()).unwrap(), &frame.data()).unwrap();
    socket.write_frame(&data).unwrap();
}

/// The first frame from the drives that decodes, waiting at most `deadline` (testing.md rule 6: wait with a deadline,
/// never a fixed nap).
fn next_reply(socket: &CanSocket, deadline: Duration) -> Option<Inbound> {
    let end = Instant::now() + deadline;
    while Instant::now() < end {
        if let Ok(CanFrame::Data(frame)) = socket.read_frame()
            && let Id::Extended(id) = frame.id()
            && let Ok(inbound) = decode(id.as_raw(), frame.data())
            && !matches!(inbound, Inbound::Echo(_))
        {
            return Some(inbound);
        }
    }
    None
}

/// Guards: safety - sim-drive and the sim tests refuse any interface `ip` doesn't call `vcan` before a frame is sent, so
/// running the sim suite on the Pi can't put simulated replies or host commands on a real bus (testing.md rule 8).
#[test]
fn only_vcan_is_served() {
    assert!(
        matches!(ensure_vcan("lo"), Err(NotVcan::OtherKind { .. })),
        "lo"
    );
    assert!(
        matches!(ensure_vcan("nosuchbus0"), Err(NotVcan::Unchecked { .. })),
        "missing"
    );
    assert!(
        matches!(ensure_vcan("-v"), Err(NotVcan::Unchecked { .. })),
        "an ip flag"
    );
    ensure_vcan(BUS).unwrap();

    let stop = AtomicBool::new(false);
    let mut drives = [SimDrive::new(
        Drive::new(id(1), Model::Rs03),
        Uid([0; 8]),
        0,
    )];
    let refused = serve("lo", &mut drives, &stop);
    assert!(
        matches!(refused, Err(ServeError::NotVcan(NotVcan::OtherKind { .. }))),
        "{refused:?}"
    );
}

/// Guards: protocol - a simulated drive on vcan answers the host's frames through the kernel: identity to type 0, and
/// a status in Run to an enable (RobStride manuals §4.1.1 to §4.1.3; PLAN item 4).
#[test]
fn a_drive_on_vcan_answers_the_host() {
    let uid = Uid([0x51, 0x4D, 1, 2, 3, 4, 5, 6]);
    let mut drives = [SimDrive::new(Drive::new(id(21), Model::Rs03), uid, 11)];
    let stop = AtomicBool::new(false);
    let host = host_socket(BUS);
    std::thread::scope(|scope| {
        let sim = scope.spawn(|| serve(BUS, &mut drives, &stop));

        // The sim thread may not have its socket open yet: ask until it answers, for at most a second.
        let started = Instant::now();
        let identity = loop {
            send(&host, encode::get_id(id(21)));
            if let Some(reply) = next_reply(&host, Duration::from_millis(20)) {
                break Some(reply);
            }
            if started.elapsed() > Duration::from_secs(1) {
                break None;
            }
        };
        assert_eq!(
            identity,
            Some(Inbound::Identity {
                device: id(21),
                uid
            })
        );

        send(&host, encode::enable(id(21)));
        let status = next_reply(&host, Duration::from_millis(50));
        let mode = match status {
            Some(Inbound::Status(s)) => Some(s.header.mode),
            _ => None,
        };
        assert_eq!(mode, Some(Mode::Run), "{status:?}");

        stop.store(true, Ordering::Relaxed);
        sim.join().unwrap().unwrap();
    });
}
