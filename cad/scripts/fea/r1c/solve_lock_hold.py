"""Hold the workstation's large-solve lock (C:\\joe\\.fea_solve.lock) for a shell job, in main's own layout (2026-11-14).

    python solve_lock_hold.py OWNER STATUS_FILE RELEASE_FILE PARENT_WINPID [LOG]

The lock is the one tools/solidworks/sw_instance.big_solve uses (RULES.md rule 6): the file is created exclusively, with the
lines owner, pid, process start time and time taken, and it is removed by its holder only. This process is the holder: a real
Windows process that lives for the whole job, so its pid and start time prove it alive to every other thread's check.

Unlike big_solve, it never removes a lock it did not write (coordinator, 2026-11-14). If the file looks stale by big_solve's own
rule (sw_instance._solve_lock_holder), it waits anyway and reports that once to LOG, for a person to decide.

It writes HELD to STATUS_FILE once it holds the lock, and lets go when RELEASE_FILE appears or the shell job PARENT_WINPID ends.
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'tools', 'solidworks'))
import sw_instance as S  # noqa: E402

owner, status, release, parent = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
log = sys.argv[5] if len(sys.argv) > 5 else None
born_parent = S._started(parent)
LOCK = os.environ.get('SOLVE_LOCK_TEST_PATH', S.SOLVE_LOCK)      # tests only


def say(msg):
    if log:
        with open(log, 'a') as f:
            f.write(f'{msg} {time.strftime("%H:%M")}\n')


def parent_alive():
    return born_parent is not None and S._started(parent) == born_parent


mine = f"{owner}\n{os.getpid()}\n{S._started(os.getpid())!r}\n{time.strftime('%Y-%m-%dT%H:%M:%S%z')}\n"
reported = False
while True:
    if not parent_alive():
        sys.exit(0)
    try:
        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        if not reported and S._solve_lock_holder(LOCK) is None:
            try:
                text = open(LOCK).read().strip().replace('\n', ' | ')
            except OSError:
                text = '(unreadable)'
            say(f'SOLVE LOCK LOOKS STALE, not removed, waiting (report to the coordinator): {LOCK}: {text}')
            reported = True
        time.sleep(15)
        continue
    with os.fdopen(fd, 'w') as f:
        f.write(mine)
    break
with open(status, 'w') as f:
    f.write('HELD\n')
try:
    while parent_alive() and not os.path.exists(release):
        time.sleep(2)
finally:
    try:
        if open(LOCK).read() == mine:
            os.remove(LOCK)
    except OSError:
        pass
    try:
        os.remove(status)
    except OSError:
        pass
