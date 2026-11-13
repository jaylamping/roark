"""Check every number in the packet's R1g results table against the saved reports (review, 2026-11-13: no number in the packet
without a saved file).
For each table row, every SF triplet "a / b / c" (0.5 / 1 / 2 mm) must appear as "a/b/c" in one of the saved report files, and
every other decimal number must appear in one of them as a whole token. Prints each number not found, with its row.
    python packet_numbers_check.py PACKET.md REPORT_DIR [REPORT_DIR ...]      (exit 1 if anything is unmatched)"""
import re
import sys
from pathlib import Path

packet = Path(sys.argv[1]).read_text(encoding='utf-8')
texts = []
for d in sys.argv[2:]:
    for f in sorted(Path(d).glob('*')):
        if f.suffix in ('.txt', '.json') and f.name != Path(sys.argv[1]).name:
            texts.append((f.name, f.read_text(encoding='utf-8', errors='replace')))
corpus = '\n'.join(t for _, t in texts)
flat = re.sub(r'\s*/\s*', '/', corpus)      # "a / b / c" and "a/b/c" both match

sec = packet.split('**Results', 1)[1]      # '**Results**' or '**Results (r1g4)**'
tab = []
for ln in sec.splitlines():      # the first table after the marker
    if ln.startswith('|'):
        tab.append(ln)
    elif tab:
        break
rows = [ln for ln in tab if not ln.startswith('| ---')][1:]
TRIP = re.compile(r'(\d+\.\d+)\s*/\s*(\d+\.\d+)\s*/\s*(\d+\.\d+)')
miss = 0
for row in rows:
    case = row.split('|')[1].strip()
    rest = row
    for m in TRIP.finditer(row):
        key = '/'.join(m.groups())
        if key not in flat:
            print(f'NOT FOUND triplet {key:20s} | {case}')
            miss += 1
        rest = rest.replace(m.group(0), ' ')
    for v in re.findall(r'(?<![\d.])(\d+\.\d+)(?![\d.])', rest):
        if not re.search(r'(?<![\d.])' + re.escape(v) + r'(?![\d])', corpus):
            print(f'NOT FOUND number  {v:20s} | {case}')
            miss += 1
print(f'{len(rows)} rows checked against {len(texts)} files: {miss} not found')
sys.exit(1 if miss else 0)
