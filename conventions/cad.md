# CAD in git

**Status:** agreed by Joey, 2026-11-08. Sol 6.1 and Grok 4.6 reviewed this process over five rounds ([marengo PR #281](https://github.com/jaylamping/marengo/pull/281)) and
both agreed. This repo starts its `cad/` tree empty: files come over from marengo only when work needs them.

This page is how CAD files (SolidWorks parts, assemblies and drawings, STEP/STL exports and print files) are versioned. The
runtime never reads them (tenet 2).

## 1. What goes in git

**Git holds the design of record. The CAD workstation holds everything that led to it.**

| Versioned (binaries through Git LFS) | Ignored (stays on the CAD workstation) |
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
   a plain file move. Rebuild and save the top assembly, stage everything, then run
   `python tools/cad/check_sw_refs.py --all` on Windows and commit with nothing saved in between: every reference of every
   tracked part, assembly and drawing must resolve to a committed or staged file in `cad/`, outside the scratch folders, and
   it refuses if a scanned file's working copy differs from its staged copy. **Why:** a plain move breaks every assembly that
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
the SHA-256 of both (for an LFS file, the `oid` in its pointer). Record one right after exporting:
`python tools/cad/record_export.py exports/<region>/<file> <region>/<part>.SLDPRT --config <name> --settings "<STEP AP214, ...>"`. The check warns when the source changed after the export
(stale) or an export has no entry, and fails when an export no longer matches its entry. **Why:** an export that silently
drifts from its part is how a print or a URDF ends up built from the wrong geometry.

## 6. Writer lock, hooks and LFS budget

**Writer lock.** Several sessions share the one checkout on the CAD workstation. Before a session opens SolidWorks to change anything in
`cad/`, it takes the lock and names itself in that shell:

```bash
python3 tools/cad/cad_lock.py acquire <name>   # prints the CAD_WRITER value to export in this shell (<name>:<token>)
python3 tools/cad/cad_lock.py refresh          # during long work, at least every few hours
python3 tools/cad/cad_lock.py release          # after the commit
```

PowerShell: `$env:CAD_WRITER = "<name>:<token>"`. The token is new on every acquire, so two sessions that pick the same name
never share the lock. Hold it too while switching branches, resetting or pulling in that checkout. The pre-commit hook refuses
a commit that touches CAD unless `CAD_WRITER` holds the lock, and refreshes it. A lock not refreshed for 4 hours is stale, even
if SolidWorks is still open: make sure that session has stopped and closed its SolidWorks, then
`acquire <name> --take-stale`. Every change to the lock runs under a short mutex file, `.cad-writer.lock.mutex`; an unreadable
lock, or a mutex left by a crash, is cleared by hand. **Why:** two sessions saving into one tree, or one committing while another is mid-save, corrupt
assemblies in ways that only show when someone opens them.

**Hooks.** Install once per clone that commits CAD, and again after `git lfs install`:

```bash
python3 tools/cad/install_hooks.py
```

pre-commit checks staged sizes and, when CAD is staged, the lock and the `--repo` layout. pre-push checks the pushed sizes and
the LFS budget for all refs of the push together, runs any `pre-push.local`, and only then runs `git lfs pre-push`, so nothing
is uploaded for a refused push; it fails if Git LFS is missing. Git LFS's stock pre-push hook is replaced; any other existing
hook is kept as `<hook>.local` and still runs. CI repeats the size and layout checks, so a `--no-verify` commit is
still caught at the PR.

All worktrees of a clone share one hooks folder, so `install_hooks.py` runs only from the main checkout and refuses in a
linked worktree. A worktree whose
branch has no `tools/cad/hooks/` (one cut before them) prints a warning and skips the CAD checks; its pre-push still runs Git
LFS. **Why:** on Joey-PC an install from a CAD worktree once broke every commit in the power-board worktrees.

**LFS budget.** The pre-push hook fails a push over the per-push or storage limit in
[cad/manifests/lfs-budget.json](../cad/manifests/lfs-budget.json): 300 MB in one push, and 8 GB stored in total, with a
warning from 6 GB. There is no monthly limit. **Why:** GitHub Free's 10 GiB of LFS storage is a running total of every
version ever pushed, not an allowance that refills each month, so the total is the figure to cap. With Joey's OK for
that one push, run `CAD_BUDGET_OK=1 git push ...` (never export it). `python3 tools/cad/lfs_budget.py report` shows the
total and what each month added.

**How it is counted.** The hook reads the LFS pointer files in git history, so it needs no LFS content. "Stored" is every
distinct LFS object reachable from the remote's branches as this clone last fetched them; a new version of a file is a new
object, and the old one still counts. The push adds the objects in its commits that the remote does not hold yet. This is
a lower bound: objects from deleted branches or rewritten history are still stored by GitHub, and with stale
remote-tracking refs it can count an object the remote already has as new. Fetch before a big push. Check the real figure
on GitHub (Settings, Billing, Git LFS) at the start of each month.

## 7. Clones and bandwidth

Install [Git LFS](https://git-lfs.com) and run `git lfs install` once per machine before adding anything under `cad/`. Without
it, `git add` stores a CAD file as a plain blob, in history for good.

Downloads have their own limit: 10 GiB a month, and every LFS download counts against it, including each clone and each
pull of new CAD on every machine (holly-pc, Joey-PC, the Mac, cloud sessions). The storage cap above does not cover this. CI checks out without LFS content, and every check here reads sizes from
the pointer files. A plain `git clone` on a machine with Git LFS installed downloads all of it, so clone with
`GIT_LFS_SKIP_SMUDGE=1 git clone ...` unless you need the CAD, then fetch only what you need:
`git lfs pull --include "cad/shoulder/**"`.

## 8. Backup

`_wip/`, `_sim/` and `_archive/` exist only on the CAD workstation. Git is not their backup, and holly-pc has no backup of
its own yet: promote a design before it would hurt to lose it. Joey-PC keeps the copies made when CAD moved to holly-pc.

## 9. CAD workstation

All SolidWorks, Simulation and KiCad work runs on **holly-pc**, a PC kept for it, from 2026-11-11. Joey-PC is Joey's own
PC: it keeps the older copies as a backup and is the fallback CAD machine. There SolidWorks runs hidden only, never
visible, because Joey may be using it.

- The shared checkout is `C:\joe\code\roark`. `subst J: C:\joe` maps it to `J:\code\roark`, the same path it had on
  Joey-PC, so scripts and SolidWorks references keep working. If `J:` is missing after a restart, run that line first.
- Files are worked on from holly-pc's own disk, never over the network share from Joey-PC. **Why:** a dropped
  connection mid-save can corrupt a SolidWorks file, and FEA output would load Joey-PC's disk and network.
- Nobody uses holly-pc while sessions run, so SolidWorks may run visibly there; hidden stays the default
  ([RULES.md](../tools/solidworks/RULES.md)).

### SolidWorks and Bambu Studio settings on holly-pc

holly-pc's SolidWorks is a fresh install. Its defaults differ from Joey-PC's in ways the scripts relied on without saying so
(found while rebuilding the upper arm R1, 2026-11-11). Set these in the script that exports, not by hand, and log them:

| Setting | Joey-PC (as the v26 exports show) | holly-pc default | What to do |
| --- | --- | --- | --- |
| Default part template | set, **IPS** units | **none** | Pass a template (`SW_PART_TEMPLATE`, e.g. `C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2026\templates\MBD\part 0051mm to 0250mm.prtdot`) and set the document to MMGS (`SetUserPreferenceInteger(263, 0, 5)`). STEP exports then come out in mm instead of inches; the geometry is the same. |
| STL: do not translate to positive space (toggle 71) | on | **off**: STLs shift by the part's negative extents | Turn it on. Anything that reads an exported STL in the CAD frame breaks otherwise. |
| STL binary (69), units (211 = mm), quality (78) | binary, mm, Fine | same | Set them anyway. Fine reproduced the v26 face counts. |
| STEP AP (75) | AP203 | AP203 | Set it anyway. |
| Simulation solver, mesher, Jacobian points | defaults | defaults | `p3_fea.py` logs them. The smoke test re-solved two Joey-PC cases within 2 %, with nearly the same node counts. |

`cad/scripts/arm/organic_master.py` does all of this at startup; copy that block into other export scripts.

Bambu Studio **2.09.01.70**, the version the upper-arm slices used, is installed at `C:\Program Files\Bambu Studio`. Its GUI had
not been run, so `%APPDATA%\BambuStudio\system\BBL` didn't exist. Fall back to the presets the install ships in
`resources\profiles\BBL`. Re-slicing the reviewed ring that way reproduced the stored slice exactly (3465 s, 19.04 g).

## 10. Requirements, gate and print log

Each printed part also has a requirements spec in its region folder, a pre-print gate report and a print log in
`prints/<region>/`: [part-lifecycle.md](part-lifecycle.md). Sharing the CAD workstation between threads (worktrees, claims,
the FEA queue): [cad-workstation.md](cad-workstation.md).
