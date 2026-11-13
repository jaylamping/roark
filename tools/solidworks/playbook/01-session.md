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
   | `busy` | another session is solving; it does not answer while it solves | go on: `launch()` waits for it. Never treat it as hung |
   | `HALF-CLOSED` | a dead instance that stalls every launch on the machine | stop. Report the PID and the `taskkill /PID <pid> /T /F` line for Joey. Do not launch |

4. **Memory.** `job()` refuses to start under 8 GB free. Do not lower it. Joey's rule for holly-pc (2026-11-11): each job
   stays near 6 GB, three or four ordinary jobs and one or two heavy ones machine-wide.
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
  sections or chunks of 20,000 points, never whole-mesh tests.

## When a script hangs or dies

1. Do not start another instance. Run `sw_instance.py --status`.
2. `busy`: it is working. A 400,000-node contact solve takes 7 to 11 minutes; reading back 2.4 M nodes over COM took over an
   hour. Wait.
3. Read `%TEMP%\sw_hidden_<pid>.log`: a hidden modal dialog blocks the instance, and the log names it.
4. If your own instance is stuck, end it through `end_session(state_file)` or `Instance.close()`, which force-stop your own
   PID and its solver. You may never stop another session's process.
5. If it is `HALF-CLOSED` and not yours, give Joey the `taskkill` line and stop.

## When you finish

Close SolidWorks (leaving the `with` block does it), commit and push what should be kept, then
`python tools/pc/claims.py release <session>`.
