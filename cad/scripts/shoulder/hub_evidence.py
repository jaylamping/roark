"""Evidence file of the hub for the pre-print gate (conventions/part-lifecycle.md section 2), from the FE runs on record
in hardware/shoulder/study-20261111/checks/A_HUB_LUGS.md ("Rev E1 candidate").

    python hub_evidence.py <the hub export the runs stand for> [out.json]

The export's content hash is recorded under the spec's export path, so the evidence is stale as soon as that file holds
anything else. `converged` is true only where the result held on a finer mesh; where it is false the note says why.
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'tools' / 'cad'))
import gate      # noqa: E402
import gitlfs    # noqa: E402

PART = 'shoulder_hub_left'
SPEC = REPO / 'cad' / 'shoulder' / 'shoulder_requirements.md'
# safety factors, worst 0.5 mm ball, hub nodes only (hub_top_post.py, hub_lug_post.py, hub_stop2_post.py)
FEA = [
    dict(case='HUB_TOP', part=PART, bulk_sf=3.68, layer_sf=3.16, shear_sf=2.07, converged=False,
         note='HUBB_Ah on the final rev E1 shape, global element 6.0 with the fine zones, Intel direct sparse; 1 mm ball 4.20 / 3.54 / 2.68. '
              'Not converged by the rule: a finer global mesh passes the 14 GB limit of the direct solver, and on rev D3c7 the '
              'same step (4.5 against 2.6) moved the layer figure from 0.91 to 0.65'),
    dict(case='HUB_LUG', part=PART, bulk_sf=1.56, layer_sf=1.61, shear_sf=1.56, converged=False,
         note='HUBL_G90YAWP_MAX, 1.19 M nodes; 1.56 is the governing figure (shear across the layers at the lug), entered as bulk. '
              'Run on the first rev E1 shape; the later edits (hole edges, step fillet, head seats) do not touch the lugs, but the '
              'run has not been repeated on this export'),
    dict(case='HUB_ESTOP', part=PART, bulk_sf=3.10, layer_sf=3.10, converged=False,
         note='HUBL_STOP6_ZB; 3.10 is the governing figure of the read-out, entered for both marks. Run on the first rev E1 shape, '
              'not repeated on this export'),
]
ACCESS = [dict(part=PART, insertion_clear=True, screws_reachable=True,
               method='by geometry, not a ray check: the six M4 heads sit on the tube ends in the open centre bore and take a straight '
                      'driver from the arm side before the arm goes on; the arm thread compared this export with the released hub '
                      'below Y 302 (identical) and checked its cable route (3.64 mm smallest clearance)',
               notes='the RS02 output thread depth (7 mm on the drawing) is not measured on a real motor')]


def main(export, out):
    spec = gate.front_matter(SPEC)
    part = next(p for p in spec['part'] if p['name'] == PART)
    ev = dict(sources={part['export']: gitlfs.content_sha256(Path(export))},
              load_cases={lc['id']: gate.load_case_sha256(lc) for lc in spec['load_case'] if lc['id'] in {r['case'] for r in FEA}},
              fea=FEA, access=ACCESS)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(ev, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(out, ev['sources'])


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else REPO / "cad" / gate.front_matter(SPEC)["evidence"])
