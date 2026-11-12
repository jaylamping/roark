//! The black box's files: their names, the one being written, cutting it, and pruning old ones.

use std::fs::{self, File, OpenOptions};
use std::io::{self, Write as _};
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use zstd::stream::write::Encoder;

/// Every black-box file ends with this; the name before it is `<bus>-<UTC start>`.
pub(crate) const SUFFIX: &str = ".log.zst";
/// zstd's default level: on a Pi 5 it compresses far faster than five buses of `candump -L` text arrive.
const LEVEL: i32 = 3;

/// `YYYYMMDDTHHMMSSZ` for `secs` seconds after the Unix epoch (ISO 8601 basic format, UTC).
pub(crate) fn utc_stamp(secs: u64) -> String {
    let (y, m, d) = civil_from_days(secs / 86_400);
    let s = secs % 86_400;
    format!(
        "{y:04}{m:02}{d:02}T{:02}{:02}{:02}Z",
        s / 3600,
        s % 3600 / 60,
        s % 60
    )
}

/// The calendar date `days` days after 1970-01-01 (Howard Hinnant's `civil_from_days`, for days on or after it).
fn civil_from_days(days: u64) -> (u64, u64, u64) {
    let z = days + 719_468;
    let era = z / 146_097;
    let doe = z - era * 146_097;
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let day = doy - (153 * mp + 2) / 5 + 1;
    let month = if mp < 10 { mp + 3 } else { mp - 9 };
    let year = yoe + era * 400 + u64::from(month <= 2);
    (year, month, day)
}

/// Whether `name` is one of `bus`'s files. The dash keeps `can1` from claiming `can10`'s.
fn is_bus_file(name: &str, bus: &str) -> bool {
    name.strip_prefix(bus)
        .and_then(|rest| rest.strip_prefix('-'))
        .is_some_and(|rest| rest.ends_with(SUFFIX))
}

/// Make `<bus>-<UTC start>.log.zst` in `dir`, never over an existing file: a restart within the same second gets `-1`,
/// `-2` and so on.
fn create(dir: &Path, bus: &str, start: SystemTime) -> io::Result<(PathBuf, File)> {
    let secs = start.duration_since(UNIX_EPOCH).map_or(0, |d| d.as_secs());
    let stamp = utc_stamp(secs);
    for n in 0..100_u32 {
        let name = if n == 0 {
            format!("{bus}-{stamp}{SUFFIX}")
        } else {
            format!("{bus}-{stamp}-{n}{SUFFIX}")
        };
        let path = dir.join(name);
        match OpenOptions::new().write(true).create_new(true).open(&path) {
            Ok(file) => return Ok((path, file)),
            Err(e) if e.kind() == io::ErrorKind::AlreadyExists => {}
            Err(e) => return Err(e),
        }
    }
    Err(io::Error::new(
        io::ErrorKind::AlreadyExists,
        format!("100 files named {bus}-{stamp} already in {}", dir.display()),
    ))
}

/// A file that has been finished: complete, synced, and its directory entry synced.
#[derive(Debug)]
pub(crate) struct Closed {
    pub(crate) path: PathBuf,
    pub(crate) lines: u64,
}

struct Current {
    path: PathBuf,
    encoder: Encoder<'static, File>,
    opened: Instant,
    lines: u64,
    unflushed: bool,
}

/// Writes one bus's lines to a file that is cut every `cut`. A file is opened at the first line after a cut, so a quiet
/// bus makes no empty files.
pub(crate) struct Rotator {
    dir: PathBuf,
    bus: String,
    cut: Duration,
    current: Option<Current>,
}

impl Rotator {
    pub(crate) fn new(dir: PathBuf, bus: String, cut: Duration) -> Self {
        Self {
            dir,
            bus,
            cut,
            current: None,
        }
    }

    /// Write one line, newline included, to the open file, first closing it if its time is up and opening the next.
    /// `wall` names a new file; `now` times the cut. Returns the file it closed.
    pub(crate) fn line(
        &mut self,
        line: &[u8],
        wall: SystemTime,
        now: Instant,
    ) -> io::Result<Option<Closed>> {
        let closed = if self.due(now) { self.close()? } else { None };
        if self.current.is_none() {
            let (path, file) = create(&self.dir, &self.bus, wall)?;
            // The new name is in the directory before the first line is (deploy.md section 1, power loss).
            File::open(&self.dir)?.sync_all()?;
            self.current = Some(Current {
                path,
                encoder: Encoder::new(file, LEVEL)?,
                opened: now,
                lines: 0,
                unflushed: false,
            });
        }
        let Some(current) = &mut self.current else {
            return Ok(closed);
        };
        current.encoder.write_all(line)?;
        current.lines += 1;
        current.unflushed = true;
        Ok(closed)
    }

    /// Run once a second: close the file if its time is up (so a bus gone quiet doesn't leave it open), otherwise
    /// end a zstd block so everything written so far reads back after a crash.
    pub(crate) fn tick(&mut self, now: Instant) -> io::Result<Option<Closed>> {
        if self.due(now) {
            return self.close();
        }
        if let Some(c) = &mut self.current
            && c.unflushed
        {
            c.encoder.flush()?;
            c.unflushed = false;
        }
        Ok(None)
    }

    fn due(&self, now: Instant) -> bool {
        self.current
            .as_ref()
            .is_some_and(|c| now.saturating_duration_since(c.opened) >= self.cut)
    }

    /// Finish the open file: end its zstd frame and sync it to disk.
    pub(crate) fn close(&mut self) -> io::Result<Option<Closed>> {
        let Some(c) = self.current.take() else {
            return Ok(None);
        };
        let file = c.encoder.finish()?;
        file.sync_all()?;
        Ok(Some(Closed {
            path: c.path,
            lines: c.lines,
        }))
    }
}

/// Delete `bus`'s files in `dir` last written more than `keep` before `now`, except `open`. Returns what it deleted
/// and the first error it met; it goes on past an error, so one bad file doesn't keep the rest forever.
pub(crate) fn prune(
    dir: &Path,
    bus: &str,
    keep: Duration,
    now: SystemTime,
    open: Option<&Path>,
) -> (Vec<PathBuf>, Option<io::Error>) {
    let mut deleted = Vec::new();
    let mut first_error = None;
    let entries = match fs::read_dir(dir) {
        Ok(entries) => entries,
        Err(e) => return (deleted, Some(e)),
    };
    for entry in entries {
        let result = entry.and_then(|entry| {
            let path = entry.path();
            let name = entry.file_name();
            let mine = name.to_str().is_some_and(|n| is_bus_file(n, bus));
            if !mine || open == Some(path.as_path()) || !entry.file_type()?.is_file() {
                return Ok(());
            }
            let written = entry.metadata()?.modified()?;
            if now.duration_since(written).is_ok_and(|age| age > keep) {
                fs::remove_file(&path)?;
                deleted.push(path);
            }
            Ok(())
        });
        if let Err(e) = result {
            first_error.get_or_insert(e);
        }
    }
    (deleted, first_error)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Guards: number - the UTC start in each black-box file's name, which readers and the cross-check against a
    /// session's MCAP sort and match by (logging.md section 8.6).
    #[test]
    fn file_names_carry_the_utc_start() {
        let cases = [
            (0, "19700101T000000Z"),
            (951_782_400, "20000229T000000Z"),
            (1_709_251_199, "20240229T235959Z"),
            (1_793_746_002, "20261103T224642Z"),
            (4_107_542_400, "21000301T000000Z"),
        ];
        for (secs, stamp) in cases {
            assert_eq!(utc_stamp(secs), stamp, "{secs}");
        }
    }

    /// Guards: safety - pruning deletes only this bus's black-box files older than the window, never another bus's,
    /// the open one, or anything else in the directory (logging.md section 8.7).
    #[test]
    fn prune_deletes_only_this_bus_files_past_the_window() {
        let dir = std::env::temp_dir().join(format!("candump-rotate-prune-{}", std::process::id()));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();
        let now = SystemTime::now();
        let day = Duration::from_hours(24);
        let make = |name: &str, age: Duration| {
            let path = dir.join(name);
            let file = File::create(&path).unwrap();
            file.set_modified(now - age).unwrap();
            path
        };
        let old = make("can1-20260101T000000Z.log.zst", 8 * day);
        let old_again = make("can1-20260101T000000Z-1.log.zst", 8 * day);
        let recent = make("can1-20261110T000000Z.log.zst", day);
        let open = make("can1-20260102T000000Z.log.zst", 8 * day);
        let other_bus = make("can10-20260101T000000Z.log.zst", 8 * day);
        let not_ours = make("can1-notes.txt", 8 * day);

        let (mut deleted, error) = prune(&dir, "can1", 7 * day, now, Some(&open));
        deleted.sort();
        assert!(error.is_none(), "{error:?}");
        assert_eq!(deleted, vec![old_again, old]);
        for kept in [recent, open, other_bus, not_ours] {
            assert!(kept.is_file(), "{} was deleted", kept.display());
        }
        fs::remove_dir_all(&dir).unwrap();
    }
}
