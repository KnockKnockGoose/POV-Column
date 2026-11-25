# POV LED Column: Parts to Buy, with Verified Amazon Links

**Prepared for Brian** · Claude (Opus 5.5), parts-sourcing agent on the desktop PC · 2026-11-01
Source of truth: `docs/2026-11-01-feasibility.md` (rev 2026-11-01b), Sections 3.3, 5, 6, 8.1, 10.1 and Appendix B. Owned items checked against `fusionclaude/shop/inventory.yaml` (item names only).
Deadline: parts on hand by **Tuesday 2026-11-03** for a Friday 2026-11-06 publish.

---

## Abstract

Every item in Section 1 was opened on its live Amazon product page on Sunday 2026-11-01 and was **in stock, shipped from Amazon, with delivery on Monday 11-02** (overnight or "tomorrow"). The Friday buy list is seven items for **$79.93 before tax**.

Two spec deviations came out of the live-page check:

1. **Motor torque.** No 500-600 RPM gearmotor in the JGB37-520 class meets the "≥ 1 kg·cm rated" line in Section 6. Their rated (continuous) load torque is 0.19-0.5 kgf·cm. The 1 kg·cm figure already includes a 2.5× margin over a 3 s spin-up. At 0.28 kgf·cm (27 mN·m) the motor still holds steady speed with about 10× margin and spins up in about 4-6 s. Section 5.2 has the arithmetic. Bigger motors (Pololu-type 18.8:1, JGB37-3530) arrive Nov 10-21, too late.
2. **18650 cells.** Amazon US does not list loose brand-name 18650 cells (Samsung, Molicel, LG). Searches return only chargers, NiMH cells and no-name wired packs. The recommended 2×18650 shield (Option B) therefore can't be completed from Amazon by Tuesday. The buy list swaps in a **10,000 mAh INIU power bank** (sold and shipped by Amazon.com, 2 × USB-A at 2.4 A). It gives about 6 h at the 4.5 W typical load. The shield stays as an optional add-on if you buy cells from a battery specialist.

---

## 1. Buy for Friday (8-strip build)

Sorted by how much the build depends on it. All checks were made on 2026-11-01 around midday ET. Delivery dates are as Amazon showed them then.

"Overnight 4-8 AM" applies to orders over $25. This order is $79.93, so those items arrive Monday 11-02 early morning.

| # | Need | Item (pack) | Link | Price | Delivery shown | Why it meets the spec |
|---|---|---|---|---|---|---|
| 1 | Motor | **Copkim 12V DC geared motor kit, 600 rpm**: JGB37-520 motor with bracket, CCM6N PWM speed controller, **2 × 6 mm flange couplings**, screws | https://www.amazon.com/dp/B0G12TFR5Z | $19.99 | **Tomorrow, Mon Nov 2** (cutoff was 55 min away when checked; after it, expect Tue Nov 3) | 12 V, 600 rpm no-load (450 RPM ≈ 75 % voltage), **6 mm D-shaft**, bolted 6 mm flange coupling included. Listing states 0.28 kgf·cm load torque, **below the 1 kg·cm spec** (see Abstract and 5.2). Sold by Liaeish, ships from Amazon |
| 1-alt | Motor | ZVKV 12V DC geared motor kit, 600 RPM 37GB-520: motor, PWM controller, 2 × 6 mm flange couplings, bracket, wrench | https://www.amazon.com/dp/B0GX9276FW | $19.99 | Tue Nov 3 (**only 4 left**) | Same class. States **0.5 kgf·cm load torque, 18 W max**, the best rated torque found at 600 RPM with fast delivery. Coupling bore 6 mm. Arrives a day later |
| 2 | Level shifter | **Bridgold 10 pcs SN74AHCT125N**, DIP-14 | https://www.amazon.com/dp/B08R6BCSYC | $7.99 | Tomorrow, Mon Nov 2 | Genuine **AHCT** part, with TTL-compatible inputs, so 3.3 V ESP32 data reads as HIGH at 5 V VCC. Not the HC part. 2 needed, 8 spare. Ships from Amazon |
| 3 | Hall sensor | **ALLECIN 20 pcs A3144 (OH3144 / AH3144E)**, TO-92, 3-pin | https://www.amazon.com/dp/B0CZ6QXMZ2 | $6.99 | Overnight, Mon Nov 2 | Unipolar digital switch with open-collector output. Run at 5 V (A3144 needs ≥ 4.5 V) with the 10 kΩ pull-up to **3.3 V**, so the ESP32 never sees 5 V. Ships from Amazon |
| 4 | Magnet | **rhinocats 80 pcs 6 × 3 mm** neodymium discs, Ni-Cu-Ni plated | https://www.amazon.com/dp/B0FMP58G7B | $7.49 | Overnight, Mon Nov 2 | Matches the ~6 × 3 mm spec. Set the sensor-to-magnet gap to 2-4 mm, and stack 2 discs if it misses at speed. The A3144 switches only on a **south** pole facing its branded face, so flip the magnet if it doesn't trigger. Grade not stated. Ships from Amazon |
| 5 | Rotor power | **INIU 10000 mAh 22.5 W power bank** (2 × USB-A, 1 × USB-C) | https://www.amazon.com/dp/B09176JCKZ | $22.99 | Tomorrow, Mon Nov 2 | Replaces the 2×18650 shield (no genuine cells on Amazon). USB-A output 2.4 A at 5 V covers the 0.90 A typical / 1.03 A peak load. Set the FastLED cap to **2000 mA** (not 2500). About 37 Wh nominal, so roughly 6 h typical. **Sold and shipped by Amazon.com** |
| 6 | Power lead | **Maixbomr 2 pcs USB-A male to 2-pin bare wire, 11"** | https://www.amazon.com/dp/B0BTXB9DF4 | $7.99 | Tomorrow, Mon Nov 2 | 22 AWG (AWM 2464, per the listing photo), rated for 5 V/3 A devices. It takes the bank's USB-A output straight to the 5 V bus ring. A USB-A port gives 5 V without negotiation. Ships from Amazon |
| 7 | Power switch | **uxcell 5 pcs KCD11 rocker**, SPST, 2-pin, 125 V/6 A, 250 V/3 A | https://www.amazon.com/dp/B07GNHMY3B | $6.49 | Overnight, Mon Nov 2 | The inventory has no slide switch. Common SS12D00 mini slides are rated only 0.5 A, too small for a 1-2 A bus. A KCD11 is rated ≥ 3 A. Ships from Amazon |
| | | **Total (items 1-7, one of each)** | | **$79.93** | | before tax; free shipping on all |

**If you want insurance on the motor:** add 1-alt as well (+$19.99, total $99.92). Then you have a spare motor and the higher-torque unit by Tuesday.

---

## 2. Owned - don't buy

Checked against the shop inventory (item names only).

| Part (feasibility 10.1) | Inventory match | Note |
|---|---|---|
| ESP32 dev board | ESP-WROOM-32 ESP32 dev board, 3-pack | Confirm the classic ESP32 with `esptool.py chip_id` |
| WS2812B 60/m 5 V IP30 black PCB, 5 m | WS2812B 5 V strip, 5 m 60/m IP30 black PCB | 1.87 m used |
| SK9822 60/m (fallback) | BTF-LIGHTING SK9822 5 m 30/m + 5 m 60/m, black PCB | Section 8.4 upgrade |
| Bench DC power supply | Bench DC power supply | Confirm ≥ 12 V, ≥ 1 A. The motor kit's PWM controller is a second speed option |
| CD4017 counters | CD4017 decade counter, 20-pack | **Not needed** |
| 1000 µF capacitor | ALLECIN electrolytic capacitor assortment, 24 values | Confirm a 1000 µF, ≥ 10 V part is in the box |
| 330 Ω ×8, 10 kΩ | BOJACK 25-value kit (likely resistors); SMD 0805 assortment books | Check that through-hole 330 Ω is present |
| 22 AWG wire | NAOEVO 22 AWG silicone stranded; TUOFENG 22 AWG solid | |
| Connectors | WEKESIGO JST/Dupont kit; Dupont crimper kit; 3-pin 10 mm LED strip connectors; screw terminals | |
| Protoboard | YUNGUI 15 × 20 cm; Rindion double-sided assortment | |
| Heat-set inserts | INCLY 440-pc M2-M6 brass kit | M3 for the flange coupling |
| M3 screws/nuts (and balance nuts) | NINDEJIN 880-pc M2-M5 SHCS kit | M3 nuts for the balance pockets |
| Black PLA | Bambu PLA Basic Black (×2); ELEGOO PLA Black | Tube + caps |
| CA glue, heat shrink, hot glue | Starbond CA; Ginsco heat-shrink kit; hot glue gun | Strip ends, joints |
| Second ESP32 for v2 base control | Same 3-pack | v2 only |

**Not in the inventory, despite the brief:** 18650 cells or holders, magnets, hall sensors, level shifters (only CD4017, NE555 and 2N2222) and a slide switch. All of them are in Section 1, apart from the cells, which are replaced by the power bank. The inventory's IRFZ44N MOSFETs are **not logic-level**, so the v2 ESP32 motor-control MOSFET still needs a part such as an IRLZ44N or a driver module.

---

## 3. Optional / nice to have

| Item | Link | Price | Delivery shown | When to buy |
|---|---|---|---|---|
| diymore V8 2×18650 battery shield, 5 V/3 A + 3 V/1 A, micro-USB charging (**2 holders**) | https://www.amazon.com/dp/B07SZKNST4 | $9.99 | Overnight, Mon Nov 2 | Only if you buy genuine cells elsewhere (see 5.1). Cells sit side by side, so the pair balances about the axis |
| FORIOT V8 dual 18650 shield, 5 V/3 A (1 board) | https://www.amazon.com/dp/B0CJQZ2CLS | $9.99 | Tomorrow, Mon Nov 2 | Alternative to the above. Listing states protection IC and up to 95 % conversion efficiency |
| Brand-name 18650 cells (Samsung 30Q / Molicel P28A-P30B / LG) | **Not available on Amazon US.** Search shown: https://www.amazon.com/s?k=Samsung+30Q+18650+3000mAh | - | - | **UNVERIFIED / not sourceable on Amazon.** Buy from a battery specialist instead |
| HiLetgo 5 pcs KY-003-style hall module (3144E), 5 V | https://www.amazon.com/dp/B01NBE2XIR | $5.99 | Overnight, Mon Nov 2 | Easier to mount, but the module pulls up to its own VCC. Power it from **3.3 V**, or remove its pull-up, before wiring it to GPIO 27 |
| VSKIZ 50 pcs 10 × 3 mm magnets | https://www.amazon.com/dp/B0BVY5VYQY | $9.99 | Tomorrow, Mon Nov 2 | Stronger field and more gap tolerance than 6 × 3 mm |
| AUWHEMITY 200 pcs 6 × 3 mm magnets | https://www.amazon.com/dp/B0GY3Z1KFD | $9.99 | Overnight, Mon Nov 2 | Alternative to item 4 |
| Vanxy 12 pcs SN74AHCT125N | https://www.amazon.com/dp/B0GHN5GY56 | $7.59 | Tomorrow, Mon Nov 2 | Alternative to item 2 (also ships from Amazon) |
| PWM DC motor speed controller | included in the motor kit | - | - | Nothing to buy |
| Slip ring | - | - | - | **Not needed.** Rejected in feasibility 5.3 (250-300 RPM rating) |
| Spare WS2812B / SK9822 strip | owned (white-PCB WS2812B 5 m reel, BTF ECO reels, SK9822 reels) | - | - | Nothing to buy |

---

## 4. v2 16-strip extras (Appendix B)

| Item | Link | Price | Delivery shown | Note |
|---|---|---|---|---|
| **Vanxy 10 pcs SN74HCT245N**, DIP-20 octal bus transceiver | https://www.amazon.com/dp/B0FPQZ1GZL | $7.99 | Tomorrow, Mon Nov 2 | **HCT**, not HC (listing B0HFCBH4GB is the HC part; avoid it). 2 needed for 16 lines. Tie DIR high and OE low. Alternative: 4 × 74AHCT125 from the item-2 pack, which already covers 16 lines |
| 8 more strips (1.87 m) | owned (3.1 m left on the black reel) | - | - | |
| Power for 1.69 A typical | INIU bank (item 5) at 2.4 A | - | - | About 3 h typical. Keep the 2000 mA cap |
| Logic-level MOSFET or motor-driver module for base control over ESP-NOW | not sourced here | - | - | v2 Wi-Fi speed control, Section 8.5 |

Buying the 74HCT245 pack now with the Friday order costs $7.99 and saves a later shipment. It's optional.

---

## 5. Notes on substitutions

### 5.1 Battery: power bank instead of the 2×18650 shield

- **Why.** Feasibility 5.2 says to buy brand-name cells from a reputable seller. Live Amazon searches for Samsung 30Q, Molicel, Nitecore, Tenergy and generic flat-top 18650s returned no loose brand-name cells, only chargers, NiMH AAs and no-name wired packs. Amazon US appears to restrict loose 18650 sales. A shield without trustworthy cells is not worth spinning at 18 g.
- **What changes.** The INIU bank, at about 37 Wh nominal and roughly 30 Wh delivered at 5 V, runs about 6 h at 4.5 W, longer than Option B's 4.1 h. Its limit is 2.4 A per port, against the shield's 3 A. Lower the software cap to `FastLED.setMaxPowerInVoltsAndMilliamps(5, 2000)`. The 0.90 A typical load is far below 2 A.
- **Mounting.** Strap the bank flat with its centre on the spin axis, held in a printed cradle that is captured on all sides. The symmetric case balances like the 2-cell shield did. Some banks switch off below about 50-100 mA, but the LED quiescent current alone is 0.11 A, so that isn't an issue. The bank's QC/SCP fast-charge modes need the device to ask for them, so bare wires stay at 5 V.
- **If you still want Option B,** order the diymore V8 shield (Section 3) and buy 2 genuine cells from a specialist battery retailer with 2-day shipping. Check its delivery date against Tuesday before ordering.

### 5.2 Motor torque: why a 0.28-0.5 kgf·cm motor is acceptable

- 0.28 kgf·cm = 27 mN·m and 0.5 kgf·cm = 49 mN·m, rated continuous.
- Steady state at 450 RPM needs about 1.8 mN·m of drag plus gearbox and bearing losses, so the margin is about 10× or more.
- Spin-up: t = I·ω / (τ − τ_drag) = 2.3 × 10⁻³ kg·m² × 47.1 rad/s / (27 − 2) mN·m ≈ **4.3 s** (2.3 s with the 0.5 kgf·cm unit). Ramp the bench-supply voltage over about 5-10 s rather than switching straight to 12 V. Start current then stays near the rated 0.6 A instead of the 1.65 A stall current.
- The 1 kg·cm spec in Section 6 was "36 mN·m for a 3 s spin-up, times 2.5". The only change is accepting a slower spin-up. Bigger options (Pololu-type 18.8:1 37D, JGB37-3530) were not deliverable before Nov 10.
- The motor's own listing lists no shaft load rating. The roughly 6 N axial load sits within what a 37 mm gearbox output bearing normally carries, but **don't add a side load**. Keep the rotor balanced and clamp the base.
- Avoid listing B0C7GN1VPD ("DC 12V 600 rpm Gear Motor with Bracket"). Its listing states a **5.5 mm** D-shaft, which won't fit a 6 mm coupling.

### 5.3 Other notes

- **Hall part.** Use the bare A3144 (item 3). Power it at 5 V and pull its output up to 3.3 V, as in feasibility 8.1. KY-003 modules work but pull up to their own supply (Section 3 note).
- **Switch.** A KCD11 rocker replaces the "mini slide switch". Typical SS12D00 slides are rated 0.5 A, while the bus carries 1-2 A. Mount the rocker near the axis so centripetal load on it stays small.
- **Level shifter.** Both 74AHCT125 listings name the SN74**AHCT**125N part. Don't substitute 74HC125, whose CMOS thresholds at 5 V need about 3.5 V input, the same marginal case the buffer is there to fix.
- **Prices and dates** are as shown on 2026-11-01 and can change. The motor kit's same-day cutoff was under an hour away when checked. Order everything in one cart so the overnight items qualify for the over-$25 rule.

---

## Explain it

- **"Verify the spec, not the title."** Every listing title said "high torque". Only the bullet text gave the real rated load torque, 0.19-0.5 kgf·cm, a factor of 2-5 below the design target. Working the spin-up equation (t = Iω/τ) turned an apparent failure into an acceptable trade: a few extra seconds of ramp. It's a good on-camera beat about checking datasheets against requirements.
- **Supply-chain constraints change the design.** Genuine 18650s aren't on Amazon, so the power design moved from a 2-cell shield to a commercial power bank. Runtime went up, current headroom came down, and one firmware constant changed.
