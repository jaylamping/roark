"""Count a run from its own logs: jobs launched, jobs that failed before one worked, minutes. Stdlib only.

    python tools/pc/run_metrics.py eval/<run>            # a table per script and the totals
    python tools/pc/run_metrics.py eval/<run> --json

Reads <folder>/runs.log (one line per swkit.job(): start, seconds, script and arguments, pid, "ok" or the error) and
<folder>/times.log (swkit.stamp()). Per script: jobs, how many failed, whether the first job passed, and the seconds
SolidWorks was open. Totals: the same summed, the share of scripts whose first job passed, and the minutes between
the first and last stamp. These are the benchmark's process numbers: retries per task, first-try pass rate, time.
A script that was run under two names counts as two; a job killed from outside leaves no line at all.
"""
import json
import sys
from pathlib import Path


def read(folder):
    folder = Path(folder)
    rows = []
    runs = folder / 'runs.log'
    for line in (runs.read_text(encoding='utf-8').splitlines() if runs.exists() else []):
        part = line.split('\t')
        if len(part) < 5:
            continue
        rows.append(dict(start=part[0], seconds=float(part[1].split()[0]), script=part[2].split()[0] if part[2] else '-',
                         ok=part[4].strip() == 'ok', outcome=part[4].strip()))
    scripts = {}
    for r in rows:
        s = scripts.setdefault(r['script'], dict(jobs=0, failed=0, first_passed=r['ok'], passed=False, seconds=0.0,
                                                 last_error=None))
        s['jobs'] += 1
        s['failed'] += 0 if r['ok'] else 1
        s['passed'] = s['passed'] or r['ok']
        s['seconds'] += r['seconds']
        if not r['ok']:
            s['last_error'] = r['outcome'][:160]
    minutes = None
    times = folder / 'times.log'
    if times.exists():
        stamps = [float(ln.split('\t')[0]) for ln in times.read_text(encoding='utf-8').splitlines() if ln.strip()]
        if len(stamps) > 1:
            minutes = round((stamps[-1] - stamps[0]) / 60, 1)
    n = len(scripts)
    total = dict(scripts=n, jobs=len(rows), failed=sum(not r['ok'] for r in rows),
                 first_try_pass_share=round(sum(s['first_passed'] for s in scripts.values()) / n, 2) if n else None,
                 never_passed=sorted(k for k, s in scripts.items() if not s['passed']),
                 solidworks_minutes=round(sum(r['seconds'] for r in rows) / 60, 1), clock_minutes=minutes)
    return dict(folder=str(folder), scripts=scripts, total=total)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    res = read(sys.argv[1])
    if '--json' in sys.argv:
        print(json.dumps(res, indent=1))
    else:
        print(f'{"script":32} jobs failed first-try passed seconds')
        for name, s in res['scripts'].items():
            print(f'{name[:32]:32} {s["jobs"]:4} {s["failed"]:6} {"yes" if s["first_passed"] else "no":>9} '
                  f'{"yes" if s["passed"] else "NO":>6} {s["seconds"]:7.0f}')
        t = res['total']
        print(f'total: {t["jobs"]} jobs, {t["failed"]} failed, first job passed for {t["first_try_pass_share"]} of '
              f'{t["scripts"]} scripts, SolidWorks open {t["solidworks_minutes"]} min, clock {t["clock_minutes"]} min'
              + (f', never passed: {t["never_passed"]}' if t['never_passed'] else ''))
