"""Rotor ring (R17) spigot refit, 2026-11-18: grow the 8 crush ribs that hold the 6820's inner ring.

Brian: the spigot is loose in the bearing bore; one wrap of electrical tape (~+0.36 mm on Ø) made it snug,
so the printed rib tips came out under Ø100 (drawn Ø100.10, no XY compensation).
Measured 2026-11-18 (old ring, opposite rib pairs): 99.40 / 99.64 / 99.24, mean 99.43 = 0.67 under drawing.

Works on the rev k mesh (cad/rotor_ring_k.stl, print orientation: plate face on the bed, spigot up, z 6-17):
  spigot tube r 47.0-49.8, z 6-17, 45° lead-in r 49.8 -> 49.1 over z 16.3-17;
  8 ribs at -15° + k*45°, each a Ø1.0 cylinder (centre r 49.55, tip r 50.05), z 6.4-16.3, 45° top chamfer to r 49.8 at z 16.3.
New ribs: identical shape and angles, centre moved out so the tip sits at the new Ø. Nothing outside
r 49.80-50.6 / z 6.35-16.35 changes (rod holes, key and nut pockets, land, web, trim flange untouched).

Outputs (cad/):  rotor_ring_n_ribsXXXpXX.stl (full rings, see RINGS)
                 rotor_ring_fit_test_4x_100p30-101p00.stl  (4 test rings: spigot top 5.4 mm (4.7 mm of rib) + lead-in on a 0.8 mm flange to r 53.5,
                                           1/2/3/4 notches in the flange = Ø100.30/100.55/100.80/101.00)
Run: py -X utf8 make_refit.py   (trimesh + manifold3d)
"""
from pathlib import Path
import numpy as np
import trimesh
import manifold3d as mf

ROOT = Path(__file__).resolve().parents[4]          # POV-LED-Column
CAD = ROOT / "cad"
SRC = CAD / "rotor_ring_k.stl"

R_CYL, Z_RIB0, Z_CHAMF = 49.8, 6.4, 16.3            # spigot OD radius, rib start, where the rib chamfer meets the cylinder
RIB_R = 0.5                                         # rib = Ø1.0 cylinder
ANGLES = [-15 + 45 * k for k in range(8)]
RINGS = [100.30, 100.45, 100.60, 100.80, 101.00]           # full rings, rib-tip Ø
TESTS = [(1, 100.30), (2, 100.55), (3, 100.80), (4, 101.00)]  # fit-test plate: notch count, rib-tip Ø (v3)
SEG = 720
TEST_STL = "rotor_ring_fit_test_4x_100p30-101p00.stl"


def to_mf(m):
    return mf.Manifold(mf.Mesh(vert_properties=np.asarray(m.vertices, np.float32),
                               tri_verts=np.asarray(m.faces, np.uint32)))


def to_tm(M):
    g = M.to_mesh()
    return trimesh.Trimesh(np.asarray(g.vert_properties)[:, :3], np.asarray(g.tri_verts), process=False)


def annulus(r_in, r_out, z0, z1):
    h = z1 - z0
    return (mf.Manifold.cylinder(h, r_out, r_out, SEG) - mf.Manifold.cylinder(h, r_in, r_in, SEG)).translate([0, 0, z0])


def ribs(d_tip):
    rc = d_tip / 2 - RIB_R
    h = Z_CHAMF - Z_RIB0
    out = None
    for a in ANGLES:
        t = np.radians(a)
        c = mf.Manifold.cylinder(h, RIB_R, RIB_R, 48).translate([rc * np.cos(t), rc * np.sin(t), Z_RIB0])
        out = c if out is None else out + c
    # 45° top chamfer: keep r <= R_CYL + (Z_CHAMF - z)
    cone = mf.Manifold.cylinder(h, R_CYL + h, R_CYL, SEG).translate([0, 0, Z_RIB0])
    return out ^ cone


def ring(base, d_tip):
    cut = annulus(R_CYL + 0.005, 50.6, Z_RIB0 - 0.05, Z_CHAMF + 0.05)
    return (base - cut) + ribs(d_tip)


def test_ring(full, n_notch):
    z0, flange_t, r_fl = 11.6, 0.8, 53.5
    top = full ^ mf.Manifold.cylinder(17.0 - z0, 51.5, 51.5, SEG).translate([0, 0, z0])
    top = top.translate([0, 0, flange_t - z0])
    fl = annulus(47.0, r_fl, 0, flange_t + 0.01)
    for i in range(n_notch):                       # 1.6 wide x 2.5 deep notches, 7° apart, at +x
        t = np.radians(7 * (i - (n_notch - 1) / 2))
        cutter = mf.Manifold.cube([5.0, 1.6, 3 * flange_t], center=True).translate([r_fl, 0, 0])
        fl = fl - cutter.rotate([0, 0, np.degrees(t)])
    return top + fl


def main():
    base = to_mf(trimesh.load(SRC))
    orig_vol = base.volume()
    for d in RINGS:
        full = ring(base, d)
        tag = f"{d:.2f}".replace(".", "p")
        tm = to_tm(full)
        assert tm.is_watertight, tag
        tm.export(CAD / f"rotor_ring_n_ribs{tag}.stl")
        v = tm.vertices
        r = np.hypot(v[:, 0], v[:, 1])
        sel = (v[:, 2] > 6.3) & (v[:, 2] < 16.4)
        print(f"ring Ø{d:.2f}: rib tip Ø {2 * r[sel].max():.3f}, vol {full.volume() / 1000:.2f} cm3 "
              f"(rev k {orig_vol / 1000:.2f}), bbox {np.round(tm.bounds, 2).tolist()}")
    pos = [(-56, -55), (56, -55), (-56, 55), (56, 55)]        # 2 x 2, notch counts 1 2 / 3 4 (front row = 1, 2)
    plate = None
    for (n, d), p in zip(TESTS, pos):
        t = test_ring(ring(base, d), n).translate([p[0], p[1], 0])
        plate = t if plate is None else plate + t
    tp = to_tm(plate)
    assert tp.is_watertight
    tp.export(CAD / TEST_STL)
    print(f"fit-test plate: {plate.volume() / 1000:.2f} cm3, bbox {np.round(tp.bounds, 2).tolist()}")


if __name__ == "__main__":
    main()
