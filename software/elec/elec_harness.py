"""Strip wiring harness: the tube unwrapped (theta 0..360 across, z up), 24 strips with direction arrows, the 22 serpentine
jumpers, the 8 feeds and 2 chain-start leads, the wall slots. -> docs/img/elec_harness.svg/.png and the wiring table
docs/img/elec_wiring_table.csv.  Run: py software/elec/elec_harness.py
Geometry from fusionclaude/lib/povlib.py: strip s at theta 15 s, set k = s mod 3, LED0 z = 11.11 + 5.556 k, strip length 233.3,
cut end z0 = LED0 - 8.33; wall slots behind each strip end: bottom z0 + 1 .. z0 + 6, top z1 - 6 .. z1 - 1 (7 x 5 mm).
"""
import csv
import math
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch

OUT = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "img")
PITCH, L = 1000 / 60, 14 * 1000 / 60
R = 80.0
CIRC = 2 * math.pi * R


def strip_info(s):
    k = s % 3
    z_led0 = 11.11 + PITCH / 3 * k
    z0 = z_led0 - PITCH / 2
    return dict(s=s, th=15 * s, set="ABC"[k], z0=z0, z1=z0 + L, chain=s // 12, inverted=(s % 2 == 1), feed=(s % 3 == 0), start=(s % 12 == 0),
                x=15 * s / 360 * CIRC + CIRC / 48)


S = [strip_info(s) for s in range(24)]
jumpers = [(s, s + 1, "top" if s % 2 == 0 else "bottom") for s in range(24) if s % 12 != 11]

fig, ax = plt.subplots(figsize=(16, 8.4))
ax.set_xlim(-6, CIRC + 6); ax.set_ylim(-50, 318); ax.set_aspect("equal"); ax.axis("off")
ax.add_patch(Rectangle((0, 0), CIRC, 250, fc="#1b1b1b", ec="#000"))
ax.text(CIRC / 2, 309, "Rotor tube unwrapped: theta 0 -> 360 deg left to right (seen from OUTSIDE), z up. Strip s at 15 deg x s; sets A / B / C staggered by 5.56 mm.",
        ha="center", fontsize=9)
ax.text(CIRC / 2, 299, "Even strips: arrow UP, input at the bottom.  Odd strips: mounted inverted, arrow DOWN, input at the top.  Jumpers alternate top / bottom (red).",
        ha="center", fontsize=8.5, color="#333")
ax.plot([8, 18], [288, 288], color="#f94144", lw=1.6); ax.text(21, 288, "4-wire jumper, 45 mm ribbon", fontsize=7, va="center")
ax.plot([128, 138], [288, 288], color="#ffb703", lw=1.6); ax.text(141, 288, "feed: 5V + GND, 26 AWG", fontsize=7, va="center")
ax.plot([238, 248], [288, 288], color="#90e0ef", lw=2.2); ax.text(251, 288, "chain start: 5V, GND, CLK, DATA", fontsize=7, va="center")
ax.add_patch(Rectangle((368, 285), 7, 5, fc="none", ec="#aaa", lw=0.6, ls=":")); ax.text(378, 288, "7 x 5 mm wall slot behind the strip end", fontsize=7, va="center")
for st in S:
    x = st["x"]
    col = {"A": "#e63946", "B": "#48cae4", "C": "#80ed99"}[st["set"]]
    ax.add_patch(Rectangle((x - 6, st["z0"]), 12, L, fc="#2f2f2f", ec=col, lw=1.4))
    for i in range(14):
        z = st["z0"] + PITCH / 2 + i * PITCH
        ax.add_patch(Rectangle((x - 2.5, z - 2.5), 5, 5, fc="#777", ec="none"))
    if st["inverted"]:
        ax.add_patch(FancyArrowPatch((x, st["z1"] - 22), (x, st["z0"] + 22), arrowstyle="-|>", mutation_scale=12, color="#f4d35e", lw=1.2))
    else:
        ax.add_patch(FancyArrowPatch((x, st["z0"] + 22), (x, st["z1"] - 22), arrowstyle="-|>", mutation_scale=12, color="#f4d35e", lw=1.2))
    ax.text(x, 125, "%d%s" % (st["s"], st["set"]), ha="center", va="center", fontsize=7.5, color=col, fontweight="bold",
            bbox=dict(fc="#1b1b1b", ec="none", pad=1.0))
    for zs in (st["z0"] + 1.0, st["z1"] - 6.0):
        ax.add_patch(Rectangle((x - 3.5, zs), 7, 5, fc="none", ec="#aaa", lw=0.6, ls=":"))
    if st["inverted"]:
        ax.text(x, st["z1"] - 10.5, "IN", ha="center", fontsize=5.2, color="#f4d35e")
        ax.text(x, st["z0"] + 7.5, "OUT", ha="center", fontsize=5.2, color="#ccc")
    else:
        ax.text(x, st["z0"] + 7.5, "IN", ha="center", fontsize=5.2, color="#f4d35e")
        ax.text(x, st["z1"] - 10.5, "OUT", ha="center", fontsize=5.2, color="#ccc")

for a, b, end in jumpers:
    xa, xb = S[a]["x"], S[b]["x"]
    if end == "top":
        za, zb = S[a]["z1"] - 3.5, S[b]["z1"] - 3.5
        zm = max(za, zb) + 12
    else:
        za, zb = S[a]["z0"] + 3.5, S[b]["z0"] + 3.5
        zm = min(za, zb) - 12
    ax.plot([xa, xa, xb, xb], [za, zm, zm, zb], color="#f94144", lw=1.6)
    ax.text((xa + xb) / 2, zm + (2.0 if end == "top" else -2.0), "%d-%d" % (a, b), ha="center", va="bottom" if end == "top" else "top", fontsize=5.5, color="#f94144")

for st in S:
    if st["feed"]:
        x = st["x"]
        col = "#90e0ef" if st["start"] else "#ffb703"
        ax.plot([x, x], [st["z0"] + 3.5, -20], color=col, lw=2.2 if st["start"] else 1.6)
        if st["start"]:
            ax.text(x, -23, "START %d\n5V GND CLK DATA\nfrom %s" % (st["s"], "J3" if st["s"] == 0 else "J4"), ha="center", va="top", fontsize=6, color="#0077b6")
        else:
            ax.text(x, -23, "feed %d\n5V GND\nfrom J%d" % (st["s"], {3: 6, 6: 7, 9: 8, 15: 9, 18: 10, 21: 11}[st["s"]]), ha="center", va="top", fontsize=6, color="#b36b00")
ax.text(0, -47, "Chain 0: strips 0-11 (theta 0-165 deg) from J3.    Chain 1: strips 12-23 (180-345 deg) from J4.    Feeds every third strip (0, 3, ... 21): one per 45 deg sector, symmetric.",
        fontsize=8, ha="left")
ax.text(CIRC + 4, -49, "fig. elec_harness, 2026-11-02 rev c", fontsize=6, color="#888", ha="right")
for ext in ("svg", "png"):
    fig.savefig(os.path.join(OUT, "elec_harness." + ext), dpi=160 if ext == "png" else None, bbox_inches="tight", facecolor="white")

# ---------------------------------------------------------------- wiring table
rows = []
feed_conn = {0: "J3", 12: "J4", 3: "J6", 6: "J7", 9: "J8", 15: "J9", 18: "J10", 21: "J11"}
feed_len = {0: 200, 12: 200, 3: 150, 6: 200, 9: 200, 15: 150, 18: 150, 21: 150}
for s, c in feed_conn.items():
    st = S[s]
    if st["start"]:
        rows.append(("start lead %d" % s, "carrier %s pins 1-6" % c, "strip %d bottom end: 5V, CI, DI, GND pads" % s, "red / black / orange+black twisted / yellow+black twisted",
                     "26 AWG (5V, GND), 28 AWG (CLK, DATA, 2 x signal GND)", feed_len[s], "through strip %d's bottom slot; the two 28 AWG signal GNDs are spliced into the 26 AWG GND 30 mm before the pad (one wire per pad); 6P screw terminal at the carrier, wires in from below, 28 AWG ends tinned and folded" % s))
    else:
        a, b = (s, s + 1) if s % 2 else (s - 1, s)      # the jumper at strip s's BOTTOM end (odd strips: their output end)
        rows.append(("feed %d" % s, "carrier %s pins 1-2" % c, "strip %d bottom-end 5V and GND pads, as a second wire beside jumper %d-%d's wire (alternative: 3-way splice into that jumper 10-15 mm from the pad)" % (s, a, b),
                     "red / black", "26 AWG silicone", feed_len[s], "solder on the bench with the strip face down: tin both wires, lay them side by side on the pad, one joint; through the bottom slot; 2P screw terminal at the carrier (wires in from the ESP32 side)"))
for a, b, end in jumpers:
    rows.append(("jumper %d-%d" % (a, b), "strip %d %s end: 5V, CO, DO, GND" % (a, end), "strip %d %s end: 5V, CI, DI, GND" % (b, end),
                 "4 consecutive ribbon colours, same order every time: red 5V, orange CLK, yellow DATA, green GND (matches the pad order 5V|C|D|GND, no crossing)",
                 "4 x 28 AWG ribbon (peeled from the rainbow IDC cable)", 45, "through the two %s slots, inside the wall; Kapton over each slot" % end))
rows.append(("hall lead", "carrier J5 pins 1-3 (OUT, GND, 5V), 3P screw terminal, wires in from below", "A3144 legs (flat face toward you, legs down: 1 = VCC, 2 = GND, 3 = OUT)", "white / black / red", "3 x 28 AWG twisted (tin + fold the ends for the clamps)", 120, "through the cap's lead slot, under the sled plate"))
# rev d (2026-11-03): no switch loop (the KCD11 and J2 are gone; the pigtail plug is the on/off)
rows.append(("pigtail", "bank USB-A port (+x)", "carrier J1 screw terminal (straight onto bus A, rev d): red = 5 V, black = GND", "red / black (verify with a meter)", "22 AWG (as bought), 0.28 m; optional inline 3 A fuse holder", 280, "over the bank top, down the -x side, zip-tied to the cradle; rev d: the plug IS the on/off (cap off, plug in, cap on; unplug to stop / charge)"))
rows.append(("motor leads", "PWM OUT+ / OUT-", "motor terminals (C7 100 nF across)", "red / black", "22 AWG", 200, "base only"))
rows.append(("jack leads", "DC jack centre (+) / sleeve (-)", "PWM IN+ / IN-", "red / black", "22 AWG", 150, "base only"))
with open(os.path.join(OUT, "elec_wiring_table.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["wire", "from", "to", "colour", "gauge / type", "cut length mm", "route / note"])
    w.writerows(rows)
print("wrote elec_harness.svg/.png + elec_wiring_table.csv (%d rows)" % len(rows))
