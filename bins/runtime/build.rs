//! Embeds the git revision the binary is built from, with `-dirty` when the tree has changes, as `ROARK_GIT_REVISION`
//! (rust.md section 1: every binary knows its build). `unknown` outside a git checkout.

use std::io::Write as _;
use std::process::Command;

fn git(args: &[&str]) -> Option<String> {
    let out = Command::new("git").args(args).output().ok()?;
    out.status
        .success()
        .then(|| String::from_utf8_lossy(&out.stdout).trim().to_owned())
}

fn main() -> std::io::Result<()> {
    let revision = match git(&["rev-parse", "HEAD"]) {
        Some(head) => {
            // A failed status counts as dirty: a build that can't prove its tree clean doesn't claim it.
            let dirty = git(&["status", "--porcelain"]).is_none_or(|s| !s.is_empty());
            if dirty { format!("{head}-dirty") } else { head }
        }
        None => "unknown".to_owned(),
    };
    // Cargo reads its instructions from the build script's stdout.
    let mut out = std::io::stdout().lock();
    writeln!(out, "cargo:rustc-env=ROARK_GIT_REVISION={revision}")?;
    // A new commit, a change staged, or any source file edited changes the revision or the dirty flag.
    if let Some(dir) = git(&["rev-parse", "--absolute-git-dir"]) {
        writeln!(out, "cargo:rerun-if-changed={dir}/HEAD")?;
        writeln!(out, "cargo:rerun-if-changed={dir}/index")?;
        writeln!(out, "cargo:rerun-if-changed={dir}/refs")?;
    }
    for tree in [
        "../../bins",
        "../../crates",
        "../../config",
        "../../Cargo.lock",
    ] {
        writeln!(out, "cargo:rerun-if-changed={tree}")?;
    }
    Ok(())
}
