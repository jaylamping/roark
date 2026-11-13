"""Check the packet's results table against the saved reports, case by case (review of the R1g4 packet, 2026-11-13).
1. Every SF triplet "a / b / c" in a table row must appear as "a/b/c" in THAT case's own reports (REPORT_DIR/<prefix>_<case>.*.txt),
   and every other decimal number in the row must appear in them as a whole token.
2. Completeness: every region of that case's spot and region reports whose 0.5 mm SF is below the case's target (1.2 for the stops,
   1.5 otherwise) must be listed in the row (its triplet present), unless the region is in EXCUSED below with a reason.
Case names map to report names by CASES. Exit 1 on any failure.
    python packet_numbers_check.py PACKET.md REPORT_DIR [PREFIX=r1g4]"""
import re
import sys
from pathlib import Path

CASES = {'STOP_0': 'stop0', 'STOP_124': 'stop124', 'YAW -17': 'yawm', 'YAW +17': 'yawp', 'G90': 'g90',
         'G90 + YAW -17': 'g90ym', 'G90 + YAW +17': 'g90y'}
TARGET = {'stop0': 1.2, 'stop124': 1.2}
# regions that repeat another listed region (same nodes, a wider mask), so they need no row of their own
EXCUSED = {
    'arm elsewhere in the hub end': 'the same nodes as the arm end-face corner band (listed)',
    'hub lug -X incl. roots': 'the hub lug roots spot (listed) covers the same root',
    'hub lug +X incl. roots': 'the hub lug roots spot (listed) covers the same root',
    'post -X front (inserts)': 'its plate-hole edge is the PETG ring by the insert (listed)',
    'post +X front (inserts)': 'its plate-hole edge is the PETG ring by the insert (listed)',
    'our post at the boss hole edge': 'the same nodes as the PETG ring by the insert (listed)',
}
packet = Path(sys.argv[1]).read_text(encoding='utf-8')
RD = Path(sys.argv[2])
PREFIX = sys.argv[3] if len(sys.argv) > 3 else 'r1g4'
TRIP = re.compile(r'(\d+\.\d+)\s*/\s*(\d+\.\d+)\s*/\s*(\d+\.\d+)')
sec = packet.split('**Results', 1)[1]
tab = []
for ln in sec.splitlines():
    if ln.startswith('|'):
        tab.append(ln)
    elif tab:
        break
rows = [ln for ln in tab if not ln.startswith('| ---')][1:]
fails = 0
for row in rows:
    case = row.split('|')[1].strip().strip('*')
    key = CASES.get(case)
    if key is None:
        print(f'UNKNOWN CASE {case!r}'); fails += 1; continue
    files = sorted(RD.glob(f'{PREFIX}_{key}.*.txt'))
    if not files:
        print(f'NO REPORTS for {case} ({PREFIX}_{key}.*.txt)'); fails += 1; continue
    corpus = '\n'.join(f.read_text(encoding='utf-8', errors='replace') for f in files)
    flat = re.sub(r'\s*/\s*', '/', corpus)
    rowtrips = set()
    rest = row
    for m in TRIP.finditer(row):
        k = '/'.join(m.groups())
        rowtrips.add(k)
        if k not in flat:
            print(f'NOT FOUND in {key}: triplet {k}'); fails += 1
        rest = rest.replace(m.group(0), ' ')
    for v in re.findall(r'(?<![\d.])(\d+\.\d+)(?![\d.])', rest):
        if not re.search(r'(?<![\d.])' + re.escape(v) + r'(?![\d])', corpus):
            print(f'NOT FOUND in {key}: number {v}'); fails += 1
    # completeness
    tgt = TARGET.get(key, 1.5)
    for f in files:
        if not (f.name.endswith('.spot_report.txt') or f.name.endswith('.region_report.txt')):
            continue
        label = None
        for ln in f.read_text(encoding='utf-8', errors='replace').splitlines():
            if ln.startswith('-- '):
                label = ln[3:].split(':')[0].strip()
                continue
            m = re.search(r'SF \.5/1/2 (\d+\.\d+)/(\d+\.\d+)/(\d+\.\d+)', ln)
            if not m or label is None:
                continue
            if float(m.group(1)) < tgt:
                k = '/'.join(m.groups())
                if k in rowtrips or any(label.startswith(x) for x in EXCUSED):
                    continue
                print(f'MISSING ROW in {case}: {f.name}: {label}: {ln.strip()[:90]}'); fails += 1
print(f'{len(rows)} rows checked, each against its own case reports ({PREFIX}_<case>.*.txt): {fails} failures')
sys.exit(1 if fails else 0)
