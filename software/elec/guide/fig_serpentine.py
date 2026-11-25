"""Serpentine map of both chains for the wiring guide: 24 strips seen from OUTSIDE, tube unwrapped (theta 0 at the left), each
strip's number, set, angle and orientation, every jumper with its BENCH end (first joint, soldered on the bench) and its LOOP end
(second joint, soldered pads-up beside the tube later), the six feeds and the two start leads with their carrier terminals, and
the mounting order (6 before 5, 18 before 17).

  py software/elec/guide/fig_serpentine.py      -> docs/img/guide_serpentine_map.svg/.png
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import matplotlib.pyplot as plt                                     # noqa: E402
from matplotlib.patches import Circle, FancyBboxPatch, Polygon, Rectangle   # noqa: E402

from guide_common import (BENCH_AT, FEED_J, JUMPERS, LOOP_AT, MOUNT_ORDER, SET_COL, START_J, WC,   # noqa: E402
                          save, set_letter, stamp, upright)

DX = 1.0          # strip spacing
H = 9.0           # drawn strip length (schematic)
BW = 0.40         # drawn strip width


def strip_x(s):
    return s * DX + (0.6 if s >= 12 else 0.0)


def main():
    fig, ax = plt.subplots(figsize=(17.5, 8.6))
    ax.set_xlim(-2.2, 24.9)
    ax.set_ylim(-9.0, H + 4.6)
    ax.axis("off")
    ax.set_aspect("auto")

    ax.text(-1.5, H + 4.3, "Both chains, seen from OUTSIDE the tube, unwrapped (theta 0 at the left, +15 deg per strip). "
            "Even strips upright (arrow UP, IN at the bottom); odd strips inverted (arrow DOWN, IN at the top).",
            fontsize=9.2, fontweight="bold", va="top")
    ax.text(-1.5, H + 3.65, "Every jumper joins strip s OUT to strip s+1 IN at the SAME end of the tube.  "
            "B = first end, soldered on the BENCH now.  L = second end, soldered pads-up beside the tube later (27 mm pulled out, "
            "pushed back as a loop).  Not to scale.", fontsize=7.6, va="top", color="#333")

    for ch, (s0, s1, jt, bus, spi) in enumerate(((0, 11, "J3", "bus A", "VSPI 23 / 18"), (12, 23, "J4", "bus B", "HSPI 13 / 14"))):
        x0, x1 = strip_x(s0) - 0.45, strip_x(s1) + 0.45
        ax.plot([x0, x0, x1, x1], [H + 2.35, H + 2.6, H + 2.6, H + 2.35], color="#444", lw=0.9)
        ax.text((x0 + x1) / 2, H + 2.75, "chain %d: strips %d-%d, start lead %s, feeds on %s, %s" % (ch, s0, s1, jt, bus, spi),
                ha="center", va="bottom", fontsize=8.0, fontweight="bold")

    for s in range(24):
        x = strip_x(s)
        st = set_letter(s)
        col = SET_COL[st]
        ax.add_patch(Rectangle((x - BW / 2, 0), BW, H, fc="#fafafa", ec=col, lw=1.4, zorder=3))
        up = upright(s)
        y_a, y_b = (2.4, 6.6) if up else (6.6, 2.4)
        ax.annotate("", xy=(x, y_b), xytext=(x, y_a), arrowprops=dict(arrowstyle="-|>", color="#e09f3e", lw=2.0, mutation_scale=12), zorder=4)
        ax.text(x, H / 2, "%d%s" % (s, st), rotation=90, ha="center", va="center", fontsize=9.5, fontweight="bold", color=col, zorder=5,
                bbox=dict(fc="#fafafa", ec="none", pad=0.5))
        ax.text(x, -0.25 if True else 0, "", fontsize=1)
        ax.text(x, H + 0.15, "IN" if not up else "OUT", ha="center", va="bottom", fontsize=5.6, color="#555", zorder=5)
        ax.text(x, -0.15, "IN" if up else "OUT", ha="center", va="top", fontsize=5.6, color="#555", zorder=5)
        ax.text(x, -3.25, "%d°" % (15 * s), ha="center", va="center", fontsize=6.0, color="#555")

    # jumpers
    for a, b, end in JUMPERS:
        xa, xb = strip_x(a), strip_x(b)
        if end == "top":
            y0, y1 = H + 0.62, H + 1.75
        else:
            y0, y1 = -0.62, -1.75
        for k, (net, c) in enumerate((("5V", "red"), ("D", "orange"), ("C", "yellow"), ("GND", "green"))):
            off = (k - 1.5) * 0.055
            yy = y1 + (off if end == "top" else -off)
            ax.plot([xa, xa, xb, xb], [y0, yy, yy, y0], color=WC[c], lw=1.3, zorder=2, solid_joinstyle="round")
        bench, loop = BENCH_AT[(a, b)], LOOP_AT[(a, b)]
        for s_, kind in ((bench, "B"), (loop, "L")):
            xs = strip_x(s_)
            yy = y0 - 0.02 if end == "top" else y0 + 0.02
            if kind == "B":
                ax.add_patch(Rectangle((xs - 0.17, yy - 0.17), 0.34, 0.34, fc="#1d3557", ec="none", zorder=6))
                ax.text(xs, yy, "B", color="white", fontsize=5.6, ha="center", va="center", fontweight="bold", zorder=7)
            else:
                ax.add_patch(Circle((xs, yy), 0.19, fc="white", ec="#7b2cbf", lw=1.3, zorder=6))
                ax.text(xs, yy, "L", color="#7b2cbf", fontsize=5.6, ha="center", va="center", fontweight="bold", zorder=7)
        lab_y = y1 + (0.32 if end == "top" else -0.32)
        hot = (a, b) in ((5, 6), (17, 18))
        ax.text((xa + xb) / 2, lab_y, "%d-%d" % (a, b), ha="center", va="center", fontsize=6.0, zorder=7,
                color="#b00" if hot else "#222", fontweight="bold" if hot else "normal")

    # strips 11 and 23: bottom OUT open
    for s in (11, 23):
        x = strip_x(s)
        ax.text(x, -0.95, "open\n(chain end)", ha="center", va="top", fontsize=5.0, color="#888")

    # feeds and start leads
    for s, j in FEED_J.items():
        x = strip_x(s)
        ax.plot([x - 0.06, x - 0.06], [-0.05, -2.55], color=WC["red"], lw=1.6, zorder=2)
        ax.plot([x + 0.06, x + 0.06], [-0.05, -2.55], color=WC["black"], lw=1.6, zorder=2)
        ax.add_patch(Circle((x - 0.06, -0.05), 0.07, fc=WC["red"], ec="none", zorder=6))
        FancyBox(ax, x, -2.75, "%s\nfeed %d" % (j, s), "#ffc9c9" if s < 12 else "#ffe8a3")
    for s, j in START_J.items():
        x = strip_x(s)
        for k, c in enumerate(("red", "black", "black", "black")):
            ax.plot([x - 0.12 + 0.08 * k] * 2, [-0.05, -2.55], color=WC[c], lw=1.4, zorder=2)
        FancyBox(ax, x, -2.75, "%s\nstart" % j, "#8ecae6")

    # mounting order
    ax.text(-2.15, -4.25, "mount order\n(tube session)", fontsize=6.4, va="center", fontweight="bold")
    for pos, s in enumerate(MOUNT_ORDER):
        x = strip_x(s)
        hot = s in (5, 6, 17, 18)
        ax.add_patch(Circle((x, -4.25), 0.3, fc="#fde68a" if hot else "#eef2f7", ec="#b00" if hot else "#557", lw=1.2 if hot else 0.7, zorder=5))
        ax.text(x, -4.25, str(pos % 12 + 1), ha="center", va="center", fontsize=6.6, fontweight="bold", zorder=6)
    for a, b in ((5, 6), (17, 18)):
        xa, xb = strip_x(a), strip_x(b)
        ax.annotate("", xy=(xa + 0.05, -4.85), xytext=(xb - 0.05, -4.85), arrowprops=dict(arrowstyle="-|>", color="#b00", lw=1.0, mutation_scale=8))
        ax.text((xa + xb) / 2, -5.15, "%d goes on\nbefore %d" % (b, a), ha="center", va="top", fontsize=5.6, color="#b00")

    # bench-work summary per strip (what is soldered on the bench, and what waits for the tube)
    ax.text(-2.15, -6.55, "bench joints\n(top / bottom)", fontsize=6.4, va="center", fontweight="bold")
    for s in range(24):
        x = strip_x(s)
        top, bot = [], []
        for a, b, end in JUMPERS:
            if s in (a, b):
                kind = "B" if BENCH_AT[(a, b)] == s else "L"
                (top if end == "top" else bot).append(kind)
        if s in FEED_J:
            bot.append("F")
        if s in START_J:
            bot.append("S")
        def fmt(lst):
            return "".join(sorted(lst, key="SBFL".index)) if lst else "-"
        n_bench = sum(1 for t in top + bot if t in "BFS")
        ax.text(x, -6.3, fmt(top), ha="center", va="center", fontsize=6.4, fontweight="bold", color="#1d3557")
        ax.text(x, -6.85, fmt(bot), ha="center", va="center", fontsize=6.4, fontweight="bold", color="#1d3557")
        ax.add_patch(Rectangle((x - 0.42, -7.25), 0.84, 1.3, fc="#f2fbf4" if n_bench else "#fff4e6", ec="#ccc", lw=0.4, zorder=1))
    ax.text(-1.5, -7.75, "S = start lead, B = ribbon first end, F = feed pair (bench now);  L = ribbon second end (tube, later);  "
            "- = nothing.  Strips 5 and 17 carry NO bench joints;  6 and 18 carry three (B top, B + F bottom).",
            fontsize=6.6, va="center", color="#333")

    # legend
    lx = 4.0
    ly = -8.55
    ax.add_patch(Rectangle((lx - 0.17, ly - 0.17), 0.34, 0.34, fc="#1d3557"))
    ax.text(lx, ly, "B", color="white", fontsize=5.6, ha="center", va="center", fontweight="bold")
    ax.text(lx + 0.3, ly, "bench end", fontsize=6.2, va="center")
    ax.add_patch(Circle((lx + 1.9, ly), 0.19, fc="white", ec="#7b2cbf", lw=1.3))
    ax.text(lx + 1.9, ly, "L", color="#7b2cbf", fontsize=5.6, ha="center", va="center", fontweight="bold")
    ax.text(lx + 2.2, ly, "loop end", fontsize=6.2, va="center")
    for k, (t, c) in enumerate((("5V", "red"), ("DATA", "orange"), ("CLK", "yellow"), ("GND", "green"))):
        ax.plot([lx + 3.5 + k * 0.95, lx + 3.85 + k * 0.95], [ly, ly], color=WC[c], lw=2.2)
        ax.text(lx + 3.9 + k * 0.95, ly, t, fontsize=5.8, va="center")
    for k, (st, c) in enumerate(SET_COL.items()):
        ax.add_patch(Rectangle((lx - 3.2 + k * 0.95, ly - 0.15), 0.25, 0.3, fc="#fafafa", ec=c, lw=1.4))
        ax.text(lx - 2.9 + k * 0.95, ly, "set " + st, fontsize=5.8, va="center", color=c)
    stamp(ax, 24.9, -9.0, "guide_serpentine_map")
    save(fig, "guide_serpentine_map", dpi=190)


def FancyBox(ax, x, y, text, fc):
    ax.add_patch(FancyBboxPatch((x - 0.38, y - 0.62), 0.76, 0.62, boxstyle="round,pad=0,rounding_size=0.08", fc=fc, ec="#135", lw=0.7, zorder=5))
    ax.text(x, y - 0.31, text, ha="center", va="center", fontsize=5.6, fontweight="bold", zorder=6)


if __name__ == "__main__":
    main()
