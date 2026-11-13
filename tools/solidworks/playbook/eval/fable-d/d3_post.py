"""D3 after the SolidWorks jobs: picture sheets of the plates and the two tables as markdown (d3_tables.md), from the JSON.

    python d3_post.py one | two
"""
import json
import sys

from common import HERE, PICS, WIP
import sheet

part = sys.argv[1]
res = json.loads((HERE / f'd3_part_{part}.json').read_text())
sfx = '' if part == 'one' else '_b'
names = list(res['plates'])
st = sheet.sheet([str(WIP / 'd3' / f'{n}{sfx}.stl') for n in names], str(PICS / f'd3_part_{part}.png'), px=210)
lines = ['| Plate | Volume mm3 | Hand mm3 | Diff % | Mass g | Bodies | STL watertight | Thinnest wall mm, where | '
         + ('Counterbore floor Z mm | ' if part == 'two' else '') + 'As the table says? |', '| --- | --- | --- | --- | --- | --- | --- | --- | '
         + ('--- | ' if part == 'two' else '') + '--- |']
for n in names:
    r = res['plates'][n]
    s = r['built']
    what = 'as the table says' if not r['changed'] else 'CHANGED: ' + '; '.join(r['why'])
    lines.append(f"| {n}{sfx} | {r['volume_mm3']:.2f} | {r['hand_volume_mm3']:.2f} | {r['diff_pct']:+.4f} | {r['mass_g']:.2f} | {r['bodies']} | "
                 f"{'yes, 1 shell' if r['stl_watertight'] and r['stl_shells'] == 1 and r['stl_volume_ok'] else 'NO'} | "
                 f"{r['min_wall_mm']:.2f}, {r['min_wall_where']} | " + (f"{r['counterbore_floor_z_mm']:.2f} (before {r['floor_z_before']:.2f}) | " if part == 'two' else '') + f"{what} |")
lines.append('')
lines.append('As built (measured on each finished solid: every hole centre, diameter and Z range; the solid must match or the script stops):')
lines.append('')
lines.append('| Plate | Outside | Thick | Bore | Ring A | Ring B | Counterbore | Chamfer |')
lines.append('| --- | --- | --- | --- | --- | --- | --- | --- |')
for n in names:
    s, m = res['plates'][n]['built'], res['plates'][n]['measured']
    lines.append(f"| {n}{sfx} | {m['od']:g} | {m['thick']:g} | {m['bore']:g} | {m['n_a']} x {m['a_dia'][0]:g} on {m['a_circle'][0]:g}, first at {m['a_angles'][0]:g} deg | "
                 f"{m['n_b']} x {m['b_dia'][0]:g} on {m['b_circle'][0]:g}, first at {m['b_angles'][0]:g} deg | {m['cb_dia'][0]:g} from Z {m['floor_z'][0]:g} to {m['cb_top_z'][0]:g} | {s['chamfer']:g} |")
(HERE / f'd3_table_{part}.md').write_text('\n'.join(lines) + '\n')
print('\n'.join(lines))
print(json.dumps({k: v['bbox_mm'] for k, v in st.items()}))
