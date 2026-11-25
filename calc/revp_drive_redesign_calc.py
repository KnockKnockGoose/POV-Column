"""Rev p drive review (2026-11-22): the numbers behind docs/2026-11-22-drive-redesign.md.

Run:  py -X utf8 calc/revp_drive_redesign_calc.py
Out:  calc/revp_drive_redesign_calc.json, calc/revp_drive_redesign_calc_output.txt

Bench data: docs/measurements.md (11-19 .. 11-22) and the Main session's relays of 11-22 (shields out = no change;
grease flushed with IPA + light oil = ring + plate at 165 mA). SKF constants: SKF "The SKF model for calculating the
frictional moment" (tables 1a, 2a, 3, 4), read from the PDF on 2026-11-22. ASSUMED marks an estimate.
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = {}
LINES = []
G = 9.81


def p(s=""):
    print(s)
    LINES.append(s)


def hdr(s):
    p()
    p("== " + s)


def w(rpm):
    return rpm * 2 * math.pi / 60


# ------------------------------------------------------------------ A. inputs
hdr("A. Inputs")
ROTOR_KG = 0.8836          # rev o model rotor, no battery (docs/2026-11-20-rev-o-cad.md section 6)
BATT_KG = 0.199            # INIU bank (#14)
RINGPLATE_KG = 0.20        # rotor ring 96 g + bottom-cap plate 51 g + hub core, nut plate, rods ~50 g (ASSUMED)
I_ROTOR = 3.9e-3           # kg m2, full rotor without the bank (rev m report); with the bank ~4.0e-3 (rev k)
I_RINGPLATE = 7e-4         # kg m2 (ring 0.5 m (r1^2 + r2^2) + plate disc), ASSUMED
BENCH = [  # (date, setup, total A at 12 V, rotor rpm or None)
    ("11-20", "motor alone, belt off (PWM board, full)", 0.122, None),
    ("11-20/21", "base + belt + hub, no rotor", 0.124, None),
    ("11-21", "base + belt + hub after centring", 0.180, None),
    ("11-19", "bare rotor, old ring, fresh-grease 6820", 0.327, None),
    ("11-19", "+ board + battery, old ring", 0.660, 117.0),
    ("11-21", "rotor + board + battery, rev o", 0.600, 142.0),
    ("11-22", "belt as tight as possible (no skips)", 0.650, None),
    ("11-22", "AFTER flush + oil: ring + plate, no tube, no battery", 0.165, None),
]
for b in BENCH:
    p(f"  {b[0]:<8} {b[1]:<55} {b[2]*1000:5.0f} mA   rotor rpm {b[3] if b[3] else '-'}")
OUT["bench"] = BENCH

# ------------------------------------------------------------------ B. motor
hdr("B. JGB37-520 motor model (12 V; straight line through two measured points)")
V = 12.0
I0 = 0.122                 # A, motor alone (11-20)
N0 = 540.0                 # rpm, motor alone (11-20, slow-mo 240 fps)
N1, I1 = 2 * 117.0, 0.660  # 11-19: 117 rpm rotor through the 2:1 belt at 0.66 A, 12 V direct
k = None
# n = (V - I R) / k  with two points -> R, k
R = (V * (N0 - N1)) / (N0 * I1 - N1 * I0)
k = (V - I0 * R) / N0      # V per motor rpm
KE = k * 60 / (2 * math.pi)  # V s / rad at the gearbox output
I_STALL = V / R
p(f"  R = {R:.1f} ohm, k = {k*1000:.2f} mV/rpm (Ke {KE:.3f} V s/rad at the output), stall current {I_STALL:.2f} A")
n_rev_j = (5.07 - I0 * R) / k
p(f"  check, 11-14 rev j direct drive at 5.07 V: the line gives {n_rev_j:.0f} rpm at no-load current (measured 188): the rev j load was ~0")
n_1121 = (V - 0.600 * R) / k
p(f"  check, 11-21: 0.600 A -> motor {n_1121:.0f} rpm -> rotor {n_1121/2:.0f} rpm (measured 130-155 by video)")
ETA_G = (0.65, 0.75, 0.85)  # gearbox efficiency range, ASSUMED
ETA_B = 0.95                # belt
kt_out = [KE * e for e in ETA_G]                 # N m per A above I0, at the gearbox output
kt_rot = [2 * ETA_B * x for x in kt_out]         # at the rotor through the 2:1 belt
p(f"  torque per amp above I0: output {kt_out[0]:.3f}-{kt_out[2]:.3f} N m/A; at the rotor (2:1, 95 %) {kt_rot[0]:.3f}-{kt_rot[2]:.3f} N m/A")
T_STALL_OUT = [x * (I_STALL - I0) for x in kt_out]
p(f"  stall torque at 12 V: output {T_STALL_OUT[0]:.3f}-{T_STALL_OUT[2]:.3f} N m; at the rotor {2*ETA_B*T_STALL_OUT[0]:.2f}-{2*ETA_B*T_STALL_OUT[2]:.2f} N m")


def motor_out(n_motor, eta=0.75):
    """output torque (N m) and power (W) at motor speed n (rpm) at 12 V"""
    i = (V - k * n_motor) / R
    t = KE * eta * max(0.0, i - I0)
    return t, t * w(n_motor), i


pmax = max((motor_out(n)[1], n) for n in range(0, 541, 2))
p(f"  maximum mechanical output at 12 V (eta 0.75): {pmax[0]:.2f} W at {pmax[1]} motor rpm = {pmax[1]/2:.0f} rotor rpm")
OUT["motor"] = dict(R=R, k_V_per_rpm=k, Ke=KE, I_stall=I_STALL, kt_rotor=kt_rot, T_stall_out=T_STALL_OUT, Pmax_W=pmax[0], Pmax_rpm=pmax[1])

# ------------------------------------------------------------------ C. torque budget before / after
hdr("C. Torque at the rotor, from the current above the base (kt 0.24-0.31 N m/A)")
BASE = (0.124, 0.180)
rows = [("bare rotor, fresh grease (11-19)", 0.327), ("rotor + board + battery (11-21)", 0.600),
        ("belt as tight as possible (11-22)", 0.650), ("AFTER: ring + plate, oiled (11-22)", 0.165)]
OUT["torque_budget"] = []
for name, i in rows:
    lo = max(0.0, i - BASE[1]) * kt_rot[0]
    hi = max(0.0, i - BASE[0]) * kt_rot[2]
    p(f"  {name:<40} {i*1000:4.0f} mA -> {1000*lo:5.0f} .. {1000*hi:5.0f} mN m at the rotor")
    OUT["torque_budget"].append(dict(case=name, I=i, lo_mNm=1000 * lo, hi_mNm=1000 * hi))
P_before = 0.125 * w(142)
p(f"  Before: ~0.125 N m at ~142 rpm = {P_before:.2f} W at the rotor = {P_before/ETA_B:.2f} W out of the motor:"
  f" its whole {pmax[0]:.1f} W maximum. No gear ratio fixes a power shortfall.")
OUT["P_before_W"] = P_before

# ------------------------------------------------------------------ D. SKF model: 6820 and alternatives
hdr("D. SKF frictional moment (M = phi_ish phi_rs G_rr (nu n)^0.6 + G_sl mu_sl + M_seal), N mm = mN m")
SKF = {  # series: (R1, R2, S1, S2)
    "618": (4.7e-7, 1.7, 6.50e-3, 0.78), "60": (4.1e-7, 1.7, 3.73e-3, 14.6), "62": (3.9e-7, 1.7, 3.23e-3, 36.5)}
BRG = {  # name: (series, d, D, C0 N, d1/d2 seal counterface mm)
    "6820": ("618", 100.0, 125.0, 23000.0, 106.6), "6802": ("618", 15.0, 24.0, 1270.0, 17.9),
    "6002": ("60", 15.0, 32.0, 2850.0, 20.5), "608": ("62", 8.0, 22.0, 1370.0, 12.1)}
KZ, KRS_OIL, KRS_GREASE = 3.1, 6e-8, 6e-8


def skf(name, Fa, Fr, nu, n, seal=None, mu_ehl=0.05):
    ser, d, D, C0, ds = BRG[name]
    R1, R2, S1, S2 = SKF[ser]
    dm = 0.5 * (d + D)
    aF = math.radians(24.6 * (max(Fa, 1e-3) / C0) ** 0.24)
    Grr = R1 * dm ** 1.96 * (Fr + R2 / math.sin(aF) * Fa) ** 0.54
    Gsl = S1 * dm ** -0.145 * (Fr ** 5 + S2 * dm ** 1.5 / math.sin(aF) * Fa ** 4) ** (1 / 3)
    ish = 1 / (1 + 1.84e-9 * (n * dm) ** 1.28 * nu ** 0.64)
    rs = math.exp(-KRS_OIL * nu * n * (d + D) * math.sqrt(KZ / (2 * (D - d))))
    phibl = math.exp(-2.6e-8 * (n * nu) ** 1.4 * dm)
    musl = phibl * 0.12 + (1 - phibl) * mu_ehl
    Mrr = ish * rs * Grr * (nu * n) ** 0.6
    Msl = Gsl * musl
    Mseal = 0.0
    if seal == "RS1":     # table 3: DGBB RS1, D <= 62: 0.023 ds^2.25 + 2; D > 100: 0.018 ds^2.25 + 0
        Mseal = (0.023 * ds ** 2.25 + 2) if D <= 62 else (0.018 * ds ** 2.25 if D > 100 else 0.018 * ds ** 2.25 + 15)
    return dict(Mrr=Mrr, Msl=Msl, Mseal=Mseal, M=Mrr + Msl + Mseal, aF_deg=math.degrees(aF))


FA_FULL, FA_BATT, FA_RP = ROTOR_KG * G, (ROTOR_KG + BATT_KG) * G, RINGPLATE_KG * G
p(f"  Axial load on the 6820: ring + plate {FA_RP:.1f} N, full rotor {FA_FULL:.1f} N, + battery {FA_BATT:.1f} N; Fr 1 N")
p("  6820 rolling + sliding (no seal), mN m:      150 rpm   188 rpm   225 rpm   250 rpm")
OUT["skf_6820"] = {}
for label, Fa, nu in [("run-in grease, nu 150 (full rotor)", FA_FULL, 150), ("run-in grease, nu 250 (full rotor)", FA_FULL, 250),
                      ("light oil nu 15 (full rotor)", FA_FULL, 15), ("light oil nu 30 (full rotor)", FA_FULL, 30),
                      ("light oil nu 30 (+ battery)", FA_BATT, 30), ("light oil nu 30 (ring + plate)", FA_RP, 30)]:
    vals = [skf("6820", Fa, 1.0, nu, n)["M"] for n in (150, 188, 225, 250)]
    OUT["skf_6820"][label] = vals
    p(f"    {label:<40} " + "  ".join("%7.1f" % v for v in vals))
seal6820 = skf("6820", FA_FULL, 1.0, 150, 188, seal="RS1")["Mseal"]
seal6802 = skf("6802", 8.0, 15.0, 150, 188, seal="RS1")["Mseal"]
p(f"  If the 6820 had contact seals (SKF RS1 row, D > 100: 0.018 x {BRG['6820'][4]}^2.25): M_seal = {seal6820:.0f} mN m."
  " Yours is ZZ: shields don't touch, and removing them changed nothing (11-22).")
p(f"  The hub's 6802-2RS (RS1 row, D <= 62: 0.023 x 17.9^2.25 + 2): M_seal = {seal6802:.1f} mN m -- now the largest single drag in the drive")
OUT["seal_6820_RS1_mNm"], OUT["seal_6802_mNm"] = seal6820, seal6802
fresh_meas = (0.10, 0.13)
model_run_in = skf("6820", FA_BATT, 1.0, 150, 142)["M"]
p(f"  Fresh factory fill, measured by difference: {1000*fresh_meas[0]:.0f}-{1000*fresh_meas[1]:.0f} mN m at ~142 rpm, vs the model's run-in"
  f" {model_run_in:.0f} mN m: x{1000*fresh_meas[0]/model_run_in:.1f}-{1000*fresh_meas[1]/model_run_in:.1f} for churning a full, fresh fill.")
oil_full = skf("6820", FA_FULL, 1.0, 25, 225)["M"]
p(f"  After flush + light oil (nu ~25 at room temperature): {oil_full:.1f} mN m at 225 rpm, full rotor -> {fresh_meas[0]*1000/oil_full:.0f}-{fresh_meas[1]*1000/oil_full:.0f}x less")
rp = skf("6820", FA_RP, 1.0, 25, 225)["M"]
p(f"  Check against 11-22 (ring + plate, oiled): model {rp:.1f} mN m -> {rp/1000/kt_rot[1]*1000:.0f} mA over the base; measured 165 mA vs a 124-180 mA base")
OUT["oil_full_225"] = oil_full
p("  Small bearings instead of the 6820 (two on a spindle, full rotor on one, the other preloaded 10 N), grease nu 150, 225 rpm:")
for name in ("6002", "608"):
    m1 = skf(name, FA_FULL, 1.0, 150, 225)["M"]
    m2 = skf(name, 10.0, 0.5, 150, 225)["M"]
    p(f"    2 x {name}ZZ: {m1:.1f} + {m2:.1f} = {m1+m2:.1f} mN m (oiled: {skf(name, FA_FULL, 1.0, 25, 225)['M'] + skf(name, 10.0, 0.5, 25, 225)['M']:.1f})")
    OUT[f"pair_{name}"] = m1 + m2

# ------------------------------------------------------------------ E. air drag
hdr("E. Air drag of the column")
RHO, NU_AIR = 1.2, 1.5e-5
R_T, L_T = 0.080, 0.250
for rpm in (188, 225):
    om = w(rpm)
    Re = om * R_T ** 2 / NU_AIR
    Cf = 0.0727 * Re ** -0.2          # turbulent flat-plate skin friction, rough estimate for a rotating cylinder
    T_skin = math.pi * RHO * om ** 2 * R_T ** 4 * L_T * Cf * 2
    v = om * (R_T + 0.002)
    T_form = 0.5 * RHO * v ** 2 * 1.0 * (24 * 2 * 0.25 * 0.001 + 336 * 5e-3 * 1.6e-3 * 0.5) * (R_T + 0.002)
    p(f"  {rpm} rpm: Re {Re:.0f}, skin ~{1000*T_skin:.2f} mN m, rails + LED bumps ~{1000*T_form:.2f} mN m -> ~{1000*(T_skin+T_form):.1f} mN m")
    OUT[f"air_{rpm}"] = 1000 * (T_skin + T_form)
p("  Bench evidence: rev j turned 188 rpm on 5.07 V at no-load current (section B), so the air load is a few mN m,")
p("  not the 27 mN m the rev k / m budget carried.")

# ------------------------------------------------------------------ F. after: predicted full-rotor operating point
hdr("F. Prediction for the full rotor after the flush (no battery; slip ring + pogo when fitted)")
for nu in (15, 30):
    T = skf("6820", FA_FULL, 1.0, nu, 225)["M"] + OUT["air_225"] + 1.6   # + slip ring (<1.6 measured)
    di = T / 1000 / kt_rot[1]
    i_tot = (0.124 + di, 0.180 + di)
    n_rot = [(V - i * R) / k / 2 for i in i_tot]
    p(f"  oil nu {nu}: {T:.0f} mN m at the rotor -> +{1000*di:.0f} mA -> {1000*i_tot[0]:.0f}-{1000*i_tot[1]:.0f} mA total,"
      f" rotor {n_rot[1]:.0f}-{n_rot[0]:.0f} rpm at full knob")
    OUT[f"pred_nu{nu}"] = dict(T_mNm=T, I_A=i_tot, rpm=n_rot)

# ------------------------------------------------------------------ G. belt
hdr("G. GT2 belt 20T / 40T, 122 mm, C 30.33")
r1, r2, C = 20 * 2 / (2 * math.pi), 40 * 2 / (2 * math.pi), 30.33
span = math.sqrt(C ** 2 - (r2 - r1) ** 2)
wrap1 = 180 - 2 * math.degrees(math.asin((r2 - r1) / C))
teeth1 = 20 * wrap1 / 360
p(f"  pitch radii {r1:.2f} / {r2:.2f} mm; free span {span:.1f} mm; wrap on the 20T {wrap1:.0f} deg = {teeth1:.1f} teeth in mesh")
for label, T in [("before (0.125 N m)", 0.125), ("after, hub incl. 6802 (0.040 N m)", 0.040)]:
    Te = T / (r2 / 1000)
    p(f"  {label:<36} effective tension {Te:5.1f} N -> slack side goes slack below T0 = {Te/2:.1f} N per strand")
    OUT[f"Te_{T}"] = Te
MU_BELT = 0.0075      # kg/m, GT2 6 mm, ASSUMED
for T0 in (3, 5, 8, 12, 20):
    f = 1 / (2 * span / 1000) * math.sqrt(T0 / MU_BELT)
    dl = 1.0 * span / (4 * T0)
    p(f"  T0 {T0:>2} N: pluck {f:4.0f} Hz, 1 N (~100 g) at mid-span deflects {dl:.2f} mm, hub / 6802 side load {2*T0:.0f} N")
p("  Finger tension (rev n diag step 3: ~3 mm under a light push) is T0 ~ 3-5 N: slack below Te 6-10 N. Before, Te was ~10 N:")
p("  the slack side went slack and the 20T's ~9 teeth ratcheted (the pops, 2-3 per turn, count set by the tension).")
p("  'As tight as possible' (T0 >~ 15 N) stopped the skips but put >30 N on a 5 mm-wide 6802 cantilevered 8-10 mm.")

# ------------------------------------------------------------------ H. pins
hdr("H. Drive pins (r 8 mm)")
for label, T in [("before", 0.125), ("after", 0.025)]:
    p(f"  {label}: {T/0.008:.1f} N on the driving pin")
e_list = (0.05, 0.10, 0.20)
for e in e_list:
    for rpm in (188, 225):
        Tr = I_ROTOR * w(rpm) ** 2 * e / 8.0
        p(f"  pin in a radial notch with an axis offset of {e} mm, STIFF drive (no belt), {rpm} rpm: forced torque ripple +-{1000*Tr:.0f} mN m")
p("  The belt and the light hub absorbed that ripple in rev o. A direct drive needs a constant-velocity coupling (Oldham).")

# ------------------------------------------------------------------ I. unbalance from the battery
hdr("I. Battery unbalance vs the 6820's gravity preload")
r_p = 0.05625
for U in (2000, 5000):
    for rpm in (150, 188, 225):
        F = U * 1e-6 * w(rpm) ** 2
        M = F * 0.081
        lim = (ROTOR_KG + BATT_KG) * G * r_p / 2
        p(f"  U {U} g mm at {rpm} rpm: {F:.2f} N rotating, moment {M:.3f} N m vs tipping limit W r_p / 2 = {lim:.2f} N m ({100*M/lim:.0f} %)")
p("  G6.3 at 225 rpm for this rotor: ~240 g mm. The battery off-axis by 10-25 mm is 2,000-5,000 g mm.")

# ------------------------------------------------------------------ J. coast-down reference
hdr("J. Coast-down (maintenance reference)")
for label, T, Iz in [("fresh grease, full rotor", 0.10, I_ROTOR), ("oiled, full rotor", oil_full / 1000 + 0.003, I_ROTOR),
                     ("oiled, ring + plate", rp / 1000, I_RINGPLATE)]:
    for rpm in (188,):
        t = Iz * w(rpm) / T
        rev = Iz * w(rpm) ** 2 / (2 * T) / (2 * math.pi)
        p(f"  {label:<28} from {rpm} rpm at {1000*T:.0f} mN m: stops in {t:.1f} s after {rev:.1f} turns")
p("  (oil drag falls with speed as n^0.6, so the real coast is a little longer than this constant-torque estimate)")

# ------------------------------------------------------------------ K. fallbacks
hdr("K. Fallback drives")
# K1 JGB37 direct drive at 1:1
for T in (0.025, 0.06, 0.125):
    n = N0 * (1 - T / T_STALL_OUT[1])
    p(f"  JGB37 direct (1:1) at {1000*T:.0f} mN m: {n:.0f} rpm at 12 V; droop {N0/T_STALL_OUT[1]:.0f} rpm per N m (+-5 mN m = +-{5e-3*N0/T_STALL_OUT[1]:.0f} rpm)")
# K2 NEMA 17 stepper pull-out at 12 V
STEP = {"17HS13-1504H hollow (0.25 N m, 1.5 A)": (0.25, 1.5, 1.6, 2.4e-3),
        "17HS19-2004S1 (0.59 N m, 2.0 A)": (0.59, 2.0, 1.4, 3.0e-3)}
OUT["stepper"] = {}
for name, (Th, Ir, Rph, L) in STEP.items():
    kt = Th / Ir
    row = []
    for rpm in (150, 188, 225, 250):
        om = w(rpm)
        we = 50 * om
        E = kt * om
        # largest phase current the 12 V bridge can push: |V| >= sqrt((I R + E)^2 + (I w L)^2)
        lo, hi = 0.0, Ir
        for _ in range(40):
            mid = 0.5 * (lo + hi)
            if math.hypot(mid * Rph + E, mid * we * L) <= 0.95 * V:
                lo = mid
            else:
                hi = mid
        row.append(0.7 * kt * lo)   # 0.7: sine microstepping + load angle, ASSUMED
    kth = Th * 50
    fn = math.sqrt(kth / I_ROTOR) / (2 * math.pi)
    p(f"  {name}: pull-out ~" + " / ".join("%.2f" % x for x in row) + " N m at 150 / 188 / 225 / 250 rpm;"
      f" torsional mode with the rotor {fn:.1f} Hz")
    OUT["stepper"][name] = dict(pullout=row, f_mode=fn)
# K3 friction idler on the spigot bore (r 47)
for r_m in (29.0, 31.0, 33.0):
    r_w = 47.0 - r_m
    p(f"  idler on the spigot bore: motor at r {r_m:.0f}, wheel r {r_w:.0f}: motor {225*47/r_w:.0f} rpm for 225 (the JGB37 has 540 no-load)")
# K4 pogo pins sliding on face rings
k_arch, F_pogo, H_ni = (1e-5, 1e-4), 0.6, 5e9
for rr in (0.015, 0.025):
    s_h = w(225) * rr * 3600
    vol = [kk * F_pogo * s_h / H_ni * 1e9 for kk in k_arch]
    p(f"  pogo pin sliding on a ring at r {1000*rr:.0f} mm, 225 rpm: {s_h/1000:.1f} km per hour, wear {vol[0]:.4f}-{vol[1]:.3f} mm3/h"
      f" (Archard k 1e-5..1e-4, 0.6 N); the 0.76 um gold is gone in minutes")
p("  Drag of 4 brushes at 1.5 N, mu 0.25, r 12 mm: %.0f mN m" % (1000 * 4 * 1.5 * 0.25 * 0.012))

# ------------------------------------------------------------------ L. lubrication
hdr("L. Oil in an open 6820")
for rr in (0.051, 0.059):
    a = w(225) ** 2 * rr
    p(f"  centrifugal acceleration at r {1000*rr:.0f} mm, 225 rpm: {a:.0f} m/s2 ({a/G:.1f} g): oil on the turning inner ring moves out into the races")
vol_free = math.pi / 4 * (118.4 ** 2 - 106.6 ** 2) * 13 * 0.5 / 1000   # cm3, half the annulus between the ring lands, ASSUMED
p(f"  free volume between the ring lands ~{vol_free:.0f} cm3; 4-6 drops (0.2-0.3 cm3) is ~2 % of it: a film, not a fill")

with open(os.path.join(HERE, "revp_drive_redesign_calc.json"), "w", encoding="utf-8") as f:
    json.dump(OUT, f, indent=1, default=float)
with open(os.path.join(HERE, "revp_drive_redesign_calc_output.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(LINES) + "\n")
print("\nwrote calc/revp_drive_redesign_calc.json and _output.txt")
