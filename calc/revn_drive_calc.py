"""Rev n drive redesign: the numbers behind docs/2026-11-17-rev-n-drive-redesign.md (2026-11-17).

Part A  why the rev m.2 printed spool broke (plug / flange junction): section, service stresses, assembly loads
Part B  rev n load paths: pins, notches, hub, bearing, pin-drive kinematics with the two axes offset, belt fit,
        and the lead take-up (B7): why the slip ring hangs under the deck instead of being clamped to it
Part C  assembly-step counts

SI inside; mm / N / MPa printed. Geometry from fusionclaude/lib/povlib.py (rev m / m.2 / n blocks). Material numbers are datasheet
values (Polymaker Fiberon PET-CF17, Bambu PETG-CF) and ASSUMED knock-downs, marked.

Run: py calc/revn_drive_calc.py   -> prints the tables, writes calc/revn_drive_calc.json
"""
import json
import math
import os

OUT = {}


def show(title, rows):
    print("\n== " + title)
    for k, v, unit, note in rows:
        vs = ("%.3g" % v) if isinstance(v, float) else str(v)
        print("   %-64s %10s %-8s %s" % (k, vs, unit, note))
    OUT[title] = [{"item": k, "value": v, "unit": unit, "note": note} for k, v, unit, note in rows]


# ---------------------------------------------------------------- loads (rev m report, calc/rev_m_power_calc.py)
T_RUN = 0.029            # N m at the rotor, 225 rpm (27 mN m air drag + 2 bearing)
T_SPINUP = 0.060         # N m at the rotor during a 1.5 s spin-up
T_STALL_MOTOR = 0.22     # N m at the gearbox output (estimated stall, listings disagree)
RATIO = 2.0              # 20T -> 40T
T_STALL = T_STALL_MOTOR * RATIO
BELT_STRAND = 4.0        # N static tension per strand (finger tension)
BELT_RADIAL = 2 * BELT_STRAND
RPM = 225.0
W = 2 * math.pi * RPM / 60.0

# ---------------------------------------------------------------- materials
PETCF_Z = 27.9           # MPa, Fiberon PET-CF17 tensile strength between layers (datasheet, dry, as printed)
PETCF_Z_EPS = 0.008      # elongation at break between layers
PETCF_XY = 60.0          # MPa in-plane (order of magnitude)
KD_SMALL_LAYER = 0.5     # ASSUMED knock-down for 10 s layers at ~95 % part fan (the plug printed alone); 0.3-0.6 is typical for CF copolyesters
PETGCF_Z = 30.0          # MPa, Bambu PETG-CF layer strength (ASSUMED from the TDS's Z tensile ~ 30)
PETGCF_XY = 55.0
TAU_Z = lambda s: 0.577 * s      # shear from tensile (von Mises)

# ================================================================ Part A: the rev m.2 spool
R_PLUG = 11.1            # plug d22.2
R_FLANGE = 14.0          # cone top r 14 at z -3.08 (the step)
R_WIRE = 3.0
N_INS, D_INS, DEPTH_INS, R_INS = 4, 4.0, 5.0, 8.0     # 4 x d4.0 x 5 insert holes at r 8
L_INS, D_INS_OD = 4.0, 4.2                            # M3 x 4 insert, 4.2 over the knurl
D_HOLE_PRINT = 3.75                                   # H2D prints d4.0 holes 0.2-0.3 small
Z_STEP, Z_HOLE_BOT = -3.08, -3.0
R_BORE_AT_STEP = 6.2 - (Z_STEP + 5.3)                 # 45 deg bore cone: r 6.2 at z -5.3
A_gross = math.pi * (R_PLUG ** 2 - R_BORE_AT_STEP ** 2)
A_holes = N_INS * math.pi * (D_INS / 2) ** 2
A_net = A_gross - A_holes
J_net = 0.8 * math.pi / 2 * (R_PLUG ** 4 - R_BORE_AT_STEP ** 4)     # mm4, -20 % for the 4 holes
I_net = J_net / 2
wall_out = R_PLUG - (R_INS + D_INS / 2)
wall_cone = (5.3 - 3.0 - (6.2 - (R_INS - D_INS / 2))) / math.sqrt(2)    # hole-bottom inner corner to the bore cone, normal distance
show("A1 rev m.2 spool: the section that broke (plane of the insert-hole bottoms, z -3.0 .. -3.08)", [
    ("plug diameter / flange diameter at the step", "22.2 / 28", "mm", "sharp inside corner, no fillet, on a layer line"),
    ("insert holes", "4 x d4.0 x 5", "mm", "bottoms at z -3.0: 0.08 mm above the step"),
    ("wall outside each insert hole", wall_out, "mm", "own rule since rev f: >= 2.5 mm"),
    ("ligament, hole bottom to the bore's 45 deg cone", wall_cone, "mm", ""),
    ("net area at the plane", A_net, "mm2", "gross %.0f - 4 holes %.0f" % (A_gross, A_holes)),
    ("polar second moment (net)", J_net, "mm4", ""),
])
tau_run = T_RUN * 1e3 * R_PLUG / J_net
tau_stall = T_STALL * 1e3 * R_PLUG / J_net
M_belt = BELT_RADIAL * (8.1 - 3.08)
sig_belt = M_belt * R_PLUG / I_net
show("A2 service loads on that section: none of them can break it", [
    ("torsion, running (29 mN m)", tau_run, "MPa", "strength between layers >= %.0f MPa in shear (PET-CF, with the %.1f knock-down)" % (TAU_Z(PETCF_Z) * KD_SMALL_LAYER, KD_SMALL_LAYER)),
    ("torsion, motor stall through 2:1 (0.44 N m)", tau_stall, "MPa", "safety factor %.0f" % (TAU_Z(PETCF_Z) * KD_SMALL_LAYER / tau_stall)),
    ("bending from the belt (8 N at 5 mm)", sig_belt, "MPa", "safety factor %.0f" % (PETCF_Z * KD_SMALL_LAYER / sig_belt)),
])
# insert displacement vs relief volume
V_disp = math.pi / 4 * (D_INS_OD ** 2 - D_HOLE_PRINT ** 2) * L_INS
V_relief = math.pi / 4 * D_HOLE_PRINT ** 2 * (DEPTH_INS - L_INS)
# screw jacking: M3 x 10 through the 6 mm core floor reaches exactly the insert's length; the 1 mm relief is full of displaced melt
K_NUT = 0.2
for_T = lambda T: T / (K_NUT * 0.003)
F_snug, F_firm, F_hard = for_T(0.1), for_T(0.3), for_T(0.5)
sig = lambda F, n: n * F / A_net
KT = 2.5
show("A3 assembly loads: the inserts and their screws", [
    ("plastic displaced by one insert (d4.2 knurl in a d3.75 printed hole, 4 mm)", V_disp, "mm3", ""),
    ("relief volume under the insert (1 mm of d3.75 hole)", V_relief, "mm3", "= %.0f %% full: no real clearance under the screw tip" % (100 * V_disp / V_relief)),
    ("M3 x 10 reach below the pocket ceiling (10 - 6 mm core floor)", 4.0, "mm", "= insert length exactly: 0 mm margin once the relief is full"),
    ("M3 axial force at 0.1 / 0.3 / 0.5 N m (K 0.2)", "%.0f / %.0f / %.0f" % (F_snug, F_firm, F_hard), "N", "a hex key reaches 0.5 N m easily"),
    ("tension across the layers if ONE screw bottoms at 0.3 N m", sig(F_firm, 1) * (A_net / (A_net / 4)), "MPa", "on its quarter of the section (%.0f mm2)" % (A_net / 4)),
    ("... times Kt %.1f at the hole-bottom / step corner" % KT, sig(F_firm, 1) * 4 * KT, "MPa", "vs %.0f MPa (PET-CF between layers, x %.1f) -> cracks" % (PETCF_Z * KD_SMALL_LAYER, KD_SMALL_LAYER)),
    ("all four bottoming at 0.3 N m: mean tension", sig(F_firm, 4), "MPa", "x Kt = %.0f MPa" % (sig(F_firm, 4) * KT)),
    ("all four at 0.5 N m: mean tension", sig(F_hard, 4), "MPa", "x Kt = %.0f MPa > %.1f datasheet strength" % (sig(F_hard, 4) * KT, PETCF_Z)),
    ("strain to break between layers (PET-CF)", 100 * PETCF_Z_EPS, "%", "no yielding: a crack at one hole runs round the plane"),
    ("hoop strain locked in round an insert on cooling (d alpha 2.1e-5 x 200 K)", 100 * 2.1e-5 * 200, "%", "in a %.1f mm wall heated through" % wall_out),
])
# blind belt: can the 122 mm belt pass the spool's d28 bottom flange with the hanger slid in 2 mm?
C0, P = 30.33, 2.0
D1, D2 = 20 * P / math.pi, 40 * P / math.pi
L = lambda C, da, db: 2 * C + math.pi * (da + db) / 2 + (db - da) ** 2 / (4 * C)
D_fl = 2 * (14.0 + 0.38)                 # belt pitch line riding on the r 14 flange
show("A4 fitting the belt (rev m.2): blind, with no slack", [
    ("belt pitch length at C 30.33 on 20T / 40T", L(C0, D1, D2), "mm", "the 122 mm belt"),
    ("loop needed to pass the spool's d28 flange, hanger slid in 2 mm", L(C0 - 2, D1, D_fl), "mm", "> 122: the flange has to be forced through the belt, unseen, under a 1.1 kg rotor"),
])

# ================================================================ Part B: rev n
R_PIN_C, D_PIN = 8.0, 3.0
N_PIN = 4
F_pin_run = T_RUN / (R_PIN_C * 1e-3)                  # worst case: one pin carries it all
F_pin_stall = T_STALL / (R_PIN_C * 1e-3)
ENG = 4.1                                             # mm of pin in the notch below the chamfer
p_run = F_pin_run / (D_PIN * ENG)
p_stall = F_pin_stall / (D_PIN * ENG)
# pin as a cantilever from the nut face (z -1.8) to mid-engagement (z -6)
a = 4.2
sig_pin = 32 * F_pin_stall * a / (math.pi * 2.39 ** 3)     # M3 minor d 2.39
tau_pin = F_pin_stall / (math.pi / 4 * 2.39 ** 2)
# core floor: pin bearing in the d3.4 holes over 6 mm
p_core = F_pin_stall / (3.0 * 6.0)
# notch land: in-plane shear of the land between two notches (the layers are not asked to pass anything on)
land_w = 2 * math.pi * 8.0 / 4 - 4.0
A_land = land_w * (10.0 - 6.15)
tau_land = F_pin_stall / A_land
show("B1 rev n torque path: steel pins, in-plane plastic", [
    ("force on ONE pin, running / stall (r 8)", "%.1f / %.0f" % (F_pin_run, F_pin_stall), "N", "4 pins fitted; one is assumed to carry everything"),
    ("pin on the notch wall (d3 x 4.1 mm), running / stall", "%.2f / %.1f" % (p_run, p_stall), "MPa", "PETG-CF bearing ~ 50 MPa: factor %.0f at stall" % (50 / p_stall)),
    ("pin bending at the nut face, stall (M3 root d2.39)", sig_pin, "MPa", "A2-70 screw: 450 MPa yield -> factor %.1f" % (450 / sig_pin)),
    ("pin shear, stall", tau_pin, "MPa", ""),
    ("pin on the hub core's d3.4 hole (6 mm PET-CF floor), stall", p_core, "MPa", "plus the clamp friction of the nut"),
    ("land between two notches: in-plane shear, stall", tau_land, "MPa", "within one layer (strong direction, ~%.0f MPa): factor %.0f" % (TAU_Z(PETGCF_XY), TAU_Z(PETGCF_XY) / tau_land)),
    ("layers that must pass torque to the next layer", 0, "", "teeth z -11.6..-4.6 and notches z -10.8..-3.1 overlap: the same layers"),
])
# preload paths
A_nut = 6 * (5.5 / 2) ** 2 * math.tan(math.radians(30)) - math.pi / 4 * 3.4 ** 2
show("B2 fastener preload: compression only", [
    ("nut bearing area on the plate (5.5 AF hex - d3.4 hole)", A_nut, "mm2", ""),
    ("pressure under a nut at 0.3 N m (500 N)", F_firm / A_nut, "MPa", "PET-CF creep limit ~ 40 MPa; 1.4 mm of plate + 6 mm of core in compression"),
    ("threaded blind holes / heat-set inserts in the new parts", 0, "", "nothing a screw can bottom in or jack apart"),
])
# hub neck (journal) under a knock and the belt
RJ, RB = 7.3, 3.8
I_j = math.pi / 4 * (RJ ** 4 - RB ** 4)
M_belt_n = BELT_RADIAL * (8.1 - 2.5 + 2.5)            # belt plane -8.1 to the bearing mid-plane -17.2: 9.1 mm
sig_belt_n = BELT_RADIAL * 9.1 * RJ / I_j
F_knock = 50.0
sig_knock = F_knock * 14.0 * RJ / I_j * 2.0
show("B3 hub journal (carries no torque): belt and handling", [
    ("belt overhang from the bearing mid-plane", 9.1, "mm", "single 6802; moment %.0f N mm" % (BELT_RADIAL * 9.1)),
    ("bending stress in the journal from the belt", sig_belt_n, "MPa", ""),
    ("a 50 N sideways knock on the crown (lever 14 mm, Kt 2)", sig_knock, "MPa", "vs ~%.0f MPa between layers (PETG-CF, x 0.5): factor %.0f" % (PETGCF_Z * 0.5, PETGCF_Z * 0.5 / sig_knock)),
])
# bearing
C0r, Cr = 2260.0, 4000.0      # N, 6802 class (catalogue ~ 2.26 / 4.0 kN)
n_rev = 225.0
L10_h = (Cr / max(BELT_RADIAL, 1.0)) ** 3 * 1e6 / (60 * n_rev)
show("B4 hub bearing 6802-2RS (15 x 24 x 5)", [
    ("radial load (belt)", BELT_RADIAL, "N", "static rating C0r ~ %.0f N: factor %.0f" % (C0r, C0r / BELT_RADIAL)),
    ("axial load if the rotor is pushed down with the pins on the crown", 100.0, "N", "<= 0.5 C0r = %.0f N; all in compression down to the deck" % (0.5 * C0r)),
    ("L10 life at 8 N, 225 rpm", L10_h, "h", "not a limit; the seals' grease is"),
    ("friction torque (mu 0.0015 x 8 N x 9.75 mm + seals ~ 1 mN m)", 0.0015 * BELT_RADIAL * 9.75 + 1.0, "mN m", "vs 29 mN m rotor load"),
    ("stand-in printed bush: mu 0.2 x 8 N x 7.55 mm", 0.2 * BELT_RADIAL * 7.55, "mN m", "+%.0f %% motor torque; PV %.3f MPa m/s (limit ~0.05 dry)" % (
        100 * 0.2 * BELT_RADIAL * 7.55 / 29.0, BELT_RADIAL / (15.1 * 5.0) * W * 0.00755)),
])
# pin drive with the hub axis offset e from the rotor axis
I_ROTOR = 3.887e-3
I_MOTOR_REFL = 4e-4           # ASSUMED: armature ~1e-6 kg m2 x (10 x 2)^2
rows = []
for e in (0.2, 0.5):
    amp = e / R_PIN_C                         # relative angle amplitude, rad
    share = I_MOTOR_REFL / (I_ROTOR + I_MOTOR_REFL)
    dT = I_ROTOR * share * amp * W ** 2       # torque ripple at the pins
    rows.append(("axes offset %.1f mm: relative angle +- %.1f deg, torque ripple at the pins" % (e, math.degrees(amp)), dT * 1e3, "mN m",
                 "< %.0f mN m drag: the driving pin never lifts off; rotor speed ripple +- %.2f deg" % (T_RUN * 1e3, math.degrees(amp * share))))
rows.append(("notch play: each side / outer end", 0.5, "mm", "covers 0.5 mm of offset; backlash +- %.1f deg (irrelevant: the hall sensor reads the rotor)" % math.degrees(0.5 / 8.0)))
show("B5 drop-in pin drive with the two axes not quite coaxial", rows)
# belt fit rev n
D_cone = 2 * (12.0 + 0.75 + 0.254)            # belt teeth riding on the widest part of the lead-in cone (r 12.0)
show("B6 fitting the belt (rev n): from above, in view", [
    ("loop needed to slide down the hub's lead-in cone (no top flange), hanger slid in 2 mm", L(C0 - 2, D1, D_cone), "mm", "<= 122: drops on"),
    ("centre distance at which it just slides on", next(c / 100 for c in range(3033, 2700, -1) if L(c / 100, D1, D_cone) <= 122.0), "mm", "hanger travel is 28.33 .. 32.33"),
])

# ================================================================ Part C: assembly steps
# ---------------------------------------------------------------- B7 the lead take-up (v16): the slip ring hangs and is its own counterweight
G = 9.81
M_RING = 0.010            # kg, 12.5 mm capsule with leads (ASSUMED until weighed)
M_EXTRA = 0.0048          # kg, 3 x (M3 x 10 + 2 nuts) in the flange holes, if more pull is wanted
LIFT = 45.0               # mm travel between stop B (on the neck) and knot A (under the neck)
SLACK = 5.5               # mm of lead between stop B and the plug that is slack when the rotor is seated
EI_LEAD = 7.0             # N mm2 per 30 AWG PTFE lead (7 x 0.10 mm strands sliding + PTFE tube 0.6 / 0.3, E 0.5 GPa): ESTIMATE
GJ_LEAD = 2.4             # N mm2 per lead (PTFE tube, G 0.2 GPa): ESTIMATE
MU_LEAD = 0.7e-3          # kg/m per lead
T_DRAG = 1.0              # N mm, slip-ring drag torque (catalogue class <= 0.1 N cm): ASSUMED until measured
Z_NECK0, Z_BOSS, Z_FLT, Z_END, Z_FLOOR, Z_DECK_U = -17.0, -76.0, -77.5, -93.7, -106.0, -27.5
L_ROT = Z_NECK0 - Z_BOSS                      # rotating lead length below the neck
L_PEND = Z_NECK0 - (Z_FLT - 8.0)              # neck to the ring's centre of mass
f_pend = math.sqrt(G / (L_PEND / 1000.0)) / (2 * math.pi)
Wt = M_RING * G
f_string = math.sqrt(Wt / (6 * MU_LEAD)) / (2 * L_ROT / 1000.0)
twist = T_DRAG * L_ROT / (6 * GJ_LEAD)
m_crit = 2 * math.sqrt(6 * EI_LEAD * Wt)
l_eg = (EI_LEAD / (MU_LEAD * G * 1e-3)) ** (1.0 / 3.0)      # elasto-gravity length of one lead, mm
SPIGOT = 11.0             # mm: the rotor ring's spigot reaches 11 mm into the 6820 (z -19 .. -8)
show("B7 lead take-up: the slip ring hangs under the deck on its rotor leads and is the counterweight", [
    ("why not clamp it (rev m.2 position): slack to hide when the rotor comes down", LIFT + SLACK, "mm", "the lift needed to get a hand under the rotor; there is %.1f mm between the boss and the hub's neck to put it in" % 3.8),
    ("a 30 AWG PTFE lead bends by its stiffness, not its weight, below", l_eg, "mm", "so 50 mm of slack makes a loop up to 25 mm wide; the motor pulley's flange is 22.3 mm from the axis"),
    ("hanging ring: weight on the leads (10 g ASSUMED) / with 3 x M3 x 10 + 2 nuts in the flange", "%.3f / %.3f" % (Wt, (M_RING + M_EXTRA) * G), "N", "the leads are always in tension: a lead in tension cannot loop"),
    ("travel between stop B and knot A", LIFT, "mm", "rotor lifts %.1f mm with the plug in; %.0f mm of room under the spigot for a hand" % (LIFT + SLACK, LIFT + SLACK - SPIGOT)),
    ("ring at rest: flange top / body end / above the cavity floor", "%.1f / %.1f / %.1f" % (Z_FLT, Z_END, Z_END - Z_FLOOR), "mm", "room for the stator leads to turn"),
    ("ring at full lift: flange top below the deck underside", Z_DECK_U - (Z_FLT + LIFT), "mm", "knot A stops under the neck first; flange to the hanger's edge 2.0 mm"),
    ("rotating lead length below the neck (boss, six leads, knot A)", L_ROT, "mm", "nearest stationary part 4.7 mm (clamp ring opening); keep loose wires 20 mm from the axis"),
    ("pendulum frequency of the hanging ring (%.0f mm)" % L_PEND, f_pend, "Hz", "= %.0f rpm: passed on the way up; at 188 / 225 rpm a 0.5 mm off-centre neck moves the ring %.2f / %.2f mm" % (
        f_pend * 60, 0.5 / abs(1 - (188 / 60.0 / f_pend) ** 2), 0.5 / abs(1 - (225 / 60.0 / f_pend) ** 2))),
    ("first string frequency of the six taut leads", f_string, "Hz", "far above the 3.75 Hz spin: no whirl"),
    ("wind-up of the %.0f mm of leads under %.1f N mm of drag" % (L_ROT, T_DRAG), twist / (2 * math.pi), "turn", "steady, unwinds at stop; the stator leads resist the same torque"),
    ("torque at which the taut bundle would kink (2 sqrt(EI T))", m_crit, "N mm", "factor %.1f over the drag; %.1f N mm with the extra weight" % (m_crit / T_DRAG, 2 * math.sqrt(6 * EI_LEAD * (M_RING + M_EXTRA) * G))),
])

REVM2 = [("heat-set 4 inserts into the spool's plug", "insert; 1.1 mm walls"), ("CA the lead guide into the spool (2 keys)", "glue"),
         ("slip ring + clamp ring on the deck, 3 screws", ""), ("hanger + motor under the deck, 4 + 4 screws", "from below"),
         ("20T pulley on the shaft; set its height to a spool that is on the rotor, not here", "blind"),
         ("thread 6 leads as a flat row through the 4.6 x 1.6 slot, then the spool, then the core's d7 hole", "fiddly; rotor tied to the base from here on"),
         ("spool into the core pocket, 4 x M3 x 10 from the core top", "sled out; rotor held over the base on 225 mm leads"),
         ("loop the belt round the motor pulley and the spool while lowering the rotor", "blind; the belt has no slack"),
         ("push the rotor's spigot into the bearing", ""),
         ("base on its side, bottom plate off: pull the motor out, tighten 4 hanger screws", "blind: rotor on, belt out of sight"),
         ("leads up the channel, slack loop, land on the buck IN", "top cap off")]
REVM2_OFF = 4            # steps to redo, with tools, each time the rotor comes off (leads, belt, tension, spigot)
REVN = [("solder 2 wires to the XH header clinched in the nut plate", "bench, once"),
        ("nut plate (4 nuts) into the core pocket, 4 x M3 x 16 from the core top = the pins", "bench, once"),
        ("pigtail up the channel to the buck IN", "once"),
        ("press the 6802 into the cup, the hub into the 6802 (by hand)", "bench"),
        ("slip ring: knot A in its 6 rotor leads, then from below the deck push the leads up through the deck hole and the clamp ring", "in view from below; the ring hangs there"),
        ("thread the leads up through the cup + hub, set it on the clamp ring, 3 x M3 x 8 tightened with the jig in the bearing bore", "in view, from above; a 4.6 x 3.0 funnel-fed hole"),
        ("pull the leads up to the knot; zip tie (stop B) at the 32 mm mark, cut at 46 mm, crimp 2 XH contacts (3 + 3), click into the plug", "bench tool, once"),
        ("belt over the motor pulley, down the hub's cone; pull the motor out, tighten 4 hanger screws", "rotor off, belt in view"),
        ("plug in, lower the rotor, turn up to a quarter turn until the pins drop, push home", "every time: no tools; the leads stay taut, nothing to tuck in")]
blind_m = sum(1 for _, n in REVM2 if n.startswith("blind"))
show("C assembly steps (drive + slip-ring interface only; shell inserts, collar, bearing and the rest are the same in both)", [
    ("rev m.2: steps / blind steps / heat-set + glue steps", "%d / %d / 2" % (len(REVM2), blind_m), "", "+ %d steps repeated with tools whenever the rotor comes off" % REVM2_OFF),
    ("rev n: steps / blind steps / heat-set + glue steps", "%d / 0 / 0" % len(REVN), "", "the last one is the only one repeated: no tools"),
    ("printed parts in the torque path: rev m.2 / rev n", "1 (spool, across its layers) / 1 (hub, within its layers)", "", ""),
    ("heat-set inserts in drive parts: rev m.2 / rev n", "4 / 0", "", ""),
])
OUT["steps_revm2"] = REVM2
OUT["steps_revn"] = REVN
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "revn_drive_calc.json"), "w", encoding="utf-8") as f:
    json.dump(OUT, f, indent=1)
print("\nwrote calc/revn_drive_calc.json")
