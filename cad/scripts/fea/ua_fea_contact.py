"""Upper-arm clamshell contact FEA: the ring as its own body in its printed clearances (cad/_sim/upper-arm/
UA_CLAM_CONTACT.SLDPRT, built by cad/scripts/arm/ua_parts.py fea_contact), no-penetration contact between the ring and the
halves, the ring pin as a pin connector, loads and fixture as in ua_fea.py. Reports the pin connector force (the ring-screw
load) next to the stresses.

    python cad/scripts/fea/ua_fea_contact.py GLm GLp G90 ...
"""
import sys

from p3_fea import CASES, F, PARTS, I, pick, run, VARIANT, pythoncom
from ua_fea import HUB_BOX, LOADS, RING_BOX, SEAM, case

PARTS['clam_c'] = F / 'UA_CLAM_CONTACT.SLDPRT'
PIN = ('cyl', 1.7, [156.0, 244.0, -35.0, 161.0, 249.0, -11.0])
REGIONS = {'seam_band': SEAM, 'hub': HUB_BOX, 'ring': RING_BOX, 'ring_end': [160, 232, -30, 175, 250, 42]}


def ring_body(d):
    for b in d.GetBodies2(0, True):
        x = b.GetBodyBox()
        if x[0] * 1000 > 149.5 and x[3] * 1000 < 167.5:
            return b
    raise SystemExit('no ring body')


def contact(st, d, lbc):
    bs = list(d.GetBodies2(0, True))
    print(' bodies', len(bs), [round(b.GetMassProperties(1190)[3] * 1e9) for b in bs], flush=True)
    if len(bs) != 2:
        raise SystemExit('expected 2 bodies (halves+hub, ring)')
    rb = ring_body(d)
    cm = st.ContactManager
    n = I()
    pairs = cm.FindNonTouchingPairs(VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, bs), 0.0, 0.0004, n)        # faces of different bodies 0 .. 0.4 mm apart (m)
    pairs = pairs[0] if isinstance(pairs, tuple) and len(pairs) == 2 and not hasattr(pairs[1], 'GetBox') else pairs
    print(' non-touching pairs', getattr(n, 'value', n), 'returned', None if pairs is None else len(pairs), flush=True)
    err = I()
    cm.CreateContactSetsFromPairList(0, VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, list(pairs or [])), err)         # no penetration
    print(' contact sets', cm.ContactSetCount, 'err', err.value, flush=True)
    if err.value or cm.ContactSetCount == 0:
        raise SystemExit('contact failed')
    pf = pick(d, PIN)
    ring_f = [f for f in pf if f.GetBody.Name == rb.Name]
    half_f = [f for f in pf if f.GetBody.Name != rb.Name]
    err = I()
    pin = lbc.AddPinConnector(VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, ring_f), VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, half_f), err)
    print(' pin connector faces', len(ring_f), len(half_f), 'err', err.value, flush=True)
    if err.value:
        raise SystemExit('pin failed')
    try:
        st.StaticStudyOptions.UseSoftSpring = 1        # the ring is held only by contact and one pin: stabilise rigid-body modes
    except Exception as ex:
        print(' soft springs not set', str(ex)[:80], flush=True)

    def post(st_, res):
        try:
            err_ = I()
            f = res.GetConnectorForces2(pin, 0, 0, err_) if hasattr(res, 'GetConnectorForces2') else None
            return {'pin_force': None if f is None else [round(float(v), 2) for v in (f[0] if isinstance(f, tuple) else f)]}
        except Exception as ex:
            return {'pin_force_err': str(ex)[:120]}
    return post


for k, (f, m) in LOADS.items():
    CASES['c' + k] = case(f, m, part='clam_c', regions=REGIONS, pre_mesh=contact)
    CASES['c' + k + '_fine'] = case(f, m, fine=True, part='clam_c', regions=REGIONS, pre_mesh=contact)

if __name__ == '__main__':
    for n in sys.argv[1:]:
        run('clam_' + n, CASES['c' + n if not n.startswith('c') else n])
