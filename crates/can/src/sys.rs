//! The bus layer's only `unsafe` (rust.md section 10): reading one frame with its kernel timestamp, its direction flags
//! and the socket's overflow counter in one `recvmsg`, waiting on the socket with `ppoll`, and reading two socket
//! options back with `getsockopt`. `socketcan` 4.0 reads
//! timestamps but drops `msg_flags`, and `nix` truncates the flags to the ones it names, which excludes the two we need.
//! Everything else goes through `socketcan`'s and `nix`'s safe calls.

use std::io;
use std::mem::{size_of, zeroed};
use std::os::fd::{AsRawFd, BorrowedFd};
use std::time::Duration;

use telemetry::{Direction, FrameRecord};

/// `include/uapi/asm-generic/socket.h`, the same on aarch64 and x86-64.
pub(crate) const SO_RCVBUFFORCE: libc::c_int = 33;
const SO_TIMESTAMPNS_OLD: libc::c_int = 35;
pub(crate) const SO_RXQ_OVFL: libc::c_int = 40;
/// The 64-bit-time option (logging.md section 8.3: keeps working after 2038).
pub(crate) const SO_TIMESTAMPNS_NEW: libc::c_int = 64;

/// `include/uapi/linux/can.h`.
const CAN_EFF_FLAG: u32 = 0x8000_0000;
const CAN_RTR_FLAG: u32 = 0x4000_0000;
const CAN_ERR_FLAG: u32 = 0x2000_0000;
const CAN_EFF_MASK: u32 = 0x1FFF_FFFF;
const CAN_SFF_MASK: u32 = 0x0000_07FF;

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

/// Read one frame without blocking. `Ok(None)` when nothing is queued.
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
    // SAFETY: `fd` is an open socket for the borrow's lifetime; `msg` points at `iov` (one buffer the size of `frame`)
    // and `control`, all live and writable until the call returns.
    let n = unsafe { libc::recvmsg(fd.as_raw_fd(), &raw mut msg, libc::MSG_DONTWAIT) };
    if n < 0 {
        let e = io::Error::last_os_error();
        return if e.kind() == io::ErrorKind::WouldBlock {
            Ok(None)
        } else {
            Err(e)
        };
    }
    if usize::try_from(n).ok() != Some(size_of::<libc::can_frame>()) {
        // Not one whole frame: a kind, not a message, so the tick path never allocates.
        return Err(io::Error::from(io::ErrorKind::InvalidData));
    }
    let mut stamp_ns = 0;
    let mut drops = None;
    // SAFETY: `msg` was filled by a successful `recvmsg`, so its control pointer and length describe `control`, and
    // the CMSG macros walk only inside it. Each payload is read unaligned and only when its length covers the type.
    unsafe {
        let mut cmsg = libc::CMSG_FIRSTHDR(&raw const msg);
        while !cmsg.is_null() {
            let level = (*cmsg).cmsg_level;
            let kind = (*cmsg).cmsg_type;
            let len = (*cmsg).cmsg_len;
            let data = libc::CMSG_DATA(cmsg);
            // A length that doesn't fit is never satisfied, so its payload is never read.
            let ts_len = usize::try_from(libc::CMSG_LEN(TIMESPEC_BYTES)).unwrap_or(usize::MAX);
            let u32_len = usize::try_from(libc::CMSG_LEN(U32_BYTES)).unwrap_or(usize::MAX);
            if level == libc::SOL_SOCKET
                && (kind == SO_TIMESTAMPNS_NEW || kind == SO_TIMESTAMPNS_OLD)
                && len >= ts_len
            {
                let ts = data.cast::<libc::timespec>().read_unaligned();
                stamp_ns = timespec_ns(ts.tv_sec, ts.tv_nsec);
            } else if level == libc::SOL_SOCKET && kind == SO_RXQ_OVFL && len >= u32_len {
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
    let ts = libc::timespec {
        tv_sec: libc::time_t::try_from(timeout.as_secs()).unwrap_or(libc::time_t::MAX),
        tv_nsec: libc::c_long::from(timeout.subsec_nanos()),
    };
    let mut pfd = libc::pollfd {
        fd: fd.as_raw_fd(),
        events: libc::POLLIN,
        revents: 0,
    };
    // SAFETY: one valid `pollfd` for an fd that is open for the borrow's lifetime, a valid `timespec`, no signal mask.
    let n = unsafe { libc::ppoll(&raw mut pfd, 1, &raw const ts, std::ptr::null()) };
    if n < 0 {
        let e = io::Error::last_os_error();
        return if e.kind() == io::ErrorKind::Interrupted {
            Ok(false)
        } else {
            Err(e)
        };
    }
    if pfd.revents & (libc::POLLERR | libc::POLLHUP | libc::POLLNVAL) != 0 {
        let errno = socket_option(fd, libc::SO_ERROR)?;
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
    let bytes = socket_option(fd, libc::SO_RCVBUF)?;
    usize::try_from(bytes).map_err(|_| io::Error::from(io::ErrorKind::InvalidData))
}

/// One `SOL_SOCKET` integer option.
fn socket_option(fd: BorrowedFd<'_>, option: libc::c_int) -> io::Result<libc::c_int> {
    let mut value: libc::c_int = 0;
    let mut len = libc::socklen_t::try_from(size_of::<libc::c_int>()).unwrap_or_default();
    // SAFETY: `fd` is open for the borrow's lifetime; `value` and `len` are live and writable, and `len` holds
    // `value`'s size.
    let rc = unsafe {
        libc::getsockopt(
            fd.as_raw_fd(),
            libc::SOL_SOCKET,
            option,
            (&raw mut value).cast(),
            &raw mut len,
        )
    };
    if rc < 0 {
        Err(io::Error::last_os_error())
    } else {
        Ok(value)
    }
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
    let extended = raw & CAN_EFF_FLAG != 0;
    let error = raw & CAN_ERR_FLAG != 0;
    let id = if extended || error {
        raw & CAN_EFF_MASK
    } else {
        raw & CAN_SFF_MASK
    };
    FrameRecord {
        id,
        extended,
        error,
        remote: raw & CAN_RTR_FLAG != 0,
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
