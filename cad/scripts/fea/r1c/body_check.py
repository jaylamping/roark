"""Per-body node counts of a hub-seat result (review 3, item 10; 2026-11-14). The mesh guard checks only the total node count while
the solve runs; this checks, after the body split (post.txt line 1), that every body is there in its own run and big enough:
one arm run, one hub run, one brass run (the two inserts), two steel runs (the bolts), three pad runs (four pads, two of them adjacent in node order); each at least MIN_FRAC
(default 0.85) of the r1g6 base counts below. Exit 1 with BODY CHECK FAILED and the reason.
    python body_check.py POST_TXT [LABEL]"""
import os
import re
import sys

BASE = {'arm': [196062], 'hub': [188232], 'brass': [1784], 'steel': [1949, 1949], 'pad': [386, 193, 193]}      # r1g6_g90y (the first pad run is two pads, 2 x 193)
MIN = float(os.environ.get('MIN_FRAC', '0.85'))
line = open(sys.argv[1]).read().split('\n')[0]
lab = sys.argv[2] if len(sys.argv) > 2 else sys.argv[1]
runs = re.findall(r'(arm|hub|steel|brass|pad|shim) (\d+)-(\d+)', line)
got = {}
for nm, a, b in runs:
    got.setdefault(nm, []).append(int(b) - int(a) + 1)
small = re.search(r'(\d+) of 50 nodes or fewer', line)
bad = []
for nm, ref in BASE.items():
    g = got.get(nm, [])
    if len(g) != len(ref):
        bad.append(f'{nm}: {len(g)} runs, expected {len(ref)}')
        continue
    for k, (n, r) in enumerate(zip(sorted(g), sorted(ref))):
        if n < MIN * r:
            bad.append(f'{nm} run {k}: {n} nodes, under {MIN:.2f} x {r}')
if small and int(small.group(1)):
    bad.append(f'{small.group(1)} runs of 50 nodes or fewer (a split body or a misclassed node)')
summary = ', '.join(f'{nm} {"+".join(str(n) for n in v)}' for nm, v in got.items())
if bad:
    print(f'BODY CHECK FAILED {lab}: ' + '; '.join(bad) + f' (counts: {summary})')
    sys.exit(1)
print(f'BODY CHECK OK {lab}: {summary}')
