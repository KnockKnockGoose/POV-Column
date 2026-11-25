"""Electrical numbers for docs/2026-11-02-electrical-design.md (SI units). Run: py calc/elec_calc.py

v2 rotor: 24 SK9822 strips (14 LEDs each, 336 LEDs) on two 12-strip serpentine chains, INIU BI-B61 power bank (USB-A, 5 V,
2.4 A for an un-negotiated load per the 2026-11-01 listing check; the official spec lists SCP modes up to 5 V 4.5 A),
firmware cap 2.0 A, ESP32-WROOM-32 DevKit, one 74AHCT125, A3144 hall. Rev d (2026-11-03): no rocker switch; the pigtail plug is the on/off. Geometry from fusionclaude/lib/povlib.py (tube r 80,
wall 1.6, strips at 15 deg, carrier 70 x 90 (rev h; 60 x 80 before) standing at y -19, sled plate z 6-8.4). Every number quoted in the report comes
from here; assumptions are marked and should be replaced by bench measurements where the report says "measure".
"""
import math
import numpy as np

G = 9.81
# ---------------------------------------------------------------- wire data (AWG: area mm2, ohm/m at 20 C, ~g/m silicone-insulated)
AWG = {22: (0.326, 0.0530, 3.8), 24: (0.205, 0.0842, 2.7), 26: (0.129, 0.1339, 2.0), 28: (0.0810, 0.2129, 1.3), 30: (0.0509, 0.3386, 0.9)}
# ---------------------------------------------------------------- strip and LED (assumptions: SK9822 ~ APA102 class)
N_STRIP, N_LED, N_CHAIN = 24, 14, 2
N = N_STRIP * N_LED
I_CH_FULL = 0.020          # A per colour channel at 255 and gb 31 (assumption; measure one strip white: expect ~0.8-0.85 A for 14 LEDs)
I_DARK = 0.001             # A per LED, data idle (APA102/SK9822 ~0.5-1 mA; measure: a dark 14-LED strip should read 7-15 mA)
I_ESP = 0.12               # A ESP32 average with Wi-Fi; peaks 0.3-0.4 A for ~ms
CAP_A = 2.6                # firmware cap on LED current incl. dark current (rev e, 2026-11-03: the bank's USB-A label reads 5 V 3 A; was 2.0 for the listed 2.4 A)
I_PORT = 3.0               # INIU USB-A port for a plain 5 V load (label read by Brian 2026-11-03; listing said 2.4); the SCP spec allows 4.5 A, so a fault may draw more
I_FUSE = 4.0               # F1 fast-blow (rev e: 4 A; 3 A was too close to the 2.72 A draw)
STRIP_L = 14 * 1000 / 60 / 1000          # m, 0.2333
R_STRIP_RAIL = 0.30        # ohm/m per copper rail (5 V or GND) of a 12 mm 60/m strip (assumption; measure: ~0.07 ohm end-to-end per rail)
V_PORT = 5.0               # bank port voltage under load (measure; INIU regulates to ~5.0-5.1 V)


def hdr(t):
    print("\n=== %s ===" % t)


hdr("Rotor loads at r (what the wiring sees)")
for rpm in (225, 270, 300):
    w = 2 * math.pi * rpm / 60
    print("%d rpm: w = %.2f rad/s; a = w^2 r: r 80 mm %.1f g (strips, slots), r 42 mm %.1f g (hall), r 30 mm %.1f g (carrier edge), r 12 mm %.2f g (bank CG)" % (
        rpm, w, w ** 2 * 0.080 / G, w ** 2 * 0.042 / G, w ** 2 * 0.030 / G, w ** 2 * 0.012 / G))
w = 2 * math.pi * 225 / 60
for awg, L in ((28, 0.045), (26, 0.30), (22, 0.30)):
    m = AWG[awg][2] * L
    print("  %d AWG x %.0f mm wire: %.2f g -> %.4f N at r 80 (225 rpm); a 1 g blob of hot glue at r 80: %.3f N" % (awg, L * 1e3, m, m * 1e-3 * w ** 2 * 0.080, 1e-3 * w ** 2 * 0.080))
print("  a strip pad peels at roughly 5-10 N; the wire loads above are 1000x smaller -> strain relief is for handling and fatigue, not for g")

hdr("Current budget (5 V rail)")
cases = [("sparse text, 15 % lit, one channel", 0.15 * N * I_CH_FULL), ("dog animation (validator peak, LEDs only)", 0.889 - 0.336 - 0.12),
         ("dense text, 30 % lit", 0.30 * N * I_CH_FULL), ("all white 255 (never)", 3 * N * I_CH_FULL)]
print("%-46s %8s %8s %8s %8s | %8s %8s %8s" % ("case", "LEDs A", "dark A", "ESP A", "total A", "capped", "W", "h@30Wh"))
for lab, i_led in cases:
    dark = N * I_DARK
    tot = i_led + dark + I_ESP
    capped = min(i_led + dark, CAP_A) + I_ESP
    print("%-46s %8.2f %8.2f %8.2f %8.2f | %8.2f %8.1f %8.1f" % (lab, i_led, dark, I_ESP, tot, capped, 5 * capped, 30 / (5 * capped)))
print("per chain at the cap: %.2f A; per feed with 8 feeds (4 per chain): %.2f A; with 4 feeds (chain ends only): %.2f A" % (CAP_A / 2, CAP_A / 8, CAP_A / 4))
print("port margin: cap %.1f + ESP32 %.2f = %.2f A vs %.1f A port = %.0f %% headroom; idle (blank LEDs + ESP32) = %.2f A, far above any bank auto-off threshold (~0.05-0.1 A)" % (
    CAP_A, I_ESP, CAP_A + I_ESP, I_PORT, (1 - (CAP_A + I_ESP) / I_PORT) * 100, N * I_DARK + I_ESP))

hdr("Trunk: bank -> pigtail -> fuse -> screw terminal J1 -> bus (series resistances, assumptions)")
# rev d (2026-11-03): the KCD11 rocker SW1, its 2 x 0.30 m 22 AWG loop and the J2 terminal are gone; plugging the pigtail into the bank is the
# on/off. The removed elements are kept here so the before/after numbers come from the same script.
trunk = [("USB-A plug/receptacle contacts (2 x 15 mohm)", 0.030), ("pigtail 22 AWG, 0.28 m x 2", 2 * 0.28 * AWG[22][1]),
         ("screw terminal J1 (2 contacts)", 0.010), ("F1 %.0f A fast-blow 5 x 20 + clips" % I_FUSE, 0.012), ("bus wire + joints (incl. the J1 -> bus A tap)", 0.005)]
removed_rev_d = [("switch loop 22 AWG, 2 x 0.30 m (carrier -> top cap -> carrier)", 2 * 0.30 * AWG[22][1]), ("KCD11 contact", 0.020),
                 ("J2 2.54 mm screw terminal, 2 clamps", 0.020)]
R_trunk = sum(r for _, r in trunk)
R_old = R_trunk + sum(r for _, r in removed_rev_d)
for lab, r in trunk:
    print("  %-62s %6.1f mohm" % (lab, r * 1e3))
I_CAP = CAP_A + I_ESP      # 2.72 A at the cap
for I in (0.9, 2.12, I_CAP):
    print("  total %.0f mohm -> %.0f mV at %.2f A (bus at %.2f V from a %.2f V port)" % (R_trunk * 1e3, R_trunk * I * 1e3, I, V_PORT - R_trunk * I, V_PORT))
for lab, r in removed_rev_d:
    print("  removed in rev d: %-51s %6.1f mohm" % (lab, r * 1e3))
for I in (0.9, I_CAP):
    print("  before rev d (with the switch loop): %.0f mohm -> %.0f mV at %.2f A (bus %.2f V); rev d gains %.0f mV" % (
        R_old * 1e3, R_old * I * 1e3, I, V_PORT - R_old * I, (R_old - R_trunk) * I * 1e3))
print("  F1 %.0f A fast-blow at %.2f A: %.0f %% of rating (3 A would have been %.0f %%); I2t ~ 18 A2s vs the 0.06 A2s inrush; clears a hard short, NOT a 4.5 A SCP fault (the bank's own protection is the first line)" % (
    I_FUSE, I_CAP, I_CAP / I_FUSE * 100, I_CAP / 3.0 * 100))
print("  a PTC instead of F1: 3 A-hold parts are 20-50 mohm (%.0f-%.0f mV); 2.5 A-hold parts derate to ~2.2 A at 40 C, below the %.2f A draw; trip = 2 x hold, so a 4.5 A-capable port may never trip one" % (0.020 * I_CAP * 1e3, 0.050 * I_CAP * 1e3, I_CAP))
V_bus = V_PORT - R_trunk * I_CAP
print("  ESP32 LDO (AMS1117-3.3 class, dropout ~1.0-1.3 V at 0.3-0.8 A): needs VIN >= ~4.4-4.6 V; bus %.2f V -> margin %.2f V. A series Schottky (0.3-0.4 V) would eat it: none on VIN." % (V_bus, V_bus - 4.5))

hdr("Feed lengths from the CAD (bottom slot of strip s at r 77, theta 15 s, z 5 -> carrier connector; + routing allowance)")
# carrier at y -19, components toward -y; connectors along the right band (x +22) and bottom band (x -22 .. +22), z 13-18
def feed_len(s, conn_xy, conn_z=15.0, allowance=0.06):
    th = math.radians(15 * s)
    p = np.array([77 * math.cos(th), 77 * math.sin(th), 5.0])
    q = np.array([conn_xy[0], -19.0, conn_z])
    r50 = np.array([50 * math.cos(th), 50 * math.sin(th), 3.0])     # radially inward under the sled plate to r 50, then to the connector
    d = np.linalg.norm(p - r50) + np.linalg.norm(r50 - q)
    return d / 1000 + allowance
feeds = {0: (-12, "J3 chain 0 (bottom band)"), 12: (12, "J4 chain 1 (bottom band)"), 3: (22, "J6"), 6: (22, "J7"), 9: (22, "J8"), 15: (22, "J9"), 18: (22, "J10"), 21: (22, "J11")}
print("  strip  theta  path+60mm  cut length (round up to 50 mm)")
cut = {}
for s, (x, j) in feeds.items():
    L = feed_len(s, (x, -19))
    cut[s] = math.ceil(L * 20) / 20
    print("  %5d  %5d  %6.0f mm  %4.0f mm  %s" % (s, 15 * s, L * 1e3, cut[s] * 1e3, j))
print("  jumper: chord between neighbouring strip ends at r 77.6 = %.1f mm; + 2 x (1.6 wall + 6 mm inside + 4 mm stripped) -> cut 45 mm" % (2 * 77.6 * math.sin(math.radians(7.5))))

hdr("Chain copper network: node voltages with 8 feeds vs 4 feeds (nodal analysis, uniform load, one chain at the 1.0 A cap)")
# nodes: B_s (bottom end) and T_s (top end) of strips s = 0..11. Strip resistor between B_s and T_s (5 V + GND rails lumped as one
# round-trip resistance). Jumpers: T_s-T_{s+1} for even s, B_s-B_{s+1} for odd s. Loads: half of each strip's share at each end.
R_s = 2 * R_STRIP_RAIL * STRIP_L
R_j = 2 * 0.045 * AWG[28][1]
def solve(feed_strips, I_chain=1.0, feed_awg=26, R_bus=0.03):
    n = 24
    Gm = np.zeros((n, n)); Iv = np.zeros(n)
    B = lambda s: 2 * s
    T = lambda s: 2 * s + 1
    def add(a, b, R):
        g = 1 / R; Gm[a, a] += g; Gm[b, b] += g; Gm[a, b] -= g; Gm[b, a] -= g
    for s in range(12):
        add(B(s), T(s), R_s)
        if s < 11:
            add(T(s), T(s + 1), R_j) if s % 2 == 0 else add(B(s), B(s + 1), R_j)
    for s in range(12):
        Iv[B(s)] -= I_chain / 12 / 2; Iv[T(s)] -= I_chain / 12 / 2
    Rf = {}
    for s in feed_strips:
        Rf[s] = 2 * cut.get(s, 0.30) * AWG[feed_awg][1] + R_bus
        Gm[B(s), B(s)] += 1 / Rf[s]; Iv[B(s)] += V_bus / Rf[s]
    V = np.linalg.solve(Gm, Iv)
    return V, {s: (V_bus - V[B(s)]) / Rf[s] for s in feed_strips}
for name, fs in (("8 feeds (0,3,6,9 per chain)", [0, 3, 6, 9]), ("4 feeds (chain ends 0 and 11)", [0, 11])):
    V, If = solve(fs)
    print("  %-32s min node %.3f V (drop %.0f mV below the bus at %.2f V); feed currents: %s" % (
        name, V.min(), (V_bus - V.min()) * 1e3, V_bus, ", ".join("s%d %.2f A" % (s, i) for s, i in If.items())))
V, If = solve([0, 3, 6, 9], I_chain=0.38)
print("  8 feeds at the dog's realistic 0.38 A per chain: drop %.0f mV" % ((V_bus - V.min()) * 1e3))
print("  strip copper: R_s = %.3f ohm round trip per strip (%.2f ohm/m per rail, assumption - measure); jumper %.3f ohm" % (R_s, R_STRIP_RAIL, R_j))

hdr("Signal lines at 8 MHz")
t_bit = 1 / 8e6
print("clock period %.0f ns, half period %.1f ns; one-way delay of a 0.30 m lead at 5 ns/m = %.1f ns (shorter than the driver's 2-4 ns rise time only by 2x: terminate)" % (t_bit * 1e9, t_bit / 2 * 1e9, 0.3 * 5))
Z0, Rout = 100.0, 25.0
C_load = 25e-12
for Rs in (33, 68, 100, 330):
    tau = (Rs + Rout) * C_load
    print("  R_s = %3d ohm: source match %s (Z0 ~ %.0f ohm twisted pair, R_out ~ %.0f ohm); RC with %.0f pF = %.1f ns, 10-90 %% rise %.1f ns (budget: < 15 ns)" % (
        Rs, "OK" if 50 <= Rs + Rout <= 130 else "no", Z0, Rout, C_load * 1e12, tau * 1e9, 2.2 * tau * 1e9))
print("  jumpers (45 mm): delay 0.2 ns, C ~2 pF -> no termination; the SK9822 re-drives CO/DO at every LED, so each hop is point-to-point")
print("  ribbon crosstalk over 0.30 m, adjacent 28 AWG at 1.27 mm: C_m ~ 15 pF -> a few hundred mV on DATA at the clock edge = the sampling instant -> keep a GND conductor between CLK and DATA on the chain-start leads (twisted pairs CLK+GND, DATA+GND)")

hdr("Bulk capacitance, wire inductance, inrush")
L_loop = 1.0e-6   # ~0.8 m of untwisted 22 AWG loop, ~1.2 uH/m
for dI, dt in ((1.0, 1e-6), (2.0, 1e-6)):
    print("  LED step %.1f A in %.0f us through %.1f uH of trunk with NO local cap: V = L di/dt = %.1f V (the bus would collapse); with a local cap the trunk current ramps at L/R = %.0f us" % (
        dI, dt * 1e6, L_loop * 1e6, L_loop * dI / dt, L_loop / R_trunk * 1e6))
for C in (1000e-6, 2000e-6):
    for dI, t_resp in ((1.0, 100e-6), (2.0, 200e-6)):
        print("  C = %4.0f uF: a %.1f A step held for the bank's %.0f us response droops %.0f mV" % (C * 1e6, dI, t_resp * 1e6, dI * t_resp / C * 1e3))
C_tot = 2000e-6
for I_lim in (3.0, 4.5):
    print("  inrush: %.0f uF from 0 to 5 V at a %.1f A port limit takes %.1f ms (ideal peak V/R = %.0f A, never reached); energy %.0f mJ" % (
        C_tot * 1e6, I_lim, C_tot * 5 / I_lim * 1e3, 5 / R_trunk, 0.5 * C_tot * 25 * 1e3))
print("  cap ripple current: column-rate steps are ~20 kHz bursts; a 1000 uF / 10 V general-purpose electrolytic (ripple ~1 A) is fine; 105 C low-ESR preferred")

hdr("Hall sensor")
R_pu, C_f = 10e3, 1e-9
v_mag = w * 0.042
print("A3144: VCC 5 V (4.5-24 V), open-collector 25 mA max; pull-up %.0f k to 3.3 V sinks %.2f mA; RC filter %.0f k x %.0f nF = %.0f us" % (R_pu / 1e3, 3.3 / R_pu * 1e3, R_pu / 1e3, C_f * 1e9, R_pu * C_f * 1e6))
print("  magnet passes the sensor at v = w r = %.2f m/s (225 rpm); the field exceeds B_op over ~10 mm of travel -> pulse ~%.0f ms, >> 10 us filter, << %.0f ms quarter-rev lockout" % (v_mag, 0.010 / v_mag * 1e3, 60 / 225 / 4 * 1e3))
print("  edge timing: the open-collector pulls down through ~100 ohm -> fall time %.1f us; 20 us of total jitter = %.3f deg = %.3f column at M 96" % (100 * C_f * 1e6 * 2.2, 20e-6 * 225 / 60 * 360, 20e-6 * 225 / 60 * 96))

hdr("Thermal")
P_led = 5 * CAP_A
print("LEDs at the %.1f A cap: %.0f W into the strips, ~55 %% of it heat in the driver ICs (VDD - V_f) = %.1f W over 24 strips on a spinning 0.13 m2 tube in a %.1f m/s flow (h ~ 15 W/m2K): wall rise ~%.0f K" % (
    CAP_A, P_led, 0.55 * P_led, w * 0.08, 0.55 * P_led / (15 * 0.13)))
print("bank boost at 88 %%: %.1f W inside the bank; ~0.02 m2 of case in still rotor air (h ~ 5): ~%.0f K rise -> warm, fine (< 45 C)" % (P_led * 0.12 / 0.88, P_led * 0.12 / 0.88 / (5 * 0.02)))
print("ESP32 LDO: (%.1f - 3.3) V x 0.15 A = %.2f W; 74AHCT125 at 8 MHz driving 25 pF x 4: < 10 mW" % (V_bus, (V_bus - 3.3) * 0.15))

hdr("Base (12 V)")
print("225 rpm on a 600 rpm (12 V) motor: ~%.0f %% of no-load speed -> PWM duty ~40-45 %% plus load; a 12 V 2 A adapter covers the 1.65 A stall (ramp the knob)" % (225 / 600 * 100))
print("jack/PWM/motor wiring 22 AWG: 0.6 A rated / 1.65 A stall -> 2 x 0.2 m x 53 mohm x 1.65 A = %.0f mV at stall, nothing" % (2 * 0.2 * 0.053 * 1.65 * 1e3))
print("motor terminal cap 100 nF ceramic (X7R, 50 V) + optional 2 x 47 nF to the can: brush-noise snubber; the rotor shares no conductor with the base, so the only coupling is radiated")

hdr("Balance: wire masses")
items = [("2 chain-start leads (6 x 28/26 AWG, 0.30 m)", 2, 0.30 * (4 * AWG[28][2] + 2 * AWG[26][2]), 40),
         ("6 feeds (2 x 26 AWG, 0.30 m)", 6, 0.30 * 2 * AWG[26][2], 40), ("22 jumpers (4 x 28 AWG ribbon, 45 mm)", 22, 0.045 * 4 * AWG[28][2], 78),
         ("hall lead (3 x 28 AWG, 0.12 m)", 1, 0.36 * AWG[28][2], 30)]     # rev d: the switch loop (2 x 22 AWG, 0.30 m, 2.3 g) is gone
for lab, n, m, r in items:
    print("  %-48s %2d x %.2f g at r ~%d mm -> each %.0f g mm; placed symmetrically -> net ~0" % (lab, n, m, r, m * r))
print("  worst asymmetry if one feed were missing: %.0f g mm vs the 259 g mm G6.3 budget -> route all eight alike, then trim with nuts" % (0.30 * 2 * AWG[26][2] * 40))

hdr("Measurement notes")
print("cheap 24 MS/s logic analyser: 3 samples per 8 MHz clock period -> edges aliased; decode at 2-4 MHz test speed, or use the Rigol DHO814 (1.25 GS/s): probe CLK/DATA at strip 0's pads with a ground spring")
print("multimeter current: 10 A range in series with the J1 5 V lead; expect: all blank %.2f A, dog %.2f A, dense text %.2f A" % (N * I_DARK + I_ESP, 0.889, min(0.30 * N * I_CH_FULL + N * I_DARK, CAP_A) + I_ESP))
