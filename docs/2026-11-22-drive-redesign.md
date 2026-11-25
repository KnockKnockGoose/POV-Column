# POV LED Column drive review: why rev o couldn't run, the bearing grease that caused it, and what to build next

**Prepared for Brian** · Claude (Opus 5.5), drive-redesign agent on the desktop PC · 2026-11-22
Inputs: your brief of 11-22 (a clean-sheet review of the rotor drive and support), the Main session's relays of 11-22 (direct drive to be weighed seriously; pins shortened, ~3 pops per turn; belt pulled as tight as possible: no skips at ~650 mA; the 6820 would not coast even before it was epoxied; **shields out = no change; grease flushed with IPA and the bearing lightly oiled: ring + plate 165 mA**), `docs/measurements.md` (11-19 to 11-22), the rev j / k / m / n / o reports, `docs/2026-11-21-rev-o-concentricity.md`, `fusionclaude/lib/povlib.py` (rev k to rev o blocks), the firmware's hall scheduler (`lib/povcore/povsched.h`), the SKF frictional-moment model (constants read from SKF's PDF today), and live part listings (section 8).
Outputs: this report (+ `.html`), `calc/revp_drive_redesign_calc.py` (+ `.json`, `_output.txt`), `calc/revp_figures.py`, `docs/img/revp_drag_before_after.png`, `docs/img/revp_power_vs_speed.png`. No CAD: the recommendation reuses the rev o parts you've built (section 6). Nothing was printed, ordered or emailed. The Fusion document was not opened.

---

## Abstract

The rev o drive could not run because the rotor's load was four to five times what the drive was designed for, and nearly all of it was the factory grease in the 6820. From the motor current, the rotor needed about **0.10-0.15 N·m** at 130-155 rpm with the board and battery on. The drive was sized for 29 mN·m. At 142 rpm that is **1.9 W, the JGB37-520's entire maximum output at 12 V** (fitted from your own bench points: R ≈ 11 Ω, 540 rpm no-load), so the speed collapsed to the motor's power peak, and no gear ratio could have fixed it. The same torque put about **10 N of effective tension** on a belt whose slack side goes slack above 6-10 N at finger tension (that happens when the effective tension exceeds twice the installed tension). The 20T's nine engaged teeth then ratcheted: the pops, whose count changed with tension, and the skipping. Pulling the belt as tight as possible stopped the skips but loaded the single 6802 and the hanger with 30-40 N. The SKF model gives 37 mN·m for this bearing with *run-in* grease. A fresh, full factory fill churns about three times that. Contact seals would have been worse (SKF's RS1 constants give 0.66 N·m for this size), but yours is ZZ, and removing the shields changed nothing. **Flushing the grease with IPA and oiling lightly (11-22) dropped the ring + plate to 165 mA, inside the 124-180 mA the drive draws with no rotor.** The model predicts about 17-22 mN·m for the full oiled rotor at 225 rpm (6-8 times less), which puts the operating point at about 240 rpm at full knob. **Recommendation: keep rev o as built, with the degreased 6820, a belt-tension spec and an oiling routine, and prove it with the full-rotor test in section 5.** Direct drive (a hollow-shaft stepper with the capsule slip ring under it) is the ranked fallback if that test fails. It costs $30-45, but the motor is backordered about two weeks.

## 1. Summary

1. **Root cause: the 6820's factory grease, not the drive design.** The torque was measured as motor current above the base, and the numbers agree three ways: the motor model, the SKF bearing model, and the 11-22 flush (section 3).
2. **Why it showed up as a drive problem:**
    - **The motor.** It ran out of power. 0.125 N·m at 142 rpm is all 1.9 W it can make at 12 V.
    - **The belt.** It ran past its slack-side limit and ratcheted: the pops and the skips.
    - **The pins.** They carried 15.6 N, and their 0.5 mm play turned every load swing into a knock.
    - After the flush, those three loads fall to about 0.4 W, 3 N and 3 N.
3. **Option 1, recommended: keep rev o** (cup v2, 6802 hub, belt, pins, option D) with:
    - the oiled 6820;
    - a belt tension of **5-8 N per strand** (2 N at mid-span moves it 2-3 mm), not "as tight as possible";
    - an oiling routine (section 5.4);
    - the battery out as soon as the pogo pins arrive (11-23). With it on, the unbalance moment at 225 rpm can reach 75 % of what lifts one side of the bearing.
    - It needs no new parts.
    - Optional: a 6802ZZ in the hub. Its 6802-2RS seals now make about half of what's left of the drive's drag.
4. **The full-rotor test decides it** (section 5.3; predicted 0.19-0.26 A and 230-250 rpm at full knob). Its main unknown: on 11-19 the board and battery added 60-80 mN·m. If that was grease churning it will be gone. If it was a rub or the battery's unbalance, it will still be there.
5. **Fallback if it fails: direct drive, hollow-shaft NEMA 17 stepper**:
    - the 12.5 mm capsule slip ring under the motor, keyed to its hollow shaft;
    - a printed Oldham to two of the rotor's existing pins;
    - the rev o contact head and pogo pins on the motor's hub;
    - exact speed with no knob drift (the motor turns in steps, so its speed is set by the step rate, not the load), and no belt;
    - $30-45. The motor is backordered: StepperOnline estimates Dec 1-7, Amazon Dec 14.
    - Direct drive was never dropped for a drive reason. Rev j wobbled because of its *support*, which the 6820 has since fixed. Rev m moved the motor only to free the axis for the slip ring.
6. **What would not help:**
    - a bigger belt or a tighter belt;
    - a friction idler (the JGB37 is too slow for any ratio that fits inside the spigot);
    - pogo pins sliding on face rings (they would wear through in tens of hours);
    - a motor on top (a gantry in every shot);
    - replacing the 6820 with a small bearing pair (1.3-3 mN·m against the oiled 6820's 12-18, but a whole new support for a 10-15 mN·m gain).

![The drag at the rotor, from the motor current above the base: 34-62 mN m bare and 98-160 mN m with the board and battery while the 6820 held its factory grease, against 0-12 mN m for the ring and plate after the flush and a predicted 17-22 mN m for the full oiled rotor; the dashed line is the 29 mN m the rev k-o drive was designed for](img/revp_drag_before_after.png)

## 2. What the bench showed (11-19 to 11-22)

| Date | Setup | 12 V current | Rotor rpm | Notes |
|---|---|---|---|---|
| 11-19 | bare rotor, old ring | 327 mA | - | no board, no rpm |
| 11-19 | + board + battery, old ring | 660 mA | 115-120 | popping |
| 11-20 | motor alone, belt off | 122 mA | (540 at the motor) | slow-mo |
| 11-20/21 | base + belt + hub, no rotor | 124-180 mA | - | runs smoothly |
| 11-21 | rotor + board + battery, rev o | ~600 mA | 130-155 (video) | 2 pops per turn at fixed angles; ±10-15 % speed within a turn; one-pin run still pops |
| 11-21 | rotor on the 6820, pins out, flicked | - | - | stops almost at once |
| 11-22 | after the alignment pass | - | - | belt skips badly; pins shortened: **~3 pops per turn** |
| 11-22 | belt pulled as tight as possible | ~650 mA | full speed? (no reading) | skipping stops |
| 11-22 | 6820 loose, before epoxy (recalled) | - | - | flicked inner ring stops at once |
| 11-22 | **ZZ shields removed in place** | - | - | **no change**: they weren't rubbing |
| 11-22 | **grease flushed with IPA, light oil; ring + plate, no tube, no battery** | **165 mA** | full speed (no reading) | **spins freely** |
| next | **full rotor** (section 5.3) | | | pending |

## 3. Root-cause assessment

### 3.1 The motor, fitted to your bench

Two of your points fix a straight-line DC motor model at 12 V:

- 540 rpm at 0.122 A, motor alone (11-20);
- 234 motor rpm at 0.66 A through the 2:1 belt (11-19).

The model, n = (V − IR)/k (`calc/revp_drive_redesign_calc.py` §B):

| Quantity | Value |
|---|---|
| Armature resistance R | **11.2 Ω** (stall current 1.07 A) |
| Back-EMF constant k | 19.7 mV/rpm (Ke 0.188 V·s/rad at the gearbox output) |
| Torque per amp above no-load, at the rotor (2:1 belt, 95 %) | 0.23-0.30 N·m/A (gearbox efficiency 0.65-0.85, ASSUMED) |
| Stall torque at the rotor | 0.22-0.29 N·m |
| **Maximum mechanical output** | **1.9 W at 270 motor rpm = 135 rotor rpm** |

It reproduces the two runs it wasn't fitted to:

- **Rev j, 11-14:** 188 rpm on 5.07 V at exactly the no-load current. The rotor sitting on the shaft needed almost no torque.
- **11-21:** 0.600 A predicts 134 rpm; the video gave 130-155.

### 3.2 The load, before and after the flush

Torque at the rotor = (current − base) × torque per amp. The base is 124-180 mA.

| Case | Current | Torque at the rotor |
|---|---|---|
| bare rotor, fresh grease (11-19) | 327 mA | 34-62 mN·m |
| rotor + board + battery (11-21) | 600 mA | **98-145 mN·m** |
| belt as tight as possible (11-22) | 650 mA | 109-160 mN·m |
| **ring + plate after the flush (11-22)** | **165 mA** | **0-12 mN·m** |
| design budget, rev k to rev o | | 29 mN·m (27 "air" + 2 bearing) |

**Before: about 0.125 N·m at 142 rpm is 1.86 W at the rotor, 1.96 W out of the motor: all of its 1.9 W.** That is why the speed sat at the power peak (figure 2). **A gear ratio trades speed for torque at constant power, so no ratio could have reached 188 rpm with that load.**

**The air is not the load.** A skin-friction estimate plus form drag on the 48 rails and 336 LED bumps gives **2-3 mN·m at 188-225 rpm**. Rev j's no-load current at 188 rpm confirms that. The 27 mN·m in the old budget was a very conservative guess, and the bearing term it did carry (2 mN·m, μ·P·d/2) left out the viscous rolling drag that dominates a lightly loaded large bearing.

![Mechanical power at the rotor against rotor speed: the JGB37's power curve at 12 V through the 2:1 belt peaks at about 1.7-1.9 W near 135 rpm; the factory-grease load line (0.125 N m) crosses it at that peak, which is where the column ran (130-155 rpm); the oiled load (about 0.020 N m) crosses near 240 rpm, above both target speeds](img/revp_power_vs_speed.png)

### 3.3 The bearing, by the SKF model

M = φ_ish φ_rs G_rr (ν n)^0.6 + G_sl μ_sl + M_seal (N·mm = mN·m).

- **Geometry:** SKF table 2a, 618 series: R1 4.7 × 10⁻⁷, R2 1.7, S1 6.5 × 10⁻³, S2 0.78.
- **Rolling variable:** G_rr = R1 d_m^1.96 (F_r + R2 F_a / sin α_F)^0.54, with α_F = 24.6 (F_a / C0)^0.24 °.
- **Inputs:** d_m 112.5 mm; F_a 8.7 N (full rotor), 10.6 N (+ battery), 2.0 N (ring + plate); F_r 1 N.

| 6820 drag, mN·m | 150 rpm | 188 rpm | 225 rpm | 250 rpm |
|---|---|---|---|---|
| run-in grease, base oil ν 150 mm²/s | 35 | 39 | 42 | 44 |
| run-in grease, ν 250 | 45 | 49 | 53 | 55 |
| **light oil, ν 15** | **10** | **11** | **12** | **13** |
| **light oil, ν 30** | **14** | **16** | **18** | **19** |
| light oil ν 30, + battery | 16 | 18 | 20 | 21 |
| light oil ν 30, ring + plate | 8 | 9 | 10 | 10 |

**Fresh grease.**

- The measured 100-130 mN·m is **2.7-3.5 times** the model's 37 mN·m for run-in grease at 142 rpm.
- That is the churning of a full, fresh factory fill, which the model doesn't include. It drops a little with run-in but never to the oiled level.
- A flicked inner ring on its own (about 100 g, I ≈ 2.7 × 10⁻⁴ kg·m², tens of mN·m of fresh-grease drag even unloaded) stops within about a tenth of a turn. That matches "it would not coast" even before the epoxy.

**After the flush.** Light oil (ν ≈ 25 mm²/s at room temperature) gives **16 mN·m at 225 rpm** for the full rotor, **6-8 times less**. Two effects multiply:

- the churning goes;
- the viscosity term drops as ν^0.6.

**Check against 11-22.** For the ring + plate the model gives 8.8 mN·m, about 33 mA over the base. You read 165 mA against a 124-180 mA base. They agree.

**Seals.** SKF table 3, deep-groove ball bearings, RS1 seal, D > 100 mm: M_seal = 0.018 d_s^2.25. With d_s = 106.6 mm:

- **a 6820-2RS would add 0.66 N·m**, and this motor could never have turned it;
- ZZ shields don't touch the inner ring, and your 11-22 test shows that;
- **the hub's 6802-2RS** (RS1, D ≤ 62: 0.023 × 17.9^2.25 + 2) costs **17 mN·m at the hub**. That's already in the base current, but with the 6820 oiled it is now **about half of all the drive's remaining drag.**

**Small bearings instead (Main's question).** Two small bearings on a spindle, the rotor on one and the other preloaded with 10 N:

| Pair | Greased | Oiled |
|---|---|---|
| 2 × 6002ZZ | 3.1 mN·m | 1.3 mN·m |
| 2 × 608ZZ | 1.3 mN·m | 0.6 mN·m |

Drag scales roughly with d_m², so a small pair is about 5-25 times lower than the oiled 6820. Getting that gain would take:

- a new support: a spindle or post, a 40-60 mm bearing span, preload, and a wide flange to carry the rocking moment out to the wall the way the collar does;
- a new answer for the axis.

That buys 10-15 mN·m. Not worth it for this column; it is the right call for a later product.

### 3.4 The belt (GT2, 20T / 40T, 122 mm, C 30.33)

**Geometry:**

- pitch radii 6.37 / 12.73 mm;
- free span 29.7 mm;
- wrap on the 20T 156°, so **8.7 teeth in mesh**.

**Effective tension:**

- **Before:** T_e = 0.125 / 0.0127 = **9.8 N**. The slack side goes slack when T_e > 2 T₀, so it went slack at any tension under 4.9 N per strand.
- Your finger tension ("~3 mm under a light push") is about 2.5-5 N. Running with a slack side, the 20T's teeth ratchet out under each load peak.
- **That explains the pops and their changing count.** They were 2 per turn, then ~3 when the pin length (and the tension) changed. A fixed geometric feature can't change its count. A ratchet threshold can.
- **"As tight as possible" stopped the skips** by raising T₀ above about 15 N. That puts 30-40 N sideways on a 5 mm-wide 6802 whose load sits 8-10 mm off its centre, and on the printed cup, hanger and motor bushing.
- **After:** T_e ≈ 3.1 N at the hub, including the 6802's seal drag. Any T₀ above 1.6 N keeps the slack side taut, so 5-8 N gives 3-5 times margin.

| T₀ per strand | 2 N push at mid-span moves it | Pluck tone (phone tuner, belt mass ASSUMED 7.5 g/m) | Side load on the hub's 6802 |
|---|---|---|---|
| 3 N | 4.9 mm | ~340 Hz | 6 N |
| **5 N** | **3.0 mm** | **~435 Hz** | **10 N** |
| **8 N** | **1.9 mm** | **~550 Hz** | **16 N** |
| 12 N | 1.2 mm | ~675 Hz | 24 N |
| 20 N | 0.7 mm | ~870 Hz | 40 N |

### 3.5 The pins and the knocks

- **Before:** **15.6 N** on the driving pin (0.125 N·m at r 8 mm). With 0.5 mm of play a side, any dip in the transmitted torque let the pin leave its wall and hit it again: the knocks on top of the ratchet.
- **After:** **3.1 N**.
- **Why the one-pin run still popped:** the pops weren't handover between pins.
- **Why rev o's pins are fine on a belt, and a direct drive would need something else.** A pin in a radial notch isn't constant-velocity when the two axes are offset by e: it forces a once-per-turn speed swing of ±e/r.
    - A belt and a 5 g hub absorb that.
    - A stiff direct drive would push it into the rotor as a torque ripple of J ω² e / r: **±27 mN·m at e = 0.1 mm and 225 rpm**. That is more than the whole oiled drag, so the pin would leave its wall every turn.
    - Hence the Oldham in the fallback (section 7).

### 3.6 The battery's unbalance (still open)

The rotor sits on the 6820 by gravity. One side of the bearing unloads when the tilting moment reaches W r_p / 2 = 10.6 N × 0.05625 m / 2 = **0.30 N·m**.

The battery 10-25 mm off-axis is U = 2,000-5,000 g·mm, against **240 g·mm for G6.3** (a standard balance grade) at 225 rpm. Its CG is about 81 mm above the bearing.

| U | 150 rpm | 188 rpm | 225 rpm |
|---|---|---|---|
| 2,000 g·mm | 0.040 N·m (13 %) | 0.063 N·m (21 %) | 0.090 N·m (30 %) |
| 5,000 g·mm | 0.100 N·m (33 %) | 0.157 N·m (53 %) | **0.225 N·m (75 %)** |

So at 225 rpm a carelessly placed battery can nearly tip the rotor on its seat. **Get it off the rotor (option D, pogo pins 11-23), then balance** (rev k §9, four-run method).

### 3.7 Ranked causes

| Rank | Cause | Evidence | Size | Status |
|---|---|---|---|---|
| 1 | **Fresh factory grease in the 6820** | current 600-650 → 165 mA after the flush; the SKF model with a ×3 churning factor; no coast even before the epoxy | 0.10-0.13 N·m of the 0.10-0.15 | **fixed 11-22** |
| 2 | **Motor power shortfall at that load** | 1.9 W needed = 1.9 W available; speed at the power peak | collapsed speed, ±10-15 % swings | gone with 1 |
| 3 | **Belt slack side, ratcheting** | T_e 9.8 N vs 2 T₀ ≈ 5-10 N; skips stop when tightened; pop count changed with tension | pops, skips | gone with 1, if T₀ 5-8 N |
| 4 | **Pin backlash under 15.6 N** | knocks; one pin still popped | noise, impact | 3.1 N after 1 |
| 5 | **Battery unbalance on a gravity-seated bearing** | 21-75 % of the tipping moment at 188-225 rpm | wobble, knock at high rpm | **open**: option D |
| 6 | 6802-2RS seal drag in the hub | 17 mN·m by SKF; in the base current | ~half of the remaining drag | optional 6802ZZ |
| - | ring fit, pin handover, hanger tilt, proud insert, shields | your 11-21 / 22 tests | none | ruled out |

## 4. Options, ranked

The options weigh support, drive and power together. The direct-drive variants and Main's power-transfer list (a) to (d) are in the table. Every option assumes the oiled 6820, because the oil fix is what made the load small.

| # | Option | What changes | Parts to buy | Print | Risk | Unknowns | Verdict |
|---|---|---|---|---|---|---|---|
| **1** | **Keep rev o, degreased 6820** (+ tension spec, oiling, option D) | nothing built changes | none (optional 6802ZZ $10-14, sewing-machine oil $6) | none (0.47 h if you swap the hub's bearing) | low | the full-rotor test; the 11-19 board + battery increment | **recommended** |
| 2 | **Direct drive, hollow-shaft NEMA 17 stepper** (TMC2209 + a Nano you have), capsule slip ring under the motor, printed Oldham, option D head on the motor hub | motor, hub, Oldham, slip-ring cradle; belt, 20T, hanger, cup, 6802, JGB37, PWM board retired | stepper $16-30, driver $11 | ~2 h (CAD first) | medium: a stepper on a 650:1 inertia; 12 V caps it at ~0.17 N·m | torsional mode ~9 Hz near 3 × 188 rpm; motor lead time | **fallback 1**: exact speed, no belt |
| 3 | Direct drive, solid NEMA 17 + 5 mm through-bore slip ring on its shaft (Main's c) | as 2, with a $24 two-day ring instead of the hollow motor | stepper $15, ring $24, driver $11 | ~2 h | medium-high: ring length unverified (product page blocked); needs a long shaft | ring dims, shaft length | fallback 2: if you can't wait for 2 |
| 4 | Direct drive with the JGB37 (rev k's Oldham) + battery, or + a DIY carbon-brush ring pair (Main's b) | motor back on the axis | brushes ~$8 | ~1.5 h | medium: brushes are DIY; speed droops ±20 rpm per ±5 mN·m | brush wear, ring runout | quick test rig only |
| 5 | Friction idler on the spigot bore (rev o axis kept) | wheel + spring arm replace the belt | a 1000-rpm gearmotor ~$15 | ~1 h | medium: slip, wear, preload | idler ratio forces 590-755 motor rpm for 225 | not worth it |
| - | Pogo pins sliding on face rings (Main's b) | | | | **high**: 1.3-2.1 km of sliding an hour; gold gone in minutes | | rejected |
| - | Motor on top (Main's d) | a gantry over the tube | | | in every shot; the tube's top isn't a support | | rejected |
| - | Small bearing pair replacing the 6820 | new support, spindle, preload | ~$10 | 4-6 h | medium | | rejected for this column (section 3.3) |
| - | Wireless power, motor on the rotor | | | | ≤ 1.8 A; rotor mass and balance | | rejected (rev m §3) |

**Main's power-transfer options for direct drive, in detail:**

- **(a) Hollow-shaft motor.**
    - A hollow-shaft stepper works open loop, and its leads pass a ~4 mm bore. That's fallback 1.
    - A hollow-shaft gimbal BLDC (GBM4108H class) would pass the leads too, but it needs field-oriented control with an encoder. Run open loop, its 7 pole pairs give only ~1 N·m/rad of stiffness, a ~2.5 Hz mode right on the spin frequency.
    - Hollow-shaft geared DC motors aren't sold at hobby scale.
- **(b) Static pogo pins on concentric face rings:**
    - **Current is fine:** 1.4 A at most on 12 V, 0.7 A a pin with two in parallel, inside the 0908's 2 A.
    - **Bounce and contact noise don't matter.** They only reach the 12 V feed, which the buck and its input capacitors ride through. No LED data crosses the joint: the ESP32 is on the rotor.
    - **Wear rules it out.** At r 15-25 mm and 225 rpm each plunger slides 1.3-2.1 km an hour. The 0.76 µm gold is gone in minutes, and Archard wear (k 10⁻⁵-10⁻⁴) eats the 1.4 mm stroke in tens of hours.
    - Carbon brushes on brass rings are the sliding contact that works: about 18 mN·m of drag for four at r 12 (option 4).
- **(c) Through-bore slip ring round the shaft:**
    - 12.7 mm-bore rings run $154-306 with a 54-56 mm OD, delivered Dec 14-16.
    - The 7 mm and 10 mm bores (33 mm OD) are $64-68, two-day.
    - The **5 mm × 22 mm** one is $24, two-day: the only cheap one that fits (fallback 2).
- **(d) Motor on top:** rejected. A gantry over the tube shows in every shot, and the top cap isn't a support.

**Why the project left direct drive, and whether the reason still applies:**

- **Rev j** hung the 0.93 kg rotor on the gearmotor's 6 mm shaft. The bracket, post and deck gave 46 N·m/rad plus bushing play, a rocking mode at 7.6 Hz, which is twice the spin at 225 rpm. The result was 3-5 mm of wobble at the top. **That was a support problem.**
- **Rev k** (11-09) fixed it with the 6820 and kept direct drive through a printed Oldham. **It was designed, but never built or run.**
- **Rev m** (11-13) moved the motor off-axis only to free the axis for the slip ring.
- **So:** the rocking cause is gone for good (the 6820), and the axis conflict is the only real constraint. A hollow-shaft motor removes it.
- **With the oiled load**, the JGB37 itself would do direct drive (439 rpm at 12 V for 25 mN·m). But it droops about 4,000 rpm per N·m, so ±5 mN·m of drag drift is ±20 rpm, which is useless for filming sync. A stepper doesn't droop at all.

## 5. Recommended design: rev o as built, degreased 6820 (Option 1)

### 5.1 Parts

| Part | Status |
|---|---|
| 6820ZZ in the collar, **flushed with IPA, lightly oiled** | done 11-22 |
| ZZ shields | **refit if they came out intact** (proven non-contact: no drag, and they keep dust out and oil in); if bent, leave them off (section 5.4) |
| Rotor ring (100.80, ~0 runout), plate, core, pins (shortened rods), nut plate v2 | as built |
| Cup v2, 6802-2RS, j15.10 hub, 20T, 122 mm belt, hanger, JGB37, PWM board | as built |
| Option D: mast, slip ring (new, uncut leads), bracket, contact head v2, M4 washer, M2 slug, 3 Mill-Max pins | slip ring here; pins and washers 11-23 |
| **Optional:** 6802ZZ in a fresh hub (`revo_drive_hub_j15p10_PETG-CF`, 0.47 h, already sliced) | −17 mN·m at the hub: ~+10-15 rpm at full knob; worth it if 225 rpm is short of margin |
| Oil | the oil you used if it's a light, plain mineral or sewing-machine oil; else the needle-tip bottle in section 8 |

### 5.2 Fits and settings

| Item | Setting | Why |
|---|---|---|
| Belt tension | **T₀ 5-8 N per strand: 2 N (a 200 g push on a kitchen scale) at mid-span moves it 2-3 mm** (pluck ~430-550 Hz on a phone tuner) | 3-5 × the 1.6 N the oiled load needs; 10-16 N on the 6802 instead of 30-40 |
| Rotor ring in the 6820 | sliding, as now (§6.3 pass) | the inner ring carries rotating loads: sliding fit by the textbook rule |
| Oil | **4-6 drops** round the gap between the rings, 10 turns by hand, wipe the faces | a film, not a fill: ~2 % of the ~14 cm³ free volume. A fill churns like the grease did |
| Knob | 188 rpm at ~80 %; 225 near full | predicted 230-250 rpm at full knob |

### 5.3 Bench test plan with pass limits

Write every reading into `docs/measurements.md`. rpm: hall over Wi-Fi, or 240 fps slow-mo (rpm = 144,000 / frames for 10 turns).

| Step | Do | Pass | If it fails |
|---|---|---|---|
| 1. Base | belt at the 5.2 tension, rotor off, 12 V full knob | **≤ 0.18 A**: record as the baseline B | > 0.18 A: belt too tight, cup not centred (jig v3), or the 6802 |
| 2. Ring + plate | done 11-22: 165 mA | ≤ B + 0.04 A ✓ | |
| 3. **Drive torque check, before the rotor goes on** | ring + plate on, full knob. Wrap a thin cord **two full turns** round the plate's skirt (r ≈ 84 mm) or the ring's rim (r 91). Tie one end to a kitchen or luggage scale held still, on the side the rim moves toward (if it reads nothing, swap ends). Pull the other end gently, so the cord works as a band brake. With two turns nearly all of the scale's pull is brake torque: T ≈ F × r | **at 1.1-1.2 N on the scale (0.10 N·m = 4-5 × the oiled full-rotor load) the belt does not skip**. Note the current (~0.5 A expected) and the speed (~155 rpm): they check the motor model | skips below 1.1 N: raise T₀ toward 8 N and repeat. A stall with no skip is fine |
| 4. **Full rotor** (tube, board, battery strapped flat as close to the axis as it goes) | 12 V, full knob, 1 min | **≤ B + 0.12 A (predicted B + 0.06-0.09), ≥ 215 rpm, no skip, no pop** | current high: was the 11-19 board + battery increment a rub? Marker on the magnet top, riser and collar rim; 5 turns by hand. Pops at speed but not slow: the battery (3.6) |
| 5. 188 rpm soak | knob to 188, 30 min | current steady within ±10 %; motor warm, not hot; 0 rejected hall pulses, ≤ 1 resync a minute; no pops | creeping current: oil migrating out; re-oil 2 drops |
| 6. 225 rpm | 5 min | as step 5 | short of 225: 6802ZZ hub (5.1) |
| 7. Option D (pins 11-23) | battery out, buck on the pogo contacts | step 4 again: ≤ B + 0.10 A | |
| 8. Balance | rev k §9 four-run method | top-edge orbit visibly smaller | |
| 9. Reference | note the step 5 current at 188 rpm | this is the oiling baseline (5.4) | |

**What "passes" means for the decision:** steps 3-6 pass → **build nothing new; rev o is the drive.** Step 4 fails on current with no rub to be found, or the pops persist with the battery off → go to fallback 1 (section 7).

### 5.4 Lubrication and maintenance (open, oiled 6820)

- **Oil:** a light, plain, non-detergent oil:
    - sewing-machine oil, Liberty Oil, or light mineral oil (food-grade is fine);
    - ν about 15-45 mm²/s at room temperature (ISO VG 10-22);
    - **not** grease (the cause of all this), **not** WD-40 (a solvent that leaves almost no film), **not** a heavy motor oil (ν ≈ 100 doubles the drag).
- **Amount:** 4-6 drops after a flush; 2 drops to top up. Over-oiling brings back the churning.
- **Where the oil goes:** at 225 rpm the turning inner ring pushes oil outward at about 3 g, into the races and toward the outer ring. Wipe any that reaches the collar's shoulder. PETG and PET-CF don't mind mineral oil.
- **When to re-oil:** whichever comes first:
    - the step 5 current at 188 rpm rises **more than 0.03 A** above its baseline;
    - the bearing sounds dry or gritty;
    - monthly, or about every 20 h of running.
- **Dust:**
    - with the shields back in, normal indoor use is fine;
    - open, the rotor ring 1 mm above and the collar round the outer ring make a fair labyrinth;
    - cover the base when it's stored, and never run it near sanding;
    - if it turns gritty: IPA flush, dry, re-oil.
- **Coast reference:** after each oiling, with the pins out, flick the rotor by hand and count the turns until it stops. Re-oil when the count halves. For scale: from 188 rpm the oiled full rotor would coast about 4 s and 6 turns, against about 1 turn with the old grease (§J of the calc).

### 5.5 What carries over from rev o

**Everything.** The recommendation keeps every part rev o built and everything arriving for option D:

- the slip ring, pogo pins, washers and contact head;
- the jigs: v3 for the cup, the pin jig for the rods;
- the hex-key and insert-relief fixes from the concentricity pass. They still matter for wobble, which is a support question, not a drive one.

## 6. CAD

No new CAD. The recommended design is the as-built rev o, and the optional hub reprint is already sliced (`cad/print/rev-o_CURRENT/revo_drive_hub_j15p10_PETG-CF`). The fallback's CAD is the next step only if section 5.3 fails, and is best drawn from the motor's own drawing when it arrives (section 7).

## 7. Fallback 1, if the full-rotor test fails: direct drive with a hollow-shaft stepper

**Architecture.**

- **Support:** the oiled 6820 (unchanged).
- **Motor:** a **17HS13-1504H** NEMA 17 (42 × 42 × 33.8 mm, hollow shaft, dual-ended, 0.25 N·m, 1.5 A):
    - face-up under the deck on a printed plate;
    - its shaft concentric with the 6820, set by a jig (as jig v3 does for the cup).
- **Power path:**
    - the 12.5 mm capsule slip ring hangs under the motor;
    - its boss is keyed to the rear end of the hollow shaft by a printed adapter;
    - its six uncut leads run up through the bore (about Ø4; six Ø0.6 leads make a Ø2 bundle) to the **rev o contact head**, on a printed hub on the front shaft;
    - the **rotor's pogo pins land on it unchanged**.
- **Torque path:** a **printed Oldham disc** (rev k) between the hub's two lugs and **two of the rotor's existing rods**. It is constant-velocity for any offset, so the ±27 mN·m forced ripple of section 3.5 never happens.
- **Drive:**
    - a TMC2209 in StealthChop (the silent, voltage-mode setting), 1/16 microstepping, about 1.2 A;
    - a Nano clone you have generates the steps with a 10-20 s ramp;
    - speed from the existing pot, plus a "187.5 rpm" preset: exactly 25.00 Hz refresh, no drift for the camera.

**Numbers** (`calc/revp_drive_redesign_calc.py` §K):

- **Torque:** pull-out ~0.17 N·m at 150-250 rpm on 12 V. That is 8-10 × the oiled load, but only 1.3 × the old greased one, so the oil fix is a precondition for this option as well.
- **Torsional mode:** the rotor's inertia on the stepper's magnetic stiffness gives **~9 Hz**, close to 3 × 188 rpm. Mitigations:
    - run 187.5 or 225 rpm, and ramp through 170-190 without stopping;
    - lower the current, which lowers the mode (it goes as √I);
    - add damping with TPU pads in the Oldham's grooves (you have TPU).
- **The bigger stepper:** the 48 mm 17HS19-2004S1 has 0.37 N·m at 225 rpm and a 13.8 Hz mode, but it is solid-shaft (fallback 2).
- **Stack:** with the 33.8 mm body, the slip ring and its lead bend end about 10 mm above the bottom plate. Check that against the motor's drawing before any CAD. **The 47.75 mm hollow motor doesn't fit under the deck.**

**What it retires:** the belt, 20T, 40T hub, 6802 and its 17 mN·m of seals, cup v2, hanger, JGB37, the PWM board (keep the pot), the mast and the bracket.

**What it keeps:** the rotor (with two of its four rods), the 6820, the collar, the contact head, the washer, the slug, the pogo pins, the slip ring, the hall and the 12 V supply.

**Bench proof before the rotor goes on** (same idea as 5.3):

1. **Motor alone, ring + plate:** a ramp to 225 rpm with no stall.
2. **Brake test:** the cord on the ring's rim must hold **0.10 N·m (1.1 N at r 91) without losing steps**.
3. **Dummy inertia:** the rotor with its tube and top cap but no sled, board or battery. The tube at r 80 is most of the rotor's 3.9 × 10⁻³ kg·m². Ramp 0-225 rpm and listen for growl or hunting at each 10 rpm step.
4. **Then the rotor.**

**Fallback 2 (Main's c):** the same drive with a solid 5 mm-shaft NEMA 17 and a **5 mm × 22 mm through-bore 6-wire ring** ($24, two-day) on the shaft below the hub.

- The Moflon MT0522 family this resembles is about 19 mm long and rated 250 rpm.
- That stack needs a shaft of about 40 mm. The common 24 mm shaft is too short.
- I could not read the Amazon page to confirm its length (a bot check), so check the length before buying.

## 8. Shopping list (live-checked 2026-11-22, 11:15-11:38 ET; nothing added to a cart)

**For Option 1 (both optional):**

| # | Part | Link | Price | Delivery shown | Why |
|---|---|---|---|---|---|
| 1 | Fine light sewing-machine oil, 1 oz, with a 1.5" needle tip (4.8★) | https://www.amazon.com/dp/B0B7B649XX | $6.03 | Overnight (free over $25 of qualifying items) | puts 2 drops exactly in the race gap; only if your oil isn't light and plain |
| 1b | Liberty Oil, clear non-staining, 4 oz (4.8★) | https://www.amazon.com/dp/B00AZM0IUK | $9.95 | Overnight (same terms) | alternative |
| 2 | **uxcell 6802ZZ, 15 × 24 × 5, double shield, 10 pcs** (4.7★, 291) | https://www.amazon.com/dp/B07H928Y7Z | $9.99 | FREE Tue Nov 24 (only 11 left); $13.50 offer for **tomorrow, Nov 23** (2 left) | hub bearing without seal drag: −17 mN·m |

**Only if you go to the fallback (don't buy yet):**

| # | Part | Link | Price | Delivery shown | Note |
|---|---|---|---|---|---|
| F1 | STEPPERONLINE 17HS13-1504H hollow-shaft NEMA 17 (0.25 N·m, 1.5 A, 33.8 mm, dual shaft) | https://www.omc-stepperonline.com/nema-17-hollow-shaft-stepper-motor-bipolar-0-25-nm-35-41oz-in-1-5a-42x42x33-8mm-17hs13-1504h | $15.93 | **backorder, ships from China, est. Dec 1-7** | the one that fits under the deck |
| F1b | NEMA 17 hollow shaft, 6 mm bore, 40 / 48 mm bodies | https://www.amazon.com/dp/B0FVSKY17F | $29.99 | FREE Mon Dec 14 | pick the 40 mm body |
| F2 | BIGTREETECH TMC2209 V1.3 stepper driver | https://www.amazon.com/dp/B08SMDY3SQ | $11.19 | FREE tomorrow, Nov 23 | StealthChop, standalone or UART |
| F3 | STEPPERONLINE NEMA 17, 2 A, 0.59 N·m, 48 mm (solid shaft) | https://www.amazon.com/dp/B00PNEQKC0 | $14.99 | Overnight (free over $25) | fallback 2 only (24 mm shaft: too short for the ring) |
| F4 | Taidacent through-bore slip ring, 6 wire, 5 mm bore × 22 mm OD | https://www.amazon.com/dp/B07XGK85Q5 | $23.92 | FREE Tue Nov 24 (only 4 left) | fallback 2; length unconfirmed |

**Not available fast:** McMaster's hollow-shaft NEMA 17s (6627T181 / T191) are $179-206, and the 63.5 mm one doesn't fit. No US eBay seller listed a hollow NEMA 17 today.

## 9. Open decisions for Brian

| # | Question | Why it matters |
|---|---|---|
| Q1 | The full-rotor result (5.3 step 4): current, rpm, pops, battery on or off? | it confirms Option 1 or triggers the fallback |
| Q2 | Did the ZZ shields come out intact? Refit them? | they cost no drag and keep the oil in and the dust out |
| Q3 | Which oil did you use (name, or roughly how thin)? | sets the drag (ν^0.6) and the re-oil interval |
| Q4 | Is 188 rpm (25p) enough, or do you need 225 (30p) with margin? | 225 sits near full knob; the 6802ZZ hub adds 10-15 rpm |
| Q5 | Battery out with option D tomorrow, then balance? | the battery is the last big risk at 225 rpm |
| Q6 | Order the fallback parts now ($30-45; the motor is ~2 weeks away), or only if step 4 fails? | lead time against $30-45 |
| Q7 | The ESP32's HTTP server timed out today: fix it, or use slow-mo for the bench plan? | the hall rpm is the best tachometer you have |

## 10. How to explain it

**The 30-second version:**

> I spent two weeks redesigning a drive that kept skipping and knocking, and the drive wasn't the problem. The big 100 mm bearing came packed with fresh grease, and at this light load a thin-section bearing's drag is almost all viscous churning. It was eating a tenth of a newton-metre, which at 140 rpm is two watts. That's every watt this little gearmotor can make. So the speed collapsed to the motor's power peak, and the belt, carrying four times its design load, ratcheted a tooth at a time. I flushed the grease out with alcohol and put in a few drops of light oil. The current fell from 650 milliamps to 165. The fix took twenty minutes and no new parts.

**Numbers that read well:**

- 600-650 mA → 165 mA;
- 0.125 N·m → ~0.02 N·m;
- 1.9 W needed and 1.9 W available;
- the SKF model's 37 mN·m for run-in grease against the measured 100-130 for a fresh fill;
- if the bearing had had rubber seals instead of metal shields, 0.66 N·m, and it would never have turned;
- 9.8 N on a belt whose slack side goes slack at 5 N;
- predicted 240 rpm at full knob after the fix.

**Talking points:**

- **Measure the load before you redesign the machine.** The motor current was a torque meter the whole time; the bearing was the one part never in the budget.
- **A gear ratio can't fix a power shortfall.** Check P = T ω against the motor's power curve before choosing a ratio. The operating point is where the load line crosses the curve.
- **A belt skips when its slack side goes slack** (T_e > 2 T₀), not when the teeth are weak. Set the tension from the torque, and measure it with a push gauge or a phone tuner.
- **Large bearings at light load:** budget the viscous term (SKF M_rr = G_rr (ν n)^0.6), not μ P d / 2. Degrease and oil them before assembly, and specify shields, not seals.
- **Rule things out cheaply and in order.** Shields out first (no change), then the grease (the whole problem): twenty minutes of tests before any print.
- **Keep the support and the drive separate in your head:** wobble lives in the support chain, noise and speed in the drive chain.

**Shots:**

- the grey grease coming out in the IPA;
- the ammeter before and after;
- figure 2, with the two crossing points;
- the bare ring spinning freely by hand;
- the belt-tension push test with a kitchen scale.

## 11. Files

| Path | What |
|---|---|
| `calc/revp_drive_redesign_calc.py` (+ `.json`, `_output.txt`) | every number here: the motor fit, torque by difference, the SKF model (6820, 6802, small pairs, seals), air drag, the full-rotor prediction, belt tension / deflection / pluck, pin ripple, battery moment, coast-down, fallback motors, pogo wear, oil |
| `calc/revp_figures.py` | the two figures |
| `docs/img/revp_drag_before_after.png`, `docs/img/revp_power_vs_speed.png` | figures 1 and 2 |
| SKF source | "The SKF model for calculating the frictional moment" (tables 1a, 2a, 3, 4), SKF media hub PDF |
