"""Rev m numbers: rotor power from the base (slip ring / wireless / brushes / battery) and what 225 rpm needs mechanically.

    py calc/rev_m_power_calc.py          -> prints the tables, writes calc/rev_m_calc.json and docs/img/rev_m_wobble_vs_rpm.png

Inputs: calc/revk_calc.json + calc/revk_checks.json (rev k analysis and Fusion mass properties), docs/measurements.md,
docs/2026-11-02-electrical-design.md (current budget), fusionclaude/lib/povlib.py (bank position), vendor data quoted in
docs/2026-11-13-rotor-power-and-wobble.md. Values marked ASSUMED are not measured. SI inside; mm / g / mA in prints.
2026-11-13, rev m study (no CAD driven).
"""
import json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
K = json.load(open(os.path.join(HERE, "revk_calc.json"), encoding="utf-8"))
CK = json.load(open(os.path.join(HERE, "revk_checks.json"), encoding="utf-8"))
G = 9.81
OUT = {}


def w(rpm):
    return 2 * math.pi * rpm / 60.0


def hdr(t):
    print("\n" + "=" * 100 + "\n" + t + "\n" + "=" * 100)


# ------------------------------------------------------------------ 1. why 225 rpm (camera)
hdr("1. Camera: refresh = strips per row x rev/s; shutter x refresh must be a whole number")
STRIPS, SETS = 24, 3
PER_ROW = STRIPS // SETS                     # 8 strips paint each row per revolution
cam = []
for fps, shutter in [(30, 1 / 30), (24, 1 / 24), (30, 1 / 15), (30, 1 / 20), (60, 1 / 60)]:
    rpm = 60.0 / (PER_ROW * shutter)         # exactly one refresh per exposure
    cam.append(dict(fps=fps, shutter=f"1/{round(1/shutter)}", rpm_for_one_refresh=rpm))
    print(f"  {fps}p, shutter 1/{round(1/shutter):>2}: one full refresh per exposure at {rpm:6.1f} rpm")
OUT["camera"] = cam

# ------------------------------------------------------------------ 2. the 5 V load the power path must carry
hdr("2. Rotor 5 V load (electrical report 3.1; CAP_MA 2000-2600 today)")
LOADS = {"blank": 0.46, "dog animation": 0.89, "dense text (capped 2.0 A)": 2.12, "design peak (rev m target)": 3.0}
for k_, a in LOADS.items():
    print(f"  {k_:<28} {a:4.2f} A  {5*a:5.1f} W")
P_PEAK = 5.0 * 3.0
OUT["loads_A"] = LOADS

# ------------------------------------------------------------------ 3. options, electrical numbers
hdr("3. Power path options at 5 V / 3 A peak")
opts = {}

# 3a battery (as now)
BANK_G, BANK_Y_MM = 199.0, 5.3               # povlib BANK_MASS, BANK_Y (cradle centre off axis)
BANK_WH = 30.0                               # ~30 Wh delivered at 5 V (electrical report)
PORT_A = 2.4                                 # un-negotiated USB-A port (label 3 A)
rt = {k_: BANK_WH / (5 * a) for k_, a in LOADS.items() if a <= PORT_A}
opts["battery"] = dict(mass_on_rotor_g=BANK_G + 17.6, port_limit_A=PORT_A, runtime_h=rt,
                       static_offset_gmm=BANK_G * BANK_Y_MM, unbalance_per_mm_shift_gmm=BANK_G)
print(f"  battery: {BANK_G:.0f} g + 17.6 g pigtail on the rotor; port {PORT_A} A (< 3 A target); runtime "
      + ", ".join(f"{k_} {h:.1f} h" for k_, h in rt.items()))
print(f"           designed offset {BANK_G*BANK_Y_MM:.0f} g mm (balanced by the carrier side); every 1 mm the cell CG sits"
      f" off its case centre, or the bank is reseated differently, = {BANK_G:.0f} g mm")

# 3b capsule slip ring, Senring SNM022A-06: 6 rings x 2 A, 250 rpm continuous (SparkFun) / 300 (VoltShop), 28 AWG x 250 mm leads
R_28AWG = 0.213                              # ohm/m
LEAD_M = 0.25 + 0.10                         # 250 mm lead + ~100 mm extension each side to J1 / base terminal (ASSUMED)
R_CONTACT = 0.020                            # static ring+brush resistance per circuit (ASSUMED; capsule datasheets quote < 10-20 mohm variation)
DR_DYN = 0.030                               # dynamic contact-resistance swing per circuit while turning (ASSUMED, worst)
N_PAR = 3                                    # 3 rings per pole
r_pole = (R_28AWG * LEAD_M + R_CONTACT) / N_PAR
for scheme, v, eta in [("A: 5 V across the ring (buck in the base)", 5.0, 1.0), ("B: 12 V across the ring, buck on the rotor", 12.0, 0.90)]:
    i = P_PEAK / eta / v
    drop = i * 2 * r_pole
    noise = i * 2 * DR_DYN / N_PAR
    per_ring = i / N_PAR
    opts["slip_" + scheme[0]] = dict(V=v, I_peak_A=i, I_per_ring_A=per_ring, drop_V=drop, dyn_noise_V=noise, ring_rating_A=2.0)
    print(f"  slip ring {scheme}: I {i:4.2f} A, {per_ring:4.2f} A per ring (rated 2 A), loop drop {1000*drop:4.0f} mV,"
          f" contact noise <= {1000*noise:3.0f} mV p-p before the bulk caps / buck")
SLIP_RPM = 250.0
REV_LIFE = 10e6                              # ASSUMED order of magnitude for capsule rings (datasheets 10-50 M rev)
print(f"  speed: 225 rpm = {225/SLIP_RPM*100:.0f} % of the 250 rpm continuous rating; {REV_LIFE:.0e} rev = {REV_LIFE/(225*60):.0f} h at 225 rpm")
opts["slip_speed_frac"] = 225 / SLIP_RPM
opts["slip_life_h_at_225"] = REV_LIFE / (225 * 60)

# 3c wireless (DFRobot DFR0712-class 12 V -> 5 V 2 A, <= 1.8 A continuous, 3-6 mm gap)
WPT_I = 1.8
WPT_ETA = (0.60, 0.75)                       # ASSUMED, product study
p_in = [WPT_I * 5 / e for e in WPT_ETA]
led_cap = WPT_I - 0.12 - 0.34                # minus ESP32 and dark current
opts["wireless"] = dict(I_cont_A=WPT_I, P_out_W=5 * WPT_I, P_in_W=p_in, LED_cap_A=led_cap, short_of_3A_A=3.0 - WPT_I)
print(f"  wireless 5 V 2 A module: {WPT_I} A continuous = {5*WPT_I:.0f} W out, {p_in[1]:.0f}-{p_in[0]:.0f} W in;"
      f" LED cap would drop to {led_cap:.2f} A (today 2.0-2.6 A); short of the 3 A peak by {3-WPT_I:.1f} A")

# 3d DIY face rings + carbon brushes at the rotor ring (r ~75 mm)
R_RING = 0.075
v_surf = w(225) * R_RING
F_BRUSH, MU_BRUSH, N_BRUSH = 1.0, 0.20, 4    # ASSUMED: ~25 kPa on a 5 x 8 mm carbon brush, carbon on copper/brass
T_brush = N_BRUSH * F_BRUSH * MU_BRUSH * R_RING
opts["brushes"] = dict(surface_speed_m_s=v_surf, drag_Nm=T_brush, drag_W=T_brush * w(225), uplift_N=N_BRUSH * F_BRUSH)
print(f"  DIY brushes at r 75: surface {v_surf:.2f} m/s (carbon brushes are rated 10+ m/s), drag {1000*T_brush:.0f} mN m"
      f" ({T_brush*w(225):.1f} W, vs the rotor's 27 mN m of air drag), uplift {N_BRUSH*F_BRUSH:.0f} N vs the 10.8 N gravity preload")
OUT["options"] = opts

# ------------------------------------------------------------------ 4. balance budget
hdr("4. Balance budget at 225 rpm")
rk = CK["rotor"]
M_K = rk["mass_g"]
def g_limit(m_g, grade, rpm=225):
    return m_g * grade / w(rpm)              # g mm: e = G / omega (mm with G in mm/s)
# rev m rotor: rev k minus bank, pigtail, Oldham dog + disc; plus slip-ring rotor half, wires, rotor buck, drive spool (ASSUMED masses)
ADD = {"slip-ring rotor half + leads": 8.0, "rotor buck 5 A": 12.0, "drive spool with 40T pulley (PET-CF)": 12.0}
SUB = {"R05 power bank": 199.0, "R08 USB pigtail": 17.6, "R19 Oldham rotor dog": 1.9, "R20 Oldham disc": 4.6}
M_M = M_K - sum(SUB.values()) + sum(ADD.values())
for name, m in [("rev k (bank on)", M_K), ("rev m (base power)", M_M)]:
    print(f"  {name:<20} {m:6.0f} g: G6.3 {g_limit(m, 6.3):4.0f} g mm, G2.5 {g_limit(m, 2.5):4.0f} g mm")
F_per_1000 = 1e-6 * 1000 * w(225) ** 2
print(f"  force per 1000 g mm: {F_per_1000:.3f} N at 225 rpm vs {1e-6*1000*w(125.7)**2:.3f} N at the 125.7 rpm run "
      f"(x{(225/125.7)**2:.2f})")
print(f"  one M3 x 8 + nut (0.9 g) in the trim flange (r 88) = {0.9*88:.0f} g mm; bank shift sensitivity {BANK_G:.0f} g mm per mm"
      f" = {BANK_G/g_limit(M_K,6.3)*100:.0f} % of the G6.3 budget per mm")
OUT["balance"] = dict(M_k_g=M_K, M_m_g=M_M, G63_k=g_limit(M_K, 6.3), G63_m=g_limit(M_M, 6.3), G25_m=g_limit(M_M, 2.5),
                      add=ADD, sub=SUB)

# ------------------------------------------------------------------ 5. rocking response vs rpm (rev j, rev k, rev m)
hdr("5. Top-edge wobble vs rpm (rigid rotor rocking on its support; undamped single mode + gyroscopic stiffening)")
b, a = K["before"], K["after"]
rj = K["rotor_j"]
# lever arms
H_J = (rj["cg_z_mm"] - rj["pivot_z_mm"]) / 1000.0
H_K = (rk["cg_mm"][2] - rk["pivot_z_mm"]) / 1000.0
TOP_J = (252.0 - rj["pivot_z_mm"]) / 1000.0
TOP_K = (252.0 - rk["pivot_z_mm"]) / 1000.0
IP_K, IT_K, IT_J = rk["Izz_kgm2"], rk["It_bearing_kgm2"], rj["It_pivot_kgm2"]
IP_J = IP_K - 0.6e-3
# rev m: bank out. Bank CG z ~ 14 + 105.7/2 = 66.9 mm above the plate top (cradle floor z 14, bank standing)
zb = (14.0 + 105.7 / 2 - rk["pivot_z_mm"]) / 1000.0
dIt_bank = BANK_G / 1000 * (zb ** 2 + (0.1057 ** 2 + 0.0663 ** 2) / 12)
z_add = (-12.0 - rk["pivot_z_mm"]) / 1000.0  # spool / slip ring / buck near the plate
IT_M = IT_K - dIt_bank - 0.0176 * ((100 - rk["pivot_z_mm"]) / 1000) ** 2 + sum(ADD.values()) / 1000 * z_add ** 2
IP_M = IP_K - BANK_G / 1000 * ((0.0663 ** 2 + 0.025 ** 2) / 12 + (BANK_Y_MM / 1000) ** 2)
cg_m = (M_K * rk["cg_mm"][2] - BANK_G * (14 + 105.7 / 2) - 17.6 * 100 - 6.5 * 0 + sum(ADD.values()) * (-12)) / M_M
H_M = (cg_m - rk["pivot_z_mm"]) / 1000.0
K_J, K_K = b["k_total"], a["k_total"]
K_M = K_K  # same support


def resp(k, It, Ip, m_g, h, top, U_gmm, rpm):
    om = w(rpm)
    kg = k - m_g / 1000 * G * h               # gravity (inverted pendulum)
    den = kg - (It - Ip) * om ** 2            # synchronous forward whirl: gyroscopic term stiffens (It - Ip)
    M = U_gmm * 1e-6 * om ** 2 * h
    return abs(M / den) * top * 1000          # mm amplitude at the top edge


def fn(k, It, m_g, h):
    return math.sqrt((k - m_g / 1000 * G * h) / It) / (2 * math.pi)


def fcrit(k, It, Ip, m_g, h):
    return math.sqrt((k - m_g / 1000 * G * h) / (It - Ip)) / (2 * math.pi)


f_j, f_k, f_m = fn(K_J, IT_J, rj["mass_g"], H_J), fn(K_K, IT_K, M_K, H_K), fn(K_M, IT_M, M_M, H_M)
print(f"  rocking mode at rest: rev j {f_j:.1f} Hz, rev k {f_k:.1f} Hz, rev m {f_m:.1f} Hz (I_t {IT_M:.4f} vs {IT_K:.4f} kg m2,"
      f" CG {cg_m:.1f} vs {rk['cg_mm'][2]:.1f} mm)")
print(f"  synchronous critical: rev j {fcrit(K_J, IT_J, IP_J, rj['mass_g'], H_J)*60:.0f} rpm, rev k "
      f"{fcrit(K_K, IT_K, IP_K, M_K, H_K)*60:.0f} rpm, rev m {fcrit(K_M, IT_M, IP_M, M_M, H_M)*60:.0f} rpm")
print(f"  rev j: twice the spin hits the {f_j:.2f} Hz mode at {f_j/2*60:.0f} rpm; 2x amplification "
      + ", ".join(f"{r} rpm x{1/abs(1-(2*r/60/f_j)**2):.1f}" for r in (125.7, 180, 200, 225)))
U_ASBUILT = (1000, 2000)                     # ASSUMED as-built range (hand wiring, tape, glue, bank)
PLAY_TOP = b["play_top_mm"]                  # rev j free play at the top (radius), rev k analysis
rows = []
for rpm in (100, 125.7, 150, 180, 200, 225, 250):
    r = dict(rpm=rpm)
    for U in U_ASBUILT:
        r[f"j_U{U}"] = resp(K_J, IT_J, IP_J, rj["mass_g"], H_J, TOP_J, U, rpm)
        r[f"k_U{U}"] = resp(K_K, IT_K, IP_K, M_K, H_K, TOP_K, U, rpm)
        r[f"m_U{U}"] = resp(K_M, IT_M, IP_M, M_M, H_M, TOP_K, U, rpm)
    rows.append(r)
print("  rpm   | rev j elastic U1000/U2000 (mm) | rev k U1000/U2000 | rev m U1000/U2000   (+ rev j play 0.5-1.8 mm radius)")
for r in rows:
    print(f"  {r['rpm']:5.1f} | {r['j_U1000']:6.3f} / {r['j_U2000']:6.3f}            | {r['k_U1000']:6.4f} / {r['k_U2000']:6.4f}"
          f" | {r['m_U1000']:6.4f} / {r['m_U2000']:6.4f}")
OUT["rocking"] = dict(f_rest_hz=dict(j=f_j, k=f_k, m=f_m), It_m=IT_M, Ip_m=IP_M, cg_m_mm=cg_m, rows=rows,
                      rpm_2x_on_mode_j=f_j / 2 * 60)

# ------------------------------------------------------------------ 6. motor: is the JGB37-520 600 rpm good for 225?
hdr("6. Motor (JGB37-520, 12 V, 600 rpm no-load; ratio 1:10 ASSUMED from listings)")
T_AIR, T_BRG = 0.027, 0.0019                 # rev k analysis
T_LOAD = T_AIR + T_BRG
RATIO = 10.0
STALL_A, V = 1.65, 12.0
N0_ARM = 600 * RATIO                         # armature no-load rpm
KT = V / (N0_ARM * 2 * math.pi / 60)         # N m / A at the armature (ideal, ignores R losses)
T_STALL_OUT = KT * STALL_A * RATIO * 0.70    # 70 % gearbox efficiency ASSUMED
for name, ratio_belt in [("direct (rev k Oldham)", 1.0), ("GT2 belt 20T:40T (rev m)", 2.0)]:
    rpm_out = 225 * ratio_belt
    T_out = T_LOAD / ratio_belt / 0.95 if ratio_belt > 1 else T_LOAD
    arm_hz = rpm_out * RATIO / 60
    duty = (rpm_out / 600) / (1 - T_out / T_STALL_OUT)
    print(f"  {name:<26} gearbox output {rpm_out:4.0f} rpm, torque {1000*T_out:4.1f} mN m ({T_out/T_STALL_OUT*100:3.0f} % of the"
          f" ~{1000*T_STALL_OUT:.0f} mN m est. stall), PWM duty ~{100*duty:3.0f} %, armature {arm_hz:5.1f} Hz,"
          f" shaft power {T_LOAD*w(225):.2f} W")
    OUT.setdefault("motor", {})[name] = dict(rpm_out=rpm_out, T_out_Nm=T_out, armature_hz=arm_hz, duty=duty)
print(f"  rated torque in listings: 0.15-1.1 kg cm = {0.15*98.1:.0f}-{1.1*98.1:.0f} mN m; estimated stall at the output"
      f" {1000*T_STALL_OUT:.0f} mN m (Kt {KT*1000:.1f} mN m/A)")
print(f"  spin-up 0 -> 225 rpm on I_zz {IP_M:.4f} kg m2 at 60 mN m net: {IP_M*w(225)/0.060:.1f} s;"
      f" stored energy {0.5*IP_M*w(225)**2:.2f} J")
print(f"  WATCH: direct drive puts the armature at {225*RATIO/60:.1f} Hz, {abs(225*RATIO/60-f_k)/f_k*100:.0f} % from rev k's"
      f" {f_k:.1f} Hz rocking mode; the 2:1 belt moves it to {450*RATIO/60:.0f} Hz")
OUT["motor_stall_out_Nm"] = T_STALL_OUT

# ------------------------------------------------------------------ 7. belt geometry and loads (rev m)
hdr("7. GT2 belt, 20T motor : 40T rotor, 6 mm wide")
P = 2.0
def pd(n):
    return n * P / math.pi
D1, D2 = pd(20), pd(40)
def belt_len(C):
    return 2 * C + math.pi * (D1 + D2) / 2 + (D2 - D1) ** 2 / (4 * C)
def centre_for(L):
    lo, hi = 15.0, 80.0
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if belt_len(mid) < L else (lo, mid)
    return (lo + hi) / 2
belts = {L: centre_for(L) for L in (110, 112, 122, 158)}
for L, C in belts.items():
    print(f"  closed loop {L} mm ({L//2} T): centre distance {C:5.1f} mm; motor pulley edge (flange r 8) at r {C+8:4.1f}")
Te = T_LOAD / (D2 / 2 / 1000)
T0 = 4.0                                    # static tension per strand (ASSUMED, light finger tension)
side = 2 * T0
z_belt, z_brg = -17.0, -14.5
M_belt = side * abs(z_belt - z_brg) / 1000
print(f"  effective pull {Te:.2f} N at 29 mN m; static {T0:.0f} N per strand -> {side:.0f} N on the rotor, at z {z_belt}"
      f" vs bearing centre {z_brg}: {1000*M_belt:.0f} mN m constant (non-rotating) moment vs 300 mN m to unload the bearing")
print(f"  tooth-mesh frequency at the rotor: {40*225/60:.0f} Hz (far above the ~40 Hz rocking mode)")
OUT["belt"] = dict(D1=D1, D2=D2, centres=belts, Te_N=Te, side_N=side, moment_Nm=M_belt)

# ------------------------------------------------------------------ 8. figure
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rpms = [60 + i for i in range(0, 211)]
    fig, ax = plt.subplots(figsize=(8.0, 4.4), dpi=150)
    fig.patch.set_facecolor("#fcfcfb"); ax.set_facecolor("#fcfcfb")
    U = 1000
    jy = [resp(K_J, IT_J, IP_J, rj["mass_g"], H_J, TOP_J, U, r) + PLAY_TOP[0] for r in rpms]
    ky = [resp(K_K, IT_K, IP_K, M_K, H_K, TOP_K, U, r) + a["runout_rss_mm"] for r in rpms]
    ax.plot(rpms, [2 * v for v in jy], color="#2a78d6", lw=2, label="rev j: rotor on the gearmotor shaft")
    ax.plot(rpms, [2 * v for v in ky], color="#eb6834", lw=2, label="rev k / m: rotor on the 6820 rim bearing")
    ax.axvline(225, color="#52514e", lw=1, ls="--")
    ax.text(222, 3.6, "225 rpm: 30p at 1/30 s,\nand 2x spin = rev j's %.1f Hz mode" % f_j, ha="right", va="top", fontsize=8, color="#52514e")
    ax.text(rpms[-1], 2 * jy[-1] + 0.12, "rev j", ha="right", fontsize=9, color="#0b0b0b")
    ax.text(rpms[-1], 2 * ky[-1] + 0.12, "rev k / m", ha="right", fontsize=9, color="#0b0b0b")
    ax.set_xlabel("rotor speed (rpm)", color="#52514e"); ax.set_ylabel("top-edge wobble, peak to peak (mm)", color="#52514e")
    ax.set_ylim(0, 4.0); ax.set_xlim(60, 270)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#c3c2b7")
    ax.tick_params(colors="#52514e"); ax.grid(axis="y", color="#e7e6e2", lw=0.8)
    ax.set_title("Predicted top-edge wobble vs speed (U = 1,000 g mm; rev j with 0.5 mm of play;\n"
                 "1x response only: rev j's 2x resonance at 225 rpm comes on top)", fontsize=9, color="#0b0b0b", loc="left")
    ax.legend(loc="upper left", fontsize=8, frameon=False)
    fig.tight_layout()
    p = os.path.join(ROOT, "docs", "img", "rev_m_wobble_vs_rpm.png")
    fig.savefig(p, facecolor=fig.get_facecolor())
    print(f"\n  figure -> {p}")
except Exception as e:  # matplotlib optional
    print("  (no figure:", e, ")")

json.dump(OUT, open(os.path.join(HERE, "rev_m_calc.json"), "w", encoding="utf-8"), indent=1, default=str)
print("\n  -> calc/rev_m_calc.json")
