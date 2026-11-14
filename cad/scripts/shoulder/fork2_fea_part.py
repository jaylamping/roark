"""Fork FEA model as ONE body: the fork front (a look or analysis build) and the real fork rear inserted in place and
combined, so the joint between them is solid and nothing can float (the two-body model of fork_fea_part.py never solved).
Saved as cad/_sim/shoulder/fork2_<tag>.SLDPRT for fea_shoulder.py's F2_* cases.

    python fork2_fea_part.py TAG [TAG ...]        (TAG = a LOOK name whose fork front is in cad/_wip/look/<TAG>)
"""
import sys

from swk import CAD, L, NUL, app, finish, new_part

F = CAD / '_sim' / 'shoulder'
import os
# FORK2_REAR_TAG: a look build of the fork rear (cad/_wip/look/<tag>) in place of the real one; the result is fork2_<TAG>_<rear tag>
RT = os.environ.get('FORK2_REAR_TAG', '')
REAR = (CAD / '_wip' / 'look' / RT / 'shoulder_fork_rear_left.SLDPRT') if RT else (CAD / 'shoulder' / 'left' / 'shoulder_fork_rear_left.SLDPRT')


def vol(d):
    return [round(b.GetMassProperties(1.0)[3] * 1e9) for b in d.GetBodies2(0, True)]


def build(tag):
    front = (CAD / 'shoulder' / 'left' / 'shoulder_fork_front_left.SLDPRT') if tag == 'real' else (CAD / '_wip' / 'look' / tag / 'shoulder_fork_front_left.SLDPRT')      # 'real': the released part
    d = new_part(F / (f'fork2_{tag}_{RT}.SLDPRT' if RT else f'fork2_{tag}.SLDPRT'))
    for p in (front, REAR):
        f = d.InsertPart3(str(p), 1 | 2, '')          # solid bodies, no planes or axes
        print(tag, p.name, 'inserted', f is not None, flush=True)
    d.ForceRebuild3(False)
    v0 = vol(d)
    print(tag, 'bodies before', v0, flush=True)
    if os.environ.get('FORK2_NOCOMBINE'):
        # two separate bodies, for the joint check (bolt connectors and contact between them): saved as forkj_<tag>
        e, w = L(), L()
        ok = d.Extension.SaveAs(str(F / f'forkj_{tag}.SLDPRT'), 0, 1, NUL, e, w)
        print(tag, 'two bodies kept, saved as forkj_%s.SLDPRT' % tag, ok, e.value, flush=True)
        return
    done = False
    for mark in (2, 0, 1):
        d.ClearSelection2(True)
        ok = []
        for b in d.GetBodies2(0, True):
            sd = d.SelectionManager.CreateSelectData
            sd.Mark = mark
            ok.append(b.Select2(True, sd))
        f = d.FeatureManager.InsertCombineFeature(15903, NUL, NUL)      # add
        d.ForceRebuild3(False)
        v1 = vol(d)
        print(tag, 'combine with mark', mark, 'selected', ok, 'feature', f is not None, 'bodies after', v1, flush=True)
        if len(v1) == 1:
            done = True
            break
    if not done:
        raise SystemExit(f'{tag}: the two bodies did not combine (they may not touch)')
    print(tag, 'volume kept: %d of %d mm3' % (v1[0], sum(v0)), flush=True)
    e, w = L(), L()
    print(tag, 'save', d.Save3(1, e, w), e.value, w.value, flush=True)


if __name__ == '__main__':
    try:
        for t in sys.argv[1:]:
            build(t)
    finally:
        try:
            app().CloseAllDocuments(True)
        except Exception:
            pass
        finish()
