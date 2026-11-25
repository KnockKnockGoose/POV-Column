"""Rev n report figures: three labelled section drawings from the CAD dimensions (2026-11-17).

  docs/img/revn_fig_failure.png    rev m.2 spool in the hub core's pocket: the plane that broke and the four things that meet on it
  docs/img/revn_fig_loadpath.png   rev n: pin drive, hub, bearing cup; what carries torque, preload and a push on the rotor
  docs/img/revn_fig_takeup.png     rev n: the slip ring hangs under the deck as the take-up weight; rotor seated and rotor lifted

Colours: three validated categorical slots (blue / orange / aqua, dataviz reference palette, validate_palette.js --pairs all: pass) for the
printed drive parts, neutral greys for everything that already exists, the reserved "critical" red only for the fracture plane. Every part
is labelled directly, so nothing is told by colour alone.

Run: py calc/revn_figures.py
"""
import os
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Rectangle, FancyArrowPatch

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(HERE, "..", "docs", "img")
SURF, INK, INK2, MUTE = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8983"
BLUE, ORANGE, AQUA, CRIT = "#2a78d6", "#eb6834", "#1baf7a", "#d03b3b"
G_CORE, G_PLATE, G_DECK, G_RING, STEEL, BRASS = "#c9c8c2", "#dddcd6", "#e6e5e0", "#b4b3ad", "#55544f", "#b08d57"


def poly(ax, pts, fc, ec=INK, lw=0.8, alpha=1.0, mirror=True, z=2, hatch=None):
    for s in ((1, -1) if mirror else (1,)):
        ax.add_patch(Polygon([(s * r, zz) for r, zz in pts], closed=True, fc=fc, ec=ec, lw=lw, alpha=alpha, zorder=z, hatch=hatch))


def rect(ax, r0, r1, z0, z1, fc, mirror=True, z=3, ec=INK, lw=0.8, hatch=None, alpha=1.0):
    poly(ax, [(r0, z0), (r1, z0), (r1, z1), (r0, z1)], fc, ec, lw, alpha, mirror, z, hatch)


def label(ax, text, xy, xytext, ha="left", va="center", size=8.6, color=INK, weight="normal"):
    ax.annotate(text, xy=xy, xytext=xytext, ha=ha, va=va, fontsize=size, color=color, fontweight=weight, zorder=20,
                arrowprops=dict(arrowstyle="-", lw=0.7, color=INK2, shrinkA=1.5, shrinkB=0))


def base(ax, title, xlim, ylim):
    ax.set_facecolor(SURF)
    ax.set_aspect("equal")
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.axvline(0, color=MUTE, lw=0.7, ls=(0, (8, 3, 2, 3)), zorder=1)
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title(title, loc="left", fontsize=11.5, color=INK, fontweight="bold", pad=10)


def core_and_plate(ax):
    """Hub core (existing, PET-CF) and bottom-cap plate, section through a coupling hole at r 8."""
    poly(ax, [(3.5, 2), (3.5, 8), (6.3, 8), (6.3, 2)], G_CORE)                         # floor inside the screw hole
    poly(ax, [(9.7, 2), (9.7, 8), (22.5, 8), (22.5, 0), (14, 0), (14, -2), (11.2, -2), (11.2, 2)], G_CORE)
    rect(ax, 14.2, 27.0, -2, 0, G_PLATE)


def fig_failure():
    fig, ax = plt.subplots(figsize=(11.6, 6.4), dpi=170)
    fig.patch.set_facecolor(SURF)
    base(ax, "Rev m.2: where the printed spool broke (section through one insert, mm)", (-56.5, 44), (-15.5, 14.0))
    core_and_plate(ax)
    # spool (blue): outline with the bore and the insert hole
    spool = [(3, 2), (6, 2), (6, -3), (10, -3), (10, 2), (11.1, 2), (11.1, -3.08), (14, -3.08), (12.43, -4.6), (12.43, -11.6), (14, -11.6), (14, -13.1),
             (6.2, -13.1), (6.2, -5.3), (3, -2.1)]
    poly(ax, spool, BLUE, alpha=0.62)
    for zt in [x * 0.7 - 11.25 for x in range(10)]:                                     # tooth zone hint
        for s in (1, -1):
            ax.plot([s * 12.43, s * 11.9], [zt, zt], color=INK, lw=0.5, zorder=4)
    rect(ax, 5.9, 6.6, -2, 2, BRASS, z=5)                                               # insert wall (section)
    rect(ax, 9.4, 10.1, -2, 2, BRASS, z=5)
    rect(ax, 6.0, 10.0, -3, -2, "#9fb6d8", z=4, hatch="xxxx", lw=0.4)                   # relief full of re-solidified melt
    rect(ax, 6.6, 9.4, -2, 8, STEEL, z=6)                                               # M3 x 10 shank
    rect(ax, 5.25, 10.75, 8, 11, STEEL, z=6)                                            # head
    rect(ax, 12.6, 13.95, -11.1, -5.1, INK, mirror=False, z=6)                          # belt (one side)
    # fracture plane
    for s in (1, -1):
        ax.plot([s * 3.9, s * 11.1], [-3.04, -3.04], color=CRIT, lw=2.4, ls=(0, (4, 1.6)), zorder=12, solid_capstyle="butt")
    # labels (right side: what is there; left side: what went wrong)
    label(ax, "hub core (PET-CF), 6 mm floor", (18, 5), (24.5, 10.6))
    label(ax, "bottom-cap plate", (23, -1), (28.5, 1.6))
    label(ax, "M3 × 10 from the core top", (8, 9.5), (13.5, 12.4))
    label(ax, "M3 × 4 heat-set insert", (9.75, 0.6), (24.5, 3.9))
    label(ax, "drive spool (PET-CF),\nprinted plug-up", (13.2, -8.6), (24.5, -7.6))
    label(ax, "40T teeth + belt", (13.3, -10.2), (24.5, -11.4))
    label(ax, "bore for the lead guide", (4.5, -9.5), (24.5, -14.2))
    label(ax, "① last 5 mm printed alone: short, fan-cooled\n    layers, the weakest bond in the part", (-8.4, 1.3), (-55.5, 11.6), ha="left")
    label(ax, "② 1.1 mm of wall outside each insert\n    (own rule: ≥ 2.5 mm)", (-10.55, -0.4), (-55.5, 7.6), ha="left")
    label(ax, "③ screw tip ends exactly at the insert's\n    bottom; the 1 mm relief below is full of\n    displaced melt, so the screw jacks the\n    plug off the pulley (500–830 N each)", (-8.0, -2.5), (-55.5, 2.6), ha="left")
    label(ax, "④ Ø22.2 → Ø28 step: a sharp inside\n    corner on the same layer", (-11.1, -3.08), (-55.5, -2.9), ha="left")
    label(ax, "✕  FRACTURE PLANE  z ≈ −3.0\nthe plug with the inserts came off the pulley", (-7.2, -3.04), (-55.5, -7.0), ha="left", color=CRIT, weight="bold", size=9.2)
    label(ax, "⑤ 1.5 mm ligament to the bore's cone", (-5.3, -3.9), (-55.5, -10.6), ha="left")
    ax.text(0.5, -15.1, "spin axis", ha="left", va="bottom", fontsize=7.5, color=MUTE)
    fig.savefig(os.path.join(IMG, "revn_fig_failure.png"), facecolor=SURF, bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)


def fig_loadpath():
    fig, ax = plt.subplots(figsize=(11.8, 8.0), dpi=170)
    fig.patch.set_facecolor(SURF)
    base(ax, "Rev n: section through two drive pins (mm). Steel carries the torque; the plastic is only squeezed", (-59, 47), (-30.5, 14.5))
    core_and_plate(ax)
    # deck and clamp ring (existing); the slip ring now hangs below the frame
    rect(ax, 9.0, 30.0, -27.5, -23.5, G_DECK)
    poly(ax, [(6, -22.3), (6, -20.3), (14, -20.3), (14, -23.4), (12.2, -23.4), (12.2, -22.3)], G_CORE)                             # clamp ring
    # bearing cup (aqua)
    poly(ax, [(10.75, -20.3), (10.75, -19.7), (12.2, -19.7), (12.2, -15.2), (14.5, -15.2), (14.5, -20.3)], AQUA, alpha=0.75)
    # 6802
    rect(ax, 7.5, 8.95, -19.7, -14.7, STEEL, z=5)
    rect(ax, 10.55, 12.0, -19.7, -14.7, STEEL, z=5)
    for s in (1, -1):
        ax.add_patch(plt.Circle((s * 9.75, -17.2), 0.78, fc="#d9d8d2", ec=INK, lw=0.6, zorder=6))
    # drive hub (blue): section through a notch -> outer wall + body below the notch floor
    hub = [(10.0, -3.1), (11.7, -3.1), (12.0, -4.6), (12.48, -4.6), (12.48, -11.6), (14, -13.1), (8.5, -13.1), (8.5, -14.7), (7.3, -14.7), (7.3, -18.3), (3.8, -18.3),
           (2.3, -17.0), (2.3, -15.8), (5.5, -12.8), (5.5, -10.8), (10.0, -10.8)]
    poly(ax, hub, BLUE, alpha=0.62)
    for zt in [x * 0.7 - 11.25 for x in range(10)]:
        for s in (1, -1):
            ax.plot([s * 12.48, s * 11.9], [zt, zt], color=INK, lw=0.5, zorder=4)
    rect(ax, 12.65, 14.0, -11.1, -5.1, INK, mirror=False, z=6)                          # belt
    # nut plate (orange) with the XH window and membrane
    poly(ax, [(3.8, -2), (3.8, 0.4), (0.0, 0.4), (0.0, 2), (6.3, 2), (6.3, 0.6), (4.77, 0.6), (4.77, -2)], ORANGE, alpha=0.7)
    poly(ax, [(9.7, 2), (11.1, 2), (11.1, -2), (11.0, -2), (11.0, 0.6), (9.7, 0.6)], ORANGE, alpha=0.7)
    # nuts and pins (steel)
    rect(ax, 5.25, 6.5, -1.8, 0.6, STEEL, z=6)
    rect(ax, 9.5, 10.75, -1.8, 0.6, STEEL, z=6)
    rect(ax, 6.5, 9.5, -8.0, 8, STEEL, z=6)
    rect(ax, 5.25, 10.75, 8, 11, STEEL, z=6)
    # XH header + plug, leads, knot
    rect(ax, 0, 3.7, -6.6, 0.4, "#f4f3ee", z=7)
    rect(ax, 0, 3.4, -10.6, -6.6, "#ffffff", z=7)
    for s in (1, -1):
        ax.plot([s * 1.25, s * 1.25], [0.4, 3.6], color=STEEL, lw=1.4, zorder=8)
        ax.plot([s * 1.25, s * 2.3, s * 0.65, s * 0.65], [-10.6, -12.2, -13.1, -30.5], color=INK2, lw=1.1, zorder=8)
        ax.plot([s * 1.25, s * 0.9, s * 0.75], [3.6, 6.5, 13.5], color=INK2, lw=1.1, zorder=8)
    rect(ax, 0, 2.1, -15.6, -13.1, "#ffffff", z=9)                                    # stop B (zip tie) resting on the neck
    # arrows: torque path (belt -> teeth -> in the same layers -> notch wall -> pin -> core)
    def arrow(p0, p1, color=INK, lw=1.5, rad=0.0, style="-|>"):
        ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle=style, mutation_scale=9, lw=lw, color=color, zorder=15, connectionstyle="arc3,rad=%.2f" % rad))
    arrow((13.3, -7.0), (10.4, -7.0))
    arrow((9.7, -6.6), (9.7, 3.6), rad=0.0)
    arrow((10.4, 5.2), (16.0, 5.2))
    # preload (compression) between head and nut
    arrow((-8.0, 7.6), (-8.0, 2.4), color=INK, lw=1.3)
    arrow((-8.0, -1.9), (-8.0, 1.6), color=INK, lw=1.3)
    # labels, right: parts
    label(ax, "hub core (existing)", (18, 5), (25.5, 11.2))
    label(ax, "4 × M3 × 16 = the drive pins", (8, 9.6), (14.0, 13.2))
    label(ax, "nut plate (new, 4 mm): captive M3 nuts,\nXH header clinched in its centre", (10.4, 1.2), (25.5, 7.4))
    label(ax, "bottom-cap plate", (24, -1), (30.5, 2.4))
    label(ax, "torque: belt → teeth → notch wall → pin → core.\nTeeth and notches are in the same layers,\nso no layer has to pass it on", (10.2, -7.0), (25.5, -6.4))
    label(ax, "drive hub (new, PETG-CF)", (13.2, -12.4), (25.5, -11.6))
    label(ax, "6802-2RS bearing", (11.3, -17.2), (25.5, -15.2))
    label(ax, "bearing cup (new, PETG-CF)", (13.6, -18.2), (25.5, -18.4))
    label(ax, "clamp ring (kept from rev m.2): now the cup's seat", (13.2, -21.4), (25.5, -21.4))
    label(ax, "deck of the base shell (unchanged)", (22, -25.5), (25.5, -24.9))
    label(ax, "d18 hole in the deck: only the six leads pass", (8.9, -26.4), (25.5, -28.6), ha="left")
    # labels, left: what each joint does
    label(ax, "screw preload squeezes the core floor and the\nplate between head and nut: nothing to bottom\nin, nothing a screw can pull apart", (-8.6, 4.0), (-58.0, 11.3), ha="left")
    label(ax, "1.1 mm gap: the rotor never rests on the hub;\npins have 0.5 mm play in 4 notches, so the\nrotor lifts straight off", (-9.0, -2.55), (-58.0, 4.6), ha="left")
    label(ax, "XH plug on the slip ring's own six leads;\nonly 5 mm of slack, inside the hub's bore", (-2.6, -8.6), (-58.0, -1.9), ha="left")
    label(ax, "pin notch: 4.0 wide, to z −10.8\n(pin tips at −8.0)", (-8.0, -9.4), (-58.0, -7.6), ha="left")
    label(ax, "lead neck 4.6 × 3.0: the leads slide in it.\nA zip tie on them (stop B) rests on the\nneck and carries the hanging slip ring", (-1.9, -14.4), (-58.0, -13.8), ha="left")
    label(ax, "a push on the rotor with the pins on the\ncrown goes hub → bearing → cup → clamp\nring → deck, all in compression", (-12.8, -19.9), (-58.0, -20.6), ha="left")
    label(ax, "the leads go on down to the slip ring,\nwhich hangs under the deck and\nkeeps them taut", (-0.9, -27.0), (-58.0, -26.9), ha="left")
    ax.text(0.5, -30.1, "spin axis", ha="left", va="bottom", fontsize=7.5, color=MUTE)
    fig.savefig(os.path.join(IMG, "revn_fig_loadpath.png"), facecolor=SURF, bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)


def fig_takeup():
    """Two states of the lead take-up: rotor seated (ring hangs, stop B on the neck) and rotor lifted 50 mm (ring risen 45 mm, knot A under the neck)."""
    fig, axes = plt.subplots(1, 2, figsize=(14.6, 9.4), dpi=170, gridspec_kw=dict(wspace=0.03))
    fig.patch.set_facecolor(SURF)
    for ax, lift, rise, title in ((axes[0], 0.0, 0.0, "Rotor seated: the ring hangs, the leads stay taut"),
                                  (axes[1], 50.5, 45.0, "Rotor lifted 50 mm with the plug in")):
        left = lift == 0.0
        e = -1 if left else 1                 # the side the labels are on
        m = -e                                # the side the motor is drawn on
        base(ax, title, (-100, 42) if left else (-42, 100), (-112, 66))
        # base: floor, deck, clamp ring, cup, bearing, hub
        rect(ax, 0, 40, -109, -106, G_PLATE)
        rect(ax, 9.0, 40, -27.5, -23.5, G_DECK)
        poly(ax, [(6, -22.3), (6, -20.3), (14, -20.3), (14, -23.4), (12.2, -23.4), (12.2, -22.3)], G_CORE)
        poly(ax, [(10.75, -20.3), (10.75, -19.7), (12.2, -19.7), (12.2, -15.2), (14.5, -15.2), (14.5, -20.3)], AQUA, alpha=0.75)
        rect(ax, 7.5, 8.95, -19.7, -14.7, STEEL, z=5)
        rect(ax, 10.55, 12.0, -19.7, -14.7, STEEL, z=5)
        hub = [(6.15, -3.1), (11.7, -3.1), (12.0, -4.6), (12.48, -4.6), (12.48, -11.6), (14, -13.1), (8.5, -13.1), (8.5, -14.7), (7.3, -14.7), (7.3, -18.3), (3.8, -18.3),
               (2.3, -17.0), (2.3, -15.8), (5.5, -12.8), (5.5, -10.8), (6.15, -10.8)]
        poly(ax, hub, BLUE, alpha=0.62)
        # motor on its hanger, beside the column (one side only, away from the labels)
        for (x0, x1, z0, z1, fc) in ((14.0, 40.0, -33.5, -27.5, G_CORE), (19.0, 40.0, -52.8, -33.5, G_PLATE), (21.0, 40.0, -81.0, -52.8, G_PLATE)):
            ax.add_patch(Rectangle((min(m * x0, m * x1), z0), abs(x1 - x0), z1 - z0, fc=fc, ec=INK2, lw=0.6, alpha=0.55, zorder=1))
        ax.text(m * 30.0, -60.0, "motor on\nits hanger", ha="center", va="center", fontsize=8.0, color=INK2, zorder=4)
        # rotor (moves with the lift): plate, hub core, nut plate, header, pins
        rect(ax, 14.2, 40, -2 + lift, 0 + lift, G_PLATE)
        poly(ax, [(3.5, 2 + lift), (3.5, 8 + lift), (22.5, 8 + lift), (22.5, 0 + lift), (14, 0 + lift), (14, -2 + lift), (11.2, -2 + lift), (11.2, 2 + lift)], G_CORE)
        rect(ax, 0, 11.1, -2 + lift, 2 + lift, ORANGE, alpha=0.7)
        rect(ax, 0, 3.7, -6.6 + lift, 0.4 + lift, "#f4f3ee", z=7)
        rect(ax, 6.5, 9.5, -8.0 + lift, 8 + lift, STEEL, z=6)
        rect(ax, 5.25, 10.75, 8 + lift, 11 + lift, STEEL, z=6)
        # plug, stop B, knot A, slip ring
        zp = -10.6 + lift
        rect(ax, 0, 3.4, zp, zp + 4.0, "#ffffff", z=8)
        zb = -15.6 + rise
        rect(ax, 0, 2.1, zb, zb + 2.5, "#ffffff", z=9)
        za = -64.0 + rise
        ax.add_patch(plt.Circle((0, za), 3.0, fc=INK2, ec=INK, lw=0.6, zorder=9))
        zf = -77.5 + rise
        rect(ax, 0, 2.5, zf, zf + 1.5, G_RING, z=6)
        rect(ax, 0, 12.0, zf - 1.2, zf, G_RING, z=6)
        rect(ax, 0, 6.25, zf - 16.2, zf - 1.2, G_RING, z=6)
        for sx in (1, -1):
            if left:
                ax.plot([sx * 0.65, sx * 0.65, sx * 2.4, sx * 1.25], [zf + 1.5, zb + 2.5, zb + 3.6, zp], color=INK2, lw=1.2, zorder=8)
            else:
                ax.plot([sx * 0.65, sx * 0.65, sx * 1.25], [zf + 1.5, zp - 5.0, zp], color=INK2, lw=1.2, zorder=8)
            ax.plot([sx * 1.25, sx * 0.9, sx * 0.75], [3.6 + lift, 6.5 + lift, 13.5 + lift], color=INK2, lw=1.1, zorder=8)
        # stator leads: a loose loop, drawn under the motor side
        ax.plot([0.0, 0.0, m * 5.0, m * 18.0, m * 31.0, m * 39.0], [zf - 16.2, zf - 21.0, zf - 24.5 if left else -66.0, -97.0, -93.0, -89.0],
                color=INK2, lw=1.2, ls=(0, (4, 2)), zorder=7)
        tx = e * 98.0
        ha = "left" if left else "right"
        if left:
            label(ax, "XH plug in the header under the rotor", (e * 3.4, zp + 1.5), (tx, 22.0), ha=ha)
            label(ax, "5 mm of slack lead: it stays inside the hub's bore", (e * 2.3, zb + 3.6), (tx, 9.0), ha=ha)
            label(ax, "stop B: a zip tie on the leads. It rests on\nthe hub's neck and carries the ring", (e * 2.1, zb + 1.2), (tx, -6.0), ha=ha)
            label(ax, "deck (d18 hole) and clamp ring (d12):\nonly the six leads pass, 4.7 mm clear", (e * 9.0, -25.5), (tx, -26.0), ha=ha)
            label(ax, "six rotor leads: they turn with the rotor\nand are always in tension", (e * 0.65, -45.0), (tx, -45.0), ha=ha)
            label(ax, "knot A, 10 mm above the ring", (e * 3.0, za), (tx, -62.0), ha=ha)
            label(ax, "slip ring (it went in from below). Its boss and\nleads turn; its body and flange do not", (e * 6.25, zf - 8.0), (tx, -79.0), ha=ha)
            label(ax, "12 mm to the bottom plate", (e * 3.0, -100.0), (tx, -96.0), ha=ha)
            ax.text(m * 30.0, -101.5, "stator leads:\na loose loop", ha="center", va="center", fontsize=8.0, color=INK2, zorder=4)
        else:
            label(ax, "rotor held 50 mm up: about 40 mm of room\nfor a hand under its rim", (e * 30.0, -1.0 + lift), (tx, 62.0), ha=ha, va="top")
            label(ax, "plug it in or out here, by hand", (e * 3.4, zp + 1.5), (tx, 40.0), ha=ha)
            label(ax, "stop B has risen with the leads", (e * 2.1, zb + 1.2), (tx, 28.0), ha=ha)
            label(ax, "the leads slide up through the neck (4.6 × 3.0);\nthe ring's weight keeps them straight,\nso nothing can loop", (e * 0.65, 10.0), (tx, 10.0), ha=ha)
            label(ax, "knot A stops under the neck: any further\npull ends here, not in the slip ring", (e * 3.0, za), (tx, -14.0), ha=ha)
            label(ax, "the flange stops 5 mm below the deck,\n2 mm from the hanger's edge", (e * 12.0, zf - 0.6), (tx, -37.0), ha=ha)
            label(ax, "let go of the plug and the ring sinks back\nuntil stop B sits on the neck; the plug\nthen waits 7 mm above the hub", (e * 6.25, zf - 8.0), (tx, -60.0), ha=ha)
            ax.annotate("", xy=(e * 20.0, -77.5), xytext=(e * 20.0, -32.5), arrowprops=dict(arrowstyle="<|-|>", lw=1.0, color=INK2), zorder=12)
            ax.text(e * 22.0, -80.5, "45 mm of travel", ha="left", va="top", fontsize=8.6, color=INK)
            ax.plot([e * 13.0, e * 24.0], [-77.5, -77.5], color=MUTE, lw=0.6, ls=(0, (3, 2)), zorder=3)
        ax.text(0.8, -111.5, "spin axis", ha="left", va="bottom", fontsize=7.5, color=MUTE)
    fig.savefig(os.path.join(IMG, "revn_fig_takeup.png"), facecolor=SURF, bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)


if __name__ == "__main__":
    fig_failure()
    fig_loadpath()
    fig_takeup()
    print("wrote docs/img/revn_fig_failure.png, revn_fig_loadpath.png, revn_fig_takeup.png")
