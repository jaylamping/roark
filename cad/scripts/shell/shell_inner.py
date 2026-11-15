"""Inner surface of the body shell chest (Rev B sections) as a STEP, in torso frame coordinates.

Usage: python3 cad/scripts/shell/shell_inner.py cad/reference cad/reference/shell_inner.step
Robot frame (x fwd, y left, z up from floor) -> torso frame: X = y, Y = z - 810, Z = x
(scene.js: pelvis bottom 740 + waist extension 70; frame 155..495 above pelvis bottom; FW 38).
Inner = each constant-z outer section offset 2.4 mm inward (the shell wall), as frame_clearance.py does.
"""
import csv, sys, pathlib, math
import numpy as np
from shapely.geometry import Polygon
from build123d import Spline, Wire, Vector, Compound, export_step, Solid

WALL, N = 2.4, 96
Z0 = 810.0


def load(d, name):
    rows = list(csv.DictReader(open(d / f"shell_section_{name}.csv")))
    secs = {}
    for r in rows:
        secs.setdefault(int(r["section"]), []).append((float(r["x"]), float(r["y"]), float(r["z"])))
    return [np.array(secs[k]) for k in sorted(secs)]


def rings(d, part):
    panels = [load(d, f"{part}_{s}") for s in ("front_left", "front_right", "back_left", "back_right")]
    out = []
    for i in range(len(panels[0])):
        pts = np.vstack([p[i] for p in panels])
        z = pts[:, 2].mean()
        assert np.ptp(pts[:, 2]) < 0.05, (part, i, np.ptp(pts[:, 2]))
        c = pts[:, :2].mean(0)
        ang = np.arctan2(pts[:, 1] - c[1], pts[:, 0] - c[0])
        ring = pts[np.argsort(ang), :2]
        inner = Polygon(ring).buffer(0).buffer(-WALL)
        ex = np.array(inner.exterior.coords)[:-1]
        # resample evenly by arc length, starting at the front centre (max x near y=0)
        seg = np.linalg.norm(np.diff(np.vstack([ex, ex[:1]]), axis=0), axis=1)
        s = np.r_[0, np.cumsum(seg)]
        closed = np.vstack([ex, ex[:1]])
        k0 = np.argmax(ex[:, 0] - 5 * np.abs(ex[:, 1]))
        t = (s[k0] + np.linspace(0, s[-1], N, endpoint=False)) % s[-1]
        xs = np.interp(t, s, closed[:, 0]); ys = np.interp(t, s, closed[:, 1])
        out.append((z, xs, ys))
    return out


def to_frame(x, y, z):
    return Vector(y, z - Z0, x)


def main(d, outp):
    d = pathlib.Path(d)
    lofts = []
    for part in ("lower", "upper"):
        rs = rings(d, part)
        step = 2 if part == "upper" else 1
        rs = rs[::step] + ([rs[-1]] if (len(rs) - 1) % step else [])
        wires = [Wire([Spline(*[to_frame(x, y, z) for x, y in zip(xs, ys)], periodic=True)]) for z, xs, ys in rs]
        lo = Solid.make_loft(wires, ruled=False)
        faces = [f for f in lo.faces() if f.geom_type != "PLANE"]
        sh = Compound(children=faces, label=f"shell_inner_{part}")
        lofts.append(sh)
        print(part, len(rs), "sections, frame Y", round(rs[0][0] - Z0, 1), "to", round(rs[-1][0] - Z0, 1))
    export_step(Compound(children=lofts, label="shell_inner"), outp)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
