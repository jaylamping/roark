//! A session's directory: `session.json`, the MCAP file and its lock.

use std::fmt::Write as _;
use std::fs::{File, OpenOptions};
use std::io::{self, BufWriter, Seek, Write};
use std::path::{Path, PathBuf};

use schemars::JsonSchema;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

use crate::RecordError;
use crate::file::McapFile;

/// What a session was started with: `session.json` and every file's header.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
pub struct SessionInfo {
    /// The git revision the binary was built from.
    pub git_revision: String,
    /// Who started it.
    pub operator: String,
    /// What it ran against.
    pub stage: Stage,
    /// The skeleton file it loaded.
    pub skeleton: SkeletonRef,
    /// The buses recorded, in order: a [`BusRecorder`](crate::BusRecorder)'s index is its place here.
    pub buses: Vec<BusInfo>,
}

/// What a session ran against.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum Stage {
    /// Simulated drives on `vcan`.
    Vcan,
    /// Real drives on the bench.
    Bench,
}

/// The skeleton file by path and content hash.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
pub struct SkeletonRef {
    /// The path it was loaded from.
    pub path: String,
    /// SHA-256 of its bytes, lowercase hex.
    pub sha256: String,
}

impl SkeletonRef {
    /// Hash the file at `path`.
    ///
    /// # Errors
    /// The file can't be read.
    pub fn read(path: &Path) -> io::Result<Self> {
        let digest = Sha256::digest(std::fs::read(path)?);
        Ok(Self {
            path: path.display().to_string(),
            sha256: digest.iter().fold(String::with_capacity(64), |mut hex, b| {
                let _ = write!(hex, "{b:02x}");
                hex
            }),
        })
    }
}

/// One recorded bus and how it was observed, so a reader can tell traffic that never happened from traffic the socket
/// filtered out (logging.md section 8.5).
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
pub struct BusInfo {
    /// The interface name, as the skeleton names it.
    pub name: String,
    /// Nominal bitrate, bits per second.
    pub bitrate: u32,
    /// Where frame timestamps come from.
    pub timestamps: TimestampSource,
    /// The socket's receive filters; empty means every frame.
    pub receive_filters: Vec<CanFilter>,
    /// The socket's error-frame mask (`CAN_RAW_ERR_FILTER`); 0 records no error frames.
    pub error_filter: u32,
    /// The adapter's firmware version; none on `vcan`.
    pub adapter_firmware: Option<String>,
}

/// Where a bus's frame timestamps come from.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum TimestampSource {
    /// The adapter stamps frames (`gs_usb`).
    Hardware,
    /// The kernel stamps frames on receipt (`vcan`, the MCP2515 HAT).
    Software,
}

/// One SocketCAN receive filter: a frame passes when `frame_id & mask == id & mask`.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
pub struct CanFilter {
    /// The ID to match.
    pub id: u32,
    /// The bits that must match.
    pub mask: u32,
}

/// Where an MCAP file goes: a file that can also be made durable.
pub trait Sink: Write + Seek + Send {
    /// Flush and `fsync`, so a clean close means the bytes are on the disk.
    ///
    /// # Errors
    /// The flush or the sync failed.
    fn sync(&mut self) -> io::Result<()>;
}

impl Sink for BufWriter<File> {
    fn sync(&mut self) -> io::Result<()> {
        self.flush()?;
        self.get_ref().sync_all()
    }
}

/// `session.json`.
#[derive(Serialize)]
struct SessionJson<'a> {
    session: &'a str,
    #[serde(flatten)]
    info: &'a SessionInfo,
}

/// An open session: its directory, its MCAP file, and the file's lock.
pub struct Session<W: Sink = BufWriter<File>> {
    dir: PathBuf,
    lock: PathBuf,
    pub(crate) file: McapFile<W>,
}

impl Session {
    /// Start a session under `root` at wall-clock time `wall_ns`: make `<root>/<UTC start>/`, write `session.json`, and
    /// open `0000.mcap` with its lock and header.
    ///
    /// # Errors
    /// The directory exists already (two sessions in one second) or can't be made, or a file can't be written.
    pub fn start(root: &Path, info: SessionInfo, wall_ns: u64) -> Result<Self, RecordError> {
        Self::start_with(root, info, wall_ns, |path| {
            let file = OpenOptions::new().write(true).create_new(true).open(path)?;
            Ok(BufWriter::with_capacity(1 << 20, file))
        })
    }
}

impl<W: Sink> Session<W> {
    /// [`Session::start`], with `open` making the MCAP file's sink from its path.
    ///
    /// # Errors
    /// As [`Session::start`].
    pub fn start_with(
        root: &Path,
        info: SessionInfo,
        wall_ns: u64,
        open: impl FnOnce(&Path) -> io::Result<W>,
    ) -> Result<Self, RecordError> {
        let id = utc_seconds(wall_ns);
        let dir = root.join(&id);
        std::fs::create_dir_all(root)?;
        std::fs::create_dir(&dir)?;
        let json = serde_json::to_vec_pretty(&SessionJson {
            session: &id,
            info: &info,
        })?;
        std::fs::write(dir.join("session.json"), json)?;
        let path = dir.join("0000.mcap");
        let lock = dir.join("0000.mcap.lock");
        File::create(&lock)?;
        let file = McapFile::new(open(&path)?, id, 0, info, wall_ns)?;
        Ok(Self { dir, lock, file })
    }

    /// The session's directory.
    #[must_use]
    pub fn dir(&self) -> &Path {
        &self.dir
    }

    pub(crate) fn info(&self) -> &SessionInfo {
        self.file.info()
    }

    /// Finish the file and make it durable, then remove the lock. On any error the lock stays.
    pub(crate) fn close(self, wall_ns: u64) -> Result<crate::wire::End, RecordError> {
        let (mut sink, end) = self.file.finish(wall_ns)?;
        sink.sync()?;
        std::fs::remove_file(&self.lock)?;
        Ok(end)
    }
}

/// `wall_ns` as an RFC 3339 UTC time to the second: `2026-11-08T12:34:56Z`, the session ID (PLAN "Observability").
fn utc_seconds(wall_ns: u64) -> String {
    let secs = wall_ns / 1_000_000_000;
    let (days, rem) = (secs / 86_400, secs % 86_400);
    let (year, month, day) = civil_from_days(days);
    format!(
        "{year:04}-{month:02}-{day:02}T{:02}:{:02}:{:02}Z",
        rem / 3600,
        rem % 3600 / 60,
        rem % 60
    )
}

/// Days since 1970-01-01 to a proleptic Gregorian date (Howard Hinnant's `civil_from_days`, for days >= 0).
fn civil_from_days(days: u64) -> (u64, u64, u64) {
    let z = days + 719_468;
    let era = z / 146_097;
    let doe = z % 146_097;
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let day = doy - (153 * mp + 2) / 5 + 1;
    let month = if mp < 10 { mp + 3 } else { mp - 9 };
    let year = yoe + era * 400 + u64::from(month <= 2);
    (year, month, day)
}

#[cfg(test)]
mod tests {
    use super::utc_seconds;

    /// Guards: protocol - the session ID is its UTC start to the second (PLAN "Observability").
    #[test]
    fn session_ids_are_utc_to_the_second() {
        assert_eq!(utc_seconds(0), "1970-01-01T00:00:00Z");
        assert_eq!(utc_seconds(951_782_400_000_000_000), "2000-02-29T00:00:00Z");
        assert_eq!(
            utc_seconds(1_794_141_296_999_999_999),
            "2026-11-08T12:34:56Z"
        );
        assert_eq!(
            utc_seconds(4_102_444_799_000_000_000),
            "2099-12-31T23:59:59Z"
        );
    }
}
