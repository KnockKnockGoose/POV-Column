# Rev o rotor pin-centring jig + insert-relief reprints of the hub core and the bottom-cap plate (2026-11-21).
# Mesh CSG with manifold3d; the Fusion document is not touched.
#
# What carries the drive pins (Fusion v17 / povlib rev f + rev k + rev n; checked on the STLs below):
#   * HUB CORE (PET-CF, cad/rotor_hub_core.stl): d45 x 8 body on the bottom-cap plate's TOP face, d28.0 spigot (z -2..0) in the plate's
#     d28.4 hole (0.20 radial play as drawn), held by 4 x M3 x 8 COUNTERSUNK screws from below the plate (r 18, 45 + 90k deg) into
#     4 x M3 x 6 heat-set inserts in d4.0 x 7 holes from the core's bottom face. The 4 pins (now M3 threaded rod) pass through the
#     core floor's d3.4 holes at r 8 (45 + 90k deg, same angles as the screws), through the nut plate (d22.2 in the core's d22.4
#     pocket, d3.4 holes) into captive nuts. Rod ~d2.9 in d3.4: 0.25 radial play per hole as drawn.
#   * The core does NOT touch the rotor ring: the ring's bore is d94. The ring is located on the PLATE by 4 hex keys (5.85 AF in
#     6.0 AF pockets, r 72, 45 + 90k) and clamped by the 4 tie rods (r 60, d3.4 holes, 0 / 90 / 180 / 270).
#   * The countersunk heads sit in 90 deg cones in the 2 mm plate, so tightening them pulls the core back to where the countersinks
#     put it: the spigot's 0.2 play is NOT free play once the screws are tight. What the jig can move is the rods (0.25 each).
#
# JIG (model coordinates, rotor upright, z = 0 at the plate top; the jig sits under the spigot end face z -19, i.e. on top of the
# rotor when the rotor is upside down on the bench; print orientation = model orientation, web on the bed):
#   * web z -21.4..-19.0 (2.4 mm), r 5.5..49.6: its top face rests on the spigot's end face (r 47..49). 8 hex-key holes d7 at r 18
#     (every 45 deg) reach the 4 countersunk core screws whichever fork set is used; 8 windows r 23..42.
#   * 6 flex fingers (as jig v3) rise into the ring's d94 bore: 0.9 thick, root z -19, bump drawn r 47.15 at z -9.0..-8.4, 28 deg
#     lead-in to the tip z -7. Ring (PET-CF, ~0.67 % small) bore ~d93.37, jig (PETG-CF ~0.45 %) bump ~d93.88: ~0.25 radial preload
#     (range ~0.1-0.33); strain <= 0.41 %. Equal fingers -> the jig centres on the bore (elastic averaging), not on its own shrink.
#   * crown r 5.5..13.0, z -19..-8.5, 8 radial slots open toward the centre (pins enter from the tip end), floor z -17 (pin tips
#     at ~ -14 for 12 mm of stick-out: 3 mm margin): SET 1 (w 3.05, snug) at 45 + 90k, SET 2 (w 3.20, sliding) at 0 + 90k.
#     Turn the jig 45 deg to change set. Radial slots fix each pin's TANGENTIAL position (what the hub's radial notches see)
#     and let each pin keep its own radius. 0.5 x 45 deg lead-in on each slot. Rim marks: 1 notch = set 1 slot, 2 notches = set 2.
#   * centre r 5.5 open (XH header / pogo pins, r <= 4.7).
# CORE REPRINT: the 4 insert holes get a flat counterbore d6.5 x 1.0 at the mating face (core bottom, against the plate top): push
#   each insert flush with the counterbore floor; a collar of melted plastic or an insert up to 1.0 proud can no longer hold the
#   core off the plate. Everything else identical (hole d4.0 still ends 7.0 from the face, so a flush insert bottoms; M3 x 8 csk
#   keeps 5.0 mm in the insert).
# PLATE REPRINT: same relief d6.5 x 1.0 on the 4 sled-boss inserts (r 45; d9 bosses: 1.25 wall), the plate's own insert holes.
#   The plate's face under the core stays as is (2 mm with countersinks from below: no room for a pocket).
# Usage (repo root): py -X utf8 cad/make_revo_rotor_pin_jig.py
import math, os, numpy as np, trimesh, manifold3d as mf

HERE = os.path.dirname(os.path.abspath(__file__))
SEG = 361

Z_END = -19.0                     # spigot end face (rotor ring, model z)
WEB_T = 2.4
Z0 = Z_END - WEB_T                # -21.4: jig bed face
R_WEB_IN, R_WEB_OUT = 5.5, 49.6
KEY_R, KEY_HOLE_R = 18.0, 3.5
WIN = (23.0, 42.0, 15.0)          # r0, r1, half-angle; centred at 22.5 + 45k
FING = dict(n=6, th0=30.0, half=6.2, r_in=45.5, r_body=46.4, r_bump=47.15, z_b0=-9.0, z_b1=-8.4, z_tip=-7.0)
CROWN = dict(r_in=5.5, r_out=13.0, z_top=-8.5, z_floor=-17.0, pin_r=8.0, slot_r0=3.0, ch=0.5)
SETS = [(1, 3.05, 45.0), (2, 3.20, 0.0)]   # set id, slot width, first angle (+ 90k)
PIN_R, PIN_D, PIN_Z = 8.0, 2.90, (-14.0, -2.0)


def ccw(poly):
    a = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]))
    return poly if a > 0 else poly[::-1]


def revolve(prof):
    return mf.Manifold.revolve(mf.CrossSection([ccw(prof)]), circular_segments=SEG)


def ring(r0, r1, z0, z1):
    return revolve([(r0, z0), (r1, z0), (r1, z1), (r0, z1)])


def cyl(r, z0, z1, x=0.0, y=0.0, n=96):
    return mf.Manifold.cylinder(z1 - z0, r, r, n).translate([x, y, z0])


def box(x0, x1, y0, y1, z0, z1):
    return mf.Manifold.cube([x1 - x0, y1 - y0, z1 - z0]).translate([x0, y0, z0])


def wedge(r, th_c, half, z0, z1, n=64):
    pts = [(0.0, 0.0)] + [(r * math.cos(math.radians(th_c - half + 2 * half * k / n)),
                           r * math.sin(math.radians(th_c - half + 2 * half * k / n))) for k in range(n + 1)]
    return mf.Manifold.extrude(mf.CrossSection([ccw(pts)]), z1 - z0).translate([0, 0, z0])


def sector(r0, r1, th_c, half, z0, z1):
    return wedge(r1, th_c, half, z0, z1) - cyl(r0, z0 - 1, z1 + 1)


def stadium(w, r0, r1, z0, z1, th):
    """Radial slot of width w from radius r0 to r1 (centres of the end arcs), at angle th, z0..z1."""
    cs = mf.CrossSection.circle(w / 2, 48).translate([r0, 0]) + mf.CrossSection.circle(w / 2, 48).translate([r1, 0])
    cs = cs.hull()
    return mf.Manifold.extrude(cs, z1 - z0).translate([0, 0, z0]).rotate([0, 0, th])


def jig():
    web = ring(R_WEB_IN, R_WEB_OUT, Z0, Z_END)
    for k in range(8):
        th = math.radians(45.0 * k)
        web -= cyl(KEY_HOLE_R, Z0 - 1, Z_END + 1, KEY_R * math.cos(th), KEY_R * math.sin(th))
        web -= sector(WIN[0], WIN[1], 22.5 + 45.0 * k, WIN[2], Z0 - 1, Z_END + 1)
    f = FING
    prof = [(f["r_in"], Z_END - 0.3), (f["r_in"], f["z_tip"]), (f["r_body"], f["z_tip"]), (f["r_bump"], f["z_b1"]),
            (f["r_bump"], f["z_b0"]), (f["r_body"], f["z_b0"] - (f["r_bump"] - f["r_body"])), (f["r_body"], Z_END - 0.3)]
    fr = revolve(prof)
    fingers = None
    for k in range(f["n"]):
        s = fr ^ wedge(60.0, f["th0"] + 60.0 * k, f["half"], f["z_tip"] - 20, f["z_tip"] + 1)
        fingers = s if fingers is None else fingers + s
    c = CROWN
    crown = ring(c["r_in"], c["r_out"], Z_END - 0.3, c["z_top"])
    for sid, w, th0 in SETS:
        for k in range(4):
            th = th0 + 90.0 * k
            crown -= stadium(w, c["slot_r0"], c["pin_r"] + 1.0, c["z_floor"], c["z_top"] + 1, th)
            # 0.5 x 45 deg lead-in at the mouth (pins enter from the top in model coords = from above in print)
            lead = mf.Manifold.hull(stadium(w, c["slot_r0"], c["pin_r"] + 1.0, c["z_top"] - c["ch"], c["z_top"] - c["ch"] + 0.01, th) +
                                    stadium(w + 2 * c["ch"] + 0.02, c["slot_r0"], c["pin_r"] + 1.0, c["z_top"], c["z_top"] + 0.02, th))
            crown -= lead
    body = web + fingers + crown
    # rim marks: 1 notch at a set-1 slot angle (45 deg), 2 notches at a set-2 slot angle (0 deg)
    for th_c, n in ((45.0, 1), (0.0, 2)):
        for j in range(n):
            th = th_c + (j - (n - 1) / 2) * 4.0
            nb = box(R_WEB_OUT - 1.2, R_WEB_OUT + 1, -0.8, 0.8, Z0 - 1, Z_END + 1).rotate([0, 0, th])
            body -= nb
    return body


def to_tm(M):
    g = M.to_mesh()
    return trimesh.Trimesh(g.vert_properties[:, :3], g.tri_verts, process=True)


def from_tm(t):
    return mf.Manifold(mf.Mesh(vert_properties=np.asarray(t.vertices, dtype=np.float32), tri_verts=np.asarray(t.faces, dtype=np.uint32)))


def counterbores(stl, r, th0, z_face, d=6.5, depth=1.0):
    """Flat counterbores d x depth at the 4 insert holes (r, th0 + 90k) whose mouth is the print-top face at z_face."""
    t = trimesh.load(os.path.join(HERE, stl))
    M = from_tm(t)
    v0 = M.volume()
    for k in range(4):
        th = math.radians(th0 + 90.0 * k)
        M -= cyl(d / 2, z_face - depth, z_face + 0.6, r * math.cos(th), r * math.sin(th))
    return M, v0


def check_jig(J):
    """Overlap with the rotor ring (bore) and fit on the pins, in model coordinates."""
    ring_t = trimesh.load(os.path.join(HERE, "rotor_ring_n_ribs100p80.stl"))
    R = from_tm(ring_t).rotate([180.0, 0, 0]).translate([0, 0, -2.0])          # print z 0 (plate face) -> model -2, spigot end -> -19
    bb = R.bounding_box()
    ov = (J ^ R)
    print("ring z %.2f..%.2f; jig/ring overlap %.1f mm3 (only the finger bumps should overlap)" % (bb[2], bb[5], ov.volume()))
    fb = None
    for k in range(FING["n"]):
        th = FING["th0"] + 60.0 * k
        s = ring(46.95, 48.0, FING["z_b0"] - 1, FING["z_tip"]) ^ wedge(60.0, th, FING["half"] + 1, -30, 0)
        fb = s if fb is None else fb + s
    print("  overlap outside the bump zone: %.2f mm3" % (ov - fb).volume())
    for sid, w, th0 in SETS:
        pins = None
        for k in range(4):
            th = math.radians(th0 + 90.0 * k)
            p = cyl(PIN_D / 2, PIN_Z[0], PIN_Z[1], PIN_R * math.cos(th), PIN_R * math.sin(th))
            pins = p if pins is None else pins + p
        print("  set %d (w %.2f): pins d%.2f in the slots, overlap %.3f mm3; drawn play %.3f / side" % (sid, w, PIN_D, (J ^ pins).volume(), (w - PIN_D) / 2))


if __name__ == "__main__":
    J = jig()
    check_jig(J)
    P = J.translate([0, 0, -Z0])                                              # print: web on the bed
    t = to_tm(P)
    t.export(os.path.join(HERE, "revo_rotor_pin_centring_jig.stl"))
    print("jig: vol %.2f cm3 bbox %s watertight %s genus %d" % (t.volume / 1000, np.round(t.bounds[1] - t.bounds[0], 2), t.is_watertight, P.genus()))

    C, v0 = counterbores("rotor_hub_core.stl", 18.0, 45.0, 8.0)            # print z 8 = the core's bottom face (spigot above it)
    tc = to_tm(C)
    tc.export(os.path.join(HERE, "rotor_hub_core_o_relief.stl"))
    print("core: removed %.1f mm3 (4 x d6.5 x 1.0 = %.1f) watertight %s" % (v0 - C.volume(), 4 * math.pi * 3.25 ** 2 * 1.0 - 4 * math.pi * 2.0 ** 2 * 1.0, tc.is_watertight))

    Pl, v0 = counterbores("rotor_bottom_cap_f.stl", 45.0, 45.0, 8.0)         # print z 8 = the sled-boss tops
    tp = to_tm(Pl)
    tp.export(os.path.join(HERE, "rotor_bottom_cap_o_relief.stl"))
    print("plate: removed %.1f mm3 (expected %.1f) watertight %s" % (v0 - Pl.volume(), 4 * math.pi * (3.25 ** 2 - 2.0 ** 2) * 1.0, tp.is_watertight))
