"""Leads figure for the wiring guide: (A) a chain-start lead (S0 / S12) with its six 26 AWG conductors, ID bands, the two
twisted signal pairs, the GND splice 30 mm before the pad and the J3 / J4 pin order; (B) the six feed pairs with their
cut lengths and terminals; (C) the hall lead from the A3144's legs to J5 (the outer two swap). Not to scale.

  py software/elec/guide/fig_leads.py   -> docs/img/guide_leads.svg / .png
QA-2 N5 applied: every conductor that ends in a screw clamp is 26 AWG, clamped bare (twisted, not tinned).
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import matplotlib.pyplot as plt                       # noqa: E402
from matplotlib.patches import Polygon, Rectangle     # noqa: E402

from guide_common import WC, band, box, dim, note, save, stamp, wire   # noqa: E402


def twist(ax, x0, x1, ya, yb, cola, colb, turns, lw=2.2, z=6):
    """Two wires twisted between x0 and x1 (drawn as two interleaved sines between ya and yb)."""
    n = 400
    xs = [x0 + (x1 - x0) * i / n for i in range(n + 1)]
    ym, amp = (ya + yb) / 2, abs(ya - yb) / 2
    for col, ph in ((cola, 0.0), (colb, math.pi)):
        ys = [ym + amp * math.cos(2 * math.pi * turns * (x - x0) / (x1 - x0) + ph) for x in xs]
        wire(ax, list(zip(xs, ys)), col, lw=lw, z=z)


def panel_start(ax):
    ax.set_xlim(-14, 128)
    ax.set_ylim(-9.5, 13)
    ax.axis("off")
    ax.text(-13, 12.6, "A.  Chain-start lead S0 (strip 0 -> J3) and S12 (strip 12 -> J4): six 26 AWG conductors", fontsize=9.5,
            fontweight="bold", va="top")
    ax.text(-13, 11.1, "Pad end on the LEFT (strip 2.5 mm, tinned), terminal end on the RIGHT (strip 5 mm, twisted, NOT tinned: "
            "bare into the clamp, QA-2 N5).  Lengths S0 / S12.", fontsize=6.6, va="top", color="#333")
    # strip end (pads)
    ax.add_patch(Rectangle((-12, -1.0), 7.5, 9.0, fc="#2b2b2b", ec="#000", lw=0.8, zorder=2))
    pads = {"5V": 6.6, "DI": 4.6, "CI": 2.6, "GND": 0.4}     # measured IN-end order GND, CI, DI, 5V (#29), read bottom-up
    for nm, y in pads.items():
        ax.add_patch(Rectangle((-6.9, y - 0.45), 1.6, 0.9, fc="#c9a227", ec="#8a6d00", lw=0.5, zorder=3))
        ax.text(-7.3, y, nm, fontsize=5.6, color="white", ha="right", va="center", zorder=4, fontweight="bold")
    ax.text(-8.2, -2.0, "strip 0 / 12\nIN end (bottom)\npads by LABEL", fontsize=5.4, ha="center", va="top")
    # J3 / J4 block on the right
    jx = 112
    ax.add_patch(Rectangle((jx, -1.6), 4.0, 10.4, fc="#2e7d32", ec="#1b5e20", lw=0.9, zorder=2))
    rows = {1: 7.6, 2: 6.0, 3: 4.4, 4: 3.0, 5: 1.6, 6: 0.0}
    pin_txt = {1: "1  5V", 2: "2  GND", 3: "3  CLK", 4: "4  GND (CLK return)", 5: "5  DATA", 6: "6  GND (DATA return)"}
    for k, y in rows.items():
        ax.add_patch(Rectangle((jx + 0.4, y - 0.45), 1.4, 0.9, fc="#c9ccd1", ec="#555", lw=0.4, zorder=3))
        ax.text(jx + 4.6, y, pin_txt[k], fontsize=5.8, va="center")
    ax.text(jx + 2.0, -2.0, "J3 / J4\n6P 2.54 mm", fontsize=5.8, ha="center", va="top", fontweight="bold")
    xs = -5.3
    # 5V (red) pin 1 -> 5V pad
    wire(ax, [(xs, pads["5V"]), (8, 7.6), (jx + 0.4, rows[1])], "red", lw=2.4)
    # main GND (black) pin 2 -> GND pad, with the splice at 30 mm
    wire(ax, [(xs, pads["GND"]), (6, -0.6), (40, -0.6), (60, -0.6), (90, 2.0), (jx + 0.4, rows[2])], "black", lw=2.4)
    # CLK (black + yellow band) pin 3 -> CI ; return pin 4 ends at the splice
    wire(ax, [(xs, pads["CI"]), (14, 4.8), (30, 4.8)], "black", lw=2.2)
    twist(ax, 30, 104, 4.8, 3.6, "black", "black", 7, lw=2.0)
    wire(ax, [(104, 4.8), (jx + 0.4, rows[3])], "black", lw=2.2)
    wire(ax, [(104, 3.6), (jx + 0.4, rows[4])], "black", lw=2.2)
    wire(ax, [(30, 3.6), (27.5, 1.0), (25.5, -0.45)], "black", lw=2.0, z=7)
    # DATA (black + orange band) pin 5 -> DI ; return pin 6 ends at the splice
    wire(ax, [(xs, pads["DI"]), (14, 2.2), (34, 2.2)], "black", lw=2.2)
    twist(ax, 34, 104, 2.2, 1.0, "black", "black", 6, lw=2.0)
    wire(ax, [(104, 2.2), (jx + 0.4, rows[5])], "black", lw=2.2)
    wire(ax, [(104, 1.0), (jx + 0.4, rows[6])], "black", lw=2.2)
    wire(ax, [(34, 1.0), (32.5, 0.2), (31.0, -0.45)], "black", lw=2.0, z=7)
    # ID bands (15 mm from each end)
    for x in (12, 108.5):
        band(ax, x, 4.75 if x < 50 else 4.55, "yellow", w=1.8, h=1.3, z=9)
        band(ax, x, 2.2 if x < 50 else 1.75, "orange", w=1.8, h=1.3, z=9)
    # splice sleeve
    ax.add_patch(Rectangle((23.0, -1.25), 10.0, 1.3, fc="#3a3a3a", ec="#000", lw=0.7, alpha=0.85, zorder=10))
    note(ax, 28.0, -1.6, "GND splice, 30 mm before the pad: window-strip 5 mm of the main GND,\nwrap the two returns' 5 mm ends round it, "
         "solder, 3 mm x 15 mm heat-shrink\n(slid onto the GND BEFORE soldering), shrink.", fs=5.6, ha="center")
    # dimensions
    dim(ax, (-5.3, 10.0), (jx, 10.0), "5V and GND: 170 (S0) / 165 (S12)", fs=6.0)
    dim(ax, (-5.3, 8.85), (jx, 8.85), "CLK and DATA: 165 / 165", off=(14, 0), fs=6.0)
    dim(ax, (-5.3, -6.2), (28.0, -6.2), "30", fs=6.0)
    dim(ax, (28.0, -6.2), (jx, -6.2), "the two returns: 135 each, ending at the splice", fs=6.0)
    note(ax, 80, -2.6, "twist each signal with its return: 1 turn per 10 mm, splice -> terminal (about 13 turns);\n"
         "lay 5V and GND alongside (1 turn per 25 mm). Bands: yellow = CLK, orange = DATA, 6 mm, 15 mm from each end.",
         fs=5.6, ha="center", va="top", bg="white")
    note(ax, -13, -7.6, "At the pads: 5V red -> 5V, yellow-band -> CI, orange-band -> DI, the spliced GND -> GND (one wire per pad).  "
         "At J3 / J4: 1 red, 2 GND, 3 yellow-band, 4 its return, 5 orange-band, 6 its return.", fs=6.0, weight="bold")


def panel_feeds(ax):
    ax.set_xlim(-2, 100)
    ax.set_ylim(-1.5, 15.5)
    ax.axis("off")
    ax.text(-1, 15.2, "B.  Six feeds: red / black 26 AWG pairs, 1 turn per 25 mm", fontsize=9.5, fontweight="bold", va="top")
    ax.text(-1, 13.8, "Strip end (left): 2.5 mm, tinned, laid BESIDE the ribbon wire on the 5V and GND pads, one joint each.\n"
            "Terminal end (right): 5 mm bare, red -> pin 1, black -> pin 2.", fontsize=6.4, va="top", color="#333")
    feeds = [(3, 200, "J6", "A"), (6, 235, "J7", "A"), (9, 250, "J8", "A"), (15, 155, "J9", "B"), (18, 120, "J10", "B"), (21, 125, "J11", "B")]
    for i, (s, L, j, bus) in enumerate(feeds):
        y = 11.2 - i * 2.05
        x1 = 8 + L * 0.3
        twist(ax, 8, x1, y + 0.28, y - 0.28, "red", "black", max(2, round(L / 25)), lw=1.8)
        ax.text(7.2, y, "F%d  strip %d" % (s, s), fontsize=6.4, ha="right", va="center", fontweight="bold")
        box(ax, x1 + 0.8, y - 0.6, 6.0, 1.2, "%s" % j, fc="#2e7d32", ec="#1b5e20", fs=6.0, color="white", weight="bold")
        ax.text(x1 + 7.6, y, "%d mm   (bus %s)" % (L, bus), fontsize=6.2, va="center")
    note(ax, -1, -0.6, "Cut both conductors of a pair to the same length; route every feed the same way (under the plate, radially out, up "
         "through its bottom slot): the balance relies on it.", fs=5.8)


def panel_hall(ax):
    ax.set_xlim(-6, 100)
    ax.set_ylim(-3, 15.5)
    ax.axis("off")
    ax.text(-5, 15.2, "C.  Hall lead: A3144 -> J5, 3 x 26 AWG, 160 mm, 1 turn per 15 mm", fontsize=9.5, fontweight="bold", va="top")
    ax.text(-5, 13.8, "A3144 flat (branded) face toward you, legs down: 1 = VCC, 2 = GND, 3 = OUT.\n"
            "J5 on the carrier: 1 = OUT, 2 = GND, 3 = 5V.  The outer two SWAP.", fontsize=6.4, va="top", color="#333")
    # TO-92 body, flat face toward the viewer
    ax.add_patch(Polygon([(2, 6.2), (2, 10.5), (3.0, 11.4), (7.0, 11.4), (8, 10.5), (8, 6.2)], closed=True, fc="#222", ec="#000", zorder=3))
    ax.text(5, 9.0, "A3144\nflat face", fontsize=5.4, color="white", ha="center", va="center", zorder=4)
    legs = {1: 3.0, 2: 5.0, 3: 7.0}
    for k, x in legs.items():
        ax.plot([x, x], [6.2, 3.0], color="#c9ccd1", lw=1.6, zorder=2)
        ax.text(x, 5.65, "%d" % k, fontsize=6.0, ha="center", va="center", fontweight="bold", zorder=8,
                bbox=dict(fc="white", ec="none", pad=0.4))
        ax.add_patch(Rectangle((x - 0.45, 3.2), 0.9, 1.9, fc="#444", ec="#000", lw=0.5, alpha=0.8, zorder=5))   # 2 mm sleeve
    ax.text(9.0, 4.0, "2 mm x 8 mm heat-shrink\non each leg joint", fontsize=5.4, va="center")
    # wires from the legs to J5
    jx = 86
    rows = {1: 9.6, 2: 8.0, 3: 6.4}
    wire(ax, [(3.0, 3.0), (3.0, 0.6), (20, 0.6), (40, 3.2), (78, 6.4), (jx, rows[3])], "red", lw=2.2)
    wire(ax, [(5.0, 3.0), (5.0, 1.4), (20, 1.4), (40, 4.6), (78, 8.0), (jx, rows[2])], "black", lw=2.2)
    wire(ax, [(7.0, 3.0), (7.0, 2.2), (20, 2.2), (40, 6.0), (78, 9.6), (jx, rows[1])], "black", lw=2.2)
    band(ax, 24, 2.85, "white", w=1.8, h=1.2, z=9)
    band(ax, 74, 9.1, "white", w=1.8, h=1.2, z=9)
    ax.add_patch(Rectangle((jx, 5.4), 3.2, 5.2, fc="#2e7d32", ec="#1b5e20", lw=0.9, zorder=2))
    for k, y in rows.items():
        ax.add_patch(Rectangle((jx + 0.3, y - 0.4), 1.2, 0.8, fc="#c9ccd1", ec="#555", lw=0.4, zorder=3))
    ax.text(jx + 3.8, rows[1], "1 OUT (white band)", fontsize=5.8, va="center")
    ax.text(jx + 3.8, rows[2], "2 GND", fontsize=5.8, va="center")
    ax.text(jx + 3.8, rows[3], "3 5V (red)", fontsize=5.8, va="center")
    ax.text(jx + 1.6, 11.0, "J5  3P", fontsize=6.0, ha="center", va="bottom", fontweight="bold")
    note(ax, 30, -0.4, "The LEGS pass the bottom cap's 1.4 x 4.5 mm lead slot, not the wires: glue the sensor face-down in its pocket, bend the legs\n"
         "up through the slot, THEN solder the lead to the leg tops (2.6 mm under the sled plate): strip 3 mm, tin, lap, 320 C, 2 s.  Terminal end: 5 mm, bare.",
         fs=5.8, ha="center")


def main():
    fig = plt.figure(figsize=(14.0, 10.6))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.15, 1.0], hspace=0.06, wspace=0.10)
    panel_start(fig.add_subplot(gs[0, :]))
    panel_feeds(fig.add_subplot(gs[1, 0]))
    ax = fig.add_subplot(gs[1, 1])
    panel_hall(ax)
    stamp(ax, 100, -3, "guide_leads")
    save(fig, "guide_leads")


if __name__ == "__main__":
    main()
