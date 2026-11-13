"""Run a command under a hard memory cap (Windows job object), so a runaway job fails instead of filling holly-pc.

    python tools/pc/capped.py [--mb 6144] -- python script.py args...

Every python job on the CAD workstation that is not a SolidWorks client (post-processing, geometry checks, sweeps, slicing)
runs under about 6 GB (2026-11-12, after a 61 GB geometry check took holly-pc to 3 GB free). A SolidWorks client is left
out: the SolidWorks it launches would land in the same job, under the same cap, and be killed when the client exits.

The child starts suspended, is put in a job object with a per-process and a per-job committed-memory limit, then resumed.
Over the limit its allocations fail (Python raises MemoryError and exits), and the job is closed with KILL_ON_JOB_CLOSE, so
nothing it started outlives it. The exit code is the child's; 'CAPPED: ...' is printed to stderr if the limit was hit.
"""
import os
import sys

import msvcrt
import win32api
import win32con
import win32event
import win32job
import win32process

args = sys.argv[1:]
mb = 6144
if args[:1] == ['--mb']:
    mb = int(args[1])
    args = args[2:]
if args[:1] == ['--']:
    args = args[1:]
if not args:
    raise SystemExit(__doc__)

job = win32job.CreateJobObject(None, '')
info = win32job.QueryInformationJobObject(job, win32job.JobObjectExtendedLimitInformation)
info['ProcessMemoryLimit'] = mb * 1024 * 1024
info['JobMemoryLimit'] = mb * 1024 * 1024
info['BasicLimitInformation']['LimitFlags'] |= (win32job.JOB_OBJECT_LIMIT_PROCESS_MEMORY | win32job.JOB_OBJECT_LIMIT_JOB_MEMORY
                                               | win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE)
win32job.SetInformationJobObject(job, win32job.JobObjectExtendedLimitInformation, info)

si = win32process.STARTUPINFO()
si.dwFlags = win32con.STARTF_USESTDHANDLES
handles = []
for fd in (0, 1, 2):
    try:
        h = msvcrt.get_osfhandle(fd)
        os.set_handle_inheritable(h, True)
    except OSError:
        h = None
    handles.append(h)
si.hStdInput, si.hStdOutput, si.hStdError = handles
cmd = win32process.list2cmdline(args) if hasattr(win32process, 'list2cmdline') else __import__('subprocess').list2cmdline(args)
hp, ht, pid, tid = win32process.CreateProcess(None, cmd, None, None, True, win32process.CREATE_SUSPENDED, None, os.getcwd(), si)
win32job.AssignProcessToJobObject(job, hp)
win32process.ResumeThread(ht)
win32event.WaitForSingleObject(hp, win32event.INFINITE)
code = win32process.GetExitCodeProcess(hp)
acct = win32job.QueryInformationJobObject(job, win32job.JobObjectExtendedLimitInformation)
peak = max(acct.get('PeakProcessMemoryUsed', 0), acct.get('PeakJobMemoryUsed', 0)) / 2 ** 20
if peak >= mb * 0.98:
    print(f'CAPPED: {args[0]} reached the {mb} MB limit (peak {peak:.0f} MB); exit code {code}', file=sys.stderr)
win32api.CloseHandle(ht)
win32api.CloseHandle(hp)
job.Close()
sys.exit(code)
