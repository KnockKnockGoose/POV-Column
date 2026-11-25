# Rev o centring jig v3 (2026-11-20 evening). Mesh CSG with manifold3d; the Fusion document is not touched.
#
# Why v2 did not seat (Brian, 11-20: "fits in the lip, can't push it all the way down, certainly not over the hub"):
#   * Rev o put a 3rd 6 x 3 magnet on the riser (script 193): the stack top is now z -5.0 at theta 90, r 38..44
#     (Fusion v17, body magnet_3_asbuilt). Jig v2's disc is SOLID there (its windows are at 30 / 150 deg) and its
#     underside is z -6.6, so the jig lands on the magnet 1.6 mm short of home. Held up there, the collar
#     (bottom z -10) reaches only 0.6 mm over the tooth tips (top z -7.8): it never gets "over the hub".
#     Brian's bench: the riser sits ~180 deg from the 20T window = CAD (riser 90, motor 270). No discrepancy.
#   * Second, centring: v2's skirt is a rigid d99.7 in the 6820's d99.97 bore. Large PETG-CF / PET-CF rings print
#     0.4-0.8 % small (rotor-ring fit tests 11-18: ribs drawn 100.10 printed 99.43; test ring 100.55 = snug in 99.97),
#     so the printed skirt is ~d99.1-99.3: 0.35-0.45 mm radial play before the collar's own play. Over the 0.25 target.
#
# v3 (model coordinates, z up, exported flipped: disc top z -4.6 on the bed):
#   * Disc only where nothing stands: two 90 deg spokes (centred 0 / 180 deg); open windows 90 +-45 deg (riser, any
#     height) and 270 +-45 deg (20T pulley + motor travel, plus v2's oval), r 18..47.8. The jig is symmetric, so it
#     goes on either way round. Hex-key holes d7.8 over the cup screws (r 17.5 at 60 / 180 / 300) as before.
#   * Rim r 48.35..52, z -8.0..-4.6, rests on the 6820 inner ring's top face (z -8.0) as before.
#   * Skirt -> 6 flex fingers (60 deg pitch, 12 deg wide, 0.9 thick, root z -8 to tip z -17) with a bump drawn
#     d100.75 (printed ~d100.0-100.35 for 0.4-0.75 % shrink) and a 30 deg lead-in: the fingers preload equally,
#     so the jig centres itself in the 6820 bore whatever the print shrink (elastic averaging). Finger strain at the
#     worst-case 0.19 mm deflection: 3 t d / 2 L^2 = 0.31 %.
#   * Collar r_b..14.6 from z -12.0 (was -10.0) to -4.6: 4.2 mm on the tooth tips (d24.96 drawn), 0.8 x 45 deg lead-in
#     at its mouth, 0.5 x 45 deg elephant's-foot relief where the bore meets the bed face. Lower flange of the hub
#     (z <= -14.8) stays 2.8 below it. BELT OFF: the belt (z -14.3..-8.3, OD r 13.4) would block the collar.
#   * 3 variants, bore d25.15 / 25.30 / 25.45 (notches 1 / 2 / 3 on the rim at 0 deg + a raised digit on the 0 deg
#     spoke). Expected radial play on the printed hub: ~0.12 / 0.19 / 0.27.
# Usage (repo root): py -X utf8 cad/make_revo_jig_v3.py   -> cad/revo_centring_jig_v3_b25pXX.stl (x3) + cad/revo_centring_jig_v3.stl (plate)
import math, os, numpy as np, trimesh, manifold3d as mf

HERE = os.path.dirname(os.path.abspath(__file__))
SEG = 361
BORES = [(1, 25.15), (2, 25.30), (3, 25.45)]

ZT, ZD, ZR = -4.6, -6.6, -8.0          # disc top (bed), disc underside, rim underside (= 6820 inner ring top)
R_RIM_IN, R_RIM_OUT = 48.35, 52.0
R_COL_OUT, Z_COL_BOT = 14.6, -12.0
WIN_R = (18.0, 47.8)
FING = dict(n=6, half=6.2, r_in=48.7, r_body=49.6, r_bump=100.75 / 2, z_tip=-17.0, lead_r=49.0, z_bump0=-14.6, z_bump1=-14.2)
SCREW_PCD_R, SCREW_TH, KEY_HOLE_R = 17.5, (60.0, 180.0, 300.0), 3.9
MOTOR_Y = -30.33


def ccw(poly):
    a = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]))
    return poly if a > 0 else poly[::-1]


def revolve(prof):
    return mf.Manifold.revolve(mf.CrossSection([ccw(prof)]), circular_segments=SEG)


def ring(r0, r1, z0, z1):
    return revolve([(r0, z0), (r1, z0), (r1, z1), (r0, z1)])


def cyl(r, z0, z1, x=0.0, y=0.0):
    return mf.Manifold.cylinder(z1 - z0, r, r, 96).translate([x, y, z0])


def box(x0, x1, y0, y1, z0, z1):
    return mf.Manifold.cube([x1 - x0, y1 - y0, z1 - z0]).translate([x0, y0, z0])


def wedge(r, th_c, half, z0, z1, n=64):
    pts = [(0.0, 0.0)] + [(r * math.cos(math.radians(th_c - half + 2 * half * k / n)),
                           r * math.sin(math.radians(th_c - half + 2 * half * k / n))) for k in range(n + 1)]
    return mf.Manifold.extrude(mf.CrossSection([ccw(pts)]), z1 - z0).translate([0, 0, z0])


def sector(r0, r1, th_c, half, z0, z1):
    return wedge(r1, th_c, half, z0, z1) - cyl(r0, z0 - 1, z1 + 1)


def jig(bore_d):
    rb = bore_d / 2
    disc = ring(14.4, R_RIM_IN + 0.15, ZD, ZT)
    for th in (90.0, 270.0):                                         # riser / pulley windows, +-45 deg
        disc -= sector(WIN_R[0], WIN_R[1], th, 45.3, ZD - 1, ZT + 1)
    oval = box(-11.0, 11.0, MOTOR_Y - 2.0, MOTOR_Y + 2.0, ZD - 1, ZT + 1)   # v2's pulley window (d16 flange +-2 mm travel)
    for dy in (-2.0, 2.0):
        oval += cyl(11.0, ZD - 1, ZT + 1, 0, MOTOR_Y + dy)
    disc -= oval
    for th in SCREW_TH:                                              # hex-key access to the cup screws
        disc -= cyl(KEY_HOLE_R, ZD - 1, ZT + 1, SCREW_PCD_R * math.cos(math.radians(th)), SCREW_PCD_R * math.sin(math.radians(th)))
    rim = ring(R_RIM_IN, R_RIM_OUT, ZR, ZT) - revolve([(R_RIM_OUT - 0.4, ZT + 0.01), (R_RIM_OUT + 0.1, ZT + 0.01),
                                                        (R_RIM_OUT + 0.1, ZT - 0.5)])   # 0.4 EF chamfer, outer bed edge
    f = FING
    fprof = [(f["r_in"], ZR + 0.3), (f["r_in"], f["z_tip"]), (f["lead_r"], f["z_tip"]), (f["r_bump"], f["z_bump0"]),
             (f["r_bump"], f["z_bump1"]), (f["r_body"], f["z_bump1"] + (f["r_bump"] - f["r_body"])), (f["r_body"], ZR + 0.3)]
    fing_ring = revolve(fprof)
    fingers = None
    for k in range(f["n"]):
        s = fing_ring ^ wedge(60.0, 60.0 * k, f["half"], f["z_tip"] - 1, ZR + 1)
        fingers = s if fingers is None else fingers + s
    collar = revolve([(rb + 0.8, Z_COL_BOT), (R_COL_OUT, Z_COL_BOT), (R_COL_OUT, ZT), (rb + 0.5, ZT), (rb, ZT - 0.5),
                      (rb, Z_COL_BOT + 0.8)])
    body = disc + rim + fingers
    body -= cyl(rb + 0.3, Z_COL_BOT - 1, ZT + 1)                    # clear the bore region, then the collar defines it
    body += collar
    return body


DIGITS = {1: "bc", 2: "abged", 3: "abgcd"}


def digit(n, x0, y0, z0, h=0.6, W=5.0, H=9.0, s=1.2):
    """Raised 7-segment digit in PRINT coordinates (readable from above), lower-left corner at (x0, y0)."""
    out = None
    hh = H / 2
    for seg in DIGITS[n]:
        if seg in "adg":
            yy = {"a": H - s, "g": hh - s / 2, "d": 0.0}[seg]
            b = box(x0, x0 + W, y0 + yy, y0 + yy + s, z0, z0 + h)
        else:
            xx = x0 + (W - s if seg in "bc" else 0.0)
            yy = y0 + (hh if seg in "bf" else 0.0)
            b = box(xx, xx + s, yy, yy + hh, z0, z0 + h)
        out = b if out is None else out + b
    return out


def to_print(m, idx):
    p = m.rotate([180.0, 0.0, 0.0])                                  # (x, y, z) -> (x, -y, -z): disc top on the bed
    p = p.translate([0, 0, -p.bounding_box()[2]])
    zt = -ZD - (-ZT)                                                 # print z of the spoke's top face (model underside z -6.6) = 2.0
    p += digit(idx, 28.5, -4.5, zt - 0.01)                          # on the 0 deg spoke, r ~31
    for k in range(idx):                                             # coupon-style notches on the rim at 0 deg
        th = math.radians((k - (idx - 1) / 2) * 6.0)
        n = box(-0.8, 1.0, -0.5, 0.5, -1, 20).rotate([0, 0, math.degrees(th)]).translate([R_RIM_OUT * math.cos(th), R_RIM_OUT * math.sin(th), 0])
        p -= n
    return p


def to_tm(M):
    g = M.to_mesh()
    return trimesh.Trimesh(g.vert_properties[:, :3], g.tri_verts, process=True)


if __name__ == "__main__":
    plate = None
    for idx, d in BORES:
        P = to_print(jig(d), idx)
        t = to_tm(P)
        stem = "revo_centring_jig_v3_b%s" % ("%.2f" % d).replace(".", "p")
        t.export(os.path.join(HERE, stem + ".stl"))
        bb = t.bounds
        print("%s  %d  vol %.2f cm3  bbox %.1f x %.1f x %.2f  watertight %s  genus %d" % (stem, idx, t.volume / 1000, *(bb[1] - bb[0]), t.is_watertight, P.genus()))
        dx, dy = {1: (-55.0, 50.0), 2: (55.0, 50.0), 3: (0.0, -50.0)}[idx]   # triangle: 214 x 204 footprint (a row would be 324 wide)
        Q = P.translate([dx, dy, 0])
        plate = Q if plate is None else plate + Q
    t = to_tm(plate)
    t.export(os.path.join(HERE, "revo_centring_jig_v3.stl"))
    print("plate bbox", np.round(t.bounds[1] - t.bounds[0], 1), "vol %.2f cm3" % (t.volume / 1000))
