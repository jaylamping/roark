"""D2: the report's tables as markdown (d2_tables.md) and the verdict (d2_verdict.json), from the JSON the other scripts wrote."""
import json

from common import HERE


def rd(name):
    p = HERE / name
    return json.loads(p.read_text()) if p.exists() else None


posts = {t: rd(f'd2_post_{t}.json') for t in ('c', 'm', 'f', 's')}
tags = [t for t in ('c', 'm', 'f') if posts[t]]
fine = posts[tags[-1]]
corner = rd('d2_corner.json')
fea = {t: rd(f'd2_fea_{t}.json') for t in ('c', 'm', 'f', 's')}
SIZES = dict(c='3.5 / 1.4 / 1.0', m='2.5 / 1.0 / 0.7', f='2.1 / 0.85 / 1.2', s='2.5 / 1.0 / 0.7')
L = []

L += ['Meshes (element size mm: global / seats and ring outside / screw shanks), all second-order, direct sparse solver:', '',
      '| Mesh | Sizes | Nodes | Reaction +Y case N | Reaction +X case N | Solve + readback s |', '| --- | --- | --- | --- | --- | --- |']
for t in tags:
    p = posts[t]
    L.append(f"| {t} | {SIZES[t]} | {p['Y300']['nodes']:,} | {p['Y300']['reaction_face_N'][1]:.2f} on the face, {p['Y300']['reaction_hub_N'][1]:.3f} on the plug | "
             f"{p['X300']['reaction_face_N'][0]:.2f} on the face, {p['X300']['reaction_hub_N'][0]:.3f} on the plug | "
             f"{fea[t]['Y300']['seconds']:.0f}, {fea[t]['X300']['seconds']:.0f} |")
L += ['', 'Screw loads from the study (mid shank, a plane fitted to the stress over the section, times the area), N:', '',
      '| Mesh | Case | X 31 Z 0 | X 31 Z 7 | X -31 Z 0 | X -31 Z 7 | Sum | Hand |', '| --- | --- | --- | --- | --- | --- | --- | --- |']
for t in tags:
    p = posts[t]
    y, x = p['Y300']['screws'], p['X300']['screws']
    L.append(f"| {t} | +Y tension | " + ' | '.join(f"{s['tension_N']:.1f}" for s in y) + f" | {p['Y300']['screw_sum_N']['tension']:.1f} | 75.0 each, 300 in all |")
    L.append(f"| {t} | +X tension | " + ' | '.join(f"{s['tension_N']:.1f}" for s in x) + f" | {p['X300']['screw_sum_N']['tension']:.1f} | 24 each first guess; 75.7 in all from the contact angles |")
    L.append(f"| {t} | +X shear along X | " + ' | '.join(f"{s['shear_x_N']:.1f}" for s in x) + f" | {p['X300']['screw_sum_N']['shear_x']:.1f} | 37.5 each first guess; 17.5 in all from the contact angles |")

L += ['', f'Factors on mesh {tags[-1]}, for each way the layers could be stacked (value MPa, factor, where). Excluded: plastic within 1 mm of a bonded steel face '
      '(under the screw heads, round the insert ends) and within 3 mm of the fixed face; their largest values are in the last column.', '',
      '| Case | Half | Layers along | von Mises / 45 | Tension across layers / 22.5 | Shear between layers / 13 | Largest excluded von Mises (steel bond, fixed face) |',
      '| --- | --- | --- | --- | --- | --- | --- |']
low = {}
for c in ('Y300', 'X300'):
    for h in ('upper', 'lower'):
        for lay in ('layers_Z', 'layers_Y', 'layers_X'):
            r = fine[c][h][lay]
            ex = fine[c][h]['excluded']
            L.append(f"| {'+Y' if c == 'Y300' else '+X'} | {h} | {lay[-1]} | " + ' | '.join(f"{r[k]['mpa']:.2f}, **{r[k]['sf']:.1f}**, {tuple(r[k]['at'])}" for k in ('vm', 'layer', 'shear'))
                     + f" | {ex['vm_max_at_bonded_steel']}, {ex['vm_max_at_fixed_face']} |")
            for k in ('vm', 'layer', 'shear'):
                key = (h, lay, k)
                if key not in low or r[k]['sf'] < low[key][0]:
                    low[key] = (r[k]['sf'], c, r[k]['mpa'], r[k]['at'])
L += ['', 'Lowest factor over both load cases, per half and print direction:', '', '| Half | Layers along | Yield | Across layers | Between layers |', '| --- | --- | --- | --- | --- |']
for h in ('upper', 'lower'):
    for lay in ('layers_Z', 'layers_Y', 'layers_X'):
        L.append(f"| {h} | {lay[-1]} | " + ' | '.join(f"{low[(h, lay, k)][0]:.1f} ({'+Y' if low[(h, lay, k)][1] == 'Y300' else '+X'})" for k in ('vm', 'layer', 'shear')) + ' |')

if corner:
    L += ['', 'Convergence, layers along Z. The place of each peak on the finest mesh is followed through all meshes: the largest value within 1.5 mm of it, '
          'and the mean within 2 mm (with node count). Last step is between the two finest meshes.', '',
          '| Case, half, measure | Where | ' + ' | '.join(f'Peak {t}' for t in tags) + ' | Last step | ' + ' | '.join(f'2 mm mean {t}' for t in tags) + ' | Converged |',
          '| --- | --- | ' + ' | '.join('---' for _ in tags) + ' | --- | ' + ' | '.join('---' for _ in tags) + ' | --- |']
    for k, v in corner.items():
        rows = {r['mesh']: r for r in v['rows']}
        means = [rows[t]['mean_within_2mm'] for t in tags]
        mstep = abs(means[-1][0] - means[-2][0]) / max(means[-2][0], 1e-9) if len(means) > 1 else 0
        L.append(f"| {k.replace('Y300', '+Y').replace('X300', '+X')} | {tuple(v['at'])} | " + ' | '.join(f"{rows[t]['peak_within_1p5mm']:.2f}" for t in tags)
                 + f" | {100 * v['last_step']:.0f} % | " + ' | '.join(f"{m[0]:.2f} ({m[1]})" for m in means)
                 + f" | peak {'yes' if v['converged'] else 'NO'}, mean {'yes' if mstep <= 0.05 or abs(means[-1][0] - means[-2][0]) <= 0.1 else 'NO'} |")

if posts['s']:
    L += ['', 'Support a second way: only the walls of the two M4 insert holes held (mesh sizes as m), layers along Z:', '',
          '| Case | Half | von Mises | Tension across layers | Shear between layers | Screw tension sum N | Reaction N |', '| --- | --- | --- | --- | --- | --- | --- |']
    for c in ('Y300', 'X300'):
        if c in posts['s']:
            for h in ('upper', 'lower'):
                r = posts['s'][c][h]['layers_Z']
                L.append(f"| {'+Y' if c == 'Y300' else '+X'} | {h} | " + ' | '.join(f"{r[k]['mpa']:.2f}, **{r[k]['sf']:.1f}**, {tuple(r[k]['at'])}" for k in ('vm', 'layer', 'shear'))
                         + f" | {posts['s'][c]['screw_sum_N']['tension']:.1f} | {posts['s'][c]['reaction_face_N']} |")
(HERE / 'd2_tables.md').write_text('\n'.join(L) + '\n')
print('\n'.join(L))
