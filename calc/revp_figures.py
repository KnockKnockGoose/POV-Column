"""Figures for docs/2026-11-22-drive-redesign.md.

Run:  py -X utf8 calc/revp_figures.py   (after calc/revp_drive_redesign_calc.py)
Out:  docs/img/revp_drag_before_after.png, docs/img/revp_power_vs_speed.png
Palette: the dataviz skill's reference instance (light mode), validated there.
"""
import json
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(os.path.dirname(HERE), "docs", "img")
C = json.load(open(os.path.join(HERE, "revp_drive_redesign_calc.json"), encoding="utf-8"))

SURF, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984", "#e4e3df"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": MUTED, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "figure.facecolor": SURF, "axes.facecolor": SURF})

# ------------------------------------------------------------------ 1. drag before / after
rows = [("Bare rotor, fresh grease (11-19)", 34, 62, ORANGE),
        ("Rotor + board + battery (11-21)", 98, 145, ORANGE),
        ("Belt pulled tight, no skips (11-22)", 109, 160, ORANGE),
        ("Ring + plate, oiled: measured (11-22)", 0, 12, BLUE),
        ("Full rotor, oiled: predicted", 17, 22, BLUE)]
fig, ax = plt.subplots(figsize=(8.6, 3.6), dpi=150)
for i, (lab, lo, hi, col) in enumerate(rows):
    y = len(rows) - 1 - i
    ax.barh(y, max(hi - lo, 1.2), left=lo, height=0.42, color=col, edgecolor=SURF, linewidth=2)
    ax.text(hi + 3, y, f"{lo}-{hi}", va="center", ha="left", color=INK, fontsize=9)
ax.axvline(29, color=INK2, lw=1.2, ls=(0, (4, 3)))
ax.text(30.5, len(rows) - 0.55, "rev k-o design budget, 29 mN m", color=INK2, fontsize=8.5, va="bottom")
ax.set_yticks(range(len(rows)))
ax.set_yticklabels([r[0] for r in rows][::-1], color=INK)
ax.set_xlim(0, 180)
ax.set_ylim(-0.6, len(rows) - 0.2)
ax.set_xlabel("Drag at the rotor, mN m (from the motor current above the base)")
ax.grid(axis="x", color=GRID, lw=0.8)
ax.set_axisbelow(True)
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
ax.tick_params(axis="y", length=0)
h1 = plt.Rectangle((0, 0), 1, 1, color=ORANGE)
h2 = plt.Rectangle((0, 0), 1, 1, color=BLUE)
ax.legend([h1, h2], ["Factory grease in the 6820", "Flushed with IPA, light oil"], loc="lower right", frameon=False,
          fontsize=9, labelcolor=INK)
ax.set_title("What the 6820's factory grease cost the drive", loc="left", color=INK, fontsize=12, pad=10)
fig.tight_layout()
fig.savefig(os.path.join(IMG, "revp_drag_before_after.png"), facecolor=SURF)
plt.close(fig)

# ------------------------------------------------------------------ 2. motor power vs rotor speed
m = C["motor"]
R, k, KE = m["R"], m["k_V_per_rpm"], m["Ke"]
I0_BASE, ETA_B = 0.15, 0.95
rpm = [x * 0.5 for x in range(0, 561)]


def p_avail(nr, eta):
    i = (12.0 - k * 2 * nr) / R
    return max(0.0, KE * eta * (i - I0_BASE) * 2 * nr * 2 * math.pi / 60 * ETA_B)


fig, ax = plt.subplots(figsize=(8.6, 5.2), dpi=150)
lo = [p_avail(n, 0.65) for n in rpm]
hi = [p_avail(n, 0.85) for n in rpm]
mid = [p_avail(n, 0.75) for n in rpm]
ax.fill_between(rpm, lo, hi, color=BLUE, alpha=0.18, linewidth=0)
ax.plot(rpm, mid, color=BLUE, lw=2, label="JGB37-520 at 12 V through the 2:1 belt (what it can give)")
for T, col, lab in [(0.125, ORANGE, "Rotor with factory grease, 0.125 N m"), (0.020, AQUA, "Rotor oiled, ~0.020 N m (predicted)")]:
    ax.plot(rpm, [T * n * 2 * math.pi / 60 for n in rpm], color=col, lw=2, label=lab)
for x, lab in [(188, "188 rpm (25p)"), (225, "225 rpm (30p)")]:
    ax.axvline(x, color=INK2, lw=1, ls=(0, (4, 3)))
    ax.text(x - 4, 0.06, lab, color=INK2, fontsize=8.5, va="bottom", ha="right", rotation=90)
ax.annotate("runs here: ~130-155 rpm measured\n(motor at its power peak)", xy=(131, 1.71), xytext=(20, 2.35),
            color=INK, fontsize=9, arrowprops=dict(arrowstyle="-", color=INK2, lw=1))
ax.annotate("runs here:\n~240 rpm\nat full knob", xy=(241, 0.50), xytext=(246, 1.0), color=INK, fontsize=9,
            arrowprops=dict(arrowstyle="-", color=INK2, lw=1))
ax.plot([131], [1.71], "o", ms=7, color=ORANGE, mec=SURF, mew=2)
ax.plot([241], [0.505], "o", ms=7, color=AQUA, mec=SURF, mew=2)
ax.set_xlim(0, 280)
ax.set_ylim(0, 2.7)
ax.set_xlabel("Rotor speed, rpm")
ax.set_ylabel("Mechanical power at the rotor, W")
ax.grid(color=GRID, lw=0.8)
ax.set_axisbelow(True)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.legend(loc="upper left", frameon=False, fontsize=8.8, labelcolor=INK, bbox_to_anchor=(0.0, -0.13), ncol=1)
ax.set_title("Where the motor's power curve meets the rotor's load", loc="left", color=INK, fontsize=12, pad=10)
fig.tight_layout()
fig.savefig(os.path.join(IMG, "revp_power_vs_speed.png"), facecolor=SURF)
plt.close(fig)
print("wrote docs/img/revp_drag_before_after.png, docs/img/revp_power_vs_speed.png")
