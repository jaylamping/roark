"""Run a command inside a Windows job object with a hard per-process memory limit (children are added as they appear: the
venv launcher starts the real interpreter as a child); log the peak private bytes. memcap.py LIMIT_GB cmd args..."""
import sys, subprocess, time, psutil
import win32job, win32api, win32con
lim = int(float(sys.argv[1]) * 1024 ** 3)
job = win32job.CreateJobObject(None, '')
info = win32job.QueryInformationJobObject(job, win32job.JobObjectExtendedLimitInformation)
info['ProcessMemoryLimit'] = lim
info['BasicLimitInformation']['LimitFlags'] = win32job.JOB_OBJECT_LIMIT_PROCESS_MEMORY | win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
win32job.SetInformationJobObject(job, win32job.JobObjectExtendedLimitInformation, info)
p = subprocess.Popen(sys.argv[2:])
done, peak = set(), 0
while p.poll() is None:
    try:
        procs = [psutil.Process(p.pid)] + psutil.Process(p.pid).children(recursive=True)
    except Exception:
        procs = []
    for q in procs:
        if q.pid not in done:
            try:
                win32job.AssignProcessToJobObject(job, win32api.OpenProcess(win32con.PROCESS_ALL_ACCESS, False, q.pid)); done.add(q.pid)
            except Exception:
                pass
        try:
            peak = max(peak, q.memory_info().private)
        except Exception:
            pass
    time.sleep(0.5)
print(f'MEMCAP exit {p.returncode} peak_private_GB {peak / 1024 ** 3:.2f} limit_GB {lim / 1024 ** 3:.1f}', flush=True)
