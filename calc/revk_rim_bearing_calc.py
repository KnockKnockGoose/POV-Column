"""Rev k numbers: why the tube top wobbles on the gearmotor shaft, and what the 6820 rim bearing + printed Oldham coupling change.

    py calc/revk_rim_bearing_calc.py            -> prints the tables, writes calc/revk_calc.json

Inputs: the rotor's mass properties from the Fusion checks (calc/revk_checks.json, script fusionclaude/scripts/157), measured parts
(docs/measurements.md), and the ASSUMED values marked below (gearbox play, printed-PETG modulus, collar modulus). SI units inside; mm / g in prints.
2026-11-09, rev k.
"""
import json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
CK = json.load(open(os.path.join(HERE, "revk_checks.json"), encoding="utf-8"))
G = 9.81
RPM = 225.0
W = 2 * math.pi * RPM / 60.0                       # 23.56 rad/s
F_ROT = RPM / 60.0                                 # 3.75 Hz

# ---------------------------------------------------------------- rotor mass properties (Fusion, script 157)
rk, rj = CK["rotor"], CK["rev_j_rotor"]
M_K, M_J = rk["mass_g"] / 1000.0, rj["mass_g"] / 1000.0
IP_K = rk["Izz_kgm2"]
IP_J = IP_K - 0.6e-3                               # rev j rotor polar inertia (rev i/j checks: 3.38e-3); rev k adds ~0.6e-3 (ring + inner ring at r 50-90)
IT_K = rk["It_bearing_kgm2"]                       # about the bearing centre (z -14.5)
IT_J = rj["It_pivot_kgm2"]                         # about the gearbox face (z -15.75)
H_K = (rk["cg_mm"][2] - rk["pivot_z_mm"]) / 1000.0  # CG above the pivot
H_J = (rj["cg_z_mm"] - rj["pivot_z_mm"]) / 1000.0
TOP_K = (252.0 - rk["pivot_z_mm"]) / 1000.0         # top cap above the pivot
TOP_J = (252.0 - rj["pivot_z_mm"]) / 1000.0

# ---------------------------------------------------------------- materials (ASSUMED moduli for printed parts)
E_STEEL, G_STEEL = 200e9, 77e9
E_PETG = 2.0e9                                     # printed PETG, in-plane (ASSUMED)
E_PETCF = 4.0e9                                    # Fiberon PET-CF printed, in-plane (ASSUMED; datasheet XY ~3.5-4.5 GPa)
NU = 0.38
SANDWICH = 0.8                                     # 4 walls / 4+4 shells / 20 % gyroid deck: ~80 % of a solid plate's bending stiffness


def plate_D(E, t, f=1.0):
    return f * E * t ** 3 / (12 * (1 - NU ** 2))


def k_rigid_inclusion(D, a, b):
    """Rotational stiffness of a rigid central inclusion (radius a) in a circular plate clamped at b, under a couple (N m/rad)."""
    s = b * b + a * a
    return 4 * math.pi * D * s / (s * math.log(b / a) - (b * b - a * a))


# ---------------------------------------------------------------- BEFORE (rev j): rotor on the gearmotor shaft
t_brk, w_brk = 1.46e-3, 40e-3                      # measured kit L-bracket (#25)
I_brk = w_brk * t_brk ** 3 / 12
J_brk = w_brk * t_brk ** 3 / 3
k_brk_leg = E_STEEL * I_brk / 15e-3                # horizontal leg, bend -> gearbox screw circle (~15 mm effective)
k_brk_bend = E_STEEL * I_brk / 8.2e-3              # vertical leg, bend -> first bolt row (8.2 mm, measured)
k_brk_y = 1 / (1 / k_brk_leg + 1 / k_brk_bend)
k_brk_x = G_STEEL * J_brk / 15e-3                  # horizontal leg in torsion
k_post_y = E_PETG * (44e-3 * 10e-3 ** 3 / 12) / 9e-3          # printed post 10 x 44, deck -> top bolt row 9 mm
D_deck = plate_D(E_PETG, 4e-3, SANDWICH)
a_post = math.sqrt(10e-3 * 44e-3 / math.pi)        # post footprint as an equivalent round inclusion
k_deck = k_rigid_inclusion(D_deck, a_post, 97e-3)  # deck clamped at the wall (r 97)
k_before_y = 1 / (1 / k_brk_y + 1 / k_post_y + 1 / k_deck) - M_J * G * H_J
k_before_x = 1 / (1 / k_brk_x + 1 / k_deck) - M_J * G * H_J
k_before = min(k_before_x, k_before_y)
PLAY = {"clearance_mm": (0.03, 0.08), "span_mm": (15.0, 12.0)}     # ASSUMED gearbox output-shaft bushing: diametral clearance, support span
theta_play = (PLAY["clearance_mm"][0] / PLAY["span_mm"][0], PLAY["clearance_mm"][1] / PLAY["span_mm"][1])

# ---------------------------------------------------------------- AFTER (rev k): rotor on the 6820 in the collar
D_collar = plate_D(E_PETCF, 2.5e-3)                                # collar base plate
rib_frac = 8 * 3e-3 / (2 * math.pi * 75e-3)                       # 8 ribs x 3 mm around r 75
I_rib_pw = rib_frac * (11e-3) ** 3 / 12                            # ribs, ~11 mm mean height, per unit circumference
D_ribs = E_PETCF * I_rib_pw
D_comp = D_deck + D_collar + D_ribs                                # stacked plates (not bonded): bending stiffnesses add
a_b, L_strip = 60e-3, 37e-3                                        # load circle (bearing outer ring) and its distance to the wall (r 97)
k_collar = 3 * math.pi * D_comp * a_b ** 3 / L_strip ** 3          # radial cantilever strips, no hoop action (conservative)
# bearing tilt stiffness under the gravity preload (6820: ~32 balls d ~7.9 on a 112.5 pitch circle, contact angle ~15 deg once the clearance is taken up)
Z_b, r_p, alpha = 32, 56.25e-3, math.radians(15.0)
Fa = M_K * G
Q = Fa / (Z_b * math.sin(alpha))
delta = 2.0e-4 * Q ** (2.0 / 3.0) * 1e-3          # m: Hertz ball-groove deflection ~2.2e-4 mm x Q^(2/3) for a 7.9 mm ball (Palmgren), per contact
k_n = 1.5 * Q / delta / 2                                          # two contacts in series, N/m per ball
k_brg = (Z_b / 2) * k_n * math.sin(alpha) ** 2 * r_p ** 2
M_sep = Fa * r_p / 2                                               # moment at which the unloaded side would unload (gravity preload only)
k_ring = 1.0e4                                                     # PET-CF rotor ring + spigot (short thick ring), order of magnitude
k_after = 1 / (1 / k_collar + 1 / k_brg + 1 / k_ring) - M_K * G * H_K


def crit(k, It, Ip):
    """(rocking natural frequency at rest, synchronous forward-whirl critical speed) in Hz; gyroscopic stiffening for Ip < It."""
    return math.sqrt(k / It) / (2 * math.pi), math.sqrt(k / (It - Ip)) / (2 * math.pi)


fn_b, fc_b = crit(k_before, IT_J, IP_J)
fn_a, fc_a = crit(k_after, IT_K, IP_K)
amp_b = 1 / abs(1 - (F_ROT / fc_b) ** 2)
amp_a = 1 / abs(1 - (F_ROT / fc_a) ** 2)


def wobble(U_gmm, k, It, Ip, h, top):
    """Elastic synchronous wobble amplitude (mm) at the top for unbalance U at CG height h above the pivot."""
    M = U_gmm * 1e-6 * W ** 2 * h
    th = M / (k - (It - Ip) * W ** 2)
    return M, th, th * top * 1000.0


rows_U = []
U_g63_k = M_K * 1000 * 6.3 / W
for U in (rk["U_gmm"], U_g63_k, 1000.0):
    F = U * 1e-6 * W ** 2
    Mb, thb, wb = wobble(U, k_before, IT_J, IP_J, H_J, TOP_J)
    Ma, tha, wa = wobble(U, k_after, IT_K, IP_K, H_K, TOP_K)
    rows_U.append((U, F, Mb, wb, Ma, wa))
play_top = (theta_play[0] * TOP_J * 1000, theta_play[1] * TOP_J * 1000)

# ---------------------------------------------------------------- geometric runout after (what is left)
runout = {"bearing raceway axial runout (P6, ASSUMED 20 um over the 112.5 pitch circle)": 20e-6 / 0.1125,
          "printed land vs ring top face (one print, 0.05 mm over d100)": 0.05e-3 / 0.100,
          "plate underside / tube end squareness (0.1 mm over d160, as rev j)": 0.1e-3 / 0.160}
runout_top = {k: v * TOP_K * 1000 for k, v in runout.items()}
runout_rss = math.sqrt(sum(v ** 2 for v in runout_top.values()))

# ---------------------------------------------------------------- bearing load / life (6820ZZ: Cr 19.6 kN, C0r 23 kN, 4800 rpm grease limit)
Cr, C0r, n_lim = 19.6e3, 23e3, 4800.0
Fr = 1000.0 * 1e-6 * W ** 2                        # worst assumed unbalance force
Y_ax = 2.3
P = 0.56 * Fr + Y_ax * Fa
L10_rev = (Cr / P) ** 3 * 1e6
L10_h = L10_rev / (RPM * 60)
T_fric = 0.5 * 0.0015 * P * 0.100                  # SKF simplified, mu 0.0015, bore 100 mm
T_drag = 0.027                                     # rotor drag at 225 rpm (FDM report load audit)

# ---------------------------------------------------------------- hall field (two stacked 6 x 3 N35 discs, Br 1.2 T, ASSUMED grade)
def b_axis(z_mm, R=3.0, L=6.0, Br=1.2):
    return Br / 2 * ((z_mm + L) / math.hypot(R, z_mm + L) - z_mm / math.hypot(R, z_mm)) * 1e4    # gauss


B5 = b_axis(5.0)
B6 = b_axis(6.0)

# ---------------------------------------------------------------- printed Oldham
r_lug, T_spin = 8e-3, 0.10                          # lugs on PCD 16; spin-up torque with the knob turned up gently (ASSUMED)


def hertz_line(F, R=2.75e-3, L=2.25e-3, E=E_PETCF):
    Es = E / (1 - NU ** 2)
    return math.sqrt(F * Es / (math.pi * R * L)) / 1e6


F_lug_run, F_lug_spin = T_drag / (2 * r_lug), T_spin / (2 * r_lug)
p_run, p_spin = hertz_line(F_lug_run), hertz_line(F_lug_spin)

# ---------------------------------------------------------------- motor mount: deck post (kept) vs a tower on the bottom plate
D_bot = plate_D(E_PETG, 3e-3, SANDWICH)
k_deck_v = 16 * math.pi * D_deck / 0.097 ** 2                       # clamped plate, central load (N/m)
k_bot_v = 16 * math.pi * D_bot * (1 + NU) / ((3 + NU) * 0.085 ** 2)  # 3 mm plate on the 4 feet (r 85), simply supported
sag_motor = 0.22 * G / k_deck_v * 1000.0

# ---------------------------------------------------------------- print
print("REV K RIM BEARING - numbers (SI; mm and g where noted)\n")
print("Speed %.0f rpm = %.2f Hz, omega %.2f rad/s" % (RPM, F_ROT, W))
print("Rotor rev j: %.0f g, CG %.1f mm above the gearbox face, I_t %.2e, I_p %.2e kg m^2" % (M_J * 1000, H_J * 1000, IT_J, IP_J))
print("Rotor rev k: %.0f g, CG %.1f mm above the bearing centre, I_t %.2e, I_p %.2e kg m^2, U %.1f g mm (G6.3 allows %.0f)" % (
    M_K * 1000, H_K * 1000, IT_K, IP_K, rk["U_gmm"], U_g63_k))
print("\nBEFORE: rocking stiffness of the mount (N m/rad)")
for k, v in (("L-bracket about the bend axis (leg %.0f, bend %.0f)" % (k_brk_leg, k_brk_bend), k_brk_y), ("L-bracket in torsion", k_brk_x),
             ("printed post (PETG 10 x 44)", k_post_y), ("deck (4 mm PETG, clamped at r 97, post as a d%.0f inclusion)" % (2 * a_post * 1000), k_deck),
             ("gravity (inverted pendulum, -m g h)", -M_J * G * H_J), ("TOTAL (softer axis)", k_before)):
    print("   %-62s %8.1f" % (k, v))
print("   + gearbox output-shaft free play (ASSUMED %.2f-%.2f mm over %.0f-%.0f mm): %.4f-%.4f rad -> %.1f-%.1f mm at the top (amplitude)" % (
    PLAY["clearance_mm"][0], PLAY["clearance_mm"][1], PLAY["span_mm"][0], PLAY["span_mm"][1], theta_play[0], theta_play[1], play_top[0], play_top[1]))
print("   rocking mode at rest %.1f Hz, synchronous critical %.1f Hz -> 3.75 Hz runs at %.0f %% of it, amplification x%.2f (2x harmonic %.1f Hz sits on the rest mode)" % (
    fn_b, fc_b, 100 * F_ROT / fc_b, amp_b, 2 * F_ROT))
print("\nAFTER: rocking stiffness (N m/rad)")
for k, v in (("collar + deck on the wall (cantilever strips, no hoop action)", k_collar), ("6820 tilt stiffness under the gravity preload", k_brg),
             ("rotor ring + spigot (order of magnitude)", k_ring), ("gravity", -M_K * G * H_K), ("TOTAL", k_after)):
    print("   %-62s %8.0f" % (k, v))
print("   bearing stays seated up to %.2f N m (gravity preload x r_p / 2)" % M_sep)
print("   rocking mode at rest %.1f Hz, synchronous critical %.1f Hz (%.1f x the 3.75 Hz spin), amplification x%.3f" % (fn_a, fc_a, fc_a / F_ROT, amp_a))
print("   stiffer by x%.0f (elastic); the free play is gone (the rotor no longer hangs on the shaft)" % (k_after / k_before))
print("\nUNBALANCE: U (g mm) | F (N) | before: M (N m), top wobble (mm, amplitude, elastic only) | after: M, top wobble")
for U, F, Mb, wb, Ma, wa in rows_U:
    print("   %7.1f | %.4f | %.4f  %6.3f | %.4f  %7.4f" % (U, F, Mb, wb, Ma, wa))
print("   before, the free play adds %.1f-%.1f mm (amplitude) on top of the elastic part: %.1f-%.1f mm peak-to-peak in total at U 1000" % (
    play_top[0], play_top[1], 2 * (play_top[0] + rows_U[2][3]), 2 * (play_top[1] + rows_U[2][3])))
print("\nWHAT IS LEFT AFTER: geometric runout at the top (amplitude, mm)")
for k, v in runout_top.items():
    print("   %-78s %.3f" % (k, v))
print("   RSS %.2f mm amplitude (%.2f mm peak-to-peak) -> lap the land / plate if it shows" % (runout_rss, 2 * runout_rss))
print("\nBEARING 6820ZZ: Fa %.1f N, Fr <= %.2f N, P %.1f N vs Cr %.1f kN / C0r %.0f kN (static factor %.0f); L10 %.1e h; speed %.1f %% of the limit; friction %.1f mN m vs rotor drag %.0f mN m" % (
    Fa, Fr, P, Cr / 1e3, C0r / 1e3, C0r / P, L10_h, 100 * RPM / n_lim, T_fric * 1e3, T_drag * 1e3))
print("HALL: two 6 x 3 discs, on-axis field at 5.0 mm %.0f G, at 6.0 mm %.0f G (A3144 operates <= 350 G worst case)" % (B5, B6))
print("OLDHAM: lug force %.1f N running / %.1f N at %.2f N m spin-up; Hertz line pressure on PET-CF %.0f / %.0f MPa (PET-CF ~70+ MPa)" % (
    F_lug_run, F_lug_spin, T_spin, p_run, p_spin))
print("MOTOR MOUNT: deck centre stiffness %.0f N/mm vs a tower on the 3 mm bottom plate %.0f N/mm (x%.1f softer); motor + bracket sag on the deck %.3f mm" % (
    k_deck_v / 1e3, k_bot_v / 1e3, k_deck_v / k_bot_v, sag_motor))

out = {"rpm": RPM, "omega": W, "rotor_k": rk, "rotor_j": rj,
       "before": {"k_bracket_y": k_brk_y, "k_bracket_x": k_brk_x, "k_post": k_post_y, "k_deck": k_deck, "k_total": k_before, "fn_rest_hz": fn_b,
                  "f_crit_hz": fc_b, "amp": amp_b, "theta_play": theta_play, "play_top_mm": play_top},
       "after": {"k_collar": k_collar, "k_bearing": k_brg, "k_ring": k_ring, "k_total": k_after, "fn_rest_hz": fn_a, "f_crit_hz": fc_a, "amp": amp_a,
                 "M_sep": M_sep, "runout_top_mm": runout_top, "runout_rss_mm": runout_rss},
       "unbalance_rows": [{"U_gmm": U, "F_N": F, "M_before": Mb, "wobble_before_mm": wb, "M_after": Ma, "wobble_after_mm": wa} for U, F, Mb, wb, Ma, wa in rows_U],
       "bearing": {"Fa": Fa, "Fr": Fr, "P": P, "L10_h": L10_h, "friction_Nm": T_fric, "speed_frac": RPM / n_lim},
       "hall_G": {"5.0": B5, "6.0": B6}, "oldham": {"F_run": F_lug_run, "F_spin": F_lug_spin, "p_run_MPa": p_run, "p_spin_MPa": p_spin},
       "motor_mount": {"k_deck_N_per_m": k_deck_v, "k_bottom_plate_N_per_m": k_bot_v, "sag_mm": sag_motor}}
with open(os.path.join(HERE, "revk_calc.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, indent=1)
print("\nwrote calc/revk_calc.json")
