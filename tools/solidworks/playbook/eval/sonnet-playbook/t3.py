from study import *
def fillet_faces(d):
    return pick(d, kind='cyl', r=4.0)
out = {}
with job() as j:
    d = open_doc(j.sw, OUT / 'bracket.SLDPRT')
    rows_full = []
    def run(el):
        r = run_case(j, d, f'T3_EL{el}'.replace('.', 'p'), el, ctrl_faces=fillet_faces)
        rows_full.append(report(r, el))
        run.last = r
        return r
    rows, ok = converge(run, (3.0, 2.0, 1.5, 1.0))
    r = run.last
    print('summary', r.summary())
    # check 3: plain section, upright surfaces at z 12 (away from root fillet z<=10, bore z>=17, loaded face) on x=0 (tension) and x=6
    M = 150 * (28 - 12)
    hand_z12 = M / (50 * 36 / 6)
    msk = (np.abs(r.pos[:, 2] - 12) < 1.0) & (r.pos[:, 1] > 10) & (r.pos[:, 1] < 40) & ((r.pos[:, 0] < 0.05) | (r.pos[:, 0] > 5.95))
    sz = r.s[:, 3]
    plain_sz_x0 = float(sz[msk & (r.pos[:, 0] < 0.05)].mean())
    plain_sz_x6 = float(sz[msk & (r.pos[:, 0] > 5.95)].mean())
    vmpk = r.peak(msk)
    print('plain section z12: hand', hand_z12, 'sz x0', plain_sz_x0, 'sz x6', plain_sz_x6, 'vm peak', vmpk, 'n', int(msk.sum()))
    # singularity-style info: averages around the peak
    pk = r.peak()
    avg = {rad: r.average(pk[1], rad) for rad in (0.5, 1.0, 2.0)}
    print('avg around peak', avg)
    # how much is excluded
    print('vm max all nodes', float(r.vm.max()), 'at', r.pos[np.argmax(r.vm)].round(2).tolist())
    np.savez(OUT / 'T3_final.npz', pos=r.pos, s=r.s, disp=r.disp)
    out = dict(rows=rows, converged=ok, full=rows_full, hand_z12=hand_z12, plain_sz_x0=plain_sz_x0, plain_sz_x6=plain_sz_x6,
               plain_vm_peak=vmpk, avg=avg, vm_all=float(r.vm.max()), vm_all_at=r.pos[np.argmax(r.vm)].round(2).tolist(),
               summary=r.summary())
    close(j.sw, d)
(R / 't3_result.json').write_text(json.dumps(out, indent=1, default=str))
print(json.dumps(out, indent=1, default=str))
