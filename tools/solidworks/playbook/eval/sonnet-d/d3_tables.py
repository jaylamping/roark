"""Turn d3_part1.json / d3_part2.json into markdown tables for REPORT.md (printed to stdout)."""
import json
from pathlib import Path

RES = Path(r"J:\code\roark-wt\sw-eval-sonnet-d\tools\solidworks\playbook\eval\sonnet-d")
for fn, title in (('d3_part1.json', 'Part one'), ('d3_part2.json', 'Part two')):
    p = RES / fn
    if not p.exists():
        continue
    d = json.loads(p.read_text())
    print(f'### {title}')
    print('| Plate | volume mm3 | hand mm3 | error % | mass g | bodies | STL watertight | STL mm3 | thinnest wall mm | where | changed from the table / request | why |')
    print('| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |')
    for k, r in d.items():
        print(f"| {k} | {r['volume_mm3']} | {r['hand_volume_mm3']} | {r['vol_error_pct']} | {r['mass_g']} | {r['bodies']} | {r['stl_watertight']} | {r['stl_volume_mm3']} | {r['min_wall_mm']} | {r['min_wall_where']} | {'yes' if r['changed'] else 'no'} | {r['why']} |")
    print()
