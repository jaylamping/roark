"""One-screen summary of a hub_r1c post.txt: per region the worst 0.5 / 1 / 2 mm sphere-average SF for vm, layer and interlayer
shear (with the 0.5 mm node count), the lowest region overall, lug forces, bolts / inserts / pads, sanity.
    python case_summary.py POST_TXT [target]"""
import re
import sys

txt = open(sys.argv[1], encoding='utf-8', errors='ignore').read().splitlines()
target = float(sys.argv[2]) if len(sys.argv) > 2 else 1.2
rows = {}
pat = re.compile(r'^(arm|hub)\s+(.+?)\s+(vm|layer|shear)\s+peak.*?worst avg \.5/1/2 SF ([\d.\-/ ]+?) \(0\.5 mm: (\d+) nodes at (\[[^\]]+\]) th (\d+)\)')
for line in txt:
    m = pat.match(line.strip())
    if not m:
        continue
    body, reg, lab, sfs, n, at, th = m.groups()
    vals = [float(v) if v not in ('-', '') else 99.0 for v in sfs.strip().split('/')]
    rows.setdefault(f'{body} {reg.strip()}', {})[lab] = (vals, int(n), at, th)
skip = ('WHOLE', 'skin elsewhere')
low = []
for reg, d in rows.items():
    parts = []
    for lab in ('vm', 'layer', 'shear'):
        if lab in d:
            v, n, at, th = d[lab]
            parts.append(f'{lab} {v[0]:.2f}/{v[1]:.2f}/{v[2]:.2f} (n{n})')
            if not any(s in reg for s in skip):
                low.append((v[0], reg, lab, n, at, th, v))
    print(f'{reg[:58]:58s} ' + '  '.join(parts))
low.sort()
print('\nLOWEST (0.5 mm, excluding whole-body and skin rows):')
for v0, reg, lab, n, at, th, v in low[:5]:
    flag = '' if v0 >= target else f'  < {target}'
    print(f'  {v0:.2f} {reg} {lab} at {at} th {th} (n{n}; 1 mm {v[1]:.2f}, 2 mm {v[2]:.2f}){flag}')
for line in txt:
    if line.startswith(('lug ', 'bolts:', 'inserts:', 'soft pads', 'SANITY', 'GUARD', 'load-flank')):
        print(line.strip())
