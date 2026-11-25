# Bill of materials

What is on the column as it runs today (rev o, 2026-11-24), then what is bought and waiting, then what is only
planned. The same list as data: [bom.csv](bom.csv).

Prices are what I paid or what the listing said in November 2026 (US, mostly Amazon), and they move. Where a price
says "kit" or "owned", the part came out of a drawer. The first shopping list, with links as they were on
2026-11-01, is [2026-11-01-parts-and-links.md](2026-11-01-parts-and-links.md); the drive, the bearing and the LEDs
changed after it, so trust this page over that one.

## Fitted

### Rotor electronics

| Item | Spec | Qty | Price | Notes |
|---|---|---|---|---|
| LED strip | SK9822 (APA102-compatible, clocked), 60 LEDs/m, 5050, black PCB, 12.0 mm wide, 16.67 mm pitch | 24 pieces of 14 LEDs (5.6 m) | $43.99 per 5 m reel | Cut on the pads. Odd strips go in upside down |
| Microcontroller | ESP32 DOIT DevKit V1, 30-pin, ESP-WROOM-32, 25.4 mm row pitch | 1 | owned | Soldered straight to the carrier |
| Level shifter | SN74AHCT125N, DIP-14 | 1 | $7.99 for 10 | 3.3 V to 5 V for the two clock and two data lines |
| Carrier board | perfboard, 70 x 90 mm, 26 x 31 holes | 1 | owned | Layout and netlist: [electrical design](2026-11-02-electrical-design.md) |
| Screw terminals | 2.54 mm pitch: two 6-pin (one per LED chain), one 3-pin (hall), six 2-pin. 5 mm pitch: two 2-pin (5 V in) | 11 | kit | |
| Capacitors | 1000 uF electrolytic x 2, 100 nF ceramic x 3, 1 nF x 1 | | kit | Bulk capacitance on the 5 V bus, decoupling, hall filter |
| Resistors | 68 ohm x 4 (series, on the SPI lines), 10 k x 5 | | kit | |
| Fuse | 5 x 20 mm fast-blow, inline holder: **3 A fitted**, the design says 4 A | 1 | | In the 5 V lead from the power bank |
| Power bank | 10,000 mAh USB power bank with a USB-A port rated 5 V 3 A, about 199 g (mine is an INIU) | 1 | $22.99 | Rides on the rotor, strapped near the axis |
| USB pigtail | USB-A to bare leads, 22 AWG | 1 | $7.99 for 2 | |
| Hall sensor | A3144, TO-92, open collector, 10 k pull-up to 3.3 V | 1 | $6.99 for 20 | On **GPIO 26** (the firmware is right; older reports say 27) |
| Wire | 22 AWG silicone (power), 26 AWG (strip leads), 28 AWG ribbon (strip-to-strip jumpers) | | | Cut list: [img/wiring_cut_list.csv](img/wiring_cut_list.csv) |

### Drive and base

| Item | Spec | Qty | Price | Notes |
|---|---|---|---|---|
| Motor kit | JGB37-520 12 V DC gearmotor sold as "600 rpm" (540 rpm measured with no load), with a PWM speed controller board and a knob | 1 | $19.99 | The knob sets the speed; the firmware does not control the motor |
| 12 V supply | bench supply, or a 12 V adapter of 2 A or more | 1 | owned | The column draws 0.23 A at speed |
| Motor pulley | GT2, 20 teeth, 6 mm bore | 1 | about $5 to $10 | |
| Belt | GT2 closed loop, 6 mm wide, 122 mm long (61 teeth) | 1 | about $8 to $12 | The 40-tooth pulley is the printed hub |
| Rotor bearing | 6820ZZ deep-groove ball bearing, 100 x 125 x 13 mm | 1 | about $22 | **Flush out the grease and oil it before fitting** |
| Hub bearing | 6802-2RS, 15 x 24 x 5 mm | 1 | about $6 for 10 | |
| Magnets | neodymium discs, 6 x 3 mm | 2 (stacked) | $7.49 for 80 | On the base's riser; they pass the hall sensor once per turn |

### Fasteners

| Item | Spec | Qty | Notes |
|---|---|---|---|
| Tie rods | M3 stainless threaded rod, cut to about 261 mm | 4 | Clamp the caps onto the tube |
| Nuts for the tie rods | M3 nyloc x 8, M3 plain x 4 | 12 | |
| Drive pins | M3 threaded rod, about 12 mm standing proud of the hub core, locked with nuts | 4 | The length was set on the bench: about 6 mm of engagement in the hub |
| Heat-set inserts | M3 x 4 and M3 x 6, brass | about 29 | Deck 11, shell ears 4, controller 4, base plate 4, hub core 4, sled 2. **Seat them flush or below** |
| Screws | M3 x 6, M3 x 8, M3 x 10 (pan head and countersunk) | about 30 | From an assortment kit |

## Bought, not fitted yet ("option D": the battery off the rotor)

| Item | Spec | Qty | Price | Notes |
|---|---|---|---|---|
| Slip ring | 12.5 mm capsule slip ring, 6 wires at 2 A, rated to 300 rpm | 1 (+1 spare) | about $10 each | Fixed under the deck in a printed bracket |
| Pogo pins | Mill-Max 0908 series spring-loaded pins | 3 | about $1 each | They carry the supply across the joint between the hub and the rotor, so the rotor still lifts off by hand |
| Buck converter | 12 V to 5 V, 5 A or more | 1 | about $8 to $12 | On the rotor, in place of the power bank: the slip ring brings 12 V up |

## Planned

A 2 A fuse and a Schottky diode on the 12 V feed through the slip ring, and the 4 A fuse the design calls for.

## Tools I actually used

A soldering iron with a fine tip, flux and Kapton tape; a multimeter; a bench supply with a current readout (the
motor's current is the best gauge of how the drive is doing); calipers; a heat-set insert tip; isopropyl alcohol and
light machine oil for the bearing; a phone that films at 240 fps.

## Not on the list on purpose

There is no motor driver on the ESP32, no encoder and no slip ring in the as-built machine. Speed is set by hand with
the kit's knob, and the firmware measures the turn time from the hall pulse and follows whatever the motor does.
