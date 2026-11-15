"""Tests for the SolidWorks failure watch (pytest; run by scripts/check.sh). Rules: conventions/cad-workstation.md."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sw_watch


def test_the_same_fault_in_two_parts_is_one_kind_and_a_known_kind_is_not_reported_as_new() -> None:
    """Guards: the daily look must tell Joey about a fault once. The FFEPlus contact failure (2026-11-13) came back in
    every bolted study with a different file and node count in its text; reported as new each time it would bury a
    fault that really is new, such as the STEP import that never returned (2026-11-15)."""
    log = "\n".join([
        "2026-11-15 03:00:00 -0600\t95 s\tfea_hub.py a\tpid 4100\tFailed: solve of 'HUB_E1' ended with code 24 at 746211 nodes",
        "2026-11-15 03:10:00 -0600\t80 s\tfea_arm.py\tpid 4200\tFailed: solve of 'ARM_R1' ended with code 24 at 144396 nodes",
        "2026-11-15 03:20:00 -0600\t12 s\tselftest.py\tpid 4300\tok",
        "2026-11-15 03:30:00 -0600\t180 s\timport.py\tpid 4400\tFailed: import of C:\\joe\\x\\plate.step did not return",
        "2026-11-14 03:30:00 -0600\t9 s\told.py\tpid 1\tFailed: something older than the look",
        "not a job line",
    ])
    rows = sw_watch.parse(log, "C:\\joe\\wt")
    since = time.mktime(time.strptime("2026-11-15 00:00:00", "%Y-%m-%d %H:%M:%S"))
    solve = sw_watch.kind("Failed: solve of 'X' ended with code 24 at 5 nodes")

    first = sw_watch.sort(rows, since, set())
    assert (first["jobs"], first["failed"]) == (4, 3)
    assert len(first["new"]) == 2 and first["new"][solve]["count"] == 2
    assert first["new"][solve]["scripts"] == ["fea_hub.py a", "fea_arm.py"]

    later = sw_watch.sort(rows, since, {solve})
    assert list(later["again"]) == [solve] and len(later["new"]) == 1
    assert "did not return" in next(iter(later["new"].values()))["example"]
