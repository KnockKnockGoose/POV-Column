# rev n print files (2026-11-17): drive cartridge on the base, pin drive to the rotor

Report: `docs/2026-11-17-rev-n-drive-redesign.md` (why the rev m.2 spool broke, the redesign, assembly steps with pictures). Sliced with `fusionclaude/slicer/slice.py`. Nothing has been sent to the printer.

Rev n **replaces only the drive spool and the lead guide** from `rev-m_CURRENT/revm2_drive_parts_PET-CF_plate`. Everything else from rev m.2 stays: the base shell (no drilling), the clamp ring (now the cup's seat), the motor hanger, the sled, the bottom-cap plate (`rotor_bottom_cap_f`, unchanged file), and the rev k collar, rotor ring, keys and riser. The slip ring is kept too, but it is no longer clamped: it goes in from below and hangs under the deck on its six rotor leads (report section 3.7).

**2026-11-20, rev o:** the next files are in `../rev-o_CURRENT/` (report `docs/2026-11-20-rev-o-cad.md`). **This folder's centring jig no longer centres the as-built hub:** with the clamp ring out the hub sits 3.2 mm lower, so the jig's bore meets the hub's lead-in cone instead of its teeth (0.7-1.0 mm of play). Use `revo_centring_jig_v2` (a collar reaches the tooth tips: 0.22 mm of play).

**2026-11-19, as built on the bench (report `docs/2026-11-19-rev-n-bench-diagnosis.md`):** the clamp ring is **out** (the 20T sits lower on the motor shaft so its set screws grip, and the cartridge dropped 3.2 mm to match; belt plane z −11.3). With it out, the drive pins are **M3 × 20** (4.9 mm engaged, 2.0 mm off the notch floors; × 16 barely reaches) and the cup screws must be **M3 × 6** (an M3 × 8 over the motor hanger reaches 1.5 mm into the hanger and bottoms before it clamps). The hub is CA'd into its 6802 (the journal ribs printed loose). The hanging slip-ring take-up climbed the one time it ran: do not use it again; see report §4.

**2026-11-18, rotor ring refit:** the rev k rotor ring's spigot is loose in the 6820's inner ring. Bigger-rib rings (Ø100.30-101.00; 100.80 predicted from measurements) and a 4-ring 1.2 h fit-test plate are in `rotor_ring_refit/` (README there: test first, then print the matching full ring).

All files: H2D, **left (hardened) nozzle = extruder 1**, textured PEI, 0.2 mm layers, no supports, no brim.

| File | Parts | Material / setup | Time | Mass |
|---|---|---|---|---|
| **`revn_drive_parts_plate_PETG-CF`** (print this) | 2 drive hubs (1 spare; crown down), bearing cup (flat base down), stand-in bush, 2 nut plates (membrane down) | Bambu PETG-CF @BBL H2D 0.4 nozzle (255 / 70 °C), 6 walls, 6/6, 85 % gyroid | **1.19 h** | **14.7 g** |
| **`revn_centring_jig_PETG-CF`** (print this) | centring jig, disc face down | PETG-CF, 0.20 Structural PETG-PLA (4 walls, 4/4, 20 %) | **0.67 h** | **16.1 g** |
| `alternates/revn_nut_plate_x2_PET-CF` | 2 nut plates, same geometry as on the main plate | Fiberon PET-CF @BBL H2D (300 / 70 °C), 6 walls, 6/6, 85 % | 0.29 h | 2.7 g |
| `alternates/revn_slipring_clamp_spare_PET-CF` | clamp ring, rev m.2 geometry; only if the fitted one is damaged | Fiberon PET-CF | 0.19 h | 2.1 g |

- **Island check (script 151):** 0 starts on all eight STLs and all four sliced projects.
- **Span audit:** no unsupported region reaches more than 0.3 mm from support, except the hub's four 4 mm notch ceilings and two 0.8 mm ledges at its lead neck.
- **Single STLs** (print orientation): `cad/revn_drive_hub.stl`, `revn_bearing_cup.stl`, `revn_nut_plate.stl`, `revn_centring_jig.stl`, `revn_bush_standin.stl`, `revn_slipring_clamp_spare.stl`; plates `revn_drive_parts_plate.stl`, `revn_nut_plate_x2.stl`.
- If the PETG-CF spool is the Elegoo one, the Bambu profile is the one the shell was printed with.
- The main plate was re-sliced at 19:10 on 2026-11-17 with the final hub (lead neck 4.6 × 3.0). Same time and mass as before.

## Fits to check off the bed

| Fit | Drawn | If it's off |
|---|---|---|
| 6802 bearing (Ø24) into the cup | bore Ø24.4, 8 crush ribs to Ø23.85 | thumb pressure on the outer ring; scrape the ribs if too tight |
| hub journal into the bearing bore (Ø15) | journal Ø14.6, 8 ribs to Ø15.10 | scrape the ribs; a drop of CA if loose |
| M3 nuts into the nut plate | hex 5.6 AF × 2.6 deep | press in; ream the pocket lightly if needed |
| XH header in the nut plate | window 7.6 × 5.95, 2 tail holes Ø1.3 at 2.5 mm | open the tail holes with a 1 mm drill |
| nut plate in the hub core's pocket | Ø22.2 × 4.0 in Ø22.4 × 4 | sand the rim |
| drive pins (M3) in the hub's notches | notches 4.0 wide: 0.5 mm play each side | should be loose |
| the six slip-ring leads in the hub's neck | slot 4.6 × 3.0 | they must slide freely; clear any strings with a 2.5 mm drill |
| stand-in bush on the journal | bore Ø15.5 on the Ø15.1 ribs | must turn freely; grease it |
| jig on the hub and in the 6820 | hole Ø25.4 on the Ø24.96 tooth tips; skirt Ø99.7 in the Ø100 bore | should drop on |

## Hardware

- **From your kits:** 4 × M3 × 16 socket screws (the drive pins; **not × 20**), 4 × M3 nuts, 3 × M3 × 8 socket screws (replace the clamp ring's 3 × M3 × 6; keep the washers), 1 small zip tie (the stop on the leads), 2 × 110 mm of 26 AWG wire, grease.
- **To buy** (report section 7): 6802-2RS bearing, 15 × 24 × 5 mm; JST-XH 2.54 mm kit with 2-pin headers, plugs and contacts, if the connector kit has none.

## The leads, in short (report section 5, steps 5 to 7)

1. Knot in the six rotor leads, about 10 mm above the slip ring.
2. From below the deck, push the leads up through the deck hole and the clamp ring.
3. Thread them through the cartridge; screw the cartridge down with the jig in place.
4. Pull the leads up until the knot stops. Zip tie at **32 mm** above the top of the hub; cut at **46 mm**; crimp the XH plug (3 + 3).
5. Let go: the slip ring hangs on the zip tie. Leave its stator leads a loose 60 mm loop, and tie every other wire to the shell wall.

`.gcode` files are git-ignored. Regenerate them with `py slice.py --repack`, or re-slice.
