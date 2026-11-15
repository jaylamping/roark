# 1. The machine, your worktree, and a job

The rules themselves live in [RULES.md](../RULES.md), [cad-workstation.md](../../../conventions/cad-workstation.md) and
[cad.md](../../../conventions/cad.md). This page is the order to do things in.

## Before the first script

1. **Machine.** CAD runs on holly-pc ([cad.md section 9](../../../conventions/cad.md#9-cad-workstation)). If `J:` is missing,
   run `subst J: C:\joe`. Joey-PC is the fallback only.
2. **Worktree.** Work in your own worktree, never in `J:\code\roark`:

   ```bash
   git -C J:/code/roark fetch origin
   GIT_LFS_SKIP_SMUDGE=1 git -C J:/code/roark worktree add J:/code/roark-wt/<session> -b <branch> origin/main
   ```

3. **Look before you launch.**

   ```bash
   python tools/solidworks/sw_instance.py --status     # every SolidWorks process and whether it answers
   python tools/pc/claims.py list                       # who holds what
   ```

   | `--status` shows | Meaning | Do |
   | --- | --- | --- |
   | nothing, or instances that answer | clear | go on |
   | `busy` | another session is meshing, solving or reading a result back; it does not answer meanwhile | go on: `launch()` starts beside it. Without the keeper the new instance can sit at the splash screen until the oldest instance answers, which `launch()` waits out ([RULES.md](../RULES.md#launching-beside-a-busy-instance)). Never treat the other instance as hung |
   | `HALF-CLOSED` | a dead instance that stalls every launch on the machine | stop. Report the PID and the `taskkill /PID <pid> /T /F` line for Joey. Do not launch |

4. **Memory.** `job()` refuses to start under 8 GB free. Do not lower it. A dip under the floor is other jobs working, not a
   reason to drop the task: `job(wait_s=1800)` waits for memory as it waits for a busy instance. Joey's rule for holly-pc (2026-11-11): each job
   stays near 6 GB, three or four ordinary jobs and one or two heavy ones machine-wide.
   A `STALE` claim of another session is not yours to clear: leave it, and mention it in your report.
5. **Claim** your worktree, and add the PID once you have one:
   `python tools/pc/claims.py claim <session> --worktree J:/code/roark-wt/<session> --status "<what>"`.

## A job

```python
import sys
sys.path.insert(0, r"J:\code\roark-wt\<session>\tools\solidworks")
from swkit import *

with job() as j:            # launches your own instance; closes it on the way out, also after an error
    ...
```

- **One script is one job is one instance.** The instance is closed when the script ends. **Why:** an instance's committed
  memory only grows (one reached 26 GB over about 30 rebuilds), and a fresh one costs four seconds on holly-pc.
- **Run it in the foreground or detached, never under `timeout`.** A bare `timeout` kills the python client in the middle
  of a COM call and leaves SolidWorks half-closed, which stalls every other thread's launches (2026-11-11).
- **Never stop a script while SolidWorks is meshing or solving.** Let it finish. If it truly must end, end the instance
  through its own handle (`j.inst.close()`), not the python process.
- **Two scripts of yours must not share a state file or a folder for one instance.** If you use `session(state_file)` to
  keep an instance across scripts, each job has its own state file, and you call `end_session(state_file)` at the end.
- **Long jobs beat:** `python tools/pc/claims.py beat <session> --status "case 3 of 7"` between cases.
- **Other python work** (post-processing, mesh checks, slicing) runs under the cap:
  `python tools/pc/capped.py --mb 6144 -- python script.py`. Not SolidWorks clients: SolidWorks would land in the same cap.
  **Why:** an uncapped point-in-mesh test reached 61 GB and took holly-pc offline (2026-11-12). Work on meshes in plane
  sections or in chunks, never whole-mesh tests. For "is this point in the solid" use `sheet.inside()`: numpy only,
  20,000 points against 8,000 triangles in five seconds. `trimesh.contains` has no accelerator on this machine and broke
  a 4 GB cap on 5,000 points (2026-11-13).
- **The keeper is not yours.** Where the machine has it switched on (holly-pc does), `--status` shows one idle
  instance marked "keeper". It is the oldest SolidWorks running and takes every new launch's startup call, so a launch
  no longer waits behind another session's mesh or result read-back (22 launches in about 2 s each, 2026-11-13).
  `launch()` starts it when it is missing. Never attach to it, open a document in it or close it. It holds one of
  SolidWorks' two Auto Recover slots, so your instance may start with `no_auto_recover`: save after each step.
- **A dead instance in the way:** `python tools/solidworks/sw_kill.py --list`, then `--dead`. It ends only half-closed
  or abandoned instances and stray solvers, after watching them. Never `--force` on an instance that is not yours.
- **When the clock matters, keep launches few.** With the keeper a launch takes seconds. On a machine without it a
  launch can wait minutes behind another session's solve: `job(wait_s=1800)` keeps asking for that long instead of
  raising `did not answer` (run such a job in the background if your shell tool has its own time limit). Either way,
  put build, checks and studies in one job (at most four studies), and do the thinking, the hand calculations and the
  pictures while it runs.

## When a script hangs or dies

1. Do not start another instance. Run `sw_instance.py --status`.
2. `busy`: it is working. A 400,000-node contact solve takes 7 to 11 minutes; reading back 2.4 M nodes over COM took over an
   hour. Wait.
3. Read `%TEMP%\sw_hidden_<pid>.log`: a hidden modal dialog blocks the instance, and the log names it. No file means
   nothing has been hidden yet, which is normal. A last line
   `#32770 | Simulation` during a solve is the solver asking a question ("Excessive displacements detected"); the
   solver's files beside the model stop changing while it waits. `swfea.static()` answers that one
   ([05-fea.md](05-fea.md), contact rule 8). In your own instance only, you may read such a dialog and press its button.
4. If your own instance is stuck, end it through `end_session(state_file)` or `Instance.close()`, which force-stop your own
   PID and its solver. You may never stop another session's process.
5. If it is `HALF-CLOSED` and not yours, give Joey the `taskkill` line and stop.

## When you finish

Close SolidWorks (leaving the `with` block does it), commit and push what should be kept, then
`python tools/pc/claims.py release <session>`.
