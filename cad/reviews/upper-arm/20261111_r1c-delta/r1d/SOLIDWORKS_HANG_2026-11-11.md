# SolidWorks hangs on holly-pc, 2026-11-11 evening (upper-arm thread's record)

Times are local (CST, UTC−6).

## How the upper-arm thread launches SolidWorks

- **Launcher:** `tools/solidworks/sw_instance.py`, via `cad/scripts/arm/swlib.py`.
  - `app()` calls `session(ARM_SW_DIR/.sw_instance_pid)`. That reuses the instance named in the PID file, or calls
    `launch(visible=False)`: hidden, timeout 300 s, under a launch lock.
  - The PID file is only written once the new process has registered in the Running Object Table (ROT).
  - `finish()` calls `end_session()`, which calls `attach(pid).close()`.
- **One instance per folder:** `cad/_wip/arm-sw*` (arm-sw, arm-sw-fea, -fea2, -fea3, -fea4, -hub, -probe).
- **Solves:** `cad/scripts/fea/organic_fea.py <case>` → `p3_fea.run()`. That opens the hub-seat part, creates a static study
  with contact sets, meshes, runs `RunAnalysis`, then reads the results back over COM (`GetStress` on every node). For a
  2.4 M-node model that readback takes over an hour.
- **Chains:** `cad/scripts/fea/r1c/r1d_chain*.sh`, started detached with PowerShell `Start-Process bash ... -WindowStyle Hidden`.

## PID 2536 (hung; ended by Joey with taskkill /F about 22:00)

- **Launched** 21:12:33 into `cad/_wip/arm-sw-fea` by `r1d_chain2.sh`: the retry of `HS_STOP_0_fine` on the R1d 0.1 mm-gap
  model. The first try had failed with solver error 24, an unrestrained rigid-body mode.
- **Window title:** "SOLIDWORKS Design Premium 2026 SP0.0 - [UA_HUBSEAT_r1d_nom *]", i.e. a hub-seat part open and
  modified (the study had been created).
- **About 21:16:** I stopped its client Python (`organic_fea.py`) and the chain's bash with `Stop-Process` while it was
  meshing or solving. Two `end_session` closes after that (about 21:20 and 21:28) timed out after 240-300 s. From then its
  CPU time stayed at about 218 s: hung, no visible dialog. The shell is not allowed to force-stop a SolidWorks process.

## Failed-launch pattern from 21:26

Each new launch shows a visible window titled "splash", sits at 14-38 MB with about 0 CPU, never registers in the ROT within
the 300 s timeout, then usually exits:

| PID | Start | By |
| --- | --- | --- |
| 23412 | 21:26:24 | soft-spring chain, try 1 |
| 30876 | about 21:32 | try 2 |
| 18516 | 21:41:27 | splash; exited about 21:47 |
| 2492 | about 21:50 | bare test launch (`open_test.py`) |
| 28820 | 21:56:44 | launch probe |
| 29964 | 22:00:2x | soft-spring chain after 2536 was killed, try 1 |
| 27964 | 22:06:24 | try 2; still on splash at 22:07 |

## What else was running

- **PID 20948** (mine, started 18:21, `arm-sw-fea2`). In a long COM readback (`GetStress`, 2.4 M nodes) since about 20:32,
  CPU climbing slowly.
  - **Launches still worked** while it was busy: 20:47, 20:49, 21:12 and 21:25 (PID 29808, closed cleanly later).
- **PIDs 14328 (24 GB) and 22520:** the shoulder thread's, closed about 21:27.
- **Helpers:** `sldworks_fs` (12:00), `sldBgDwld`, `lmgrd` ×2, two `swCefSubProc` (20:21), `sldProcMon` (22:06, alongside
  the new launch).

## Observations

- The failures start right after I killed client processes in the middle of a run (about 21:16-21:20) and 2536 hung. They
  continued after 2536 was ended. The only long-lived instance left then was 20948, still inside a COM call.
- Earlier today a launch also failed once to register under heavy CPU load (12:21). That one recovered on the next try.
- Free RAM stayed 15-24 GB throughout, and CPU load was about 21%.

## Suggestions for the "Stop SolidWorks hanging" thread

- Never kill a solve's client Python while SolidWorks is meshing or solving. Let it finish or time out, then `end_session`.
- Give `end_session` a hard-kill fallback for this machine's own instances: PID plus start time are recorded, so it is
  provably ours.
- Cap readback size: read results only for a region of interest, or export with the Simulation results tools rather than
  `GetStress` on every node over COM.
- Make a launch that never registers kill its own splash process before retrying.
