"""Phase-0 test rig for the wiring guide (section 1): the carrier's chain-0 circuit on a breadboard. DevKit on USB (VIN open),
74AHCT125 channels 1 and 2 with 10 k pull-downs, 68 R series resistors, a six-position terminal with J3's pin order, the bench
supply on the rails with a bulk capacitor, test strip T on a ribbon lead. Wiring diagram, not a breadboard layout.

  py software/elec/guide/fig_rig.py   -> docs/img/guide_rig.svg / .png
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import matplotlib.pyplot as plt                       # noqa: E402
from matplotlib.patches import Circle, Polygon, Rectangle   # noqa: E402

from guide_common import WC, box, note, save, stamp, wire   # noqa: E402

TOP, BOT = 56.0, 4.0          # + rail, - rail


def resistor(ax, x0, y0, x1, y1, label, z=7):
    """A resistor body on the segment (x0,y0)-(x1,y1), leads in grey."""
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    horiz = abs(x1 - x0) > abs(y1 - y0)
    ax.plot([x0, x1], [y0, y1], color="#777", lw=1.0, zorder=z - 1)
    w, h = (4.2, 1.5) if horiz else (1.5, 4.2)
    ax.add_patch(Rectangle((mx - w / 2, my - h / 2), w, h, fc="#f1e3c6", ec="#7f4f24", lw=0.8, zorder=z))
    ax.text(mx + (0 if horiz else 1.4), my + (1.4 if horiz else 0), label, fontsize=6.0, ha="center" if horiz else "left",
            va="bottom" if horiz else "center", zorder=z + 1)


def buffer(ax, x, y, name, pin_in, pin_out):
    ax.add_patch(Polygon([(x, y - 2.6), (x, y + 2.6), (x + 5.0, y)], closed=True, fc="#fff", ec="#222", lw=1.0, zorder=5))
    ax.text(x + 1.6, y, name, fontsize=5.6, va="center", zorder=6)
    ax.text(x - 0.4, y + 0.9, "pin %d" % pin_in, fontsize=5.6, ha="right", va="bottom", color="#1d3557", fontweight="bold")
    ax.text(x + 5.4, y + 0.9, "pin %d" % pin_out, fontsize=5.6, ha="left", va="bottom", color="#1d3557", fontweight="bold")


def main():
    fig, ax = plt.subplots(figsize=(12.5, 7.4))
    ax.set_xlim(-2, 133)
    ax.set_ylim(-4, 66)
    ax.axis("off")
    ax.text(-1, 65.5, "Phase-0 test rig (section 1): the carrier's chain-0 circuit on a breadboard; the terminal has J3's pin order",
            fontsize=10, fontweight="bold", va="top")
    ax.text(-1, 62.6, "Supply 5.00 V, limit 0.30 A (1.0 A only for the E9 white test).  The DevKit runs from USB: its VIN pin stays OPEN.  "
            "Grounds common.  Wiring diagram, not to scale.", fontsize=7.0, va="top", color="#333")
    # rails
    wire(ax, [(8, TOP), (123, TOP)], "red", lw=2.6, z=3)
    wire(ax, [(8, BOT), (123, BOT)], "black", lw=2.6, z=3)
    ax.text(123.8, TOP, "+5 V rail", fontsize=6.6, va="center", color=WC["red"], fontweight="bold")
    ax.text(123.8, BOT, "GND rail", fontsize=6.6, va="center", fontweight="bold")
    # bench supply
    box(ax, -1, 46, 8.5, 9.5, "bench\nsupply\n5.00 V\n0.30 A", fc="#eef2ff", ec="#334", fs=6.2)
    wire(ax, [(7.5, 53.5), (8, TOP)], "red", lw=2.2)
    wire(ax, [(3.0, 46), (3.0, 20), (8, BOT)], "black", lw=2.2)
    # DevKit (right header only matters), USB at the bottom
    ax.add_patch(Rectangle((11, 12), 15, 38, fc="#1f3b57", ec="#000", lw=1.0, zorder=4))
    ax.add_patch(Rectangle((16, 9.6), 5, 3.4, fc="#999", ec="#333", lw=0.8, zorder=5))
    ax.text(18.5, 8.6, "micro-USB -> PC", fontsize=6.0, ha="center", va="top")
    ax.text(13.6, 31, "spare DevKit (30-pin), phase-0 flashed", fontsize=6.2, color="white", ha="center", va="center", zorder=6,
            rotation=90)
    hdr = ["3V3", "GND", "D15", "D2", "D4", "RX2", "TX2", "D5", "D18", "D19", "D21", "RX0", "TX0", "D22", "D23"]
    for i, nm in enumerate(hdr):
        y = 13.8 + i * 2.45
        used = nm in ("GND", "D18", "D23")
        ax.add_patch(Circle((24.6, y), 0.55, fc="#ffd60a" if used else "#cfd4da", ec="#333", lw=0.4, zorder=6))
        ax.text(23.6, y, "%d %s" % (i + 1, nm), fontsize=4.8, color="white" if not used else "#ffd60a", ha="right", va="center", zorder=6,
                fontweight="bold" if used else "normal")
    ax.text(12.0, 13.6, "VIN\n(OPEN)", fontsize=5.0, color="#ff8080", va="center", zorder=6, fontweight="bold")
    yg, y18, y23 = 13.8 + 1 * 2.45, 13.8 + 8 * 2.45, 13.8 + 14 * 2.45
    wire(ax, [(25.2, yg), (29, yg), (29, BOT)], "black", lw=1.8)
    # buffers
    bx, yc, yd = 46, 40.0, 24.0
    wire(ax, [(25.2, y18), (36, y18), (36, yc), (bx, yc)], "yellow", lw=1.8)
    wire(ax, [(25.2, y23), (33, y23), (33, 46), (40, 46), (40, yd + 6), (43, yd + 6), (43, yd), (bx, yd)], "orange", lw=1.8)
    buffer(ax, bx, yc, "1A>1Y", 2, 3)
    buffer(ax, bx, yd, "2A>2Y", 5, 6)
    ax.text(bx + 2.5, 47.5, "U1  74AHCT125 (spare)", fontsize=7.0, ha="center", fontweight="bold")
    # pull-downs on the inputs
    resistor(ax, 38.5, yc, 38.5, BOT, "10k", z=7)
    ax.plot([38.5, 36], [yc, yc], color="#777", lw=1.0)
    resistor(ax, 44.0, yd, 44.0, BOT, "10k", z=7)
    # series resistors and the outputs
    wire(ax, [(bx + 5, yc), (60, yc)], "yellow", lw=1.8)
    resistor(ax, 60, yc, 68, yc, "68 R")
    wire(ax, [(68, yc), (78, yc), (78, 33.2), (86, 33.2)], "yellow", lw=1.8)
    wire(ax, [(bx + 5, yd), (60, yd)], "orange", lw=1.8)
    resistor(ax, 60, yd, 68, yd, "68 R")
    wire(ax, [(68, yd), (78, yd), (78, 28.4), (86, 28.4)], "orange", lw=1.8)
    # U1 power box
    box(ax, 50.5, 6.5, 24, 13.5, "", fc="#f7f7f7", ec="#555", fs=6)
    note(ax, 51.5, 19.4, "U1 power and unused pins:\n  pin 14 VCC -> +5 V rail\n  pin 7 GND -> GND rail\n  100 nF straight across 14 - 7\n"
         "  pins 1, 4, 10, 13 (/OE) -> GND\n  pins 9, 12 (unused inputs) -> GND", fs=6.0)
    # DIP pinout inset
    ix, iy = 52, 50.5
    ax.add_patch(Rectangle((ix, iy - 0.4), 7.0, 4.6 + 0.4, fc="#3a3a3a", ec="#000", lw=0.6, zorder=4))
    ax.add_patch(Circle((ix + 3.5, iy + 4.2), 0.55, fc="white", ec="none", zorder=5))
    ax.text(ix + 3.5, iy + 1.7, "notch up", fontsize=4.6, color="white", ha="center", va="center", zorder=5)
    ax.text(ix - 0.4, iy + 3.6, "1", fontsize=5.2, ha="right", va="center", fontweight="bold")
    ax.text(ix - 0.4, iy + 0.0, "7", fontsize=5.2, ha="right", va="center")
    ax.text(ix + 7.4, iy + 0.0, "8", fontsize=5.2, ha="left", va="center")
    ax.text(ix + 7.4, iy + 3.6, "14", fontsize=5.2, ha="left", va="center", fontweight="bold")
    ax.text(ix + 10.5, iy + 1.9, "pin 1 next to the notch;\n1-7 down the left,\n8-14 up the right", fontsize=5.4, va="center")
    # terminal block (J3 twin)
    tx = 86
    ax.add_patch(Rectangle((tx, 23.5), 10.0, 17.5, fc="#2e7d32", ec="#1b5e20", lw=0.9, zorder=4))
    rows = {1: 38.0, 2: 35.6, 3: 33.2, 4: 30.8, 5: 28.4, 6: 26.0}
    names = {1: "1  5V", 2: "2  GND", 3: "3  CLK", 4: "4  GND", 5: "5  DATA", 6: "6  GND"}
    for k, y in rows.items():
        ax.add_patch(Rectangle((tx + 0.5, y - 0.5), 1.4, 1.0, fc="#c9ccd1", ec="#555", lw=0.4, zorder=5))
        ax.text(tx + 2.6, y, names[k], fontsize=5.8, va="center", color="white", zorder=6, fontweight="bold")
    ax.text(tx + 7.5, 41.6, "6-position terminal\n= J3 twin", fontsize=6.2, ha="center", va="bottom", fontweight="bold")
    wire(ax, [(tx + 0.5, rows[1]), (83, rows[1]), (83, TOP)], "red", lw=1.8)
    for k in (2, 4, 6):
        wire(ax, [(tx + 0.5, rows[k]), (81.5, rows[k]), (81.5, BOT)], "black", lw=1.4)
    # bulk cap
    ax.add_patch(Rectangle((117.0, 10), 4.5, 7, fc="#cdb4db", ec="#3d2b56", lw=0.8, zorder=5))
    ax.text(119.25, 13.5, "100-\n1000 uF", fontsize=5.0, ha="center", va="center", zorder=6)
    wire(ax, [(119.25, 17), (119.25, TOP)], "red", lw=1.4)
    wire(ax, [(119.25, 10), (119.25, BOT)], "black", lw=1.4)
    ax.text(116.4, 8.6, "stripe (-) to GND", fontsize=5.4, ha="right", va="center")
    # test strip T with its lead
    sx = 107
    ax.add_patch(Rectangle((sx, 22), 6.0, 34, fc="#2b2b2b", ec="#000", lw=0.8, zorder=4))
    for i in range(7):
        ax.add_patch(Rectangle((sx + 1.4, 24.5 + i * 4.4), 3.2, 3.2, fc="#f8f9fa", ec="#999", lw=0.4, zorder=5))
    ax.text(sx + 3.0, 57.5, "test strip T\n(14-LED spare)", fontsize=6.0, ha="center", va="bottom", fontweight="bold")
    ax.text(sx + 3.0, 20.8, "IN end, lead\nT-IN 150 mm", fontsize=5.6, ha="center", va="top")
    for i, (col, k) in enumerate((("red", 1), ("green", 2), ("yellow", 3), ("orange", 5))):
        xr = tx + 11.2 + i * 0.9
        wire(ax, [(tx + 10.0, rows[k]), (xr, rows[k]), (xr, 23.6 - i * 0.6), (sx + 0.6, 23.6 - i * 0.6)], col, lw=1.3, z=8)
    note(ax, 61, -1.0, "Lead into the terminal: red -> 1, green -> 2, yellow -> 3 (CLK), orange -> 5 (DATA) (4 and 6 empty).  The same terminal later takes "
         "S0 / S12 (pin for pin as J3), the PROBE lead and the chain on the tube.", fs=6.2, ha="center")
    stamp(ax, 132, -3.8, "guide_rig")
    save(fig, "guide_rig")


if __name__ == "__main__":
    main()
