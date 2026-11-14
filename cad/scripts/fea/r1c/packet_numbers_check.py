"""Check the packet's results table against the saved reports, case by case (review of the R1g4 packet, 2026-11-13; review 3 of r1g6,
2026-11-14).
1. Every SF triplet "a / b / c" in a table row must appear as "a/b/c" in THAT case's own reports (REPORT_DIR/<prefix>_<case>.*.txt),
   and every other decimal number in the row must appear in them as a whole token.
2. Each triplet is tied to its label (review 3): the report line holding it must be of the component named just before it in the
   row (vm / layer / shear), and its region label must share a word with the row's phrase for it (the text since the last ';' or
   cell start; the column header only when that phrase names no region), with the synonyms in SYN.
3. Completeness: every region of that case's spot, region AND post_allc (whole-part) reports with ANY of its 0.5 / 1 / 2 mm SFs
   below the case's target (1.2 for the stops, 1.5 otherwise) must be listed in the row (its triplet present), unless the region
   is in EXCUSED below with a reason.
Case names map to report names by CASES. Exit 1 on any failure.
    python packet_numbers_check.py PACKET.md REPORT_DIR [PREFIX=r1g4]"""
import re
import sys
from pathlib import Path

CASES = {'STOP_0': 'stop0', 'STOP_124': 'stop124', 'YAW -17': 'yawm', 'YAW +17': 'yawp', 'G90': 'g90',
         'G90 + YAW -17': 'g90ym', 'G90 + YAW +17': 'g90y'}
TARGET = {'stop0': 1.2, 'stop124': 1.2}
# regions that repeat another listed region (the same nodes, a wider mask), so they need no row of their own
EXCUSED = {
    'arm elsewhere in the hub end': 'the same nodes as the arm end-face corner band (listed)',
    'post -X front (inserts)': 'its plate-hole edge is the PETG ring by the insert (listed)',
    'post +X front (inserts)': 'its plate-hole edge is the PETG ring by the insert (listed)',
    'our post at the boss hole edge': 'the same nodes as the PETG ring by the insert (listed)',
}
# row words -> words that may stand for them in a report label
SYN = {'wall': ['elsewhere', 'skin'], 'hub-end': ['elsewhere', 'hub end'], 'end-face': ['end-face', 'end face'],
       'edge': ['corner', 'skin', 'edge'], 'corner': ['corner', 'skin'], 'plate': ['plate', 'skin'], 'ring': ['ring'],
       'roots': ['root'], 'root': ['root'], 'groove': ['groove'], 'fin': ['fin'], 'post': ['post'], 'posts': ['post'],
       'whole': ['whole'], 'pad': ['whole'], 'lug': ['lug'], 'face': ['face'], 'insert': ['insert', 'ring'], 'band': ['band']}
COMP = re.compile(r'\b(vm|layer|shear)\b')
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
head = [c.strip() for c in tab[0].split('|')[1:-1]]
rows = [ln for ln in tab if not ln.startswith('| ---')][1:]


def report_lines(files):
    """(label, component, triplet) for every SF triplet line of the spot / region / post_allc reports"""
    out = []
    for f in files:
        label = None
        for ln in f.read_text(encoding='utf-8', errors='replace').splitlines():
            if f.name.endswith('.post_allc.txt'):
                m = re.match(r'(arm|hub) (.+?)\s+(vm|layer|shear)\s+peak .*worst avg \.5/1/2 SF (\d+\.\d+)/(\d+\.\d+)/(\d+\.\d+)', ln)
                if m:
                    out.append((f'{m.group(1)} {m.group(2)}', m.group(3), '/'.join(m.groups()[3:])))
                continue
            if ln.startswith('-- '):
                label = ln[3:].split(':')[0].strip()
                continue
            m = re.search(r'SF \.5/1/2 (\d+\.\d+)/(\d+\.\d+)/(\d+\.\d+)', ln)
            if m and label is not None:
                c = COMP.search(ln.split('SF')[0])
                out.append((label, c.group(1) if c else '?', '/'.join(m.groups())))
    return out


def words(s):
    return [w for w in re.findall(r'[a-z][a-z\-]+', s.lower()) if len(w) >= 3 and w not in ('the', 'and', 'lowest', 'model', 'first')]


fails = 0
for row in rows:
    cells = [c.strip() for c in row.split('|')[1:-1]]
    case = cells[0].strip('*')
    key = CASES.get(case)
    if key is None:
        print(f'UNKNOWN CASE {case!r}'); fails += 1; continue
    files = sorted(RD.glob(f'{PREFIX}_{key}.*.txt'))
    if not files:
        print(f'NO REPORTS for {case} ({PREFIX}_{key}.*.txt)'); fails += 1; continue
    corpus = '\n'.join(f.read_text(encoding='utf-8', errors='replace') for f in files)
    flat = re.sub(r'\s*/\s*', '/', corpus)
    lines = report_lines([f for f in files if f.name.endswith(('.spot_report.txt', '.region_report.txt', '.post_allc.txt'))])
    rowtrips = set()
    for ci, cell in enumerate(cells[1:], 1):
        rest = cell
        for m in TRIP.finditer(cell):
            k = '/'.join(m.groups())
            rowtrips.add(k)
            rest = rest.replace(m.group(0), ' ')
            if k not in flat:
                print(f'NOT FOUND in {key}: triplet {k}'); fails += 1
                continue
            phrase = re.split(r'[;|]', cell[:m.start()])[-1]
            cm = COMP.findall(phrase)
            comp = cm[-1] if cm else None
            ctx = [w for w in words(phrase) if w not in ('vm', 'layer', 'shear')] or words(head[ci] if ci < len(head) else '')      # the header only when the phrase names no region
            cands = [(lab, c) for lab, c, t in lines if t == k]
            if not cands:
                continue      # a triplet from another report kind: found above, not label-checked
            ok = False
            for lab, c in cands:
                if comp and c != comp:
                    continue
                ll = lab.lower()
                if any(w in ll or any(s in ll for s in SYN.get(w, [])) for w in ctx):
                    ok = True
                    break
            if not ok:
                print(f'LABEL MISMATCH in {key}: {k} written as "{phrase.strip()[-60:]}" ({comp}); the reports have it as '
                      + '; '.join(f'{lab} ({c})' for lab, c in cands)); fails += 1
        for v in re.findall(r'(?<![\d.])(\d+\.\d+)(?![\d.])', rest):
            if not re.search(r'(?<![\d.])' + re.escape(v) + r'(?![\d])', corpus):
                print(f'NOT FOUND in {key}: number {v}'); fails += 1
    tgt = TARGET.get(key, 1.5)
    seen = set()
    for lab, c, k in lines:
        sfs = [float(x) for x in k.split('/')]
        if min(sfs) < tgt and k not in rowtrips and not any(lab.startswith(x) for x in EXCUSED) and (lab, c, k) not in seen:
            seen.add((lab, c, k))
            print(f'MISSING ROW in {case}: {lab} {c} {k}'); fails += 1
print(f'{len(rows)} rows checked, each against its own case reports ({PREFIX}_<case>.*.txt; spot, region and whole-part rows, all '
      f'three radii, triplets tied to their labels): {fails} failures')
sys.exit(1 if fails else 0)
