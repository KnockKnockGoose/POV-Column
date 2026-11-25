"""Single-plane balancing without a phase reference: the four-run (trial-weight) method.

Spin at the working speed and read one vibration amplitude per run, always the same way (phone accelerometer on the base
at the 3.75 Hz line, or the peak-to-peak gap at the tube's top edge): A0 with no trial weight, then the SAME trial weight
at three positions (default 0, 120, 240 deg; any three distinct angles work). The script solves |u + T e^(i th)| = A for
the original unbalance u (size and angle) and the trial weight's effect T, and prints the correction: mass (in units of
the trial weight) and angle, split over the two nearest holes of the plane's hole pattern.

    py calc/balance_4run.py 1.8 2.6 1.1 2.2                        # A0 A1 A2 A3, trial at 0/120/240, rotor-ring trim flange (24 holes)
    py calc/balance_4run.py 1.8 2.6 1.1 2.2 --trial-g 0.9 --plane top
    py calc/balance_4run.py 1.8 2.6 1.1 2.2 --angles 0 135 270 --plane top

Planes: "bottom" = rotor-ring trim flange, 24 x d3.4 holes at r 88, 15 deg apart, hole 0 on the +x axis;
        "top" = top cap trim pockets, 8 x 6.0 AF at r 72, 45 deg apart.
Angles are measured in the rotor, counter-clockwise seen from above, from hole / pocket 0 (mark it with a paint pen).
Rev k, 2026-11-09 (docs/2026-11-09-rev-k-rim-bearing.md section 8).
"""
import argparse, math

import numpy as np

PLANES = {"bottom": dict(n=24, r=88.0, name="trim flange hole"), "top": dict(n=8, r=72.0, name="top-cap pocket")}


def solve(A, angles_deg):
    A0, Ai = A[0], np.array(A[1:], float)
    th = np.radians(angles_deg)
    # unknowns ux, uy, T:  |u + T e^{i th_k}|^2 = Ai^2,  |u|^2 = A0^2
    best = None
    for T0 in np.linspace(0.05, 3.0, 30) * max(A0, 1e-9):
        for a0 in np.radians(np.arange(0, 360, 15)):
            x = np.array([A0 * math.cos(a0), A0 * math.sin(a0), T0])
            for _ in range(60):                                  # Gauss-Newton
                ux, uy, T = x
                r = [ux * ux + uy * uy - A0 * A0]
                J = [[2 * ux, 2 * uy, 0.0]]
                for t, a in zip(th, Ai):
                    vx, vy = ux + T * math.cos(t), uy + T * math.sin(t)
                    r.append(vx * vx + vy * vy - a * a)
                    J.append([2 * vx, 2 * vy, 2 * (vx * math.cos(t) + vy * math.sin(t))])
                r, J = np.array(r), np.array(J)
                step, *_ = np.linalg.lstsq(J, -r, rcond=None)
                x = x + step
                if np.linalg.norm(step) < 1e-10:
                    break
            res = float(np.sum(r ** 2))
            if x[2] > 0 and (best is None or res < best[0]):
                best = (res, x.copy())
    res, (ux, uy, T) = best
    return math.hypot(ux, uy), math.degrees(math.atan2(uy, ux)) % 360.0, T, res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("A", nargs=4, type=float, help="A0 (no trial) A1 A2 A3 (trial at the three angles)")
    ap.add_argument("--angles", nargs=3, type=float, default=[0.0, 120.0, 240.0])
    ap.add_argument("--trial-g", type=float, default=1.0, help="trial weight in grams (default 1.0)")
    ap.add_argument("--plane", choices=sorted(PLANES), default="bottom")
    a = ap.parse_args()
    u, ang_u, T, res = solve(a.A, a.angles)
    pl = PLANES[a.plane]
    m_corr = a.trial_g * u / T
    ang_c = (ang_u + 180.0) % 360.0
    pitch = 360.0 / pl["n"]
    k0 = int(ang_c // pitch)
    f = (ang_c - k0 * pitch) / pitch                             # split the mass over the two neighbouring holes
    m0 = m_corr * math.sin(math.radians((1 - f) * pitch)) / math.sin(math.radians(pitch))
    m1 = m_corr * math.sin(math.radians(f * pitch)) / math.sin(math.radians(pitch))
    print("original unbalance response %.3f (A0) at %.0f deg; trial-weight response %.3f per %.2f g (fit residual %.2e)" % (u, ang_u, T, a.trial_g, res))
    print("CORRECTION: %.2f g at %.0f deg (r %.0f mm, %.0f g mm) on the %s plane" % (m_corr, ang_c, pl["r"], m_corr * pl["r"], a.plane))
    print("  = %.2f g in %s %d (%.0f deg) + %.2f g in %s %d (%.0f deg)" % (m0, pl["name"], k0 % pl["n"], k0 * pitch, m1, pl["name"], (k0 + 1) % pl["n"], (k0 + 1) * pitch))
    print("  remove the trial weight first; parts: M3 nut ~0.3 g, M3 washer ~0.1 g, M3 x 6 SHCS ~0.6 g, M3 x 10 SHCS ~0.8 g")
    if T < 0.2 * u:
        print("  note: the trial weight moved the reading by < 20 % of A0; repeat with a heavier trial for a reliable answer")


if __name__ == "__main__":
    main()
