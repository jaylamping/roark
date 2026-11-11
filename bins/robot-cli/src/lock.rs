//! The runtime's lock: held by the runtime for as long as it runs, so `disable` never sends while it is alive
//! (architecture.md section 1: `robot-cli disable` must never run while `runtime` is alive). The kernel drops an
//! `flock` when its holder dies, by `kill -9` too, so a dead runtime never blocks the stop.

use std::fs::{File, OpenOptions};
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
    /// Its directory doesn't exist: no runtime has made it (systemd makes `/run/robot` when the runtime starts).
    #[error("{path}: no such directory")]
    NoDirectory {
        /// The lock file.
        path: PathBuf,
    },
    /// It couldn't be opened or locked for another reason.
    #[error("{path}: {source}")]
    Io {
        /// The lock file.
        path: PathBuf,
        /// What failed.
        source: io::Error,
    },
}

/// Take the lock at `path` without waiting, making the file if needed.
///
/// # Errors
/// [`LockError`]: `Held` while another process holds it.
pub fn claim(path: &Path) -> Result<Claim, LockError> {
    let file = OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .truncate(false)
        .open(path)
        .map_err(|source| {
            if source.kind() == io::ErrorKind::NotFound {
                LockError::NoDirectory {
                    path: path.to_owned(),
                }
            } else {
                LockError::Io {
                    path: path.to_owned(),
                    source,
                }
            }
        })?;
    match Flock::lock(file, FlockArg::LockExclusiveNonblock) {
        Ok(lock) => Ok(Claim { _lock: lock }),
        Err((_, Errno::EWOULDBLOCK)) => Err(LockError::Held(path.to_owned())),
        Err((_, e)) => Err(LockError::Io {
            path: path.to_owned(),
            source: e.into(),
        }),
    }
}

#[cfg(test)]
mod tests {
    use super::{LockError, claim};

    /// Guards: safety - `robot-cli disable` never runs while the runtime is alive (architecture.md section 1): the lock
    /// is refused while another holder has it, taken once that holder lets go, and a missing directory is told apart
    /// from a held lock.
    #[test]
    fn the_lock_is_refused_while_held_and_taken_once_released() {
        let dir = std::env::temp_dir().join(format!("robot-cli-lock-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join("runtime.lock");
        // flock locks belong to the open file, so a second open in this process is a second holder.
        let first = claim(&path).unwrap();
        assert!(matches!(claim(&path), Err(LockError::Held(_))));
        drop(first);
        assert!(claim(&path).is_ok());
        assert!(matches!(
            claim(&dir.join("gone").join("runtime.lock")),
            Err(LockError::NoDirectory { .. })
        ));
        let _ = std::fs::remove_dir_all(&dir);
    }
}
