# SolidWorks instance rules

Windows only; needs `pywin32` and `psutil` (`pip install pywin32 psutil`). Used by `tools/cad/check_sw_refs.py`.

This page is the rules for sharing SolidWorks. How to model, export and run studies from a script, with the helpers that
check each step, is the [playbook](playbook/README.md).

Every session runs its own SolidWorks instance, so sessions do not take turns. Joey made this the standard on 2026-11-06.

```python
import sys
sys.path.insert(0, r"J:\code\roark\tools\solidworks")
from sw_instance import launch

with launch() as inst:          # new SLDWORKS.exe, hidden, attached by PID
    sw = inst.sw                # ordinary SldWorks COM object
    cw = inst.load_simulation() # only if the session needs FEA
    ...
# leaving the block closes this instance's documents and exits only this PID
```

`inst.pid` is the session's PID. If `inst.no_auto_recover` is True, that instance has no Auto Recover.

To reuse one instance across separate script runs, use `session(state_file)` with a state file the session owns, and call `end_session(state_file)` when finished. The file holds the PID and the process start time, because Windows reuses PIDs: a file whose process is gone, or whose PID now belongs to another process, is never attached to or closed. `visible` only applies when `session()` launches a new instance.

## Hidden by default

On Joey-PC, Joey uses the PC while sessions work, so SolidWorks must never pop up or take focus there. CAD work now runs on holly-pc ([cad.md, section 9](../../conventions/cad.md#9-cad-workstation)), where nobody is at the desk and a visible window is fine. `launch()` and `session()` now start hidden. Pass `visible=True` only when someone needs to see the window.

A hidden launch does three things:

- Starts SLDWORKS.exe with its window hidden.
- Starts a small separate process that hides every window of that PID and its child processes the moment it shows, using window events, until they all exit. If one takes focus, it hands focus back. It keeps working during a blocking solve, when COM can't be called.
- Sets `Visible` and `UserControl` to False.

Setting `sw.Visible = False` alone is not enough. It read back True and the window stayed up.

Anything hidden is logged to `sw_hidden_<pid>.log` in the temp folder, and `HAD FOCUS` marks a window that took focus. **A hidden modal dialog blocks the instance, so if a script hangs, read that log first.**

**What was popping up on 2026-11-07:** a watcher logged every window for a real run. Two things showed.

- `sldexitapp.exe`, started by SolidWorks on exit, opened a visible **SOLIDWORKS Error Report** that stayed on screen and took focus. It is a separate process, `sldexitapp.exe /SWPID=<pid>`, so hiding the SolidWorks PID didn't cover it, and it appears on a crash as well as on exit. `close()` now also stops that child. The hider covers child processes and any `sldexitapp.exe` naming its PID, and stays up for 60 s after the instance has gone.
- Each launch can briefly take focus for the splash, main window, welcome screen and CAM window, during the first 20 s or so. A window hidden on show has no time to paint, and the hider hands focus back, but **Windows gives no way to refuse focus from another process, so a fullscreen game can still lose focus for a moment at launch.** Launch before starting a game, or keep launches few.

No console windows showed, from Python, PowerShell, git or Bambu Studio.

**What was still flashing on 2026-11-09:** a watcher logged every window, its ancestry and how long it stayed visible, over five launches.

- The Simulation solver, `Simulation\star.exe`, shows a progress dialog titled with the study name. It runs below a helper (`SLDWORKS.exe` → `cwanalysisproc.exe` → `star.exe`) and lives only for the solve, so the 2 s child sweep missed it: it stayed on screen and took focus. The hider now treats any process with our instance among its ancestors as ours. It also covers a `star.exe` from the Simulation folder whose parent chain is broken, if it started after our instance and has no other SolidWorks among its ancestors, so another session's solver is never touched. After the fix the solver dialog was hidden before it painted.
- Launch windows (splash, main window, welcome screen, the journal prompt) were hidden in 0 to 50 ms on a quiet PC, but the main window was once visible for 0.3 to 0.9 s. Window events reach the hider through its message loop, so slow work there delays the hide. Processes already judged foreign are now cached, so a busy desktop costs one lookup per process, not one per window event.
- **Every launch still takes focus about 7 times in its first 20 s.** Threads must reuse one instance with `session()` and `end_session()`, never launch per script.

## Sound

Measured on 2026-11-09 with the Core Audio peak meters of every session (`python tools/solidworks/sw_audio.py` lists them):

- SolidWorks never opened an audio session of its own in five launches. Its tones play through the shared **System Sounds** session, which carries every app's sounds, so it cannot be muted for our instance alone.
- A tone played each time the hidden **"A journal file could not be created"** prompt (`#32770`, "SOLIDWORKS Design") showed. That prompt comes up whenever this instance is the third SolidWorks running. `launch()` dismisses it, but the message box has already beeped. Fewer instances, through `session()` reuse, is the fix. A second, quieter tone sometimes followed a few seconds later without any SolidWorks window to match it.
- A rebuild error made through the API (a shell thicker than the part, What's Wrong count 1) played no tone.
- The hider still mutes any audio session owned by our instance or its children, in case a sound such as collision detection ever plays through one. Windows saves an app's mute by exe path, so `close()` raises `sw_unmute_<pid>.flag` and unmutes before exit. That way Joey's own SolidWorks never starts muted. If an instance crashes while muted and Joey's SolidWorks goes quiet, unmute SolidWorks in the Windows volume mixer.
- SolidWorks' own sound options live in the registry and are shared with Joey's SolidWorks. Do not change them.

**A launch can wait at the splash screen while the oldest running instance is busy.** `launch()` handles it and no hold needs agreeing between threads: see [Launching beside a busy instance](#launching-beside-a-busy-instance).

**A launch takes focus about 6 times in its first 20 s, and nothing tried stops it.** So reuse one instance across scripts with `session()` and don't restart between runs. Each measured on one launch, Joey-PC, 2026-11-07:

| Launch | Focus events | Note |
| --- | --- | --- |
| Hidden (`SW_HIDE`), event hider | 6 to 7 | Splash, main window, welcome screen, untitled dialog, CAM window |
| `SW_SHOWMINNOACTIVE` | 6 | No better |
| CAM add-in off for the launch, welcome screen setting off | 6 | Removes the CAM window only. SolidWorks writes the add-in value back at exit, so a toggle would change Joey's settings unless restored after every exit. Not used |
| `LockSetForegroundWindow` | 7 | Call fails, our process isn't allowed to set the foreground |
| `/b` switch | | Never registers in the ROT, so it can't be attached |
| Separate Windows desktop | | Not in the ROT after 2.5 minutes, so it can't be attached |

Turning off SOLIDWORKS CAM at startup in Tools, Add-Ins would remove that one window for good, but that is Joey's own setting.

Use `end_session(state_file)` to close an instance. Calling `session(state_file).close()` when the instance is already gone starts a new one just to close it.

If something won't run hidden, use `inst.minimize()`, which never takes focus. `inst.hide()` hides on demand. From another process, or for a stuck instance of your own, call `hide_windows(pid)`.

For Bambu Studio, use the CLI (`--slice`), which opens no window.

solidworks-mcp servers start their instance through their own code, so they don't get this until that build is changed.

## Hung, half-closed and orphaned instances

`python tools/solidworks/sw_instance.py --status` lists every SolidWorks process with its age, threads, windows, committed memory, whether it answers, and what it is doing. It only looks. Run it before reporting a hang.

| State | What is seen | Healthy | A launch |
| --- | --- | --- | --- |
| idle | Answers | Yes | Goes ahead |
| solving | Not answering, `cwanalysisproc.exe` or `star.exe` runs under it | Yes | Goes ahead |
| busy | Not answering, no solver, but a live client process is driving it (mesh, rebuild, reading a result back) | Yes | Goes ahead |
| orphan | Not answering, still has its windows, no solver and no live client: its client was killed mid-call | Maybe | Waits 300 s for it, then refuses and names the PID |
| HALF-CLOSED | Not answering and no windows left | No | Refuses at once and names the PID |

Under each row `--status` names who drives the instance: its claim ([cad-workstation.md section 2](../../conventions/cad-workstation.md#2-claims-and-heartbeats)),
or, when the session made none, the worktree and command line that `launch()` or `attach()` noted for it.

The live client is the process named in `sw_owner_<pid>.txt` in the temp folder, which `launch()` and `attach()` write, or failing that the process that started the instance.

## Launching beside a busy instance

Sessions do not take turns to launch. `launch()` starts a new instance beside any number of solving or busy ones.

What SolidWorks does, traced on holly-pc on 2026-11-13 with Wait Chain Traversal on a process held at the splash screen: **at startup a new SolidWorks makes one COM call into an instance that is already running, and stays at the splash screen until that instance answers.** Five traces caught the call. In four, one other instance was running and the call went to it. In the fifth, two were running and the call went to the older. Three more starts were made while a newer instance was solving and not answering, with an older one idle: all three were ready in their usual 3 to 8 s. So the call appears to go to the oldest running instance, and a newer busy one does not hold a launch up.

- While the oldest instance meshes, rebuilds or reads a result back, it does not answer at all, and the new process waits for the whole of it. One wait was still going at 150 s.
- While the oldest instance solves, it answers now and then. A new process got through 14 s into an 18 s solve of 476k nodes.
- The `/r`, `-Embedding` and `/Automation` switches make the same call and wait the same way.

So `launch()` starts the process anyway and does not count time spent beside a solving or busy instance against its `timeout`, up to `busy_wait` (two hours). The launch lock is held meanwhile, so other launches queue behind it, which is where they would be waiting in any case. The launch comes up the moment the old instance answers. It still raises at once if an instance turns out half-closed.

Before 2026-11-13 `launch()` waited for every instance that was not answering and refused after 300 s. That made threads take turns behind solves of 30 to 50 minutes, most of the time for an instance the new process would never have called.

Two things follow for a thread that wants its launches never to wait:

- Keep one instance through a run of jobs with `session()`, and recycle it on committed memory, not per job.
- An instance that stays idle and is the oldest one running would take the startup call for everyone. That is not set up, and "oldest" rests on the few starts above, not on documentation.

What went wrong on holly-pc on 2026-11-11, and what the module now does about each step:

- A job ran as `timeout 7200 python job.py`. At two hours `timeout` killed the Python client in the middle of a COM call that was returning a 2.4 M-node result. **Do not wrap a SolidWorks job in a bare `timeout`.** If a job needs a time limit, the limit must be followed by `end_session(state_file)`, which now always ends the instance.
- The cleanup then called `ExitApp` on that instance. It half-closed: no windows, one thread spinning a core, 3.6 GB still committed, still in the ROT. A COM call has no timeout, so the cleanup never returned and never reached its force-stop. `close()` now checks that the instance answers before any COM call, puts a deadline on each call, and force-stops the instance and everything it started when either fails.
- The state file still named the half-closed instance, so the next run attached to it and hung for its whole time limit. `attach()` and `session()` now raise `NotAnswering` within 30 s without touching it, and `end_session()` force-stops an instance that does not answer and always removes the state file.
- **A launch stalls at the splash screen while any other instance is not answering**, so one half-closed instance stopped every thread's launches. Seven launches sat at the splash for five minutes each. `launch()` raises at once, naming the PID, when one is half-closed, and goes ahead beside a solving or busy one ([Launching beside a busy instance](#launching-beside-a-busy-instance)).
- An instance that was 28 minutes into a real solve was taken for hung and killed. That left `cwanalysisproc.exe` and `star.exe` running on several cores and 4 GB with nothing to read the result. **An instance does not answer while it solves: that is not a hang.** `--status` shows `solving` or `busy` for it and `HALF-CLOSED` for the real thing. `close()` and `end_session()` now stop the solver with the instance.
- Committed memory grows with use: one instance reached 26 GB over about 30 rebuilds, with a working set of only 1.7 GB. Check `inst.private_mb()`, not `rss_mb()`, and start a fresh instance for each job or when it passes a few GB.
- A hidden modal dialog holds the client, not other sessions: the instance still answers, so `--status` shows it idle while its script hangs. On 2026-11-13 `load_simulation()` sat for 35 minutes behind a hidden "Yes, continue to load SOLIDWORKS Simulation / No, disable SOLIDWORKS Simulation" prompt, which came up after test instances had been stopped during startup. `sw_hidden_<pid>.log` showed it.

Threads still cannot stop another session's process. For a half-closed instance whose owner is gone, give Joey the line `--status` points at: `taskkill /PID <pid> /T /F`. `/T` matters, it takes the solver too.

## Rules

1. Each session starts its own instance with `launch()` and uses that handle. Keep it hidden.
2. Never use `GetActiveObject`, `Dispatch("SldWorks.Application")` or anything else that reaches "the running SolidWorks". It can land in another session's instance.
3. Never call `ExitApp`, close documents in, or kill a PID the session did not start.
4. One file belongs to one session. Other sessions open a copy, read-only. Agree ownership before writing.
5. Save after each step. A third instance has no Auto Recover, and an instance can crash.
6. Concurrent Simulation solves are allowed, up to the two tested so far, and the limit is per machine (What was tested, below). Joey-PC ran a pair of 476k nodes each. On holly-pc a pair of about 390k nodes each crashed, so there solves that size run one at a time; smaller pairs ran together. Keep large solves to one at a time on any machine until a pair that size is tested there. A solve expected to need more than about 6 GB takes the workstation's large-solve lock first: `with big_solve("thread name"): study.RunAnalysis`. The lock is the file `C:\joe\.fea_solve.lock` (owner, PID, process start time, time taken), created exclusively and removed afterwards. `big_solve` waits while another session holds it and takes over a lock only when its process has gone. A lock written by hand in another layout is respected as long as any number in it is a running PID. Smaller solves do not take it. `swfea.static()` takes the same lock by itself for a solve over 200,000 nodes (`heavy_solve_lock`).
7. Exit the instance when the work is done. Each one holds about 1 GB idle and about 1.6 GB after a solve.
8. solidworks-mcp follows these rules from branch `feat/owned-instance`: each MCP server launches and owns one instance, attached by PID. **A server started before that build still attaches to the running SolidWorks until it restarts**, so do not use its tools alongside other sessions. Running servers are not restarted for you.

## What was tested

Joey-PC, SolidWorks 2026 SP0, 2026-11-06, with another session's instance open throughout and untouched.

| Check | Result |
| --- | --- |
| New instance attached by PID, `GetProcessID` matches | Pass, 13 to 17 s to attach |
| Part, sketch, extrude, save, close | Pass |
| Simulation add-in in a second instance | Pass, no license prompt |
| Mesh and solve, Ø40 × 100 mm cylinder, 12,220 nodes | Pass, 0.7 s and 1.0 s |
| Two instances solving at once, 476,266 nodes each, started within 0.1 s | Pass, 19.1 and 19.4 s against 15.4 to 15.8 s alone, same peak displacement |
| Exit own instance, other instance still responding | Pass |
| RAM | About 950 MB idle, 1.3 GB with Simulation, 1.6 GB after the solve |

holly-pc, SolidWorks 2026 SP0, 2026-11-11, one instance, hidden:

| Check | Result |
| --- | --- |
| Launch to ready | Pass, 3.0 to 4.5 s |
| Part, sketch, extrude, save | Pass |
| Simulation add-in | Pass, 4 s, no license prompt |
| Mesh and solve, Ø40 × 100 mm cylinder, 100 N axial, 48,724 nodes | Pass, 0.5 s mesh and 1.9 s solve; peak displacement 2.24 µm against 2.27 µm by hand |
| RAM | About 740 MB |
| Two instances solving at once, upper-arm halves, about 390k nodes each (2026-11-11, upper-arm R1 FEA) | **Fail:** crashed reading back the results. Run solves that size one at a time |

`CreateMesh` takes element sizes in mm. A new install has no default part template until SolidWorks has been opened once
by hand, so pass a template path to `NewDocument` until then.

Hidden mode, Joey-PC, 2026-11-07:

| Check | Result |
| --- | --- |
| Launch to ready | Pass. Splash and welcome screen hidden within 0.1 s of appearing. No window took focus |
| Open, modify, save and STL export | Pass |
| Simulation add-in, mesh and solve, 307,835 nodes | Pass, 29 to 35 s. No new windows and no focus change during the run |
| Exit | Pass, hider process stops by itself |

Two startup problems came up. `launch()` handles both:

- Two SolidWorks processes starting at the same moment can stall, so launches queue on a lock file.
- A third process stops at a modal prompt, "A journal file could not be created. Auto recover will not work". `launch()` clicks OK on exactly that prompt, in its own PID only, even when it is hidden, and sets `no_auto_recover`.

Four instances ran at once in the solidworks-mcp test, each in its own PID, with no modeling load on all four.

`ExitApp` can leave a half-closed process with no documents and no Simulation license, so `close()` force-stops its own PID, and what that PID started, if it has not gone after 60 seconds.
