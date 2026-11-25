"""SPI signal investigation (2026-11-04): what a 14-LED SK9822 strip reads, and draws, under simple bit-error models.
Run: py calc/spi_bit_model.py        (prints the tables quoted in docs/2026-11-04-spi-signal-investigation.md)

Calibration (Brian's rig, fresh 14-LED strip, field 4 of 31, 1 MHz, bench supply 5.00 V): dark strip 8 mA; red 40,
green 39, blue 39, white 94 mA. One LED at field 4 and full duty therefore adds R 2.29, G 2.21, B 2.21 mA.
LED current is linear in the 5-bit field: the Normand SK9822-EC20 datasheet lists 2.324 mA at 4/31, 11.62 at 20/31 and
18 at 31/31 per colour (the bench checks it with `xF40000FF`, `xF60000FF` and `g31` at 1 MHz).
(White measured 94 mA against 102 from the three single colours; the table uses the single-colour numbers.)

Two kinds of model:
  * bit-error models (below): what the first LED reads, bit by bit, with no physics;
  * lag models (read_rc, rc_section): DATA at the DI pad as a first-order lag with separate rise / fall time constants
    (rise = fall: a series resistance into the pad's capacitance; rise 5 ns, slow fall: a weak pull-down), sampled at
    mid-bit against a switching point; rc_section lists every (switching point, tau) that reproduces the 4 MHz reading
    with 1 MHz still right, and what each fit predicts for the bench steps.

The frame is the phase-0 frame: 32 zero bits, then per LED 0xE0|field, B, G, R (MSB first), 154 off slots, 24 B 0xFF,
4 B 0x00. The strip's first LED samples DATA on each CLK rising edge. The models change WHAT it reads at each clock,
never how many clocks it sees (a clock fault adds or drops bits and scrambles the colours, which the bench did not show):

  ok   reads what was sent
  F1   a 1->0 step on DATA reaches the input late, by under one bit: read[i] = sent[i] | sent[i-1]  (slow falling edge)
  F2   the same, late by one to two bits: read[i] = sent[i] | sent[i-1] | sent[i-2]
  R1   a 0->1 step late by under one bit: read[i] = sent[i] & sent[i-1]                           (slow rising edge)
  L1   every bit read one clock late (DATA delayed about a whole bit): read[i] = sent[i-1]
  E1   every bit read one clock early (the sampling edge late by about a bit): read[i] = sent[i+1]
Every LED re-drives CLK and DATA cleanly for the next one, so what the first LED reads is what all of them get.
"""

import math

DARK_MA = 8.0
N = 14
CH_MA_F4 = {"R": (40 - 8) / N, "G": (39 - 8) / N, "B": (39 - 8) / N}   # mA per LED per channel, field 4, full duty


def to_bits(byts):
    return [(b >> k) & 1 for b in byts for k in range(7, -1, -1)]


def frame_bytes(leds, slots=168):
    out = [0, 0, 0, 0]
    for k in range(slots):
        out += list(leds[k]) if k < len(leds) else [0xE0, 0, 0, 0]
    return out + [0xFF] * (4 * (slots // 32 + 1)) + [0] * 4


MODELS = {
    "ok": lambda s, i: s[i],
    "F1": lambda s, i: s[i] | s[i - 1],
    "F2": lambda s, i: s[i] | s[i - 1] | s[i - 2],
    "R1": lambda s, i: s[i] & s[i - 1],
    "L1": lambda s, i: s[i - 1],
    "E1": lambda s, i: s[i + 1],
}


def read(sent, model):
    s = [0, 0] + sent + [0, 0]                 # the line idles low before and after a frame
    f = MODELS[model]
    return [f(s, i + 2) for i in range(len(sent))]


def decode(bits, n):
    leds = []
    for k in range(n):
        o = 32 + 32 * k
        leds.append([int("".join(str(b) for b in bits[o + 8 * j:o + 8 * j + 8]), 2) for j in range(4)])
    return leds


def led_ma(h, b, g, r):
    return (h & 31) / 4 * (r / 255 * CH_MA_F4["R"] + g / 255 * CH_MA_F4["G"] + b / 255 * CH_MA_F4["B"])


def describe(h, b, g, r):
    mark = "" if h >> 5 == 7 else " (header marker not 111!)"
    parts = [f"{name} {v * 100 // 255}%" for name, v in (("R", r), ("G", g), ("B", b)) if v]
    return f"field {h & 31}: " + (", ".join(parts) if parts else "dark") + mark


def run(leds, model, n=N):
    rd = decode(read(to_bits(frame_bytes(leds)), model), n)
    return rd, DARK_MA + sum(led_ma(*x) for x in rd)


def read_rc(sent, mhz, tau_rise, tau_fall, vth, vdd=5.0):
    """Physical version of F1 / F2: DATA at the DI pad is the sent square wave through a first-order lag, with its own
    time constant for rising and falling steps (equal = a series resistance into the pad's capacitance; a short rise and
    a long fall = a driver whose pull-down is weak). SPI mode 0: DATA changes at the start of each bit (the CLK falling
    edge) and is sampled at mid-bit (the rising edge) against a switching point vth. History matters: with a slow rise,
    a lone 1 never reaches 5 V, so the fall after it ends sooner than after a run of 1s."""
    period = 1000.0 / mhz
    k = {}
    for tau in {tau_rise, tau_fall}:
        k[tau] = (math.exp(-period / 2 / tau), math.exp(-period / tau))
    v, out = 0.0, []
    for b in sent:
        target = vdd * b
        a_half, a_full = k[tau_rise] if target > v else k[tau_fall]
        out.append(1 if target + (v - target) * a_half > vth else 0)
        v = target + (v - target) * a_full
    return out


def run_rc(leds, mhz, tau_rise, tau_fall, vth, n=N):
    rd = decode(read_rc(to_bits(frame_bytes(leds)), mhz, tau_rise, tau_fall, vth), n)
    return rd, DARK_MA + sum(led_ma(*x) for x in rd)


def rc_section():
    """Which lag at the DI pad reproduces 174-178 mA at 4 MHz with 1 MHz still right, and what each fit predicts."""
    red4 = [(0xE4, 0, 0, 0xFF)] * N
    n7 = lambda led: [led] * 7 + [(0xE0, 0, 0, 0)] * 7
    plan = [("1 g4", (0xE4, 0, 0, 0xFF)), ("g1", (0xE1, 0, 0, 0xFF)), ("2 g4", (0xE4, 0, 0xFF, 0)), ("xF6", (0xF6, 0, 0, 0xFF))]
    print()
    print("Lag models at the DI pad (fits: 14-LED red at field 4 reads 165-190 mA at 4 MHz and 40 mA at 1 MHz).")
    print("Per fit: tau range | 14-LED red at 4 MHz | n7 at 4 MHz: 1 g4, g1, 2 g4, xF6 (mA, what LED 1 reads) | n7 red g4 at 2 / 3 / 5 / 8 MHz")
    for name, sym, vths in (("series R (rise = fall)", True, (1.5, 1.8, 2.0, 2.2, 2.5)), ("weak pull-down (rise 5 ns)", False, (1.5, 2.0, 2.5, 3.0))):
        for vth in vths:
            rows, prev = [], None
            for tau in range(20, 801, 5):
                tr, tf = (tau, tau) if sym else (5, tau)
                ma4 = run_rc(red4, 4, tr, tf, vth)[1]
                if not (165 <= ma4 <= 190) or abs(run_rc(red4, 1, tr, tf, vth)[1] - 40) > 1:
                    prev = None
                    continue
                cells = []
                for label, led in plan:
                    rd, ma = run_rc(n7(led), 4, tr, tf, vth)
                    cells.append(f"{label} {ma:.0f} ({describe(*rd[1])})")
                sweep = " / ".join(f"{run_rc(n7((0xE4, 0, 0, 0xFF)), f, tr, tf, vth)[1]:.0f}" for f in (2, 3, 5, 8))
                key = (round(ma4), tuple(cells), sweep)
                if prev and prev[0] == key:
                    prev[2] = tau
                else:
                    prev = [key, tau, tau]
                    rows.append(prev)
            label = f"  {name}, switching point {vth} V:"
            if not rows:
                print(label, "no tau fits")
            for key, t0, t1 in rows:
                print(f"{label} tau {t0}-{t1} ns | {key[0]} mA | " + "; ".join(key[1]) + f" | {key[2]}")


TESTS = [
    ("1      red, field 4", [(0xE4, 0, 0, 0xFF)] * N),
    ("2      green, field 4", [(0xE4, 0, 0xFF, 0)] * N),
    ("3      blue, field 4", [(0xE4, 0xFF, 0, 0)] * N),
    ("4      white, field 4", [(0xE4, 0xFF, 0xFF, 0xFF)] * N),
    ("g1 1   red, field 1", [(0xE1, 0, 0, 0xFF)] * N),
    ("g5 1   red, field 5", [(0xE5, 0, 0, 0xFF)] * N),
    ("g31 1  red, field 31", [(0xFF, 0, 0, 0xFF)] * N),
    ("a      field ladder 1 2 4 8 16", [(0xE0 | (1 << (k % 5)), 0, 0, 0xFF) for k in range(N)]),
    ("xF60000FF  red at field 22", [(0xF6, 0, 0, 0xFF)] * N),
    ("xF78000FF  F1's reading of g5 red", [(0xF7, 0x80, 0, 0xFF)] * N),
]

if __name__ == "__main__":
    print("Per-LED current at field 4 (mA):", {k: round(v, 2) for k, v in CH_MA_F4.items()}, "| dark strip", DARK_MA, "mA\n")
    print("Total supply current (mA) for 14 LEDs, by model; measured at 4 MHz: pattern 1 at field 4 = 174-178 mA\n")
    names = list(MODELS)
    print("| test | " + " | ".join(names) + " |")
    print("|---|" + "---|" * len(names))
    for label, leds in TESTS:
        print(f"| `{label}` | " + " | ".join(f"{run(leds, m)[1]:.0f}" for m in names) + " |")
    print("\nWhat LED 0 and LED 1 read (field, duty per colour), by model:\n")
    for label, leds in TESTS:
        print(label)
        for m in names:
            rd, ma = run(leds, m)
            d0, d1 = describe(*rd[0]), describe(*rd[1])
            print(f"   {m:3s} {ma:5.0f} mA   LED0 {d0}" + ("" if d1 == d0 else f"   | LED1 {d1}"))
    print("\nField read back for a red LED (header after a 0xFF byte) under F1 / F2, sent field 1..31:")
    row = []
    for f in range(1, 32):
        r1 = run([(0xE0 | f, 0, 0, 0xFF)] * 2, "F1", 2)[0][1][0] & 31
        r2 = run([(0xE0 | f, 0, 0, 0xFF)] * 2, "F2", 2)[0][1][0] & 31
        row.append(f"{f}->{r1}/{r2}")
    print("  " + ", ".join(row))
    print("\nOne LED lit (n1), red, field 4: ok %.1f mA, F1 %.1f mA (the dark 8 mA of the other 13 included)"
          % (run([(0xE4, 0, 0, 0xFF)], "ok", 1)[1], run([(0xE4, 0, 0, 0xFF)], "F1", 1)[1]))
    # the bench plan runs with n7 (LEDs 0-6 lit, 7-13 dark) so that every step stays under the 0.30 A limit
    print("\nBench plan, n7 (7 of 14 LEDs lit), supply current in mA: ok / F1 / F2, and what F1 looks like")
    plan = [
        ("1 at field 4 (red)", (0xE4, 0, 0, 0xFF)),
        ("g1 1 (red, field 1)", (0xE1, 0, 0, 0xFF)),
        ("g5 1 (red, field 5)", (0xE5, 0, 0, 0xFF)),
        ("g31 1 (red, field 31)", (0xFF, 0, 0, 0xFF)),
        ("2 at field 4 (green)", (0xE4, 0, 0xFF, 0)),
        ("3 at field 4 (blue)", (0xE4, 0xFF, 0, 0)),
        ("xF60000FF (red, field 22)", (0xF6, 0, 0, 0xFF)),
    ]
    for label, led in plan:
        leds = [led] * 7 + [(0xE0, 0, 0, 0)] * 7
        res = {m: run(leds, m) for m in ("ok", "F1", "F2")}
        print(f"  {label:28s} {res['ok'][1]:4.0f} / {res['F1'][1]:4.0f} / {res['F2'][1]:4.0f}   F1 reads {describe(*res['F1'][0][1])}")
    rc_section()
    # the time budget: a 704 B frame against the 2.78 ms column at 225 rpm
    for mhz in (1, 2, 2.5, 3, 4, 5, 6.67, 8):
        t = 704 * 8 / mhz
        print(f"  {mhz:5.2f} MHz: 704 B frame = {t:6.0f} us = {t / 2778 * 100:5.1f} % of the 2,778 us column")
