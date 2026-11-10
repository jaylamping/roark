# Sharing Joey-PC between threads

**Status:** proposed, 2026-11-09. Sections 1 and 2 apply now; section 3 is the next build; section 4 is a one-time setup
for Joey.

Several threads share one Windows PC, one SolidWorks install, one Bambu Studio and one git clone. Most of the time lost in
the week of 2026-11-05 came from those shared pieces, not from design work:

- a Remote Control session dropped overnight (2026-11-08, about 10:44Z) and the work sat idle until someone noticed;
- SolidWorks hung after large FEA runs and had to be restarted, losing its in-memory state;
- new SolidWorks windows stole focus while Joey was gaming, even with the hidden-instance rule;
- one thread installed the CAD git hooks from its worktree, and since every worktree of a clone shares `.git/hooks`, commits
  broke in the power-board worktrees;
- approvals Joey gave in a thread couldn't reach the PC, whose permission guard only trusts what is typed there.

The rules below cut the shared state down to what can't be split, and make the rest visible. They are written so a future
job runner can take them over without changing the files they use.

## 1. One worktree and up to two SolidWorks instances per thread

- **Worktree:** each thread works in its own worktree of the roark clone, never in `J:\code\roark` itself (that one stays on
  `main` for Joey):

  ```bash
  git -C J:/code/roark fetch origin
  git -C J:/code/roark worktree add J:/code/roark-wt/<session> -b <branch> origin/main
  ```

  `<session>` is a short name for the thread (`left-arm`, `power-board`), lower case with `-`. A thread that doesn't need
  the CAD content sets `GIT_LFS_SKIP_SMUDGE=1` for the `worktree add` and pulls only what it needs later
  ([cad.md section 7](cad.md#7-clones-and-bandwidth)); worktrees share the clone's LFS store, so content is downloaded once.
- **SolidWorks:** up to two long-lived instances per thread through `tools/solidworks/sw_instance.py`
  ([RULES.md](../tools/solidworks/RULES.md)): one for modelling and, while a long study runs, one for FEA, so a 25-minute
  sweep doesn't block modelling (Joey, 2026-11-09, until the FEA queue in section 3 exists). Claim the FEA instance as its own
  session, `<session>-fea` (section 2), so both PIDs are on record. Never attach to another thread's instance and never close
  one you didn't start. Each launch steals focus and takes about 1.5 GB, so start the second one only for a long study and
  close it when the study ends.
- **CAD writer lock:** [cad.md section 6](cad.md#6-writer-lock-hooks-and-lfs-budget) still applies inside a worktree that more
  than one session uses. With one worktree per thread it is uncontested, but take it anyway. The CAD hooks check it where
  they are installed; after setup step 5 (section 4) the shared clone has none, so there nothing checks it until they are
  installed from the main checkout.
- **Hooks:** never run a hook installer from a worktree (`install_hooks.py` refuses in one); the hooks are shared by every
  worktree of the clone. The hooks skip the CAD checks in a worktree without `tools/cad/hooks/` ([cad.md section 6](cad.md#6-writer-lock-hooks-and-lfs-budget)).

## 2. Claims and heartbeats

Each session records what it holds and keeps it fresh with
[tools/pc/claims.py](../tools/pc/claims.py), one small file per session in `C:\Temp\roark-claims\`:

```bash
python tools/pc/claims.py claim left-arm --worktree J:/code/roark-wt/left-arm --sw-pid 12345 --status "upper arm FEA"
python tools/pc/claims.py beat left-arm --status "case 3 of 7"     # every few minutes during long work
python tools/pc/claims.py list                                       # everyone, with STALE after 15 min of silence
python tools/pc/claims.py who 12345                                  # whose SolidWorks is this?
python tools/pc/claims.py release left-arm                           # when done, after closing your SolidWorks
```

- `claim` and `beat` refuse a worktree or SolidWorks PID that another live session holds, so a session that went quiet and
  comes back doesn't take back what someone claimed meanwhile. The one exception is a thread's FEA instance:
  `<session>-fea` may share `<session>`'s worktree, never its PID. A claim silent for 15 minutes no longer blocks anyone,
  but **don't close its SolidWorks**: that still needs its owner or Joey (section 4).
- A claim file that can't be read blocks every `claim` and `beat` (it may be a live session's) until it is checked and
  deleted by hand, which needs Joey (section 4).
- **Long jobs beat.** A script that runs longer than a few minutes calls `beat` between steps (each FEA case, each export).
- **The owning thread checks back.** Before it starts a long job, the cloud thread schedules a check for after the job's
  expected end. If the job's claim is STALE when it checks, the thread resumes from the last saved step (scripts save after
  each step, RULES.md rule 5) instead of waiting for Joey to notice.

## 3. The FEA queue (next)

Large studies go through one runner instead of each thread driving SolidWorks through a long solve:

- A thread drops a job file in `C:\Temp\roark-fea\queue\<session>-<YYYYMMDDTHHMM>.json`: its worktree, the study script to
  run there, its arguments, a timeout, and where to write results (under the worktree's `cad/_sim/<region>/`).
- One runner (`tools/pc/fea_runner.py`, session name `fea-runner`) owns one SolidWorks instance and runs the jobs one at a
  time, oldest first. It beats between jobs and during each solve. On timeout or a hang it closes its own instance, starts a
  new one and marks the job failed with its log; the next job starts on a clean instance.
- Results and the log go to `C:\Temp\roark-fea\done\<job>.json`; the thread's check-back (section 2) picks them up.
- Two small studies may still run in a thread's own instance; RULES.md rule 6 (at most two concurrent solves) holds.

To build first on the upper-arm contact FEA, which is the next large study.

## 4. What threads may run, and what needs Joey

**Routine (allowed in the PC's Claude Code settings, no prompt):** read-only git; `git add`, `git commit`, `git push` to a
branch other than `main`; `git fetch`, `git pull`, `git switch`, `git worktree add`; `git lfs pull`, `fetch`, `ls-files`
and `status`; `git config --worktree`; the CAD tools in `tools/cad/` except `cad_lock.py acquire`; `tools/pc/claims.py`.
These are reversible and every change still lands by PR. Each allow line is the narrowest prefix that covers what threads
run, because a rule matches anything that starts with it: `git lfs:*` would also allow `git lfs install` (shared hooks)
and `git lfs prune` (the shared LFS store). `cad_lock.py acquire` asks every time, since the same command with
`--take-stale` takes over another session's lock; the prompt shows which it is.

**Needs Joey at the keyboard (or his OK in the thread, then he runs it):**

- deleting files outside the thread's own worktree (including `git worktree remove` of another thread's worktree and
  `git clean` anywhere);
- anything that writes to `main` directly;
- installing software or Python packages;
- changing shared git config or hooks (`git config` without `--worktree`, `install_hooks.py`, `git lfs install`, anything
  in `.git/hooks`);
- closing or killing another session's SolidWorks, or taking over a stale CAD lock (`--take-stale`);
- a push over the LFS budget (`CAD_BUDGET_OK=1`);
- system settings, drivers, scheduled tasks.

A thread asks for these by name and says why. It doesn't ask for anything on the routine list.

### One-time setup (about 5 minutes, at the PC)

1. Open the Claude Code settings file the PC sessions use: `%USERPROFILE%\.claude\settings.json` (the file that already
   allows `git push --force-with-lease`).
2. Merge these into its `permissions` block (keep what is already there):

   ```json
   "allow": [
     "Bash(git status:*)", "Bash(git diff:*)", "Bash(git log:*)", "Bash(git show:*)", "Bash(git branch:*)",
     "Bash(git fetch:*)", "Bash(git pull:*)", "Bash(git switch:*)", "Bash(git add:*)", "Bash(git commit:*)",
     "Bash(git push:*)", "Bash(git worktree add:*)", "Bash(git worktree list:*)",
     "Bash(git lfs pull:*)", "Bash(git lfs fetch:*)", "Bash(git lfs ls-files:*)", "Bash(git lfs status:*)",
     "Bash(git config --worktree:*)",
     "Bash(python tools/cad/gate.py:*)", "Bash(python tools/cad/check_cad_layout.py:*)",
     "Bash(python tools/cad/check_sw_refs.py:*)", "Bash(python tools/cad/record_export.py:*)",
     "Bash(python tools/cad/cad_lock.py status:*)", "Bash(python tools/cad/cad_lock.py check:*)",
     "Bash(python tools/cad/cad_lock.py refresh:*)", "Bash(python tools/cad/cad_lock.py release:*)",
     "Bash(python tools/cad/lfs_budget.py:*)",
     "Bash(python tools/check_file_sizes.py:*)", "Bash(python tools/pc/claims.py:*)"
   ],
   "deny": [
     "Bash(git push origin main:*)", "Bash(git push origin HEAD:main:*)", "Bash(git push origin +main:*)",
     "Bash(git push -f:*)", "Bash(git push -u origin main:*)", "Bash(git push origin --delete:*)",
     "Bash(git push --force-with-lease origin main:*)", "Bash(git push --force-with-lease origin HEAD:main:*)"
   ]
   ```

   Deny rules win over allow rules. There is no deny line for `--force`: as a prefix it would also block the
   `--force-with-lease` the settings already allow. The deny lines catch only the spellings listed; a push to `main` with
   other flags before the refspec still matches `git push:*`. **GitHub's protection on `main` is the only real guard**;
   these lines just stop the common attempts early. If the prompts that keep appearing name the PowerShell tool instead of
   Bash, add the same lines with `PowerShell(` in place of `Bash(`.
3. Install the gate's mesh libraries once: `python -m pip install numpy scipy trimesh rtree networkx`.
4. Turn on per-worktree git config: `git -C J:/code/roark config extensions.worktreeConfig true`. Without it,
   `git config --worktree` refuses in a clone with several worktrees, and in a clone with one it writes the shared
   `.git/config`.
5. If not done yet, put back Git LFS's stock hooks in place of the CAD hooks the arm thread's install wrote: in
   `J:\code\roark\.git\hooks`, delete `pre-commit` and rename `pre-push.lfs-orig` (Git LFS's own hook, kept by
   `install_hooks.py`) back to `pre-push`. After this the shared clone runs no CAD hooks, so the writer lock is not
   hook-checked there until the CAD hooks are installed from the main checkout
   ([cad.md section 6](cad.md#6-writer-lock-hooks-and-lfs-budget)).
6. Restart the "Joey-PC (code)" Remote Control server so it reloads the settings.

After a week, count the approvals that still got stuck and trim the lists.
