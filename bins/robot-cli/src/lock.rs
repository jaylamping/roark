//! The runtime's lock: held by the runtime for as long as it runs, so `disable` never sends while it is alive
//! (architecture.md section 1: `robot-cli disable` must never run while `runtime` is alive). The kernel drops an
//! `flock` when its holder dies, by `kill -9` too, so a dead runtime never blocks the stop.
//!
//! Only the runtime makes the file. `disable` opens it read-only, which is enough to lock it, so any user who can read
//! it can tell whether a runtime holds it.

use std::fs::File;
use std::io;
use std::path::{Path, PathBuf};

use nix::errno::Errno;
use nix::fcntl::{Flock, FlockArg};

/// A held lock. It is released when this is dropped or the process ends, however it ends.
#[derive(Debug)]
pub struct Claim {
    _lock: Flock<File>,
}

/// Why the lock wasn't taken.
#[derive(Debug, thiserror::Error)]
pub enum LockError {
    /// Another process holds it: a runtime is alive, or another `disable` is running.
    #[error("{0} is held: a runtime (or another disable) is running")]
    Held(PathBuf),
    /// It doesn't exist: no runtime using this path is running (the runtime makes it at start; `/run` is cleared at
    /// boot, and systemd removes `/run/robot` once the runtime is stopped, after its `ExecStopPost`, but not before an
    /// automatic restart).
    #[error("{0} doesn't exist: no runtime using it is running")]
    Missing(PathBuf),
    /// It exists but couldn't be opened or locked (permissions, for one): whether a runtime holds it isn't known.
    #[error("{path}: {source}")]
    Unknown {
        /// The lock file.
        path: PathBuf,
        /// What failed.
        source: io::Error,
    },
}

/// Take the lock at `path` without waiting.
///
/// # Errors
/// [`LockError`]: `Held` while another process holds it, `Missing` when no runtime made it, `Unknown` otherwise.
pub fn claim(path: &Path) -> Result<Claim, LockError> {
    let file = File::open(path).map_err(|source| {
        if source.kind() == io::ErrorKind::NotFound {
            LockError::Missing(path.to_owned())
        } else {
            LockError::Unknown {
                path: path.to_owned(),
                source,
            }
        }
    })?;
    match Flock::lock(file, FlockArg::LockExclusiveNonblock) {
        Ok(lock) => Ok(Claim { _lock: lock }),
        Err((_, Errno::EWOULDBLOCK)) => Err(LockError::Held(path.to_owned())),
        Err((_, e)) => Err(LockError::Unknown {
            path: path.to_owned(),
            source: e.into(),
        }),
    }
}

#[cfg(test)]
mod tests {
    use super::{LockError, claim};

    /// Guards: safety - `robot-cli disable` never runs while the runtime is alive (architecture.md section 1): the lock
    /// is refused while another holder has it and taken once that holder lets go; a lock that doesn't exist is told
    /// apart from one that can't be checked, so only the first lets `disable` go on.
    #[test]
    fn the_lock_is_refused_while_held_and_unknown_when_it_cant_be_opened() {
        let dir = std::env::temp_dir().join(format!("robot-cli-lock-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join("runtime.lock");
        assert!(matches!(claim(&path), Err(LockError::Missing(_))));
        std::fs::write(&path, b"").unwrap();
        // flock locks belong to the open file, so a second open in this process is a second holder.
        let first = claim(&path).unwrap();
        assert!(matches!(claim(&path), Err(LockError::Held(_))));
        drop(first);
        drop(claim(&path).unwrap());
        // A path that can't be opened for a reason other than not existing (here ENOTDIR, which root gets too, as
        // another user gets EACCES on a runtime's file made 0600): whether a runtime holds it isn't known.
        assert!(matches!(
            claim(&path.join("under-a-file")),
            Err(LockError::Unknown { .. })
        ));
        let _ = std::fs::remove_dir_all(&dir);
    }
}
