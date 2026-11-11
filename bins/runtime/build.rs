//! Embeds the git revision the binary is built from, with `-dirty` when the tree had changes, as `ROARK_GIT_REVISION`
//! (rust.md section 1: every binary knows its build). A revision passed in the environment wins: a copy without `.git`
//! (the dev box's, `scripts/devbox.sh`) is given its revision by whoever made the copy. With neither, `unknown`, and a
//! build warning says so.

use std::io::Write as _;
use std::process::Command;

const VAR: &str = "ROARK_GIT_REVISION";

fn git(args: &[&str]) -> Option<String> {
    let out = Command::new("git").args(args).output().ok()?;
    out.status
        .success()
        .then(|| String::from_utf8_lossy(&out.stdout).trim().to_owned())
}

fn main() -> std::io::Result<()> {
    // Cargo reads its instructions from the build script's stdout.
    let mut out = std::io::stdout().lock();
    writeln!(out, "cargo:rerun-if-env-changed={VAR}")?;
    let revision = if let Some(given) = std::env::var(VAR).ok().filter(|v| !v.is_empty()) {
        given
    } else if let Some(head) = git(&["rev-parse", "HEAD"]) {
        // A failed status counts as dirty: a build that can't prove its tree clean doesn't claim it.
        let dirty = git(&["status", "--porcelain"]).is_none_or(|s| !s.is_empty());
        // Rebuilt when HEAD moves (a commit, a checkout) or the index changes (a stage); an edit to a tracked file
        // rebuilds through the trees below.
        for path in ["HEAD", "index"] {
            if let Some(file) = git(&["rev-parse", "--git-path", path]) {
                writeln!(out, "cargo:rerun-if-changed={file}")?;
            }
        }
        if let Some(common) = git(&["rev-parse", "--git-common-dir"]) {
            writeln!(out, "cargo:rerun-if-changed={common}/refs")?;
            writeln!(out, "cargo:rerun-if-changed={common}/packed-refs")?;
        }
        if dirty { format!("{head}-dirty") } else { head }
    } else {
        writeln!(
            out,
            "cargo:warning=no git checkout and no {VAR}: the binary records its revision as unknown"
        )?;
        "unknown".to_owned()
    };
    writeln!(out, "cargo:rustc-env={VAR}={revision}")?;
    // The dirty flag follows the source: any change in the workspace's code, config, manifests or toolchain.
    for tree in [
        "../../bins",
        "../../crates",
        "../../config",
        "../../Cargo.toml",
        "../../Cargo.lock",
        "../../rust-toolchain.toml",
        "../../.cargo",
    ] {
        writeln!(out, "cargo:rerun-if-changed={tree}")?;
    }
    Ok(())
}
