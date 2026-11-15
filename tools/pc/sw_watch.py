"""What went wrong in SolidWorks work on this PC since the last look? conventions/cad-workstation.md.

    python tools/pc/sw_watch.py ROOT [ROOT ...] [--hours N] [--peek] [--json]

Reads every runs.log under the ROOT folders (swkit.job() writes one line per job: start, seconds, script, pid, "ok" or
the error) and the Windows Application log for SLDWORKS.exe crashes and hangs, and prints what is NEW since the last
look: failures whose kind has not been seen on this PC before, kinds seen before with how often they came back, and
crashes. Exit 0 when nothing is new, 1 when something is.

The first look covers the last N hours (default 24). After it, each look starts where the last one ended; that time
and the kinds already seen are kept in sw_watch_state.json in the claims folder. --peek looks without moving them.

A "kind" is the error text with its numbers, paths and names taken out, so that the same fault in two parts or at two
node counts counts once. A job killed from outside leaves no line, and a hang leaves none until something ends it:
this reads what was written, it does not watch a running job. Stdlib only.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

SKIP = {".git", "node_modules", "target", "__pycache__", ".venv"}


def kind(outcome: str) -> str:
    """The error with what changes from run to run taken out: paths, quoted names, hex and decimal numbers."""
    s = re.sub(r"[A-Za-z]:[\\/][^\s'\",;)]*", "<path>", outcome)
    s = re.sub(r"'[^']*'|\"[^\"]*\"", "<name>", s)
    s = re.sub(r"0x[0-9a-fA-F]+|-?\d+(\.\d+)?([eE][-+]?\d+)?", "<n>", s)
    return " ".join(s.split())[:160]


def parse(text: str, folder: str) -> list[dict]:
    """The jobs in one runs.log. Lines that are not a job line are passed over."""
    rows = []
    for line in text.splitlines():
        part = line.split("\t")
        if len(part) < 5:
            continue
        try:
            start = time.mktime(time.strptime(part[0][:19], "%Y-%m-%d %H:%M:%S"))
        except ValueError:
            continue
        outcome = part[4].strip()
        rows.append({"start": start, "when": part[0][:19], "script": part[2], "folder": folder, "ok": outcome == "ok",
                     "outcome": outcome})
    return rows


def sort(rows: list[dict], since: float, seen: set[str]) -> dict:
    """Jobs since `since`, failures grouped by kind and split into kinds not in `seen` (new) and kinds that are."""
    recent = [r for r in rows if r["start"] >= since]
    groups: dict[str, dict] = {}
    for r in recent:
        if r["ok"]:
            continue
        g = groups.setdefault(kind(r["outcome"]), {"count": 0, "example": r["outcome"], "scripts": [], "folders": [],
                                                   "last": r["when"]})
        g["count"] += 1
        g["last"] = max(g["last"], r["when"])
        for key, value in (("scripts", r["script"]), ("folders", r["folder"])):
            if value not in g[key] and len(g[key]) < 5:
                g[key].append(value)
    return {"jobs": len(recent), "failed": sum(not r["ok"] for r in recent),
            "new": {k: g for k, g in groups.items() if k not in seen},
            "again": {k: g for k, g in groups.items() if k in seen}}


def run_logs(roots: list[str]) -> list[dict]:
    rows = []
    for root in roots:
        for here, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in SKIP]
            if "runs.log" in files:
                try:
                    rows += parse((Path(here) / "runs.log").read_text(encoding="utf-8", errors="replace"), here)
                except OSError:
                    pass
    return rows


def crashes(since: float) -> list[dict] | None:
    """SLDWORKS.exe crashes (event 1000) and hangs (1002) in the Application log since `since`. None if it can't tell."""
    start = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(since))
    ps = ("$e = Get-WinEvent -FilterHashtable @{LogName='Application'; Id=1000,1002; StartTime=[datetime]'" + start + "'} "
          "-ErrorAction SilentlyContinue | Where-Object { $_.Message -match 'SLDWORKS' } | ForEach-Object { "
          "[pscustomobject]@{when=$_.TimeCreated.ToString('yyyy-MM-dd HH:mm:ss'); id=$_.Id; "
          "text=(($_.Message -split \"`n\")[0..3] -join ' ')} }; ConvertTo-Json @($e) -Compress")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=120, check=False)
        return json.loads(out.stdout or "[]") if out.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None


def state_file() -> Path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import claims
    return claims.claims_dir() / "sw_watch_state.json"


def main(argv: list[str]) -> int:
    roots = [a for a in argv if not a.startswith("--")]
    if not roots or "--hours" in argv and argv.index("--hours") + 1 >= len(argv):
        raise SystemExit(__doc__)
    hours = 24.0
    if "--hours" in argv:
        hours = float(argv[argv.index("--hours") + 1])
        roots.remove(argv[argv.index("--hours") + 1])
    path = state_file()
    state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    now = time.time()
    since = state.get("until", now - hours * 3600) if "--hours" not in argv else now - hours * 3600
    res = sort(run_logs(roots), since, set(state.get("seen", [])))
    res["crashes"] = crashes(since) if os.name == "nt" else None
    res["since"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(since))
    if "--peek" not in argv:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"until": now, "seen": sorted(set(state.get("seen", [])) | set(res["new"]))}, indent=1),
                        encoding="utf-8")
    if "--json" in argv:
        print(json.dumps(res, indent=1))
    else:
        print(f'since {res["since"]}: {res["jobs"]} jobs, {res["failed"]} failed, {len(res["new"])} new kinds, '
              f'{"?" if res["crashes"] is None else len(res["crashes"])} SolidWorks crashes or hangs')
        for label in ("new", "again"):
            for g in res[label].values():
                print(f'{label.upper():5} x{g["count"]} last {g["last"]}  {g["example"][:200]}\n      scripts: '
                      f'{"; ".join(g["scripts"])}\n      in: {"; ".join(g["folders"])}')
        for c in res["crashes"] or []:
            print(f'CRASH {c["when"]} event {c["id"]}  {c["text"][:200]}')
    return 1 if res["new"] or res["crashes"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
