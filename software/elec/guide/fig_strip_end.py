"""Strip-end pad diagrams for the wiring guide (bench view: strip FACE DOWN on the mat, pads up, the end being soldered on the
LEFT), drawn to scale in mm from measurements #28-30 (2026-11-04): 12.0 mm strip, four 2.5 x 2.5 mm back pads over an 11 mm
outer span, copper from the cut edge (0-2.5 mm). The 10 x 5 mm wall slot spans 1.0-6.0 mm from the cut end and +-5.0 across,
so the outer 0.5 mm of the two outer pads sits behind the wall and the joint window is 1.0-2.5 along: about 2.0 x 1.5 mm on
GND / 5V and 2.5 x 1.5 mm on C / D. Panel D is a side section through the tube wall at a bottom end.

  py software/elec/guide/fig_strip_end.py      -> docs/img/guide_strip_end.svg/.png
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import matplotlib.pyplot as plt                                       # noqa: E402
from matplotlib.patches import Circle, Ellipse, Polygon, Rectangle    # noqa: E402

from guide_common import WC, band, dim, save, stamp, wire              # noqa: E402

PAD_W = 2.5                                # pad width across the strip (#30)
PAD_Y = [4.25, 1.4167, -1.4167, -4.25]     # pad centres (top -> bottom): 11 mm outer span (#28), pitch (11 - 2.5) / 3 = 2.83, gap 0.33
PAD_X = (0.0, 2.5)                         # copper along the strip, from the cut edge (#30)
SLOT_HALF = 5.0                            # slot is 10 mm wide: +-5.0 across
SLOT_X = (1.0, 6.0)                        # wall-slot footprint (povlib: slot from +1.0 above the cut line, 5 mm tall)
TIP_X = 1.0                                # tinned wire tip
STRIP_TIN = 2.5


def strip(ax, x1=26.0, title="", sub=""):
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_xlim(-9.0, x1 + 1.0)
    ax.set_ylim(-11.5, 10.5)
    ax.add_patch(Rectangle((0, -6), x1, 12, fc="#2b2b2b", ec="#000", lw=1.0, zorder=1))          # black PCB, back side
    ax.add_patch(Rectangle((6.0, -6), x1 - 6.0, 12, fc="#e8e2d0", ec="#999", lw=0.5, zorder=2, alpha=0.95))    # tape + liner (left on)
    ax.text(16.0, 4.6, "double-sided tape, liner LEFT ON (option A)", fontsize=5.6, color="#555", ha="center", zorder=3)
    ax.plot([x1, x1 - 0.6, x1 + 0.4, x1], [-6, -2, 2, 6], color="white", lw=4, zorder=4)            # break line
    # LED on the FRONT (seen through): centre ~8.3 mm from the cut edge, 5 x 5 package
    ax.add_patch(Rectangle((5.8, -2.5), 5.0, 5.0, fc="none", ec="#e09f3e", lw=0.9, ls="--", zorder=5))
    ax.text(8.3, -5.3, "end LED (front, seen through)", fontsize=4.8, color="#b07020", ha="left", va="center", zorder=5)
    # zones
    ax.add_patch(Rectangle((SLOT_X[0], -SLOT_HALF), SLOT_X[1] - SLOT_X[0], 2 * SLOT_HALF, fc="none", ec="#1d4ed8", lw=0.9, ls=(0, (3, 2)), zorder=6))
    ax.add_patch(Rectangle((0, -6), 1.0, 12, fc="none", ec="#d62828", hatch="////", lw=0.0, zorder=6))
    for y in PAD_Y:
        ax.add_patch(Rectangle((PAD_X[0], y - PAD_W / 2), PAD_X[1] - PAD_X[0], PAD_W, fc="#c9a227", ec="#8a6d00", lw=0.6, zorder=6))
        if abs(y) > 3:      # outer pads: the outer 0.5 mm is behind the wall (#28, #30); solder on the INNER half
            sgn = 1 if y > 0 else -1
            ax.add_patch(Rectangle((PAD_X[0], SLOT_HALF if sgn > 0 else -SLOT_HALF - 0.5), PAD_X[1] - PAD_X[0], 0.5,
                                   fc="#6c757d", ec="#343a40", hatch="xxxx", lw=0.4, alpha=0.9, zorder=7))      # behind the wall
            y0 = y - PAD_W / 2 if sgn > 0 else y      # inner half of the pad, across
            ax.add_patch(Rectangle((1.0, y0), PAD_X[1] - 1.0, PAD_W / 2, fc="#38b000", ec="none", alpha=0.5, zorder=7))
        else:
            ax.add_patch(Rectangle((1.0, y - PAD_W / 2), PAD_X[1] - 1.0, PAD_W, fc="#38b000", ec="none", alpha=0.4, zorder=7))
    ax.plot([0, 0], [-7.6, 7.6], color="#d62828", lw=1.0, zorder=8)
    ax.text(-0.3, -6.4, "cut\nedge", fontsize=5.4, color="#d62828", ha="right", va="top")
    if title:
        ax.text(-8.8, 10.2 + 1.0 * max(0, sub.count(chr(10)) - 1), title, fontsize=8.6, fontweight="bold", va="top")
    if sub:
        ax.text(-8.8, 8.95 + 1.0 * max(0, sub.count(chr(10)) - 1), sub, fontsize=6.0, va="top", color="#333")


def pad_labels(ax, labels):
    for y, t in zip(PAD_Y, labels):
        ax.text(-0.5, y, t, fontsize=6.6, ha="right", va="center", fontweight="bold", zorder=9)


def wire_on_pad(ax, y, col, gauge="28", x_end=26.5, dy_run=0.0, band_col=None):
    """Tinned tip from TIP_X to TIP_X + 2.5 on the pad, insulation from there along the strip toward its middle."""
    if abs(y) > 3:          # outer pad: the wire goes on the middle of its inner half
        y = y - PAD_W / 4 * (1 if y > 0 else -1)
    lw_ins = {"28": 3.2, "26": 4.4}[gauge]
    lw_cu = {"28": 1.3, "26": 1.7}[gauge]
    x_ins = TIP_X + STRIP_TIN
    ax.plot([TIP_X, x_ins], [y, y], color=WC["tinned"], lw=lw_cu + 0.6, solid_capstyle="butt", zorder=10)
    ax.plot([TIP_X, x_ins], [y, y], color="#8d99ae", lw=0.5, zorder=10)
    wire(ax, [(x_ins, y), (x_ins + 3.0, y + dy_run * 0.3), (x_end, y + dy_run)], col, lw=lw_ins * 0.55, z=11)
    if band_col:
        band(ax, x_ins + 9.0, y + dy_run * 0.25, band_col, w=1.6, h=1.6, z=12)
    ax.add_patch(Ellipse((x_ins + 0.25, y), 1.2, 1.6, fc="#a9d6e5", ec="#5fa8d3", lw=0.5, alpha=0.75, zorder=12))   # CA drop


def zone_dims(ax):
    dim(ax, (0, -7.3), (1.0, -7.3), "1.0\nbare", off=(0, -1.1), fs=5.0)
    dim(ax, (1.0, -7.3), (2.5, -7.3), "joint\n1.0-2.5", off=(0.9, -1.1), fs=5.0)
    dim(ax, (-6.8, -5.5), (-6.8, 5.5), "pads 11", off=(0, 0), fs=5.0)
    dim(ax, (-3.9, -5.0), (-3.9, 5.0), "slot 10", off=(0, 0), fs=5.0)
    dim(ax, (0, -9.6), (6.0, -9.6), "slot footprint on the tube: 1.0-6.0 (dashed blue)", off=(9.0, 0), fs=5.0)
    dim(ax, (TIP_X, 6.8), (TIP_X + STRIP_TIN, 6.8), "strip + tin 2.5", off=(4.2, 0.0), fs=5.0)
    dim(ax, (21.5, -6.0), (21.5, 6.0), "12.0", off=(1.2, 0), fs=5.0)


def legend(ax, x0=-8.8, y0=-11.2):
    x = x0
    sw = [("pad 2.5 x 2.5, copper 0-2.5 from the cut (#30)", dict(fc="#c9a227", ec="#8a6d00")),
          ("solder here: 1.0-2.5, outer pads inner half", dict(fc="#38b000", ec="none", alpha=0.45)),
          ("behind the wall (outer 0.5)", dict(fc="#6c757d", ec="#343a40", hatch="xxxx")),
          ("keep flat (0-1.0)", dict(fc="none", ec="#d62828", hatch="////")), ("CA drop", None)]
    for t, kw in sw:
        if kw is None:
            ax.add_patch(Ellipse((x + 0.5, y0), 1.0, 1.0, fc="#a9d6e5", ec="#5fa8d3"))
        else:
            ax.add_patch(Rectangle((x, y0 - 0.5), 1.0, 1.0, **kw))
        ax.text(x + 1.4, y0, t, fontsize=5.0, va="center")
        x += 2.0 + 0.37 * len(t)
        if x > 14.0:
            x, y0 = x0, y0 - 1.5


def panel_a(ax):
    strip(ax, title="A.  Ribbon first end on an OUT end (bench): 20 of the 22 jumpers",
          sub="Strip FACE DOWN, OUT end on the left. Measured order (#29) GND | CO | DO | 5V: flip the red-orange-yellow-green band so green is on\n"
              "GND and red on 5V: it lies flat, yellow on CO, orange on DO, no crossing. Solder on the LED half of each pad (1.0-2.5); GND / 5V on their INNER half\n"
              "(11 mm of pads, 10 mm slot: the outer 0.5 sits behind the wall). Gaps between pads only ~0.3 mm: watch for bridges. By LABEL.")
    labels = ["GND", "CO", "DO", "5V"]
    pad_labels(ax, labels)
    for y, t in zip(PAD_Y, labels):
        wire_on_pad(ax, y, {"5V": "red", "CO": "yellow", "DO": "orange", "GND": "green"}[t])
    ax.text(26.6, 0, "to strip s+1\n(ribbon 80 mm,\nfree end)", fontsize=5.6, va="center")
    zone_dims(ax)
    legend(ax, y0=-10.9)
    ax.set_ylim(-13.2, 11.5)


def panel_b(ax):
    strip(ax, title="B.  Feed strip, bottom end (3, 6, 9, 15, 18, 21): ribbon + 26 AWG feed",
          sub="Two wires on the 5V pad and on the GND pad, ONE joint each, both on the pad's INNER half (#28): ribbon conductor first, the 26 AWG\n"
              "feed conductor stacked ON TOP of it; one touch of the iron. Too tight? Use the 3-way splice (guide 4.2) instead.")
    labels = ["GND", "CO", "DO", "5V"]
    pad_labels(ax, labels)
    for y, t in zip(PAD_Y, labels):
        wire_on_pad(ax, y, {"5V": "red", "CO": "yellow", "DO": "orange", "GND": "green"}[t])
    for y, c, dy in ((PAD_Y[3], "red", -1.2), (PAD_Y[0], "black", 1.2)):
        yy = y - (PAD_W / 4 + 0.35 if dy > 0 else -(PAD_W / 4 + 0.35))
        ax.plot([TIP_X + 0.2, TIP_X + 2.7], [yy, yy], color=WC["tinned"], lw=2.3, solid_capstyle="butt", zorder=13)
        wire(ax, [(TIP_X + 2.7, yy), (7.0, y + dy * 0.6), (26.5, y + dy * 1.6)], c, lw=2.4, z=14)
    ax.text(26.6, -5.7, "feed + (26 AWG red)\nto J6..J11 pin 1", fontsize=5.4, va="center", color=WC["red"])
    ax.text(26.6, 5.7, "feed - (26 AWG black)\nto J6..J11 pin 2", fontsize=5.4, va="center")
    ax.text(26.6, 0, "ribbon to\nthe next strip", fontsize=5.4, va="center")
    zone_dims(ax)
    ax.text(-8.8, -11.2, "Strips 6 and 18: same, but on their IN pads (GND, CI, DI, 5V) with the first end of jumper 5-6 / 17-18.",
            fontsize=5.4, color="#b00", ha="left", va="center")


def panel_c(ax):
    strip(ax, title="C.  Start lead on strip 0 / strip 12, IN end (bottom)",
          sub="Measured IN order (#29) GND | CI | DI | 5V. 26 AWG: red = 5V, black = GND, black + YELLOW band = CLK -> CI, black + ORANGE band = DATA -> DI.\n"
              "The two black signal returns end 30 mm before the strip, spliced into the GND wire (fig. guide_leads): ONE wire per pad.")
    labels = ["GND", "CI", "DI", "5V"]
    pad_labels(ax, labels)
    for y, t in zip(PAD_Y, labels):
        if t == "GND":
            wire_on_pad(ax, y, "black", gauge="26")
        elif t == "5V":
            wire_on_pad(ax, y, "red", gauge="26")
        elif t == "CI":
            wire_on_pad(ax, y, "black", gauge="26", band_col="yellow")
        else:
            wire_on_pad(ax, y, "black", gauge="26", band_col="orange")
    ax.text(26.6, 0, "to J3 / J4\n(170 / 165 mm)", fontsize=5.6, va="center")
    zone_dims(ax)


def panel_d(ax):
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_xlim(-16, 16)
    ax.set_ylim(-9.5, 21)
    ax.text(-15.8, 20.6, "D.  On the tube: side section at a BOTTOM end (top ends are the mirror image)", fontsize=8.6, fontweight="bold", va="top")
    ax.text(-15.8, 19.3, "Laid into its rails, the strip's back sits on the wall; the joint faces the 10 x 5 mm slot, the wire turns 90 deg\n"
            "through the slot and runs INSIDE the wall. The pad starts AT the cut edge, but its first 1 mm sits on solid wall:\n"
            "a bump there lifts the strip. Solder only on 1.0-2.5, the part of the pad over the slot.", fontsize=6.0, va="top", color="#333")
    # wall (radial = x, outside to the right), slot from z 1.0 to 6.0 above the cut line (z 0)
    ax.add_patch(Rectangle((-1.6, -4), 1.6, 5.0, fc="#555", ec="#222", lw=0.6))
    ax.add_patch(Rectangle((-1.6, 6.0), 1.6, 9.5, fc="#555", ec="#222", lw=0.6))
    ax.text(-0.8, 12.6, "tube wall\n1.6", color="white", fontsize=5.4, ha="center", va="center", rotation=90)
    ax.add_patch(Rectangle((0.0, -4), 3.2, 4.0, fc="#7a7a7a", ec="#222", lw=0.6))                    # printed end-stop
    ax.text(1.6, -2.0, "end-\nstop", color="white", fontsize=5.0, ha="center", va="center")
    ax.add_patch(Rectangle((0.0, 0.0), 0.46, 15.5, fc="#2b2b2b", ec="#000", lw=0.5))                  # strip PCB
    ax.add_patch(Rectangle((0.46, 5.8), 1.6, 5.0, fc="#f4f1de", ec="#e09f3e", lw=0.8))                # LED on the front
    ax.text(2.4, 8.3, "LED 0 (face OUT)", fontsize=5.2, va="center")
    ax.add_patch(Rectangle((-0.06, 0.0), 0.06, 2.5, fc="#c9a227", ec="none"))                         # pad on the back, 0-2.5 (#30)
    ax.add_patch(Polygon([(0, 1.0), (-0.45, 1.25), (-0.45, 2.3), (0, 2.5)], fc="#c9ccd1", ec="#666", lw=0.4))   # fillet, 1.0-2.5
    wire(ax, [(-0.25, 1.4), (-0.25, 3.6), (-1.2, 4.6), (-2.6, 4.9), (-9.0, 5.1)], "red", lw=2.2, z=8)
    ax.add_patch(Rectangle((-2.5, 3.2), 0.12, 6.6, fc="#e9b44c", ec="none", alpha=0.9))                # tape inside over the slot
    ax.text(-2.8, 8.8, "tape over the slot\n(inside, at mounting)", fontsize=5.2, ha="right", va="center")
    dim(ax, (4.6, 0.0), (4.6, 1.0), "1.0", off=(1.2, 0), fs=5.0)
    dim(ax, (6.6, 1.0), (6.6, 6.0), "slot 1.0-6.0", off=(2.6, 0), fs=5.0)
    dim(ax, (8.6, 0.0), (8.6, 2.5), "pad 0-2.5", off=(2.4, 0), fs=5.0)
    ax.plot([-16, 16], [0, 0], color="#d62828", lw=0.6, ls=":")
    ax.text(-15.8, 0.3, "cut line on the end-stop (z0)", fontsize=5.0, color="#d62828", ha="left", va="bottom")
    ax.text(-9.2, 5.6, "to the next strip / under\nthe sled plate (inside)", fontsize=5.2, ha="left", va="bottom")
    ax.text(-15.8, -9.2, "OUTSIDE is to the right; the LED faces out.  Wire leaves the joint toward\nthe strip's middle (up here), then dives "
            "through the slot: that bend is the strain relief.", fontsize=5.4, va="bottom", color="#333")


def main():
    fig = plt.figure(figsize=(15.0, 10.8))
    gs = fig.add_gridspec(2, 2, hspace=0.08, wspace=0.04)
    panel_a(fig.add_subplot(gs[0, 0]))
    panel_b(fig.add_subplot(gs[0, 1]))
    panel_c(fig.add_subplot(gs[1, 0]))
    ax = fig.add_subplot(gs[1, 1])
    panel_d(ax)
    stamp(ax, 16, -6.5, "guide_strip_end")
    save(fig, "guide_strip_end")


if __name__ == "__main__":
    main()
