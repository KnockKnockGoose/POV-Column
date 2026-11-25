# Rev o concentricity pass (2026-11-21), part 2: plates that go with cad/make_revo_rotor_pin_jig.py. Mesh CSG; Fusion not touched.
#   * revo_core_and_keys_plate.stl (PET-CF): the hub core with insert relief (rotor_hub_core_o_relief.stl, made by the jig script)
#     + 15 hex keys for the plate <-> rotor-ring joint in three sizes, 5 each: 5.90 / 5.95 / 6.00 AF x 5.1 (1 / 2 / 3 dimples on
#     top). The rev k key is 5.85 AF in 6.0 AF pockets (0.075 per flat as drawn, plus whatever the printed pockets add): the plate
#     can shift ~0.15 on the ring. Pick the biggest key that still pushes into BOTH pockets by hand. 0.3 x 45 deg chamfer both ends.
#   * revo_bearing_cup_v2_b24p10_relief.stl (PETG-CF): cup v2 with the coupon-picked d24.10 bore; the 0.3 mm insert-lip relief
#     at the 3 screw holes in its deck face becomes d6.5 x 1.0 (a deck insert or its collar up to 1 mm proud can't cock the cup).
#     1.5 mm stays between the relief and the screw counterbore's floor. Everything else identical.
# Usage (repo root): py -X utf8 cad/make_revo_concentricity_parts.py
import math, os, numpy as np, trimesh, manifold3d as mf

HERE = os.path.dirname(os.path.abspath(__file__))
KEY_H, KEY_CH = 5.1, 0.3
KEY_SIZES = [(1, 5.90), (2, 5.95), (3, 6.00)]


def from_tm(t):
    return mf.Manifold(mf.Mesh(vert_properties=np.asarray(t.vertices, dtype=np.float32), tri_verts=np.asarray(t.faces, dtype=np.uint32)))


def to_tm(M):
    g = M.to_mesh()
    return trimesh.Trimesh(g.vert_properties[:, :3], g.tri_verts, process=True)


def hexagon(af):
    rc = af / math.sqrt(3.0)                       # circumradius
    return mf.CrossSection([[(rc * math.cos(math.radians(60 * k)), rc * math.sin(math.radians(60 * k))) for k in range(6)]])


def slab(cs, z0, z1):
    return mf.Manifold.extrude(cs, z1 - z0).translate([0, 0, z0])


def key(af, dots):
    c = KEY_CH
    lo = slab(hexagon(af - 2 * c), 0.0, 0.01) + slab(hexagon(af), c, c + 0.01)
    hi = slab(hexagon(af), KEY_H - c - 0.01, KEY_H - c) + slab(hexagon(af - 2 * c), KEY_H - 0.01, KEY_H)
    k = mf.Manifold.hull(lo) + slab(hexagon(af), c, KEY_H - c) + mf.Manifold.hull(hi)
    for j in range(dots):
        x = (j - (dots - 1) / 2) * 1.4
        k -= mf.Manifold.cylinder(1.0, 0.45, 0.45, 24).translate([x, 0, KEY_H - 0.4])
    return k


def cyl(r, z0, z1, x=0.0, y=0.0, n=96):
    return mf.Manifold.cylinder(z1 - z0, r, r, n).translate([x, y, z0])


if __name__ == "__main__":
    core = from_tm(trimesh.load(os.path.join(HERE, "rotor_hub_core_o_relief.stl")))
    bb = core.bounding_box()
    core = core.translate([-(bb[0] + bb[3]) / 2, -(bb[1] + bb[4]) / 2, -bb[2]])
    plate = core
    keys_only = None
    for i, (dots, af) in enumerate(KEY_SIZES):
        for j in range(5):
            x = -36.0 + 18.0 * j
            y = 33.0 if i == 0 else -33.0
            if i == 2:
                x, y = 33.0, -16.0 + 8.0 * j     # third size: a column on the right
            k = key(af, dots).translate([x, y, 0])
            plate += k
            keys_only = k if keys_only is None else keys_only + k
    t = to_tm(plate)
    t.export(os.path.join(HERE, "revo_core_and_keys_plate.stl"))
    print("core + keys plate: vol %.2f cm3 bbox %s parts %d" % (t.volume / 1000, np.round(t.bounds[1] - t.bounds[0], 1), len(t.split(only_watertight=False))))
    for dots, af in KEY_SIZES:
        kt = to_tm(key(af, dots))
        print("  key %.2f AF (%d dots): vol %.1f mm3, across flats check %.3f" % (af, dots, kt.volume, kt.bounds[1][1] - kt.bounds[0][1]))

    cup_t = trimesh.load(os.path.join(HERE, "revo_cup_variants", "revo_bearing_cup_v2_bore24p10.stl"))
    cup = from_tm(cup_t)
    v0 = cup.volume()
    # screw holes in the deck face (print z 0): find them from the section at z 0.5
    sec = cup_t.section(plane_origin=[0, 0, 0.5], plane_normal=[0, 0, 1])
    holes = []
    for e in sec.discrete:
        c = e[:, :2].mean(0)
        d = 2 * np.linalg.norm(e[:, :2] - c, axis=1).mean()
        if 3.5 < d < 4.2 and 15 < np.hypot(*c) < 20:
            holes.append(c)
    assert len(holes) == 3, holes
    for (x, y) in holes:
        cup -= cyl(3.25, -1.0, 1.0, x, y)
    ct = to_tm(cup)
    ct.export(os.path.join(HERE, "revo_bearing_cup_v2_b24p10_relief.stl"))
    print("cup relief: holes at r %s, removed %.1f mm3, watertight %s" % ([round(float(np.hypot(*h)), 2) for h in holes], v0 - cup.volume(), ct.is_watertight))
