"""Carrier-board build steps for the wiring guide, one figure per step, drawn from the rev i netlist JSON.

Rev i (2026-11-04): Brian's board as counted, 26 x 31 holes; every hole is named by its PRINTED label (column letter A-Z, row number
1-31) on the axes and in the notes. Orientation: hole A1 at the bottom LEFT with the component side facing you, the row-1 end down.
Every position here comes from the netlist (no literal holes), so a re-laid board is a rerun.

Component-side views (parts) are drawn as elec_carrier_layout.png is; SOLDER-side views (bus wires, R5-R8, insulated wires)
are drawn MIRRORED, the way the board looks when it is turned over left-to-right with the USB end still up: A1 is then at the
bottom RIGHT and the letters run Z..A from left to right. Earlier steps are grey, the current step is in colour with its W-numbers
(docs/img/guide_carrier_wires.csv). Wire colours come from carrier_data.colour_of (Brian, 2026-11-04: yellow = CLK, orange = DATA).

  py software/elec/guide/fig_carrier_steps.py      -> docs/img/guide_carrier_1_mark_terminals ... guide_carrier_7_esp32 (.svg/.png)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import matplotlib.pyplot as plt                                    # noqa: E402
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle   # noqa: E402

from guide_common import WC, save, stamp                           # noqa: E402
import carrier_data as CD                                          # noqa: E402

N = CD.N
G = N["grid"]
P = G["pitch"]
NC, NR = G["NC"], G["NR"]
CC = G["c_centre"]                       # the board's centre column (rev i 12.5): figures are drawn about the board's centre line
W_, H_ = G["board"]
ZB = G.get("board_z_bot", 11.0)
Z0 = G["z0"]
ESP = N["esp"]
T254 = N["term254"]
T5 = N["term5"]
GRIP = G.get("guide_grip", 1.5)
POST_TOP = G.get("post_top", 56.4)
GUIDE_ROW = G["guide_row"]
GREY = "#c8c8c8"
BUSCOL = {"GND": "#3a3a3a", "5V_A": "#d62828", "5V_B": "#f77f00"}
REV_I = "guide 2026-11-04 (rev i, 26 x 31 board)"
L = CD.label
U1 = CD.U1
U1_L, U1_R = U1[1][0], U1[14][0]          # U1's two pin columns (D, G)
ESP_CL, ESP_CR = ESP["C"]["L"], ESP["C"]["R"]
ESP_ROWS = (ESP["R0"] + 1, ESP["R0"] + ESP["N"])    # printed rows


def X(c, side):
    x = (c - CC) * P
    return -x if side == "solder" else x


def Y(r):
    return (Z0 - ZB) + r * P


def pt(p, side):
    return X(p[0], side), Y(p[1])


def esp_x(side):
    return (X(ESP_CL, side) + X(ESP_CR, side)) / 2.0


def run_label(holes):
    hs = [tuple(h) for h in holes]
    if len(hs) > 2:
        return "%s-%s" % (L(*hs[0]), L(*hs[-1]))
    return "/".join(L(*h) for h in hs)


def board(ax, side, title, sub):
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_xlim(-W_ / 2 - 9, W_ / 2 + 9)
    ax.set_ylim(-12, H_ + 13)
    ax.add_patch(Rectangle((-W_ / 2, 0), W_, H_, fc="#f3efe6" if side == "component" else "#e9efe4", ec="#333", lw=1.4, zorder=0))
    for c in range(NC):
        for r in range(NR):
            ax.add_patch(Circle(pt((c, r), side), 0.42, fc="#c2b49a", ec="none", zorder=1))
    for c in range(NC):
        x = X(c, side)
        for yy, va in ((-1.3, "top"), (H_ + 1.0, "bottom")):
            ax.text(x, yy, chr(65 + c), ha="center", va=va, fontsize=5.0, color="#555" if c % 5 else "#000", fontweight="normal" if c % 5 else "bold")
    for r in range(NR):
        y = Y(r)
        for xx, ha in ((-W_ / 2 - 0.8, "right"), (W_ / 2 + 0.8, "left")):
            ax.text(xx, y, str(r + 1), ha=ha, va="center", fontsize=4.6, color="#555" if r % 5 else "#000", fontweight="normal" if r % 5 else "bold")
    # A1, the corner the orientation is stated by
    x, y = pt((0, 0), side)
    ax.add_patch(Circle((x, y), 1.1, fc="none", ec="#c00", lw=1.0, zorder=7))
    ax.text(x + (1.3 if side == "component" else -1.3), y - 1.5, "A1", fontsize=6.0, color="#c00", fontweight="bold", ha="left" if side == "component" else "right", va="top", zorder=7)
    # the card guides' grip: the outer 1.5 mm of each 90 mm edge, from the bottom up to the post tops (no hole is inside it)
    for sx in (-1, 1):
        ax.add_patch(Rectangle((sx * W_ / 2 - (GRIP if sx > 0 else 0), 0), GRIP, POST_TOP - ZB, fc="none", ec="#999", hatch="////", lw=0.4, zorder=1))
    ax.text(0, H_ + 9.6, title, ha="center", va="bottom", fontsize=9.5, fontweight="bold")
    ax.text(0, H_ + 6.0, sub, ha="center", va="bottom", fontsize=6.4, color="#333")
    lab = "COMPONENT SIDE (parts face you): A1 bottom LEFT, letters A..Z" if side == "component" else \
          "SOLDER SIDE (turned over left-to-right, USB up): A1 bottom RIGHT, letters Z..A"
    ax.text(0, H_ + 3.4, lab, ha="center", va="bottom", fontsize=7.0, fontweight="bold", color="#0b5394" if side == "component" else "#b45f06")
    ax.text(-W_ / 2 - 6.5, H_ / 2, "printed row number (1 = bottom, 7.5 mm up)", rotation=90, ha="center", va="center", fontsize=6, color="#555")
    ax.text(0, -5.0, "printed column letter" + (" (Z on the LEFT on this side)" if side == "solder" else ""), ha="center", va="center", fontsize=6, color="#555")
    gx = W_ / 2 - 2.2 if side == "component" else -W_ / 2 + 2.2          # bottom margin, the corner opposite A1
    ax.text(gx, 0.9, "hatched: the card guides' grip\n(beside rows 1-%d), no hole in it" % GUIDE_ROW, fontsize=4.2, color="#888",
            ha="right" if side == "component" else "left", va="bottom", zorder=2)


def term_rect(name):
    p = CD.PARTS[name]
    holes = p["holes"]
    xs = [(c - CC) * P for c, r in holes]
    zs = [Z0 + r * P for c, r in holes]
    cx, cz = sum(xs) / len(xs), sum(zs) / len(zs)
    Ln = len(holes) * T254["pitch"]
    d, b = T254["depth"], T254["pin_from_back"]
    if p["kind"] == "t254h":
        return cx - Ln / 2, cx + Ln / 2, cz - (d - b), cz + b
    if p["kind"] == "t254v":
        return cx - (d - b), cx + b, cz - Ln / 2, cz + Ln / 2
    return cx - T5["w"] / 2, cx + T5["w"] / 2, cz - T5["d"] / 2, cz + T5["d"] / 2


def draw_terminals(ax, side, state):
    """state 'now' = coloured with pin numbers, hole labels and entry arrows, 'done' = grey outline, 'ghost' = dashed (seen through from the solder side)."""
    for name, p in CD.PARTS.items():
        if p["kind"] not in ("t254h", "t254v", "term"):
            continue
        x0, x1, z0, z1 = term_rect(name)
        if side == "solder":
            x0, x1 = -x1, -x0
        y0, y1 = z0 - ZB, z1 - ZB
        if state == "now":
            fc = "#8ecae6" if name in ("J1", "J12", "J3", "J4", "J5") else ("#ffc9c9" if name in ("J6", "J7", "J8") else "#ffe8a3")
            ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc=fc, ec="#135", lw=0.9, zorder=4, alpha=0.95))
        elif state == "done":
            ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc="#eeeeee", ec="#aaa", lw=0.6, zorder=2))
            ax.text((x0 + x1) / 2, (y0 + y1) / 2, name, fontsize=5.0, ha="center", va="center", color="#999", zorder=3)
        else:
            ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc="none", ec="#9aa", lw=0.5, ls="--", zorder=2))
            ax.text((x0 + x1) / 2, y0 + 0.9, name, fontsize=4.4, ha="center", va="bottom", color="#7a9", zorder=3)
        for i, h in enumerate(p["holes"]):
            x, y = pt(h, side)
            ax.add_patch(Circle((x, y), 0.55, fc="#777" if state != "now" else "#ddd", ec="#333" if state == "now" else "none", lw=0.4, zorder=5))
            if state == "now":
                if p["kind"] == "t254h":
                    ax.text(x, y + 0.75, str(i + 1), fontsize=5.0, ha="center", va="bottom", zorder=6, fontweight="bold")
                    short = {"5V_A": "5V", "5V_B": "5V", "DATA0": "DAT0", "DATA1": "DAT1"}.get(p["nets"][i], p["nets"][i])
                    ax.text(x, y - 0.8, short, fontsize=3.4, ha="center", va="top", zorder=6, rotation=90)
                elif p["kind"] == "t254v":
                    ax.text(x + (-0.9 if side == "component" else 0.9), y, "%d %s %s" % (i + 1, "5V" if i == 0 else "G", L(*h)), fontsize=3.8,
                            ha="right" if side == "component" else "left", va="center", zorder=6, fontweight="bold")
                else:
                    ax.text(x, y + (1.5 if i == 0 else -1.5), "%d %s %s" % (i + 1, "5V" if i == 0 else "GND", L(*h)), fontsize=4.2, ha="center", va="center", zorder=6, fontweight="bold")
        if state == "now":
            mx, my = (x0 + x1) / 2, (y0 + y1) / 2
            if p["kind"] == "t254h":
                ax.annotate("", xy=(mx, y0 - 3.4), xytext=(mx, y0 - 0.2), arrowprops=dict(arrowstyle="<|-", color="#135", lw=1.0, mutation_scale=7), zorder=6)
                ax.text(mx, y1 + 0.4, "%s  %s" % (name, run_label(p["holes"])), fontsize=6.0, ha="center", va="bottom", fontweight="bold", zorder=6)
            elif p["kind"] == "t254v":
                ex = x0 - 3.2 if side == "component" else x1 + 3.2
                ax.annotate("", xy=(ex, my), xytext=(x0 - 0.2 if side == "component" else x1 + 0.2, my),
                            arrowprops=dict(arrowstyle="<|-", color="#135", lw=0.9, mutation_scale=6), zorder=6)
                ax.text((x0 + x1) / 2, y1 + 0.3, name, fontsize=5.6, ha="center", va="bottom", fontweight="bold", zorder=6)
            else:
                outward = -1 if mx < 0 else 1
                ax.annotate("", xy=(mx + outward * 7.0, my), xytext=(mx + outward * 3.9, my),
                            arrowprops=dict(arrowstyle="<|-", color="#135", lw=0.9, mutation_scale=6), zorder=6)
                ax.text(mx, y1 + 0.4, name + " (5 mm)", fontsize=5.6, ha="center", va="bottom", fontweight="bold", zorder=6)


def u1_box(side):
    xa, xb = X(U1_L, side), X(U1_R, side)
    ys = [Y(h[1]) for h in U1.values()]
    return min(xa, xb) - 1.6, max(xa, xb) + 1.6, min(ys) - 1.9, max(ys) + 1.9


def draw_u1(ax, side, state):
    x0, x1, y0, y1 = u1_box(side)
    if state == "now":
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc="#3a3a3a", ec="#000", lw=0.9, zorder=4))
        ax.add_patch(Circle(((x0 + x1) / 2, y1), 1.1, fc="#f3efe6", ec="#000", lw=0.6, zorder=5))         # notch, top
        px, py = pt(U1[1], side)
        ax.add_patch(Circle((px, py), 0.95, fc="#ffd60a", ec="#000", lw=0.6, zorder=6))
        ax.text((x0 + x1) / 2, (y0 + y1) / 2 + 2.0, "U1\n74AHCT125\nnotch UP", color="white", fontsize=5.2, ha="center", va="center", zorder=6)
        ax.annotate("pin 1 = %s" % L(*U1[1]), xy=(px, py), xytext=(px - 9.0, py + 4.0), fontsize=5.2, zorder=7,
                    arrowprops=dict(arrowstyle="-", color="#000", lw=0.6))
        for k, h in U1.items():
            x, y = pt(h, side)
            ax.add_patch(Circle((x, y), 0.5, fc="#ddd", ec="none", zorder=5))
            right = (h[0] == U1_R) == (side == "component")
            tx = x + (2.0 if right else -2.0)
            ax.text(tx, y, "%d %s %s" % (k, CD.U1_NAME[k], L(*h)), fontsize=3.7, ha="left" if right else "right", va="center", zorder=6,
                    color="#111", bbox=dict(fc="white", ec="none", pad=0.15, alpha=0.8))
    elif state == "done":
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc="#e2e2e2", ec="#aaa", lw=0.6, zorder=2))
    else:
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc="none", ec="#9aa", lw=0.5, ls="--", zorder=2))
        for k, h in U1.items():
            x, y = pt(h, side)
            ax.add_patch(Circle((x, y), 0.55, fc="#555", ec="none", zorder=5))
            if k in (1, 7, 8, 14):
                inward = -1 if (h[0] == U1_L) == (side == "solder") else 1
                ax.text(x + inward * 1.0, y, "%d %s" % (k, L(*h)), fontsize=3.6, ha="left" if inward > 0 else "right", va="center", zorder=6, color="#444")


def draw_passives(ax, side, state):
    for name, p in CD.PARTS.items():
        k = p["kind"]
        if k not in ("elco", "small", "axial", "tp"):
            continue
        holes = [tuple(h) for h in p["holes"]]
        pts = [pt(h, side) for h in holes]
        if k == "tp":
            for h in holes:
                nm = CD.TP_NAMES[h]
                x, y = pt(h, side)
                if state == "now":
                    ax.add_patch(Circle((x, y), 1.0, fc="#ffb703", ec="#135", lw=0.7, zorder=5))
                    up = nm == "TP3"
                    ax.text(x, y + (1.4 if up else -1.4), "%s %s%s" % (nm, L(*h), {"TP1": "\n5V_A", "TP2": "\n5V_B", "TP3": " GND"}[nm]), fontsize=4.4,
                            ha="center", va="bottom" if up else "top", zorder=6)
                else:
                    ax.add_patch(Circle((x, y), 0.8, fc="#ddd" if state == "done" else "#777", ec="none", zorder=4))
            continue
        cx, cy = (pts[0][0] + pts[1][0]) / 2, (pts[0][1] + pts[1][1]) / 2
        if state != "now":
            if k == "elco":
                ax.add_patch(Circle((cx, cy), 5.0, fc="#ececec" if state == "done" else "none", ec="#aaa" if state == "done" else "#9aa",
                                    lw=0.6, ls="-" if state == "done" else "--", zorder=2))
            for (x, y) in pts:
                ax.add_patch(Circle((x, y), 0.55, fc="#777", ec="none", zorder=5))
            continue
        if k == "elco":
            ax.add_patch(Circle((cx, cy), 5.0, fc="#cdb4db", ec="#135", lw=0.8, zorder=4, alpha=0.9))
            (xp, yp), (xn, yn) = pts
            ax.text(xp + 1.4, yp, "+", fontsize=9, ha="center", va="center", zorder=6, fontweight="bold", color="#b00")
            ax.text(xn + 1.4, yn, "−", fontsize=9, ha="center", va="center", zorder=6, fontweight="bold")
            ax.add_patch(Rectangle((cx - 5.0, yn - 0.9), 10.0, 1.8, fc="#555", ec="none", alpha=0.35, zorder=4))      # stripe (negative side)
            ax.text(cx - 6.0, cy, "%s 1000 µF\n+ %s at %s" % (name, "UP" if yp > yn else "DOWN", L(*holes[0])), fontsize=5.0,
                    ha="right", va="center", zorder=6, fontweight="bold")
        elif k == "small":
            ax.plot([pts[0][0], pts[1][0]], [pts[0][1], pts[1][1]], color="#135", lw=0.8, zorder=4)
            ax.add_patch(Rectangle((cx - 1.6, cy - 1.0), 3.2, 2.0, fc="#ffd6a5", ec="#135", lw=0.7, zorder=5))
            lab = {"C3": "C3 100n", "C4": "C4 1n", "C5": "C5 100n"}[name] + " " + run_label(holes)
            if name == "C3":
                ax.text(cx - 3.2, cy, lab, fontsize=4.6, ha="right", va="center", zorder=6, fontweight="bold")
            else:
                ax.text(cx + 2.0, cy, lab, fontsize=4.6, ha="left", va="center", zorder=6, fontweight="bold")
        else:
            ax.plot([pts[0][0], pts[1][0]], [pts[0][1], pts[1][1]], color="#135", lw=0.8, zorder=4)
            ax.add_patch(Circle(pts[0], 1.1, fc="#bde0fe", ec="#135", lw=0.7, zorder=5))
            if name in ("R1", "R2", "R3", "R4"):
                ax.text(pts[0][0], pts[0][1], name[1], fontsize=4.2, ha="center", va="center", zorder=7, fontweight="bold")
                if name == "R1":
                    r4 = CD.PARTS["R4"]["holes"]
                    ax.text((pt(holes[0], side)[0] + pt(r4[0], side)[0]) / 2, pts[0][1] + 1.6,
                            "R1 R2 R3 R4 = 68 (or 100) ohm, standing on %s-%s, folded into %s-%s" % (L(*holes[0]), L(*r4[0]), L(*holes[1]), L(*r4[1])),
                            fontsize=4.4, ha="center", va="bottom", zorder=6, fontweight="bold", bbox=dict(fc="white", ec="none", pad=0.2, alpha=0.85))
            else:
                ax.text(pts[0][0] - 1.6, (pts[0][1] + pts[1][1]) / 2, "%s\n10k\n%s" % (name, run_label(holes)), fontsize=4.4, ha="right", va="center", zorder=6, fontweight="bold")
        for (x, y) in pts:
            ax.add_patch(Circle((x, y), 0.5, fc="#ddd", ec="#333", lw=0.3, zorder=6))


def draw_esp(ax, side, state):
    ew, el = ESP["board"]
    y0, y1 = ESP["z0"] - ZB, ESP["z1"] - ZB
    xe = esp_x(side)
    if state == "now":
        ax.add_patch(FancyBboxPatch((xe - ew / 2, y0), ew, el, boxstyle="round,pad=0.2", fc="#1f2a44", ec="#000", lw=0.9, zorder=4, alpha=0.92))
        ax.add_patch(Rectangle((xe - 4.0, y1 - 5.6), 8.0, 5.6, fc="#bbb", ec="#000", lw=0.6, zorder=5))
        ax.text(xe, y1 - 8.0, "micro-USB UP", fontsize=5.6, ha="center", color="white", zorder=6)
        ax.add_patch(Rectangle((xe - 9.0, y0 - 1.0), 18.0, 25.5, fc="#c9ccd1", ec="#000", lw=0.5, zorder=5, alpha=0.85))
        ax.text(xe, y0 + 11.0, "WROOM module\n(antenna end DOWN)", fontsize=5.4, ha="center", va="center", zorder=6)
        for s in ("L", "R"):
            for i, nm in enumerate(ESP[s]):
                h = (ESP["C"][s], ESP["R0"] + i)
                x, y = pt(h, side)
                ax.add_patch(Circle((x, y), 0.55, fc="#ffd60a" if nm in ("VIN", "3V3", "EN", "IO23") else "#ddd", ec="#000", lw=0.3, zorder=6))
                hot = nm in ("IO23", "IO18", "IO13", "IO14", "IO27", "VIN", "3V3", "GND")
                ax.text(x + (1.3 if s == "L" else -1.3), y, "%s %s" % (nm, L(*h)) if hot or nm == "EN" else nm, fontsize=3.8, ha="left" if s == "L" else "right",
                        va="center", zorder=7, color="#ff6b6b" if hot else "#eee", fontweight="bold" if hot else "normal")
    elif state == "ghost":
        ax.add_patch(FancyBboxPatch((xe - ew / 2, y0), ew, el, boxstyle="round,pad=0.2", fc="none", ec="#9aa", ls="--", lw=0.7, zorder=2))
        for s in ("L", "R"):
            for i, nm in enumerate(ESP[s]):
                x, y = pt((ESP["C"][s], ESP["R0"] + i), side)
                ax.add_patch(Circle((x, y), 0.5, fc="none", ec="#7a8", lw=0.5, zorder=2))
        ax.text(xe, (y0 + y1) / 2, "ESP32 goes here LAST\n(columns %s and %s, rows %d-%d)\nholes stay EMPTY" % (chr(65 + ESP_CL), chr(65 + ESP_CR), ESP_ROWS[0], ESP_ROWS[1]),
                fontsize=5.0, ha="center", va="center", color="#7a8", zorder=2)


def draw_buses(ax, side, state):
    for net, path, segs in CD.BUSES:
        xs, ys = zip(*[pt(p, side) for p in path])
        if state == "now":
            ax.plot(xs, ys, color="#b08d57", lw=3.4, solid_capstyle="round", zorder=4)
            ax.plot(xs, ys, color=BUSCOL[net], lw=1.2, solid_capstyle="round", zorder=4, alpha=0.9)
        else:
            ax.plot(xs, ys, color="#bbb", lw=2.6, solid_capstyle="round", zorder=2)


def draw_wires(ax, side, wires, state, labels=True):
    for w in wires:
        xs, ys = zip(*[pt(p, side) for p in w["path"]])
        if state == "done":
            ax.plot(xs, ys, color="#c4c4c4", lw=1.1 if not w["hop"] else 1.6, zorder=3, solid_capstyle="round")
            continue
        if w["hop"]:
            ax.plot(xs, ys, color="#b08d57", lw=2.2, zorder=5, solid_capstyle="round")
        else:
            lw = {"22": 2.2, "26": 1.7, "28": 1.3}[w["gauge"]]
            col = WC[w["colour"]]
            ax.plot(xs, ys, color="#222", lw=lw + 0.9, zorder=5, solid_capstyle="round", solid_joinstyle="round")
            ax.plot(xs, ys, color=col, lw=lw, zorder=5, solid_capstyle="round", solid_joinstyle="round")
        for h in (w["a"], w["b"]):
            x, y = pt(h, side)
            esp = (int(h[0]), int(h[1])) in CD.esp_holes
            ax.add_patch(Circle((x, y), 0.75 if esp else 0.55, fc="white" if esp else "#555", ec="#c00" if esp else "none", lw=0.9, zorder=6))
        if labels and w["id"] in LABEL_AT:
            lx, ly = pt(LABEL_AT[w["id"]], side)
            ax.text(lx, ly, w["id"], fontsize=4.5, ha="center", va="center", zorder=8, color="#000", fontweight="bold",
                    bbox=dict(fc="white", ec="none", pad=0.25, alpha=0.85))
        elif labels:
            # label at the middle of the longest segment
            segs = list(zip(w["path"], w["path"][1:]))
            a, b = max(segs, key=lambda s: abs(s[1][0] - s[0][0]) + abs(s[1][1] - s[0][1]))
            (xa, ya), (xb, yb) = pt(a, side), pt(b, side)
            mx, my = (xa + xb) / 2, (ya + yb) / 2
            vert = abs(xb - xa) < abs(yb - ya)
            dx, dy = (1.0, 0) if vert else (0, -1.1)
            if w["hop"]:
                dx, dy = (0, -1.3) if not vert else (1.3, 0)
            ax.text(mx + dx, my + dy, w["id"], fontsize=4.5 if not w["hop"] else 4.0, ha="left" if vert else "center", va="center", zorder=8,
                    color="#000", fontweight="bold", bbox=dict(fc="white", ec="none", pad=0.25, alpha=0.85))


# W-label positions (grid c, r; the rev h positions with every row - 2, like the wires)
LABEL_AT = {"W46": (1.3, 14.6), "W47": (8.9, 10.4), "W48": (12.0, 13.0), "W49": (12.0, 11.5),
            "W50": (3.5, 10.3), "W51": (4.5, 9.7), "W52": (5.4, 10.3), "W53": (6.4, 9.7),
            "W54": (5.6, 4.0), "W55": (6.4, 6.4), "W56": (14.0, 0.0), "W57": (14.0, -0.6),
            "W58": (10.4, 18.0), "W59": (8.0, 24.5), "W60": (13.0, 26.0), "W61": (7.6, 23.6),
            "W18": (8.6, 24.0), "W43": (19.8, 16.0), "W44": (18.9, 25.0), "W45": (21.2, 24.0), "W36": (12.4, 13.0), "W34": (4.5, 15.0)}


def part_stubs(ax, side):
    """Component leads seen from the solder side (grey dots)."""
    for name, p in CD.PARTS.items():
        for h in p["holes"]:
            x, y = pt(h, side)
            ax.add_patch(Circle((x, y), 0.5, fc="#777", ec="none", zorder=3))


def legend(ax, items, y=-7.4):
    x = -W_ / 2
    for txt, col, lw in items:
        ax.plot([x, x + 3.0], [y, y], color=col, lw=lw, solid_capstyle="round")
        ax.text(x + 3.6, y, txt, fontsize=5.4, va="center")
        x += 3.6 + 1.25 * len(txt) + 2.0


def bus_text():
    """'GND ring: row 2 from D2 to X2, up column X to X29, ...' from the bus paths."""
    out = {}
    for net, path, segs in CD.BUSES:
        out.setdefault(net, []).append(path)
    def legs(paths):
        t = []
        for path in paths:
            for (c0, r0), (c1, r1) in zip(path, path[1:]):
                t.append("%s-%s" % (L(c0, r0), L(c1, r1)))
        return ", ".join(t)
    return out, legs


def fig1():
    fig, ax = plt.subplots(figsize=(7.4, 9.6))
    board(ax, "component", "Carrier step C1 + C2: mark the board, then fit the 11 screw terminals",
          "Hold A1 at the bottom left, parts side toward you: pencil 'USB ^' at the top and circle A1. Terminal wire entries (arrows): "
          "J3 / J5 / J4 DOWN, J6-J11 toward the ESP32, J1 / J12 outward.")
    draw_esp(ax, "component", "ghost")
    draw_terminals(ax, "component", "now")
    xe = esp_x("component")
    kw, kl = ESP["usb_keepout"]
    y_k = ESP["z1"] - ZB
    ax.add_patch(Rectangle((xe - kw / 2, y_k), kw, min(kl, H_ - y_k), fc="none", ec="#c00", lw=0.7, ls=":", zorder=3))
    ax.text(xe, y_k + 9.0, "USB plug\nkeep-out:\nnothing tall", fontsize=4.8, color="#c00", ha="center", va="center")
    ax.text(X(0, "component") - 0.4, Y(NR - 1) + 2.6, "columns A, B, Y, Z and rows 30-31: spare", fontsize=4.4, color="#777", ha="left")
    stamp(ax, W_ / 2 + 8.5, -11.6, "guide_carrier_1_mark_terminals", rev=REV_I)
    save(fig, "guide_carrier_1_mark_terminals")


def fig2():
    fig, ax = plt.subplots(figsize=(7.4, 9.6))
    by_net, legs = bus_text()
    gnd = by_net["GND"]
    ring = "row %d from %s to %s, up column %s to %s, along row %d to %s, down column %s to %s" % (
        gnd[0][0][1] + 1, L(*gnd[0][0]), L(*gnd[0][1]), chr(65 + int(gnd[1][0][0])), L(*gnd[1][1]), int(gnd[2][0][1]) + 1, L(*gnd[2][1]),
        chr(65 + int(gnd[3][0][0])), L(*gnd[3][1]))
    a = by_net["5V_A"][0]
    bb = by_net["5V_B"][0]
    gap = CD.LK1_GAP
    board(ax, "solder", "Carrier step C3: the three bare 22 AWG buses (solder side)",
          "GND ring: %s.  Bus A: column %s %s-%s, then row %d to %s.  Bus B: column %s %s-%s.  %s stays EMPTY." % (
              ring, chr(65 + int(a[0][0])), L(*a[0]), L(*a[1]), int(a[1][1]) + 1, L(*a[2]), chr(65 + int(bb[0][0])), L(*bb[0]), L(*bb[1]), L(*gap)))
    part_stubs(ax, "solder")
    draw_terminals(ax, "solder", "ghost")
    draw_buses(ax, "solder", "now")
    tk = CD.tack_holes()
    for net, holes in tk.items():
        for h in holes:
            x, y = pt(h, "solder")
            ax.add_patch(Circle((x, y), 0.9, fc="none", ec="#0a7", lw=0.9, zorder=6))
    x, y = pt(gap, "solder")
    ax.add_patch(Circle((x, y), 1.2, fc="white", ec="#c00", lw=1.2, zorder=7))
    ax.text(x - 1.8, y, "%s EMPTY\n= LK1 gap" % L(*gap), fontsize=5.0, color="#c00", ha="right", va="center", fontweight="bold", zorder=8)
    j4_6 = tuple(CD.PARTS["J4"]["holes"][-1])
    c2_neg = tuple(CD.PARTS["C2"]["holes"][1])
    tp3 = next(h for h, nm in CD.TP_NAMES.items() if nm == "TP3")
    for h, t in ((j4_6, "J4 pin 6 stub %s\nsits ON the ring" % L(*j4_6)), (c2_neg, "C2 − lead %s\non the ring" % L(*c2_neg)), (tp3, "TP3 %s on\nthe ring" % L(*tp3))):
        x, y = pt(h, "solder")
        ax.annotate(t, xy=(x, y), xytext=(x + (6.0 if h[0] > 13 else -6.0), y + (-5.0 if h[1] < 10 else 3.6)), fontsize=4.8, ha="center", zorder=8,
                    arrowprops=dict(arrowstyle="-", color="#333", lw=0.5))
    ca = int(a[0][0])
    ax.text(X(ca, "solder") + 1.2, (Y(a[0][1]) + Y(a[1][1])) / 2, "bus A", fontsize=6, color=BUSCOL["5V_A"], fontweight="bold", ha="left", rotation=90, va="center")
    ax.text(X(ca, "solder") + 1.2, (Y(bb[0][1]) + Y(bb[1][1])) / 2, "bus B", fontsize=6, color=BUSCOL["5V_B"], fontweight="bold", ha="left", rotation=90, va="center")
    top_r, bot_r = int(gnd[2][0][1]), int(gnd[0][0][1])
    ax.text(X(12, "solder"), Y(top_r) + 1.2, "GND ring (top, row %d)" % (top_r + 1), fontsize=6, color="#333", fontweight="bold", ha="center")
    ax.text(X(13, "solder"), Y(bot_r) - 1.6, "GND ring (bottom, row %d)" % (bot_r + 1), fontsize=6, color="#333", fontweight="bold", ha="center", va="top")
    lens = {}
    for net, path, segs in CD.BUSES:
        lens[net] = lens.get(net, 0.0) + sum(s_[2] for s_ in segs)
    legend(ax, [("GND ring %.0f mm" % lens["GND"], "#3a3a3a", 3), ("bus A %.0f mm" % lens["5V_A"], BUSCOL["5V_A"], 3), ("bus B %.0f mm" % lens["5V_B"], BUSCOL["5V_B"], 3)])
    ax.text(W_ / 2, -9.6, "green circles = tack holes (a wire end or a lead lands there)", fontsize=5.2, color="#0a7", ha="right", va="center")
    stamp(ax, W_ / 2 + 8.5, -11.6, "guide_carrier_2_buses", rev=REV_I)
    save(fig, "guide_carrier_2_buses")


def fig3():
    fig, ax = plt.subplots(figsize=(7.4, 9.6))
    r1, r4 = CD.PARTS["R1"]["holes"], CD.PARTS["R4"]["holes"]
    c1, c2 = CD.PARTS["C1"]["holes"], CD.PARTS["C2"]["holes"]
    board(ax, "component", "Carrier steps C4 + C5: U1, then the small parts (component side)",
          "U1 notch UP, pin 1 at %s (top LEFT).  R1-R4 stand on row %d (%s-%s), folded lead into row %d.  C1: + UP at %s.  "
          "C2: + DOWN at %s, stripe (−) UP on the GND ring at %s." % (L(*U1[1]), r1[0][1] + 1, L(*r1[0]), L(*r4[0]), r1[1][1] + 1, L(*c1[0]), L(*c2[0]), L(*c2[1])))
    draw_esp(ax, "component", "ghost")
    draw_terminals(ax, "component", "done")
    draw_u1(ax, "component", "now")
    draw_passives(ax, "component", "now")
    stamp(ax, W_ / 2 + 8.5, -11.6, "guide_carrier_3_parts", rev=REV_I)
    save(fig, "guide_carrier_3_parts")


def fig4():
    fig, ax = plt.subplots(figsize=(7.4, 9.6))
    board(ax, "solder", "Carrier steps C6 + C7a: R5-R8 on the solder side, then every GND wire",
          "R5-R8 10k lie across U1's A / OE pin pairs 1-2 (%s-%s), 4-5 (%s-%s), 9-10 (%s-%s), 12-13 (%s-%s).  Bare links (copper) = one-hole hops; "
          "black = 26 AWG insulated.  Red-ringed white ends = ESP32 pin holes: leave those ends free until C9." % (
              L(*U1[1]), L(*U1[2]), L(*U1[4]), L(*U1[5]), L(*U1[9]), L(*U1[10]), L(*U1[12]), L(*U1[13])))
    part_stubs(ax, "solder")
    draw_terminals(ax, "solder", "ghost")
    draw_u1(ax, "solder", "ghost")
    draw_buses(ax, "solder", "done")
    xmid = (X(U1_L, "solder") + X(U1_R, "solder")) / 2
    for a, b, nm in ((1, 2, "R5"), (4, 5, "R6"), (9, 10, "R7"), (12, 13, "R8")):
        (xa, ya), (xb, yb) = pt(U1[a], "solder"), pt(U1[b], "solder")
        ax.plot([xa, xb], [ya, yb], color="#135", lw=0.8, zorder=6)
        mx, my = (xa + xb) / 2, (ya + yb) / 2
        ax.add_patch(Rectangle((mx - 0.9, my - 0.75), 1.8, 1.5, fc="#bde0fe", ec="#135", lw=0.6, zorder=7))
        inward = -1 if xa > xmid else 1
        ax.text(mx + inward * 1.4, my, nm + " 10k", fontsize=4.4, ha="right" if inward < 0 else "left", va="center", zorder=8, fontweight="bold")
    draw_wires(ax, "solder", [w for w in CD.WIRES if w["step"] == "C7a"], "now")
    legend(ax, [("bare link (offcut)", "#b08d57", 2.2), ("26 AWG black", WC["black"], 1.7), ("bus (done)", "#bbb", 2.6)])
    stamp(ax, W_ / 2 + 8.5, -11.6, "guide_carrier_4_gnd", rev=REV_I)
    save(fig, "guide_carrier_4_gnd")


def fig5():
    fig, ax = plt.subplots(figsize=(7.4, 9.6))
    tp2 = next(h for h, nm in CD.TP_NAMES.items() if nm == "TP2")
    board(ax, "solder", "Carrier step C7b: the 5 V wires (22 AWG red), LK1 (22 AWG yellow)",
          "TP2 %s takes three wire ends (W43, W44, W45) plus the TP2 loop: solder them in one go.  LK1 (W38) jumps the empty hole %s." % (L(*tp2), L(*CD.LK1_GAP)))
    part_stubs(ax, "solder")
    draw_terminals(ax, "solder", "ghost")
    draw_u1(ax, "solder", "ghost")
    draw_buses(ax, "solder", "done")
    draw_wires(ax, "solder", [w for w in CD.WIRES if w["step"] == "C7a"], "done")
    draw_wires(ax, "solder", [w for w in CD.WIRES if w["step"] == "C7b"], "now")
    legend(ax, [("22 AWG red (5 V)", WC["red"], 2.2), ("22 AWG yellow (LK1)", WC["yellow"], 2.2), ("bare link", "#b08d57", 2.2), ("done", "#c4c4c4", 1.2)])
    stamp(ax, W_ / 2 + 8.5, -11.6, "guide_carrier_5_5v", rev=REV_I)
    save(fig, "guide_carrier_5_5v")


IN_SIDE = ("W46", "W47", "W48", "W49", "W58", "W59", "W60", "W61")


def lane_rows(wid):
    """The horizontal lane rows of a wire's run (fractional r), e.g. W48 -> 12.4."""
    w = next(w for w in CD.WIRES if w["id"] == wid)
    rows = [p[1] for p in w["path"] if not float(p[1]).is_integer()]
    return rows


def fig6():
    fig, ax = plt.subplots(figsize=(7.4, 9.6))
    r48, r49 = lane_rows("W48")[0], lane_rows("W49")[0]
    board(ax, "solder", "Carrier step C7c (part 1) + C7d: ESP32 -> U1 inputs, the hall network, 3V3 (28 AWG)",
          "W48 / W49 run under the ESP32's position along lanes r %g / %g (just above printed row %d).  Every red-ringed end is an ESP32 pin hole: lay the wire, "
          "solder the OTHER end now, leave this end free until C9." % (r48, r49, int(r49) + 1))
    part_stubs(ax, "solder")
    draw_terminals(ax, "solder", "ghost")
    draw_u1(ax, "solder", "ghost")
    draw_buses(ax, "solder", "done")
    draw_wires(ax, "solder", [w for w in CD.WIRES if w["step"] in ("C7a", "C7b")], "done", labels=False)
    draw_wires(ax, "solder", [w for w in CD.WIRES if w["id"] in IN_SIDE], "now")
    legend(ax, [("CLK (yellow)", WC["yellow"], 1.6), ("DATA (orange)", WC["orange"], 1.6), ("hall (white)", "#bbbbbb", 1.6), ("3V3 (violet)", WC["violet"], 1.6)])
    stamp(ax, W_ / 2 + 8.5, -11.6, "guide_carrier_6_inputs_hall", rev=REV_I)
    save(fig, "guide_carrier_6_inputs_hall")


def fig6b():
    fig, ax = plt.subplots(figsize=(7.4, 9.6))
    r56 = min(lane_rows("W56"))
    r57 = min(lane_rows("W57"))
    board(ax, "solder", "Carrier step C7c (part 2): U1 outputs -> R1-R4 -> J3 / J4 (28 AWG)",
          "W50-W53: U1 pins 3 / 6 / 8 / 11 down to the resistor tops.  W54 / W55 up into J3 pins 3 / 5;  W56 / W57 along lanes r %g / %g "
          "(between printed rows 1 and 2) under the GND ring and up into J4 pins 3 / 5." % (r56, r57))
    part_stubs(ax, "solder")
    draw_terminals(ax, "solder", "ghost")
    draw_u1(ax, "solder", "ghost")
    draw_buses(ax, "solder", "done")
    draw_wires(ax, "solder", [w for w in CD.WIRES if w["step"] in ("C7a", "C7b") or w["id"] in IN_SIDE], "done", labels=False)
    draw_wires(ax, "solder", [w for w in CD.WIRES if w["step"] == "C7c" and w["id"] not in IN_SIDE], "now")
    legend(ax, [("CLK (yellow)", WC["yellow"], 1.6), ("DATA (orange)", WC["orange"], 1.6), ("done", "#c4c4c4", 1.2)])
    stamp(ax, W_ / 2 + 8.5, -11.6, "guide_carrier_6b_outputs", rev=REV_I)
    save(fig, "guide_carrier_6b_outputs")


def fig7():
    fig, axs = plt.subplots(1, 2, figsize=(13.0, 9.0))
    ax = axs[0]
    pin = lambda nm, s=None: next((ESP["C"][k], ESP["R0"] + ESP[k].index(nm)) for k in ("L", "R") if nm in ESP[k] and (s is None or s == k))
    board(ax, "component", "C9a: the ESP32 goes in last (component side)",
          "30 pins through columns %s / %s, rows %d-%d, USB UP; PCB on its spacers.\nCorner pins (yellow): VIN %s, 3V3 %s, EN %s, D23 %s." % (
              chr(65 + ESP_CL), chr(65 + ESP_CR), ESP_ROWS[0], ESP_ROWS[1], L(*pin("VIN")), L(*pin("3V3")), L(*pin("EN")), L(*pin("IO23"))))
    draw_terminals(ax, "component", "done")
    draw_u1(ax, "component", "done")
    draw_passives(ax, "component", "done")
    draw_esp(ax, "component", "now")
    ax = axs[1]
    board(ax, "solder", "C9b: then lap the nine waiting wire ends onto the pin stubs",
          "Trim the 30 pins to ~1.5 mm first.  Then W18, W19 (GND), W30 (VIN),\nW46-W49 (IO18 / IO23 / IO14 / IO13), W60 (IO27), W61 (3V3).")
    part_stubs(ax, "solder")
    draw_buses(ax, "solder", "done")
    waiting = [w for w in CD.WIRES if w["esp_end"]]
    draw_wires(ax, "solder", [w for w in CD.WIRES if not w["esp_end"]], "done", labels=False)
    draw_wires(ax, "solder", waiting, "now")
    for s in ("L", "R"):
        for i, nm in enumerate(ESP[s]):
            h = (ESP["C"][s], ESP["R0"] + i)
            x, y = pt(h, "solder")
            ax.add_patch(Circle((x, y), 0.55, fc="#ffd60a" if nm in ("VIN", "3V3", "EN", "IO23") else "#999", ec="#000", lw=0.3, zorder=4))
            if nm in ("IO23", "IO18", "IO13", "IO14", "IO27", "VIN", "3V3", "GND", "EN"):
                ax.text(x + (-1.3 if s == "L" else 1.3), y, "%s %s" % (nm, L(*h)), fontsize=3.8, ha="right" if s == "L" else "left", va="center", zorder=7, color="#b00")
    stamp(ax, W_ / 2 + 8.5, -11.6, "guide_carrier_7_esp32", rev=REV_I)
    save(fig, "guide_carrier_7_esp32")


if __name__ == "__main__":
    for f in (fig1, fig2, fig3, fig4, fig5, fig6, fig6b, fig7):
        f()
