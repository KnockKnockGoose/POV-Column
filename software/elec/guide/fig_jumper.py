"""Jumper ribbon figure for the wiring guide: (A) peeling and cutting the 22 (+2) ribbons from the 10-wire rainbow IDC cable,
(B) the half turn between an upright and an inverted strip (pad order mirrored), (C) the tube session for the second end in
four steps (pull 27 mm out, solder pads-up on a card over the neighbour, push back and lay in, fold the loop and tape),
(D) where the 27 mm comes from (2 x 10 mm + pi x 2.3 mm fold).

  py software/elec/guide/fig_jumper.py      -> docs/img/guide_jumper.svg/.png
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import matplotlib.pyplot as plt                       # noqa: E402
from matplotlib.patches import Arc, Rectangle         # noqa: E402

from guide_common import WC, dim, save, stamp, wire   # noqa: E402

RAINBOW = ["brown", "red", "orange", "yellow", "green", "blue", "violet", "grey", "white", "black"]
RIB = ["red", "orange", "yellow", "green"]


def panel_a(ax):
    ax.set_xlim(-5, 125)
    ax.set_ylim(-30, 34)
    ax.axis("off")
    ax.text(-4, 33, "A.  Ribbon prep: 22 jumpers + 2 rig leads (T-IN, PROBE) of red / orange / yellow / green", fontsize=9, fontweight="bold", va="top")
    # the 10-wire cable, peeled
    for k, c in enumerate(RAINBOW):
        y = 22 - k * 1.27
        dy = 0.0
        if c == "brown":
            dy = 2.2
        elif k >= 5:
            dy = -2.2
        pts = [(0, y), (18, y), (26, y + dy), (60, y + dy)]
        if k < 5 or True:
            wire(ax, pts if c != "brown" and k < 5 else pts, c, lw=1.6, z=5)
    ax.text(61, 24.4, "brown: peel off first (waste)", fontsize=6, va="center")
    ax.text(61, 19.4, "red-orange-yellow-green: peel as ONE 4-wire strip, 2.2 m long", fontsize=6.4, va="center", fontweight="bold")
    ax.text(61, 12.6, "blue ... black: keep for later (test leads)", fontsize=6, va="center")
    ax.text(0, 25.4, "10-wire rainbow IDC ribbon, 28 AWG, 1.27 mm pitch", fontsize=6, va="bottom", color="#333")
    # one jumper, 80 mm, ends split 12 mm, stripped 2.5 mm
    y0 = -6.0
    x0, x1 = 15.0, 95.0
    for k, c in enumerate(RIB):
        yc = y0 + (1.5 - k) * 1.27
        ys = y0 + (1.5 - k) * 2.5
        wire(ax, [(x0 + 2.5, ys), (x0 + 8, ys), (x0 + 12, yc), (x1 - 12, yc), (x1 - 8, ys), (x1 - 2.5, ys)], c, lw=1.6, z=5)
        for xa, xb in ((x0, x0 + 2.5), (x1 - 2.5, x1)):
            ax.plot([xa, xb], [ys, ys], color=WC["tinned"], lw=2.0, solid_capstyle="butt", zorder=6)
    dim(ax, (x0, y0 - 9.0), (x1, y0 - 9.0), "cut 80 mm (all 22, guide decision)", off=(0, 0), fs=6.4)
    dim(ax, (x0, y0 + 7.0), (x0 + 12, y0 + 7.0), "split 12", off=(0, 1.5), fs=5.6)
    dim(ax, (x1 - 12, y0 + 7.0), (x1, y0 + 7.0), "split 12", off=(0, 1.5), fs=5.6)
    dim(ax, (x0, y0 - 4.6), (x0 + 2.5, y0 - 4.6), "2.5", off=(0, -1.6), fs=5.6)
    dim(ax, (x1 - 2.5, y0 - 4.6), (x1, y0 - 4.6), "2.5", off=(0, -1.6), fs=5.6)
    ax.text(x0 - 1.0, y0, "FIRST end\n(bench, now)", fontsize=6.2, ha="right", va="center", fontweight="bold", color="#1d3557")
    ax.text(x1 + 1.0, y0, "SECOND end\n(tube, later:\nleave it tinned,\nloose)", fontsize=6.2, ha="left", va="center", fontweight="bold", color="#7b2cbf")
    ax.text(55, -23, "Split the four wires 12 mm at each end (nick the web with a blade, pull apart), strip 2.5 mm (iron-melt or blade:\n"
            "28 AWG is below the KNIPEX / haisstronica range), twist, flux, tin.  1 ribbon = 4 wire ends x 2 = 8 strips + tins.",
            fontsize=6.0, ha="center", va="top", color="#333")


def panel_b(ax):
    ax.set_xlim(-2, 62)
    ax.set_ylim(-14, 34)
    ax.axis("off")
    ax.text(-1, 33, "B.  The half turn (top end shown, seen from OUTSIDE)", fontsize=9, fontweight="bold", va="top")
    ax.text(-1, 30.2, "Measured pad order (#29): upright strip s reads GND | CO | DO | 5V; the inverted strip s+1 reads 5V | DI | CI | GND from the same side.\n"
            "So the ribbon turns over once between the slots (red 5V, orange D, yellow C, green GND). Solder by the PRINTED LABEL, never by position.", fontsize=6.0, va="top")
    for sx, labels, name, arrow_up in ((8, ["GND", "CO", "DO", "5V"], "strip s (even, upright)\ntop = OUT", True),
                                       (40, ["5V", "DI", "CI", "GND"], "strip s+1 (odd, inverted)\ntop = IN", False)):
        ax.add_patch(Rectangle((sx, -12), 12, 26, fc="#2b2b2b", ec="#000", lw=0.8))
        ax.annotate("", xy=(sx + 6, 4 if arrow_up else -6), xytext=(sx + 6, -6 if arrow_up else 4),
                    arrowprops=dict(arrowstyle="-|>", color="#e09f3e", lw=2.2, mutation_scale=14))
        ax.text(sx + 6, -13.2, name, fontsize=6.2, ha="center", va="top")
        for k, t in enumerate(labels):
            px = sx + 1.5 + k * 3.0
            ax.add_patch(Rectangle((px - 0.8, 11.0), 1.6, 2.5, fc="#c9a227", ec="#8a6d00", lw=0.5, zorder=4))
            ax.text(px, 9.8, t, fontsize=5.4, ha="center", va="top", color="white", fontweight="bold", zorder=5)
    net_of = {"5V": "red", "CO": "yellow", "DO": "orange", "GND": "green", "CI": "yellow", "DI": "orange"}
    left = ["GND", "CO", "DO", "5V"]          # measured order, docs/measurements.md #29
    right = ["5V", "DI", "CI", "GND"]
    for k, t in enumerate(left):
        c = net_of[t]
        xa = 8 + 1.5 + k * 3.0
        j = [net_of[r] for r in right].index(c)
        xb = 40 + 1.5 + j * 3.0
        ymid = 20 + k * 1.3
        pts = [(xa, 12.5), (xa, 16), (24, ymid), (30, 20 + (3 - k) * 1.3), (36, 20 + j * 1.3) if False else (36, 20 + (3 - k) * 1.3), (xb, 16), (xb, 12.5)]
        wire(ax, pts, c, lw=1.8, z=6)
    ax.text(27, 26.5, "half turn", fontsize=6.4, ha="center", fontweight="bold", color="#b00")
    ax.text(27, -2, "inside the wall\n(drawn pulled out)", fontsize=5.6, ha="center", color="#555")


def panel_c(ax):
    ax.set_xlim(0, 200)
    ax.set_ylim(-1, 45)
    ax.axis("off")
    ax.text(1, 44.5, "C.  Tube session, second end of jumper s -> s+1 (strip s is already in its rails; tube off the hub)", fontsize=9, fontweight="bold", va="top")
    titles = ["1  Pull 27 mm out", "2  Solder pads-up", "3  Push back, lay in", "4  Fold the loop, tape"]
    texts = ["Reach in from the open end, push the ribbon's\nfree end out through strip s+1's EMPTY slot,\npull it out until 27 mm stands outside.",
             "Card or silicone mat over the mounted neighbour\n(QA m-f). Strip s+1 FACE DOWN on it, its end at\nthe slot; solder 4 pads by LABEL, CA, inspect.",
             "Light the chain (phase-0 '5' or '4'). Lift the\nstrip, feed the slack back through the slot, lay it\ninto its rails cut end first onto the end-stop.",
             "Inside: lay the loop flat UP the wall (bottom end)\nor DOWN the wall (top end); one tape patch\n19 x 35 mm over the slot and the loop."]
    for i in range(4):
        x0 = 2 + i * 50
        ax.add_patch(Rectangle((x0, 0), 46, 40, fc="#f7f7f7", ec="#bbb", lw=0.6))
        ax.text(x0 + 1.2, 38.8, titles[i], fontsize=7.6, fontweight="bold", va="top")
        ax.text(x0 + 1.2, 4.6, texts[i], fontsize=5.3, va="bottom", color="#222")
        # wall with a slot (outside view)
        if i in (0, 1, 2):
            ax.add_patch(Rectangle((x0 + 4, 14), 14, 20, fc="#4a4a4a", ec="#222", lw=0.5))
            ax.add_patch(Rectangle((x0 + 6.0, 18), 10, 5, fc="#111", ec="#000", lw=0.5))
            ax.text(x0 + 11, 15.0, "slot s+1", fontsize=5.0, color="white", ha="center")
        if i == 0:
            for k, c in enumerate(RIB):
                y = 21.6 - k * 0.9
                wire(ax, [(x0 + 8 + k * 2, y), (x0 + 30, y + 2), (x0 + 40, y + 6)], c, lw=1.2, z=6)
            dim(ax, (x0 + 16, 30.5), (x0 + 41, 30.5), "27 mm out", fs=5.8)
        if i == 1:
            ax.add_patch(Rectangle((x0 + 20, 12), 24, 22, fc="#d9ead3", ec="#6a9", lw=0.6))
            ax.text(x0 + 32, 32.6, "card / silicone mat", fontsize=5.0, ha="center", color="#375")
            ax.add_patch(Rectangle((x0 + 24, 15), 9, 17, fc="#2b2b2b", ec="#000", lw=0.6))
            ax.text(x0 + 28.5, 23.5, "s+1\nface\ndown", fontsize=5.0, color="white", ha="center", va="center")
            for k, c in enumerate(RIB):
                wire(ax, [(x0 + 8 + k * 2, 21.6 - k * 0.9), (x0 + 18, 30 - k * 0.5), (x0 + 25.5 + k * 2, 30.5), (x0 + 25.5 + k * 2, 28.5)], c, lw=1.2, z=6)
        if i == 2:
            ax.add_patch(Rectangle((x0 + 30, 14), 8, 24, fc="#2b2b2b", ec="#000", lw=0.6))
            ax.annotate("", xy=(x0 + 12, 20.5), xytext=(x0 + 29, 26), arrowprops=dict(arrowstyle="-|>", color="#b00", lw=1.4, mutation_scale=10))
            ax.text(x0 + 34, 13.2, "into the rails", fontsize=5.0, ha="center", va="top")
        if i == 3:
            ax.add_patch(Rectangle((x0 + 6, 10), 34, 26, fc="#4a4a4a", ec="#222", lw=0.5))
            ax.text(x0 + 23, 35.0, "inside of the wall", fontsize=5.0, color="white", ha="center", va="top")
            ax.add_patch(Rectangle((x0 + 18, 12), 10, 5, fc="#111", ec="#000", lw=0.5))
            for k, c in enumerate(RIB):
                xx = x0 + 19.2 + k * 2.4
                wire(ax, [(xx, 14.5), (xx, 27.0)], c, lw=1.2, z=6)
                wire(ax, [(xx + 0.6, 27.0), (xx + 0.6, 15.5)], c, lw=1.2, z=5)
            ax.add_patch(Rectangle((x0 + 16.5, 11.0), 13.5, 19.5, fc="#e9b44c", ec="#b8862b", lw=0.6, alpha=0.55, zorder=8))
            ax.text(x0 + 23.2, 31.0, "tape 19 x 35", fontsize=5.0, ha="center", color="white", va="bottom", zorder=9)


def panel_d(ax):
    ax.set_xlim(-14, 30)
    ax.set_ylim(-8, 26)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.text(-13.5, 25.5, "D.  Where the 27 mm comes from", fontsize=9, fontweight="bold", va="top")
    ax.add_patch(Rectangle((0, -6), 1.6, 7.0, fc="#555"))
    ax.add_patch(Rectangle((0, 6), 1.6, 16, fc="#555"))
    ax.text(0.8, 18, "wall", color="white", fontsize=5.4, ha="center", rotation=90)
    r = 2.3
    xin = -0.2
    pts = [(4.0, 3.5), (xin, 3.5), (xin - 0.6, 4.2), (xin - 0.6, 14.2)]
    wire(ax, pts, "green", lw=1.8, z=5)
    ax.add_patch(Arc((xin - 0.6 - r, 14.2), 2 * r, 2 * r, theta1=0, theta2=180, color=WC["green"], lw=1.8, zorder=5))
    wire(ax, [(xin - 0.6 - 2 * r, 14.2), (xin - 0.6 - 2 * r, 4.4), (xin - 0.6 - 2 * r - 4, 3.0), (-13, 3.0)], "green", lw=1.8, z=5)
    dim(ax, (-9.2, 4.2), (-9.2, 14.2), "10", off=(-1.0, 0), fs=5.8)
    ax.text(xin - 0.6 - r, 17.6, "fold r 2.3", fontsize=5.6, ha="center")
    ax.text(5.0, 3.5, "slot -> pads of strip s+1", fontsize=5.6, va="center")
    ax.text(-13, 1.6, "from strip s, along the wall", fontsize=5.6, va="top")
    ax.text(8.0, 16.5, "pull-out = 2 x 10 + pi x 2.3\n= 27.2 mm (CAD check row)\n\nBottom ends: loop UP the wall.\nTop ends: loop DOWN the wall.\n"
            "Loop at strip s+1, except\n5-6 and 17-18: loop at 5 / 17.", fontsize=6.0, va="top")


def main():
    fig = plt.figure(figsize=(15.5, 12.0))
    gs = fig.add_gridspec(1, 2, top=0.98, bottom=0.52, left=0.02, right=0.99, width_ratios=[1.25, 0.95], wspace=0.04)
    panel_a(fig.add_subplot(gs[0, 0]))
    panel_b(fig.add_subplot(gs[0, 1]))
    gs2 = fig.add_gridspec(1, 2, top=0.48, bottom=0.03, left=0.02, right=0.99, width_ratios=[3.2, 1.0], wspace=0.04)
    panel_c(fig.add_subplot(gs2[0, 0]))
    ax = fig.add_subplot(gs2[0, 1])
    panel_d(ax)
    stamp(ax, 30, -8, "guide_jumper")
    save(fig, "guide_jumper")


if __name__ == "__main__":
    main()
