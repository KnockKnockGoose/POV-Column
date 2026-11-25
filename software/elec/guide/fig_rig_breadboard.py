"""Phase-0 rig as a breadboard layout: every part and jumper on a named hole (Brian's rebuild, 2026-11-04).

One 63-column terminal section of a standard breadboard: rows a-e above the centre channel, f-j below, a +/- rail pair
along the top and the bottom. Holes are named like the board's print (column number + row letter, e.g. "e20").
Writes docs/img/guide_rig_breadboard.png/.svg.
"""
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle, Circle

OUT = Path(__file__).resolve().parents[3] / "docs" / "img"
NCOL = 50
ROWS = "abcdefghij"
# y of each row: a-e at 6..2, channel, f-j at -2..-6; rails above and below
Y = {r: (6 - i) if i < 5 else (-2 - (i - 5)) for i, r in enumerate(ROWS)}
Y.update({"T+": 9.0, "T-": 8.0, "B-": -8.0, "B+": -9.0})
RED, BLK, YEL, ORG, GRN, GRY = "#d62728", "#222222", "#e6b800", "#ff7f0e", "#2ca02c", "#888888"


def xy(h):
    """'e20' -> (20, y of row e); 'T+12' / 'B-40' -> rail hole at column 12 / 40."""
    if h[0] in "TB":
        return float(h[2:]), Y[h[:2]]
    return float(h[1:]), Y[h[0]]


fig, ax = plt.subplots(figsize=(17, 9.6))
ax.set_xlim(-6, NCOL + 9)
ax.set_ylim(-14.5, 14.2)
ax.set_aspect("equal")
ax.axis("off")

# board, rails, holes
ax.add_patch(FancyBboxPatch((-0.5, -10.2), NCOL + 1.2, 20.4, boxstyle="round,pad=0.2", fc="#f4f1ea", ec="#999", lw=1))
ax.add_patch(Rectangle((-0.3, -0.9), NCOL + 0.8, 1.8, fc="#e2ddd2", ec="none"))
ax.text(NCOL / 2, 0, "centre channel", ha="center", va="center", fontsize=8, color="#888")
for rail, col in (("T+", RED), ("T-", "#1f5fbf"), ("B-", "#1f5fbf"), ("B+", RED)):
    y = Y[rail]
    ax.plot([0.2, NCOL + 0.2], [y + (0.45 if rail in ("T+", "B-") else -0.45)] * 2, color=col, lw=1.6)
    ax.text(-1.0, y, rail[1].replace("-", "GND (-)").replace("+", "+5 V"), ha="right", va="center", fontsize=9,
            color=col, weight="bold")
    for c in range(1, NCOL + 1):
        if c % 6:
            ax.add_patch(Circle((c, y), 0.13, color="#bdb6a6"))
for r in ROWS:
    ax.text(0.1, Y[r], r, ha="center", va="center", fontsize=8, color="#777")
    ax.text(NCOL + 0.9, Y[r], r, ha="center", va="center", fontsize=8, color="#777")
    for c in range(1, NCOL + 1):
        ax.add_patch(Circle((c, Y[r]), 0.13, color="#bdb6a6"))
for c in (1, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50):
    ax.text(c, 7.0, str(c), ha="center", va="center", fontsize=7, color="#777")
    ax.text(c, -7.0, str(c), ha="center", va="center", fontsize=7, color="#777")


def jumper(a, b, color, lw=3.2, label=None, lab_off=(0, 0.35)):
    (x1, y1), (x2, y2) = xy(a), xy(b)
    ax.plot([x1, x2], [y1, y2], color=color, lw=lw, solid_capstyle="round", zorder=4)
    for x, y in ((x1, y1), (x2, y2)):
        ax.add_patch(Circle((x, y), 0.22, fc=color, ec="black", lw=0.6, zorder=5))
    if label:
        ax.text((x1 + x2) / 2 + lab_off[0], (y1 + y2) / 2 + lab_off[1], label, fontsize=7.5, ha="center",
                va="bottom", zorder=6, bbox=dict(fc="white", ec="none", pad=0.5, alpha=0.85))


def part(a, b, text, fc, ec="#6b4f2a", h=0.55, fs=7.5):
    (x1, y1), (x2, y2) = xy(a), xy(b)
    ax.plot([x1, x2], [y1, y2], color=GRY, lw=1.4, zorder=4)
    for x, y in ((x1, y1), (x2, y2)):
        ax.add_patch(Circle((x, y), 0.18, fc=GRY, zorder=5))
    xm, ym = (x1 + x2) / 2, (y1 + y2) / 2
    w = max(abs(x2 - x1), abs(y2 - y1)) * 0.55
    if abs(x2 - x1) >= abs(y2 - y1):
        ax.add_patch(Rectangle((xm - w / 2, ym - h / 2), w, h, fc=fc, ec=ec, zorder=6))
    else:
        ax.add_patch(Rectangle((xm - h / 2, ym - w / 2), h, w, fc=fc, ec=ec, zorder=6))
    ax.text(xm, ym, text, ha="center", va="center", fontsize=fs, zorder=7)


# rail links (both rails, left end): top + to bottom +, top - to bottom -
jumper("T+2", "B+2", RED, label="wire: top + to bottom +", lab_off=(3.2, 2.2))
jumper("T-3", "B-3", BLK, label="wire: top GND to bottom GND", lab_off=(3.9, -2.9))
# DevKit GND lead
x, y = xy("B-8")
ax.plot([x, x], [y, -11.2], color=BLK, lw=3.2, zorder=4)
ax.add_patch(Circle((x, y), 0.22, fc=BLK, ec="black", zorder=5))
ax.text(x + 0.3, -10.75, "DevKit GND", fontsize=7.5, ha="left", bbox=dict(fc="white", ec="none", pad=0.3), zorder=6)

# U1 74AHCT125: notch LEFT, pins 1-7 on row f cols 20-26, pins 14-8 on row e cols 20-26
ax.add_patch(FancyBboxPatch((19.45, -1.75), 7.1, 3.5, boxstyle="round,pad=0.05", fc="#2b2b2b", ec="black", zorder=3))
ax.add_patch(Circle((19.45, 0), 0.45, fc="#e2ddd2", ec="black", zorder=3.5))
ax.add_patch(Circle((20.0, -1.25), 0.16, fc="white", zorder=4))
ax.text(23, 0.25, "74AHCT125", color="white", ha="center", fontsize=10, weight="bold", zorder=4)
ax.text(23, -0.55, "text upright, notch LEFT", color="#ccc", ha="center", fontsize=7, zorder=4)
for i in range(7):
    c = 20 + i
    ax.text(c, -2.55, str(i + 1), ha="center", va="center", fontsize=7.5, color="#c00", weight="bold", zorder=6)
    ax.text(c, 2.55, str(14 - i), ha="center", va="center", fontsize=7.5, color="#c00", weight="bold", zorder=6)
ax.text(16.6, -2.55, "pin 1 (dot)", ha="center", va="center", fontsize=7.5, color="#c00")

# U1 power + decoupling + /OE + unused inputs
jumper("a20", "T+20", RED, label="pin 14 VCC")
part("b20", "T-18", "", "#f2d36b", ec="#8a6d00")       # 100 nF ceramic: pin 14 to GND
ax.text(17.2, 6.9, "100 nF", fontsize=7.5, ha="center", bbox=dict(fc="white", ec="none", pad=0.4))
for col, pin in ((21, 13), (22, 12), (24, 10), (25, 9)):
    jumper(f"a{col}", f"T-{col}", BLK, lw=2.4)
ax.text(31.5, 6.0, "pins 13, 12, 10, 9 -> GND", fontsize=7.5, ha="left",
        bbox=dict(fc="white", ec="none", pad=0.4))
for col in (20, 23, 26):
    jumper(f"j{col}", f"B-{col}", BLK, lw=2.4)
ax.text(23, -9.95, "pins 1, 4 (/OE) and 7 (GND) -> GND", fontsize=7.5, ha="center",
        bbox=dict(fc="white", ec="none", pad=0.4))

# inputs: pull-downs + DevKit signals (flying leads from the DevKit straight into the chip's columns)
part("i21", "B-16", "10k", "#bfe0ff", ec="#2060a0")    # pin 2 (1A, CLK in)
part("i24", "B-29", "10k", "#bfe0ff", ec="#2060a0")    # pin 5 (2A, DATA in)
for hole, col, txt in (("h21", YEL, "D18"), ("h24", ORG, "D23")):
    x, y = xy(hole)
    ax.plot([x, x - 0.6, x - 0.6], [y, y - 0.4, -11.2], color=col, lw=3.2, zorder=4, solid_capstyle="round")
    ax.add_patch(Circle((x, y), 0.22, fc=col, ec="black", lw=0.6, zorder=5))
    ax.text(x - 0.9, -10.75, txt, fontsize=7.5, ha="right", color="black", zorder=6,
            bbox=dict(fc="white", ec="none", pad=0.3))

# outputs: 68 R off the chip's output columns, then jumpers to the terminal
part("g22", "g31", "68R", "#f3e2c4")                   # pin 3 (1Y, CLK out)
part("h25", "h34", "68R", "#f3e2c4")                   # pin 6 (2Y, DATA out)
jumper("f31", "f42", YEL, label="CLK -> T3")
jumper("g34", "g44", ORG, label="DATA -> T5", lab_off=(0, -1.05))

# 6-position terminal in row i, cols 40-45 (pin 1 at 40)
ax.add_patch(Rectangle((39.4, -5.6), 6.2, 1.6, fc="#2e7d32", ec="black", zorder=6))
for k in range(6):
    ax.add_patch(Circle((40 + k, -4.8), 0.33, fc="#9ccc9c", ec="black", zorder=7))
    ax.text(40 + k, -4.8, str(k + 1), ha="center", va="center", fontsize=8, weight="bold", zorder=8)
ax.text(42.5, -3.55, "terminal (wires enter from below)", fontsize=7.5, ha="center", zorder=8)
jumper("j40", "B+40", RED, lw=2.4)
for col in (41, 43, 45):
    jumper(f"j{col}", f"B-{col}", BLK, lw=2.4)
ax.text(46.6, -6.5, "T1 -> +5 V, T2/4/6 -> GND", fontsize=7.5, ha="left")

# bulk cap across the bottom rails, stripe to GND
part("B+48", "B-48", "", "#d9c3e6", ec="#5b3a7a", h=0.9)
ax.text(47.5, -10.8, "1000 uF across the rails: stripe (-) leg in GND", fontsize=7.5, ha="center", color="#5b3a7a")

# supply and DevKit blocks
ax.add_patch(FancyBboxPatch((-5.6, -13.9), 9.5, 2.6, boxstyle="round,pad=0.2", fc="#eef3ff", ec="#557"))
ax.text(-0.85, -12.2, "BENCH SUPPLY  5.00 V, limit 0.05 A", fontsize=8, ha="center", weight="bold")
ax.text(-0.85, -13.2, "red -> bottom +5 V rail, black -> bottom GND rail", fontsize=7, ha="center")
jumper("B+1", "B+1", RED)
jumper("B-1", "B-1", BLK)
ax.add_patch(FancyBboxPatch((6.5, -13.9), 24, 2.6, boxstyle="round,pad=0.2", fc="#1f3550", ec="black"))
ax.text(18.5, -12.2, "SPARE DevKit (on USB; off this section, wired by flying leads)", color="white", fontsize=8.5,
        ha="center", weight="bold")
ax.text(18.5, -13.2, "D18 -> h21 (yellow, CLK)   D23 -> h24 (orange, DATA)   GND -> bottom GND rail   VIN: nothing", color="white",
        fontsize=7.5, ha="center")

ax.text(-5.6, 13.3, "Phase-0 test rig: breadboard layout (every hole named: column + row letter)", fontsize=15,
        weight="bold")
ax.text(-5.6, 12.1, "Supply OFF while building. Check the rails aren't split in the middle: if the red/blue lines break "
        "halfway, bridge both. Keep every bare lead clear of its neighbours.", fontsize=9)
ax.text(-5.6, 11.1, "Colours: red +5 V, black GND, yellow CLK, orange DATA. T's lead: red -> T1, green -> T2, "
        "yellow -> T3, orange -> T5.", fontsize=9)
ax.text(NCOL + 8.5, -14.3, "fig. guide_rig_breadboard, 2026-11-04, software/elec/guide/fig_rig_breadboard.py",
        fontsize=7, color="#888", ha="right")

OUT.mkdir(parents=True, exist_ok=True)
for ext in ("png", "svg"):
    fig.savefig(OUT / f"guide_rig_breadboard.{ext}", dpi=160, bbox_inches="tight")
print(OUT / "guide_rig_breadboard.png")
