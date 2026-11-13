from t6 import *
OUT.mkdir(parents=True, exist_ok=True)
el, cl = float(sys.argv[1]), float(sys.argv[2])
do_build = '--build' in sys.argv
res = {}
with job() as j:
    if do_build:
        build(j)
    d = open_doc(j.sw, OUT / 'ct6.SLDPRT')
    t0 = time.time()
    r = solve(j, d, f'T6_E{el}_C{cl}'.replace('.', 'p'), el, cl)
    log('solve total s', round(time.time() - t0))
    print('summary', r.summary())
    rad, y, pin, inblock, pad = label(r)
    # sanity on the labels: every node is in exactly one class (except coincident interface nodes)
    log('nodes', r.nodes, 'pin', int(pin.sum()), 'block', int(inblock.sum()), 'pad', int(pad.sum()), 'unlabelled', int((~pin & ~inblock & ~pad).sum()))
    # block peak: block nodes, away from the fixed bottom (2 el) 
    fixed_away = r.away()
    bm = inblock & fixed_away
    vb, atb = r.peak(bm)
    vb_all = float(r.vm[inblock].max())
    # pin
    vp, atp = r.peak(pin)
    # pad
    vpad = float(r.vm[pad].max()) if pad.any() else None
    # rises
    uz = r.disp[:, 3]
    pin_axis = pin & (rad < 1.0) & (y < 14)
    rise = float(uz[pin_axis].mean())
    top_pin = pin & (rad > 4.9) & (r.pos[:, 2] > 14.9) & (np.abs(r.pos[:, 0]) < 0.6) & (y < 10)
    top_hole = inblock & (rad < 5.15) & (r.pos[:, 2] > 15.0) & (np.abs(r.pos[:, 0]) < 0.6) & (y < 10)
    pen = (15.0 + uz[top_pin].mean()) - (15.1 + uz[top_hole].mean()) if top_pin.any() and top_hole.any() else None
    # contact patch: block nodes on hole face with vm > 1 MPa
    holeface = inblock & (rad < 5.15)
    ang = np.degrees(np.arctan2(r.pos[:, 0], r.pos[:, 2] - 10))
    patch = holeface & (r.vm > 0.5 * vb)
    res = dict(el=el, cl=cl, nodes=r.nodes, elements=r.elements, solve_s=r.seconds, reaction=r.reaction, applied=r.applied,
               block_peak=(vb, atb), block_peak_all=vb_all, block_peak_all_at=r.pos[inblock][np.argmax(r.vm[inblock])].round(2).tolist(),
               pin_peak=(vp, atp), pad_peak_vm=vpad, pin_rise_axis_mm=rise, penetration_mm=pen,
               patch_angles=[float(ang[patch].min()), float(ang[patch].max())] if patch.any() else None,
               patch_y=[float(y[patch].min()), float(y[patch].max())] if patch.any() else None,
               max_disp=r.max_disp(), excessive=r.excessive,
               top_pin_n=int(top_pin.sum()), top_hole_n=int(top_hole.sum()),
               hole_top_avg_vm_midspan=float(r.vm[holeface & (y < 6) & (np.abs(ang) < 20)].max()) if (holeface & (y < 6) & (np.abs(ang) < 20)).any() else None)
    prof = {}
    for lo, hi in ((0,3),(3,6),(6,9),(9,12),(12,14),(14,14.9),(14.9,15.001)):
        m = holeface & (y >= lo) & (y < hi)
        top = m & (np.abs(ang) < 40)
        prof[f'{lo}-{hi}'] = [float(r.vm[top].max()) if top.any() else None, float(r.vm[m & (np.abs(ang) >= 40)].max()) if (m & (np.abs(ang) >= 40)).any() else None, int(top.sum())]
    res['profile_top_other_n'] = prof
    np.savez(OUT / f'res_E{el}_C{cl}.npz', pos=r.pos, s=r.s, disp=r.disp)
    close(j.sw, d)
print(json.dumps(res, indent=1, default=str))
(R / f't6_result_E{el}_C{cl}.json').write_text(json.dumps(res, indent=1, default=str))
