# POV LED Column rev m: what to buy (and what you already have)

**Prepared for Brian** · Claude (Opus 5.5), laptop session · 2026-11-13

Built from: the rev m CAD report (`docs/2026-11-13-rev-m-cad.md`: 154 checks, 0 fail), the rev m study's parts list (`docs/2026-11-13-rotor-power-and-wobble.md` §6.1), and your inventory (`fusionclaude/shop/inventory.yaml`, `docs/2026-11-01-parts-and-links.md` §2).
Prices are estimates. Links are searches unless marked: check the live listing.

## 1. Buy

| # | Part | Exact spec (from the CAD) | Link | Est. |
|---|---|---|---|---|
| 1 | **Slip ring** (rev m.2) | **Generic 12.5 mm 6-circuit capsule**, 6 × 2 A, 0-300 rpm: Ø24 × 1.2 flange with 3 × Ø3.2 on PCD 18, Ø12.5 × 15 body, Ø5 rotor boss, 6 + 6 leads 225 mm, 30 AWG PTFE. **Buy 2 (one spare).** The CAD (v13, `docs/2026-11-13-rev-m-cad.md` §9) is drawn to the seller's drawing (the seller's drawing (not included here)). The SNM022A-06 is no longer needed. | the listing you picked | **~$10 each, ~$20** |
| 2 | **GT2 20T pulley** | **6 mm bore**, for 6 mm belt, set screws. Any hub size works now: with the Ø24 flange the hub clears the slip ring by 10.7 mm and the clamp ring by 5.1 mm (rev m.2). | [Amazon](https://www.amazon.com/s?k=GT2+20+teeth+pulley+6mm+bore+6mm+width) | $5-10 |
| 3 | **GT2 closed-loop belt, 6 mm** | **122 mm** (61 teeth) is the design length. Get a **multi-length pack that includes 122** (110/112 are tension fallbacks). | [Amazon](https://www.amazon.com/s?k=GT2+closed+loop+belt+6mm+122mm) | $8-12 |
| 4 | **Buck converter, 12 V → 5 V** | Adjustable, **≥ 5 A**, XL4015-class, **≤ 20 g, as small as possible**. The CAD assumes the size; measure it when it arrives (Q1). | [Amazon](https://www.amazon.com/s?k=XL4015+5A+buck+converter+adjustable) | $8-12 |
| 5 | **12 V supply** | 12 V **3 A** adapter, 5.5 × 2.1 mm barrel. You own a 9 V and a 24 V adapter, neither of them 12 V. Skip this if you'll run the bench supply at 12 V / 3 A. | [Amazon](https://www.amazon.com/s?k=12V+3A+power+supply+adapter+5.5x2.1) | ~$10 |
| 6 | **Inline fuse, 2 A** | On the 12 V feed to the slip ring (Q5). The ring carries 2 A per circuit, 3 circuits per pole. Blade or 5 × 20 mm, matching your holder. | [Amazon](https://www.amazon.com/s?k=2A+fast+blow+fuse+assortment) | $5-8 |
| 7 | **Step drill bit reaching ≥ 14 mm (9/16")** | Only for the **d14 motor-shaft hole** now (Q2, "drill, don't reprint"). The centre hole stays the deck's existing **d18** (rev m.2: no centre drilling; the 12.5 mm body passes through it). A 4-20 mm or ¼-¾" bit covers it; ½" (12.7) bits are too small. Your inventory has no step bit. **Skip it if you reprint the shell instead** (8.4 h). | [Amazon](https://www.amazon.com/s?k=step+drill+bit+4-20mm) | $10-15 |

**Total: about $55-85** (about $45-75 without the adapter). Rev m.2: the slip ring dropped from $20-30 (SNM022A-06) to ~$20 for two generic capsules.

## 2. Already have: don't buy

| Need (from the CAD) | You have |
|---|---|
| 7 × M3 heat-set inserts (deck: 3 clamp ring + 4 hanger) + 4 × M3 × 4 (spool) | INCLY 440-pc M2-M6 brass insert kit |
| M3 × 6 (motor 4, slip-ring clamp ring 3) + washers, M3 × 10 (spool 4), M3 × 8 + nuts (trim) | NINDEJIN 880-pc M2-M5 SHCS + nuts + washers kit |
| 22 AWG red/black (buck OUT → J1, 110 mm; ~10 mm splices on 5 leads; motor leads recut) | NAOEVO 22 AWG silicone, TUOFENG 22 AWG solid |
| Screw terminals / JST for the slip-ring leads | WEKESIGO JST/Dupont kit, screw terminals |
| CA (lead guide into the spool), heat-shrink | Starbond CA, Ginsco heat-shrink kit |
| Motor, PWM controller | Copkim 12 V 600 rpm kit (the motor stays; it moves onto the new hanger) |
| 6820ZZ bearing | **Ordered** (confirmed today) |
| PET-CF, PETG, PLA for the prints | On the printer (rev k setup) |
| Spare LED strip | SK9822 reels (cut a replacement test strip from a reel) |

## 3. Check before ordering

| Item | Why |
|---|---|
| **M3 × 300 threaded rods** (rev k) | The rev k plan needs them. I can't find them in the inventory or confirm they were ordered with the 6820. Rev k §6 has the spec. |
| **4 A fast-blow fuse** | Only for the rev k week while the bank is still on the rotor. Rev m removes the bank, and the 5 V fuse with it. Buy it only if you'll run on the bank for days. |
| Fuse holder for the 12 V line | The rev m study says you have one. Confirm it takes the fuse you buy (blade vs glass). |

## 4. Print (not buy)

From `cad/print/rev-m_CURRENT/`. These are sliced but not sent to the printer.

| Plate | Material | Time | Mass |
|---|---|---|---|
| Drive parts: spool + lead guide + slip-ring clamp ring + motor hanger (rev m.2) | PET-CF | 1.55 h | 26.0 g |
| Centred sled v2 | PETG | 1.55 h | 28.7 g |
| Deck drill template (rev m.2: d18 window, no centre drilling) | PLA | 0.67 h | 20.6 g |
| *(alternative)* Base shell, only if not drilling | PETG | 8.36 h | 296.3 g |

## 5. When the parts arrive

1. Measure the **slip ring** (CAD report §9.6: flange thickness, body length, lead OD) and the **buck** (PCB size, holes, mass). The 20T pulley's hub no longer matters. Script 169 re-solves the board and buck position in one run (CAD report Q1).
2. Dry-fit the board in the printed sled **before** cutting or splicing any lead (Q3).
3. Set the buck to **5.00 V** on the bench before it touches the carrier.
