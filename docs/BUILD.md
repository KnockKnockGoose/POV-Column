# Build guide (outline)

This is the order I would build it in now, with a pointer to the document that has the detail for each step. It is an
outline, not a kit manual: the detailed documents were written during the build and some of them describe an earlier
revision. Where one of them disagrees with this page, with [`cad/README.md`](../cad/README.md) or with the firmware,
those three win.

Read the [safety section](../README.md#safety) first. Parts: [BOM.md](BOM.md). Files to print:
[`cad/README.md`](../cad/README.md).

**Time:** about 42 h of printing, two or three evenings of soldering (24 strips, their jumpers and a perfboard), and
a day of assembly and tuning if nothing surprises you. Something will.

## 1. Print

1. Print the **fit coupons** and the **ring fit test** first. Leave them 30 minutes to cool, then try them on the
   real bearings. They choose three sizes for your printer and filament: the cup's bore and the hub's journal for
   the 6802 (the rev o print README says how to read them), and the rotor-ring spigot that **slides** into the 6820
   with one hand.
2. Print the 13 parts in [`cad/README.md`](../cad/README.md). Dry PET-CF and PETG-CF before printing. The tube is
   the long one (15 h): check that a strip fits its rails on the `tube_end_rings_fitcheck` piece before you start it.
3. Seat every heat-set insert **flush or slightly below** the surface. Check with a straight edge. An insert 2 mm
   proud tilted my motor and my hub.

Detail: [`cad/print/README.md`](../cad/print/README.md) for the rev j and rev k parts, the READMEs in
`cad/print/rev-m_CURRENT/`, `rev-n_CURRENT/` and `rev-o_CURRENT/` (the last one has "Reading the coupons"),
[2026-11-03-fdm-optimisation.md](2026-11-03-fdm-optimisation.md) and
[2026-11-20-rev-o-cad.md](2026-11-20-rev-o-cad.md).

## 2. Electronics on the bench

4. **Flash the ESP32 over USB before you solder it in.** Copy `software/firmware/src/wifi_secrets.example.h` to
   `wifi_secrets.h`, fill in your network, and flash the bench sketch (`phase0`). After the rotor is closed, every
   update is over Wi-Fi. The board asks your router for an address and answers as `pov.local`; if that name does not
   resolve on your PC, give the board a fixed address with the four optional lines in the same file.
5. Build the carrier board: screw terminals, power buses, capacitors, the 74AHCT125, the series resistors, the hall
   pull-up, then the ESP32. The wiring guide walks through it one layer at a time with a figure for each.
6. Test with one strip on the bench before any strip goes in the tube. The bench sketch has a serial menu for it
   (chains, colours, the hall input, the current cap).

Detail: [2026-11-04-wiring-build-guide.md](2026-11-04-wiring-build-guide.md) (sections 2 to 5),
[2026-11-02-electrical-design.md](2026-11-02-electrical-design.md) (schematics, netlist, bring-up steps),
[2026-11-04-spi-signal-investigation.md](2026-11-04-spi-signal-investigation.md) (if the LEDs sparkle).

Two things the older documents get wrong for the machine as built: the hall sensor is on **GPIO 26** (GPIO 27 was
damaged on mine), and there is no DC jack: the 12 V supply's leads go straight to the speed controller.

## 3. Strips

7. Cut 24 pieces of 14 LEDs on the pads. Solder leads to the back pads of the input end, test each piece.
8. Slide the strips into the tube's rails. **Odd-numbered strips go in upside down**, so the data runs up one strip
   and down the next (a serpentine), in two chains of 12.
9. Join strip to strip with short ribbon jumpers. The joint is made with the pads facing up beside the tube, then
   the slack is folded back inside the wall.

Detail: [2026-11-04-wiring-build-guide.md](2026-11-04-wiring-build-guide.md) (strip ends, jumpers, the serpentine
map), [2026-11-02-v2-24-strips-tie-rods.md](2026-11-02-v2-24-strips-tie-rods.md) (why 24 strips in 3 sets).

One note for the firmware: on my build the strips ended up one rail back from the drawing. That is one constant,
`SET_SHIFT` in `software/povgen/povanim.py` (2 as built, 0 as designed). If your rows look shuffled in threes, that
is the setting, and `gen_dog_ball.py --povmap` regenerates the firmware's table from it.

## 4. Rotor

10. Bottom-cap plate: inserts, the hall sensor glued into its pocket, the hub core screwed on from below.
11. The four **drive pins** (M3 threaded rod) go through the hub core into the nut plate. Use the pin-centring jig,
    and leave about 12 mm standing proud so about 6 mm engages the hub. With 1 mm engaged, mine cammed out.
12. Hex keys, rotor ring, tie rods. Scrape the ring's spigot until it is a one-hand sliding fit in the 6820.
    Never print it tighter.
13. Sled, carrier board, power bank and the fused pigtail. Land every lead on its terminal.
14. Tube, then the top cap. Tighten the four nyloc nuts evenly, a little at a time.

Detail: [2026-11-09-rev-k-rim-bearing.md](2026-11-09-rev-k-rim-bearing.md) (the ring and the collar),
[2026-11-17-rev-n-drive-redesign.md](2026-11-17-rev-n-drive-redesign.md) (the pins),
[2026-11-21-rev-o-concentricity.md](2026-11-21-rev-o-concentricity.md) (keeping the stack straight).

## 5. Base and drive

15. Base shell: inserts, the speed controller and its knob, the supply leads, the riser with **two** stacked magnets.
16. **The 6820: flush the factory grease out with isopropyl alcohol while turning it, let it dry, add four to six
    drops of light oil.** Then press it into the collar by its outer ring. Flick the inner ring: it should spin
    freely and coast. Mine did not, for four days.
17. Motor and 20-tooth pulley on the hanger. The 40-tooth hub on its 6802 in the cup. With the belt off, centre the
    cup under the big bearing with centring jig v3, then tighten its screws.
18. Belt on, at 5 to 8 N per strand: it should deflect easily under a finger. Tighter loads the small bearing and
    costs speed.

Detail: [2026-11-22-drive-redesign.md](2026-11-22-drive-redesign.md) (the bearing, the belt, the numbers),
[2026-11-19-rev-n-bench-diagnosis.md](2026-11-19-rev-n-bench-diagnosis.md), the README in
`cad/print/rev-o_CURRENT/` ("How to use it (centring the cup)").

## 6. First spin

19. Motor and drive alone first, no rotor. Note the current at 12 V: mine draws 124 to 180 mA. A lot more means
    something is binding.
20. Lower the rotor on and turn it by hand until the pins drop into the hub's notches.
21. Clamp the base. First spin inside a box. Step up: 100, 150, 225 rpm. Mine takes 233 mA at 224.5 rpm with the LEDs
    on. Watch the current more than the rpm: about 24 rpm is lost for every extra 0.1 A.
22. Open `http://pov.local` (or the board's address) from a phone or PC. Run the calibration patterns
    (`POST /api/pattern`), trim the picture's angle (`offset_x8`) until the front is at the front, and flash the
    column firmware (`pov`) over Wi-Fi with `software/firmware/tools/ota_flash.py`.
23. Balance it. I have not done this yet; the method is in the
    [rev k report](2026-11-09-rev-k-rim-bearing.md) (four runs with a trial mass) and `calc/balance_4run.py`.

Detail: [`software/firmware/README.md`](../software/firmware/README.md) (one command per job, the web API). Flash
over Wi-Fi only with `ota_flash.py`: it retries, and it reports success only when the board says it is running the new
build. Thirteen plain OTA uploads in the first week gave two clean flashes, which is why that tool exists.

## 7. Put something on it

```
py software/examples/test_pattern.py
py software/pipeline/pov_request.py "test pattern" --script software/examples/test_pattern.py --target http://pov.local --wait-playing
```

Then the rest of [`software/README.md`](../software/README.md): text, live frames, the game, and the model writing
scenes for you.

## Keeping it running

- **Re-oil the big bearing** when the motor current at your usual speed has crept up by about 30 mA.
- **Film it** at a shutter that covers one full repaint: 1/30 s at 225 rpm, 1/25 s at 188 rpm.
- If the picture jumps or tears, look at the hall pulses first (`/api/status` counts rejected ones): gap and magnet
  count before firmware.
