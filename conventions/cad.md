# CAD in git

**Status:** agreed by Joey, 2026-11-08. Sol 6.1 and Grok 4.6 reviewed this process over five rounds ([marengo PR #281](https://github.com/jaylamping/marengo/pull/281)) and
both agreed. This repo starts its `cad/` tree empty: files come over from marengo only when work needs them.

This page is how CAD files (SolidWorks parts, assemblies and drawings, STEP/STL exports and print files) are versioned. The
runtime never reads them (tenet 2).

## 1. What goes in git

**Git holds the design of record. Joey-PC holds everything that led to it.**

| Versioned (binaries through Git LFS) | Ignored (stays on Joey-PC) |
|---|---|
| The one current file of each part and assembly: the file the robot assembly or a print uses today, in its region folder | Variants, studies, test and render copies: `_wip/<topic>/` |
| The STEP/STL export of a current part that something uses (a print, a review, a URDF, another tool) | FEA and solver output: `_sim/<region>/`, `*.CWR`, `*.STE` |
| The exact 3MF of anything printed, with its G-code and settings checklist | Old copies and raw review logs: `_archive/` |
| Review packets at a gate: markdown and key renders | SolidWorks `.checkpoints/`, `~$` lock files, `Backup of *` copies |
| Vendor models, references, drawings, CAD scripts and macros | Any file at or over the size limit |

The LFS patterns are in [.gitattributes](../.gitattributes) and the ignore rules in [.gitignore](../.gitignore).

**Why:** a clone should give anyone the robot as it is now, while the experiments that led there would fill the LFS quota for
nothing.

## 2. Rules

1. **Work in `_wip/`.** New ideas, variants and experiments start there and are never committed.
2. **Promote when chosen.** A part moves into its region folder when it is picked: it passes its gate, or an assembly or a
   print starts using it. Move and rename native files **inside SolidWorks** (Pack and Go or SOLIDWORKS Explorer), never with
   a plain file move. Rebuild the top assembly once before committing. **Why:** a plain move breaks every assembly that
   references the file, and the break only shows when someone opens it.
3. **Overwrite in place.** Region, export, print and drawing folders hold only the current version; git history is the
   version trail. No `_v2`, `_revC`, `_final`, `(2)` or `Copy of` files there.
4. **Commit at a gate, not on every save.** Commit native files at the end of a design pass or a review gate, and squash
   interim saves before pushing. **Why:** GitHub Free gives 10 GiB of LFS storage and 10 GiB of downloads a month, and every
   pushed version of a file is stored for good, even after it's overwritten.
5. **No file at or over the size limit** ([PLAN.md](../PLAN.md#repo-toolchain-ci-and-deploy)), LFS included.
   `python3 tools/check_file_sizes.py` checks the working tree, `--staged` the next commit and `--range <revs>` the commits
   being pushed; [scripts/check.sh](../scripts/check.sh) and CI run the working-tree check on every PR. Simplify or split a
   file that large, or keep it in `_wip/`. **Why:** GitHub rejects plain files of 100 MiB, and one large LFS file eats the
   quota. CI sees a file only after the push has uploaded it, so CI alone can't save the quota: check before pushing.
6. **Prints:** commit the exact 3MF that was printed, its G-code and the settings checklist, overwriting the previous print of
   that part. **Why:** the G-code is the true record of the print; Bambu Studio has changed saved 3MF settings on open.
7. **Reviews** pin the exact design they reviewed: commit the CAD first, then the packet, whose markdown carries a
   `Pinned commit: <full 40-character SHA>` line and links files by `https://github.com/jaylamping/roark/blob/<sha>/cad/...`.
   A packet holds markdown, key renders (each under about 2 MB) and small data; raw logs, prompts and bulky data stay in
   `_archive/`. **Why:** files are overwritten in place, so only a commit link still shows what was reviewed.

## 3. Folder layout

CAD lives only under `cad/`. Folders are split by body region, with a few function folders beside them. Left and right go in
the file name, not the folder. A region folder is created when its first file is committed.

```
cad/
  robot.SLDASM                root robot assembly
  # body regions: native parts and assemblies, plus .md notes
  torso/  waist/  shoulder/  upper-arm/  elbow/  forearm/  hand/  hip/  leg/  head/  neck/  shell/
  arm/                        whole-arm assemblies only
  fixtures/                   test stands, jigs and rigs (not part of the robot)
  electronics/                board models for fit checks
  # function folders
  vendor/<maker>/             purchased models (actuators, frame hardware, compute, fasteners)
  reference/                  read-only references and datum reports
  exports/<region>/           STEP/STL exported from native CAD
  prints/<region>/            3MF, G-code and settings checklist of each printed part
  reviews/<region>/<YYYYMMDD>_<topic>/   review packets
  drawings/<region>/          SLDDRW and PDF drawings
  scripts/                    CAD automation scripts and macros
  # scratch (gitignored): nothing a kept assembly references
  _wip/<topic>/  _sim/<region>/  _archive/
```

## 4. Names

| What | Pattern | Example |
|---|---|---|
| Part | `<region>_<part>[_left\|_right].SLDPRT` | `shoulder_pitch_bracket_left.SLDPRT` |
| Assembly | `<region>_<what>_asm.SLDASM` | `arm_left_asm.SLDASM` |
| Vendor model | `vendor_<maker>_<model>.<ext>` | `vendor_robstride_rs03.SLDPRT` |

Lower case, words joined by `_`, no robot name (tenet 7). A region whose folder has a hyphen uses `_` in file names:
`upper-arm/upper_arm_link_left.SLDPRT`.

## 5. Layout check and export records

`python3 tools/cad/check_cad_layout.py` checks the folder on disk (scratch included); `--repo` checks what git tracks, from the
index, against the rules in the index, so it works without LFS content and checks a commit by its own rules. [scripts/check.sh](../scripts/check.sh) and CI
run `--repo` and the tests in `tools/cad/`. The rules it reads live in
[cad/manifests/cad-layout.json](../cad/manifests/cad-layout.json) (folders, file types, version-copy pattern, review limits)
and [cad/manifests/cad-conventions.json](../cad/manifests/cad-conventions.json) (names). Add a region there and in section 3
before creating its folder.

It fails on: a loose file at the top of `cad/`, an unknown top-level folder or a folder name not in lower case; a file type
outside its folder's list in `cad-layout.json`; FEA output outside `_sim/`; a version copy (`_v2`, `_revC`, `_final`, `(2)`,
`Copy of`) in a region, export, print or drawing folder; a review file outside `reviews/<region>/<YYYYMMDD>_<topic>/` or over
the review file limit; a missing or malformed `exports.json`; and, in `--repo`, a CAD file outside `cad/`, a CAD file
committed as a plain blob instead of through LFS, two paths that differ only in case, or any tracked file in a scratch folder,
lock file or Explorer file. It warns on names that break section 4 (case, region prefix, robot name), review files and packets
over the warning limits, and packets with no `Pinned commit:` line. The limits are `reviewLimits` in `cad-layout.json`.

**Export records.** Each STEP/STL in `exports/` has an entry in
[cad/manifests/exports.json](../cad/manifests/exports.json): the export, its source part, configuration, export settings, and
the SHA-256 of both (for an LFS file, the `oid` in its pointer). The check warns when the source changed after the export
(stale) or an export has no entry, and fails when an export no longer matches its entry. **Why:** an export that silently
drifts from its part is how a print or a URDF ends up built from the wrong geometry.

## 6. Writer lock, hooks and LFS budget

**Writer lock.** Several sessions share the one checkout on Joey-PC. Before a session opens SolidWorks to change anything in
`cad/`, it takes the lock and names itself in that shell:

```bash
python tools/cad/cad_lock.py acquire <name>      # then: export CAD_WRITER=<name>  (PowerShell: $env:CAD_WRITER = "<name>")
python tools/cad/cad_lock.py release <name>      # after the commit
```

Hold it too while switching branches, resetting or pulling in that checkout. The pre-commit hook refuses a commit that touches
CAD unless `CAD_WRITER` holds the lock. A lock untouched for 4 hours is stale: make sure that session has stopped and closed
its SolidWorks, then `acquire <name> --take-stale`. An unreadable lock, or a leftover `.recover` guard from a crashed takeover,
is cleared by hand. **Why:** two sessions saving into one tree, or one committing while another is mid-save, corrupt
assemblies in ways that only show when someone opens them.

**Hooks.** Install once per clone that commits CAD, and again after `git lfs install`:

```bash
python tools/cad/install_hooks.py
```

pre-commit checks staged sizes and, when CAD is staged, the lock and the `--repo` layout. pre-push checks the pushed sizes and
the LFS budget for all refs of the push together, then runs `git lfs pre-push`, and fails if Git LFS is missing. Another
existing hook is kept as `<hook>.local` and still runs. CI repeats the size and layout checks, so a `--no-verify` commit is
still caught at the PR.

All worktrees of a clone share one hooks folder, so installing from one worktree installs for all of them. A worktree whose
branch has no `tools/cad/hooks/` (one cut before them) prints a warning and skips the CAD checks; its pre-push still runs Git
LFS. **Why:** on Joey-PC an install from a CAD worktree once broke every commit in the power-board worktrees.

**LFS budget.** The pre-push hook fails a push that adds more than 300 MB of new LFS data, takes the month past 1 GB, or takes
storage past 9 GB ([cad/manifests/lfs-budget.json](../cad/manifests/lfs-budget.json)). With Joey's OK for that push, set
`CAD_BUDGET_OK=1`. `python tools/cad/lfs_budget.py report` shows the totals. It counts what local history can see and dates
objects by commit, so it is a lower bound: objects from deleted branches or rewritten history are still billed. Check the
real figure on GitHub (Settings, Billing, Git LFS) at the start of each month.

## 7. Clones and bandwidth

Install [Git LFS](https://git-lfs.com) and run `git lfs install` once per machine before adding anything under `cad/`. Without
it, `git add` stores a CAD file as a plain blob, in history for good.

Every LFS download counts against the 10 GiB a month. CI checks out without LFS content, and every check here reads sizes from
the pointer files. A plain `git clone` on a machine with Git LFS installed downloads all of it, so clone with
`GIT_LFS_SKIP_SMUDGE=1 git clone ...` unless you need the CAD, then fetch only what you need:
`git lfs pull --include "cad/shoulder/**"`.

## 8. Backup

`_wip/`, `_sim/` and `_archive/` exist only on Joey-PC. Git is not their backup: they are covered by Joey-PC's own backup, or
the design is promoted before it would hurt to lose it.
