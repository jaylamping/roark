//! The bus layer's only `unsafe` (rust.md section 10): reading one frame with its kernel timestamp, its direction flags
//! and the socket's overflow counter in one `recvmsg`. `socketcan` 4.0 reads timestamps but drops `msg_flags`, and
//! `nix` truncates the flags to the ones it names, which excludes the two we need. Waiting on the socket and reading
//! socket options go through `nix`'s safe calls.

use std::io;
use std::mem::{size_of, zeroed};
use std::os::fd::{AsRawFd, BorrowedFd};
use std::time::Duration;

use nix::errno::Errno;
use nix::poll::{PollFd, PollFlags, ppoll};
use nix::sys::socket::{getsockopt, sockopt};
use nix::sys::time::TimeSpec;
use telemetry::{Direction, FrameRecord};

/// Payload sizes for `CMSG_LEN`: a `timespec` is two 64-bit fields on every target this runs on, a count is 4 bytes.
const TIMESPEC_BYTES: libc::c_uint = 16;
const U32_BYTES: libc::c_uint = 4;
const _: () = assert!(size_of::<libc::timespec>() == 16);

/// One frame as the socket delivered it.
#[derive(Clone, Copy, Debug)]
pub(crate) struct Received {
    pub(crate) frame: FrameRecord,
    /// The socket's cumulative overflow count, when the kernel attached it (only to frames queued after a drop).
    pub(crate) drops: Option<u32>,
}

/// Room for a timestamp and an overflow count, aligned for `cmsghdr`.
#[repr(C, align(8))]
struct ControlBuffer([u8; 128]);

/// Read one frame without blocking. `Ok(None)` when nothing is queued; `Interrupted` when two signals in a row cut the
/// read short.
pub(crate) fn recv(fd: BorrowedFd<'_>) -> io::Result<Option<Received>> {
    // SAFETY: `can_frame` is plain old data; all-zero is a valid value.
    let mut frame: libc::can_frame = unsafe { zeroed() };
    let mut control = ControlBuffer([0; 128]);
    let mut iov = libc::iovec {
        iov_base: (&raw mut frame).cast(),
        iov_len: size_of::<libc::can_frame>(),
    };
    // SAFETY: `msghdr` is plain old data; all-zero is a valid empty header, filled in below.
    let mut msg: libc::msghdr = unsafe { zeroed() };
    msg.msg_iov = &raw mut iov;
    msg.msg_iovlen = 1;
    msg.msg_control = control.0.as_mut_ptr().cast();
    msg.msg_controllen = control.0.len();
    // A signal can interrupt even a non-blocking call; that is no news about the socket, so read once more. A second
    // interruption in a row comes back as `Interrupted`: whether frames are still queued isn't known, so the drain
    // reports the socket unemptied.
    let mut interrupted = false;
    let n = loop {
        msg.msg_controllen = control.0.len();
        // SAFETY: `fd` is an open socket for the borrow's lifetime; `msg` points at `iov` (one buffer the size of
        // `frame`) and `control`, all live and writable until the call returns.
        let n = unsafe { libc::recvmsg(fd.as_raw_fd(), &raw mut msg, libc::MSG_DONTWAIT) };
        if n >= 0 {
            break n;
        }
        let e = io::Error::last_os_error();
        if e.kind() == io::ErrorKind::WouldBlock {
            return Ok(None);
        }
        if e.kind() != io::ErrorKind::Interrupted || interrupted {
            return Err(e);
        }
        interrupted = true;
    };
    if usize::try_from(n).ok() != Some(size_of::<libc::can_frame>()) {
        // Not one whole frame: a kind, not a message, so the tick path never allocates.
        return Err(io::Error::from(io::ErrorKind::InvalidData));
    }
    let mut stamp_ns = 0;
    let mut drops = None;
    // A length that doesn't fit is never satisfied, so its payload is never read.
    // SAFETY: `CMSG_LEN` is arithmetic on its argument; it reads no memory.
    let (ts_len, u32_len) = unsafe { (libc::CMSG_LEN(TIMESPEC_BYTES), libc::CMSG_LEN(U32_BYTES)) };
    let ts_len = usize::try_from(ts_len).unwrap_or(usize::MAX);
    let u32_len = usize::try_from(u32_len).unwrap_or(usize::MAX);
    // SAFETY: `msg` was filled by a successful `recvmsg`, so its control pointer and length describe `control`, and
    // the CMSG macros walk only inside it. Each payload is read unaligned and only when its length covers the type.
    unsafe {
        let mut cmsg = libc::CMSG_FIRSTHDR(&raw const msg);
        while !cmsg.is_null() {
            let level = (*cmsg).cmsg_level;
            let kind = (*cmsg).cmsg_type;
            let len = (*cmsg).cmsg_len;
            let data = libc::CMSG_DATA(cmsg);
            if level == libc::SOL_SOCKET
                // `SO_TIMESTAMPNS` is the old, `time_t`-sized value; on 64-bit targets its payload is the same.
                && (kind == libc::SO_TIMESTAMPNS_NEW || kind == libc::SO_TIMESTAMPNS)
                && len >= ts_len
            {
                let ts = data.cast::<libc::timespec>().read_unaligned();
                stamp_ns = timespec_ns(ts.tv_sec, ts.tv_nsec);
            } else if level == libc::SOL_SOCKET && kind == libc::SO_RXQ_OVFL && len >= u32_len {
                drops = Some(data.cast::<u32>().read_unaligned());
            }
            cmsg = libc::CMSG_NXTHDR(&raw const msg, cmsg);
        }
    }
    Ok(Some(Received {
        frame: record(&frame, stamp_ns, direction(msg.msg_flags)),
        drops,
    }))
}

/// Wait up to `timeout` for a frame, to the nanosecond. True if one is ready. An error on the socket comes back as
/// its own errno (`ENODEV` when the interface is gone), `ENETDOWN` when it has none.
pub(crate) fn wait(fd: BorrowedFd<'_>, timeout: Duration) -> io::Result<bool> {
    let mut fds = [PollFd::new(fd, PollFlags::POLLIN)];
    let n = match ppoll(&mut fds, Some(TimeSpec::from_duration(timeout)), None) {
        Ok(n) => n,
        // A signal: no frame yet; the caller waits again until its deadline.
        Err(Errno::EINTR) => return Ok(false),
        Err(e) => return Err(e.into()),
    };
    let broken = PollFlags::POLLERR | PollFlags::POLLHUP | PollFlags::POLLNVAL;
    if fds[0].revents().is_some_and(|r| r.intersects(broken)) {
        let errno = getsockopt(&fd, sockopt::SocketError).map_err(io::Error::from)?;
        return Err(io::Error::from_raw_os_error(if errno == 0 {
            libc::ENETDOWN
        } else {
            errno
        }));
    }
    Ok(n > 0)
}

/// The socket's receive buffer, as the kernel reports it.
pub(crate) fn receive_buffer(fd: BorrowedFd<'_>) -> io::Result<usize> {
    getsockopt(&fd, sockopt::RcvBuf).map_err(io::Error::from)
}

/// `MSG_CONFIRM` marks a frame this socket sent; `MSG_DONTROUTE` one sent from this host (measured on `vcan`: our own
/// echo carries both, another local socket's only the second).
fn direction(flags: libc::c_int) -> Direction {
    if flags & libc::MSG_CONFIRM != 0 {
        Direction::TxEcho
    } else if flags & libc::MSG_DONTROUTE != 0 {
        Direction::TxOther
    } else {
        Direction::Rx
    }
}

fn record(frame: &libc::can_frame, stamp_ns: u64, direction: Direction) -> FrameRecord {
    let raw = frame.can_id;
    let extended = raw & libc::CAN_EFF_FLAG != 0;
    let error = raw & libc::CAN_ERR_FLAG != 0;
    let id = if extended || error {
        raw & libc::CAN_EFF_MASK
    } else {
        raw & libc::CAN_SFF_MASK
    };
    FrameRecord {
        id,
        extended,
        error,
        remote: raw & libc::CAN_RTR_FLAG != 0,
        len: frame.can_dlc.min(8),
        data: frame.data,
        stamp_ns,
        direction,
    }
}

fn timespec_ns(sec: libc::time_t, nsec: libc::c_long) -> u64 {
    let sec = u64::try_from(sec).unwrap_or(0);
    let nsec = u64::try_from(nsec).unwrap_or(0);
    sec.saturating_mul(1_000_000_000).saturating_add(nsec)
}
