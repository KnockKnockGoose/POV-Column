"""Shared constants and drawing helpers for the wiring build guide figures (docs/2026-11-04-wiring-build-guide.md).

Every figure script in this folder imports this module and writes docs/img/guide_<name>.svg + .png through save().
Colour convention (Brian, 2026-11-03, plus the QA-2 N5 change and Brian's ribbon decision of 2026-11-04):
  single wires: red = 5 V, black = GND; the 26 AWG start-lead / hall signal conductors are BLACK with a coloured ID band
  (orange band = DATA, yellow band = CLK, white band = hall OUT) because only red / black 26 AWG is on hand.
  ribbon jumpers: red / orange / yellow / green = 5V / DATA / CLK / GND (green is GND in the ribbon only); flipped, the band
  lies flat on the pads GND, C, D, 5V in its own order (green, yellow, orange, red). Carrier 28 AWG: orange = data, yellow = clock.
"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
IMG = os.path.join(ROOT, "docs", "img")
REV = "guide 2026-11-04 (rev h)"

WC = {"red": "#d62828", "black": "#151515", "orange": "#f77f00", "yellow": "#ffd60a", "green": "#2b9348",
      "white": "#ffffff", "blue": "#1d4ed8", "violet": "#7b2cbf", "brown": "#7f4f24", "grey": "#8d99ae",
      "bare": "#b08d57", "tinned": "#c9ccd1"}
NET_RIBBON = {"5V": "red", "C": "yellow", "D": "orange", "GND": "green"}
SET_COL = {"A": "#c1121f", "B": "#0077b6", "C": "#2d6a4f"}
FEED_J = {3: "J6", 6: "J7", 9: "J8", 15: "J9", 18: "J10", 21: "J11"}
START_J = {0: "J3", 12: "J4"}
JUMPERS = [(s, s + 1, "top" if s % 2 == 0 else "bottom") for s in range(24) if s % 12 != 11]
LOOP_AT = {(a, b): (a if (a, b) in ((5, 6), (17, 18)) else b) for a, b, _ in JUMPERS}       # second-soldered end
BENCH_AT = {(a, b): (b if (a, b) in ((5, 6), (17, 18)) else a) for a, b, _ in JUMPERS}      # first end, on the bench
MOUNT_ORDER = [0, 1, 2, 3, 4, 6, 5, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 18, 17, 19, 20, 21, 22, 23]
JUMPER_CUT = 80          # mm, all 22 (guide decision, QA-2 m-d)


def set_letter(s):
    return "ABC"[s % 3]


def upright(s):
    return s % 2 == 0      # even strips: arrow UP, IN at the bottom; odd strips inverted, IN at the top


def end_role(s, end):
    """'IN' or 'OUT' for strip s at end 'top' / 'bottom'."""
    if upright(s):
        return "IN" if end == "bottom" else "OUT"
    return "IN" if end == "top" else "OUT"


def wire(ax, pts, col, lw=3.0, z=6, ls="-", outline=True):
    xs, ys = zip(*pts)
    edge = "#555555" if col == "black" else "#222222"
    eff = [pe.Stroke(linewidth=lw + 2.6, foreground="white"), pe.Stroke(linewidth=lw + 1.1, foreground=edge), pe.Normal()] if outline else None
    c = WC.get(col, col)
    ax.plot(xs, ys, color=c, lw=lw, ls=ls, solid_capstyle="round", solid_joinstyle="round", zorder=z, path_effects=eff)


def band(ax, x, y, col, w=1.2, h=1.6, z=8, vertical=False):
    """A coloured ID band (heat-shrink) on a wire at (x, y)."""
    if vertical:
        ax.add_patch(Rectangle((x - h / 2, y - w / 2), h, w, fc=WC[col], ec="#222", lw=0.6, zorder=z))
    else:
        ax.add_patch(Rectangle((x - w / 2, y - h / 2), w, h, fc=WC[col], ec="#222", lw=0.6, zorder=z))


def box(ax, x, y, w, h, text="", fc="#f6f6f6", ec="#333", fs=7, z=3, lw=0.9, round_=0.6, color="#111", weight="normal", ha="center"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=%g" % round_, fc=fc, ec=ec, lw=lw, zorder=z))
    if text:
        tx = x + w / 2 if ha == "center" else x + 0.8
        ax.text(tx, y + h / 2, text, ha=ha, va="center", fontsize=fs, zorder=z + 1, color=color, fontweight=weight)


def note(ax, x, y, text, fs=6.5, color="#333", ha="left", va="top", z=9, bg=None, weight="normal", **kw):
    bbox = dict(fc=bg, ec="none", pad=1.5) if bg else None
    ax.text(x, y, text, fontsize=fs, color=color, ha=ha, va=va, zorder=z, bbox=bbox, fontweight=weight, **kw)


def arrow(ax, p0, p1, col="#333", lw=1.0, z=7, style="-|>", ms=8):
    ax.annotate("", xy=p1, xytext=p0, arrowprops=dict(arrowstyle=style, color=col, lw=lw, mutation_scale=ms), zorder=z)


def dim(ax, p0, p1, text, off=(0, 0), fs=6, col="#444", z=7):
    """Dimension line with arrows at both ends and a centred label."""
    ax.annotate("", xy=p1, xytext=p0, arrowprops=dict(arrowstyle="<->", color=col, lw=0.7, shrinkA=0, shrinkB=0), zorder=z)
    mx, my = (p0[0] + p1[0]) / 2 + off[0], (p0[1] + p1[1]) / 2 + off[1]
    ax.text(mx, my, text, fontsize=fs, color=col, ha="center", va="center", zorder=z + 1, bbox=dict(fc="white", ec="none", pad=0.6))


def stamp(ax, x, y, name, fs=5.5, rev=None):
    ax.text(x, y, "fig. %s, %s, software/elec/guide" % (name, rev or REV), fontsize=fs, color="#999", ha="right", va="bottom")


def save(fig, name, dpi=170):
    os.makedirs(IMG, exist_ok=True)
    for ext in ("svg", "png"):
        fig.savefig(os.path.join(IMG, "%s.%s" % (name, ext)), dpi=dpi if ext == "png" else None, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote docs/img/%s.svg/.png" % name)


def load_netlist():
    with open(os.path.join(IMG, "elec_carrier_netlist.json"), encoding="utf-8") as f:
        return json.load(f)
