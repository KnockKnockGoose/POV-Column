"""Numbers for docs/2026-11-01-feasibility.md, revision 2026-11-01b (SI units).

Run:  py calc/feasibility_calc.py
Chosen design: 160 mm column, 8 straight WS2812B strips (2 interleave sets x 4), 450 RPM, 72 columns/rev.
Also prints the 16-strip v2 variant and the original 80 mm / 4-strip / 900 RPM design (appendix).
"""
import math

G = 9.81
RHO_PLA = 1240.0          # kg/m^3
RHO_AIR, NU_AIR = 1.2, 1.5e-5
PITCH = 1000 / 60         # mm, 60 LED/m  (11.67 mm is the GAP between 5 mm packages, not the pitch)
LED_BODY = 5.0            # mm
STRIP_KG_M = 0.025        # kg/m, bare 60/m strip
T_LED = 30e-6             # s per LED (24 bit @ 800 kbit/s)
RESET = (50e-6, 280e-6)   # s, WS2812B original / -V5 latch


def hdr(t):
    print(f"\n=== {t} ===")


def line_time(n, reset=280e-6):
    return n * T_LED + reset


def drag(R, H, w, rough=3.0):
    """Skin friction on a rotating cylinder (Theodorsen-Regier) + 2 laminar end discs (von Karman)."""
    v = w * R
    Re = v * R / NU_AIR
    Cf = 0.01
    for _ in range(50):
        Cf = (1 / (-0.6 + 4.07 * math.log10(Re * math.sqrt(Cf)))) ** 2
    tau_side = 0.5 * RHO_AIR * v**2 * Cf * (2 * math.pi * R * H) * R
    Red = w * R**2 / NU_AIR
    Cm = 3.87 / math.sqrt(Red)
    tau_disc = 2 * 0.5 * RHO_AIR * w**2 * R**5 * Cm * 0.5
    tau = rough * tau_side + tau_disc
    return dict(v=v, Re=Re, Cf=Cf, tau_side=tau_side, tau_disc=tau_disc, tau=tau, P=tau * w)


def power(N, bank_wh=3.35 * 3.6, shield_wh=2 * 3.0 * 3.6, cap_A=2.5, eta=0.85):
    typ = N * 0.30 * 0.020 + N * 0.001 + 0.12          # A @ 5 V: 30 % lit, one channel, + quiescent + ESP32
    P = typ * 5
    return dict(typ_A=typ, typ_W=P, max_A=N * 0.060, cap_A=cap_A,
                bank_h=bank_wh * eta / P, bank_cap_h=bank_wh * eta / (min(cap_A, 2.4) * 5),
                shield_h=shield_wh * eta / P, shield_cap_h=shield_wh * eta / (cap_A * 5))


def design(name, D_mm, H_mm, wall_mm, n_strips, n_sets, rpm, M, leds_per_strip,
           cap_kg=0.045, core_kg=0.20, core_r=0.015, rails=True, lines=None, leds_per_line=None):
    hdr(name)
    R, H, t = D_mm / 2000, H_mm / 1000, wall_mm / 1000
    f = rpm / 60
    w = 2 * math.pi * f
    circ = math.pi * D_mm
    K = n_strips // n_sets                       # strips sharing each row set
    rows = n_sets * leds_per_strip
    N = n_strips * leds_per_strip
    row_pitch = PITCH / n_sets
    print(f"D {D_mm} mm, R {R*1000:.0f} mm, H {H_mm} mm, circumference {circ:.1f} mm")
    print(f"strips {n_strips} @ {360/n_strips:.1f} deg, {leds_per_strip} LED each -> N = {N} LEDs; "
          f"strip length {leds_per_strip*PITCH:.1f} mm each, total {N*PITCH/1000:.2f} m")
    print(f"strip width fraction of circumference: {n_strips*10/circ*100:.0f} % (10 mm channels)")
    print(f"rpm {rpm}, f_rot {f:.2f} rev/s, w {w:.2f} rad/s, period {1000/f:.1f} ms")
    print(f"interleave sets {n_sets}, K = {K} passes per row per rev -> refresh {K*f:.1f} Hz; "
          f"rows {rows} at {row_pitch:.2f} mm pitch")
    print(f"  lit span: LED centres over {(leds_per_strip-1)*PITCH + (n_sets-1)*row_pitch:.1f} mm, "
          f"strip ends span {leds_per_strip*PITCH + (n_sets-1)*row_pitch:.1f} mm")
    tcol = 1 / (f * M)
    arc = circ / M
    print(f"M {M} columns/rev ({360/M:.2f} deg): t_col {tcol*1e6:.0f} us, arc/column {arc:.2f} mm, "
          f"pixel aspect w/h {arc/row_pitch:.2f}; square pixels at M = {circ/row_pitch:.1f}")
    print(f"  LED body = {LED_BODY/circ*360:.2f} deg = {LED_BODY/arc:.2f} columns; "
          f"smear (arc + body) {arc+LED_BODY:.1f} mm = {(arc+LED_BODY)/arc:.2f} pitches")
    print(f"  strip phase offset per strip: {M/n_strips:.2f} columns")
    lines = lines or n_strips
    leds_per_line = leds_per_line or leds_per_strip
    for nl, label in ((leds_per_line, "per data line"), (2 * leds_per_line, "2 in series/batched")):
        for rs in RESET:
            tl = line_time(nl, rs)
            print(f"  {label:20s} n={nl:3d} reset {rs*1e6:.0f} us: t_line {tl*1e6:.0f} us, "
                  f"margin vs t_col {(1-tl/tcol)*100:+.0f} %, max cols/rev {1/(tl*f):.0f}")
    print(f"frame bytes {N*M*3} ({N*M*3/1024:.1f} KiB); 30-frame loop {30*N*M*3/1024:.0f} KiB; "
          f"frames in 300 KB heap {300e3/(N*M*3):.0f}, in 1.5 MB LittleFS {1.5e6/(N*M*3):.0f}")
    print(f"LED data rate {N*24*f*M/1e6:.2f} Mbit/s, columns/s {f*M:.0f}")
    # mass / inertia
    m_shell = RHO_PLA * math.pi * (D_mm / 1000) * H * t
    m_rails = RHO_PLA * (2 * n_strips) * H * (1.2e-3 * 1.0e-3) if rails else 0
    m_strip = n_strips * leds_per_strip * PITCH / 1000 * STRIP_KG_M
    m_caps = 2 * cap_kg
    I = (m_shell + m_rails + m_strip) * R**2 + m_caps * 0.5 * R**2 + core_kg * core_r**2
    m_tot = m_shell + m_rails + m_strip + m_caps + core_kg + 0.02
    vol = (m_shell + m_rails) / RHO_PLA * 1e9
    print(f"mass: shell {m_shell*1e3:.0f} g, rails {m_rails*1e3:.0f} g, strips {m_strip*1e3:.0f} g, "
          f"caps {m_caps*1e3:.0f} g, core {core_kg*1e3:.0f} g, hub 20 g -> total {m_tot*1e3:.0f} g")
    print(f"tube print volume {vol/1e3:.0f} cm3 -> ~{vol/8/3600:.1f} h at 8 mm3/s effective")
    KE = 0.5 * I * w**2
    print(f"I {I:.3e} kg m2, KE {KE:.2f} J, spin-up 0->{rpm} in 3 s: {I*w/3*1e3:.1f} mN m")
    a = w**2 * R
    print(f"surface speed {w*R:.2f} m/s, centripetal {a:.0f} m/s2 = {a/G:.1f} g")
    print(f"hoop stress {RHO_PLA*w**2*R**2/1e3:.1f} kPa; strip adhesive pressure {2.5*a/1e3:.2f} kPa")
    d = drag(R, H, w)
    print(f"drag: Re {d['Re']:.2e}, Cf {d['Cf']:.4f}, side {d['tau_side']*1e3:.2f} mN m x3 rough, "
          f"discs {d['tau_disc']*1e3:.3f} mN m -> {d['tau']*1e3:.2f} mN m, {d['P']:.3f} W")
    e = 6.3e-3 / w                               # m (G = e*w in mm/s)
    U = m_tot * e
    print(f"G6.3: e {e*1e6:.0f} um, U {U*1e6:.0f} g mm; M3 nut 0.5 g at r={R*1000-8:.0f} mm = "
          f"{0.5*(R*1000-8):.0f} g mm -> {U*1e6/(0.5*(R*1000-8)):.1f} nuts")
    m1 = leds_per_strip * PITCH / 1000 * STRIP_KG_M
    print(f"one strip missing ({m1*1e3:.1f} g at R): U {m1*1e3*R*1e3:.0f} g mm = {m1*1e3*R*1e3/(U*1e6):.1f}x limit")
    for m, ecc, lab in ((0.046, 0.015, "one 18650 15 mm off-axis"), (0.1, 0.005, "100 g 5 mm off")):
        print(f"unbalance {lab}: {m*ecc*w**2:.2f} N")
    p = power(N)
    print(f"power: typ {p['typ_A']:.2f} A = {p['typ_W']:.1f} W, abs max {p['max_A']:.2f} A, cap {p['cap_A']} A")
    print(f"  1x18650 bank 12.1 Wh: typ {p['bank_h']:.1f} h, at 2.4 A {p['bank_cap_h']:.2f} h")
    print(f"  2x18650 shield 21.6 Wh: typ {p['shield_h']:.1f} h, at {p['cap_A']} A cap {p['shield_cap_h']:.2f} h")
    print(f"  cell current at cap (1S2P, 3.6 V, eta .85): {p['cap_A']*5/3.6/0.85:.1f} A total, "
          f"{p['cap_A']*5/3.6/0.85/2:.1f} A per cell; per-strip feed at cap {p['cap_A']/n_strips:.2f} A")
    print(f"filming: hero shutter 1/{K*f:.0f} s; 24p -> {24/K*60:.0f} RPM; "
          f"travel at 1/2000 {w*R*1e3/2000:.2f} mm, at 1/4000 {w*R*1e3/4000:.2f} mm")
    return dict(I=I, KE=KE, w=w, R=R)


new = design("CHOSEN: 160 mm, 8 straight strips, 2 sets, 450 RPM, M=72", 160, 250, 1.6, 8, 2, 450, 72, 14)

hdr("Chosen design: alternatives and checks")
for M in (60, 64, 72, 96, 144):
    f = 7.5
    print(f"M {M}: t_col {1e6/(f*M):.0f} us, arc {math.pi*160/M:.2f} mm, aspect {math.pi*160/M/(PITCH/2):.2f}, "
          f"/8 = {M/8:.2f}, 8-parallel margin {(1-700/(1e6/(f*M)))*100:+.0f} %, "
          f"2-batch margin {(1-1400/(1e6/(f*M)))*100:+.0f} %")
f = 7.5
for sets in (1, 2, 4):
    K = 8 // sets
    print(f"8 strips, {sets} sets: rows {sets*14} @ {PITCH/sets:.2f} mm, K {K}, refresh @450 {K*f:.0f} Hz, "
          f"RPM for 30 Hz {30/K*60:.0f}")
# what the preliminary chat number 5.9 mm came from
print(f"chat row pitch 5.9 mm = 11.8/2 (gap used as pitch); correct = {PITCH/2:.2f} mm; "
      f"square-pixel M: chat {math.pi*160/5.9:.0f} vs correct {math.pi*160/(PITCH/2):.0f}")
# helix option at R = 80 mm
R = 80.0
for M in (72, 144):
    s = (2 * math.pi / M) * R / PITCH
    a = math.asin(s)
    dz = PITCH * math.cos(a)
    print(f"helix one-column-per-LED at M={M}: alpha {math.degrees(a):.1f} deg, dz {dz:.2f} mm, "
          f"LEDs in 240 mm {240/dz:.1f}, wrap over 240 mm {240*math.tan(a):.0f} mm = "
          f"{math.degrees(240*math.tan(a)/R):.0f} deg")
# 2 x 2 wall comparison and inertia ratio
old_I = 3.4e-4
print(f"I ratio new/old (1.6 mm wall) {new['I']/old_I:.1f}")
_ = design("(check) chosen design with 2.0 mm wall", 160, 250, 2.0, 8, 2, 450, 72, 14)
# 1 kg cm in mN m
print(f"\n1 kg cm = {G*0.01*1e3:.0f} mN m")
# 5 m reel usage
print(f"reel: 8 strips use {8*14*PITCH/1000:.2f} m, 16 strips {16*14*PITCH/1000:.2f} m, of 5 m "
      f"(5 m = {5000/PITCH:.0f} LEDs)")

v2a = design("V2 VARIANT: 16 strips, 4 sets (quarter pitch), 450 RPM, M=128, I2S 16 lines",
             160, 250, 1.6, 16, 4, 450, 128, 14)
v2b = design("V2 VARIANT: 16 strips, 4 sets, 450 RPM, M=72, RMT 8 lines x 2 strips chained (28 LED)",
             160, 250, 1.6, 16, 4, 450, 72, 14, lines=8, leds_per_line=28)
v2c = design("V2 VARIANT: 16 strips, 2 sets, 225 RPM, M=72", 160, 250, 1.6, 16, 2, 225, 72, 14)

old = design("ORIGINAL (appendix): 80 mm, 4 helical strips, 2 sets, 900 RPM, M=72",
             80, 240, 2.0, 4, 2, 900, 72, 14, cap_kg=0.030, core_kg=0.13, rails=False)
a = math.asin(math.radians(5) * 40 / PITCH)
print(f"original helix alpha {math.degrees(a):.1f} deg, dz {PITCH*math.cos(a):.2f} mm, "
      f"rows pitch {PITCH*math.cos(a)/2:.2f} mm")

hdr("Chosen design: data-line options at 450 RPM, M = 72 (t_col 1852 us)")
for lab, tl in (("8 lines x 14 LED, all parallel (RMT 8 ch or I2S)", line_time(14)),
                ("8 lines, RMT sends 4 at a time (2 batches)", 2 * line_time(14)),
                ("4 lines x 28 LED (2 strips chained per pin)", line_time(28)),
                ("1 line x 112 LED (all chained / Nano bit-bang)", line_time(112))):
    print(f"{lab:50s} {tl*1e6:5.0f} us, margin {(1-tl/(1/(7.5*72)))*100:+4.0f} %, "
          f"max cols/rev {1/(tl*7.5):.0f}")
print(f"Nano SRAM 2048 B vs one frame {112*72*3} B")

hdr("Wi-Fi control (chosen design)")
typ = power(112)["typ_A"]
print(f"typical {typ:.2f} A incl. 0.12 A ESP32 average; with Wi-Fi TX peak 0.25 A: {typ-0.12+0.25:.2f} A "
      f"(cap 2.5 A, shield 3 A)")
fb = 112 * 72 * 3
print(f"frame {fb} B; upload at ~1 MB/s effective Wi-Fi {fb/1e6*1e3:.0f} ms; "
      f"16-byte header + 30 frames {16+30*fb} B; RMT symbols per 14-LED strip {14*24} = {14*24/64:.2f} x 64-symbol blocks")
rim = 0.249 + 0.006 + 0.047
print(f"rim mass {rim/0.612*100:.0f} % of rotor, rim inertia {rim*0.08**2/new['I']*100:.0f} % of I")
bits = 32 + 112 * 32 + 112 / 2
print(f"SK9822 112 LEDs on one 8 MHz SPI bus: {bits:.0f} bits = {bits/8e6*1e3:.2f} ms")
