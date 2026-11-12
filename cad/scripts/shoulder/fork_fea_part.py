"""Fork FEA model: one part holding the fork front and fork rear as two bodies (InsertPart, same coordinates), saved in
cad/_sim/shoulder/fork_fea.SLDPRT for fea_shoulder.py's FORK_* cases (bonded where they meet at the joint face)."""
import sys
from swk import session, STATE, L, CAD
from build_parts import OUT, NAMES

F = CAD / '_sim' / 'shoulder'


def main():
    from swk import new_part
    d = new_part(F / 'fork_fea.SLDPRT')
    for k in ('fork_front', 'fork_rear'):
        p = OUT / f"{NAMES[k]}.SLDPRT"
        f = d.InsertPart3(str(p), 1 | 2, '')          # solid bodies, no planes/axes
        print(k, p.name, 'inserted', f is not None, flush=True)
    d.ForceRebuild3(False)
    bodies = d.GetBodies2(0, True)
    print('bodies', len(bodies), [round(b.GetMassProperties(1.0)[3] * 1e9) for b in bodies], flush=True)
    e, w = L(), L()
    print('save', d.Save3(1, e, w), e.value, w.value, flush=True)


if __name__ == '__main__':
    main()
