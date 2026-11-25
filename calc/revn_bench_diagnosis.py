"""Rev n bench diagnosis (2026-11-19): the numbers behind docs/2026-11-19-rev-n-bench-diagnosis.md.

Run:  py calc/revn_bench_diagnosis.py
Out:  calc/revn_bench_diagnosis.json, calc/revn_bench_diagnosis_output.txt, docs/img/revn_diag_speed_vs_current.png

Bench data: Brian's measurements on 2026-11-19, read from the laptop Main session's log (times ET).
Everything marked ASSUMED is an estimate until the bench plan in the report measures it.
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = {}
LINES = []


def p(s=""):
    print(s)
    LINES.append(s)


def hdr(s):
    p()
    p("== " + s)


# ------------------------------------------------------------------ A. bench data (2026-11-19, ET)
hdr("A. Bench data, 2026-11-19 (Main session on the laptop; hall rpm read over Wi-Fi from /api/status)")
BENCH = [
    # (time, setup, supply, current A, rotor rpm or None, note)
    ("11:44", "hub journal loose in the 6802", "12 V via PWM", None, None, "hub wobbles, noisy, belt skips; hub CA'd into the 6802 -> much better"),
    ("12:00", "tight ring (100.80), bare rotor", "12 V via PWM, full knob", 0.735, None, "no board on the rotor, so no rpm"),
    ("12:23", "tight ring + board + battery, 2 magnets", "12 V via PWM, full knob", None, 73, "1.2 pulses/s: hall missing ~3 of 4 passes"),
    ("12:24", "tight ring + board + battery", "12 V via PWM, full knob", 0.789, None, "Brian: 'it feels slow'"),
    ("12:29", "tight ring + board + battery, 3 magnets", "12 V via PWM, full knob", 0.789, 102, "100.9-103.1 rpm, valid flickers at the 100 rpm gate, 7 rejected, 27 resyncs"),
    ("12:33", "same, PWM bypassed", "13.5 V direct", None, 114, "111.3-116.5 rpm (+11 %), one false 2164 rpm, rejected 16->19, resyncs 54->63"),
    ("12:38", "base alone (rotor off)", "12 V direct", 0.122, None, "cup screws as fitted"),
    ("12:39", "base alone, cup screws loosened", "12 V direct", 0.110, None, ""),
    ("12:40", "base alone, cup screws looser", "12 V direct", 0.080, None, "rotor on with screws this loose: belt skips"),
    ("12:44", "base alone, cup screws snug", "12 V direct", 0.104, None, ""),
    ("13:27", "tight ring, rotor on, belt skipping", "12 V direct", 0.600, 0, "rotor stalled (no new hall pulses), belt jumping teeth"),
    ("13:34", "tight ring, belt off, by hand", "-", None, None, "even drag all round, no catch point, does not coast"),
    ("14:28", "6820 taken off", "12 V direct", None, None, "'all the load went away, it spun really fast'"),
    ("14:35", "old loose ring (99.43), bare rotor", "12 V direct", 0.327, None, "board not fitted, so no rpm"),
    ("14:54", "old loose ring + board + battery, 3 magnets", "12 V direct", 0.660, 117, "117.5-119.6 rpm valid, 0 rejected; then 114.8-117.0, 2 rejected; popping / odd sounds"),
]
for t, s, v, i, n, note in BENCH:
    p(f"  {t}  {s:<44} {v:<24} {('%.3f A' % i) if i is not None else '   -   ':>8}  {('%3d rpm' % n) if n is not None else '   -   ':>8}  {note}")
OUT["bench"] = [dict(time=t, setup=s, supply=v, current_A=i, rotor_rpm=n, note=note) for t, s, v, i, n, note in BENCH]
p("  Correction: 119 rpm was NOT measured at 327 mA. 327 mA was the bare rotor (no board, so no rpm);")
p("  117-119 rpm was measured at 660 mA with the board and battery on the rotor.")

# ------------------------------------------------------------------ B. motor: what the speed/current points say
hdr("B. Motor (JGB37-520, 12 V; belt 20T:40T, so motor rpm = 2 x rotor rpm if the belt does not slip)")
I0 = 0.10        # A, motor no-load current incl. gearbox (11-07: ~0.15 A via the PWM board; 11-19 base alone 0.08-0.12 A)
pts = [(0.660, 2 * 117.0, 12.0), (0.789, 2 * 102.0, 12.0)]   # (A, motor rpm, V); the PWM board at full knob taken as 12 V
(i1, n1, _), (i2, n2, _) = pts
b = (n1 - n2) / (i2 - i1)            # rpm per A (= R/K)
a = n1 + b * i1                      # rpm at I = 0
K = 12.0 / a                         # V per rpm (back-EMF constant)
R = b * K                            # ohm
N0_fit = a - b * I0
IS_fit = a / b
p(f"  Two loaded points at 12 V: {i1:.3f} A -> {n1:.0f} motor rpm, {i2:.3f} A -> {n2:.0f} motor rpm")
p(f"  Straight line N = {a:.0f} - {b:.0f} I  ->  K = {K*1000:.2f} mV/rpm, R = {R:.1f} ohm, no-load {N0_fit:.0f} rpm, stall {IS_fit:.2f} A")
p(f"  The listing's stall current is 1.65 A (calc/elec_calc.py): the fit's {IS_fit:.2f} A agrees; its no-load speed ({N0_fit:.0f}) does not agree with 600.")
# what the 11-14 rev j run implies (188 rpm direct at 5.07 V, rotor on the motor shaft, no 6820)
n_514_fit = (5.07 - I0 * R) / K
p(f"  Cross-check, 11-14 rev j direct drive: 188 rpm (image locked + 191 rpm FFT) at 5.07 V. The fitted motor would top out at"
  f" {n_514_fit:.0f} rpm on 5.07 V even with no load,")
p("  so either the motor changed, or tonight's speeds hide belt slip, or the line is not straight (it is two points). Measure it (bench step 1).")


def model(name, n0, istall, i0=I0):
    """speed at 12 V vs total current: N = n0 * (1 - (I - i0)/(istall - i0))"""
    return dict(name=name, n0=n0, istall=istall, i0=i0)


MODELS = [
    model("M0 design (listing: 600 rpm, 1.65 A stall)", 600.0, 1.65),
    model("M1 tonight's two points only", N0_fit, IS_fit),
    model("M2 best fit, tonight + 11-14 (520 rpm, 1.2 A stall)", 520.0, 1.20),
]


def rotor_rpm(m, i, v=12.0):
    n_motor = m["n0"] * (v / 12.0) - m["n0"] * (i - m["i0"]) / (m["istall"] - m["i0"])
    return max(0.0, n_motor / 2.0)


def current_for(m, rotor, v=12.0):
    n_motor = 2 * rotor
    return m["i0"] + (m["n0"] * (v / 12.0) - n_motor) * (m["istall"] - m["i0"]) / m["n0"]


p()
p("  Rotor rpm at 12 V for a total motor current of:   0.15    0.25    0.33    0.40    0.50    0.66    0.79 A")
for m in MODELS:
    row = "  ".join("%5.0f" % rotor_rpm(m, i) for i in (0.15, 0.25, 0.33, 0.40, 0.50, 0.66, 0.79))
    p(f"  {m['name']:<62} {row}")
p()
p("  Current budget for 188 rpm (and 225), at 12 / 15 / 16 V:")
OUT["motor_models"] = []
for m in MODELS:
    c = {v: current_for(m, 188, v) for v in (12.0, 15.0, 16.0)}
    c225 = current_for(m, 225, 12.0)

    def fmt(x):
        return " none" if x < 0.11 else "%5.2f" % x

    p(f"  {m['name']:<62} 188: {fmt(c[12.0])} / {fmt(c[15.0])} / {fmt(c[16.0])} A    225 @ 12 V: {fmt(c225)} A")
    OUT["motor_models"].append(dict(m, I_for_188_12V=c[12.0], I_for_188_15V=c[15.0], I_for_188_16V=c[16.0], I_for_225_12V=c225))
p("  (a budget below ~0.11 A is impossible: the base alone draws 0.08-0.12 A)")

# torque per amp at the rotor (through 2:1 belt, 95 %), for converting currents to drag
ETA_G, ETA_B = 0.65, 0.95       # gearbox and belt efficiency, ASSUMED


def kt_rotor(m):
    k_vs = (12.0 - m["i0"] * 12.0 / m["istall"]) / (m["n0"] * 2 * math.pi / 60)   # V s/rad at the gearbox output
    return k_vs * ETA_G * 2 * ETA_B                                               # N m per A at the rotor


p()
p("  Rotor drag implied by the extra current above the base (0.104 A), N m per A at the rotor:")
for m in MODELS:
    p(f"    {m['name']:<62} {kt_rotor(m):.3f} N m/A")
DRAG_CASES = [("old loose ring, bare rotor", 0.327), ("old loose ring + board + battery", 0.660),
              ("tight ring, bare rotor", 0.735), ("tight ring + board + battery", 0.789), ("belt-skip stall", 0.600)]
p("  case                                   extra A    drag at the rotor, mN m (M0 / M1 / M2)")
OUT["drag_cases"] = []
for name, i in DRAG_CASES:
    d = [1000 * (i - 0.104) * kt_rotor(m) for m in MODELS]
    p(f"    {name:<36} {i-0.104:6.3f}     {d[0]:5.0f} / {d[1]:5.0f} / {d[2]:5.0f}")
    OUT["drag_cases"].append(dict(case=name, current_A=i, extra_A=i - 0.104, drag_mNm=d))
p("  Design budget (rev k / m / n): 29 mN m at 225 rpm = 27 'air' + 2 bearing.")

# belt: effective pull at the skip limit
r40 = 40 * 2.0 / math.pi / 2 / 1000
p()
for m in MODELS:
    t_hub = (0.600 - 0.104) * kt_rotor(m)
    p(f"  Belt skip limit ({m['name'][:2]}): ~{1000*t_hub:.0f} mN m at the hub = {t_hub/r40:.1f} N effective pull on the 40T (r {1000*r40:.2f} mm)")
OUT["belt_skip_hub_mNm"] = [1000 * (0.600 - 0.104) * kt_rotor(m) for m in MODELS]

# ------------------------------------------------------------------ C. the 6820's own drag (SKF 2004 model, rolling term)
hdr("C. 6820ZZ running torque, properly fitted (SKF frictional-moment model, rolling term; ZZ shields add none)")
D_M = 112.5                 # mm, pitch diameter (100 x 125)
C0 = 23000.0                # N
R1, R2 = 4.7e-7, 1.7        # SKF geometry constants, 618 series deep-groove ball bearings
FA, FR = 10.0, 2.0          # N: bare rotor ~1.0 kg on the inner ring; small radial (pin force / unbalance)
alpha = math.radians(24.6 * (FA / C0) ** 0.24)
G_rr = R1 * D_M ** 1.96 * (FR + R2 / math.sin(alpha) * FA) ** 0.54
p(f"  dm {D_M} mm, Fa {FA} N, Fr {FR} N -> alpha_F {math.degrees(alpha):.1f} deg, G_rr {G_rr:.4f}")
p("  M_rr = G_rr (nu n)^0.6 [N mm]; nu = grease base-oil viscosity at room temperature (ASSUMED 100-250 mm2/s)")
p("  rpm:            100     150     188     225")
OUT["brg6820_mNm"] = {}
for nu in (100, 150, 250):
    row = [G_rr * (nu * n) ** 0.6 for n in (100, 150, 188, 225)]
    OUT["brg6820_mNm"][nu] = row
    p(f"  nu {nu:3d} mm2/s:   " + "  ".join("%5.0f" % x for x in row) + "   mN m")
p("  The design assumed 1.9 mN m (mu 0.0015 x load), which ignores this viscous rolling term. A thin-section bearing at")
p("  almost no load is all viscous drag: ~30-60 mN m here, more than the whole 29 mN m budget. It drops ~30 % after")
p("  an hour's run-in (grease channels) and ~4x if the grease is replaced by light oil (M ~ nu^0.6).")
I_BARE = 1.8e-3   # kg m2, bare rotor I_zz, ASSUMED (rev m full rotor 3.9e-3)
for w_hand in (2 * math.pi * 1.0,):
    t = 0.035
    p(f"  Hand-spin coast, bare rotor (I_zz ~{I_BARE:.1e} kg m2 ASSUMED) from 1 rev/s at 35 mN m: stops in"
      f" {I_BARE*w_hand/t:.2f} s after {I_BARE*w_hand**2/(2*t)/(2*math.pi):.2f} rev.")
p("  So 'it does not coast' is normal for this bearing. The current at 12 V is the test, not the coast.")

# ------------------------------------------------------------------ D. why a printed spigot pinches a thin-section bearing
hdr("D. The thin inner ring vs a printed spigot")
E_ST = 208e3                  # N/mm2
B_IR, T_IR = 13.0, 3.1        # mm, inner ring width and mean radial thickness (61820: d 100, d1 ~106.8)
R_IR = 51.5                   # mm, mean radius
EI = E_ST * B_IR * T_IR ** 3 / 12
dD_per_N = 0.1488 * R_IR ** 3 / EI          # Roark: two opposite point loads, change in diameter along the load line
CLR = (0.012, 0.036)                         # mm, radial internal clearance, ISO 5753 group N, d 80-100
p(f"  Inner ring EI {EI:.2e} N mm2; two opposite forces P ovalise it by {1000*dD_per_N:.1f} um per N")
p(f"  Internal clearance (group N) {CLR[0]*1000:.0f}-{CLR[1]*1000:.0f} um is used up by P = {CLR[0]/dD_per_N:.0f}-{CLR[1]/dD_per_N:.0f} N across the ring")
OUT["ring_ovalise_um_per_N"] = 1000 * dD_per_N
OUT["ring_force_to_eat_clearance_N"] = [CLR[0] / dD_per_N, CLR[1] / dD_per_N]
# plastic spigot compliance: free 2.8 mm wall ring vs rooted in the 5 mm hub + 3 mm ribbed web
E_PC = 4000.0
EI_sp = E_PC * 11.0 * 2.8 ** 3 / 12
dD_sp = 0.1488 * 48.4 ** 3 / EI_sp
EI_web = E_PC * 4.0 * 44.0 ** 3 / 12        # the ring's flat annulus r 47..91 bending in its own plane, ~4 mm thick
dD_web = 0.1488 * 69.0 ** 3 / EI_web
p(f"  Printed spigot as a free 2.8 mm ring: {1000*dD_sp:.0f} um per N (soft); the whole rotor ring in its plane: {1000*dD_web:.2f} um per N")
p(f"  The rotor ring is {dD_per_N/dD_web:.0f}x stiffer in-plane than the steel inner ring: its 0.4 mm of ovality is imposed on the bearing.")
p("  Measured ovality of the printed ring: 0.40 mm (99.24-99.64). That is 11-33x the bearing's clearance.")
p("  => any spigot that grips on all 8 ribs pinches the balls along its long axis; any that does not pinch is loose on its short axis.")
OUT["spigot_free_um_per_N"] = 1000 * dD_sp
OUT["rotor_ring_inplane_um_per_N"] = 1000 * dD_web

# ------------------------------------------------------------------ E. as-built stack (clamp ring removed)
hdr("E. As-built drive stack: clamp ring (3.2 mm incl. its 0.1 crush gap) removed, cup on the deck")
DROP = 3.2
DES = dict(crown=-3.1, notch_floor=-10.8, chamfer=0.8, belt=-8.1, brg_bot=-19.7, brg_top=-14.7, cup_bot=-20.3,
           neck=(-15.8, -17.0), journal_end=-18.3, plate_under=-2.0, deck_top=-23.5, hanger_top=-27.5,
           cup_screw_tip_M3x8=-25.8, insert=(-23.5, -27.5))
ASB = {k: (tuple(x - DROP for x in v) if isinstance(v, tuple) else v - DROP) for k, v in DES.items()
       if k not in ("chamfer", "plate_under", "deck_top", "hanger_top", "insert", "cup_screw_tip_M3x8")}
for k in ("crown", "notch_floor", "belt", "brg_bot", "brg_top", "cup_bot", "journal_end"):
    p(f"  {k:<14} design {DES[k]:6.1f}   as built {ASB[k]:6.1f}")
pins = {}
for L in (16, 18, 20):
    tip = 8.0 - L                       # head on the hub core top at z +8
    eng = ASB["crown"] - tip
    floor = tip - ASB["notch_floor"]
    pins[L] = dict(tip=tip, engagement=eng, below_chamfer=eng - DES["chamfer"], floor_clear=floor)
    p(f"  pins M3 x {L}: tip z {tip:5.1f}, in the notch {eng:4.1f} mm ({eng-DES['chamfer']:4.1f} below the chamfer), above the floor {floor:4.1f} mm")
p("  -> as built, M3 x 20 is the right pin (design check: >= 3.5 engaged, >= 1.0 above the floor); M3 x 16 barely reaches.")
screws = {}
lobe_top_asb = DES["cup_bot"] - DROP + 2.0          # 2 mm lobes on the cup's underside plane
for L in (5, 6, 8):
    tip = lobe_top_asb + 0.5 - L                     # 0.5 mm washer
    in_insert = DES["insert"][0] - max(tip, DES["insert"][1])
    above_hanger = tip - DES["hanger_top"]
    screws[L] = dict(tip=tip, thread_in_insert=in_insert, above_hanger=above_hanger)
    p(f"  cup screw M3 x {L} + washer: tip z {tip:5.1f}, {in_insert:3.1f} mm in the deck insert, {above_hanger:+4.1f} mm vs the motor hanger's top")
p("  -> the M3 x 8 over the motor hanger (flange_screw_2) now reaches 1.5 mm INTO the hanger: it bottoms before it clamps")
p("     that lobe. Use M3 x 6 (3.5 mm in the insert, 0.5 mm clear) or keep x 8 with 2 mm of washers under the head.")
OUT["as_built"] = dict(drop=DROP, z=ASB, pins=pins, cup_screws=screws)

# ------------------------------------------------------------------ F. the drive's side loads
hdr("F. Side loads on the hub: one driving pin at r 8 mm + the belt")
for t in (0.029, 0.060, 0.130):
    f_pin = t / 0.008
    t_belt = t / 2 / 0.95   # motor-side torque is irrelevant here; belt effective pull at the hub:
    pull = t / r40
    p(f"  rotor drag {1000*t:4.0f} mN m: pin force {f_pin:5.1f} N (turns with the rotor), belt effective pull {pull:5.1f} N + ~8 N static (fixed)")
p("  The 6802 is one 5 mm bearing with the load ~10 mm above its centre: the resultant swings 8-30 N once per turn")
p("  at high drag, so the hub nods in the bearing's internal play (~0.2-0.5 deg for a 6802, group N). That is the 'wobble'.")

# ------------------------------------------------------------------ G. hall: field vs gap
hdr("G. Hall sensor: field on the axis of a stack of 6 x 3 mm N35 discs (Br ~1.2 T ASSUMED)")
BR = 1.2


def b_axial(z, n_mag, rad=3.0, h=3.0):
    L = n_mag * h
    return BR / 2 * ((z + L) / math.sqrt(rad ** 2 + (z + L) ** 2) - z / math.sqrt(rad ** 2 + z ** 2)) * 1e4   # gauss


p("  gap mm:     2      3      4      5      6      7      8      9     10")
for n in (1, 2, 3):
    p(f"  {n} magnet{'s' if n > 1 else ' '} " + " ".join("%6.0f" % b_axial(z, n) for z in range(2, 11)) + "  G")
p("  A3144 operate point 70-350 G (datasheet span). Tonight: 1 magnet = no pulses, 2 = about 1 pass in 4, 3 = every pass.")
p("  2 magnets at the design 5.0 mm give 644 G, so the as-built gap is larger: ~7.5-8 mm with 2 (300 G), ~4.5-5 mm with 3.")
p("  Likely: the riser or the sensor sits ~2.5 mm further apart than drawn (clay check in bench step 4).")
OUT["hall_G"] = {n: {z: b_axial(z, n) for z in range(2, 11)} for n in (1, 2, 3)}

# ------------------------------------------------------------------ H. hanging slip ring
hdr("H. Hanging slip ring: pendulum, wind-up and kinking")
g = 9.81
for L in (50, 60, 68, 80):
    f = math.sqrt(g / (L / 1000)) / (2 * math.pi)
    p(f"  pendulum {L} mm: {f:4.2f} Hz = {60*f:5.0f} rpm")
p("  Tonight's top speed was 115-119 rpm: on the pendulum's resonance (68 mm -> 114 rpm).")
d_w = 1.6       # mm, OD of each wire of Brian's red/black pair (22-26 AWG silicone), ASSUMED
for n in (2, 5, 10):
    L = 60.0
    tan_a = 2 * math.pi * (d_w / 2) * n / L
    short = L * (1 - 1 / math.sqrt(1 + tan_a ** 2))
    p(f"  red/black pair, 60 mm, twisted {n:2d} turns: shortens {short:4.1f} mm before it kinks")
EI_W = 1.0e-6   # N m2 per stranded 24 AWG wire, ASSUMED
for T in (0.10, 0.15, 0.30):
    m_c = 2 * math.sqrt(2 * EI_W * T)
    p(f"  kink (loop) torque 2 sqrt(EI T) at {T:.2f} N tension: {1000*m_c:.2f} mN m (6 x 30 AWG PTFE leads of the design: ~4 mN m)")
p("  A capsule ring's drag is ~1 mN m by catalogue, more on cheap clones (ASSUMED): at or above the pair's kink torque.")
p("  The body is held only by its stator leads in a loose 60 mm loop: nothing stops it turning for the first turn(s),")
p("  so the rotor drags the whole ring round and winds the stator leads; once they wind up, the pair above it twists.")
p("  Both wind-ups shorten the leads and lift the ring. The ring weighs ~10 g: 0.1 N cannot keep 60 mm of lead straight.")

# ------------------------------------------------------------------ figure
OUT_PNG = os.path.join(ROOT, "docs", "img", "revn_diag_speed_vs_current.png")
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ink, ink2, muted, grid = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e1"
    series = ["#2a78d6", "#eb6834", "#1baf7a"]   # categorical slots 1-3 (validated all-pairs)
    fig, ax = plt.subplots(figsize=(9.0, 5.4), dpi=150)
    fig.patch.set_facecolor("#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    xs = [i / 200 for i in range(16, 200)]
    labels = ["M0 design: 600 rpm, 1.65 A stall", "M1 tonight's two points only: 364 rpm, 1.67 A", "M2 best fit incl. 11-14: 520 rpm, 1.2 A stall"]
    for m, c, lab in zip(MODELS, series, labels):
        ys = [rotor_rpm(m, x) for x in xs]
        ax.plot(xs, ys, color=c, lw=2.0, label=lab, solid_capstyle="round")
    ax.axhspan(0, 300, xmin=(0.60 - 0.0) / 1.0, xmax=1.0, color="#f1efe9", zorder=0)
    ax.text(0.985, 287, "belt skips here\n(stalled at 0.60 A)", ha="right", va="top", fontsize=8.5, color=ink2)
    for yv, lab in ((188, "188 rpm target"), (225, "225 rpm")):
        ax.axhline(yv, color=muted, lw=1.0, ls=(0, (4, 3)), zorder=1)
        ax.text(0.012, yv + 3, lab, fontsize=8.5, color=ink2, va="bottom")
    meas = [(0.660, 117, "loose ring + board + battery\n0.66 A, 117 rpm (measured)", (0.55, 74)),
            (0.789, 102, "tight ring + board + battery\n0.79 A, 102 rpm (measured)", (0.99, 110))]
    for x, y, lab, xyt in meas:
        ax.plot([x], [y], "o", ms=8, color=ink, mec="#fcfcfb", mew=2.0, zorder=5)
        ax.annotate(lab, (x, y), xytext=xyt, fontsize=8.5, color=ink, ha="right",
                    arrowprops=dict(arrowstyle="-", color=muted, lw=0.8))
    for m, (xl, dy, short) in zip(MODELS, ((0.36, 7, "M0 design"), (0.36, 7, "M1"), (0.12, 8, "M2 best fit"))):
        ax.text(xl, rotor_rpm(m, xl) + dy, short, fontsize=8.5, color=ink, ha="left",
                bbox=dict(boxstyle="round,pad=0.15", fc="#fcfcfb", ec="none"))
    for x, lab in ((0.104, "base alone\n0.08-0.12 A"), (0.327, "loose ring,\nbare rotor\n0.33 A (no rpm)"),
                   (0.735, "tight ring,\nbare rotor\n0.74 A (no rpm)")):
        ax.plot([x, x], [0, 14], color=ink, lw=2.0, solid_capstyle="round")
        ax.text(x, 18, lab, fontsize=8, color=ink2, ha="center", va="bottom")
    ax.set_xlim(0, 1.0)
    ax.set_ylim(0, 300)
    ax.set_xlabel("total motor current at 12 V (A)", color=ink2)
    ax.set_ylabel("rotor speed (rpm), 20T:40T belt", color=ink2)
    ax.grid(True, color=grid, lw=0.8)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(muted)
    ax.tick_params(colors=ink2)
    leg = ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=3, frameon=False, fontsize=8.5)
    for t in leg.get_texts():
        t.set_color(ink)
    ax.set_title("Rev n: rotor speed vs motor current, three motor models and tonight's points", fontsize=11, color=ink, loc="left")
    fig.tight_layout()
    fig.savefig(OUT_PNG, facecolor=fig.get_facecolor())
    p()
    p("figure: " + os.path.relpath(OUT_PNG, ROOT))
except Exception as e:  # matplotlib missing is not fatal for the numbers
    p("figure skipped: %r" % e)

with open(os.path.join(HERE, "revn_bench_diagnosis.json"), "w", encoding="utf-8") as f:
    json.dump(OUT, f, indent=1, default=str)
with open(os.path.join(HERE, "revn_bench_diagnosis_output.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(LINES) + "\n")
