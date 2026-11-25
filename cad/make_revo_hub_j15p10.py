# Rev o drive hub with a plain 6802 journal d15.10 (Brian's coupon stub 4, 2026-11-20), everything else = the rev n / rev o hub.
# Mesh CSG on cad/revn_drive_hub.stl (print orientation: crown on the bed, journal on top, z' = -z_model - 3.1).
# Old journal: d14.6 core + 8 crush ribs to d15.10, z' 11.6..15.2 (3.6 into the inner ring), 45 deg lead-in.
# Usage (from the repo root): py cad/make_revo_hub_j15p10.py cad/revn_drive_hub.stl cad/revo_drive_hub_j15p10.stl cad/revo_hub_and_cup_plate.stl cad/revo_cup_variants/revo_bearing_cup_v2_bore24p10.stl
# Plate: 2 hubs (y +18) + cup v2 bore 24.10 (y -22). Verified 2026-11-20: journal sections r 7.550 all round, 0 mm3 removed elsewhere, island check 0.
# New journal: union a solid annulus r 6.0..7.55 over z' 11.5..15.2 with a 0.5 x 45 deg lead-in at the free end (r 7.05 at z' 15.2),
# i.e. the coupon stub's 0.5 lead-in. r 6.0 stays inside the existing wall (bore r <= 3.9 there), so the bore / neck / cone are untouched.
import sys, numpy as np, trimesh, manifold3d as mf

src, dst, dst_plate, cup = sys.argv[1:5]
R, Z0, Z1, CH, RIN, SEG = 15.10 / 2, 11.5, 15.2, 0.5, 6.0, 512


def to_mf(m):
    return mf.Manifold(mf.Mesh(vert_properties=np.asarray(m.vertices, np.float32), tri_verts=np.asarray(m.faces, np.uint32)))


def to_tm(M):
    g = M.to_mesh()
    return trimesh.Trimesh(g.vert_properties[:, :3], g.tri_verts, process=True)


hub = trimesh.load(src)
c = hub.bounds.mean(0)
hub.apply_translation([-c[0], -c[1], 0])
H = to_mf(hub)
# journal profile (r, z) revolved: solid with a 45 deg chamfer at the top outer edge
prof = [[RIN, Z0], [R, Z0], [R, Z1 - CH], [R - CH, Z1], [RIN, Z1]]
J = mf.Manifold.revolve(mf.CrossSection([prof]), circular_segments=SEG)
# old journal minus anything above Z1 (none) ; union
N = H + J
out = to_tm(N)
print("old vol %.2f  new vol %.2f  (+%.2f mm3)  genus %d  watertight %s" % (hub.volume, out.volume, out.volume - hub.volume, N.genus(), out.is_watertight))
out.export(dst)
# plate: 2 hubs + cup v2 bore 24.10
cm = trimesh.load(cup)
cc = cm.bounds.mean(0)
cm.apply_translation([-cc[0], -cc[1], -cm.bounds[0, 2]])
parts = []
for dx in (-17.0, 17.0):
    h = out.copy(); h.apply_translation([dx, 18.0, 0]); parts.append(h)
cm.apply_translation([0, -22.0, 0]); parts.append(cm)
plate = trimesh.util.concatenate(parts)
print("plate bounds", plate.bounds.round(2).tolist(), "cup extents", cm.extents.round(2).tolist())
plate.export(dst_plate)
