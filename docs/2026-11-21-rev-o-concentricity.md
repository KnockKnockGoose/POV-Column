# POV LED Column rev o: concentricity of the whole rotor chain, the pin-centring jig, and the two pops per turn

**Prepared for Brian** · Claude (Opus 5.5), rev o concentricity agent · 2026-11-21
Inputs: your bench state of 11-21 (pops at ~130-155 rpm, ~600 mA at 12 V, twice per turn at two fixed rotor angles ~145 / 215° apart, 20-40 ms each; still there with the tight 100.80 ring and with 4 threaded-rod pins 12 mm out; one hub-core insert found ~2-3 mm proud and re-seated; visible wobble after the re-seat), `docs/measurements.md`, the rev k / rev n / rev o reports, `fusionclaude/lib/povlib.py`, the part STLs in `cad/`.
Outputs: `cad/make_revo_rotor_pin_jig.py`, `cad/make_revo_concentricity_parts.py`, print files in `cad/print/rev-o_CURRENT/` (sliced, **not sent**). The Fusion document was not touched. Nothing was printed, ordered or emailed.

## 1. Summary

- **The part the pins go through is the hub core** (PET-CF, d45, the 4 heat-set inserts). **It does not sit on the rotor ring.** It sits on the **bottom-cap plate**: a d28.0 spigot in a d28.4 hole, plus 4 × M3 × 8 **countersunk** screws up from under the plate (r 18, at the pins' angles) into the core's inserts. The ring's bore is d94 and never touches the core. The ring is located on the plate by the 4 hex keys (5.85 AF in 6.0 AF pockets, r 72) and clamped by the 4 tie rods (r 60).
- **The pins (drive) and the wobble (support) are two different chains.** Pins only carry torque. Where they sit cannot tilt the tube, but it decides **which pin drives**. What the tube's axis follows is: the 6820's inner-ring face, the ring's land, the ring's top face, the plate, the tube's lip and end, and the tie-rod tension.
- **Best explanation for two pops per turn at two fixed rotor angles, not 180° apart (hypothesis, testable in 2 minutes):** the 4 pins sit in notches with **0.5 mm of play a side**. At any moment only one pin drives. Where each pin sits in its notch, together with a small hub-to-rotor axis offset that runs once per turn, decides which one that is. If **two pins share the drive**, the drive passes from one to the other **twice per turn, at fixed rotor angles**. Each handover is a small impact across the backlash.
    - For two adjacent pins, the handovers are 180° − 2·asin(Δc / (√2·e)) apart. Δc is the difference in the two pins' offsets in their notches; e is the axis offset. **145° needs only Δc ≈ 0.4·e**, for example 0.06 mm against 0.15 mm.
    - It explains why the tight ring and the longer pins changed nothing. The pops are louder at speed because the impact speed grows with rpm.
    - **Test: run with ONE pin** (take three rods out). One M3 rod carries the stall torque: 55 N, 172 MPa bending against 450 MPa yield (rev n §3.3). **If the pops stop, run one pin for good.**
- **Third candidate (from your coast-down, 11-21): the fresh 6820's ~0.1 N·m drag, which swings within a turn** (the video shows ±10-15 % speed). That would also explain most of the 600 mA. See section 4.
- **Second candidate: the rotor rocks on its seat.** The rotor is held down by gravity only: the ring's 2.2 mm land sits on the 6820's inner-ring face. A land that isn't flat (or a twisted plate-and-ring stack) gives a few high spots. A rotating load (unbalance grows with rpm², plus the pin force jumping between pins) then tips it from one rest to the other twice per turn, also at fixed rotor angles and not 180° apart. **Test: a 1-2 kg weight centred on the top cap.** If the pops start at a higher speed or stop, it's the seat.
- **The proud insert.** It cocked the core on the plate, so the pins tilted and their tips shifted, up to ~0.5 mm at 2° of cock. That is the same size as the notch play, so it fed the handover mechanism. **It can't cause a visible wobble of the tube**, because the core carries no rotor weight. The inserts sit at the pins' angles (45 + 90k°), so **the 145 / 215° spacing does not line up with them**: the spacing comes from the handover geometry, not from a feature passing a point.
- **What to do:** two quick tests, the pin jig as a gauge, then a measurement pass up the support chain with calipers and printer paper, each stage with a pass limit (section 6). **Print now: the pin jig (0.99 h) and the core + hex-key plate (0.92 h): 1.91 h, 31.5 g.** The cup and plate reprints are only for a failed check.

## 2. The print list

All on the H2D, **left (hardened) nozzle = extruder 1**, textured PEI, 0.2 mm, no supports. **No brim** on every file: `brim_type = no_brim` and skirt 0 in both 3mfs, no per-object brim keys, and 0 brim/skirt features in the G-code. **Island check (script 151): 0** on every STL.

| # | File (`cad/print/rev-o_CURRENT/`) | What | Material / process | Time | Mass |
|---|---|---|---|---|---|
| 1 | **`revo_rotor_pin_centring_jig_PETG-CF`** | pin-centring jig and go/no-go gauge (section 4) | Bambu PETG-CF, 4 walls, 4/4, 20 % (jig v3's process) | **0.99 h** | **17.0 g** |
| 2 | **`revo_core_and_keys_plate_PET-CF`** | hub core with insert relief + 15 hex keys (5 × 5.90 / 5.95 / 6.00 AF; 1 / 2 / 3 dimples) | Fiberon PET-CF (dry it), 5 walls, 6/5, 40 % (the core's original process) | **0.92 h** | **14.5 g** |
| 3 (if needed) | `revo_bearing_cup_v2_b24p10_relief_PETG-CF` | cup v2 at the coupon-picked d24.10, insert relief 0.3 → 1.0 mm deep | Bambu PETG-CF, 6 walls, 6/6, 85 % (the drive parts' process) | 0.39 h | 4.9 g |
| 4 (if needed) | `rotor_bottom_cap_o_relief_PETG-CF` | bottom-cap plate with insert relief on its 4 sled-boss inserts | Bambu PETG-CF, 6 walls, 6/6, 85 % (as your PETG-CF plate) | 2.28 h | 51.3 g |
| have | `revo_centring_jig_v3_PETG-CF` | cup centring (reuse) | | | |
| opt. | `optional/revo_rotor_ring_compliant_PET-CF` | compliant-spigot ring, only if the ring fails step 6.3 | Fiberon PET-CF | 3.13 h | 80.7 g |

**Order:** 1 → 2 (main path 1.91 h, 31.5 g). Print 3 only if a deck insert under the cup is proud and you'd rather not file it. Print 4 only if your plate fails step 6.4 or is dented where the insert sat. The single-core file from earlier today is superseded by plate 2.

## 3. The chain, joint by joint

"Tilts the rotor" means the tube's axis can end up at an angle to the spin axis (seen at the top). "Offset" means parallel eccentricity. Play is as drawn; printed holes come out smaller.

| # | Joint | Radial location | Axial / tilt location | Play as drawn | Heat-set inserts that can cock it | Visible wobble | Pops |
|---|---|---|---|---|---|---|---|
| B1 | deck → 6820 collar | 4 × M3 × 10 in holes (screws only) | collar plate flat on the deck | screw clearance | **4 × M3 × 4 in the deck** under the collar | **no**: a tilted or offset 6820 is still a fixed axis; the rotor spins true about it | no |
| B2 | collar → 6820 outer ring | 8 crush ribs (124.85) + epoxy | shoulder | 0 (glued) | none | no (fixed axis) | only if the epoxy let go |
| R1 | **6820 inner ring → rotor ring spigot** | 8 crush ribs: tight ring scraped to a sliding fit; old ring **very loose** | **land (r 50.6-52.8, 2.2 wide) on the inner-ring face, gravity only, not clamped** | tight ~0-0.03, loose ≫ 0.1 | none | **yes**: loose spigot plus unloaded land lets the rotor tilt within the clearance over 11 mm | **yes: rocking seat (candidate 2)** |
| R2 | ring land vs ring top face (wedge) | n/a | parallelism of two printed faces | print flatness | none | **yes**: tilt × 3.0 at the tube top (258 / 85) | via R1 |
| R3 | **rotor ring → bottom-cap plate** | 4 hex keys (5.85 in 6.0 AF, r 72); tie rods in d3.4 don't locate | faces clamped by 4 tie rods (r 60) and ring nuts | ~0.15 offset | none (nuts) | offset of the plate and tube; tilt if the rods pull unevenly | small |
| R4 | plate flatness (2 mm PETG-CF) | n/a | its own flatness under rod clamp | print / warp | | **yes**: tilt at the tube seat | |
| R5 | **plate → tube** | lip d156.4 in the d156.8 bore ("fits great", #36) | tube end on the plate | ≤ 0.2 offset | none | offset ≤ 0.2; tilt if the tube end isn't square or the rods are uneven | no |
| R6 | tube → top cap, tie rods | top-cap lip, same | rods clamp the stack | | none (nylocs) | rod tension decides how square the tube is pulled | no |
| R7 | plate → sled / carrier / bank | 4 × M3 in d3.4 sled holes (screws only) | sled on 4 bosses | ~0.2 | **4 × M3 × 6 in the plate's bosses** (r 45) | balance only (mass offset) | no |
| D1 | **plate → hub core** | d28.0 spigot in d28.4 (0.2), but **the countersunk heads locate it** | core face on the plate top | 0.2 until tight, then wherever the countersinks put it | **4 × M3 × 6 in the core (r 18): the one found proud** | **no** (carries no rotor weight) | **yes**: tilts the pins |
| D2 | core → nut plate | d22.2 in d22.4 | captive in the pocket | 0.1 | none | no | via D3 |
| D3 | **core / nut plate → pins (rod ~d2.9)** | d3.4 holes in the core floor (6 mm) and the nut plate (4 mm); nuts in 5.6 AF pockets | nut clamp | **0.25 a pin** | none | no | **yes: sets which pin drives** |
| D4 | **pins → 40T hub notches** | notch 4.0 wide, radial to r 10 | tips ~1 mm off the floors | **0.5 a side** (backlash ±3.6° at r 8) | none | no | **yes: handover impacts (candidate 1)** |
| D5 | hub → 6802 → cup → deck | journal d15.10 (push fit, CA'd), cup bore d24.10 (no rock, CA), cup on 3 screws in d3.8 holes, **centred by jig v3** | cup flat on the deck | cup ±0.4 until centred | **3 deck inserts** under the cup (now 1.0 mm relief on reprint 3) | no | the hub-to-rotor offset (e) feeds D4 |

**Worst-case pin offset from the 6820 axis, as drawn:** keys 0.15, plus the core's countersinks against its spigot (~0.1-0.2 if the countersinks and inserts disagree), plus each rod's 0.25. That makes **up to about 0.6 mm**, against 0.5 mm of notch play.

## 4. Ranking

**Visible wobble (the tube's top orbit):**
1. **R1 + R2: the seat.** A loose spigot lets the rotor tilt whenever the land unloads. A 0.05 mm wedge in the ring's land-to-top-face thickness already gives 0.25 mm of runout at the top.
2. **R3 + R4 + R6: the plate stack.** Plate wedge or warp, and uneven tie-rod tension.
3. **R5: the tube's lip and end squareness.** At most 0.2 mm of offset from the lip; tilt if the end isn't square.
4. **Unbalance on a soft base** (not a joint). It grows with rpm², so the hand-turn test separates it from the geometry: geometric runout is the same turned by hand and running.
5. The base side (B1, B2, D5) and the pins (D1-D4) **cannot** make the tube wobble.

**Two pops per turn at two fixed rotor angles, 145 / 215°:**
1. **D3 + D4 + D5: drive handover between two pins** (section 1). D1, the cocked core, made it worse.
2. **R1 + R2: rocking on the seat.**
3. **Load-torque swings in the 6820** (your coast-down, 11-21): the fresh 6820 drags about **0.1 N·m** (the rotor stops almost at once by hand), and the video shows the speed swinging **±10-15 % within a turn**. A drag that changes around the turn (fresh grease, or an inner ring squeezed by the ring's ribs at a couple of spots) loads and unloads the drive at fixed rotor angles. With 0.5 mm of backlash, every unload lets the driving pin come off its wall and hit it again. The same 1 mm of backlash also turns that swing into impacts. Test: coast-down by hand with the pins out, before and after a run-in (10 min at low speed) or degreasing. **The one-pin test does not rule this out**: a single pin still has backlash. If one pin is quiet, it was handover; if one pin still pops, look here or at the seat.
4. Anything rubbing at two rotor angles: trim screws in the ring's 24-hole flange (15° steps, so 135 / 225 or 150 / 210 are possible) touching the collar, or rod-end nuts touching the 6820's outer ring. **If you have trim weights fitted, check their clearance first.** The tie rods and keys are at 90° steps, so they can't give 145.

## 5. Fixes, joint by joint (the decisions)

| Joint | Fix | Why this one |
|---|---|---|
| D4 / D3 | **Run one pin** if the one-pin test stops the pops. Otherwise centre the pins with the jig. Optional: 6 mm of thin heat-shrink on the driving pin to soften starts and stops (rev n Q9) | It removes the handover itself. Four pins with backlash will always hand over. Four tight pins in radial notches would overconstrain the drive (it binds unless the axes agree to ~0.05) |
| D3 | **Pin-centring jig** (print 1) | it locates on the ring's bore, which is concentric with the spigot that runs in the 6820, and sets each pin's tangential position, which is the only thing the radial notches see |
| D1 | **Core reprint with insert relief** (print 2): d6.5 × 1.0 counterbore at each insert. Push each insert flush with the counterbore floor | an insert or melted collar up to 1 mm proud can't hold the faces apart. The hole still ends 7.0 mm from the face, so a flush insert bottoms out. The M3 × 8 countersunk keeps 5 mm of thread |
| D1 | keep the countersunk screws. **If you need the jig to move the core**, swap to M3 × 8 socket heads + a washer | countersunk heads re-centre in their cones. Socket heads sit on the flat and keep the jig's position. They hang 3.5 mm below the plate at r 18, 2 mm outside the hub's crown |
| R3 | **Hex key fit set** (print 2): the biggest key that pushes into both pockets by hand | takes the ~0.15 mm plate-on-ring play out without reprinting either part |
| R1 | stay on the **tight (100.80) ring**, scraped to a sliding fit. **Do not run the loose ring.** Compliant ring only if the tight one fails 6.3 | the spigot is the only radial location of the rotor |
| R2 / R4 | **check the wedge with calipers** (6.3, 6.4). Lap on a flat tile with 240-grit paper if over the limit | cheaper and more accurate than a reprint |
| R6 | tighten the tie rods evenly: finger-tight, then the same number of flats on each, in a cross pattern; check the tube top after | uneven rods tilt the tube on the plate |
| R5 | if the tube rocks on the plate's lip before the rods go on, one turn of masking tape (~0.1 mm) on the lip | closes the 0.2 offset |
| D5 / B1 | **cup: jig v3 as before.** Insert check: straight edge across each deck insert; **file proud inserts flush** (or print reprint 3) | base-side tilt doesn't wobble the rotor, but a cocked cup tilts the hub's notches |
| R7 | plate reprint 4 only if your plate fails 6.4 or is dented; it adds the same relief on the sled-boss inserts | a proud sled insert tilts the sled (balance), not the tube |
| all | **balance last**: trim screws in the ring's 24-hole flange (r 88) | after the geometry is right, what's left at speed is unbalance |

**Not done, on purpose:** a new locating register between the ring and the plate (reprints of the 3 h ring and the 2.3 h plate) when tight keys do the same job. A zero-backlash 4-pin drive (it overconstrains). A printed dial indicator (calipers and paper are enough for the 0.1 mm limits below).

## 6. Bench sequence

**Tools:** calipers; a sharp screwdriver taped flat to something heavy that sits still on the table or the base (the "pointer"); **printer paper = 0.10 mm a sheet** (check: calipers on a 10-sheet stack ≈ 1.0 mm), and kitchen foil ≈ 0.02 mm for finer steps. Mark 8 angles on the ring's rim with a marker: 0 = tie rod 0, then every 45°.

**Runout with a pointer:** set the tip over the surface. Turn the part by hand to the closest point and set the tip so **one sheet drags lightly**. Then go round the 8 marks and find how many sheets slide in at each with the same light drag. **TIR ≈ (most sheets − 1) × 0.1 mm.** Use foil to split a sheet.

### 6.1 Two quick tests before printing anything (rotor as it is now)
1. **Hand-turn wobble:** belt off, pointer at the tube's top edge (outside face). Turn slowly by hand and read the TIR. Then run at 150 rpm and judge the wobble by eye against the same tip. **Same size: geometric** (sections 6.3-6.6 find it). **Much bigger running: unbalance or a soft base** (balance, and keep the base bolted to the desk).
2. **One-pin run:** take out 3 of the 4 rods (keep the one that's easiest to reach). Crawl up to 155 rpm, as in your crawl test. Note the speed and current where pops start, or that they don't.
3. **Weight-on-top run** (4 rods back in): a 1-2 kg weight centred on the top cap, taped. Same crawl.
4. Write all three into `docs/measurements.md`. They decide the path:
    - **One pin quiet:** handover confirmed. Keep one pin, then do 6.6 for the wobble.
    - **Weight quiet:** the seat. Do 6.3 first.
    - **Neither:** look for a rub (trim screws, rod-end nuts), then do the full pass.

### 6.2 Inserts (with print 2 in hand)
- Heat the insert in the new core's counterbore until it is **flush with the counterbore floor** (the ledge). Let it cool.
- **Flush check:** lay a straight edge (steel rule edge-on) across the core's face over each insert. Nothing may touch the rule; you should see light under it everywhere. Slide a sheet of paper under the rule at each insert: it must pass.
- Same check on the deck inserts under the cup (3), the collar (4) and the hanger (4), and on the plate's sled-boss inserts. File proud ones flush.

### 6.3 Rotor ring alone in the 6820 (pass limits)
- **Ring wedge**, ring off: calipers across the ring from the **land face to the top face** right over the land (r ~51, about 40 mm in from the OD: the jaw tip sits on the 2.2 mm land beside the spigot) at the 8 marks. **Pass: spread ≤ 0.05 mm.** If your jaws don't reach, skip it: the face-runout check below sees the same wedge. Over: lap the top face on 240-grit on a tile, figure-8 strokes, then recheck. Never lap the land.
- **Spigot fit:** drop the ring into the 6820. Press down at each mark with one finger: **no click and no rock** (a sheet of paper under the land at the opposite side must stay pinched).
- **Face runout:** pointer on the ring's top face at r ~85. **Pass: ≤ 0.10 mm TIR** (≤ 2 sheets).
- **Radial runout:** pointer on the ring's OD (r 91). **Pass: ≤ 0.10 mm TIR.**

### 6.4 Plate on the ring
- **Plate wedge**, plate off: calipers across the plate at the tube seat (r ~79, between the lip and the outer skirt) at 8 points. **Pass: spread ≤ 0.05 mm.** Over: lap, or print reprint 4.
- **Keys:** pick the biggest size (dimples 3 → 2 → 1) that pushes into **both** pockets by hand. Fit all 4, plate on, rods finger-tight, then the same number of flats on each in a cross pattern.
- **Plate top face at r ~80:** **pass ≤ 0.15 mm TIR.** **Lip OD:** **pass ≤ 0.15 mm TIR.**

### 6.5 Core and pins (pin jig, print 1)
- Core on the plate, inserts flush (6.2), 4 countersunk screws snug in a cross pattern. Pins in, nuts snug.
- **Rotor upside down on the table.** Measure the rods (expect 2.85-2.95). Fit the jig on **set 1** (the single rim notch over a pin): the fingers go into the ring's bore, the pins into the slots, then press it flat onto the spigot's end face.
    - **Goes on: pass**, concentric within about 0.1 mm.
    - **Only set 2 goes on** (turn it 45°, double notch on a pin): within about 0.15. Acceptable with one pin; re-centre for four.
- **To centre:** loosen the rods' nuts so the rods move in their holes. Jig on, press flat, tap round the rim and turn it a degree each way so the fingers settle. Tighten the nuts in a cross pattern, lift the jig straight off, and re-gauge with set 1.
- If a rod can't reach its slot, the core is off. Loosen its countersunk screws through the jig's key holes (2 mm hex key), press, and snug them. If it creeps back when tightened, use socket heads + washers (section 5).

### 6.6 Tube and top cap
- Before the rods go on: does the tube rock on the plate's lip? If yes, tape the lip (section 5).
- Rods as in 6.4. **Tube bottom edge:** **pass ≤ 0.2 mm TIR.** **Tube top edge:** **pass ≤ 0.5 mm TIR** (≤ 6 sheets). Over: slacken the rod on the high side by one flat, tighten the opposite one, then recheck.

### 6.7 Cup and drive (base)
- Belt off, cup screws loose, **jig v3** as in the rev o README: fingers in the 6820, collar over the hub's teeth, press flat, snug the screws in rotation, lift off. Spin the hub: it must run true to the screwdriver tip at its crown, **≤ 0.1 mm** (1 sheet).

### 6.8 Run
- Rotor on, crawl up as before, and note the speed and current at each step and where any pop starts. Pin set: one pin if 6.1 said so.
- If it wobbles more running than turned by hand: balance. Tape a known mass (an M3 × 10 + nut ≈ 1.0 g) at one trim hole at a time and watch the top orbit at 150 rpm. Keep the position that shrinks it most.

## 7. Open questions (for you)

| # | Question | Why it matters |
|---|---|---|
| Q1 | The three runs in 6.1: speed and current at the first pop, or none | decides handover vs seat |
| Q2 | Is the tight 100.80 ring in now, and does it slide in the 6820 with no rock? | R1 is the top wobble suspect |
| Q3 | Any trim screws fitted in the ring's flange? At which holes? | a rub at two angles is the third pop candidate |
| Q4 | Where are the rods' lock nuts, under the nut plate or on top of the core? | sets how you loosen them with the jig on |
| Q5 | Rod diameter (calipers) | picks the jig's slot set |
| Q6 | Which hex key size fits both pockets? | R3 play |
| Q7 | Hand-turned tube-top TIR before and after the pass | the measure of success |
| Q8 | Coast-down with the pins out: seconds from a hand flick, before and after a 10-minute low-speed run-in | 6820 drag (~0.1 N·m now) is the third pop candidate and most of the 600 mA |

## 8. How to explain it

> The column popped twice a turn, at the same two spots on the rotor, and they weren't opposite each other. That asymmetry was the clue. The rotor is driven by four pins in four slots, and each slot has half a millimetre of play. So only one pin is ever actually pushing. Which one depends on tiny offsets, a few hundredths of a millimetre, plus how far the two axes are apart. If two pins take turns, the drive hands over twice per revolution, and every handover is a small collision across the play. Four pins sounds stronger than one. But with backlash, more pins just means more handovers. One pin, or a jig that puts all four exactly on their lines, fixes the drive. The wobble is a different problem in a different chain: what holds the tube up, not what turns it.

- **Separate the chains:** support (bearing → ring → plate → tube) sets the wobble; drive (pins → hub) sets the noise. Asking "does this part carry weight?" rules half of them out at once.
- **Elastic averaging:** six equal flex fingers centre the jig on the bore whatever the print shrink. It is the same trick jig v3 used.
- **Radial slots, not holes:** the jig fixes each pin's tangential position, the only thing a radial notch sees, and lets each pin keep its own radius.
- **Relief under heat-set inserts:** a 1 mm counterbore at the mouth means a melted collar or a slightly proud insert can't hold two faces apart.
- **Measuring without a dial indicator:** printer paper at 0.1 mm a sheet, a screwdriver taped to something heavy, and calipers for wedge. The limits are all 0.05-0.5 mm, which this resolves.

**Shots:** the jig going on (the fingers settling into the bore); the paper-feeler runout check; the one-pin run against the four-pin run (audio); the proud insert beside the counterbored core.

## 9. Files

| File | What |
|---|---|
| `cad/make_revo_rotor_pin_jig.py` | the jig (with overlap checks against the ring STL and d2.90 pins), the core and plate relief STLs |
| `cad/make_revo_concentricity_parts.py` | core + 15 hex keys plate, cup v2 d24.10 relief |
| `cad/revo_rotor_pin_centring_jig.stl`, `cad/revo_core_and_keys_plate.stl`, `cad/rotor_hub_core_o_relief.stl`, `cad/rotor_bottom_cap_o_relief.stl`, `cad/revo_bearing_cup_v2_b24p10_relief.stl` | print-orientation STLs (island check 0 each) |
| `cad/print/rev-o_CURRENT/README.md` | how-to-use steps; `_slice_log.txt` has every slice command and the no-brim checks |

**Jig checks (mesh CSG, model coordinates):** against the rotor ring STL, overlap is only in the finger bumps (9.2 mm³, the intended preload; 0.00 mm³ elsewhere). Against 4 × d2.90 pins at r 8, 0 overlap on both sets; drawn play is 0.075 / 0.150 a side. The fingers clear the hall sensor (r 41) and the plate. The crown (r ≤ 13, top z −8.5) stays 6.5 mm below the nut plate and clears the XH header / pogo pins (r ≤ 4.7).
