"""Numbers for docs/2026-11-02-v2-24-strips-tie-rods.md (SI units).

Run:  py calc/v2_calc.py
v2 design (Brian, 2026-11-02): 160 mm column, 24 straight 60/m strips in 3 interleave sets x 8 (15 deg apart), 336 LEDs,
42 rows at 5.556 mm, 4 x M3 steel tie rods clamping the caps. Final LED choice (Brian, later on 2026-11-02): **SK9822**
(APA102-class, clock + data, 12 mm black PCB) on two 12-strip serpentine chains driven by the ESP32's two hardware SPI hosts;
the WS2812B / 8-RMT-chain numbers are kept for comparison. Rotor mass / inertia / unbalance come from the Fusion model
(fusionclaude/scripts/082_pov2_checks.py); everything else is derived here. feasibility_calc.py still documents v1.
"""
import math

G = 9.81
RHO_AIR, NU_AIR = 1.2, 1.5e-5
PITCH = 1000 / 60                      # mm, 60 LED/m
LED_BODY = 5.0                         # mm
T_LED = 30e-6                          # s per LED (24 bit @ 800 kbit/s)
RESETS = (50e-6, 280e-6)               # WS2812B original / V5 latch
# --- geometry (lib/povlib.py D) ---
D_TUBE, H_TUBE, R_TUBE = 160.0, 250.0, 80.0
N_STRIP, N_SET, N_LED = 24, 3, 14
ROWS, ROW_PITCH = N_SET * N_LED, PITCH / N_SET
CIRC = math.pi * D_TUBE
N_CHAIN, LEDS_PER_CHAIN = N_STRIP // N_SET, N_SET * N_LED
# --- Fusion-measured rotor (082_pov2_checks, materials: PLA tube/top cap, PET-CF hub/sled, 304 rods) ---
M_ROTOR = 0.969                        # kg (952 g modelled + 18 g wiring/inserts/glue), SK9822 12 x 0.46 mm strips; WS2812B 10 mm: 949 g
I_ZZ = 3.70e-3                         # kg m^2 (WS2812B version 3.55e-3)
U_DESIGN = 53.0                        # g mm residual (board stack vs cradle offset etc.)
M_BASE = 0.664                         # kg
M_STRIP = 6.7e-3                       # kg per 14-LED 12 mm SK9822 strip (10 mm WS2812B: 5.8 g)
M_ROD = 14.3e-3                        # kg per M3 x 257 rod (304)
# --- motor (Copkim JGB37-520 600 rpm kit; alt ZVKV 0.5 kgf cm) ---
TAU = {"Copkim 0.28 kgf cm": 0.28 * G * 0.01, "ZVKV 0.5 kgf cm": 0.5 * G * 0.01}    # N m rated (27.5 / 49 mN m)
# --- power ---
I_PORT = 2.4                           # A, INIU BI-B61 USB-A at 5 V per the 2026-11-01 listing check (box may say 3 A)
I_PIGTAIL = 3.0                        # A, 22 AWG USB-A pigtail rating
CAP_A = 2.0                            # FastLED setMaxPowerInVoltsAndMilliamps(5, 2000) - includes the ~1 mA/LED dark current
WH_USABLE = 30.0                       # Wh delivered at 5 V from the 37 Wh (10 Ah x 3.7 V) bank, ~81 % (boost + cell losses)


def hdr(t):
    print("\n=== %s ===" % t)


def line_time(n, reset):
    return n * T_LED + reset


def drag_torque(w, R=R_TUBE / 1000, H=H_TUBE / 1000, rough=3.0):
    """Theodorsen-Regier skin friction on the drum (x3 for the ribbed surface) + two laminar end discs."""
    v = w * R
    Re = v * R / NU_AIR
    Cf = 0.01
    for _ in range(50):
        Cf = (1 / (-0.6 + 4.07 * math.log10(Re * math.sqrt(Cf)))) ** 2
    tau_side = 0.5 * RHO_AIR * v ** 2 * Cf * (2 * math.pi * R * H) * R
    Red = w * R ** 2 / NU_AIR
    tau_disc = 2 * 0.5 * RHO_AIR * w ** 2 * R ** 5 * (3.87 / math.sqrt(Red)) * 0.5
    return rough * tau_side + tau_disc


hdr("Geometry: 24 strips, 3 sets, 42 rows")
z_a = (H_TUBE - (13 * PITCH + 2 * ROW_PITCH)) / 2
print("row pitch p/3 = %.3f mm, %d rows span %.1f mm; set A LED0 at z %.2f, B %.2f, C %.2f (centred in the %g tube, %.1f mm margins)" % (
    ROW_PITCH, ROWS, 13 * PITCH + 2 * ROW_PITCH, z_a, z_a + ROW_PITCH, z_a + 2 * ROW_PITCH, H_TUBE, z_a - LED_BODY / 2))
print("strip ends: A %.2f..%.2f, B %.2f..%.2f, C %.2f..%.2f -> 7 mm skirts cover the outermost ends only" % tuple(
    v for k in range(3) for v in (z_a - PITCH / 2 + k * ROW_PITCH, z_a - PITCH / 2 + k * ROW_PITCH + N_LED * PITCH)))
print("strip arc at r80: %.2f mm per 15 deg; rail pair 13.0 mm wide -> %.2f mm between neighbouring pairs; strips cover %.0f %% of the circumference" % (
    math.radians(15) * R_TUBE, math.radians(15) * R_TUBE - 13.0, N_STRIP * 10 / CIRC * 100))
print("reel: %d x %.1f mm = %.2f m of the 5 m black reel (v1 used 1.87 m)" % (N_STRIP, N_LED * PITCH, N_STRIP * N_LED * PITCH / 1000))

hdr("Refresh, columns and the data budget (8 chains x 42 LEDs)")
K = N_STRIP // N_SET
for reset in RESETS:
    print("chain update: 42 x 30 us + %.0f us reset = %.0f us" % (reset * 1e6, line_time(LEDS_PER_CHAIN, reset) * 1e6))
print("refresh = K x f_rot with K = %d strips per set: 225 rpm -> %.0f Hz, 240 -> %.0f, 270 -> %.0f, 300 -> %.0f, 450 -> %.0f" % (
    K, *(K * r / 60 for r in (225, 240, 270, 300, 450))))
print("%5s %5s | %4s %6s %6s | %8s %8s %8s | %6s %6s" % ("rpm", "Hz", "M", "px w", "w/h", "t_col us", "1-batch", "2-batch", "maxM50", "maxM280"))
for rpm in (225, 240, 270, 300):
    f = rpm / 60
    for M in (72, 80, 90, 96, 120):
        tcol = 1 / (f * M)
        t1 = line_time(LEDS_PER_CHAIN, 280e-6)
        t2 = 2 * t1
        print("%5d %5.0f | %4d %6.2f %6.2f | %8.0f %+7.0f%% %+7.0f%% | %6.0f %6.0f" % (
            rpm, K * f, M, CIRC / M, CIRC / M / ROW_PITCH, tcol * 1e6, (1 - t1 / tcol) * 100, (1 - t2 / tcol) * 100,
            1 / (f * line_time(LEDS_PER_CHAIN, 50e-6)), 1 / (f * t1)))
print("integer columns per 15 deg strip step: M = 72 (3), 96 (4), 120 (5); square pixels at M = %.1f" % (CIRC / ROW_PITCH))
print("RECOMMENDED: 225 rpm (30 Hz, shutter 1/30), M = 96 -> pixels %.2f x %.3f mm (aspect %.2f), 42 x 96 = %d px, t_col %.0f us vs %.0f us update (%.0f %% margin)" % (
    CIRC / 96, ROW_PITCH, CIRC / 96 / ROW_PITCH, ROWS * 96, 1e6 / (3.75 * 96), line_time(42, 280e-6) * 1e6, (1 - line_time(42, 280e-6) * 3.75 * 96) * 100))
print("  if the RMT driver batches 4+4 (show() ~3.1 ms): M = 72 at 225 rpm (%.0f %% margin) or the I2S parallel driver" % ((1 - 2 * line_time(42, 280e-6) * 3.75 * 72) * 100))
print("  viewing (no camera): 270 rpm = 36 Hz, M = 96 still has %.0f %% margin single-batch" % ((1 - line_time(42, 280e-6) * 4.5 * 96) * 100))
for M in (72, 96):
    fb = N_STRIP * N_LED * M * 3
    print("frame M=%d: %d B = %.1f KiB; heap 300 KB holds %d, LittleFS 1.5 MB holds %d; LED data rate at 225 rpm %.2f Mbit/s" % (
        M, fb, fb / 1024, 300e3 // fb, 1.5e6 // fb, N_STRIP * N_LED * 24 * 3.75 * M / 1e6))
print("LED body 5 mm = %.2f columns at M 96; smear per column (arc + body) %.1f mm" % (LED_BODY / (CIRC / 96), CIRC / 96 + LED_BODY))
print("hall jitter 20 us at 225 rpm = %.3f deg; strip phase offset = 4 columns per strip, 12 per chain sector (45 deg)" % (20e-6 * 3.75 * 360))

hdr("SK9822 (final): two 12-strip chains on VSPI (DATA 23 / CLK 18) and HSPI (DATA 13 / CLK 14)")
N_CH, LEDS_CH = 2, 12 * N_LED
def sk_bits(n):                        # 32-bit start frame + 32 bits per LED + end frame of ceil(n/2) bits rounded up to bytes
    return 32 + 32 * n + 8 * math.ceil(n / 16)
for f_spi in (8e6, 10e6, 20e6):
    t_ch = sk_bits(LEDS_CH) / f_spi
    t_one = sk_bits(N_STRIP * N_LED) / f_spi
    print("SPI %.0f MHz: per chain %d LEDs = %d bits = %.2f ms (both chains in parallel); all 336 on one bus %.2f ms" % (
        f_spi / 1e6, LEDS_CH, sk_bits(LEDS_CH), t_ch * 1e3, t_one * 1e3))
t_ch = sk_bits(LEDS_CH) / 8e6
print("%5s %5s | %4s %6s | %8s %8s %8s" % ("rpm", "Hz", "M", "px w", "t_col us", "margin", "maxM@8MHz"))
for rpm in (225, 270, 300):
    f = rpm / 60
    for M in (96, 120, 144):
        tcol = 1 / (f * M)
        print("%5d %5.0f | %4d %6.2f | %8.0f %+7.0f%% %8.0f" % (rpm, K * f, M, CIRC / M, tcol * 1e6, (1 - t_ch / tcol) * 100, 1 / (f * t_ch)))
print("LED body 5 mm = %.2f columns at M 96, %.2f at M 120: beyond ~M 100 the package, not the data, limits horizontal resolution -> keep M = 96" % (
    LED_BODY / (CIRC / 96), LED_BODY / (CIRC / 120)))
print("PWM: SK9822 ~4.7 kHz = %.0f cycles per 2.78 ms column (WS2812B 0.4-2 kHz = 1-6): mid-tones render as solid arcs; 5-bit global brightness (31 steps) dims without losing colour depth" % (4.7e3 * 2.778e-3))
print("level shifting: 2 x (CLK + DATA) = 4 lines -> ONE 74AHCT125 (the second chip of the pair is spare); 33-100 R series optional at 8 MHz")
print("wiring: 22 four-wire jumpers (~25 mm, 28 AWG ribbon), 8 bottom feeds (power at every 3rd strip, 0.25 A each at the 2 A cap; clock + data ride on feeds 0 and 12), 48 wall slots 7 x 5")
print("copper: feed every 3 strips -> longest path 1.5 strips = 0.35 m at 0.25 A x 0.6 ohm/m = %.0f mV; SK9822 is constant-current so a few tens of mV cost nothing" % (0.25 * 0.35 * 0.6 * 1e3))
print("strip mass: 12 mm PCB ~5.3 g + 1.4 g LEDs = 6.7 g per strip (10 mm WS2812B 5.8 g) -> +22 g, +1.4e-4 kg m2")
print("current: SK9822 ~20 mA per channel and ~1 mA idle per LED like WS2812B -> the power table below stands; the 5-bit global brightness scales LED current linearly")
print("firmware: FastLED.addLeds<SK9822, DATA, CLK, BGR, DATA_RATE_MHZ(8)>() x2 (hardware SPI when the pins are a host's defaults: VSPI 23/18, HSPI 13/14); odd strips index-reversed; hall on GPIO 27 unchanged")
print("reels: 24 x 233.3 mm = 5.6 m of the 2 x 5 m SK9822 (owned + B07BPYFB28); 4.4 m spare")

hdr("Rotor dynamics (Fusion masses)")
for rpm in (225, 270, 300, 450):
    w = 2 * math.pi * rpm / 60
    e = 6.3 / w                                   # mm  (ISO 21940: G [mm/s] = e [mm] x omega [rad/s])
    U_allow = M_ROTOR * 1e3 * e                   # g mm
    KE = 0.5 * I_ZZ * w ** 2
    td = drag_torque(w)
    a_rim = w ** 2 * R_TUBE / 1000
    print("%3d rpm: w %.1f rad/s | G6.3 e %.0f um -> U <= %.0f g mm (design %.0f = %.0f %%) | KE %.2f J | drag %.2f mN m (%.3f W) | %.1f g at r80" % (
        rpm, w, e * 1e3, U_allow, U_DESIGN, 100 * U_DESIGN / U_allow, KE, td * 1e3, td * w, a_rim / G))
    for name, tau in TAU.items():
        print("      spin-up 0->%d rpm on %s (%.0f mN m): %.1f s; steady torque margin %.0fx" % (rpm, name, tau * 1e3, I_ZZ * w / (tau - td), tau / td))
w = 2 * math.pi * 225 / 60
print("225 rpm centrifugal loads: strip %.1f g -> %.2f N (%.2f kPa on its 23.3 cm2 adhesive); each rail pair sees the same %.2f N; one missing strip = %.0f g mm = %.1fx the G6.3 limit" % (
    M_STRIP * 1e3, M_STRIP * w ** 2 * 0.08, M_STRIP * w ** 2 * 0.08 / (233.3e-3 * 10e-3) / 1e3, M_STRIP * w ** 2 * 0.08,
    M_STRIP * 1e3 * 80, M_STRIP * 1e3 * 80 / (M_ROTOR * 1e3 * 6.3 / w)))
print("rotor weight on the gearbox bearing %.1f N; tipping: 1 N residual at CG height %.0f mm = %.2f N m vs restoring %.2f N m (1.6 kg on a 180 mm footprint)" % (
    M_ROTOR * G, 100 + 9.5, 1 * 0.11, (M_ROTOR + M_BASE) * G * 0.09))
print("PLA hoop stress at 225 rpm: %.1f kPa (surface speed %.2f m/s); at 450 rpm 17.6 kPa" % (1240 * w ** 2 * 0.08 ** 2 / 1e3, w * 0.08))

hdr("Tie rods: 4 x M3 x 256.8 mm 304 stainless at r 60, nyloc each end")
A_rod = math.pi * 1.5e-3 ** 2
A_ts = 5.03e-6                                     # tensile stress area M3
EI = 200e9 * math.pi * 1.5e-3 ** 4 / 4
mu = 7900 * A_rod
L = 0.2568
F_snug = 150.0                                     # N per rod, finger-tight + 1/8 turn (~0.1 N m)
k_rod = 4 * 200e9 * A_rod / L
tube_end = math.pi * (0.08 ** 2 - 0.0784 ** 2)
k_tube = 3.5e9 * tube_end / 0.25
print("rod mass %.1f g each, %.0f g for 4 (+ 8 nylocs ~3 g); I contribution 4 x m r^2 = %.2e kg m2 = %.0f %% of I_zz" % (
    M_ROD * 1e3, 4 * M_ROD * 1e3, 4 * M_ROD * 0.06 ** 2, 100 * 4 * M_ROD * 0.06 ** 2 / I_ZZ))
print("preload %.0f N/rod (T ~ 0.2 F d = %.2f N m): rod stress %.0f MPa (304 yield ~205); nut face %.1f mm2 -> %.1f MPa on the printed floor (keep < 25 MPa for PLA creep)" % (
    F_snug, 0.2 * F_snug * 0.003, F_snug / A_ts / 1e6, 0.866 * 5.5 ** 2 - math.pi * 1.7 ** 2, F_snug / (0.866 * 5.5 ** 2 - math.pi * 1.7 ** 2)))
sig_cr = 0.3 * 3.5e9 * 1.6e-3 / (0.08 * math.sqrt(3 * (1 - 0.36 ** 2)))
print("tube end ring %.0f mm2 under 4 x %.0f N = %.2f MPa; thin-shell axial buckling (0.3 knockdown) %.1f MPa -> factor %.0f" % (
    tube_end * 1e6, F_snug, 4 * F_snug / tube_end / 1e6, sig_cr / 1e6, sig_cr * tube_end / (4 * F_snug)))
for dT in (10, 20):
    dL = (70e-6 - 17e-6) * 0.25 * dT                 # PLA grows more than steel
    F = dL / (1 / k_rod + 1 / k_tube)
    print("warm-up %+d K: PLA tube grows %.2f mm more than the rods -> clamp force %+.0f N total (%+.0f N/rod) on top of the preload; cold = looser. Snug only; nylocs retain regardless; optional M3 wave washers under the top nuts" % (
        dT, dL * 1e3, F, F / 4))
f_beam = 22.4 / (2 * math.pi * L ** 2) * math.sqrt(EI / mu)
f_string = math.sqrt(F_snug / mu) / (2 * L)
print("rod lateral natural frequency: clamped beam %.0f Hz, +tension -> ~%.0f Hz, vs 3.75-7.5 Hz rotation: no resonance" % (f_beam, math.hypot(f_beam, f_string)))
q = M_ROD * w ** 2 * 0.06 / L
print("rod centrifugal bow at 225 rpm: %.2f N distributed -> %.3f mm mid-span (fixed ends, no tension credit); at 450 rpm x4" % (q * L, q * L ** 4 / (384 * EI) * 1e3))
print("nyloc reuse: prevailing torque is specified for ~5 reinstallations (ISO 2320) -> keep spares for the top cap, or thumb nuts on top")

hdr("Power and battery (336 LEDs, 5 V)")
N = N_STRIP * N_LED
for lab, frac in (("sparse text (15 % lit, one channel)", 0.15), ("dense text (30 % lit)", 0.30), ("all white 255 (never)", 1.0 * 3)):
    i_led = N * frac * 0.020
    i_tot = i_led + N * 0.001 + 0.12
    i_run = min(i_tot - 0.12, CAP_A) + 0.12
    P = i_run * 5
    print("%-38s LEDs %.2f A + dark %.2f A + ESP32 0.12 A = %.2f A -> after the %.1f A cap: %.2f A, %.1f W, ~%.1f h on %.0f Wh" % (
        lab, i_led, N * 0.001, i_tot, CAP_A, i_run, P, WH_USABLE / P, WH_USABLE))
print("port limit %.1f A: cap %.1f A + ESP32 0.12 A = %.2f A (%.0f %% margin); pigtail 22 AWG %.0f A OK; per chain at the cap %.2f A, per feed (2 per chain) %.3f A" % (
    I_PORT, CAP_A, CAP_A + 0.12, (1 - (CAP_A + 0.12) / I_PORT) * 100, I_PIGTAIL, CAP_A / N_CHAIN, CAP_A / N_CHAIN / 2))
print("v1 for comparison: 112 LEDs, 0.90 A typical, cap 2.5 A; v2 triples the LED count so brightness is now port-limited, not LED-limited")
r22, r24, r26 = 0.053, 0.084, 0.134                # ohm/m
print("wire gauge: trunk pigtail->switch->bus 22 AWG, 0.8 m loop at %.1f A = %.0f mV; 16 power branches 24 AWG (%.3f A, 0.2 m: %.1f mV) or the owned 22 AWG; 8 data lines 26-28 AWG with the 330 R at the carrier; 16 jumpers 28 AWG 3-wire ribbon ~30 mm" % (
    CAP_A + 0.12, (CAP_A + 0.12) * 0.8 * r22 * 1e3, CAP_A / 16, CAP_A / 16 * 0.2 * r24 * 1e3))
print("strip copper: 0.3 A per chain over 0.7 m of 60/m strip (~0.3 ohm/m per rail) = %.0f mV worst case without the C-bottom feed; with it %.0f mV" % (
    0.25 * 0.7 * 0.6 * 1e3, 0.25 * 0.233 * 0.6 * 1e3))

hdr("Filming")
print("hero: 30p, 1/30 s at 225 rpm (K=8 -> 30 Hz); 24p -> 180 rpm; fast-shutter reveal at 1/2000: surface moves %.2f mm" % (w * 0.08 * 1e3 / 2000))
print("mass check vs v1: rotor %.0f g (v1 781), I %.2f vs 2.72 mN m s2 (+%.0f %%); KE at 225 rpm %.2f J vs 3.0 J at 450 (v1)" % (
    M_ROTOR * 1e3, I_ZZ * 1e3, (I_ZZ / 2.72e-3 - 1) * 100, 0.5 * I_ZZ * w ** 2))
