"""System block diagram for the electrical report -> docs/img/elec_block.svg/.png. Run: py software/elec/elec_block.py"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "img")
os.makedirs(OUT, exist_ok=True)

fig, ax = plt.subplots(figsize=(13, 8.2))
ax.set_xlim(0, 130); ax.set_ylim(0, 82); ax.axis("off")


def box(x, y, w, h, text, fc="#f7f7f7", ec="#333", lw=1.2, fs=9.5, bold=False, ls="-"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.2", fc=fc, ec=ec, lw=lw, ls=ls))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, fontweight="bold" if bold else "normal", linespacing=1.25)


def arrow(x0, y0, x1, y1, text=None, color="#333", lw=1.6, style="-|>", off=(0, 1.6), fs=8.2, ls="-"):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle=style, mutation_scale=14, color=color, lw=lw, ls=ls))
    if text:
        ax.text((x0 + x1) / 2 + off[0], (y0 + y1) / 2 + off[1], text, ha="center", va="bottom", fontsize=fs, color=color)


# ---------------------------------------------------------------- rotor
ax.add_patch(FancyBboxPatch((2, 24), 126, 56, boxstyle="round,pad=0.6,rounding_size=2", fc="none", ec="#1f4e79", lw=1.8, ls="--"))
ax.text(4, 78.5, "ROTOR (spins at 225 rpm; everything below the dashed line is the stationary base)", fontsize=10.5, color="#1f4e79", fontweight="bold", va="center")

box(4, 60, 22, 14, "BT1  INIU BI-B61\n10 Ah power bank\nUSB-A port: 5 V, 2.4 A\n(on the spin axis)", fc="#e8f1fb", bold=False)
box(30, 63, 34, 8, "USB-A pigtail, 22 AWG, 0.28 m + F1 3 A\nplug in = ON, unplug = OFF / charge (no switch)", fc="#fff", fs=8.4)
box(71, 56, 54, 21, "CARRIER BOARD (70 x 90 mm perfboard on the sled)\nJ1 5 V in (screw terminal)  ->  5 V bus A | LK1 | bus B\nC1, C2 1000 uF   ·   U1 74AHCT125 level shifter (5 V)   ·   R1-R4 68 R\nR9 10 k pull-up + C4 1 nF (hall)   ·   30-pin ESP32 soldered direct", fc="#fdf6e3", fs=9)
box(74, 32, 30, 16, "U2  ESP32 DOIT DevKit V1 (30-pin)\nVIN pin <- bus A (no series diode)\nVSPI: GPIO 23 DATA0, 18 CLK0\nHSPI: GPIO 13 DATA1, 14 CLK1\nGPIO 27 <- hall (3.3 V pull-up)", fc="#eef7ee", fs=8.8)
box(8, 30, 26, 18, "CHAIN 0: strips 0-11\n(theta 0-165 deg, 168 LEDs)\nserpentine: even strips data up,\nodd strips inverted; 11 jumpers\nfeeds at strips 0, 3, 6, 9", fc="#fff5f5", fs=8.8)
box(38, 30, 26, 18, "CHAIN 1: strips 12-23\n(theta 180-345 deg, 168 LEDs)\nsame pattern\nfeeds at strips 12, 15, 18, 21", fc="#fff5f5", fs=8.8)
box(108, 32, 18, 12, "U4  A3144 hall\nin the bottom cap\nr 42, theta 90 deg\n5 V, open collector", fc="#eef7ee", fs=8.5)

arrow(26, 67, 30, 67)
arrow(65, 67, 71, 67, "5 V", off=(0, 1.2))
arrow(98, 56, 98, 48, "5 V, GPIOs", off=(7, -2))
arrow(74, 48, 64, 48, "J4: 5V-B, GND,\nCLK1, DATA1 (twisted + GND)", color="#8b0000", off=(0, 1.5))
arrow(74, 52, 34, 52, "J3: 5V-A, GND, CLK0, DATA0", color="#8b0000", off=(-4, 1.2))
arrow(80, 56, 46, 50, "J9-J11: 3 x (5V-B, GND) feeds", color="#c00", style="-|>", off=(6, 2.5), ls=":")
arrow(78, 56, 16, 50, "J6-J8: 3 x (5V-A, GND) feeds", color="#c00", off=(-8, 2.5), ls=":")
arrow(117, 44, 117, 56, "J5: 5 V, GND, OUT", off=(7.5, -3))
ax.text(21, 25.8, "Nothing crosses the rotating joint electrically: no slip ring, no wire. The base talks to the rotor only through the magnet's field.", fontsize=8.8, color="#1f4e79", style="italic", ha="left")

# ---------------------------------------------------------------- base
ax.add_patch(FancyBboxPatch((2, 2), 126, 19, boxstyle="round,pad=0.6,rounding_size=2", fc="none", ec="#555", lw=1.8, ls="--"))
ax.text(4, 19.6, "BASE (stationary; 12 V system, galvanically separate from the rotor)", fontsize=10.5, color="#444", fontweight="bold", va="center")
box(4, 5, 20, 10, "12 V in: wall adapter\n(2 A) or bench supply\nvia J13 DC jack 5.5/2.1\ncentre positive", fc="#f3f3f3", fs=8.5)
box(32, 5, 24, 10, "U5  PWM speed controller\n(kit's CCM6N / 1203B class)\nIN+ IN-  ->  OUT+ OUT-\nknob on the front flat", fc="#f3f3f3", fs=8.5)
box(64, 5, 22, 10, "M1  JGB37-520 gearmotor\n12 V, 600 rpm no-load\nC7 100 nF across the terminals\n~0.3 A at 225 rpm, 1.65 A stall", fc="#f3f3f3", fs=8.5)
box(96, 5, 30, 10, "B06  two 6 x 3 mm magnets\nin the deck at r 42, theta 90 deg\n5.0 mm gap to the hall face\n(field only: no conductor)", fc="#f3f3f3", fs=8.5)
arrow(24, 10, 32, 10, "22 AWG", off=(0, 1))
arrow(56, 10, 64, 10, "22 AWG", off=(0, 1))
arrow(111, 15, 117, 32, "magnetic field\nonce per revolution", color="#1f4e79", style="-|>", ls="--", off=(10, -4))
ax.text(126, 1.0, "fig. elec_block, 2026-11-03 rev d (no switch)", fontsize=7, color="#888", ha="right")

for ext in ("svg", "png"):
    fig.savefig(os.path.join(OUT, "elec_block." + ext), dpi=160 if ext == "png" else None, bbox_inches="tight", facecolor="white")
print("wrote elec_block.svg/.png")
