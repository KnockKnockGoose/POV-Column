"""Per-wire strip harness drawings (rev g, 2026-11-03).

  py software/elec/elec_harness_detailed.py            -> both figures
  py software/elec/elec_harness_detailed.py closeup    -> docs/img/elec_harness_strips0-2.png/.svg   (strips 0-3, J3 start, feed 3)
  py software/elec/elec_harness_detailed.py full       -> docs/img/elec_harness_detailed.png/.svg/.pdf (all 24 strips, carrier inset, cut list)

Every conductor is drawn on its own: the four ribbon wires of each jumper, the six wires of each start lead (with the twisted
CLK / DATA pairs and the splice of their black returns into the 26 AWG GND), each feed's red + black pair, the hall lead.
Cut lengths and gauges are read from docs/img/wiring_cut_list.csv (written by calc/wiring_cut_list.py from the CAD routes).

Drawing conventions (schematic, not to scale along the tube):
  * The tube is unwrapped and seen from OUTSIDE, theta 0 -> 360 deg left to right; strip s at 15 deg x s, set k = s mod 3 (A/B/C).
  * Strip ends are drawn near scale (pads, the 10 x 5 mm rev g wall slot 1 mm above the cut line, pad zone 0.5-3.0 mm), the middle
    of each strip is broken out. The pads are on the strip's BACK, drawn seen through the strip.
  * Pad order 5V | CLK | DATA | GND left to right on an upright (even) strip seen from outside - ASSUMED (electrical E15), check the
    printed pad order. An inverted (odd) strip reads GND | DATA | CLK | 5V from the same side, so every jumper is mirrored (the ribbon
    makes a half turn): match colour to the pad label, never to position.
  * Beyond the slot every wire runs INSIDE the tube wall; the drawing pulls those runs out past the strip ends so each one can be seen.
  * Colours (Brian, 2026-11-03): single wires red = 5V, black = GND, orange = CLK, yellow = DATA; ribbon red / orange / yellow /
    green with green = GND in the ribbon only.
"""
import csv
import math
import os
import re
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Polygon, Rectangle, FancyBboxPatch

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(HERE, "..", "..", "docs", "img")
REV = "rev g"
DATE = "2026-11-03"

WC = {"red": "#d62828", "black": "#151515", "orange": "#f77f00", "yellow": "#ffd60a", "green": "#2b9348", "white": "#ffffff"}
SET_COL = {"A": "#c1121f", "B": "#0077b6", "C": "#2d6a4f"}
NET_RIBBON = {"5V": "red", "C": "orange", "D": "yellow", "GND": "green"}
PAD_OFF = [-3.7, -1.233, 1.233, 3.7]          # pad centres across the strip, mm (9.0 mm outer span assumed, E15)
FEED_J = {3: "J6", 6: "J7", 9: "J8", 15: "J9", 18: "J10", 21: "J11"}
START_J = {0: "J3", 12: "J4"}


# ------------------------------------------------------------------------------------------------ data
def load_cuts():
    rows = list(csv.DictReader(open(os.path.join(IMG, "wiring_cut_list.csv"), encoding="utf-8")))
    cut = {r["item"]: int(float(r["cut length mm (CAD)"])) for r in rows}
    bench = {}
    for r in rows:
        if r["item"].startswith("jumper"):
            a, b = map(int, r["item"].split()[1].split("-"))
            m = re.match(r"strip (\d+)", r["from"])
            bench[(a, b)] = int(m.group(1)) if m else a
    pig = None
    for r in csv.DictReader(open(os.path.join(IMG, "elec_wiring_table.csv"), encoding="utf-8")):
        if r["wire"] == "pigtail":
            pig = r["cut length mm (electrical report, before the wiring CAD)"]
    return rows, cut, bench, pig


ROWS, CUT, BENCH, PIG_BOUGHT = load_cuts()
JUMPERS = [(s, s + 1, "top" if s % 2 == 0 else "bottom") for s in range(24) if s % 12 != 11]


def start_cuts(s):
    p = CUT["start lead %d power pair" % s]
    g = CUT["start lead %d signal wires" % s]
    return dict(pow=p, sig=g, ret=g - 30)


# ------------------------------------------------------------------------------------------------ drawing primitives
def wire(ax, pts, col, lw, z=6, ls="-"):
    xs, ys = zip(*pts)
    out = "#555555" if col in ("black",) else "#222222"
    ax.plot(xs, ys, color=WC[col], lw=lw, ls=ls, solid_capstyle="round", solid_joinstyle="round", zorder=z,
            path_effects=[pe.Stroke(linewidth=lw + 3.2, foreground="white"), pe.Stroke(linewidth=lw + 1.3, foreground=out), pe.Normal()])


def twisted(ax, xc, y0, y1, cols, amp, period, lw, z=6):
    """Two conductors twisted about a vertical centreline xc from y0 to y1 (drawn as interleaved sines)."""
    n = 200
    for i, col in enumerate(cols):
        pts = []
        for j in range(n + 1):
            y = y0 + (y1 - y0) * j / n
            ph = 2 * math.pi * (y - y0) / period + (math.pi if i else 0.0)
            pts.append((xc + amp * math.sin(ph), y))
        wire(ax, pts, col, lw, z=z + i)


def label(ax, x, y, txt, fs, rot=0, col="#111", ha="center", va="center", z=20, bg="white", weight="normal", alpha=0.92):
    ax.text(x, y, txt, fontsize=fs, rotation=rot, color=col, ha=ha, va=va, zorder=z, fontweight=weight,
            bbox=None if bg is None else dict(fc=bg, ec="none", pad=0.6, alpha=alpha))


class Strip:
    """Geometry of one strip in drawing units. S = drawing units per mm at the strip ends."""

    def __init__(self, s, x, yb, S, H1, G):
        self.s, self.x, self.S = s, x, S
        self.k = s % 3
        self.set = "ABC"[self.k]
        self.inv = s % 2 == 1
        self.yb = yb
        self.H1, self.G = H1, G
        self.yt = yb + 2 * H1 + G
        self.W = 12.0 * S

    def pads(self):
        order = ["5V", "C", "D", "GND"]
        if self.inv:
            order = order[::-1]
        return {n: self.x + PAD_OFF[i] * self.S for i, n in enumerate(order)}

    def end_is_in(self, end):
        return (end == "bottom") != self.inv

    def slot_edge(self, end):          # where a wire leaves the strip back into the wall (far edge of the slot)
        return self.yb + 6 * self.S if end == "bottom" else self.yt - 6 * self.S

    def cut(self, end):
        return self.yb if end == "bottom" else self.yt


def draw_strip(ax, st, fs, pad_labels=True, theta=True, small=False):
    S, x, W = st.S, st.x, st.W
    col = SET_COL[st.set]
    yb, yt, H1, G = st.yb, st.yt, st.H1, st.G
    # body: two sections with a break
    for (y0, y1) in ((yb, yb + H1), (yt - H1, yt)):
        ax.add_patch(Rectangle((x - W / 2, y0), W, y1 - y0, fc="#fbfbf7", ec=col, lw=1.6, zorder=2))
    zig = []
    n = 6
    for i in range(n + 1):
        zig.append((x - W / 2 + W * i / n, yb + H1 + (6 if i % 2 else -6) * S / 8))
    ax.plot(*zip(*zig), color=col, lw=1.0, zorder=3)
    zig2 = [(px, py + G) for px, py in zig]
    ax.plot(*zip(*zig2), color=col, lw=1.0, zorder=3)
    ax.add_patch(Rectangle((x - W / 2, yb + H1 + 2), W, G - 4, fc="#fbfbf7", ec="none", zorder=1, alpha=0.5))
    # LEDs (front face), faint
    for e in ("bottom", "top"):
        c = st.cut(e)
        sg = 1 if e == "bottom" else -1
        for d in (8.33, 25.0):
            if d * S < H1 - 2.5 * S:
                yc = c + sg * d * S
                ax.add_patch(Rectangle((x - 2.5 * S, yc - 2.5 * S), 5 * S, 5 * S, fc="#eeeeee", ec="#cfcfcf", lw=0.6, zorder=2))
    # slots (behind the strip end, 10 x 5 mm, 1 mm above the cut line) and pads (back side, seen through)
    for e in ("bottom", "top"):
        c = st.cut(e)
        sg = 1 if e == "bottom" else -1
        y0 = c + sg * 1.0 * S
        ax.add_patch(Rectangle((x - 5 * S, min(y0, y0 + sg * 5 * S)), 10 * S, 5 * S, fc="none", ec="#6c757d", lw=1.0, ls=(0, (3, 2)), zorder=3))
        pz0, pz1 = c + sg * 0.5 * S, c + sg * 3.0 * S
        for n, px in st.pads().items():
            ax.add_patch(Rectangle((px - 0.8 * S, min(pz0, pz1)), 1.6 * S, 2.5 * S, fc="#d4a373", ec="#7f5539", lw=0.8, ls=(0, (2, 1)), zorder=4))
        if pad_labels:
            isin = st.end_is_in(e)
            names = {"5V": "5V", "C": "CI" if isin else "CO", "D": "DI" if isin else "DO", "GND": "GND"}
            ly = c + sg * (12.5 if not small else 11.5) * S
            for n, px in st.pads().items():
                ax.plot([px, px], [c + sg * 6.4 * S, ly - sg * 2.2 * S], color="#999", lw=0.5, ls=":", zorder=4)
                label(ax, px, ly, names[n], fs * 0.85, rot=90, col="#7f5539", z=8, weight="bold")
    # arrow + IN/OUT + number
    ya, yz = yb + H1 * 0.62, yt - H1 * 0.62
    if st.inv:
        ya, yz = yz, ya
    ax.add_patch(FancyArrowPatch((x, ya), (x, yz), arrowstyle="-|>", mutation_scale=fs * 2.2, color="#e09f3e", lw=fs * 0.25, zorder=7))
    for e in ("bottom", "top"):
        c = st.cut(e)
        sg = 1 if e == "bottom" else -1
        isin = st.end_is_in(e)
        txt = ("IN" if isin else "OUT")
        label(ax, x + W / 2 + 1.0 * S, c + sg * 17 * S, txt, fs * 1.05, ha="left", col="#b5651d" if isin else "#555", weight="bold", bg=None)
    label(ax, x, (yb + yt) / 2, "%d%s" % (st.s, st.set), fs * 1.6, col=col, weight="bold", z=9)
    if theta:
        label(ax, x, yt + (st.S * 3.0), "", 1, bg=None)


def strip_end_note(ax, st, end, fs, side="right", dx=None):
    """Text block beside a strip end: pad order left->right as seen from outside."""
    isin = st.end_is_in(end)
    names = {"5V": "5V", "C": "CI" if isin else "CO", "D": "DI" if isin else "DO", "GND": "GND"}
    order = sorted(st.pads().items(), key=lambda kv: kv[1])
    txt = "pads L->R: " + " | ".join(names[n] for n, _ in order)
    c = st.cut(end)
    sg = 1 if end == "bottom" else -1
    x = st.x + st.W / 2 + 1.0 * st.S if dx is None else st.x + dx
    label(ax, x, c + sg * 25.5 * st.S, txt, fs * 0.8, ha="left", col="#444", bg="white")


def jumper_wires(ax, A, B, end, cut_mm, fs, base, gap, lw, labels=True, stub_to=None, bench=None, shift=0.0, short=False):
    """The four ribbon wires of jumper A->B at `end`, drawn as nested U's (the mirrored pad order makes them nest without crossing)."""
    pa, pb = A.pads(), B.pads() if B is not None else None
    sg = -1 if end == "bottom" else 1
    if B is not None:
        edge = min(A.cut(end), B.cut(end)) if end == "bottom" else max(A.cut(end), B.cut(end))
        order = sorted(["5V", "C", "D", "GND"], key=lambda n: pb[n] - pa[n])
    else:
        edge = A.cut(end)
        order = sorted(["5V", "C", "D", "GND"], key=lambda n: -pa[n])
    for rank, n in enumerate(order):
        lev = edge + sg * (base + rank * gap)
        xa = pa[n]
        if B is not None:
            xb = pb[n]
            pts = [(xa, A.slot_edge(end)), (xa, lev), (xb, lev), (xb, B.slot_edge(end))]
        else:
            xb = stub_to
            pts = [(xa, A.slot_edge(end)), (xa, lev), (xb, lev)]
        wire(ax, pts, NET_RIBBON[n], lw, z=6 + rank)
        ax.plot([xa], [A.cut(end) - sg * 1.75 * A.S], "o", ms=lw * 1.3, color="#adb5bd", mec="#495057", zorder=12)
        if B is not None:
            ax.plot([xb], [B.cut(end) - sg * 1.75 * B.S], "o", ms=lw * 1.3, color="#adb5bd", mec="#495057", zorder=12)
        if labels:
            nm = {"5V": "5V", "C": "CLK", "D": "DATA", "GND": "GND"}[n]
            xm = (xa + xb) / 2 if B is not None else (xa + xb) / 2
            label(ax, xm + shift, lev, ("%s %s 28AWG %d" if short else "%s %s 28 AWG %d") % (NET_RIBBON[n], nm, cut_mm), fs, z=21)
    return order


def loop_mark(ax, st, end, fs, text=True):
    """Hairpin glyph for the second-soldered (loop) end: 27 mm pulled out, pushed back as a loop up / down the wall."""
    S = st.S
    sg = 1 if end == "bottom" else -1
    c = st.cut(end)
    x0 = st.x - st.W / 2 - 3.2 * S
    y0 = c + sg * 2 * S
    h = 13 * S
    pts = [(x0, y0), (x0, y0 + sg * h), (x0 - 1.6 * S, y0 + sg * (h + 1.6 * S / S * 1.6)), (x0 - 3.2 * S, y0 + sg * h), (x0 - 3.2 * S, y0)]
    ax.plot(*zip(*pts), color="#6a4c93", lw=2.0, zorder=11)
    if text:
        label(ax, x0 - 1.6 * S, y0 + sg * (h + 4.5 * S), "LOOP\nend", fs * 0.75, col="#6a4c93", weight="bold", bg="white")


def bench_mark(ax, st, end, fs):
    S = st.S
    sg = 1 if end == "bottom" else -1
    c = st.cut(end)
    label(ax, st.x - st.W / 2 - 3.5 * S, c + sg * 9 * S, "BENCH\nend", fs * 0.75, col="#1d3557", weight="bold", bg="white")


def feed_wires(ax, st, y_tag, cut_mm, fs, lw, jname, labels=True, tag=True):
    pads = st.pads()
    pitch = abs(PAD_OFF[1] - PAD_OFF[0]) * st.S
    out = {}
    for n, col, pin in (("5V", "red", 1), ("GND", "black", 2)):
        px = pads[n]
        dx = 0.42 * pitch * (1 if px > st.x else -1)
        x = px + dx
        wire(ax, [(x, st.slot_edge("bottom")), (x, y_tag)], col, lw, z=10)
        ax.plot([px], [st.yb + 1.75 * st.S], "o", ms=lw * 1.5, color="#adb5bd", mec="#495057", zorder=12)
        out[n] = x
        if labels:
            label(ax, x, y_tag + 0.36 * (st.yb - y_tag), "%s %s 26 AWG %d" % ("5V" if n == "5V" else "GND", col, cut_mm), fs, rot=90, z=22)
        if tag:
            label(ax, x, y_tag - fs * 1.3, "%s.%d" % (jname, pin), fs, col="#222", weight="bold", bg="#e9ecef", alpha=1)
    return out


def start_lead(ax, st, y_pins, f, fs, lw26, lw28, cuts, jname, block=False):
    """Six wires J?.1-6 -> strip bottom pads. f scales the fan-out geometry (1.0 = close-up)."""
    P = 55 * f
    pads = st.pads()
    ys = st.slot_edge("bottom")
    x0 = st.x
    pin = {i + 1: x0 - (6 - i) * P for i in range(6)}
    D = ys - y_pins
    r = lambda d: ys - d * D / 738.0
    # levels (close-up reference, rel to the slot edge, scaled with D)
    y_red, y_gnd, y_or, y_ye = r(168), r(198), r(248), r(268)
    y_untw, y_cb, y_db, y_spl = r(348), r(308), r(328), r(138)
    x_gp = pads["GND"]
    # power pair
    wire(ax, [(pin[1], y_pins), (pin[1], y_red), (pads["5V"], y_red), (pads["5V"], ys)], "red", lw26, z=8)
    wire(ax, [(pin[2], y_pins), (pin[2], y_gnd), (x_gp, y_gnd), (x_gp, ys)], "black", lw26, z=9)
    # twisted pairs
    xc_c, xc_d = (pin[3] + pin[4]) / 2, (pin[5] + pin[6]) / 2
    y_tw0 = y_pins + 0.07 * D
    amp, per = 0.22 * P, 0.11 * D
    for (pa_, pb_, xc, sig, ret) in ((pin[3], pin[4], xc_c, "orange", "black"), (pin[5], pin[6], xc_d, "yellow", "black")):
        wire(ax, [(pa_, y_pins), (xc - amp, y_tw0)], sig, lw28, z=10)
        wire(ax, [(pb_, y_pins), (xc + amp, y_tw0)], ret, lw28, z=10)
        twisted(ax, xc, y_tw0, y_untw, [sig, ret], amp, per, lw28, z=10)
    # untwisted ends
    xo, xcb = xc_c - amp, xc_c + amp
    xy, xdb = xc_d - amp, xc_d + amp
    wire(ax, [(xo, y_untw), (xo, y_or), (pads["C"], y_or), (pads["C"], ys)], "orange", lw28, z=12)
    wire(ax, [(xy, y_untw), (xy, y_ye), (pads["D"], y_ye), (pads["D"], ys)], "yellow", lw28, z=12)
    xs1, xs2 = x_gp + 30 * f, x_gp + 45 * f
    wire(ax, [(xcb, y_untw), (xcb, y_cb), (xs1, y_cb), (xs1, y_spl), (x_gp, y_spl)], "black", lw28, z=13)
    wire(ax, [(xdb, y_untw), (xdb, y_db), (xs2, y_db), (xs2, y_spl - 6 * f), (x_gp, y_spl - 6 * f)], "black", lw28, z=13)
    # splice: heat-shrink sleeve + dot
    ax.add_patch(Rectangle((x_gp - 7 * f - 3, y_spl - 22 * f), 14 * f + 6, 34 * f, fc="#adb5bd", ec="#343a40", lw=1.0, alpha=0.75, zorder=15))
    ax.plot([x_gp], [y_spl - 3 * f], "o", ms=lw26 * 1.9, color="#ced4da", mec="#111", mew=1.2, zorder=16)
    for n in ("5V", "C", "D", "GND"):
        ax.plot([pads[n]], [st.yb + 1.75 * st.S], "o", ms=lw26 * 1.2, color="#adb5bd", mec="#495057", zorder=17)
    # labels
    label(ax, pin[1], (y_pins + y_red) / 2, "5V red 26 AWG %d" % cuts["pow"], fs, rot=90, z=22)
    label(ax, pin[2], (y_pins + y_gnd) / 2 - 0.05 * D, "GND black 26 AWG %d" % cuts["pow"], fs, rot=90, z=22)
    label(ax, xc_c, (y_tw0 + y_untw) / 2, "CLK pair: orange 28 AWG %d\n+ black return 28 AWG %d" % (cuts["sig"], cuts["ret"]), fs * 0.92, rot=90, z=22)
    label(ax, xc_d, (y_tw0 + y_untw) / 2, "DATA pair: yellow 28 AWG %d\n+ black return 28 AWG %d" % (cuts["sig"], cuts["ret"]), fs * 0.92, rot=90, z=22)
    return dict(pin=pin, y_spl=y_spl, x_gp=x_gp, xs2=xs2)


def j_block(ax, x_left, y_top, pitch, nets, jname, title, fs, numbers=None):
    n = len(nets)
    numbers = numbers or list(range(1, n + 1))
    w = pitch * n
    h = pitch * 1.25
    ax.add_patch(FancyBboxPatch((x_left, y_top - h), w, h, boxstyle="round,pad=2", fc="#2a9d8f", ec="#1b4332", lw=1.4, zorder=15))
    for i, net in enumerate(nets):
        xc = x_left + pitch * (i + 0.5)
        ax.add_patch(Rectangle((xc - pitch * 0.32, y_top - h * 0.55), pitch * 0.64, h * 0.4, fc="#e9ecef", ec="#333", lw=0.8, zorder=16))
        label(ax, xc, y_top - h * 0.35, str(numbers[i]), fs, col="#111", bg=None, z=17, weight="bold")
        label(ax, xc, y_top - h * 0.8, net, fs * 0.72, col="white", bg=None, z=17)
    label(ax, x_left + w / 2, y_top - h - fs * 2.2, title, fs * 0.9, col="#1b4332", weight="bold", bg=None)
    return {numbers[i]: x_left + pitch * (i + 0.5) for i in range(n)}


# ------------------------------------------------------------------------------------------------ figure 1: close-up
SEQ = [
    "BENCH (all strips cut, laid out in chain order, pads up)",
    "1  Cut strips 0-3 on their cut lines. Mark BOTH ends of each strip:",
    "    number + IN / OUT (0 and 2 arrow UP, IN at the bottom; 1 and 3",
    "    inverted, arrow DOWN, IN at the top).",
    "2  Cut ribbons: jumper 0-1 = {j01} mm, 1-2 = {j12} mm, 2-3 = {j23} mm",
    "    (4 wires red / orange / yellow / green = 5V / CLK / DATA / GND).",
    "3  Start lead (J3): slide 15 mm of 2 mm heat-shrink on the 26 AWG",
    "    black; twist the two 28 AWG black returns onto it 30 mm from its",
    "    pad end, solder, shrink. Twist orange+black and yellow+black.",
    "4  Strip 0 BOTTOM (IN): red->5V, orange->CI, yellow->DI, black->GND.",
    "    Order GND, 5V, CLK, DATA; 320 C, 1-2 s per pad; wire lies along",
    "    the strip toward LED 0, tinned end >= 1 mm above the cut line.",
    "5  Strip 0 TOP (OUT): first end of jumper 0-1 (green GND, red 5V,",
    "    orange CO, yellow DO). Strip 1 BOTTOM (OUT): first end of 1-2.",
    "    Strip 2 TOP (OUT): first end of 2-3. Strip 3 BOTTOM (OUT): first",
    "    end of 3-4 + feed 3 (red on 5V, black on GND, beside the ribbon",
    "    wire, one joint each). CA drop + Kapton on every finished end.",
    "TUBE (tube off the hub, one strip at a time, in chain order)",
    "6  Mount strip 0: start lead out through its bottom slot, jumper 0-1",
    "    through its top slot; cut end onto the stop, press into the rails.",
    "7  Reach in from the top: push 0-1's free end out through strip 1's",
    "    TOP slot, pull 27 mm out. Strip 1 face down beside its rails,",
    "    solder its IN pads: COLOUR TO LABEL (order is mirrored on the",
    "    inverted strip). Push the slack back, fold the loop DOWN the wall,",
    "    lay strip 1 in (its 1-2 ribbon goes out through its bottom slot).",
    "8  Meter: 0 CO -> 1 CI and 0 DO -> 1 DI = 0 ohm; 5V-5V, GND-GND;",
    "    5V-GND > 100 ohm and climbing.",
    "9  Same at the bottom: 1-2's free end out through strip 2's BOTTOM",
    "    slot, 27 mm, solder strip 2 IN, loop folds UP the wall, mount 2.",
    "10 Same at the top for 2-3 into strip 3; then strip 3 goes on with",
    "    feed 3 and 3-4 out through its bottom slot. Tape each slot + loop.",
    "CARRIER (last)",
    "11 Start lead into J3 from below: 1 red, 2 black 26, 3 orange,",
    "    4 its black, 5 yellow, 6 its black. Feed 3 into J6: 1 red, 2 black.",
    "    Strip 5 mm, tin, fold the 28 AWG ends double, clamp, tug, varnish.",
]


def fig_closeup():
    S, H1, G = 8.0, 26 * 8.0, 50.0
    sp = 380.0
    fs = 11.0
    strips = [Strip(s, s * sp, 0.0, S, H1, G) for s in range(4)]
    fig, ax = plt.subplots(figsize=(29.5, 16.6))
    ax.set_xlim(-660, 2720); ax.set_ylim(-1010, 940); ax.set_aspect("equal"); ax.axis("off")
    for st in strips:
        draw_strip(ax, st, fs)
        label(ax, st.x, st.yt + 290, "strip %d%s,  theta %d deg\n%s" % (st.s, st.set, 15 * st.s, "inverted: arrow DOWN\nIN at the top" if st.inv else "upright: arrow UP\nIN at the bottom"),
              fs * 1.0, col=SET_COL[st.set], weight="bold", bg=None)
    lw = 4.2
    for (a, b, end) in [(0, 1, "top"), (1, 2, "bottom"), (2, 3, "top")]:
        jumper_wires(ax, strips[a], strips[b], end, CUT["jumper %d-%d" % (a, b)], fs * 0.85, 7.5 * S, 30, lw)
        bs = BENCH[(a, b)]
        ls_ = b if bs == a else a
        bench_mark(ax, strips[bs], end, fs)
        loop_mark(ax, strips[ls_], end, fs)
        mid = (strips[a].x + strips[b].x) / 2
        edge = strips[a].cut(end) if end == "top" else min(strips[a].cut(end), strips[b].cut(end))
        sg = 1 if end == "top" else -1
        label(ax, mid, edge + sg * (7.5 * S + 3 * 30 + 52), "jumper %d-%d  (%s end)  4 x 28 AWG ribbon, cut %d mm" % (a, b, end, CUT["jumper %d-%d" % (a, b)]),
              fs * 1.0, col="#333", weight="bold", bg=None)
    # jumper 3-4 stub (bench end on strip 3)
    st3 = strips[3]
    jumper_wires(ax, st3, None, "bottom", CUT["jumper 3-4"], fs * 0.85, 7.5 * S, 30, lw, labels=False, stub_to=st3.x + 230)
    ax.annotate("", xy=(st3.x + 262, -105), xytext=(st3.x + 232, -105), arrowprops=dict(arrowstyle="-|>", color="#333", lw=1.5))
    label(ax, st3.x + 80, -265, "jumper 3-4 (cut %d)\n-> strip 4 bottom IN\n(loop end at strip 4)" % CUT["jumper 3-4"], fs * 0.9, ha="left", bg=None)
    bench_mark(ax, st3, "bottom", fs)
    # feed 3
    yt_ = -690
    fx = feed_wires(ax, st3, yt_, CUT["feed 3"], fs * 0.85, 5.0, "J6", labels=True, tag=False)
    j_block(ax, st3.x - 72, yt_, 72, ["GND", "5V_A"], "J6", "", fs, numbers=[2, 1])
    label(ax, st3.x, yt_ - 150, "carrier J6 (2P 2.54 mm screw terminal,\nwires in from the ESP32 side)\nfeed 3: 1 = 5V red, 2 = GND black", fs * 0.95, col="#1b4332", bg=None)
    # start lead
    st0 = strips[0]
    res = start_lead(ax, st0, -690, 1.0, fs * 0.85, 5.0, 3.6, start_cuts(0), "J3")
    pin = res["pin"]
    j_block(ax, pin[1] - 27.5, -690, 55, ["5V_A", "GND", "CLK0", "GND", "DATA0", "GND"], "J3", "", fs)
    label(ax, (pin[1] + pin[6]) / 2, -870, "carrier J3: 6P 2.54 mm screw terminal, wires enter from below\n1 5V red 26 | 2 GND black 26 | 3 CLK orange | 4 its black | 5 DATA yellow | 6 its black",
          fs * 0.95, col="#1b4332", bg=None)
    ax.annotate("", xy=(res["x_gp"] + 8, res["y_spl"] - 6), xytext=(150, -330), arrowprops=dict(arrowstyle="-|>", color="#111", lw=1.4), zorder=30)
    label(ax, 150, -360, "SPLICE: both 28 AWG black returns\ntwisted onto the 26 AWG GND 30 mm\nbefore the GND pad, soldered,\n15 mm x 2 mm heat-shrink",
          fs * 0.9, ha="left", col="#111", bg="#fff3bf", alpha=1)
    label(ax, -650, -330, "start lead 0\n(chain 0, from J3)\n6 wires, one bundle\nunder the sled plate", fs, ha="left", col="#333", weight="bold", bg=None)
    # mirrored-order callout
    label(ax, -500, 845, "Mirrored pad order: strip 0 reads 5V|CO|DO|GND, strip 1 (inverted) reads GND|DI|CI|5V from the same side.\n"
          "The ribbon makes a half turn (the U's nest). Match colour to the printed pad label, never to position.", fs * 0.95, ha="left", col="#9d0208", bg="#ffe5e5", alpha=1)
    # title + footer
    ax.text(-640, 935, "POV LED column - strip harness close-up: strips 0-3, start lead J3, jumpers 0-1 / 1-2 / 2-3, feed 3   (%s, %s)" % (REV, DATE),
            fontsize=fs * 1.75, fontweight="bold", va="top")
    ax.text(-640, -1005, "Seen from OUTSIDE, tube unwrapped, theta 0 -> 360 deg left to right. Not to scale along the tube (strip middles broken out, strip spacing "
            "widened); strip ends near scale: 12 mm strip, pads 0.5-3.0 mm from the cut line, 10 x 5 mm wall slot (dashed) 1-6 mm above it.\n"
            "Pads are on the strip BACK (drawn seen through). Pad order 5V | CLK | DATA | GND on an upright strip is ASSUMED (E15) - check the printed pad order. "
            "Beyond the slot every wire runs INSIDE the wall; drawn pulled out for clarity. Cut lengths: docs/img/wiring_cut_list.csv.",
            fontsize=fs * 0.85, va="bottom", color="#333")
    # right panel: legend, section sketch, soldering sequence
    px = 1560
    ax.text(px, 800, "Legend", fontsize=fs * 1.3, fontweight="bold", va="top")
    leg = [("red", 5.0, "5V  (single wire 26 AWG / ribbon)"), ("black", 5.0, "GND (single wire)"), ("orange", 3.6, "CLK (single 28 AWG / ribbon)"),
           ("yellow", 3.6, "DATA (single 28 AWG / ribbon)"), ("green", 3.6, "GND - in the ribbon ONLY")]
    for i, (c, w_, t) in enumerate(leg):
        y = 750 - i * 34
        wire(ax, [(px, y), (px + 70, y)], c, w_)
        ax.text(px + 85, y, t, fontsize=fs, va="center")
    y = 750 - 5 * 34
    ax.add_patch(Rectangle((px + 10, y - 10), 13, 20, fc="#d4a373", ec="#7f5539", ls=(0, (2, 1)))); ax.text(px + 85, y, "pad (strip back, seen through)", fontsize=fs, va="center")
    y -= 34
    ax.add_patch(Rectangle((px, y - 12), 70, 24, fc="none", ec="#6c757d", ls=(0, (3, 2)))); ax.text(px + 85, y, "10 x 5 mm wall slot behind the end", fontsize=fs, va="center")
    y -= 34
    ax.plot([px + 35], [y], "o", ms=7, color="#adb5bd", mec="#495057"); ax.text(px + 85, y, "solder joint", fontsize=fs, va="center")
    y -= 34
    ax.text(px, y, "Wire labels: colour, signal, gauge, cut length in mm", fontsize=fs, va="center", color="#333")
    # section sketch (side view through a bottom strip end)
    sx, sy = 2420, 500
    ax.text(sx - 120, sy + 250, "Side section at a bottom end", fontsize=fs * 1.05, fontweight="bold", va="top")
    ax.add_patch(Rectangle((sx, sy - 200), 30, 160, fc="#ced4da", ec="#495057"))           # wall below slot
    ax.add_patch(Rectangle((sx, sy), 30, 200, fc="#ced4da", ec="#495057"))                 # wall above slot (slot = gap -40..0)
    ax.add_patch(Rectangle((sx + 30, sy - 60), 8, 250, fc="#fbfbf7", ec="#c1121f"))        # strip
    ax.add_patch(Rectangle((sx + 30, sy - 70), 25, 10, fc="#6c757d", ec="#333"))           # end-stop
    ax.add_patch(Rectangle((sx + 26, sy - 55), 4, 22, fc="#d4a373", ec="#7f5539"))         # pad on back
    wire(ax, [(sx + 27, sy - 50), (sx + 27, sy - 8), (sx + 10, sy - 8), (sx - 20, sy - 8), (sx - 20, sy - 180)], "red", 3.0)
    ax.text(sx + 70, sy - 64, "cut end on the printed end-stop", fontsize=fs * 0.85, va="center")
    ax.text(sx + 70, sy - 30, "pad on the back, wire laid toward LED 0", fontsize=fs * 0.85, va="center")
    ax.text(sx + 70, sy + 120, "strip (LEDs face out)", fontsize=fs * 0.85, va="center", color="#c1121f")
    ax.text(sx - 30, sy - 25, "slot", fontsize=fs * 0.85, ha="right", va="center")
    ax.text(sx + 15, sy + 215, "wall", fontsize=fs * 0.85, ha="center")
    ax.text(sx - 30, sy - 120, "inside:\nto the next\nstrip / carrier", fontsize=fs * 0.85, ha="right", va="center")
    ax.text(sx + 110, sy + 215, "outside", fontsize=fs * 0.85, ha="center")
    # soldering sequence
    sq = [l.format(j01=CUT["jumper 0-1"], j12=CUT["jumper 1-2"], j23=CUT["jumper 2-3"]) for l in SEQ]
    ax.text(px, 175, "Soldering sequence (electrical report 7.1, 7.2, 7.6)", fontsize=fs * 1.2, fontweight="bold", va="top")
    y = 135
    for l in sq:
        hdr = l.isupper() or l.startswith(("BENCH", "TUBE", "CARRIER"))
        ax.text(px, y, l, fontsize=fs * (0.98 if not hdr else 1.02), va="top", family="DejaVu Sans Mono" if not hdr else None,
                fontweight="bold" if hdr else "normal", color="#1d3557" if hdr else "#111")
        y -= 29
    for ext in ("png", "svg"):
        fig.savefig(os.path.join(IMG, "elec_harness_strips0-2." + ext), dpi=200 if ext == "png" else None, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote elec_harness_strips0-2.png/.svg")


# ------------------------------------------------------------------------------------------------ figure 2: all 24 strips
def wire_list():
    """Every conductor on the rotor harness: (item, qty, gauge, colour, cut mm, note)."""
    out = []
    for s in (0, 12):
        c = start_cuts(s)
        j = START_J[s]
        out += [("start lead %d (%s) 5V" % (s, j), 1, "26 AWG", "red", c["pow"], "%s.1 -> strip %d 5V" % (j, s)),
                ("start lead %d (%s) GND" % (s, j), 1, "26 AWG", "black", c["pow"], "%s.2 -> strip %d GND (splice 30 mm before)" % (j, s)),
                ("start lead %d (%s) CLK" % (s, j), 1, "28 AWG", "orange", c["sig"], "%s.3 -> strip %d CI, twisted with its return" % (j, s)),
                ("start lead %d (%s) DATA" % (s, j), 1, "28 AWG", "yellow", c["sig"], "%s.5 -> strip %d DI, twisted with its return" % (j, s)),
                ("start lead %d (%s) CLK/DATA returns" % (s, j), 2, "28 AWG", "black", c["ret"], "%s.4 / .6 -> GND splice" % j)]
    for s in (3, 6, 9, 15, 18, 21):
        out.append(("feed %d (%s)" % (s, FEED_J[s]), 2, "26 AWG", "red + black", CUT["feed %d" % s], "%s.1 / .2 -> strip %d bottom 5V / GND" % (FEED_J[s], s)))
    for a, b, end in JUMPERS:
        out.append(("jumper %d-%d (%s)" % (a, b, end), 1, "4 x 28 AWG ribbon", "R/O/Y/G", CUT["jumper %d-%d" % (a, b)], "bench end strip %d" % BENCH[(a, b)]))
    h = CUT["hall lead"]
    out += [("hall lead OUT", 1, "28 AWG", "white", h, "J5.1 -> A3144 leg 3"), ("hall lead GND", 1, "28 AWG", "black", h, "J5.2 -> leg 2"),
            ("hall lead 5V", 1, "28 AWG", "red", h, "J5.3 -> leg 1 (3 wires twisted)")]
    out.append(("pigtail (as bought)", 1, "22 AWG 2-core", "red + black", int(PIG_BOUGHT or 280), "bank USB-A -> J1; route %d mm" % CUT["pigtail (as bought)"]))
    return out


def totals(wl):
    t = {}
    for item, q, g, c, L, _ in wl:
        if c == "red + black":
            for cc in ("red", "black"):
                t[(g, cc)] = t.get((g, cc), 0) + q * L
        elif c == "R/O/Y/G":
            t[(g, "ribbon (4 wires)")] = t.get((g, "ribbon (4 wires)"), 0) + q * L
        else:
            t[(g, c)] = t.get((g, c), 0) + q * L
    return t


def fig_full():
    S, H1, G = 6.0, 22 * 6.0, 36.0
    sp = 200.0
    fs = 6.4
    lw_r, lw26, lw28 = 2.4, 3.0, 2.2
    strips = [Strip(s, s * sp, (s % 3) * 5.556 * S, S, H1, G) for s in range(24)]
    fig, ax = plt.subplots(figsize=(40, 20.9))
    ax.set_xlim(-400, 4990); ax.set_ylim(-1960, 850); ax.set_aspect("equal"); ax.axis("off")
    # tube outline (unwrapped wall), theta ticks
    ax.add_patch(Rectangle((-sp / 2, -15), 24 * sp, max(st.yt for st in strips) + 30, fc="#f1f3f5", ec="#adb5bd", lw=1.0, zorder=0))
    ytop = max(st.yt for st in strips)
    for st in strips:
        draw_strip(ax, st, fs, small=True)
        label(ax, st.x, ytop + 175, "strip %d%s\ntheta %d" % (st.s, st.set, 15 * st.s), fs * 1.15, col=SET_COL[st.set], weight="bold", bg=None)
    for s in (11, 23):
        label(ax, strips[s].x, strips[s].yb - 40, "CO / DO open\n(chain end)", fs * 0.9, col="#555", bg="white")
    ax.annotate("", xy=(24 * sp - sp / 2, ytop + 250), xytext=(-sp / 2, ytop + 250), arrowprops=dict(arrowstyle="-|>", color="#555", lw=1.2))
    label(ax, 9 * sp, ytop + 250, "theta 0 -> 360 deg (seen from OUTSIDE)", fs * 1.2, col="#333", bg="#f8f9fa", alpha=1)
    label(ax, 2.5 * sp, ytop + 250, "chain 0: strips 0-11 (start J3)", fs * 1.2, col="#333", bg="#f8f9fa", alpha=1)
    label(ax, 15.5 * sp, ytop + 250, "chain 1: strips 12-23 (start J4)", fs * 1.2, col="#333", bg="#f8f9fa", alpha=1)
    # jumpers
    for a, b, end in JUMPERS:
        A, B = strips[a], strips[b]
        sh = 0.0
        if end == "bottom":
            sh = 24.0 if a in FEED_J else (-24.0 if b in FEED_J else 0.0)
        jumper_wires(ax, A, B, end, CUT["jumper %d-%d" % (a, b)], fs * 0.8, 40, 17, lw_r, shift=sh, short=True)
        bs = BENCH[(a, b)]
        lp = b if bs == a else a
        bench_mark(ax, strips[bs], end, fs)
        loop_mark(ax, strips[lp], end, fs)
        edge = max(A.yt, B.yt) if end == "top" else min(A.yb, B.yb)
        sg = 1 if end == "top" else -1
        label(ax, (A.x + B.x) / 2 + sh * 1.6, edge + sg * (40 + 3 * 17 + 22), "jumper %d-%d  cut %d" % (a, b, CUT["jumper %d-%d" % (a, b)]), fs * 0.95, col="#333", weight="bold", bg=None)
    # feeds
    y_tag = -430
    for s, j in FEED_J.items():
        feed_wires(ax, strips[s], y_tag, CUT["feed %d" % s], fs * 0.85, lw26, j)
        label(ax, strips[s].x, y_tag - 34, "feed %d" % s, fs, col="#333", weight="bold", bg=None)
    # start leads
    for s, j in START_J.items():
        st = strips[s]
        res = start_lead(ax, st, y_tag, 0.62, fs * 0.8, lw26, lw28, start_cuts(s), j)
        for p, xp in res["pin"].items():
            label(ax, xp, y_tag - 12, "%s.%d" % (j, p), fs * 0.8, col="#222", weight="bold", bg="#e9ecef", alpha=1)
        label(ax, (res["pin"][1] + res["pin"][6]) / 2, y_tag - 36, "start lead %d -> %s" % (s, j), fs, col="#333", weight="bold", bg=None)
        label(ax, res["x_gp"] + 34, res["y_spl"] - 2, "splice", fs * 0.8, ha="left", col="#111", bg="#fff3bf", alpha=1)

    # ---------------- carrier inset
    ix, iy = -360, -560
    ax.add_patch(FancyBboxPatch((ix, iy - 900), 2900, 880, boxstyle="round,pad=6", fc="#f8fff8", ec="#2d6a4f", lw=1.4, zorder=0))
    ax.text(ix + 10, iy - 30, "Carrier board end: every wire's screw terminal and pin (2.54 mm KF128 blocks; J1 5 mm). Start leads and hall lead enter J3 / J5 / J4 from below, "
            "feeds enter J6-J11 from the ESP32 side. Strip 5 mm, tin, fold 28 AWG ends double, clamp, tug, varnish the screw.", fontsize=fs * 1.2, va="top", fontweight="bold", color="#1b4332")
    yb_ = iy - 760
    P = 46
    stub = 300

    def stubs(x0, nets, jname, wires_):
        pins = j_block(ax, x0, yb_, P, nets, jname, jname, fs * 1.05)
        for p, (col, lw_, txt) in wires_.items():
            xp = pins[p]
            wire(ax, [(xp, yb_ + 4), (xp, yb_ + stub)], col, lw_)
            label(ax, xp, yb_ + stub * 0.52, txt, fs * 0.82, rot=90, z=22)
        return pins

    for s, x0 in ((0, ix + 120), (12, ix + 1000)):
        j = START_J[s]
        c = start_cuts(s)
        stubs(x0, ["5V_%s" % ("A" if s == 0 else "B"), "GND", "CLK%d" % (s // 12), "GND", "DATA%d" % (s // 12), "GND"], j,
              {1: ("red", lw26, "strip %d 5V  26 AWG %d" % (s, c["pow"])), 2: ("black", lw26, "strip %d GND  26 AWG %d" % (s, c["pow"])),
               3: ("orange", lw28, "strip %d CI  28 AWG %d" % (s, c["sig"])), 4: ("black", lw28, "CLK return  28 AWG %d" % c["ret"]),
               5: ("yellow", lw28, "strip %d DI  28 AWG %d" % (s, c["sig"])), 6: ("black", lw28, "DATA return  28 AWG %d" % c["ret"])})
    # J5 hall + A3144
    hx = ix + 580
    pins = j_block(ax, hx, yb_, P, ["HALL", "GND", "5V_A"], "J5", "J5 (hall)", fs * 1.05)
    sx0, sy0 = hx + 1.5 * P, yb_ + 420
    ax.add_patch(Rectangle((sx0 - 45, sy0), 90, 60, fc="#343a40", ec="#111", zorder=15))
    label(ax, sx0, sy0 + 30, "A3144\nflat face\ntoward you", fs * 0.8, col="white", bg=None, z=16)
    legs = {1: sx0 - 28, 2: sx0, 3: sx0 + 28}
    h = CUT["hall lead"]
    for p, (col, leg, nm) in {1: ("white", 3, "OUT"), 2: ("black", 2, "GND"), 3: ("red", 1, "5V")}.items():
        xp = pins[p]
        wire(ax, [(xp, yb_ + 4), (xp, yb_ + 150), (legs[leg], yb_ + 300), (legs[leg], sy0)], col, lw28)
        label(ax, legs[leg], sy0 - 18, "%d" % leg, fs * 0.9, col="#111", bg="white")
        label(ax, xp, yb_ + 92, "%s %s 28 AWG %d" % (nm, col, h), fs * 0.8, rot=90, z=22)
    label(ax, sx0, sy0 + 85, "legs: 1 VCC, 2 GND, 3 OUT\n(at the cap's lead slot; 3 wires twisted)", fs * 0.9, col="#333", bg=None)
    # J1 pigtail
    j1x = ix + 1520
    pins = j_block(ax, j1x, yb_, 70, ["5V_A", "GND"], "J1", "J1 (5 mm)", fs * 1.05)
    for p, col in ((1, "red"), (2, "black")):
        wire(ax, [(pins[p], yb_ + 4), (pins[p], yb_ + stub)], col, 3.6)
    label(ax, j1x + 70, yb_ + stub + 40, "pigtail from the bank USB-A (+x)\n22 AWG as bought %s mm (route %d)\nVERIFY colours with a meter" % (PIG_BOUGHT, CUT["pigtail (as bought)"]),
          fs * 0.9, col="#333", bg=None)
    # feeds J6..J11
    fx = ix + 1760
    for i, s in enumerate((3, 6, 9, 15, 18, 21)):
        j = FEED_J[s]
        x0 = fx + i * 2.6 * P
        stubs(x0, ["5V_%s" % ("A" if s < 12 else "B"), "GND"], j, {1: ("red", lw26, "strip %d 5V 26 AWG %d" % (s, CUT["feed %d" % s])),
                                                                     2: ("black", lw26, "strip %d GND 26 AWG %d" % (s, CUT["feed %d" % s]))})
    label(ax, fx + 6.5 * P, yb_ - 110, "J6-J8 on bus A (strips 3, 6, 9), J9-J11 on bus B (15, 18, 21)", fs * 0.95, col="#1b4332", bg=None)

    # ---------------- cut list table
    wl = wire_list()
    tx, ty = 2620, -540
    cols = [(0, "item"), (620, "qty"), (700, "gauge / type"), (1060, "colour"), (1290, "cut mm"), (1420, "to / note")]
    ax.text(tx, ty, "Cut list (rotor harness, every conductor) - from docs/img/wiring_cut_list.csv", fontsize=fs * 1.35, fontweight="bold", va="top")
    rh = 23.0
    y = ty - 50
    for dx, h_ in cols:
        ax.text(tx + dx, y, h_, fontsize=fs * 1.05, fontweight="bold", va="center")
    ax.plot([tx, tx + 2330], [y - rh / 2, y - rh / 2], color="#333", lw=0.8)
    for i, (item, q, g, c, L, note) in enumerate(wl):
        y -= rh
        if i % 2 == 0:
            ax.add_patch(Rectangle((tx - 5, y - rh / 2), 2335, rh, fc="#f1f3f5", ec="none", zorder=0))
        for dx, v in zip([d for d, _ in cols], [item, str(q), g, c, str(L), note]):
            ax.text(tx + dx, y, v, fontsize=fs, va="center", family="DejaVu Sans Mono")
        if c in WC:
            wire(ax, [(tx + 1225, y), (tx + 1270, y)], c, 2.2)
    # totals
    t = totals(wl)
    y -= rh * 1.8
    ax.text(tx, y, "Totals by gauge and colour (cut lengths x qty)", fontsize=fs * 1.2, fontweight="bold", va="center")
    for (g, c), L in sorted(t.items()):
        y -= rh
        ax.text(tx, y, "%-20s %-18s %6d mm  (%.2f m)" % (g, c, L, L / 1000), fontsize=fs, va="center", family="DejaVu Sans Mono")
    y -= rh * 1.3
    ax.text(tx, y, "Jumper lengths are the cut list's per-jumper CAD values (75 / 80); report 7.6 says cut all 22 at 80 - either fits, 80 is the safe single length.\n"
            "Base wiring (motor, supply, pot cable) is in wiring_cut_list.csv, not on this rotor drawing.", fontsize=fs * 0.95, va="top", color="#9d0208")

    # ---------------- legend
    lx, ly = -380, 840
    ax.text(lx, ly, "POV LED column - strip harness, every wire (%s, %s)" % (REV, DATE), fontsize=fs * 3.0, fontweight="bold", va="top")
    ly2 = ly - 70
    items = [("red", lw26, "5V"), ("black", lw26, "GND (single wire)"), ("orange", lw28, "CLK"), ("yellow", lw28, "DATA"), ("green", lw_r, "GND - ribbon only"), ("white", lw28, "hall OUT")]
    for i, (c, w_, t_) in enumerate(items):
        x = lx + i * 280
        wire(ax, [(x, ly2), (x + 50, ly2)], c, w_)
        ax.text(x + 60, ly2, t_, fontsize=fs * 1.15, va="center")
    ax.text(lx + 6 * 280, ly2, "Ribbon jumpers red / orange / yellow / green = 5V / CLK / DATA / GND.  Label = colour, signal, gauge, cut mm.  "
            "BENCH end = first end, soldered on the bench; LOOP end = second end, pulled out 27 mm, soldered pads-up, pushed back as a loop (report 7.6).",
            fontsize=fs * 1.1, va="center")
    ax.text(lx, ly2 - 38, "Pad order 5V | CLK | DATA | GND left to right on an UPRIGHT (even) strip seen from outside: ASSUMED (E15) - check the printed pad order. "
            "Inverted (odd) strips read GND | DATA | CLK | 5V, so every jumper is mirrored: match colour to the pad label, never to position.",
            fontsize=fs * 1.1, va="center", color="#9d0208", fontweight="bold")
    ax.text(lx, -1950, "Seen from outside, unwrapped theta 0 -> 360 deg. Strips at 15 deg x s, sets A / B / C staggered 5.56 mm (drawn to scale at the ends); strip middles broken out, "
            "strip spacing not to scale. Dashed box = 10 x 5 mm rev g wall slot, 1-6 mm above the cut line; pads drawn seen through the strip (they are on its back). "
            "Beyond the slot every wire runs INSIDE the tube wall; drawn pulled out past the strip ends for clarity. Close-up of strips 0-3: elec_harness_strips0-2.png. "
            "Script software/elec/elec_harness_detailed.py.", fontsize=fs * 1.05, va="bottom", color="#333")
    for ext in ("png", "svg", "pdf"):
        fig.savefig(os.path.join(IMG, "elec_harness_detailed." + ext), dpi=200 if ext == "png" else None, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote elec_harness_detailed.png/.svg/.pdf")


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "both"
    if what in ("closeup", "both"):
        fig_closeup()
    if what in ("full", "both") and "fig_full" in globals():
        fig_full()
