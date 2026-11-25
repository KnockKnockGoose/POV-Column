"""Rev o CAD numbers (2026-11-20): as-built stack, cup v2, slip-ring bracket and drive mast, why the slip ring's rotor is not driven by its leads, pogo pins and
contacts, hall field with 3 magnets, compliant rotor-ring spigot, centring jig v2, retention / load-path table, mass and balance (from the Fusion checks).
Writes revo_cad_calc.json and revo_cad_calc_output.txt next to this file. Geometry values are the ones the rev o scripts build (fusionclaude/lib/povlib.py
rev o block, scripts 193-198); the check results come from calc/revo_checks.json and revo_asbuilt_checks.json (script 194).
Units: mm, N, MPa, g, mN m. ASSUMED values are marked."""
import json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = {}
LINES = []


def p(s=""):
    LINES.append(s)
    print(s)


def hdr(s):
    p()
    p("=" * 100)
    p(s)
    p("=" * 100)


# ------------------------------------------------------------------ A. as-built stack
hdr("A. As-built drive stack (clamp ring out: cartridge, 20T and belt 3.2 mm lower) and screw lengths")
DROP = 3.2
DECK_TOP, DECK_T, HANGER_TOP = -23.5, 4.0, -27.5
crown, notch_floor, chamfer = -3.1 - DROP, -10.8 - DROP, 0.8
pins = {}
for L in (16, 18, 20):
    tip = 8.0 - L
    pins[L] = dict(tip=tip, in_notch=crown - tip, below_chamfer=crown - chamfer - tip, floor_clear=tip - notch_floor)
    p(f"  drive pin M3 x {L}: tip z {tip:5.1f}, {crown - tip:4.1f} in the notch, {crown - chamfer - tip:4.1f} below the chamfer, {tip - notch_floor:4.1f} above the floor")
p("  -> M3 x 20 as built (rule: >= 3.5 below the chamfer, >= 1.0 off the floor).")
cv2 = dict(cb_floor=-21.0)
screws = {}
for ang, L in ((300, 6), (60, 10), (180, 10)):
    tip = cv2["cb_floor"] - L
    screws[ang] = dict(L=L, tip=tip, in_insert=DECK_TOP - max(tip, DECK_TOP - DECK_T), past_deck=(DECK_TOP - DECK_T) - tip)
    p(f"  cup v2 screw at {ang:3d} deg: M3 x {L}, tip z {tip:5.1f}: {screws[ang]['in_insert']:.1f} in the deck insert"
      + ("" if ang == 300 else f", {screws[ang]['past_deck']:.1f} into the bracket arm (self-tapped)") + (f", {tip - HANGER_TOP:.1f} above the hanger" if ang == 300 else ""))
OUT["A"] = dict(drop=DROP, pins=pins, cup_v2_screws=screws, belt_plane=-8.1 - DROP, bearing=(-22.9, -17.9), crown=crown)

# ------------------------------------------------------------------ B. cup v2
hdr("B. Bearing cup v2: plain bore, stiff disc, counterbored screws")
OD_RING = (24.000, 23.991)          # 6802 outer ring, ISO normal tolerance (0 / -0.009)
BORE_DRAWN = 24.20
PRINT_HOLE = (-0.18, -0.10)          # ASSUMED: PETG-CF holes of d~24 print 0.10-0.18 small (rev n crush-rib cup and diagnosis R2 note)
printed = (BORE_DRAWN + PRINT_HOLE[0], BORE_DRAWN + PRINT_HOLE[1])
clr = (printed[0] - OD_RING[0], printed[1] - OD_RING[1])
p(f"  bore drawn d{BORE_DRAWN:.2f}; expected print {printed[0]:.2f}..{printed[1]:.2f} -> diametral clearance on the 24.000/23.991 ring {clr[0]:.3f}..{clr[1]:.3f}")
p("  target 'thumb push, no rock, then 3 dots of CA': 0.02-0.08. The coupon plate brackets it (d24.05..24.35 in 0.05 steps); cup variants for every coupon.")
stiff = (5.1 / 2.0) ** 3
p(f"  plate bending stiffness vs the rev n cup's 2 mm lobes: (5.1 / 2.0)^3 = {stiff:.1f}x; no crush ribs, so no interference for the clamp to add to")
A_head = math.pi * (2.75 ** 2 - 1.9 ** 2)
for T in (0.15, 0.30):
    F = T / (0.2 * 0.003)
    p(f"  M3 SHCS head on the d3.8 hole: {A_head:.1f} mm2; at {T:.2f} N m -> preload {F:.0f} N -> {F / A_head:.0f} MPa on PETG-CF (yield ~50): "
      + ("snug, OK" if F / A_head < 25 else "too much: creep"))
p(f"  friction holding the cup at 0.15 N m: 3 x {0.15 / 0.0006:.0f} N x 0.3 = {3 * 250 * 0.3:.0f} N vs the belt's 8-18 N (plus 3 epoxy dots)")
p("  0.4 mm pads (diagnosis R2) left out: the as-built hub fixes the bearing 0.6 above the deck, so pads would leave a 0.2 mm seat ledge, and a 0.4 mm relief on")
p("  a bed face is an unprintable ceiling (bridge strands 0.4 mm off the bed land on it). The stiff disc + clearance bore remove the reason for them.")
OUT["B"] = dict(bore_drawn=BORE_DRAWN, printed=printed, clearance=clr, stiffness_ratio=stiff, head_area=A_head, snug_Nm=0.15)

# ------------------------------------------------------------------ C. why the slip ring's rotor is driven by a mast, not by its leads
hdr("C. Driving the slip ring's rotor: a wire pair vs a printed mast")
DRAG = {"assumed rev m.2/n": 1.0, "Moflon catalog (0.005 N m)": 5.0, "A2V CTC012-06S catalog (0.05 N m)": 50.0}
EA = 0.205 * 60e3      # N, 24 AWG stranded copper, E_eff ~60 GPa ASSUMED (lay)
r_pair = 0.8           # mm, half the centre distance of two 1.6 mm OD wires
p("  Two wires twisted between fixed ends: each becomes a helix; torque ~ EA r alpha^3 (alpha = helix angle), strain = alpha^2 / 2.")
wire = {}
for k, T in DRAG.items():
    a = (T / (EA * r_pair)) ** (1 / 3)
    eps = a * a / 2
    theta = a * 6.0 / r_pair
    wire[k] = dict(T=T, alpha=a, strain=eps, twist_deg_6mm=math.degrees(theta))
    p(f"  {k:<36} {T:5.1f} mN m: alpha {math.degrees(a):4.1f} deg, copper strain {100 * eps:4.2f} % (yield ~0.1 %), twist over 6 mm {math.degrees(theta):5.0f} deg")
EI = 2e-6 * 1e6        # N mm2 for the pair (2 x 1e-6 N m2 per wire, ASSUMED as the diagnosis)
for L in (6.0, 12.0, 15.0):
    p(f"  Greenhill buckling of a free {L:4.1f} mm pair: M_cr = 2 pi EI / L = {2 * math.pi * EI / L:.1f} mN m")
p("  -> above ~1 mN m the leads yield or buckle; the catalog drag is 5-50 mN m. A mast keyed in the hub's neck carries the torque; the leads ride inside it.")
p("  Offset: wires bent by an axis offset e over L see rotating bending each turn: strand strain ~ 0.04 mm / (L^2 / 6e).")
for e, L in ((0.3, 10.0), (0.6, 10.0)):
    R = L * L / (6 * e)
    p(f"     e {e:.1f} mm over {L:.0f} mm: bend radius {R:5.1f} mm -> strand strain {100 * 0.04 / R:.2f} % per turn (copper endurance ~0.06-0.09 %)")
p("  -> the stator floats +-0.4 on its pins so the boss stays on the hub's axis and the leads stay straight.")
OUT["C"] = dict(drag_cases=DRAG, wire=wire)

# ------------------------------------------------------------------ D. mast strength
hdr("D. Mast: torque path, side load from the anti-rotation pin, socket")
kL, kW, chL, chW = 4.4, 2.7, 2.6, 1.0
t_min = min((kL - chL) / 2, (kW - chW) / 2)
Am = math.pi * ((kW + chW) / 4) ** 2 + ((kL + chL) / 2 - (kW + chW) / 2) * ((kW + chW) / 2)
Z_weak = (kL * kW ** 3 / 12 - chL * chW ** 3 / 12) / (kW / 2)   # rectangle approximation of the hollow obround, weak axis
neck_h = 1.2
mast = {}
for k, T in DRAG.items():
    tau = T / (2 * Am * t_min)
    F_key = T / (2 * 1.6)
    s_bear = F_key / (neck_h * 0.5)
    F_side = T / 9.0
    sig = F_side * 6.5 / Z_weak
    mast[k] = dict(tau=tau, bearing=s_bear, side_N=F_side, bending=sig)
    p(f"  {k:<36} {T:5.1f} mN m: key torsion {tau:4.1f} MPa, key/neck bearing {s_bear:5.1f} MPa (1.2 mm neck), anti-rotation side load {F_side:4.2f} N -> "
      f"bending at the neck {sig:4.1f} MPa (PETG-CF across layers ~20-30)")
sock = math.pi * 5.0 * 1.0 * 5.0 * 2.5
p(f"  socket CA'd on the d5 x 1.0 boss: {math.pi * 5.0:.1f} mm2 x ~5 MPa (CA on a plastic boss, ASSUMED) -> ~{sock:.0f} N mm = {sock / 1000:.2f} N m >> 0.05")
p("  -> fine at 5 mN m; at the worst catalog 50 mN m the 1.2 mm neck is the weak point (26 MPa bearing): measure the drag first (bench step 0).")
OUT["D"] = dict(key=(kL, kW), channel=(chL, chW), t_min=t_min, Am=Am, Z_weak=Z_weak, cases=mast, socket_Nmm=sock)

# ------------------------------------------------------------------ E. pogo pins and contacts
hdr("E. Pogo pins (Mill-Max 0908-X-15-20-75-14-11-0) and the hub-crown contacts")
A = {0: 6.48, 1: 6.99, 2: 7.49, 3: 8.00, 4: 8.51, 5: 8.89, 6: 9.40, 7: 9.91, 8: 10.41, 9: 10.92}
seat = 2.0
c_nom = 0.80
stroke = 1.40
pin_tol, stack_tol = 0.13, 0.30
for name, X, face in (("+ pin 0908-9 on the slug", 9, -8.12), ("- pins 0908-6 on the washer", 6, -6.60)):
    free = seat - A[X]
    c = face - free
    p(f"  {name:<30} A {A[X]:5.2f}: free tip z {free:6.2f}, face z {face:6.2f} -> compression {c:.2f} of {stroke:.2f}; "
      f"with +-{pin_tol} pin length and +-{stack_tol} stack: {c - pin_tol - stack_tol:.2f}..{c + pin_tol + stack_tol:.2f}")
f = lambda c: (25.0 + (60.0 - 25.0) / 0.70 * c) * 9.81e-3
p(f"  spring: 25 g preload, 60 g at 0.70 -> {f(0.8):.2f} N per pin at 0.80; 3 pins {3 * f(0.8):.2f} N up on the rotor (8.7 N weight) and down on the hub")
p("  current: rotor max 1.4 A (rev m power report); + pin 1.4 / 2.0 A continuous (3 A peak); - pins 0.7 A each; contact 20 mohm max + ~10 mohm brass")
p(f"  drop at 1.4 A: + {1.4 * 0.03 * 1000:.0f} mV, - {0.7 * 0.03 * 1000:.0f} mV; slip ring 2 + 2 rings at 2 A each; 30 AWG leads ~20 mm: {0.34 * 0.02 / 2 * 1000:.1f} mohm per pole")
landing = []
wid, wod, slug_r, rt, r_minus = 4.3, 9.0, 1.7, 0.25, 3.25
for e in (0.0, 0.5, 0.85, 1.0):
    worst_plus = slug_r - (e + rt)
    rs = [math.hypot(r_minus * math.cos(math.radians(th)) + e * math.cos(math.radians(a)), r_minus * math.sin(math.radians(th)) + e * math.sin(math.radians(a)))
          for a in range(0, 360, 15) for th in (90, 270)]
    n_on = min(sum(1 for th in (90, 270) if (r := math.hypot(r_minus * math.cos(math.radians(th)) + e * math.cos(math.radians(a)),
                                                             r_minus * math.sin(math.radians(th)) + e * math.sin(math.radians(a)))) - rt >= wid / 2 and r + rt <= wod / 2)
               for a in range(0, 360, 15))
    landing.append(dict(offset=e, plus_margin=worst_plus, minus_on_worst=n_on))
    p(f"  offset {e:4.2f}: + pin margin on the slug {worst_plus:5.2f} mm; - pins on the washer in the worst direction: {n_on} of 2")
p("  short check (Fusion, 1.0 offset, 8 directions): + pin to the - washer >= 0.61; - pins to the + slug >= 1.55 (calc/revo_checks.json)")
OUT["E"] = dict(A=A, seat=seat, c_nom=c_nom, stroke=stroke, force_N=f(0.8), landing=landing)

# ------------------------------------------------------------------ F. hall
hdr("F. Hall sensor: 3 magnets instead of a riser cap")
BR = 1.2


def b_axial(z, n, rad=3.0, h=3.0):
    L = n * h
    return BR / 2 * ((z + L) / math.sqrt(rad ** 2 + (z + L) ** 2) - z / math.sqrt(rad ** 2 + z ** 2)) * 1e4


p("  gap mm:   " + "".join("%7d" % z for z in range(2, 11)))
for n in (2, 3):
    p(f"  {n} magnets " + "".join("%7.0f" % b_axial(z, n) for z in range(2, 11)) + "  G")
p(f"  as built (field inference): 2 magnets ~7.5 mm -> {b_axial(7.5, 2):.0f} G (1 pass in 4); 3 magnets ~4.5 mm -> {b_axial(4.5, 3):.0f} G (every pass);")
p(f"  a +2.5 riser cap with 2 magnets would give 5.0 mm -> {b_axial(5.0, 2):.0f} G. 3 magnets is the stronger field with no print; the model keeps 3")
p("  (the 3rd stands 3 mm proud: drawn 2.0 to the sensor, nothing else turning within 3 mm). A3144 operate point 70-350 G.")
OUT["F"] = dict(G={n: {z: b_axial(z, n) for z in range(2, 11)} for n in (2, 3)}, decision="keep 3 magnets, no riser cap")

# ------------------------------------------------------------------ G. compliant spigot
hdr("G. Rotor ring: compliant spigot (8 bow-spring skins)")
E = 4000.0              # MPa, PET-CF in the print plane, ASSUMED
t, r_mid, half = 0.6, 49.5, 18.0
Ls = 2 * math.radians(half) * r_mid
ks = {}
for h in (7.0, 10.0):
    I = h * t ** 3 / 12
    ks[h] = 192 * E * I / Ls ** 3
p(f"  skin {t} thick, arc {Ls:.1f} mm, fixed-fixed beam with a centre load: k = {ks[7.0]:.1f} N/mm (7 mm effective height) .. {ks[10.0]:.1f} (10 mm);")
k_lo, k_hi = ks[7.0], 2 * ks[10.0]
p(f"  with the top edge held as well, ~{k_lo:.0f}-{k_hi:.0f} N/mm per rib")
BORE = 99.97
rows = []
for tip in (99.90, 100.00, 100.10, 100.20, 100.30, 100.40):
    d = max(0.0, (tip - BORE) / 2)
    rows.append((tip, d, k_lo * d, k_hi * d))
    p(f"  printed tips d{tip:.2f}: radial preload {d:.3f} -> {k_lo * d:4.2f}..{k_hi * d:4.2f} N per rib; push-on ~{8 * 0.3 * k_hi * d:4.1f} N")
p(f"  0.4 mm oval = +-0.10 radial -> +-{k_lo * 0.1:.1f}..{k_hi * 0.1:.1f} N between the long and short axes; the 6820's clearance goes at 4-12 N across the ring")
P = k_hi * 0.25
M = P * Ls / 8
sig = 6 * M / (7.0 * t ** 2)
p(f"  skin stress at 0.25 radial and the stiff end of the range: {P:.1f} N -> {sig:.0f} MPa in the print plane (PET-CF ~70-80): OK")
p("  drawn tips d100.60 (the 100.80 rigid ring pinched; rigid ribs this size printed ~0.4-0.7 small): expected print ~100.0-100.3 -> 0.5-2.6 N per rib")
OUT["G"] = dict(k_range=(k_lo, k_hi), arc=Ls, rows=rows, skin_stress=sig, tips_drawn=100.60)

# ------------------------------------------------------------------ H. centring jig v2
hdr("H. Centring jig: the rev n jig no longer reaches the as-built hub's teeth")
teeth_top, cone_top_r, cone_bot_r, jig_hole_r, tip_r = -11.6 + 7.0 - DROP, 11.7, 12.0, 25.4 / 2, 24.96 / 2
p(f"  rev n jig: its d25.4 bore spans z -6.6..-4.6; as built the teeth end at z {teeth_top:.1f} and the crown (lead-in cone r 11.7-12.0) at -6.3")
p(f"  -> it sits on the lead-in cone only: radial play {jig_hole_r - cone_top_r:.2f}..{jig_hole_r - cone_bot_r:.2f} mm (the hub can be ~1 mm off-centre)")
p(f"  v2: a collar r 12.7..14.6 down to z -10.0 puts the bore on the tooth tips (r {tip_r:.2f}) over z -10.0..{teeth_top:.1f}: play {jig_hole_r - tip_r:.2f} drawn")
OUT["H"] = dict(revn_play=(jig_hole_r - cone_top_r, jig_hole_r - cone_bot_r), v2_play=jig_hole_r - tip_r)

# ------------------------------------------------------------------ I. checks, mass, balance (from Fusion)
hdr("I. Checks, mass and balance (Fusion, script 194)")
chk = {}
for k, fn in (("as built", "revo_asbuilt_checks.json"), ("rev o", "revo_checks.json")):
    path = os.path.join(HERE, fn)
    if os.path.exists(path):
        j = json.load(open(path, encoding="utf-8"))
        r = j["rotor"]
        chk[k] = dict(rows=j["n_rows"], fail=j["n_fail"], m=r["mass_g"], U=r["U_gmm"], G63=r["U_G63_gmm"], rock=r["rocking_Hz"], hub=j["hub_group"])
        p(f"  {k:<9}: {j['n_rows']} rows, {j['n_fail']} FAIL; rotor {r['mass_g']} g, U {r['U_gmm']} g mm ({100 * r['U_gmm'] / r['U_G63_gmm']:.0f} % of G6.3 at 225 rpm), "
          f"rocking {r['rocking_Hz']} Hz; hub group {j['hub_group']['mass_g']} g on the 6802")
OUT["I"] = chk

# ------------------------------------------------------------------ J. retention / load path
hdr("J. Retention and load path (what holds what, against which load)")
RET = [
    ("6802 outer ring in cup v2", "clearance bore + 3 CA dots in the grooves; seat ledge", "belt 8-18 N radial, pins' push", "CA dots >> 20 N"),
    ("cup v2 on the deck", "3 x M3 (snug 0.15 N m) + 3 epoxy dots", "belt pull 8-18 N", "friction 225 N"),
    ("hub in the 6802", "CA'd as built", "belt + pin push 8-30 N", "as built"),
    ("rotor drive", "4 x M3 x 20 pins in the notches (4.9 engaged)", "rotor drag 30-130 mN m -> 4-16 N per pin", "steel pins, 0.5 play"),
    ("slip-ring stator", "flange on the bracket ledge, 3 pins (+-0.4 float)", "drag 5-50 mN m -> 0.6-5.6 N on one pin", "pin shear 1.2 MPa max"),
    ("bracket under the deck", "2 x M3 x 10 through the deck inserts, 3.5 mm self-tapped", "0.1 N + pin reaction", "~400 N pull-out"),
    ("slip-ring rotor", "mast socket CA'd on the d5 boss", "drag 5-50 mN m", "~0.2 N m"),
    ("mast drive", "obround key in the hub's 4.6 x 3.0 neck", "drag 5-50 mN m", "2.6-26 MPa bearing on 1.2 mm"),
    ("contact head in the hub", "45 deg cone seat + d11 slip fit, CA", "pogo 1.9 N down; lift-off friction ~0.2 N", "CA >> 10 N"),
    ("brass washer / slug", "recess / well + CA; leads soldered before pressing in", "pogo 0.6-0.8 N each", "seated on plastic"),
    ("pogo pins in the nut plate", "barrel in d1.70, collar on its step, CA; core ceiling 0 mm above", "0.6-0.9 N push-up", "CA + step"),
    ("rotor on the 6820", "own weight (8.7 N) on the inner ring; compliant spigot centres it", "pogo 1.9 N up", "net 6.8 N down"),
]
for row in RET:
    p("  %-28s | %-58s | %-38s | %s" % row)
OUT["J"] = RET

# ------------------------------------------------------------------ K. shopping list (prices: see the report; live stock could not be read: bot protection)
hdr("K. To buy / from the kits")
BUY = [("Mill-Max 0908-6-15-20-75-14-11-0 pogo pin (A 9.40)", 4, "2 + 2 spares", "Digi-Key 1991679"),
       ("Mill-Max 0908-9-15-20-75-14-11-0 pogo pin (A 10.92)", 2, "1 + 1 spare", "Digi-Key 1991682"),
       ("M4 brass flat washer DIN 125-A, 4.3 x 9 x 0.8", 1, "pack (one used)", "Amazon / McMaster brass washers"),
       ("M2 brass heat-set insert (INCLY kit)", 1, "have", "kit"), ("M3 x 10 SHCS", 2, "have (kit)", "kit"), ("M3 x 6 SHCS", 1, "have / bench plan", "kit"),
       ("26 AWG silicone wire red + black, ~120 mm", 1, "have", "kit"), ("6802-2RS (new, for a fresh hub if ever needed)", 0, "have (10-pack)", "")]
for b in BUY:
    p("  %-52s x%d  %-18s %s" % b)
OUT["K"] = BUY

with open(os.path.join(HERE, "revo_cad_calc.json"), "w", encoding="utf-8") as fh:
    json.dump(OUT, fh, indent=1, default=str)
with open(os.path.join(HERE, "revo_cad_calc_output.txt"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(LINES) + "\n")
print("\nwrote revo_cad_calc.json, revo_cad_calc_output.txt")
