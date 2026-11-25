"""QA finding B2 (2026-11-03): where the 22 serpentine jumpers go, decided with numbers. Run: py calc/b2_jumper_calc.py

The geometry is the rev f column (fusionclaude/lib/povlib.py): tube r 80 / wall 1.6, 48 rails 1.2 x 1.0 (to r 81), printed end-stops 2 mm tall
under every bottom end, 7 mm cap skirts (bore r 83.2), SK9822 strips 12.0 x 0.46 with 5 x 5 x 1.6 LEDs at 16.67 pitch, sets A / B / C staggered
by 5.56 mm, a 4-wire 28 AWG ribbon (1.0 mm OD at 1.27 pitch) per jumper.

Three candidate routes:
  outside  QA option 2: both ends on the bench to the FRONT pads, the ribbon runs on the outside of the tube past the strip ends, over the
           rails, under the skirts; no jumper wall slots.
  inside   QA option 1 geometry: through the wall slot behind each strip end and along the inside of the wall (the design as drawn); the
           second joint of every ribbon made THROUGH the slot after the strip is mounted.
  inside+slack  QA option 3 procedure on the same geometry: the ribbon's second end is soldered pads-up beside the tube with the ribbon pulled
           out of the second slot, then the slack is pushed back in and taped flat (chosen).
Every number below is printed; the reports quote this script.
"""
import math

# --- geometry (mm) --------------------------------------------------------------------------------------------------------
R_OUT, T_WALL, H_TUBE = 80.0, 1.6, 250.0
RAIL_H, STOP_H_TOTAL = 1.0, 2.0                      # rails to r 81; end-stop 2 steps (1.0 and 0.5 proud) under each bottom cut end
STRIP_T, LED_H, LED_W, LED_PITCH = 0.46, 1.6, 5.0, 1000.0 / 60.0
TAPE_T = 0.2
SKIRT_IR, SKIRT_H, CAP_T = 83.2, 7.0, 2.0
LIP_H = 3.0
Z_LED0 = {"A": (250.0 - (13 * LED_PITCH + 2 * LED_PITCH / 3)) / 2}
Z_LED0["B"] = Z_LED0["A"] + LED_PITCH / 3
Z_LED0["C"] = Z_LED0["A"] + 2 * LED_PITCH / 3
STRIP_LEN = 14 * LED_PITCH
Z0 = {k: v - LED_PITCH / 2 for k, v in Z_LED0.items()}          # bottom cut end
Z1 = {k: v + STRIP_LEN for k, v in Z0.items()}                   # top cut end
RIB_OD, RIB_PITCH, N_WIRE = 1.0, 1.27, 4
BEND_R = 2.0 * RIB_OD                                            # the wiring CAD's bend-radius limit for the ribbon
STACK = (N_WIRE - 1) * RIB_PITCH + RIB_OD                        # 4.81: a flat ribbon lying on the tube needs this much z
NEED_BEYOND = STACK + BEND_R                                     # room needed beyond the pad zone for a flat stack + its 90 deg turn
PAD_Z = (0.5, 3.0)                                               # ASSUMED solderable pad zone from the cut line (Brian measures)
PAD_SPAN, PAD_PITCH = 9.0, 2.5                                   # ASSUMED outer-edge span / pitch of the four end pads (Brian measures)
SLOT_W_OLD, SLOT_W_NEW, SLOT_H, SLOT_OFF = 7.0, 10.0, 5.0, 1.0
LOOP, FOLD_R = 10.0, 2.3                                         # rev g slack loop: overshoot past the second slot, hairpin radius
STRIP_DEG, N_STRIP, CHAIN_LEN = 15.0, 24, 12
RIB_G_PER_M = 1.1                                                # per 28 AWG ribbon wire (povwire WIRE["28r"])
FEED_EVERY = 3

# --- jumper ends by strip set and tube end -----------------------------------------------------------------------------------
ends = []                                                        # (strip, set, end)
for s in range(N_STRIP):
    if s % CHAIN_LEN >= CHAIN_LEN - 1:
        continue
    end = "top" if s % 2 == 0 else "bottom"
    for t in (s, s + 1):
        ends.append((t, "ABC"[t % 3], end))
count = {}
for _, k, end in ends:
    count[(k, end)] = count.get((k, end), 0) + 1
led0_edge = {k: Z_LED0[k] - LED_W / 2 for k in "ABC"}             # lower edge of LED0's package above the tube bottom
led13_edge = {k: Z_LED0[k] + 13 * LED_PITCH + LED_W / 2 for k in "ABC"}

print("== B2: the 22 jumpers = 44 ribbon ends; strip-end geometry (mm) for the OUTSIDE route (QA option 2)")
print("   a flat 4-wire ribbon stack is %.2f tall; with its 90 deg turn it needs %.1f mm of strip/tube beyond the pad zone" % (STACK, NEED_BEYOND))
print("   %-10s %5s %6s | %14s %14s | %7s %7s | %s" % ("end", "set", "ends", "beyond cut end", "pad -> LED edge", "fit out", "fit in", "verdict"))
squeezed = 0
rows = []
for end in ("bottom", "top"):
    for k in "ABC":
        n = count.get((k, end), 0)
        if end == "bottom":
            beyond = Z0[k] - 0.0                                 # cut end down to the tube bottom (the end-stop lives in it)
            to_led = led0_edge[k] - (Z0[k] + PAD_Z[1])           # pad zone top to the LED0 package edge
        else:
            beyond = H_TUBE - Z1[k]
            to_led = (Z1[k] - PAD_Z[1]) - led13_edge[k]
        fit_out = max(0, int(math.floor((beyond - BEND_R + (RIB_PITCH - RIB_OD)) / RIB_PITCH))) if beyond > BEND_R else 0
        fit_in = max(0, int(math.floor((to_led - 0.3 + (RIB_PITCH - RIB_OD)) / RIB_PITCH)))
        ok_flat = beyond >= NEED_BEYOND
        if ok_flat:
            verdict = "flat stack beyond the end (%s the skirt)" % ("under" if (beyond <= SKIRT_H) else "outside")
        elif fit_out + fit_in >= N_WIRE:
            verdict = "no flat stack: 2 wires round the end + 2 over the component zone (margins %.1f / %.1f)" % (beyond - 2 * RIB_PITCH - BEND_R + (RIB_PITCH - RIB_OD), to_led - 2 * RIB_PITCH)
            squeezed += n
        else:
            verdict = "does not fit"
            squeezed += n
        rows.append((end, k, n, beyond, to_led, fit_out, fit_in, verdict))
        print("   %-10s %5s %6d | %14.2f %14.2f | %7d %7d | %s" % (end, k, n, beyond, to_led, fit_out, fit_in, verdict))
print("   -> %d of %d ribbon ends sit where only %.2f mm of tube lies beyond the cut end (set A bottom, set C top): the 'under the skirt' ends are exactly the ones with no room" % (squeezed, len(ends), Z0["A"]))
under_skirt = sum(n for (k, end), n in count.items() if (end == "bottom" and Z0[k] + PAD_Z[1] <= SKIRT_H) or (end == "top" and Z1[k] - PAD_Z[1] >= H_TUBE - SKIRT_H))
print("   joints hidden by the 7 mm skirts on the outside route: %d of %d; visible on the dark strip ends: %d" % (under_skirt, len(ends), len(ends) - under_skirt))
rib_top_rail = R_OUT + RAIL_H + RIB_OD
rib_top_face = R_OUT + STRIP_T + RIB_OD + 0.3
led_top = R_OUT + STRIP_T + LED_H + TAPE_T
print("   radial, outside route: ribbon over a rail top r %.2f, on a strip face with its fillet r %.2f, LED top + tape r %.2f; skirt bore r %.1f -> %.2f / %.2f / %.2f mm" % (
    rib_top_rail, rib_top_face, led_top, SKIRT_IR, SKIRT_IR - rib_top_rail, SKIRT_IR - rib_top_face, SKIRT_IR - led_top))
print("   a top-end ribbon beyond a set-C cut end (%.2f mm of tube) against the top cap plate at z %.0f: the lower of two stacked wires at z %.2f, the upper's edge at z %.2f (plate at %.0f)" % (
    H_TUBE - Z1["C"], H_TUBE, Z1["C"] + BEND_R, Z1["C"] + BEND_R + RIB_PITCH + RIB_OD / 2, H_TUBE))

print("== INSIDE route (the design as drawn), slot width against the end pads")
print("   assumed pad span %.1f (outer edge to outer edge), pitch %.1f, pad zone %.1f-%.1f from the cut line (MEASURE: E15)" % (PAD_SPAN, PAD_PITCH, *PAD_Z))
for w in (SLOT_W_OLD, SLOT_W_NEW):
    hidden = max(0.0, (PAD_SPAN - w) / 2)
    print("   slot %4.1f wide: outer pads hidden behind the wall by %.2f mm each side; wall left to the rail root (6.3 from the strip centre) %.2f mm" % (w, hidden, 6.3 - w / 2))
print("   slot z: cut + %.1f .. cut + %.1f; solderable pad inside the slot footprint %.1f mm (>= 1.5 needed); the lower edge cannot drop: set-A bottom ribbons sit %.2f mm above the 3 mm cap lip" % (
    SLOT_OFF, SLOT_OFF + SLOT_H, PAD_Z[1] - SLOT_OFF, (Z0["A"] + SLOT_OFF + 0.5 - RIB_OD / 2) - LIP_H))
perf = 8 * SLOT_W_NEW / (2 * math.pi * R_OUT) * 100
print("   end-ring perforation per z band: 8 slots x %.0f mm = %.0f of %.0f mm circumference (%.0f %%); slot bridge in the upright print %.0f mm (PETG: 7-10 accepted elsewhere)" % (
    SLOT_W_NEW, 8 * SLOT_W_NEW, 2 * math.pi * R_OUT, perf, SLOT_W_NEW))

print("== procedure for the second joint of every ribbon")
pull = 2 * LOOP + math.pi * FOLD_R
chord = 2 * (R_OUT - T_WALL - 0.6) * math.sin(math.radians(STRIP_DEG / 2))
print("   through-slot (option 1): 44 joints made through a %.0f x %.0f window to pads facing away, iron within ~25 deg of the wall, no inspection" % (SLOT_W_NEW, SLOT_H))
print("   slack loop (option 3, CHOSEN): ribbon out of the second slot by %.0f mm (2 x %.0f overshoot + a %.1f mm-radius fold) -> strip lies pads-up beside the tube; loop pushed back and taped" % (pull, LOOP, FOLD_R))
routed_old = chord + 2 * 5.0
routed_new = routed_old + pull
print("   ribbon routed: %.0f mm (wall chord %.1f + two dives) -> %.0f mm with the loop; cut %.0f -> %.0f (routed + 2 x 4, rounded up to 5)" % (
    routed_old, chord, routed_new, 5 * math.ceil((routed_old + 8) / 5), 5 * math.ceil((routed_new + 8) / 5)))
m_old = 22 * 4 * routed_old / 1000.0 * RIB_G_PER_M
m_new = 22 * 4 * routed_new / 1000.0 * RIB_G_PER_M
print("   ribbon mass on the rotor: %.1f g -> %.1f g (+%.1f g, symmetric: every strip has one loop at one end); 22 x 65 mm = %.2f m of 4-wire ribbon (owned: 2 x 16 ft)" % (m_old, m_new, m_new - m_old, 22 * 0.065))
print("   serviceability: a dead strip's two loops are pulled out through its own two slots (%.0f mm each), both joints are then outside the wall" % pull)
print("== slots that stay in use: every strip end has a jumper, a feed or a start lead except the bottoms of strips %d and %d (unused DOUT): 46 of 48" % (CHAIN_LEN - 1, 2 * CHAIN_LEN - 1))
print("== what Brian measures on a peeled reel end (defaults in brackets): outer-edge pad span [%.1f -> slot %.0f], pad zone from the cut line [%.1f-%.1f -> slot from +%.1f], pad order across the strip" % (
    PAD_SPAN, SLOT_W_NEW, PAD_Z[0], PAD_Z[1], SLOT_OFF))
