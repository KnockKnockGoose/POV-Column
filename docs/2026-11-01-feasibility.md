# Spinning Persistence-of-Vision LED Column: Feasibility Study

**Prepared for Brian** · Claude (Opus 5.5), feasibility agent on the desktop PC · 2026-11-01 (revision 2026-11-01b)
Source brief: brain dump 2026-11-01 10:25 (`Brain-Dump/obs/2026-11-01_1025_brain-dump.txt`, the section starting "It's November 1st"), plus Brian's design choice of 2026-11-01: **160 mm column, 8 strips, about 450 RPM**.
Target: YouTube Video 2. **Date check:** 2026-11-06 is the Friday; 2026-11-07 is a Saturday. The plan below aims to publish Friday 11-06 and keeps Saturday 11-07 as a buffer day.

---

## Revision 2026-11-01b: what changed from the 80 mm design and why

The first version of this report (kept in summary as Appendix A) recommended an 80 mm column with 4 helical strips at 900 RPM. Brian has since chosen a **160 mm column with 8 strips at about 450 RPM**. This revision reworks every section for that design. All numbers come from `calc/feasibility_calc.py`, which now prints the chosen design, the 16-strip variant (Appendix B) and the original design (Appendix A).

| Quantity | 80 mm / 4 strips / 900 RPM (old) | **160 mm / 8 strips / 450 RPM (new)** | Why it changed |
|---|---|---|---|
| Image size (pixels) | 28 × 72 | **28 × 72** (unchanged) | 2 interleave sets × 14 LEDs; 72 columns kept |
| Pixel size (w × h) | 3.5 × 8.15 mm | **7.0 × 8.33 mm** | Circumference doubles; the image is 2× wider for the same pixel count |
| Refresh rate | 30 Hz | **30 Hz** | Twice the strips at half the speed: f = K·f_rot = 4 × 7.5 |
| Surface speed, hoop stress | 3.77 m/s, 17.6 kPa | **3.77 m/s, 17.6 kPa** | Both depend only on ωR, which is unchanged |
| Centripetal acceleration | 36 g | **18 g** | ω²R: ω halves (÷4), R doubles (×2) |
| Column time | 926 µs | **1852 µs** | Half the speed; the data budget now has 62 % margin, up from 24 % |
| LEDs, typical current | 56, 0.51 A | **112, 0.90 A** | Twice the strips |
| Rotor inertia, stored energy | 3.5 × 10⁻⁴ kg·m², 1.6 J | **2.3 × 10⁻³ kg·m², 2.5 J** | Thin tube I ∝ R³; ω² ÷ 4 |
| Strip mounting | Helix at 12.1° in grooves | **Straight vertical strips between printed rails** | The one-column helix would now be 24.8°, no longer "slightly diagonal" (Section 2.3) |
| Data lines / level shifters | 4 / one 74AHCT125 | **8 / two 74AHCT125** | One line per strip; the classic ESP32 has exactly 8 RMT channels |
| Power | 1×18650 power bank, ~4 h | **2×18650 shield, ~4.1 h** (bank still works, 2.3 h) | Double the load; the bigger tube has room for the shield |
| Motor | ≥ 30 mN·m, ~1000 RPM | **≥ 100 mN·m (≈1 kg·cm), 500-600 RPM no-load** | 3× the spin-up torque, half the speed |
| Control | Simple Wi-Fi text box | **Phone web UI at `pov.local`, WebSocket, browser image conversion, LittleFS, OTA** | Added at Brian's request; OTA is essential on a sealed rotor (Section 8.5) |

**Corrections to the preliminary chat numbers.** The interleaved row pitch is **8.33 mm**, not 5.9 mm. The 5.9 mm figure halved Brian's measured 11.8 mm, which is the *gap* between 5 mm LED packages. The *pitch* of a 60 LED/m strip is 1000/60 = 16.67 mm, so half-pitch interleaving gives 8.33 mm rows. Square pixels therefore need **60 columns, not 85**. The original 80 mm report already used the correct 16.67 mm pitch, so it carried no such error. The stored-energy estimate of "~8×, ~3 J" holds only for a 2 mm wall (7.8×, 3.0 J). The recommended 1.6 mm wall gives **6.7×, 2.5 J**. The other chat numbers check out: 3.8 m/s, 18 g, 30 Hz, 1852 µs vs 700 µs, two 74AHCT125, ≥ 100 mN·m, ~2 mN·m drag, ~1 A and ~4 h on 2×18650.

---

## Abstract

This study checks whether a 3D-printed cylinder carrying eight WS2812B strips, battery powered and spun by a motor, can show text and images by persistence of vision (POV). It also sizes the electronics, power, motor and balance. **Verdict: it works, and the 160 mm design is easier than the 80 mm one in every limiting number except rotor inertia.** The build is a Ø160 × 250 mm column with **8 straight strips of 14 LEDs (112 LEDs)** in two half-pitch interleaved sets, spinning at **450 RPM (7.5 rev/s)** and drawing **72 angular columns per revolution**. That gives a **28 × 72 pixel, 360° image at 30 Hz** with pixels about 7 × 8 mm. Two conditions carry over from the first version. Use the classic **ESP32** you already own (not the Nano), with **each strip on its own data pin**, so 8 pins use all 8 RMT channels; the CD4017 counter chips are not needed. A 2×18650 shield on the rotor gives about 4 h of typical content, and a 12 V DC gearmotor of about 1 kg·cm drives it. The ESP32 serves its own web page, so a phone browser changes the text, colours and images, and new firmware goes in over the air (Section 8.5). The data budget has 62 % margin, or 24 % even if the LED driver sends the 8 lines in two batches. The main risks are WS2812B timing and PWM behaviour and the larger rotor's balance. A bench test today (Sunday) settles the first before anything is printed.

---

## 1. Requirements recovered from the brain dump

| Requirement (Brian's words, paraphrased) | Interpretation used here |
|---|---|
| WS2812B strips, "60 … 5V IP30", ~5 mm LEDs, ~11.8 mm apart, 9.3 mm wide | 60 LED/m strip. Pitch p = 1000/60 = **16.67 mm**; LED body 5.0 mm, so the **gap is 11.67 mm**. The measured 11.8 mm is the gap, not the pitch. The build uses the single **5 m black-PCB reel** (300 LEDs) he owns. |
| Drop the bundled controller, drive with an Arduino | Section 3: a Nano is not enough; the ESP32 is (already owned, 3-pack). |
| Several strips, slightly diagonal, each still reads as a vertical line | With 8 strips on a 160 mm drum the clean helix would be 24.8°. **Straight vertical strips** are recommended instead (Section 2.3). |
| Whole column spins, speed-controlled motor ("stepper") | DC gearmotor recommended over a stepper (Section 6). |
| Electronics inside, battery on the rotor, avoid a slip ring | Yes. Slip rings checked and rejected (Section 5.3). |
| Bottom piece hides the motor, top cap hides the strip ends | Kept. With 8 parallel data lines every strip is fed from the bottom, so no wires return over the top (Section 3.4). |
| Software: text/photos in, per-LED per-angle colours out | Python generator plus ESP32 firmware (Section 8). |
| **Added 2026-11-01:** change what it shows from the phone over Wi-Fi | ESP32-served web page at `pov.local`, WebSocket, browser-side image conversion, LittleFS storage, OTA (Section 8.5). |
| "Counter chips" to route the signal to multiple strips | Inventory shows **CD4017 decade counters** (20-pack). Not needed, and they would corrupt WS2812B timing (Section 3.4). |
| **Decided 2026-11-01:** 160 mm diameter, 8 strips, ~450 RPM, ~240 mm tall | Adopted as the design basis for this revision. |

---

## 2. POV requirements: speed and resolution

### 2.1 Geometry (chosen design)

| Parameter | Value |
|---|---|
| Column outer diameter / radius | D = 160 mm, R = 80 mm |
| Circumference | πD = 502.7 mm |
| Tube height | 250 mm body (lit span 242 mm, see below); fits a 256 × 256 × 256 mm Bambu volume, and the H2D, printed vertically in one piece |
| Strips | **8, straight and vertical, 45° apart**, 14 LEDs each = **112 LEDs**, 233.3 mm per strip, 1.87 m of the 5 m reel |
| Strip footprint | 8 × 10 mm channels = 16 % of the circumference, leaving 53 mm of bare black tube between strips |
| Vertical layout | **Set A** (strips 0, 2, 4, 6) with LED centres at z₀ + 16.67·i; **Set B** (strips 1, 3, 5, 7) offset by p/2 = 8.33 mm. This gives **28 interleaved rows at 8.33 mm pitch**. LED centres span 225 mm; strip ends span 241.7 mm. |

Each set is four strips at 90°, so each set is balanced by itself, statically and dynamically. That is a nice property to mention in the video.

### 2.2 Refresh rate, RPM and the row layout

Flicker fusion for a bright, small, moving source sits at about 30-50 Hz for the eye. A camera only needs the exposure to integrate one full refresh (Section 9).

With K strips sharing the same row set, every row is redrawn K times per revolution:

  f_refresh = K · f_rot

| Layout of the 8 strips | Rows (pitch) | K | Refresh at 450 RPM | RPM needed for 30 Hz |
|---|---|---|---|---|
| 1 set, all at the same height | 14 (16.67 mm) | 8 | 60 Hz | 225 |
| **2 sets, half-pitch offset (recommended)** | **28 (8.33 mm)** | **4** | **30 Hz** | **450** |
| 4 sets, quarter-pitch offset | 56 (4.17 mm) | 2 | 15 Hz (visible flicker; 1/15 s shutter smears motion) | 900 (72 g, 4× the stored energy) |

**Recommendation: 2 sets, 28 rows at 30 Hz.** The 56-row layout doubles vertical resolution but halves the refresh, and getting 30 Hz back means 900 RPM on a 160 mm rotor, which undoes the reason for choosing this design. The row offsets are **physical** (they set the height at which each strip is stuck down), so this is decided before gluing, not in software. If 56 rows are wanted later, the clean route is the 16-strip variant in Appendix B, which reaches 56 rows at the same 450 RPM and 30 Hz.

### 2.3 Angular resolution and strip angle

**Column count: M = 72 columns/rev (Δθ = 5°).** The script compared the options:

| M | Pixel width | Aspect w/h | Column time | Margin, 8 parallel lines | Margin, 2 batches of 4 | Columns per strip spacing (÷8) |
|---|---|---|---|---|---|---|
| 60 | 8.4 mm | 1.01 (square) | 2222 µs | 68 % | 37 % | 7.5 (not an integer) |
| 64 | 7.9 mm | 0.94 | 2083 µs | 66 % | 33 % | 8 |
| **72** | **7.0 mm** | **0.84** | **1852 µs** | **62 %** | **24 %** | **9** |
| 96 | 5.2 mm | 0.63 | 1389 µs | 50 % | −1 % (fails) | 12 |

M = 72 is chosen because:
- Pixels are close to square (0.84).
- It keeps margin even in the worst case, where the LED driver sends the 8 lines as two batches of 4 (Section 3.2).
- The 45° strip spacing is exactly 9 columns.
- The firmware and generator from the first design carry over unchanged.

M = 96 is worth trying later, but only once the bench test confirms that all 8 lines really run in parallel.

What the viewer sees:
- The LED body is 5 mm, which is 3.6° or 0.72 of a column, so at 160 mm the LED no longer limits horizontal resolution (at 80 mm it covered 1.4 columns).
- During one column the LED moves 7 mm, so each pixel appears as a ~12 mm wide smear, 1.7 pitches. That is sharper than the 80 mm design, which smeared over 2.4 pitches.
- About 120° of the drum faces the camera at once, roughly 24 columns. In a 5 × 7 font with 1-column spacing (42 mm wide, 58 mm tall characters), that shows **about 4 characters at a time**.
- 28 rows hold **two lines of 7-row text**.

**Strip angle: straight vertical strips, compensated in software.** On a cylinder, a helical strip makes LED i step θ_i = i·p·sin α / R. A step of exactly one column needs:

  sin α = Δθ·R / p = (0.0873 rad × 80 mm) / 16.67 mm, so **α = 24.8°**

At that angle each strip wraps 111 mm (79°) around the drum over 240 mm of height. That is a pronounced spiral, not the "slightly diagonal" look of the brief. The gentler 12.1° helix only works with 144 columns/rev, which fails the data budget (Section 3.1). Straight strips win on every practical count:
- The rails print cleanly.
- The half-pitch offsets are exact.
- There is one LED per row per strip.
- The only software term is a per-strip phase offset c₀(s) = 9·s columns.

The helix stays a styling option (Section 13). If chosen, it needs 15 LEDs per strip (vertical step 15.1 mm) and helical rails.

---

## 3. Controller and data rate

### 3.1 WS2812B timing

- 800 kbit/s and 24 bit/LED give **30 µs per LED**.
- Latch (reset) gap: ≥ 50 µs on the original WS2812B, **≥ 280 µs on WS2812B-V5**. The die revision of these strips is unknown, so 280 µs is assumed (conservative).

  t_line(n) = 30 µs · n + 280 µs, against t_col = 1/(f_rot·M) = 1/(7.5 × 72) = **1852 µs**

| Data-line arrangement (112 LEDs) | Time per column update | Margin vs 1852 µs | Max columns/rev |
|---|---|---|---|
| **8 lines × 14 LEDs, all parallel (recommended)** | **700 µs** | **62 %** | 190 |
| 8 lines, driver sends 4 at a time (2 batches) | 1400 µs | 24 % | 95 |
| 4 lines × 28 LEDs (2 strips chained per pin) | 1120 µs | 40 % | 119 |
| 1 line × 112 LEDs (all chained, or Nano bit-bang) | 3640 µs | fails | 37 |

### 3.2 Board choice, and checking the ESP32 variant

| Board | Parallel WS2812B output | RAM for frames | Verdict |
|---|---|---|---|
| **Arduino Nano** (ATmega328P, owned) | No. It bit-bangs one pin at a time with interrupts off, which is the 112-LED serial case above (fails). | **2 KB SRAM vs a 24.2 KB frame.** It doesn't fit. | **Not enough.** |
| **ESP32-WROOM-32** (classic ESP32, dual core 240 MHz, owned ×3) | Yes. The classic ESP32 has **8 RMT channels, all able to transmit**, which is exactly one per strip. It also has an **I2S parallel mode** that drives 8-24 lines at once. | ~300 KB heap ≈ 12 frames; 1.5 MB LittleFS ≈ 62 frames | **Recommended.** |
| ESP32-S3 / -S2 / -C3 (for comparison) | RMT TX channels: 4 / 4 / 2 | | Would force batching or I2S/LCD. Check that the 3-pack is the classic part. |

**Variant check.** The inventory names ESP32-WROOM-32 modules, which carry the classic ESP32 (ESP32-D0WD) chip. The claim of 8 RMT channels holds for that chip. Confirm on Sunday: `esptool.py chip_id` should print "ESP32" (not "ESP32-S3"), or read the can label "ESP32-WROOM-32".

**The one caveat is the library, not the chip.** Depending on the FastLED version and its RMT memory-block setting, the RMT driver may give each channel two memory blocks. In that case it runs only 4 channels at once and sends the other 4 straight after: the 1400 µs "2 batches" row, which still fits with 24 % margin. If the bench measurement shows about 1400 µs instead of about 700 µs, there are two fixes:
1. Set FastLED's RMT memory-block count to 1 (more sensitive to Wi-Fi interrupts).
2. Switch to FastLED's **ESP32 I2S parallel driver** (`#define FASTLED_ESP32_I2S`), which clocks all 8 lines out together via DMA and is less sensitive to Wi-Fi.

Either way the 72-column design works.

**Pins** (avoid the strapping pins 0/2/5/12/15, flash pins 6-11 and the input-only pins 34-39): data on **GPIO 16, 17, 18, 19, 21, 22, 23, 25**, hall sensor on **GPIO 27**.

### 3.3 3.3 V logic into 5 V strips

The WS2812B logic-high threshold is 0.7·VDD = 3.5 V at 5 V, and the ESP32 outputs 3.3 V. That is marginal, and a spinning rotor is no place for intermittent glitches. Fit **two 74AHCT125 quad buffers** (8 channels, one per strip), powered at 5 V. Add a 330 Ω series resistor per data line and a 1000 µF capacitor across 5 V/GND at the strip power bus. A single pack of 74AHCT125s normally holds 5-10 chips, so one purchase covers it. A 74HCT245 (8 channels in one chip) would also work but isn't in the inventory.

### 3.4 What the "counter chips" are and why they aren't needed

- **What they are.** The inventory lists a **CD4017 decade counter** 20-pack. It moves a single HIGH output along Q0 to Q9 (a one-hot sequencer, the classic "LED chaser" chip). The word you were reaching for was **multiplexing**.
- **Why they aren't needed.** WS2812B strips are *addressable*. Each LED takes its 24 bits and passes the rest on, so the routing happens in the data stream.
- **Why they would hurt.** A CD4017 can only sequence, not pass data. CD4000-series logic also adds ~100-300 ns of delay at 5 V, against a WS2812B T0H spec of 400 ± 150 ns.
- **The fix is 8 GPIO pins.** All 8 data lines enter at the bottom next to the electronics, so **no wire has to return over the top cap**. The 4 × 28 chained option would save one level shifter, but it needs a jumper over the top between each pair of strips. It is kept only as a fallback.
- (A good beat for the video: "I was ready to use my counter chips, and it turns out I didn't need them.")

---

## 4. Frame buffer and software data flow

- One frame = 112 LEDs × 72 columns × 3 B = **24.2 KB**. A 30-frame animation = 709 KB, stored in LittleFS (1.5 MB holds about 62 frames) with the current frame in RAM (about 12 frames fit in heap).
- Bandwidth to the LEDs: 112 LEDs × 24 bit × 540 columns/s = **1.45 Mbit/s**, the same total as the 80 mm design. It is spread over 8 lines and generated in hardware, so the CPU only refills buffers.

---

## 5. Power

### 5.1 Current budget (5 V rail)

| Load | Formula | Current |
|---|---|---|
| LEDs, absolute max (all white, 255) | 112 × 60 mA | 6.7 A (never run this way) |
| LEDs, typical text (≈30 % of pixels lit, one saturated channel) | 112 × 0.30 × 20 mA | 0.67 A |
| LED quiescent (≈1 mA each, even dark) | 112 × 1 mA | 0.11 A |
| ESP32 with Wi-Fi on (average; TX peaks 0.1-0.25 A) | | 0.12 A |
| **Typical total** | | **≈0.90 A ≈ 4.5 W** |
| Typical with a Wi-Fi TX peak | 0.90 − 0.12 + 0.25 | 1.03 A (short peaks; the 1000 µF bus cap and the 3 A shield absorb them) |
| Software cap (`FastLED.setMaxPowerInVoltsAndMilliamps(5, 2500)`) | | 2.5 A = 12.5 W; 0.31 A per strip feed |

### 5.2 Battery runtime and choice

Assume 85 % converter efficiency. Runtime = E·η / P.

| Option | Energy | Typical (4.5 W) | At the cap |
|---|---|---|---|
| A. Cylindrical 1×18650 USB power bank (≈3350 mAh, 5 V 2.4 A), on the axis | 12.1 Wh | ≈2.3 h | ≈0.85 h at 2.4 A |
| **B. 2×18650 battery shield (1S2P, 5 V/3 A boost, USB charging) with 2 brand-name 3.0 Ah cells**, recommended | 21.6 Wh | **≈4.1 h** | ≈1.5 h at 2.5 A |

**Why Option B now:**
- **Runtime.** The load has doubled, so the single-cell bank drops to about 2.3 h. The shield restores the ~4 h of the first design.
- **Headroom.** The 3 A output carries the 2.5 A cap, while the bank tops out at 2.4 A.
- **Cell current.** At the cap the cells deliver 4.1 A total, 2.0 A each in parallel, which is comfortable for brand-name cells.
- **Room.** The 156 mm bore has plenty of space for the shield.
- **Balance.** Mount the shield so the spin axis runs between the two cells. The pair then balances itself, while a single cell 15 mm off-axis would pull 1.5 N. The script gives 1.5 N for that case, against 6.1 N at 900 RPM, so the lower speed is far more forgiving.
- Buy Samsung, Molicel or LG cells from a reputable seller; counterfeit 18650s are common on Amazon.

Option A remains a valid quick fallback: about 2.3 h is enough for a filming session with a recharge between takes.

### 5.3 Slip ring, considered and rejected

- Cheap capsule slip rings (12-22 mm, ~2 A per circuit) are typically rated **250-300 RPM**, below the 450 RPM needed.
- At the 2.5 A cap, two or three circuits would be needed in parallel.
- A slip ring adds a stationary 5 V supply.
- On-rotor batteries remain simpler. A slip ring only makes sense for a permanent display, and then as power-only.

---

## 6. Motor: torque, power and type

### 6.1 Rotor mass and inertia (estimate)

| Part | Mass | Effective radius |
|---|---|---|
| PLA tube, Ø160 × 250 mm, **1.6 mm wall** (4 × 0.4 mm perimeters, no infill) | 249 g | 80 mm (thin shell, m·R²) |
| 16 guide rails, 1.2 × 1.0 mm | 6 g | 80 mm |
| 8 strips (25 g/m × 233 mm) | 47 g | 80 mm |
| 2 caps (2 mm skins, ribs, 10-15 % infill) | 90 g | disc, ½·m·R² |
| 2×18650 shield + cells, ESP32, board, sled | 200 g | ~15 mm |
| Hub / flange coupling | 20 g | axis |
| **Total** | **≈612 g** | **I ≈ 2.3 × 10⁻³ kg·m²** (6.7× the 80 mm design; 7.8× with a 2 mm wall) |

At ω = 2π × 7.5 = 47.1 rad/s:
- Kinetic energy ½Iω² = **2.5 J** (3.0 J with a 2 mm wall). That is about a 250 g phone dropped from 1 m, still small.
- Spin-up from 0 to 450 RPM in 3 s: τ = I·ω/t = **36 mN·m**.

### 6.2 Aerodynamic drag

The rotor is axisymmetric, so drag is skin friction only.
- Tip speed v = ωR = 3.77 m/s; Re = vR/ν = 2.0 × 10⁴.
- Theodorsen-Regier rotating-cylinder friction law gives C_f ≈ 0.0064.
- τ_side = ½ρv²·C_f·(2πRH)·R = 0.55 mN·m. With ×3 for the bumpy LED and rail surface, plus 0.12 mN·m for the end discs: **≈1.8 mN·m, 0.08 W.**

Drag is about 4× the 80 mm value (τ ∝ R²·H at fixed surface speed) and still negligible.

**Motor spec:** spin-up (36 mN·m) plus drag (1.8 mN·m) plus gearbox and bearing losses, with about 2.5× margin, gives **≥ 100 mN·m (≈1 kg·cm) rated torque**. Speed: **500-600 RPM no-load at 12 V**, so 450 RPM sits at about 75-90 % voltage with headroom for load. Power is about 1-3 W.

### 6.3 Stepper vs DC vs BLDC

| | NEMA17 stepper + driver | **12 V DC gearmotor (JGB37-520 class, 500-600 RPM variant)** | BLDC + ESC |
|---|---|---|---|
| 450 RPM? | Yes, but it needs a driver (TMC2209), a 24 V supply and ramps against 2.3 × 10⁻³ kg·m² of inertia, or it stalls. | Yes, at ~10-11 V on the bench supply | RC motors idle at thousands of RPM; poor low-speed start |
| Speed control | Exact, open loop | Bench-supply voltage knob, or a PWM module | ESC |
| Parts owned | None | Bench DC supply (owned) | None |
| **Verdict** | Not worth it: the hall sensor measures speed, so exact open-loop speed buys nothing | **Recommended** | Overkill |

**Mounting:**
- The heavier, wider rotor gets a **6 mm D-shaft flange coupling bolted to the bottom cap with 4 × M3 into heat-set inserts** (owned), instead of the single set screw of the first design.
- Axial load is about 6 N, which the gearbox output bearing handles.
- No top bearing is needed if the rotor is balanced (Section 7).
- Clamp the base to the bench.

---

## 7. Balance, retention and safety

| Check | Number | Consequence |
|---|---|---|
| Centripetal acceleration at the strips | ω²R = 178 m/s² = **18 g** (half the 80 mm design) | Strip adhesive load 2.5 kg/m² × 178 = **0.44 kPa**, an easy load for fresh 3M tape. Still **print guide rails** (pairs, 10 mm apart, 1.2 × 1.0 mm) that locate each strip and fix the row offsets, plus a drop of CA or Kapton at each end. |
| Unbalance from one 18650 15 mm off-axis | **1.5 N** rotating | Mount the 2-cell shield symmetric about the axis. |
| Balance target, ISO 21940 G6.3 | e = 6.3/ω = 134 µm, so U ≈ **82 g·mm** for 0.61 kg | ≈ 2.3 M3 nuts (0.5 g each) at r = 72 mm. **Print 8 balance pockets in the top cap at r = 72 mm** (and optionally 8 in the bottom cap for couple unbalance). Spin up in steps and add nuts opposite the heavy side. |
| Missing or uneven strip | One strip = 5.8 g at R = 467 g·mm, **5.7× the limit** | Cut all 8 strips to exactly 14 LEDs and route all 8 wire sets the same way. The symmetry does the balancing. |
| PLA hoop stress | σ = ρω²R² = **17.6 kPa** vs ~50 MPa | Safety factor about 3000, unchanged from 80 mm because it depends only on surface speed. |
| Tip speed / stored energy | 3.77 m/s, 2.5 J | Knuckle-bump level, but the larger drum grabs loose cables and hair more easily. Keep a guard or box around first spins. |
| Li-ion | Protected cells in a 2×18650 shield, strapped to a printed sled | Never rely on spring clips; zip-tie or capture every board; hot-glue solder joints. Run first spins inside a cardboard box. |

**Print notes:**
- The 160 mm tube footprint leaves ~48 mm each side on a 256 mm bed.
- A 1.6 mm all-perimeter wall keeps rim mass low: the rim (tube, rails and strips) is 49 % of the rotor mass but supplies 85 % of its inertia.
- Estimated **206 cm³, ~7 h**, so print it overnight. An optional internal stiffening ring at mid-height helps the tall thin wall hold its roundness during printing.
- Print the caps with thin skins and 10-15 % infill.

---

## 8. Electronics, firmware and software design

### 8.1 Rotor electronics (all inside the tube)

```
2x18650 shield (cells either side of the axis) -> slide switch -> 5 V bus ring on bottom cap
   5 V bus -+- 1000 uF -+- 8 strips, each fed at the bottom (22 AWG star)
            +- ESP32 5V pin
ESP32 GPIO 16,17,18,19,21,22,23,25 -> 2 x 74AHCT125 (at 5 V) -> 330 R -> strip DIN 0..7
A3144 hall (5 V, open collector, 10 k pull-up to 3.3 V) -> GPIO 27 interrupt
neodymium magnet fixed in the stationary base, under the hall sensor's path
```

### 8.2 Firmware (Arduino-ESP32 + FastLED)

1. **Hall ISR.** Record `t_now = esp_timer_get_time()` and set `T = t_now − t_prev` (about 133.3 ms at 450 RPM).
2. **Column scheduler, pinned to core 1.** For column c, fire at `t_prev + c·T/72 − t_latency`. `FastLED.show()` drives all 8 lines at once (RMT or I2S, Section 3.2). Strip s shows image column (c + 9·s) mod 72; set B rows interleave with set A rows.
3. **Wi-Fi task on core 0.** Web page, WebSocket commands, frame uploads and OTA (Section 8.5).
4. **Telemetry.** RPM on the web page, used to set the bench-supply voltage for 7.50 rev/s.

Hall timing jitter of about 20 µs is 0.05° at 7.5 rev/s, which is negligible.

### 8.3 PC generator (Python, ~150 lines)

1. **Input:** text (PIL font render) or an image/GIF.
2. **Resample** to 28 rows × 72 columns (360° unwrap). Pixels are 7.0 × 8.33 mm, so the aspect correction is small (0.84).
3. **LED map** (`ledmap.json`: strip, index, z, θ for each LED). Pixel for strip s, LED i at column c = image[2i + (s mod 2), (c + 9s) mod 72].
4. **Quantize** (8.4), gamma 2.2, brightness cap.
5. **Output** a `.pov` binary (header + frames × 72 × 112 × 3 B), plus a matplotlib preview of the unwrapped and cylinder-rendered view. The preview is a good on-screen video asset.

### 8.4 The one real WS2812B limitation: internal PWM

- WS2812B dims by PWM at about **0.4-2 kHz** (period 0.5-2.5 ms) depending on die revision. That is comparable to one 1852 µs column, so mid-tones would render as dashed arcs. The banding is slightly less than at 926 µs, but still there.
- **Mitigation for Friday:** use saturated colours (each channel 0 or 255, 8 colours) and dim globally with the cap.
- **Upgrade path, already owned:** **SK9822 (APA102-type) 60/m strips**.
  - ~4.7 kHz PWM.
  - Clocked SPI: all 112 LEDs on one 8 MHz bus update in about 0.5 ms.
  - Same pitch, so the same tube fits.
  - Write the firmware with FastLED so the chipset is a compile switch.
- Use the **black-PCB WS2812B reel** on a black PLA tube for the best POV contrast.

### 8.5 Control over Wi-Fi (phone browser, no app)

**Architecture.** The rotor ESP32 serves its own web page. There is no native app: any phone browser works, and the page is part of the firmware.

| Piece | Design |
|---|---|
| Network | Joins the home Wi-Fi (credentials in a gitignored `wifi_secrets.h`). Advertises **`http://pov.local`** by mDNS. If the home network isn't found within 10 s, it falls back to its own access point (`POV-Column`, page at 192.168.4.1) so it still works at a shoot location. |
| Web page | One static HTML/JS file stored in LittleFS. Controls: text box, colour, brightness, mode (scroll / static / animation / test pattern), scroll speed, phase trim, plus a live RPM readout. |
| Live commands | **WebSocket** (`/ws`, small JSON messages such as `{"text":"SUBSCRIBE","color":"#ff0000"}`). Text is rendered on the ESP32 with its built-in 5×7 font, so typing updates the column in about one revolution (133 ms). |
| Images | The polar conversion runs **in the browser** (canvas JS: resample to 28 × 72, map to strips and LEDs, quantize to the 0/255 palette). The page sends the finished bytes: **24,192 B per frame** (112 × 72 × 3), which uploads in well under 0.1 s. The ESP32 saves frames to **LittleFS** (about 62 fit), so content survives power-off. The Python generator stays the reference implementation and makes the preview plots for the video. |
| OTA updates | **ArduinoOTA / ElegantOTA** over Wi-Fi, using the default 4 MB partition scheme (two app slots + 1.5 MB LittleFS). **This is the biggest win**: once the rotor is closed and balanced, its USB port is inaccessible, and opening it would upset the balance. Get OTA working on Monday, *before* the rotor is sealed. |
| Motor speed from the phone | **Not for Friday.** The motor is in the stationary base, and the rotor ESP32 has no wire to it, so speed stays on the bench-supply knob. v2 option: a second ESP32 (owned 3-pack) in the base with a logic-level MOSFET or a small motor-driver module, linked to the rotor by **ESP-NOW**, so the page's RPM slider closes the loop with the hall-measured speed. |

**Is RMT safe with Wi-Fi active?** It is safe with care, but not guaranteed:
- The RMT and I2S peripherals generate the WS2812B waveform in hardware, so Wi-Fi never touches the bit timing *while a buffer plays*.
- The risk is the **refill**. A 14-LED strip is 336 RMT symbols, which is 5.25 of the 64-symbol memory blocks, so the RMT driver (FastLED's or NeoPixelBus's) must refill each channel from an interrupt partway through every update. If a Wi-Fi interrupt delays that refill past the end of the hardware buffer, the line stalls longer than the latch time and the strip shows a glitched column. Both libraries document this as flicker under Wi-Fi load.
- **Mitigations, in order:**
  1. Call `FastLED.show()` from a task pinned to **core 1**, so the RMT interrupt is allocated on core 1. Arduino runs the Wi-Fi stack on core 0.
  2. Prefer 2 memory blocks per channel. That means fewer refills, at the cost of the 4 + 4 batching, which still fits with 24 % margin (Section 3.2).
  3. If glitches remain, use the **I2S parallel DMA driver**. It streams the whole buffer from RAM by DMA with no per-block interrupt, so it is the robust choice when Wi-Fi is active.
- **Bench check on Sunday:** run the 8 test strips while the phone streams WebSocket text, and look for stray flashes.

**Optional v2 hooks** (good for the video, not in the Friday scope):
- A **"POV" tab in the Brain Dump App** (Expo, server on the Pi). The Pi server relays `POST http://pov.local/api/text` on the home network.
- **"Claude, show 'subscribe'"**: Claude Code on the desktop runs `curl -X POST http://pov.local/api/text -d "SUBSCRIBE"`. It makes a one-line on-camera hook that ties into the channel's Claude-hub theme.

---

## 9. Filming POV on the Sony ZV-E10

**Principle:** each row is redrawn every 1/f_refresh = 1/30 s. An exposure of exactly n/30 s captures a complete image in every frame, with no bands, even with the rolling shutter.

| Shot | Settings | Why |
|---|---|---|
| **Hero (the image)** | **30p, shutter 1/30 s**, manual exposure and WB, dark room, ISO 100-400, f/4-5.6 | Shutter = one refresh at 450 RPM with K = 4 |
| If you shoot 24p | Run at **360 RPM** (6 rev/s, 24 Hz refresh), shutter 1/24-1/25 | Keep shutter × refresh = 1 |
| **"Reveal" (how it really works)** | 1/2000-1/4000 s | The surface moves only 1.9 / 0.9 mm per exposure, so it freezes to 8 bare strips with a few lit LEDs |
| Slow-mo | 120p (HFR), 1/125 | 16 frames per revolution: the strips visibly "paint" the letters |
| Long-exposure still | 1/4-1 s, tripod | Light-painting thumbnail (a real photo, per the no-AI-thumbnail rule) |

Tips:
- A slowly moving dark band means the RPM is slightly off 7.50 rev/s. Nudge the supply voltage using the RPM readout.
- Keep the room dark.
- 1080p30 limits rolling-shutter skew.
- The 160 mm drum fills the frame from further back, which helps depth of field.

---

## 10. Recommended build for Friday

> **"POV-1":** black PLA tube, Ø160 × 250 mm, 1.6 mm wall, guide rails for 8 straight strips at 45° (optionally rails for 16 positions; Appendix B). 8 × 14-LED black-PCB WS2812B strips in a 4+4 half-pitch interleave (28 rows). ESP32 + 2 × 74AHCT125. 2×18650 shield on the axis. A3144 hall sensor + magnet. 12 V 500-600 RPM gearmotor (≥ 1 kg·cm) on the bench supply, spinning at 450 RPM with 72 columns/rev. Content changed from a phone browser at `pov.local` (text, colour, images), with OTA firmware updates: Wi-Fi text, a logo, one short animation.

### 10.1 Parts list

| Part | Have? | Notes |
|---|---|---|
| WS2812B 60/m 5 V IP30, **black PCB**, 5 m reel | **Owned** | 1.87 m used (8 × 14 LEDs); 3.1 m left, enough for a 16-strip v2 |
| ESP32-WROOM-32 dev board | **Owned** (3-pack) | Confirm the classic ESP32 chip (Section 3.2) |
| SK9822 60/m strip (fallback) | **Owned** | Section 8.4 |
| 1000 µF cap, 330 Ω ×8, 10 kΩ, 22 AWG silicone wire, JST/Dupont, protoboard, heat-set inserts, M3 screws/nuts, black PLA, printer | **Owned** | |
| Bench DC power supply (motor speed via voltage) | **Owned** | Confirm ≥ 12 V, ≥ 1 A |
| CD4017 counters | Owned | **Not needed** |
| 74AHCT125 quad buffer (DIP-14), pack | **Buy** | ~$7; **2 needed** (one pack covers it) |
| A3144 hall sensors (or KY-003 modules), pack | **Buy** | ~$6 |
| Neodymium disc magnets ~6 × 3 mm | **Buy** | ~$8 |
| **12 V DC gearmotor, 500-600 RPM no-load, rated ≥ 1 kg·cm (≈100 mN·m), 6 mm D-shaft** (JGB37-520 class) + bracket + **6 mm flange coupling** | **Buy** | ~$15-20; check the RPM variant on the listing |
| **2×18650 battery shield, 5 V/3 A out, USB charging + 2 brand-name 18650 (≥ 3.0 Ah, Samsung/Molicel/LG)** | **Buy** | ~$25-30. Fallback: a 1×18650 cylindrical bank (~$15, 2.3 h) |
| Mini slide switch | Probably owned | |
| PWM DC motor speed controller 12 V | Optional | Only if the bench supply is needed elsewhere |
| Second ESP32 (owned) + logic-level MOSFET module for base motor control over ESP-NOW | Owned / optional | v2 only (Section 8.5); nothing extra is needed for phone control on Friday |

Order today (Sunday 11-01) with one- or two-day delivery so everything arrives by **Tuesday 11-03**. Before buying, check each listing's delivery date on the live page, and prefer the fastest delivery even if it costs more.

### 10.2 Day-by-day plan

| Day | Build | Film / edit |
|---|---|---|
| **Sun 11-01** | Place the order. Confirm the ESP32 chip type. Bench test: cut **8 × 14-LED** strips, drive all 8 from one ESP32 with FastLED, time `show()` with `micros()`: ~700 µs means parallel, ~1400 µs means batched (both fit; Section 3.2). Check 3.3 V data, 0/255 vs mid-tone flicker, and **Wi-Fi robustness** (stream WebSocket text while the 8 lines update; Section 8.5). Start Fusion CAD: tube + rails, bottom cap (coupling, hall pocket, bus ring), top cap (balance pockets at r = 72 mm), battery sled. | Strip/inventory intro, counter-chip beat, bench test |
| **Mon 11-02** | Print the tube overnight (~7 h). Firmware v0 with **fake hall pulses** from a timer, **plus Wi-Fi: `pov.local`, AP fallback, WebSocket text/colour/brightness, and OTA** (proven before the rotor is sealed). Python generator v0 (text → `.pov` + preview). | Screen capture of the generator, CAD time-lapse |
| **Tue 11-03** | Parts arrive. Solder the rotor board (ESP32 + 2 × AHCT125 + hall), stick the 8 strips between the rails at the two set heights, wire the 8 bottom feeds identically, fit the battery sled. Hand-spin test. Print caps + base. | Assembly B-roll, macro solder shots |
| **Wed 11-04** | Mount the motor. Spin up in steps 150 → 300 → 450 RPM inside a box. Balance with nuts. Tune the phase trim from the phone page. Evening: browser canvas image converter + LittleFS frame upload (a port of the Python generator; uploading Python-made `.pov` files is the fallback). | First-spin reaction (the money shot); fast-shutter "reveal" |
| **Thu 11-05** | Content: phone text, logo, one animation; optional SK9822 swap test. **Film the A-roll** at 30p, 1/30 s, dark room. | A-roll + long-exposure thumbnail |
| **Fri 11-06** | Edit (Video 1 Premiere workflow), −14 LUFS, export, upload Unlisted → **publish** | |
| Sat 11-07 | Buffer / publish if Friday slips | |

**Fallback if the motor or balance fails by Wednesday:** spin it slowly on a lazy-susan or a drill at low speed. Hall sync makes the image correct at any speed; it will flicker below 450 RPM but still shows well on a 1/15 s shutter.

---

## 11. Risks and mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Latch > 280 µs or slow clones | Low | 62 % margin (24 % even when batched); Sunday bench measurement |
| RMT runs only 4 lines at once | Med | Still fits (1400 µs); or set RMT memory blocks to 1, or use the I2S parallel driver |
| ESP32 boards are not the classic chip | Low | `esptool chip_id` on Sunday; an S3 would need I2S/LCD or 4 × 28 chaining |
| 3.3 V data glitches | Med without buffers | 2 × 74AHCT125 |
| Mid-tone banding (WS2812B PWM) | High for photos, nil for 0/255 | Saturated palette; SK9822 for photos |
| Wi-Fi interrupting RMT refills | Med | Wi-Fi on core 0, `show()` on core 1, 2 RMT blocks per channel; I2S DMA driver as the robust fallback |
| Rotor sealed before OTA works | Low | OTA proven Monday on the bench, before assembly |
| Wobble / base walk (larger rotor) | Med | Symmetric strips and battery, balance pockets, bolted flange coupling, clamped base |
| Tall thin tube out of round | Low-med | 4-perimeter wall, mid-height ring, slow outer-wall speed |
| Schedule (1 week) | Med | Everything not owned arrives Tuesday; hand-spin fallback |

---

## 12. How to explain it

- **One-liner:** "Eight strips of LEDs spinning at 450 RPM become a 2,000-pixel, 360° screen. Each LED changes colour 540 times a second, in sync with a magnet that tells it where it is."
- **Scaling the design is a trade, not a guess.** Doubling the diameter and halving the RPM keeps the surface speed, and with it hoop stress and drag per area, exactly the same. It halves the g-load and doubles the image width. Doubling the strip count restores the 30 Hz refresh at half the speed (f = K·f_rot). The cost is inertia, which grows with R³ for a thin tube, so the motor and balancing get more attention.
- **The binding constraint is serial data, not CPU.** Each WS2812B costs 30 µs, so one line refreshes only about 15-20 LEDs per ~1 ms column. The fix is parallelism: one data line per strip, 8 lines driven at the same time by the ESP32's 8 RMT channels. Matching the hardware's parallel width to the problem is a good systems-thinking example.
- **Check the library, not just the datasheet:** the chip has 8 channels, but the driver may batch them 4 + 4. The design was sized to survive that case (24 % margin).
- **Why not the counter chips:** the LEDs are addressable, so routing happens *in the data*. Extra logic would have broken the 400 ns timing.
- **Why straight strips:** a helix that makes each LED step exactly one column would be 24.8° on this drum. That is a big spiral, so straight strips with a per-strip phase offset (9 columns per 45°) are simpler to print and to code.
- **Engineering sanity checks:**
  - Drag is negligible (skin friction only, 0.08 W).
  - The motor is sized by spin-up (36 mN·m), with margin to ≈1 kg·cm.
  - The real mechanical risk is unbalance: one missing strip is 5.7× the ISO G6.3 limit, so symmetry does the balancing.
- **Camera physics:** the shutter must integrate one full refresh (1/30 s). A fast shutter reveals the trick.
- **A sealed spinning device means OTA first:** once balanced, the rotor can't be opened for a USB cable. Over-the-air updates and a browser UI (served by the device itself, with the conversion done in phone JS) are design requirements, not extras.
- **Closed loop vs open loop:** the hall sensor measures speed, so the cheap DC gearmotor is as good as a stepper. Sensing beats precision actuation, the same idea as feedback control in a process plant.

---

## 13. Open decisions for Brian

Decided and removed from this list: 160 mm diameter, 8 strips, ~450 RPM. **Strip angle: straight vertical strips** (Brian, 2026-11-01, after seeing the CAD; the helix stays a styling option only).

**Also answered by Brian on 2026-11-01** (recorded in `2026-11-01-cad-build.md` and the parts order): **8 strip slots** (no 16-position rails, so #3 is no), **printed base** with the PWM controller and a 12 V jack (#6), **WS2812B** strips he owns (#5), and the **INIU power bank** on the rotor sled from the parts order (#1). Still open: #4 publish day and #7 Wi-Fi v2. The list below is kept as written.

1. **Power:** Option B (2×18650 shield, ~4.1 h, recommended) or Option A (1×18650 bank, ~2.3 h, simpler)?
2. **Strip angle:** straight vertical strips (recommended) or the 24.8° helix look?
3. **Future-proof the tube:** print rails for 16 positions now so a 16-strip v2 (Appendix B) needs no reprint? Recommended yes; it costs ~6 g and nothing in print time.
4. Publish Friday 11-06 or Saturday 11-07?
5. Keep WS2812B for the story, with SK9822 in reserve, or go straight to SK9822 for photo-quality images?
6. Base: printed, or a walnut block from the shop?
7. Wi-Fi v2 (after Friday): phone RPM control via a base ESP32 + ESP-NOW, a Brain Dump App tab, and/or the "Claude, show 'subscribe'" hook?

---

## Appendix A. The original 80 mm design (superseded 2026-11-01b)

The first version of this report recommended the design below. It is still valid, and every number comes from the `ORIGINAL` block of `calc/feasibility_calc.py`.

| Item | 80 mm design |
|---|---|
| Column | Ø80 × 240 mm, 2 mm PLA wall, black |
| Strips | 4 × 14 LEDs (56), **helical at 12.1°** in 10 × 1 mm grooves (one LED = one column at M = 72), vertical step 16.3 mm, 2+2 interleave, 28 rows at 8.15 mm |
| Speed / refresh | 900 RPM (15 rev/s), K = 2, 30 Hz |
| Columns | 72/rev, 3.5 mm arc, t_col 926 µs vs 700 µs line update (24 % margin) |
| Loads | 36 g at the strips, 3.77 m/s, hoop stress 17.6 kPa, I ≈ 3.5 × 10⁻⁴ kg·m², KE 1.6 J, spin-up 11 mN·m, drag 0.5 mN·m |
| Electronics | ESP32, 4 data lines (RMT), one 74AHCT125, A3144 hall |
| Power | 1×18650 on-axis power bank, 0.51 A typical, ~4 h |
| Motor | 12 V ~1000 RPM gearmotor, ≥ 30 mN·m |
| Balance | G6.3: e = 67 µm, U ≈ 26 g·mm |

Why it was superseded: Brian preferred a larger, more legible image and a slower, calmer rotor. The 160 mm design keeps the pixel count and refresh, doubles the image width, halves the g-load and roughly triples the data-timing margin (62 % vs 24 %).

---

## Appendix B. A 16-strip variant at 160 mm (recommended as v2, not for Friday)

**Fit.** 16 strips × 10 mm channels = 160 mm of the 503 mm circumference (32 %), at 22.5° spacing. They fit with ~21 mm of black between strips. The strips use 3.73 m of the 5 m reel. A v2 that keeps Friday's 8 strips needs 8 more (1.87 m), and the remaining 3.1 m covers that.

| Variant (16 × 14 = 224 LEDs) | Rows (pitch) | K | RPM for 30 Hz | Columns | Data drive | Time per column update vs t_col |
|---|---|---|---|---|---|---|
| **B1. 4 sets, quarter-pitch** | **56 (4.17 mm)** | 4 | **450** | 128 (3.9 mm, aspect 0.94) | **I2S parallel, 16 lines** | 700 µs vs 1042 µs (**33 % margin**) |
| B2. 4 sets, quarter-pitch | 56 (4.17 mm) | 4 | 450 | 72 (pixels 1.7:1 wide) | RMT, 8 lines × 2 strips chained (28 LEDs) | 1120 µs vs 1852 µs (40 %); at 128 columns it fails (−8 %) |
| B3. 2 sets, half-pitch | 28 (8.33 mm) | 8 | **225** | 72 | Either | 700-1120 µs vs 3704 µs (≥ 70 %) |

- **Drive.** The classic ESP32 has 8 RMT channels, so 16 independent lines need the **I2S parallel-output driver** (FastLED's ESP32 I2S driver or NeoPixelBus's I2S parallel methods, both of which do 16 lines). Chaining 2 strips per RMT line works only at 72 columns.
- **Rows.** Quarter-pitch rows (4.17 mm) are tighter than the 5 mm LED body, so the image becomes vertically continuous. Sets go at z₀, +p/4, +p/2, +3p/4 on positions s mod 4. Each set of 4 strips sits at 90° and is self-balanced.
- **Speed option.** B3 instead keeps 28 rows and drops to **225 RPM**. That gives 4.5 g, 0.7 J, and an almost silent rotor, which is the "calm" option.
- **Power.** 1.69 A typical (8.4 W). On the 2×18650 shield that is 2.2 h, and the 2.5 A cap still holds (0.16 A per strip feed).
- **Level shifters.** 16 lines need **2 × 74HCT245** (8 channels each), or 4 × 74AHCT125.
- **Mechanics.** It adds 47 g; I = 2.6 × 10⁻³ kg·m², KE 2.9 J, spin-up 41 mN·m. The ≈1 kg·cm motor still covers it.
- **Data.** A 128-column frame is 86 KB: 3 frames in heap, 17 in flash. Animations get short.

**Recommendation:** build **8 strips for Friday** and treat 16 strips (B1, 56 × 128 at 450 RPM) as a **v2 / Video 3** "double the resolution" upgrade. It adds an I2S driver change, 8 more strips to wire and balance, and twice the current. None of that belongs in a one-week schedule, but all of it is a natural follow-up episode. Printing rails for 16 positions now (decision 3) makes v2 a strip-and-firmware upgrade with no reprint.

---

## References / equations used

- Data time: t = 24 bit / 800 kHz × n + t_reset (WS2812B and WS2812B-V5 datasheets, Worldsemi).
- POV refresh f = K·f_rot. Column time t_col = 1/(f_rot·M). Helix one-column condition sin α = Δθ·R/p.
- ESP32 (classic) Technical Reference Manual, RMT chapter: 8 channels. ESP32-S3/-S2/-C3 TRMs: 4/4/2 TX channels.
- Rotating-cylinder skin friction: Theodorsen & Regier (1944), NACA Report 793. Disc moment C_m = 3.87·Re^−0.5 (von Kármán, laminar).
- Balance quality: ISO 21940-11 (formerly ISO 1940-1), G = e·ω.
- Thin rotating ring hoop stress σ = ρ·ω²·R².
- Calculation script: `calc/feasibility_calc.py` (prints the chosen design, the 16-strip variants and the original design; reproduces every number in this report).
