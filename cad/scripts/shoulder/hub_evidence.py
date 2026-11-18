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
    dict(case='HUB_TOP', part=PART, bulk_sf=2.84, layer_sf=2.30, shear_sf=1.83, converged=True,
         note='HUBB_Ah on the adopted shape (seats at Y 298.86, R 4 at the tubes), Intel direct sparse. The lowest of the hub-top '
              'regions on the run with a 1.3 mm zone on the six tube-to-plate rounds (383k nodes): von Mises and layer tension round '
              'the cable tunnel, shear at the rounds. Standard mesh (338k nodes): 1.95 in shear at the rounds, within 6 % on the '
              '0.5 mm ball and 1 % on the 1 mm ball (2.07 against 2.06). Left out as a connector artefact: the tube walls within '
              '3 mm of the head seats, where the screws are tied rigidly (shear 1.40 to 1.47)'),
    dict(case='HUB_LUG', part=PART, bulk_sf=1.54, layer_sf=1.62, shear_sf=1.54, converged=True,
         note='HUBL_G90YAWP_MAX on the adopted shape; 1.54 is the governing figure (shear across the layers at the lug), entered as '
              'bulk; von Mises 2.63. The lower of two meshes: 1.20 M nodes reads layer 1.62, shear 1.55, von Mises 2.66; 1.54 M nodes '
              '(mesh controls x 0.8) reads 1.63, 1.54, 2.63. Within 1.2 % on the 0.5 mm ball and 2 % on the 1 mm ball'),
    dict(case='HUB_ESTOP', part=PART, bulk_sf=3.10, layer_sf=3.26, shear_sf=3.10, converged=True,
         note='HUBL_STOP6_ZB on the adopted shape; 3.10 is shear across the layers, entered as bulk; von Mises 5.40. The lower of two '
              'meshes: 1.20 M nodes reads layer 3.27, shear 3.11, von Mises 5.44; 1.55 M nodes (mesh controls x 0.8) reads 3.26, 3.10, '
              '5.40. Within 1 % on the 0.5 mm ball and 4 % on the 1 mm ball'),
]
ACCESS = [dict(part=PART, insertion_clear=True, screws_reachable=True,
               method='by geometry, not a ray check: the six M4 heads sit on the tube ends in the open centre bore and take a straight '
                      'driver from the arm side before the arm goes on; the arm thread compared the first rev E1 export with the released hub '
                      'below Y 302 (identical) and checked its cable route (3.64 mm smallest clearance)',
               notes='M4 x 30 with one washer goes 5.2 mm into the RS02; its holes bottom out at 6.5 to 7 mm (Joey, measured 2026-11-15)')]


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
