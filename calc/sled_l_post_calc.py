"""Sled rev l (2026-11-10): why a rev j card-guide post snapped, and what the beefed post buys, per material.

Sections are cut from the exported print-orientation STLs (plate top at print z 2.4; post tops at z 50.4) and clipped to the post's own
footprint (the rev l web to the cradle corner is ignored: conservative for loads across the board, irrelevant for loads along it).
Load case: a side push F at the post top (L = 48 mm from the plate top). Cantilever root stress sigma = Kt * F * L * c / I.
  Kt (bending, shoulder fillet, Peterson-type charts): rev j square root, FDM inside corner r ~0.3 mm on a 6 mm post (r/d 0.05) -> ~2.3;
  rev l R2.5 fillet on a 6 mm post (r/d 0.42) -> ~1.2.  Both are ASSUMED round numbers, good to +-20 %.
Material (between-layer, Z, the direction a post bends across): Polymaker Fiberon PET-CF17 TDS v1.0 (annealed specimens): 27.9 MPa,
0.8 % elongation, Charpy unnotched 3.1 kJ/m2; Bambu PETG HF TDS: 23 +-4 MPa, 5.1 % elongation, impact 10.6 kJ/m2.
  F_break = sigma_Z * I / (Kt * L * c)            (a steady push)
  d_break = (eps_Z / Kt) * L^2 / (3 c)            (a knock: tip deflection at which the root fibre reaches the break strain)
Run: py -X utf8 calc/sled_l_post_calc.py
"""
import numpy as np, trimesh
from shapely.geometry import box as sbox
from shapely.ops import unary_union

CAD = __file__.replace("\\", "/").rsplit("/calc/", 1)[0] + "/cad/"
L = 48.0
MAT = {"PET-CF17": (27.9, 0.008), "PETG": (23.0, 0.051)}


def section(path, z, xr, yr):
    m = trimesh.load(CAD + path)
    s = m.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    pl, _ = s.to_planar(to_2D=np.eye(4))
    poly = unary_union(list(pl.polygons_full)).intersection(sbox(xr[0], yr[0], xr[1], yr[1]))
    return poly


def props(poly, n=400):
    """Area, centroid, Ix (about the x axis through the centroid: load along y), Iy, c_y, c_x, by rasterising."""
    x0, y0, x1, y1 = poly.bounds
    xs = np.linspace(x0, x1, n)
    ys = np.linspace(y0, y1, n)
    dx, dy = xs[1] - xs[0], ys[1] - ys[0]
    from shapely import contains_xy
    X, Y = np.meshgrid(xs, ys)
    inside = contains_xy(poly, X, Y)
    A = inside.sum() * dx * dy
    cx, cy = X[inside].mean(), Y[inside].mean()
    Ix = ((Y[inside] - cy) ** 2).sum() * dx * dy
    Iy = ((X[inside] - cx) ** 2).sum() * dx * dy
    return A, Ix, Iy, max(y1 - cy, cy - y0), max(x1 - cx, cx - x0)


def main():
    cases = [  # (label, stl, z, x range, y range, Kt)
        ("rev j root (6 x 6, square corner)", "rotor_sled_j.stl", 2.5, (-41, -34), (-23, -15), 2.3),
        ("rev j U-section above the slot floor", "rotor_sled_j.stl", 6.0, (-41, -34), (-23, -15), 1.0),
        ("rev l below the slot floor (6 x 12 rounded)", "rotor_sled_l.stl", 4.8, (-41, -34), (-25.01, -12.99), 1.2),
        ("rev l slotted section (cheeks 4.9)", "rotor_sled_l.stl", 6.0, (-41, -34), (-25.01, -12.99), 1.0),
    ]
    print("%-42s %6s %8s %8s | %s" % ("section (-x post)", "A mm2", "Ix mm4", "Iy mm4", "F_break N across / along the board ; tip deflection at break mm across / along"))
    for label, stl, z, xr, yr, kt in cases:
        A, Ix, Iy, cy, cx = props(section(stl, z, xr, yr))
        L_here = L - (z - 2.4)
        parts = []
        for mname, (sig, eps) in MAT.items():
            fy = sig * Ix / (kt * L_here * cy)
            fx = sig * Iy / (kt * L_here * cx)
            dy_ = (eps / kt) * L_here ** 2 / (3 * cy)
            dx_ = (eps / kt) * L_here ** 2 / (3 * cx)
            parts.append("%s %5.1f / %5.1f ; %5.2f / %5.2f" % (mname, fy, fx, dy_, dx_))
        print("%-42s %6.1f %8.0f %8.0f | %s" % (label, A, Ix, Iy, "  |  ".join(parts)))


if __name__ == "__main__":
    main()
