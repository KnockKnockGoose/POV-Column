# rev o print files (2026-11-20): cup v2, fixed slip ring with a drive mast, pogo contacts, jig v3, fit coupons

Report: `docs/2026-11-20-rev-o-cad.md` (why each part looks the way it does, checks, assembly, shopping list). Sliced with `fusionclaude/slicer/slice.py` (commands in `_slice_log.txt`). **Nothing has been sent to the printer.**

Rev o starts from the rev n drive **as you built it**: clamp ring out (cup on the deck, everything 3.2 mm lower, belt plane z −11.3), drive pins M3 × 20, cup screws M3 × 6, 3 magnets on the riser. The hub, the 6802 (CA'd onto it), the 20T, the belt, the hanger, the shell, the collar and the epoxied 6820 all stay as they are.

All files: H2D, **left (hardened) nozzle = extruder 1**, textured PEI, 0.2 mm layers, no supports, no brim. Island check (script 151): 0 starts on every STL.

## 2026-11-21 (afternoon): concentricity pass: rotor pin-centring jig, hub core with insert relief, hex-key fit set

Report: `docs/2026-11-21-rev-o-concentricity.md` (every joint in the chain, the two-pops explanation, the bench sequence with pass limits). **Do the two quick tests in its section 6.1 first (one-pin run, weight-on-top run).**

| File | What | Time | Mass |
|---|---|---|---|
| **`revo_rotor_pin_centring_jig_PETG-CF`** (print first) | jig that centres the 4 drive pins on the rotor ring's bore; two slot sets (**1** = 3.05 snug, **2** = 3.20 sliding) | **0.99 h** | **17.0 g** |
| **`revo_core_and_keys_plate_PET-CF`** | the hub core, unchanged except a **flat counterbore d6.5 × 1.0 at each of its 4 insert holes** on the face that sits on the plate, + **15 hex keys** for the plate ↔ ring joint: 5 each of 5.90 / 5.95 / 6.00 AF (1 / 2 / 3 dimples; the rev k key is 5.85): use the biggest that pushes into both pockets by hand | **0.92 h** | **14.5 g** |
| `revo_bearing_cup_v2_b24p10_relief_PETG-CF` (only if a deck insert under the cup is proud and you'd rather not file it) | cup v2 at d24.10, its 0.3 mm insert relief made 1.0 mm deep (d6.5) | 0.39 h | 4.9 g |
| `rotor_bottom_cap_o_relief_PETG-CF` (only if your plate is dented, cracked or bent where the proud insert sat) | the bottom-cap plate, unchanged except the same d6.5 × 1.0 relief on its 4 sled-boss inserts | 2.28 h | 51.3 g |

Jig: Bambu PETG-CF, left nozzle (extruder 1), textured PEI, 0.2 mm, 4 walls, 4/4, 20 % (jig v3's process). Core + keys: Fiberon PET-CF (dry it), left nozzle, 5 walls, 6/5, 40 % (the core's original process). Plate and cup: Bambu PETG-CF, 6 walls, 6/6, 85 % (as your PETG-CF plate / the drive parts). **No brim** on all four: `no_brim` + skirt 0 in both 3mfs, 0 brim/skirt features in the G-code. Island check (151): 0 on all four. Generators: `cad/make_revo_rotor_pin_jig.py` and `cad/make_revo_concentricity_parts.py` (mesh CSG; Fusion not touched).

**Which part is which.** The pins go through the **hub core** (PET-CF, d45, the part with the 4 heat-set inserts). The core does **not** sit on the rotor ring: it sits on the **bottom-cap plate** (your PETG-CF plate). A d28.0 spigot sits in the plate's d28.4 hole (0.20 radial play), and 4 × M3 × 8 **countersunk** screws go up from under the plate (r 18, at the pins' angles) into the core's inserts. The rotor ring's bore is d94 and never touches the core. The ring is located on the plate by the 4 hex keys (5.85 in 6.0 pockets, r 72) and the 4 tie rods (r 60).

**Play, as drawn:** core on plate 0.20 radial, but the countersunk heads pull the core to wherever the 4 countersinks put it, so it isn't free once tight. Each pin (rod ~d2.9) in the core's d3.4 hole and the nut plate's d3.4 hole: about 0.25 radial. Plate on ring through the hex keys: about 0.15. Worst case pin to ring axis about 0.6 mm; the hub's notches give 0.5 a side.

**Insert relief (core):** push each insert **flush with the counterbore floor** (the ledge you can see), not with the face. A melted collar, or an insert up to 1 mm proud of the floor, then can't hold the core off the plate. The hole still ends 7.0 mm from the face, so a flush insert bottoms out. The M3 × 8 countersunk screws keep 5 mm of thread. Check with a straight edge across the face: no insert or collar may touch it.

**How to use the jig (rotor upside down on the table, spigot up):**
1. Measure the rods with calipers (expect 2.85-2.95). Try **slot set 1** (the single rim notch is on a set-1 slot): turn the jig so the single notch lines up with a pin.
2. **Gauge first, change nothing.** Lower the jig straight down: the six fingers go into the ring's bore and the pins go into the slots. Press it flat onto the spigot's end face (a light, even push).
    - If it goes all the way down on set 1 without forcing, the pins are concentric with the ring to within about 0.1 mm. **Then the pin circle is not your problem.** Write that down and stop here.
    - If set 1 won't go but **set 2** does (turn the jig 45°, double notch on a pin), the pins are within about 0.15 mm.
    - If neither goes, note which pin is in the way and which side of its slot it hits.
3. **To centre the pins:** jig off. Loosen the 4 rods' lock nuts half a turn, wherever you can reach them, so each rod moves in its hole. Jig back on (set 1 if the rods slide in, else set 2) and press it flat. Tap the jig lightly round the rim and turn it a degree or two each way so the fingers settle. Hold it down and tighten the rod nuts again, in a cross pattern.
4. **If a pin can't reach its slot** with the rod loose, the core itself is off. Its 4 countersunk screws sit under the jig's key holes at r 18 (2 mm hex key; 8 holes, so they line up with either set). Loosen them, press the jig flat, and snug them in a cross pattern. **Warning:** countersunk heads re-centre in their cones, so the core may creep back. If it does, swap them for M3 × 8 socket heads with a thin washer each: the heads then sit on the flat around the countersink, and the core keeps the jig's position. They hang about 3.5 mm below the plate at r 18; the hub's crown (r ≤ 12.5) clears them by 2 mm.
5. Lift the jig straight up. It must come off without dragging a pin. Then re-check step 2 with set 1.

## 2026-11-21: motor hanger with insert relief (the deck inserts stood proud)

| File | What | Time | Mass |
|---|---|---|---|
| **`revo_motor_hanger_relief_PETG-CF`** (print this) | the rev m.2 motor hanger, unchanged except for **4 relief pockets in the deck face** | **0.89 h (54 min)** | **14.6 g** |

**Why:** the 4 deck heat-set inserts (M3 × 4) stand about 2 mm proud of the deck's underside. The hanger then sat on their tips, not on the deck, so the gearmotor and the 20T were cocked.

**What changed:** at each deck screw there is a d6.5 pocket, 2.5 deep, with a 0.5 × 45° mouth chamfer. It is an obround swept over the slot's ±2 mm belt-tension travel. The insert's knurl is d4.2 and its melted collar is about d5.5, so it clears by 0.5 mm. The floor under the M3 × 10 washer is 3.5 mm. The pocket keeps ≥ 1.0 mm of new wall to the outline, so travel is limited near the edge. The inner row (nearer the rotor) clears −2 … +1.75 mm of slot travel; the outer row clears −0.25 … +2 mm. Tensioning the belt pulls the hanger away from the axis, so the inserts move toward the free side of both pockets. Everything else is the rev m.2 hanger: identical below z 3.5 (section areas checked at z 1, 3 and 3.4), the gearbox face, the d12.4 boss hole, the 4 gearbox screws with their d6.5 × 3.3 counterbores, and the slots. The pockets (chamfer included) stay at least 7.6 mm clear of the gearbox counterbores. The outer-row slot ends were already 0.3 mm from the corner arc in rev m.2; that is unchanged.

**Print:** gearbox face down, as before. The pockets open upward, so there are no supports. Bambu PETG-CF, left nozzle (extruder 1), textured PEI, 0.2 mm, 6 walls, 6/6, 85 % gyroid (the drive parts' process). **No brim:** `no_brim` in both 3mfs, skirt 0, 0 brim/skirt features in the G-code. Island check (151): 0. Generator: `cad/make_revo_motor_hanger_relief.py` (mesh CSG on `cad/revm_motor_hanger.stl`, with section checks; Fusion not touched). Fit it with the same 4 × M3 × 10 + washers into the deck inserts. Filing the insert tips flush is still fine: the pockets just stay empty.

**Likely cause of the old hanger's bend:** clamping the 4 screws over proud insert tips levered the 6 mm plate's corners around them. The motor's heat is unlikely: a few watts at 0.6 A, far below PETG-CF's ~70 °C. The pockets remove those pivot points.

## 2026-11-20 late: centring jig v3 (jig v2 did not seat)

| File | What | Time | Mass |
|---|---|---|---|
| **`revo_centring_jig_v3_PETG-CF`** (print this) | 3 jigs v3 on one plate, bore **1** = d25.15, **2** = d25.30, **3** = d25.45 (notches on the rim + a raised digit on one spoke) | **1.77 h** | **43.7 g** (14.6 g each) |

Same process as jig v2: Bambu PETG-CF, left nozzle (extruder 1), textured PEI, 0.2 mm, 4 walls, 4/4, 20 % gyroid, no supports. **No brim:** `brim_type = no_brim` in both 3mfs, skirt 0, no per-object overrides, and 0 brim or skirt features in the G-code. Island check (script 151): 0 on the plate and on each jig. Generator: `cad/make_revo_jig_v3.py` (mesh CSG; the Fusion document was not touched). Jig v2 is in `superseded/`: **don't print it.**

**Why v2 stopped short.** Rev o added a 3rd magnet to the riser, so the stack's top is now z −5.0, at 90°, r 38-44 (Fusion v17, `magnet_3_asbuilt`). Jig v2's disc is solid there, with its underside at −6.6, so it landed on the magnet **1.6 mm short of home**. Held up there, its collar reached only 0.6 mm over the hub's teeth, so it never got "over the hub". The riser is 180° from the 20T window, which is where you found it on the bench and where the CAD has it (riser 90°, motor 270°). Second problem: v2's skirt was a rigid d99.7 in the 6820's d99.97 bore. A printed ring that size comes out 0.4-0.8 % small (the rotor-ring fit tests), so v2 would have left ~0.4 mm of play before the collar's own play.

**What v3 changes:**
- **Wide open windows: 90° ± 45° (riser) and 270° ± 45° (20T and motor travel)**, r 18-47.8, right through the disc. Nothing stands above the 6820 there, at any height. The plastic is two 90° spokes centred on 0° and 180°, plus the rim and the collar. **The jig is symmetric, so it goes on either way round.** Both windows clear the 3-magnet stack even if it were 2 mm taller, and they clear the 20T at its nominal position and ±2 mm of belt-tension travel. The cup-screw key holes (d7.8 at 60 / 180 / 300°) are unchanged.
- **Six flex fingers instead of the rigid skirt.** Each finger is 0.9 mm thick and 9 mm long, with a bump drawn at d100.75 and a 30° lead-in. All six press equally on the 6820's bore, so the jig centres itself whatever the print shrink. At 0.4-0.75 % shrink a finger deflects 0.01-0.19 mm (0.3 % strain at most). Expect a light, even push as the bumps go in, then it sits on the inner ring's top face as before.
- **Longer collar: z −12.0 (was −10.0), so it bears on 4.2 mm of tooth tips.** It has a 0.8 × 45° lead-in at the mouth, which catches the hub up to 1.7 mm off-centre, and a 0.5 mm elephant's-foot relief where the bore meets the bed face. The hub's lower flange is still 2.8 mm below the collar.
- Checked in CSG at the home position against the as-built hub STL (j15.10), the 3-magnet stack and its column, the 20T at −2 / 0 / +2 mm, the motor shaft, the 6820's rings and shields, cup v2 and the screw heads: **0 overlap**, except the fingers' intended preload on the bore.

**Which variant:** check each one on the hub alone first (belt off, jig upside down, collar over the hub's teeth). **Use the smallest bore that slides over the teeth all the way with no force and doesn't rock.** Expected radial play on the printed hub: **1** ≈ 0.12, **2** ≈ 0.19, **3** ≈ 0.27 mm. Try 2 first. If 2 rocks, use 1, but only if 1 still slides freely. Use 3 only if 1 and 2 are tight. The collar's play adds directly to the centring error, so the smallest bore that slides wins.

**How to use it (centring the cup):**
1. **Rotor off, belt OFF.** The belt sits where the collar goes (z −14.3 … −8.3), so with the belt on the jig can't seat.
2. **Loosen the three cup screws** half a turn (60 / 180 / 300°), so the cup slides on the deck.
3. Turn the jig so one window is over the 20T pulley; the riser is then under the other window. Lower it straight down: the fingers go into the 6820's bore, and the collar finds the hub's crown and slides down over the teeth. **Press lightly on the rim until it sits flat on the 6820's inner ring all the way round.** If it stops early, lift it and look: nothing should touch the spokes.
4. Hold the jig down. **Snug the screws in rotation** (60 → 180 → 300, then round again) through the key holes: ~0.15 N·m, two fingers on a short key.
5. **Lift the jig straight up.** It must come off without dragging the hub. If the hub moves with it, the bore is too tight: use the next variant up and repeat.
6. Spin the hub by hand: it should run true to the 6820. Then belt back on, tension as before.

## 2026-11-20 evening: mast v2 + contact head v2 (after your fit checks)

| File | What | Time | Mass |
|---|---|---|---|
| **`revo_mast_head_v2_plate_PETG-CF`** (print this) | 4 masts v2 (key sizes, notches on the body: **1** = 4.45 × 2.85, **2** = 4.50 × 2.90 ×2, **3** = 4.55 × 2.95) + 2 contact heads v2 | **0.26 h (16 min)** | **2.1 g** |

Same process as the drive parts: Bambu PETG-CF, left nozzle (extruder 1), textured PEI, 0.2 mm, 6 walls, 6/6, 85 %, no supports.

- **No brim:** `brim_type = no_brim` in both 3mfs, skirt 0, no per-object overrides, and 0 brim or skirt features in the G-code (inner brims included).
- **Island check (script 151):** 0 on all five STLs.
- **This supersedes the masts and heads on `revo_drive_parts_plate`.**

**What changed and why** (report §4.2 / §4.3 has the numbers):

- **Key 4.4 × 2.7 → 4.50 × 2.90** (0.05 a side in the 4.6 × 3.0 neck).
    - The v1 key really allowed ±9.8° as drawn, not ±4°. You measured ±15°, so about 0.07 a side extra came from the print and from tilt in the 1.2 mm neck.
    - The coupons show the printer itself only shrinks about 0.4 % (under 0.02 mm at this size), so 0.05 should still slide by hand. As drawn it turns ±3.5°.
    - **Pick the fit:** try notch 2 first. If it's stiff, use notch 1. If it still turns a lot, use notch 3. Every one is a full mast.
- **Socket end prints clean now.** The flat ring overhang is a 45° cone, and the mouth has a 0.3 chamfer. The Ø5.05 × 1.0 cylinder that centres it on the boss is unchanged, and it still prints socket-down.
- **3 + 3 leads, no splices.**
    - Channel Ø2.2 → **Ø2.6**, then a 45° cone into a **3.2 × 1.6** slot through the key. That's 37 % fill for six Ø0.6 PTFE leads.
    - The key walls are 0.65, below the 0.8 rule. That's fine at < 1.6 mN·m drag: 0.16 MPa in torsion, and 4.9 MPa even at the 50 mN·m catalog worst case.
    - **If six won't thread:** go 2 + 2. Cut yellow (−) and orange (+) off at the boss and insulate them.
- **Head Ø10.9 → Ø10.8**, so it slides down onto the hub's cone and the washer sits 0.30 below the crown.
- **Head lead holes Ø1.6 → Ø2.0**, so a 3-lead bundle (Ø1.3) threads. The − hole moves to r 3.5, still under the washer.

## 2026-11-20 afternoon: replacement drive hub, journal d15.10 (from the coupons)

The as-built hub is off (CA'd while loose, so it ran out), and the spare rev n hub is very loose in a fresh 6802: its d14.6 journal with 8 crush ribs to d15.10 printed small. Coupon readings (`docs/measurements.md`): **stub 4 = d15.10** is a push fit you can remove with no wobble; stub 5 = d15.15 sticks. **Cup: ring 2 = d24.10.**

| File | What | Time | Mass |
|---|---|---|---|
| **`revo_hub_and_cup_plate_PETG-CF`** (print this) | 2 drive hubs j15.10 (1 spare) + cup v2 bore d24.10 | **1.13 h** | **14.3 g** |
| `revo_drive_hub_j15p10_PETG-CF` | 1 hub alone | 0.47 h | 4.6 g |

- **The hub is the same rev n / rev o hub, except the journal.** It has 40T teeth, the lead-in cone, the 45° lower flange, the crown d12.3 hole with 4 pin notches, the d11 bore and 45° cone for the contact head, and the 4.6 × 3.0 lead neck for the mast key. **Only the journal changed:** it is now a plain d15.10 cylinder, 3.6 mm into the inner ring, with a 0.5 × 45° lead-in at its end. That is the coupon stub's shape on the same process, so the fit should transfer directly. The old journal had no CA groove, so this one has none either.
- **How it was made:** mesh CSG on `cad/revn_drive_hub.stl` (`cad/make_revo_hub_j15p10.py`; the Fusion document was not touched). **Checked:** sections through the journal are round at r 7.550, the bore, neck and notches are unchanged (0 mm³ removed, +34 mm³ added, all at r ≥ 7.02), and the island check (script 151) finds 0 starts on both STLs.
- **No brim:** `brim_type = no_brim` in the project and sliced 3mf, skirt 0, no per-object overrides, and 0 Brim features in the G-code. Send the **`.gcode.3mf`**. If you re-slice the `.3mf` in Bambu Studio, check that Others → Brim type still reads "No-brim".
- Same process as the drive parts: Bambu PETG-CF, left nozzle (extruder 1), textured PEI, 0.2 mm, 6 walls, 6/6, 85 % gyroid, no supports.
- **Fit off the bed** (wait 30 min): a fresh 6802 should go onto the journal with a firm thumb push and come off again without rocking. If it's tight, scrape the journal lightly. Don't print a d15.05 hub unless it really won't go on: the coupon at that size wobbled.

## Print order

| # | File | What | Material / process | Time | Mass |
|---|---|---|---|---|---|
| 1 | **`revo_fit_coupons_PETG-CF`** | 7 cup-bore rings d24.05 … 24.35 (notches 1 … 7 = 0.05 steps) and 7 hub-journal stubs d14.95 … 15.25 (notches 1 … 7) | PETG-CF, 6 walls, 6/6, 85 % (the drive parts' process) | **1.27 h** | **31.3 g** |
| 2 | **`revo_centring_jig_v3_PETG-CF`** | centring jig **v3** (3 bore variants; see the section at the top). v2 (`superseded/`) lands on the 3rd magnet: don't print it | PETG-CF, 4 walls, 4/4, 20 % | **1.77 h** | **43.7 g** |
| 3 | **`revo_drive_parts_plate_PETG-CF`** | cup v2 (bore d24.20), slip-ring bracket, 2 masts, 2 contact heads, 2 nut plates v2 (one spare of each small part) | PETG-CF, 6 walls, 6/6, 85 % | **0.87 h** | **11.3 g** |
| (3b) | `cup_variants/revo_bearing_cup_v2_bore24pXX_PETG-CF` | the cup alone at each coupon size, if coupon 4 (d24.20) is not the one | same | 0.39 h each | 5.0 g |
| opt. | `optional/revo_rotor_ring_compliant_PET-CF` | rotor ring with a compliant spigot (8 bow-spring skins, ribs d100.60): **only if scraping the 100.80 ring fails** | Fiberon PET-CF, 5 walls, 6/6, 40 % (the rev k ring's process) | 3.13 h | 80.7 g |

**Total for the main path: 2.8 h and 59 g of PETG-CF.** (Jig v3 now replaces jig v2: 1.77 h, 43.7 g for the three variants.) The rev n jig can't centre the as-built hub either: its bore sits on the hub's lead-in cone, ~1 mm loose.

## Reading the coupons (30 min after printing: PETG-CF keeps shrinking)

- **Cup bore:** take a new 6802. Push it into each ring by its outer ring until it sits on the ledge. Pick the smallest ring it goes into with **a thumb push and no rock** (it should lift out by tipping the ring over). Ring 4 = d24.20 is the cup on the main plate; for another ring, print `cup_variants/..._bore24pXX` (XX = 05, 10, … 35).
- **Hub journal** (for a future hub; yours is CA'd): pick the stub the bearing's bore goes onto with a firm thumb push. Write both picks into `docs/measurements.md`.

## Fits to check off the bed

| Fit | Drawn | If it's off |
|---|---|---|
| 6802 outer ring in cup v2 | plain bore d24.20, 0.4 chamfer, 3 CA grooves; **coupon pick (11-20): ring 2 = d24.10** → `cup_variants/..._bore24p10` (also on the hub + cup plate) | from the coupon; never press it in: 3 dots of CA in the grooves fix it |
| 6802 inner ring on the hub journal (replacement hub) | **plain d15.10** (coupon stub 4: push fit, no wobble; stub 5 = d15.15 stuck), 0.5 lead-in, 3.6 long | scrape lightly if tight; no CA needed if it's like the coupon |
| mast's obround key in the hub's lead neck (4.6 × 3.0) | **v2: 4.50 × 2.90** (notch 2); 4.45 × 2.85 (notch 1), 4.55 × 2.95 (notch 3) on the same plate | v1 4.4 × 2.7 turned ±15°: use the notch that slides by hand with the least turn |
| mast's socket on the slip ring's d5 boss | d5.05 × 1.0, v2: 45° ceiling + 0.3 mouth chamfer | CA'd on the bench: square to the flange |
| 6 leads through the mast | v2: channel d2.6, key slot 3.2 × 1.6 (6 × Ø0.6 PTFE) | if six won't go, 2 + 2 (yellow / orange cut at the boss) |
| contact head in the hub's d11 bore | **v2: d10.8** (v1 d10.9 sat flush, not on the cone), 45° seat on the hub's cone; lead holes d2.0 | sand the head lightly; CA'd |
| M4 brass washer in the head's recess | d9.3 × 0.8 | CA |
| M2 brass insert (+ slug) in the head's well | d3.7 well | CA |
| pogo pins in nut plate v2 | barrel holes d1.70, collar counterbores d2.05 × 0.71 from the top | open the holes with a 1.7 mm drill by hand; CA |
| bracket arms on the cup's M3 × 10 | d2.6, self-tapped (3.5 mm) | the screws cut their own thread |
| slip-ring flange on the bracket | 3 pins d2.4 in its d3.2 holes (± 0.4 float) | must sit loose |

## Assembly order (report §9 has every step)

1. **Before option D:** measure the slip ring's drag. Hold the body, tape a 100 mm stick across the boss and hang pennies (2.5 g each) on its end; 1 penny turns it = below 2.5 mN·m. Above 8 pennies, ask before building.
2. Print the coupons, then jig **v3**, then the drive plate. Run the diagnosis bench plan (steps 1-8) **with jig v3**, the old cup and M3 × 6.
3. **Cup v2** (once the bench plan passes): the 6802 + hub into the cup size the coupon picked, 3 CA dots in the grooves. On the deck with jig v3 (belt off, screws loose, snug in rotation): M3 × 6 at 300°, snug (~0.15 N·m); M3 × 10 at 60 / 180° (they stick 3.5 mm out under the deck until the bracket goes on).
4. **Option D** (when the pins arrive; rotor off, belt off, base on its side, bottom plate off):
    1. On the bench (new slip ring, mast v2): **no splices and no cuts yet.** Thread all six 225 mm rotor leads through the mast from the socket end and out through the key's slot. CA the mast's socket square onto the boss.
    2. Flange on the bracket (pins in its holes). From below, push the mast up into the hub until its key drops into the neck.
    3. Hold the bracket up; drive the 60 / 180° M3 × 10 back through the inserts so they self-tap 3 turns into its arms. Spin the hub by hand: nothing may rub.
    4. Rotor off: thread the + three (green / brown / orange) through the head's centre hole and the − three (black / red / yellow) through the hole under the washer seat. **Only now cut each pole to ~15 mm above the head**, then strip and tin 3 mm. Solder the + three into the M2 insert and the − three to the M4 washer **above** the head, and trim stray strands. Press both into the head, then CA. Push the head into the hub's crown onto its cone, and CA it.
    5. On the bench: wires onto the pins' tails (red on the 0908-9, black on each 0908-6); pins into nut plate v2 from the top, then CA; wires up the hub core's Ø7 hole to the buck IN.
    6. Meter: > 1 MΩ slug to washer unpowered, +12 V on the slug powered. Drop the rotor on and read the buck's input.

## Hardware

- **From your kits:** 2 × M3 × 10 SHCS (cup, 60 / 180°, through into the bracket), 1 × M3 × 6 SHCS (cup, 300°, over the hanger: never longer), 1 × M2 brass heat-set insert (INCLY kit, the + slug), red / black 26 AWG (~120 mm each, 2 black), CA, 5-min epoxy.
- **To buy:** Mill-Max **0908-6-15-20-75-14-11-0** × 2 (+2 spare) and **0908-9-15-20-75-14-11-0** × 1 (+1 spare) pogo pins (Digi-Key); **M4 brass flat washers DIN 125** (4.3 × 9 × 0.8). Links and prices in the report, section 10.
