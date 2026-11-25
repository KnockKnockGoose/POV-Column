# Rotor ring refit (2026-11-18): bigger spigot ribs for the 6820's inner ring

> **2026-11-19, read this first.** The full **100.80** ring (picked from the fit test: two-thumb press on test ring 3), pressed into the 6820 whose outer race had been epoxied into the collar, **pinched the bearing**: the bare rotor drew 735 mA and stalled the belt; the old loose ring drew 327 mA. A thin-section ring has 0.012-0.036 mm of internal clearance and goes 3 µm oval per newton of squeeze, while a printed Ø100 ring is ~0.4 mm out of round, so **this spigot must be a sliding fit, never an interference fit** (the rotor's loads turn with the inner ring, so a loose inner ring is the textbook fit here). Use the old ring, or scrape the 100.80 ring's high ribs until it seats with a one-hand push at any angle (largest rib pair 99.90-99.95 in the 99.97 bore). The test rings below are springier than the full ring, so they over-state how much interference is safe. Report: `docs/2026-11-19-rev-n-bench-diagnosis.md` §2.1, §3.

**Problem (Brian, 2026-11-18):** the rotor ring's spigot (R17, `rev-k_CURRENT/rotor_ring_k_PET-CF`) is loose in the 6820's inner-ring bore. One wrap of electrical tape (~0.18 mm, so about +0.36 mm on Ø) made it snug. The collar and the outer ring are fine: **leave the collar alone.**

**Measured (Brian, calipers):**
- old ring, rib tips across opposite pairs: **99.40 / 99.64 / 99.24**, mean **99.43** against Ø100.10 drawn. That is 0.67 mm small and **0.4 mm oval**;
- 6820 inner bore: **99.97** (re-measured; a first reading of 99.49 was a chord).

**Predicted match: the 100.80 ring** (`rotor_ring_n_ribs100p80_PET-CF`, test ring 3). From the formula below: 99.97 + 0.10 + 0.67 = **100.74**.

**Cause:** the old ribs are Ø1.0 round bumps only 0.25 mm proud of a Ø99.6 spigot, printed with no XY compensation. A 0.4 mm nozzle mostly rounds them away, and the ring shrinks and goes oval as it cools. The new ribs stand 0.35-0.70 mm proud, so they print more faithfully than the old ones did. They may come out **closer to the drawing** than the 0.67 mm shortfall suggests. That is why you test first.

**Why still test first:** a real 6820's bore is 100.000 mm, +0 / -0.020, and 99.97 agrees. But the new ribs stand 0.35-0.70 mm proud, so they print more faithfully than the old 0.25 mm ones did. They may come out **closer to the drawing** than the 0.67 mm shortfall suggests, which would make 100.80 a little tight. The 4-ring plate brackets it (100.30 / 100.55 / 100.80 / 101.00). **Err big:** a rib that is too tight can be scraped down; one that is too small cannot be fixed.

**Fix:** the same ring with only the ribs grown. They keep the same shape (Ø1.0 round ribs, same 8 angles, same z 6.4-16.3, same 45° top chamfer, same spigot lead-in), with the centres moved out so the tips land at the new Ø. Rod holes, nut and key pockets, land, web, windows and trim flange are geometrically the rev k mesh. Rebuilding at Ø100.10 reproduces rev k to within 1.3 mm³.

## Files (H2D, **left hardened nozzle = extruder 1**, Fiberon PET-CF 300 / 70 °C, textured PEI, 0.2 mm, 5 walls, 6/6, 40 % gyroid, no supports, no brim: the rev k ring's exact process)

| File | What | Time | Mass |
|---|---|---|---|
| **`rotor_ring_fit_test_4x_100p30-101p00_PET-CF`** (print first) | 4 test rings: the top 5.4 mm of the spigot (4.7 mm of rib + the lead-in), real 2.8 mm wall, on a 0.8 mm flange to Ø107. Rib tips by **notches**: **1 = 100.30, 2 = 100.55, 3 = 100.80, 4 = 101.00** | **1.16 h** | **31.0 g** |
| `rotor_ring_n_ribs100p30_PET-CF` | full rotor ring, ribs Ø100.30 | 3.00 h | 82.9 g |
| `rotor_ring_n_ribs100p45_PET-CF` | full rotor ring, ribs Ø100.45 | 3.00 h | 82.9 g |
| `rotor_ring_n_ribs100p60_PET-CF` | full rotor ring, ribs Ø100.60 | 3.00 h | 82.9 g |
| `rotor_ring_n_ribs100p80_PET-CF` | full rotor ring, ribs Ø100.80 | 3.02 h | 82.9 g |
| `rotor_ring_n_ribs101p00_PET-CF` | full rotor ring, ribs Ø101.00 | 2.99 h | 82.9 g |

Test ring → full ring (**expected: 3 → 100p80**): **1 → 100p30, 2 → 100p60** (scrape lightly; or 100p45 if ring 2 felt only just firm), **3 → 100p80, 4 → 101p00**. Between two rings: print the bigger one and scrape.

- Time: the test rings are all perimeter (the 2.8 mm wall at the outer wall's 60 mm/s), so 4 rings take 1.16 h. A thinner test wall would print faster but be springier than the real spigot, and the test would steer you toward a ring that is too tight.
- **Island check (script 151):** 0 starts on all six STLs.
- STLs (print orientation) in `cad/`: `rotor_ring_fit_test_4x_100p30-101p00.stl`, `rotor_ring_n_ribs100p30/100p45/100p60/100p80/101p00.stl`. Generator: `make_refit.py` (trimesh + manifold3d, from `cad/rotor_ring_k.stl`). For another size, edit `RINGS` / `TESTS` and rerun. The slice command is in `_slice_log.txt`.
- `.gcode` is git-ignored; the `.gcode.3mf` is the file to send. The first 3-ring plate (100.30 / 100.45 / 100.60) was dropped once the measurements came in (in git history at ab3aa0e).

## The oval (0.4 mm spread on the old ring)

- **It is not elephant's foot.** The spigot starts 6 mm above the bed, and elephant-foot compensation only acts on layer 1. Still, measure the next ring **at mid-height of the spigot** (the ribs' top 0.3 mm is the lead-in chamfer and reads small).
- **Find out whether it is the printer.** The ring's bed orientation is on the part: the rib at -15° (one of 8 at 45° steps). Measure the old ring across the pair nearest the printer's X axis and the pair nearest Y. If the small diameter consistently lines up with one axis, it is XY scale or skew (belt tension / Bambu calibration). Then every round part on this printer is affected, not just this one.
- Otherwise it is cooling shrink of a thin spigot on a large web, and the bearing rounds it out when pushed on. The ribs take up the rest.
- **No slicer change applied, on purpose.** The seam is "aligned" (it sits in a concave rib root), and the outer wall already runs at 60 mm/s. Neither causes nor fixes an oval. Keeping the process identical is also what lets the test rings predict the full ring.

## The fit you want (and the limit on it)

In rev n the rotor lifts off by hand (report step 9) **and the 6820 has to stay in the collar**. Pulling the rotor up loads the bearing through its balls and tries to pull the outer ring out of the collar. So **the spigot must stay looser than the collar's outer-ring fit**: firm push on, firm pull off, no rock. Not a press fit. A ring that needs a vise or a mallet is too tight for rev n, even if it feels "solid".

## Procedure

1. Print the 4-ring test plate. Let it cool for 30 min before trying anything (PET-CF keeps shrinking as it cools).
2. Use the bearing **out of the collar**, held in your hand. Push each ring in by its flange, lead-in first, until the flange sits on the inner ring. Wiggle it, then pull it out.
   - too loose: drops in, or rocks when you wiggle it;
   - **right: a firm thumb push to seat it, no rock, a firm pull to get it out without tools**;
   - too tight: needs more than hand force, or won't seat. Scraping the rib tips of the next-bigger ring down to this is fine.
3. Check the winner with the bearing **in the collar** on the base. Push it in and pull it out. The bearing must not move in the collar. If it does, go one size looser (or scrape).
4. Print the matching full ring (3.0 h). Move the 4 hex keys, the M3 nuts and the tie rods across from the old ring; it fits back exactly as before.
5. **Scraping:** a little off the tip of each of all 8 ribs, evenly, with a blade; re-try. Too loose: the tape trick works as a stopgap.

**Seat the bearing in the collar by its outer ring only; never press or pull on the inner ring or the shields to do it.** Never pull the rotor up so hard that the bearing starts to come out of the collar. If it does, the spigot is too tight: scrape the ribs.

## Picking a size from measurements

Measure the old ring's rib-tip Ø across opposite ribs (average the pairs) = **D_meas**, and the bearing bore (largest reading) = **d_b**:

```
shrink     s       = 100.10 - D_meas          (how far the old ribs printed under the drawing)
draw tips  D_draw  = d_b + 2 * 0.05 + s       (0.05 mm radial interference on the printed size, as designed)
```

With D_meas = 99.43 and d_b = 99.97: s = 0.67, D_draw = **100.74 → the 100p80 ring**. Taller ribs shrink less, so the formula leans slightly tight: test first, scrape if needed. Keep the target at **0.05 mm**, below the collar's 0.075, so the spigot stays the looser of the two fits.
