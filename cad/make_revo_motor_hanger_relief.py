# Rev o motor hanger with relief pockets for the deck's proud heat-set insert tips (Brian, bench 2026-11-21: the 4 M3 x 4 deck inserts stand
# ~2 mm proud of the deck underside, so the hanger could not seat flat and the gearmotor + 20T were cocked).
# Mesh CSG on cad/revm_motor_hanger.stl (rev m.2 hanger, print orientation: gearbox face z 0 on the bed, deck face z 6 on top, design y = y + 38).
# Usage (repo root): py cad/make_revo_motor_hanger_relief.py cad/revm_motor_hanger.stl cad/revo_motor_hanger_relief.stl
# Pocket per deck screw (slots d3.4 at (+-21, 18.5) / (+-21, -20), +-2 along y for belt tension):
#   d6.5 obround swept over the slot's +-2 travel (insert d4.2 knurl + melted collar ~d5.5 -> 0.5 mm clearance at any slot position),
#   2.5 deep (z 3.5..6: floor 3.5 under the M3 x 10 washer), clipped to keep >= 1.0 mm wall to the hanger outline, 0.5 x 45 deg mouth chamfer.
#   Near the outline the clip limits travel: inner row (18.5) insert collar clears for -2..+1.75 mm, outer row (-20) for -0.25..+2 mm
#   (belt tension moves the hanger away from the axis, i.e. the inserts toward +y in the hanger, so the tensioned side is the free one).
import sys, numpy as np, trimesh, manifold3d as mf
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

src, dst = sys.argv[1:3]
R, T, DEPTH, WALL, CH, TOP = 6.5 / 2, 2.0, 2.5, 1.0, 0.5, 6.0
SCREWS = [(-21.0, 18.5), (21.0, 18.5), (-21.0, -20.0), (21.0, -20.0)]


def to_mf(m):
    return mf.Manifold(mf.Mesh(vert_properties=np.asarray(m.vertices, np.float32), tri_verts=np.asarray(m.faces, np.uint32)))


def to_tm(M):
    g = M.to_mesh()
    return trimesh.Trimesh(g.vert_properties[:, :3], g.tri_verts, process=True)


def outline(m, z):
    s = m.section([0, 0, 1], [0, 0, z])
    p2, _ = s.to_2D(to_2D=np.eye(4)) if hasattr(s, "to_2D") else s.to_planar(to_2D=np.eye(4))
    return p2.polygons_full


def slab(poly, z0, z1):
    b = trimesh.creation.extrude_polygon(poly, z1 - z0)
    b.apply_translation([0, 0, z0])
    return to_mf(b)


hanger = trimesh.load(src)
assert np.allclose(hanger.bounds, [[-26, -24, 0], [26, 24, 6]], atol=1e-3), hanger.bounds
H = to_mf(hanger)
outer = Polygon(outline(hanger, 5.0)[0].exterior)          # rounded 52 x 48 outline (no holes)
keep_in = outer.buffer(-WALL, join_style=1)
cut = None
for (x, y) in SCREWS:
    ob = unary_union([Point(x, y - T).buffer(R, 256), Point(x, y + T).buffer(R, 256)]).convex_hull
    body = ob.intersection(keep_in)
    parts = [slab(body, TOP - DEPTH, TOP - CH + 0.001)]
    n = 5                                                  # 45 deg chamfer as 0.1 mm steps (finer than the 0.2 layers)
    for i in range(n):
        d = CH * (i + 0.5) / n
        lay = ob.buffer(d, 256).intersection(outer.buffer(-(WALL - d), join_style=1))
        parts.append(slab(lay, TOP - CH + CH * i / n, TOP - CH + CH * (i + 1) / n + (0.5 if i == n - 1 else 0.001)))
    P = parts[0]
    for q in parts[1:]:
        P = P + q
    cut = P if cut is None else cut + P
N = H - cut
out = to_tm(N)
print("old vol %.2f  new vol %.2f  (-%.2f mm3)  genus %d  watertight %s  bounds %s" % (
    hanger.volume, out.volume, hanger.volume - out.volume, N.genus(), out.is_watertight, out.bounds.round(3).tolist()))
# checks: below the pocket floor nothing changed; in the pocket zone min wall to the outline; counterbores / boss / slots intact
for z in (1.0, 3.0, 3.4):
    a0 = sum(p.area for p in outline(hanger, z)); a1 = sum(p.area for p in outline(out, z))
    print("z %.1f section area old %.2f new %.2f (diff %.3f)" % (z, a0, a1, a1 - a0))
# (the hole at each deck screw is pocket + the original slot; the outer-row slot ends already sit 0.30 mm from the corner arc in rev m.2, unchanged)
for z in (4.75, 5.9):
    old_holes = unary_union([Polygon(h) for p in outline(hanger, z) for h in p.interiors])
    new_holes = [Polygon(h) for p in outline(out, z) for h in p.interiors]
    print("z %.2f:" % z)
    for h in new_holes:
        c, b = h.centroid, h.bounds
        pk = h.difference(old_holes)
        w = pk.exterior.distance(outer.exterior) if pk.geom_type == "Polygon" and not pk.is_empty else (
            min(g.exterior.distance(outer.exterior) for g in pk.geoms) if not pk.is_empty else float("nan"))
        print("   hole c=(%6.2f,%6.2f) %5.2f x %5.2f   new material removed %6.2f mm2, its wall to the outline %.2f" % (
            c.x, c.y, b[2] - b[0], b[3] - b[1], pk.area, w))
out.export(dst)
print("wrote", dst)
