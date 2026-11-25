# rev m print files (rev m.2, 2026-11-13: 12.5 mm capsule slip ring; PETG-CF shell added 2026-11-15)

> **2026-11-17: the drive spool and the lead guide on `revm2_drive_parts_PET-CF_plate` are superseded by rev n** (`../rev-n_CURRENT/`, report `docs/2026-11-17-rev-n-drive-redesign.md`): the spool broke twice at assembly. The clamp ring (now only the seat of the rev n cup: the slip ring hangs under the deck) and the motor hanger from that plate stay in use, and so do the shell, the sled and the bottom-cap plate. The 4 spool inserts and the CA step are gone.

Report: `docs/2026-11-13-rev-m-cad.md` §9 (rev m.2) and §5 (rev m). Sliced with `fusionclaude/slicer/slice.py`. Nothing has been sent to the printer.

| File | Parts | Material / setup | Time | Mass |
|---|---|---|---|---|
| `revm2_drive_parts_PET-CF_plate_PET-CF` | drive spool (plug up), lead guide (top down, nose up), slip-ring clamp ring (top down, pocket + pins up), motor hanger (gearbox face down) | Fiberon PET-CF, hardened nozzle, extruder 1, 6 walls, 6/6, 85 % | 1.55 h | 26.0 g |
| `rotor_sled_m_PETG` | centred sled v2 (plate down), unchanged from rev m | Bambu PETG Matte, 0.20 Structural PETG-PLA, extruder 1, textured PEI | 1.55 h | 28.7 g |
| `revm2_deck_drill_template_PLA` | deck drill template (disc down): pilots for the 3 clamp-ring inserts (PCD 35), the 2 front hanger inserts and the d14 shaft hole; a d18 window over the existing centre hole | Bambu PLA Matte, PLA Fitcheck | 0.67 h | 20.6 g |
| **`base_shell_m2_PETG-CF`** (2026-11-15, **the shell to print**: Brian is reprinting it in matte CF) | base shell, rev m.2 deck, deck down on the plate. Holes checked in the mesh: d18 centre, d14 shaft hole, 3 × d4.0 clamp inserts (PCD 35), 4 × d4.0 hanger inserts, **4 × d4.0 rev k collar holes (r 94.5, diagonals)**, the old d6.3 hole, 4 × d4.0 bottom-plate ear inserts. Island check 0 starts; no supports, no brim | Bambu PETG-CF @BBL H2D 0.4 nozzle (255 / 70 °C, 11.5 mm³/s), **hardened nozzle, extruder 1 (left)**, textured PEI, 0.20 Structural PETG-PLA (4 walls, 4/4, 20 % gyroid), same as the PETG shell | **8.84 h** | **270.3 g** |
| `alternates/base_shell_m2_PETG` | the same shell in PETG Matte (the fallback if the PETG-CF spool runs short) | PETG, as rev j | 8.36 h | 296.3 g |

**PETG-CF shell notes (2026-11-15):**
- **Drill template not needed with the reprinted shell:** every deck hole (rev k collar + rev m.2) is printed in. The deck then takes **11 × M3 × 4 inserts**: 4 collar, 3 clamp ring, 4 hanger.
- **Fits:** the shell has no lip or bore fit to the rotor. Its mating features are the D outline (collar flush on top, bottom plate below) and the d4.0 insert holes. PETG-CF shrinks less than PETG, so the part comes out a hair larger (a few tenths of a mm over 200 mm at most): cosmetic at the outline. The d4.0 holes shrink with the part, so they come out at least as big as in PETG and still grip the M3 × 4 inserts. CF-filled PETG is stiffer and less ductile. Press the inserts slowly, at the same iron temperature as for PETG, and let each one cool before moving on.
- **Spool:** needs about 280 g left (270 g plus purge). The profile is identical to Generic PETG-CF (255 / 70 °C, 11.5 mm³/s), so if the spool isn't Bambu, pick its own preset in Bambu Studio. No re-slice is needed.
- CF is abrasive: the left (hardened) nozzle only, never the right one.

Hardware for rev m.2:
- **Deck:** 7 × M3 × 4 heat-set inserts (3 clamp ring + 4 hanger).
- **Spool:** 4 more inserts.
- **Clamp ring:** 3 × M3 × 6 + washers.
- **Gearbox:** 4 × M3 × 6 SHCS.
- **Hanger:** 4 × M3 × 10 + washers.
- **Buck:** 2 × M3 × 6, plus 2 inserts in the sled's standoffs.
- **Lead guide:** CA it into the spool.

The superseded rev m (SNM022A-06) plate, template and shell are in `../rev-m_superseded/`.
`.gcode` files are git-ignored. Regenerate them with `py slice.py --repack`, or re-slice.
