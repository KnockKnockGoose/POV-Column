"""Perfboard carrier-board layout (top view, 2.54 mm grid) -> docs/img/elec_carrier_layout.svg/.png, a build list
(docs/img/elec_carrier_netlist.txt) and the same tables as JSON for the Fusion wiring CAD (docs/img/elec_carrier_netlist.json,
read by fusionclaude/lib/povcarrier.py so the 3D board is built from the layout that passed the checks here).
Run: py software/elec/elec_carrier.py

Board (rev i, 2026-11-04): Brian's 70 x 90 mm double-sided plated Rindion perfboard, UNCUT, with the holes he COUNTED
(docs/measurements.md #31): 26 x 31 holes on the 2.54 mm grid, columns printed A-Z across the 70 mm side, rows printed 1-31 along the
90 mm side; margins 3.25 mm each side across (centred), 7.5 mm from the row-1 edge to row 1 (measured at Z1) and 5.5 mm from the
row-31 edge (7.5 + 30 x 2.54 + 5.5 = 89.2 against the calipered 90.0: within measuring error; the model keeps 90.0 and the 7.5).

ORIENTATION: hole A1 at the BOTTOM LEFT with the COMPONENT SIDE facing you. The row-1 end goes DOWN into the sled (its 7.5 mm margin
puts row 1 at z 18.5, 0.08 mm under rev h's row 2, so every hole lands where rev h had one); column A is on the left seen from the
component side (from the solder side the letters run Z..A left to right). Components toward -y (away from the bank), USB end of the
ESP32 UP, the 90 mm edges in the sled's card guides.

Grid: hole (c, r), c = 0..25 = printed column letter A..Z, r = 0..30 = printed row number - 1 (label(c, r), e.g. (3, 2) = D3).
Board frame (drawing, checks): x = (c - 12.5) * 2.54 from the board's centre line (which falls BETWEEN columns M and N), figure y =
7.5 + 2.54 r from the bottom edge (z_abs = 18.5 + 2.54 r). The DevKit's two pin columns are ten columns apart (I and S), so its centre
column N sits half a pitch (+1.27 mm) right of the board's centre line; the CAD keeps the DevKit and every part and wire exactly where
rev h had them (column N on the rotor axis, x_cad = (c - 13) * 2.54) and instead puts the board outline and both card guides 1.27 mm
toward -x (BOARD_X): that keeps every wire route, cut length and the cut list valid, keeps the pigtail cable 1.1 mm clear of the board's
-x edge, and moves the rotor's unbalance the right way (the board's FR4 + the guide posts go toward the side opposite the CG).

The drawing is the COMPONENT side; solder-side wires are drawn as if the board were transparent (same coordinates, no mirror).
Fractional coordinates are mid-path points of insulated wires (lanes; they only need a hole at their ends). A hole-to-net check at the end
of the script asserts that every wire end lands on a hole of its own net, that no solder lands in the card guides' grip, that no two
component-side bodies overlap, that nothing stands under the ESP32 board or in the path of a USB plug, and that the bottom terminals keep
the S-bend height their wires need.

Revision 2026-11-04 i (Brian counted the holes): the rev h layout is kept hole for hole; NC x NR = 26 x 31 (was an assumed 27 x 35); every
  ROW below = rev h row - 2 (rev h's rows 0-1 do not exist on the real board: row 1 is 7.5 mm up), columns unchanged (C..X used; A, B, Y, Z
  spare); the DevKit body / USB keep-out are centred on its pin columns (ESP_X) instead of x 0; U1's body is drawn from its pins; the card-
  guide rule is now geometric (no hole's pad reaches the guides' 1.5 mm grip: columns A / Z are 3.25 mm in); every hole carries its
  printed label in the figure, the build list and the JSON. Nothing electrical changed. The notes below quote their holes in the numbering
  of their own revision (rev h = rev i + 2 rows; rev d = rev h - 2 columns).
Revision 2026-11-03 h (70 x 90 board): the rev d layout shifted TWO COLUMNS RIGHT on an assumed 27 x 35 grid so the DevKit stayed on the
  board's centre line; columns 0-1 / 25-26 and rows 31-34 spare; the card guides at c 0 / c 26.
Revision 2026-11-03 d (switch removed, Brian's decision): the KCD11 rocker SW1, its loop and the J2 terminal are gone; plugging the
  pigtail into the bank is the on/off. J1 pin 1 is now 5V_A and lands on bus A through one short insulated 22 AWG tap.
Revision 2026-11-02 c (ESP32-30 fix, Brian's measured board + his connector choices):
  * U2 is the 30-pin DOIT ESP32 DevKit V1 (15 pins per row, 25.4 mm row pitch as measured), SOLDERED STRAIGHT to the
    perfboard (no female headers: the DevKit's own male pins go through the board, its PCB sits 2.5 mm above it). Pin order
    from the Mischianti high-resolution pinout (https://mischianti.org/doit-esp32-dev-kit-v1-high-resolution-pinout-and-specs/),
    confirmed on Brian's board 2026-11-04 (measurements #32): with the USB at the bottom and the module facing you, left column
    top->bottom EN, VP, VN, D34, D35, D32, D33, D25, D26, D27, D14, D12, D13, GND, VIN; right column D23, D22, TX0, RX0, D21, D19,
    D18, D5, TX2, RX2, D4, D2, D15, GND, 3V3. On the carrier the USB points UP, so (component side toward you) those columns read
    bottom->top and swap sides: left header (column I) = D23 ... 3V3, right header (column S) = EN ... VIN.
  * 2.54 mm PCB screw terminals (KF128-2.54 family, 8.8 mm tall, side wire entry, 18-26 AWG) replace every JST-XH: J3 / J5 /
    J4 along the bottom edge with the wires entering from BELOW (they S-bend down into the sled's pass-through slots), J9..J11,
    J6..J8 up the right edge with the wires entering from the ESP32 side (-x); J1 / J12 stay the owned 5 mm terminals.
  * Nothing taller than 1.5 mm may sit under the DevKit (its outline +-14.2 mm about its centre, z 28..79.3) or in a USB plug's path
    above its top edge (+-5.5 mm about its centre, z 79..99): the hall network sits top-left, C5 at the bottom beside J5, C2 right of
    the DevKit's top, C1 above J3, R1-R4 under U1, TP1 above the bus-A rail.
Revision 2026-11-02 b (report agent): U1 footprint corrected, chain-0 CLK/DATA on J3 pins 3/5, C1's GND tap on its
negative hole, GND bus off the card-guide columns, J2 pins swapped, TP2 on the bus-B junction.
"""
import json
import os
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, FancyBboxPatch

OUT = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "img")
FLIP = "--flip" in sys.argv                # flipped view: A1 top left, row 1 at the top
P = 2.54
W, H = 70.0, 90.0         # the uncut Rindion 70 x 90 board (calipered by Brian, measurements #27)
NC, NR = 26, 31           # rev i: COUNTED by Brian (measurements #31): columns A-Z across the 70 mm side, rows 1-31 along the 90 mm side
CC = (NC - 1) / 2.0       # 12.5: the board's centre line, between columns M (12) and N (13)
C_AXIS = 13               # column N: the DevKit's centre column (its pins in I = 8 and S = 18); on the rotor axis in the CAD
ESP_X = (C_AXIS - CC) * P  # +1.27: the DevKit's centre, right of the board's centre line (board frame, component side toward you)
BOARD_X = -ESP_X          # -1.27: the board outline's centre in the rotor / CAD frame (the card guides move with it)
MARGIN_X = (W - (NC - 1) * P) / 2.0      # 3.25 each side (measured: centred)
MARGIN_ROW1, MARGIN_ROW31 = 7.5, 5.5     # measured: row 1 to its edge (at Z1), row 31 to its edge; 7.5 + 76.2 + 5.5 = 89.2 vs 90.0 calipered
BOARD_Z_BOT = 11.0        # the board's bottom edge on the sled's guide-slot floors (since rev c)
Z0 = BOARD_Z_BOT + MARGIN_ROW1           # 18.5: z of r = 0 (printed row 1): THE ROW-1 END GOES DOWN
ROW_OFF_REV_H = -2        # every row in the tables = the rev h row - 2 (rev h (c, r) at z 13.5 + 2.54 r sits 0.08 mm above rev i (c, r - 2))
COL_OFF_REV_H = 0         # columns unchanged (rev h numbering = rev i numbering = printed letter index)
POST_TOP = 56.4           # card-guide post tops (sled plate top z 8.4 + PROTO_GUIDE_H 48, fusionclaude povlib)
GUIDE_GRIP = 1.5          # the guides grip the outer 1.5 mm of each 90 mm edge from the board bottom (z 11) up to the post tops
PAD_R = 1.0               # a solder pad + its fillet, radius (the pads are ~1.8 mm)
GUIDE_ROW = next(r for r in range(NR) if Z0 + r * P - PAD_R >= POST_TOP)            # 16: rows 0..15 (printed 1..16) stand beside the posts
GUIDE_COLS = [c for c in range(NC) if abs((c - CC) * P) + PAD_R > W / 2 - GUIDE_GRIP]  # columns whose pads reach the grip: none (A / Z are 3.25 mm in)
REV = "2026-11-04 rev i (26 x 31 holes, counted)"


def label(c, r):
    """Brian's printed label of hole (c, r): column letter + row number, e.g. (3, 2) -> 'D3'."""
    return "%s%d" % (chr(65 + int(c)), int(r) + 1)


def hl(h):
    """'D3 (3,2)': label and grid coordinates of a hole."""
    return "%s (%d,%d)" % (label(*h), int(h[0]), int(h[1]))


def pl(p):
    """A path point: a hole as 'D3 (3,2)', a lane point as '(4.6,4.6)'."""
    return hl(p) if is_hole(p) else "(%g,%g)" % (p[0], p[1])


def xy(c, r):
    """Board frame: x from the board's centre line, y from its bottom edge (mm)."""
    return (c - CC) * P, MARGIN_ROW1 + r * P


def z_of(r):
    return Z0 + r * P


def is_hole(p):
    return float(p[0]).is_integer() and float(p[1]).is_integer()


# ---------------------------------------------------------------- U2: DOIT ESP32 DevKit V1, 30-pin, soldered direct. With the USB pointing UP (toward
# row 31) and the component side toward the viewer, the rows read (bottom = antenna end -> top = USB end):
ESP_L = ["IO23", "IO22", "TX0", "RX0", "IO21", "IO19", "IO18", "IO5", "IO17", "IO16", "IO4", "IO2", "IO15", "GND", "3V3"]
ESP_R = ["EN", "VP", "VN", "IO34", "IO35", "IO32", "IO33", "IO25", "IO26", "IO27", "IO14", "IO12", "IO13", "GND", "VIN"]
ESP_C = {"L": 8, "R": 18}       # columns I and S, ten columns = 25.4 mm apart, centred on column N (C_AXIS)
ESP_R0 = 7                      # rev i: printed rows 8..22 (rev h rows 9..23)
ESP_N = 15
assert (ESP_C["L"] + ESP_C["R"]) / 2.0 == C_AXIS
ESP_BOARD = (28.33, 51.45)      # DOIT DevKit V1 outline w x l (espboards.dev); header rows 25.4 apart (measured by Brian)
ESP_ANT_OVERHANG = 8.4          # antenna-end edge below the first pin row; the USB-end edge is 51.45 - 35.56 - 8.4 = 7.5 above the last
ESP_LIFT = 2.54                 # the male header's plastic spacer: DevKit PCB underside 2.54 mm above the carrier's component face
USB_KEEPOUT = (11.0, 20.0)      # a micro-USB plug's overmold: +-5.5 about the DevKit's centre for 20 mm beyond its top edge; nothing tall there
# 2.54 mm screw terminals (KF128-2.54 family): 8.8 mm tall, M1.6 screws, 18-26 AWG, 8 A (LCSC / makerselectronics listings);
# body depth and the pin's offset from the back face are not published: 6.5 / 2.5 assumed from the KF128 drawing. MEASURE one.
TERM254 = dict(pitch=2.54, depth=6.5, height=8.8, pin_from_back=2.5, entry_h=3.4, entry_d=2.2)
TERM5 = dict(pitch=5.08, w=7.6, d=10.0, height=10.0)     # the owned 5 mm DIANN terminals (J1, J12)
SBEND_MIN = 8.0                 # a bottom-row terminal's wires S-bend down into the sled slots: >= 8 mm from the body's entry face to the board bottom


def esp_pin(name, side=None):
    for s, names in (("L", ESP_L), ("R", ESP_R)):
        if side and s != side:
            continue
        if name in names:
            return (ESP_C[s], ESP_R0 + names.index(name))
    raise KeyError(name)


ESP_Z0 = z_of(ESP_R0) - ESP_ANT_OVERHANG                 # DevKit PCB bottom edge (antenna end), 27.88
ESP_Z1 = ESP_Z0 + ESP_BOARD[1]                           # top edge (micro-USB), 79.33

# U1 74AHCT125 DIP-14, vertical, NOTCH UP, seen from the component side: pin 1 at the TOP-LEFT D21 (3,20), pins 1-7 run DOWN the
# left column D to D15 (3,14), pins 8-14 run UP the right column G from G15 (6,14) to G21 (6,20).
U1 = {k: (3, 20 - (k - 1)) for k in range(1, 8)}
U1.update({k: (6, 14 + (k - 8)) for k in range(8, 15)})
U1_NAME = {1: "1OE", 2: "1A", 3: "1Y", 4: "2OE", 5: "2A", 6: "2Y", 7: "GND", 8: "3Y", 9: "3A", 10: "3OE", 11: "4Y", 12: "4A", 13: "4OE", 14: "VCC"}
U1_NET = {1: "GND", 2: "IO18", 3: "Y1", 4: "GND", 5: "IO23", 6: "Y2", 7: "GND", 8: "Y3", 9: "IO14", 10: "GND", 11: "Y4", 12: "IO13", 13: "GND", 14: "5V_A"}

C_CONN, C_A, C_B, C_CAP, C_RES, C_TP = "#8ecae6", "#ffc9c9", "#ffe8a3", "#cdb4db", "#bde0fe", "#ffb703"
# name: (holes, label, colour, kind, nets per hole)
#   term  = owned 5 mm screw terminal (2 holes, 5.08 apart)      t254h = 2.54 mm screw terminal, pins in a row along x, wires enter from BELOW (-z)
#   t254v = 2.54 mm screw terminal, pins stacked along z, wires enter from the ESP32 side (-x); t254vx = same, wires enter from the board edge (+x)
#   elco  = radial electrolytic (first hole +)   small = ceramic   axial = resistor standing on the first hole   tp = bare-wire test loop
parts = {
    "J1": ([(3, 25), (3, 27)], "J1 5V in\n(pigtail, 5 mm)", C_CONN, "term", ["5V_A", "GND"]),     # rev d: straight onto bus A (no switch)
    "J12": ([(22, 25), (22, 27)], "J12 bus-B in\n(optional, 5 mm)", C_CONN, "term", ["5V_B", "GND"]),
    "J3": ([(c, 2) for c in range(3, 9)], "J3 chain 0 (6P, wires in from " + ("above" if FLIP else "below") + ")", C_CONN, "t254h", ["5V_A", "GND", "CLK0", "GND", "DATA0", "GND"]),
    "J5": ([(c, 2) for c in range(10, 13)], "J5 hall (3P)", C_CONN, "t254h", ["HALL", "GND", "5V_A"]),
    "J4": ([(c, 2) for c in range(18, 24)], "J4 chain 1 (6P, wires in from " + ("above" if FLIP else "below") + ")", C_CONN, "t254h", ["5V_B", "GND", "CLK1", "GND", "DATA1", "GND"]),
    "J9": ([(22, 4), (22, 5)], "J9 s15 (B)", C_B, "t254v", ["5V_B", "GND"]), "J10": ([(22, 7), (22, 8)], "J10 s18 (B)", C_B, "t254v", ["5V_B", "GND"]),
    "J11": ([(22, 10), (22, 11)], "J11 s21 (B)", C_B, "t254v", ["5V_B", "GND"]),
    "J6": ([(22, 13), (22, 14)], "J6 s3 (A)", C_A, "t254v", ["5V_A", "GND"]), "J7": ([(22, 16), (22, 17)], "J7 s6 (A)", C_A, "t254v", ["5V_A", "GND"]),
    "J8": ([(22, 19), (22, 20)], "J8 s9 (A)", C_A, "t254v", ["5V_A", "GND"]),
    "C1": ([(5, 7), (5, 5)], "C1 1000u\n+ at " + ("BOTTOM" if FLIP else "top"), C_CAP, "elco", ["5V_A", "GND"]),
    "C2": ([(18, 26), (18, 28)], "C2 1000u\n+ at " + ("top" if FLIP else "BOTTOM"), C_CAP, "elco", ["5V_B", "GND"]),
    "C3": ([(6, 22), (4, 22)], "C3 100n", C_CAP, "small", ["5V_A", "GND"]),     # rev h row 24: row 23 overlapped the DIP socket by 0.5 mm
    "C4": ([(9, 25), (9, 27)], "C4 1n", C_CAP, "small", ["HALL", "GND"]),     # column J: one column further right it stood 0.87 mm from a USB plug (CAD check wants 1.0)
    "C5": ([(14, 2), (14, 0)], "C5 100n", C_CAP, "small", ["5V_A", "GND"]),
    "R1": ([(3, 11), (3, 9)], "R1 68", C_RES, "axial", ["Y1", "CLK0"]), "R2": ([(4, 11), (4, 9)], "R2 68", C_RES, "axial", ["Y2", "DATA0"]),
    "R3": ([(5, 11), (5, 9)], "R3 68", C_RES, "axial", ["Y3", "CLK1"]), "R4": ([(6, 11), (6, 9)], "R4 68", C_RES, "axial", ["Y4", "DATA1"]),
    "R9": ([(7, 25), (7, 27)], "R9 10k", C_RES, "axial", ["HALL", "3V3"]),
    "TP": ([(6, 24), (9, 28), (20, 24)], "", C_TP, "tp", ["5V_A", "GND", "5V_B"]),
}
TP_NAMES = ("TP1", "TP3", "TP2")      # in the order of parts["TP"] holes
GND_C, V5A_C, V5B_C, SIG_C, V33_C, V5IN_C = "#111111", "#d62828", "#f77f00", "#1d3557", "#2a9d8f", "#b5179e"
L = label
# (net, gauge, bare?, description, [polylines]); bare = tinned 22 AWG bus wire lying on the solder side, else an insulated wire on its lane
nets = [
    ("GND", "22", True, "GND ring, bare tinned 22 AWG, open: along row 2 from %s to %s, up column X to %s, along row 29 to %s, down column C to %s "
                        "(the card guides grip nothing: columns A / Z are 3.25 mm from the edges; A, B, Y, Z are spare)" % (L(3, 1), L(23, 1), L(23, 28), L(2, 28), L(2, 16)),
     [[(3, 1), (23, 1)], [(23, 1), (23, 28)], [(23, 28), (2, 28)], [(2, 28), (2, 16)]]),
    ("GND", "26", False, "GND taps to the ring: J1.2, C1- (onto J3's GND pin 2), C4, C5, the J3 / J5 / J4 GND pins, the feeds' GND pins, J12.2 "
                         "(J4 pin 6 %s and C2- %s sit ON the ring: no tap)" % (L(23, 1), L(18, 28)),
     [[(3, 27), (2, 27)], [(5, 5), (4.6, 4.6), (4.6, 2.4), (4, 2)], [(9, 27), (9, 28)], [(14, 0), (14, 1)],
      [(4, 2), (4, 1)], [(6, 2), (6, 1)], [(8, 2), (8, 1)], [(11, 2), (11, 1)], [(19, 2), (19, 1)], [(21, 2), (21, 1)],
      [(22, 5), (23, 5)], [(22, 8), (23, 8)], [(22, 11), (23, 11)], [(22, 14), (23, 14)], [(22, 17), (23, 17)], [(22, 20), (23, 20)], [(22, 27), (23, 27)]]),
    ("GND", "26", False, "GND: ESP32 GND pins -> left one %s up to the top ring %s (lane c 8.6), right one %s across to the right ring %s (row lane 20.6)"
                         % (L(8, 20), L(8, 28), L(18, 20), L(23, 21)),
     [[esp_pin("GND", "L"), (8.6, 20.4), (8.6, 27.6), (8, 28)], [esp_pin("GND", "R"), (18.4, 20.6), (22.6, 20.6), (23, 21)]]),
    ("GND", "26", False, "GND: U1 pin 7 %s -> bottom ring %s (lane c 2.5); 1OE %s, 2OE %s -> left ring; 3OE %s -> J3's GND pin 6 %s (lane c 7.0); "
                         "4OE %s and C3- %s -> left ring %s" % (L(3, 14), L(3, 1), L(3, 20), L(3, 17), L(6, 16), L(8, 2), L(6, 19), L(4, 22), L(2, 22)),
     [[(3, 14), (2.5, 13.6), (2.5, 1.4), (3, 1)], [(3, 20), (2, 20)], [(3, 17), (2, 17)], [(6, 16), (7.0, 15.6), (7.0, 3.4), (7.6, 2.4), (8, 2)],
      [(6, 19), (6.4, 19), (6.4, 21.6), (2.4, 21.6), (2, 22)], [(4, 22), (2, 22)]]),
    ("5V_A", "22", False, "5V_A entry (rev d, no switch): J1.1 %s -> the left end of the bus-A rail %s, one short insulated 22 AWG tap" % (L(3, 25), L(4, 23)),
     [[(3, 25), (3.2, 24.2), (3.7, 23.4), (4, 23)]]),
    ("5V_A", "22", True, "5V_A bus, bare 22 AWG: column V from %s up to %s, then the top rail along row 24 to %s" % (L(21, 12), L(21, 23), L(4, 23)),
     [[(21, 12), (21, 23), (4, 23)]]),
    ("5V_A", "22", False, "5V_A taps: J6-J8, the ESP32 VIN pin %s, TP1 %s; U1 VCC pin 14 %s -> C3 %s -> rail" % (L(18, 21), L(6, 24), L(6, 20), L(6, 22)),
     [[(22, 13), (21, 13)], [(22, 16), (21, 16)], [(22, 19), (21, 19)], [esp_pin("VIN"), (18, 23)], [(6, 24), (6, 23)],
      [(6, 20), (6, 22)], [(6, 22), (6, 23)]]),
    ("5V_A", "22", False, "5V_A down the left (insulated 22 AWG): rail %s -> C1+ %s (lane c 4.5); C1+ -> J3.1 %s (lane c 3.4); rail %s -> J5.3 %s (lane c 12.4); J5.3 -> C5 %s"
                          % (L(4, 23), L(5, 7), L(3, 2), L(13, 23), L(12, 2), L(14, 2)),
     [[(4, 23), (4.5, 22.6), (4.5, 7.4), (5, 7)], [(5, 7), (3.4, 6.6), (3.4, 2.4), (3, 2)], [(13, 23), (12.4, 22.6), (12.4, 2.4), (12, 2)], [(12, 2), (14, 2)]]),
    ("5V_B", "22", True, "5V_B bus, bare 22 AWG: column V from %s up to %s; LK1 = insulated link %s-%s, leave %s EMPTY" % (L(21, 3), L(21, 10), L(21, 10), L(21, 12), L(21, 11)),
     [[(21, 3), (21, 10)]]),
    ("LK1", "22", False, "LK1 link, bus B %s to bus A %s over the empty %s (snip for two pigtails)" % (L(21, 10), L(21, 12), L(21, 11)),
     [[(21, 10), (20.6, 10.5), (20.6, 11.5), (21, 12)]]),
    ("5V_B", "22", False, "5V_B taps: J9-J11, J4.1 %s (row lane 2.6 under the bus); riser from %s (lane c 19.8) to the junction hole %s = TP2, then C2+ %s and J12.1 %s"
                          % (L(18, 2), L(21, 8), L(20, 24), L(18, 26), L(22, 25)),
     [[(22, 4), (21, 4)], [(22, 7), (21, 7)], [(22, 10), (21, 10)], [(21, 3), (21, 2.6), (18.4, 2.6), (18, 2)],
      [(21, 8), (19.8, 8.6), (19.8, 23.6), (20, 24)], [(20, 24), (18.4, 24.4), (18.4, 25.6), (18, 26)], [(20, 24), (22, 24.4), (22, 25)]]),
    ("IO18", "28", False, "IO18 CLK0 %s -> U1 pin 2 (1A) %s: row lane 13.4 under U1's bottom edge and up the left (lane c 2.8)" % (L(8, 13), L(3, 19)),
     [[esp_pin("IO18"), (7.5, 13.4), (2.8, 13.4), (2.8, 19), (3, 19)]]),
    ("IO23", "28", False, "IO23 DATA0 %s -> U1 pin 5 (2A) %s: lane c 7.6 up to row lane 12.8, lane c 2.4" % (L(8, 7), L(3, 16)),
     [[esp_pin("IO23"), (7.6, 7.2), (7.6, 12.8), (2.4, 12.8), (2.4, 16), (3, 16)]]),
    ("IO14", "28", False, "IO14 CLK1 %s -> U1 pin 9 (3A) %s, under the ESP32 (row lane 12.4), lane c 6.6" % (L(18, 17), L(6, 15)),
     [[esp_pin("IO14"), (17.5, 17), (17.5, 12.4), (6.6, 12.4), (6.6, 15), (6, 15)]]),
    ("IO13", "28", False, "IO13 DATA1 %s -> U1 pin 12 (4A) %s, under the ESP32 (row lane 12.2), lane c 6.8" % (L(18, 19), L(6, 18)),
     [[esp_pin("IO13"), (17.3, 19), (17.3, 12.2), (6.8, 12.2), (6.8, 18), (6, 18)]]),
    ("Y1", "28", False, "U1 1Y pin 3 %s -> R1 top %s (lane c 3.5, under the chip)" % (L(3, 18), L(3, 11)), [[(3, 18), (3.5, 17.6), (3.5, 11.4), (3, 11)]]),
    ("Y2", "28", False, "U1 2Y pin 6 %s -> R2 top %s (lane c 4.0)" % (L(3, 15), L(4, 11)), [[(3, 15), (4.0, 14.6), (4.0, 11.4), (4, 11)]]),
    ("Y3", "28", False, "U1 3Y pin 8 %s -> R3 top %s (lane c 5.0)" % (L(6, 14), L(5, 11)), [[(6, 14), (5.0, 13.6), (5, 11)]]),
    ("Y4", "28", False, "U1 4Y pin 11 %s -> R4 top %s (lane c 5.5, under the chip)" % (L(6, 17), L(6, 11)), [[(6, 17), (5.5, 16.6), (5.5, 11.4), (6, 11)]]),
    ("CLK0", "28", False, "R1 bottom %s -> J3.3 CLK0 %s (row lane 8.6, lane c 5.6, from above)" % (L(3, 9), L(5, 2)), [[(3, 9), (3, 8.6), (5.6, 8.6), (5.6, 2.6), (5, 2)]]),
    ("DATA0", "28", False, "R2 bottom %s -> J3.5 DATA0 %s (row lane 8.2, lane c 6.4, from above)" % (L(4, 9), L(7, 2)), [[(4, 9), (4, 8.2), (6.4, 8.2), (6.4, 2.6), (7, 2)]]),
    ("CLK1", "28", False, "R3 bottom %s -> J4.3 CLK1 %s (row lane 7.8, lane c 8.6 down past the antenna end, row lane 0.7 under the GND ring, into pin 3 from below)" % (L(5, 9), L(20, 2)),
     [[(5, 9), (5, 7.8), (8.6, 7.8), (8.6, 0.7), (20, 0.7), (20, 2)]]),
    ("DATA1", "28", False, "R4 bottom %s -> J4.5 DATA1 %s (row lane 7.4, lane c 9.4, row lane 0.2, into pin 5 from below)" % (L(6, 9), L(22, 2)),
     [[(6, 9), (6, 7.4), (9.4, 7.4), (9.4, 0.2), (22, 0.2), (22, 2)]]),
    ("HALL", "28", False, "hall: J5.1 OUT %s -> lane c 10.4 up to row lane 24.6 -> R9 bottom %s; R9 -> C4 %s; C4 -> row lane 25.4 -> lane c 16.6 -> IO27 %s"
                          % (L(10, 2), L(7, 25), L(9, 25), L(18, 16)),
     [[(10, 2), (10.4, 2.4), (10.4, 24.6), (7.4, 24.6), (7, 25)], [(7, 25), (9, 25)], [(9, 25), (9.4, 25.4), (16.6, 25.4), (16.6, 16.4), esp_pin("IO27")]]),
    ("3V3", "28", False, "3V3: ESP32 3V3 pin %s (top of the left header) -> R9 top %s (lane c 7.6)" % (L(8, 21), L(7, 27)), [[esp_pin("3V3"), (7.6, 21.4), (7.6, 26.6), (7, 27)]]),
]
LW = {"22": 1.8, "26": 1.4, "28": 1.3}
NET_COL = {"GND": GND_C, "5V_IN": V5IN_C, "5V_A": V5A_C, "5V_B": V5B_C, "LK1": V5B_C, "HALL": V33_C, "3V3": V33_C}


def net_colour(net):
    return NET_COL.get(net, SIG_C)


# ---------------------------------------------------------------- hole-to-net check (catches a wire landing on the wrong pin)
hole_net = {}


def claim(h, net, who):
    h = (int(h[0]), int(h[1]))
    if not (0 <= h[0] < NC and 0 <= h[1] < NR):
        raise SystemExit("%s: hole %s is off the board" % (who, h))
    if h in hole_net and hole_net[h] != net:
        raise SystemExit("NET CONFLICT at hole %s: %s wants %s, already %s" % (hl(h), who, net, hole_net[h]))
    hole_net[h] = net


USED = ("GND", "VIN", "3V3", "IO23", "IO18", "IO13", "IO14", "IO27")
for side, names in (("L", ESP_L), ("R", ESP_R)):
    assert len(names) == ESP_N
    for i, nm in enumerate(names):
        claim((ESP_C[side], ESP_R0 + i), nm if nm in USED else "nc:" + nm + side, "U2")
hole_net[esp_pin("VIN")] = "5V_A"
hole_net[esp_pin("IO27")] = "HALL"
for k, h in U1.items():
    claim(h, U1_NET[k], "U1 pin %d" % k)
for name, (holes, lab, col, kind, pnets) in parts.items():
    for h, n in zip(holes, pnets):
        claim(h, n, name)
for net, gauge, bare, desc, paths in nets:
    if net == "LK1":
        continue
    for path in paths:
        if bare:             # bare bus wire: every hole along it belongs to the net
            for (c0, r0), (c1, r1) in zip(path, path[1:]):
                if c0 == c1:
                    for r in range(int(min(r0, r1)), int(max(r0, r1)) + 1):
                        claim((c0, r), net, desc[:30])
                elif r0 == r1:
                    for c in range(int(min(c0, c1)), int(max(c0, c1)) + 1):
                        claim((c, r0), net, desc[:30])
                else:
                    raise SystemExit("bare wire must be axis-aligned: " + desc)
        else:
            for p in (path[0], path[-1]):
                if not is_hole(p):
                    raise SystemExit("wire end %s is not a hole: %s" % (p, desc))
                claim(p, net, desc[:40])
# card guides: no solder pad may reach into the 1.5 mm grip of either 90 mm edge below the post tops
for (c, r), n in hole_net.items():
    if c in GUIDE_COLS and r < GUIDE_ROW and not n.startswith("nc:"):
        raise SystemExit("solder at %s would sit inside the card guide's grip: %s" % (hl((c, r)), n))
pad_to_grip = min(W / 2 - GUIDE_GRIP - (abs(xy(c, r)[0]) + PAD_R) for (c, r), n in hole_net.items() if r < GUIDE_ROW and not n.startswith("nc:"))
edge_to_grip = W / 2 - GUIDE_GRIP - (abs(xy(0, 0)[0]) + PAD_R)        # the outermost columns A / Z, used or not
ends = {}
for net, gauge, bare, desc, paths in nets:
    if not bare:
        for path in paths:
            for p in (path[0], path[-1]):
                ends[(int(p[0]), int(p[1]))] = ends.get((int(p[0]), int(p[1])), 0) + 1
busy = {h: n for h, n in ends.items() if n > 2}


# ---------------------------------------------------------------- component-side footprints (board frame: x, z in mm) and the body-overlap / keep-out checks
def body_rect(name, holes, kind):
    """(x0, x1, z0, z1, height) of the part's body on the component side."""
    xs = [xy(c, r)[0] for c, r in holes]
    zs = [z_of(r) for c, r in holes]
    cx, cz = sum(xs) / len(xs), sum(zs) / len(zs)
    t = TERM254
    if kind == "t254h":
        Ln = len(holes) * t["pitch"]
        return (cx - Ln / 2, cx + Ln / 2, cz - (t["depth"] - t["pin_from_back"]), cz + t["pin_from_back"], t["height"])
    if kind == "t254v":
        Ln = len(holes) * t["pitch"]
        return (cx - (t["depth"] - t["pin_from_back"]), cx + t["pin_from_back"], cz - Ln / 2, cz + Ln / 2, t["height"])
    if kind == "t254vx":
        Ln = len(holes) * t["pitch"]
        return (cx - t["pin_from_back"], cx + (t["depth"] - t["pin_from_back"]), cz - Ln / 2, cz + Ln / 2, t["height"])
    if kind == "term":
        return (cx - TERM5["w"] / 2, cx + TERM5["w"] / 2, cz - TERM5["d"] / 2, cz + TERM5["d"] / 2, TERM5["height"])
    if kind == "elco":
        return (cx - 5.0, cx + 5.0, cz - 5.0, cz + 5.0, 16.6)
    if kind == "small":
        horiz = abs(xs[0] - xs[1]) > abs(zs[0] - zs[1])
        return ((cx - 2.25, cx + 2.25, cz - 1.25, cz + 1.25, 4.5) if horiz else (cx - 1.25, cx + 1.25, cz - 2.25, cz + 2.25, 4.5))
    if kind == "axial":
        return (xs[0] - 1.2, xs[0] + 1.2, zs[0] - 1.2, zs[0] + 1.2, 7.3)
    if kind == "tp":
        return None
    raise KeyError(kind)


rects = {}
for name, (holes, lab, col, kind, pnets) in parts.items():
    if kind == "tp":
        for h, nm in zip(holes, TP_NAMES):
            x, z = xy(*h)[0], z_of(h[1])
            rects[nm] = (x - 0.6, x + 0.6, z - 0.6, z + 0.6, 2.0)
    else:
        rects[name] = body_rect(name, holes, kind)
x1u, x4u = xy(U1[1][0], 0)[0], xy(U1[14][0], 0)[0]
zcu = (z_of(U1[1][1]) + z_of(U1[7][1])) / 2.0                 # the socket's centre between pin rows 1 and 7
rects["U1 socket"] = ((x1u + x4u) / 2 - 4.7, (x1u + x4u) / 2 + 4.7, zcu - 9.4, zcu + 9.4, 10.0)
rects["U2 DevKit"] = (ESP_X - ESP_BOARD[0] / 2, ESP_X + ESP_BOARD[0] / 2, ESP_Z0, ESP_Z1, 2.5)     # 2.5 = what may fit UNDER it (nothing does)
GAP = 0.5
names = list(rects)
for i, a in enumerate(names):
    for b in names[i + 1:]:
        A, B = rects[a], rects[b]
        gap = 0.0 if (a[0] == "R" and b[0] == "R") else GAP          # standing 1/4 W resistors at 2.54 mm pitch touch: allowed
        if A[0] < B[1] + gap and B[0] < A[1] + gap and A[2] < B[3] + gap and B[2] < A[3] + gap:
            if "U2 DevKit" in (a, b) and (A[4] if a != "U2 DevKit" else B[4]) <= 2.0:
                continue
            raise SystemExit("BODY OVERLAP (< %.1f mm) on the component side: %s %s vs %s %s" % (gap, a, A[:4], b, B[:4]))
kx, kl = USB_KEEPOUT
for a, A in rects.items():
    if a == "U2 DevKit":
        continue
    if A[0] < ESP_X + kx / 2 + 1.0 and ESP_X - kx / 2 - 1.0 < A[1] and A[2] < ESP_Z1 + kl and A[3] > ESP_Z1 - 1.0 and A[4] > 1.5:     # 1.0 mm, as the CAD check
        raise SystemExit("%s stands in the path of a USB plug above the DevKit (x %+.2f +-%.1f, z %.0f..%.0f)" % (a, ESP_X, kx / 2, ESP_Z1, ESP_Z1 + kl))
if ESP_Z1 + kl > BOARD_Z_BOT + H:
    raise SystemExit("the USB plug's path (to z %.1f) runs past the board's top edge (z %.1f)" % (ESP_Z1 + kl, BOARD_Z_BOT + H))
guide_x = W / 2 - GUIDE_GRIP
for a, A in rects.items():
    if a == "U2 DevKit":
        continue
    if (A[0] < -guide_x + 1.0 or A[1] > guide_x - 1.0) and A[2] < z_of(GUIDE_ROW):
        raise SystemExit("%s is within 1 mm of a card guide post (x +-%.1f) below row %d" % (a, guide_x, GUIDE_ROW + 1))
bottom_terms = [n for n, p in parts.items() if p[3] == "t254h"]
sbend = min(rects[n][2] for n in bottom_terms) - BOARD_Z_BOT
if sbend < SBEND_MIN:
    raise SystemExit("bottom-row terminals leave only %.2f mm (< %.1f) for their wires to S-bend into the sled slots" % (sbend, SBEND_MIN))
ant_gap = ESP_Z0 - max(rects[n][3] for n in bottom_terms)
print("hole/net check OK (%s): %d holes assigned, %d insulated wire ends; holes with >2 wire ends: %s; %d component-side bodies, no overlap, "
      "nothing under the DevKit (z %.1f..%.1f) or in the USB plug's path (to z %.1f, board top %.0f)" % (
          REV, len(hole_net), sum(ends.values()), {hl(h): n for h, n in busy.items()} or "none", len(rects), ESP_Z0, ESP_Z1, ESP_Z1 + kl, BOARD_Z_BOT + H))
print("card guides: grip the outer %.1f mm of each 90 mm edge up to z %.1f (beside printed rows 1-%d); columns reaching the grip: %s; the outermost "
      "columns A / Z leave %.2f mm from pad to grip, the nearest USED pad below row %d %.2f mm; bottom terminals S-bend room %.2f mm (>= %.0f), "
      "DevKit antenna end %.2f mm above their bodies; DevKit centre x %+.2f on the board (CAD: board centre at x %+.2f)" % (
          GUIDE_GRIP, POST_TOP, GUIDE_ROW, [L(c, 0)[0] for c in GUIDE_COLS] or "none", edge_to_grip, GUIDE_ROW + 1, pad_to_grip, sbend, SBEND_MIN, ant_gap, ESP_X, BOARD_X))


# ---------------------------------------------------------------- draw (board frame)
def run_label(holes):
    """'D3-I3' for a straight run of holes, 'F8 / F6' for two, else a comma list."""
    hs = [tuple(h) for h in holes]
    if len(hs) > 2 and (len(set(c for c, r in hs)) == 1 or len(set(r for c, r in hs)) == 1):
        return "%s-%s" % (L(*hs[0]), L(*hs[-1]))
    return " / ".join(L(*h) for h in hs)


fig, ax = plt.subplots(figsize=(11.5 * W / 60.0, 14.4 * H / 80.0))
ax.set_xlim(-W / 2 - 10, W / 2 + 10); ax.set_ylim(-8, H + 14); ax.set_aspect("equal"); ax.axis("off")
if FLIP:
    ax.invert_yaxis()          # flipped view: A1 top left, Z1 top right, A31 bottom left (the labelled face, row 1 up)
ax.add_patch(Rectangle((-W / 2, 0), W, H, fc="#f3efe6", ec="#333", lw=1.5))
for c in range(NC):
    for r in range(NR):
        x, y = xy(c, r)
        ax.add_patch(Circle((x, y), 0.45, fc="#b8a68a", ec="none"))
for c in range(NC):          # printed column letters (every column) with the c index under every fifth
    x = xy(c, 0)[0]
    for yy, va in ((-1.0, "top"), (H + 0.8, "bottom")):
        ax.text(x, yy, chr(65 + c), ha="center", va=va, fontsize=6.2, color="#000" if c % 5 == 0 else "#333", fontweight="bold" if c % 5 == 0 else "normal")
    if c % 5 == 0:
        ax.text(x, -3.4, "c%d" % c, ha="center", va="top", fontsize=4.6, color="#888")
for r in range(NR):          # printed row numbers (every row) with the r index beside every fifth
    y = xy(0, r)[1]
    for xx, ha in ((-W / 2 - 0.8, "right"), (W / 2 + 0.8, "left")):
        ax.text(xx, y, str(r + 1), ha=ha, va="center", fontsize=5.6, color="#000" if r % 5 == 0 else "#333", fontweight="bold" if r % 5 == 0 else "normal")
    if r % 5 == 0:
        ax.text(-W / 2 - 4.6, y, "r%d" % r, ha="right", va="center", fontsize=4.6, color="#888")
ax.text(0, -5.6, "printed column letter A-Z (A on the left seen from the component side); grey: grid index c, x = (c - %g) x 2.54 mm from the board's centre line" % CC,
        ha="center", fontsize=6.6, color="#555")
ax.text(-W / 2 - 8.6, H / 2, "printed row number 1-31 (row 1 at the " + ("TOP" if FLIP else "bottom") + ", 7.5 mm margin); grey: r = row - 1", rotation=90, ha="center", va="center", fontsize=6.6, color="#555")
# A1, and the card guides' grip (the outer 1.5 mm of each 90 mm edge from the bottom up to the post tops at z 56.4)
xa1, ya1 = xy(0, 0)
ax.add_patch(Circle((xa1, ya1), 1.2, fc="none", ec="#c00", lw=1.2, zorder=7))
ax.text(xa1 + 1.5, ya1 - 1.9, "A1", fontsize=7.5, color="#c00", fontweight="bold", zorder=7)
for sx in (-1, 1):
    ax.add_patch(Rectangle((sx * W / 2 - (GUIDE_GRIP if sx > 0 else 0), 0), GUIDE_GRIP, POST_TOP - BOARD_Z_BOT, fc="none", ec="#999", hatch="////", lw=0.5))
for yy in ((0.0, 1.6), (H - 1.6, H)):          # the board's centre line (between M and N) as ticks on the bottom and top edges
    ax.plot([0, 0], yy, color="#666", lw=0.8, ls="--", zorder=6)
ax.text(0, xy(0, NR - 1)[1] + 2.2, "rev i: the counted 26 x 31 grid; rows 30-31 and columns A, B, Y, Z are spare (the rev h layout, every row - 2)",
        ha="center", va="bottom", fontsize=5.4, color="#777")

for net, gauge, bare, desc, paths in nets:
    lw = 2.6 if bare else LW[gauge]
    for path in paths:
        xs = [xy(c, r)[0] for c, r in path]
        ys = [xy(c, r)[1] for c, r in path]
        ax.plot(xs, ys, color=net_colour(net), lw=lw, alpha=0.9, solid_capstyle="round", zorder=3)

# U2: the DevKit outline (its PCB floats 2.5 mm above the board on the header spacers), the two pin columns, the USB plug keep-out
ew, el = ESP_BOARD
ax.add_patch(FancyBboxPatch((ESP_X - ew / 2, ESP_Z0 - BOARD_Z_BOT), ew, el, boxstyle="round,pad=0.2", fc="none", ec="#2b2b2b", ls="--", lw=0.9, zorder=4))
ax.add_patch(Rectangle((ESP_X - 4.0, ESP_Z1 - BOARD_Z_BOT - 5.6), 8.0, 5.6, fc="#999", ec="#2b2b2b", lw=0.6, zorder=4))
ax.add_patch(Rectangle((ESP_X - 9.0, ESP_Z0 - BOARD_Z_BOT - 1.0), 18.0, 25.5, fc="none", ec="#2b2b2b", lw=0.5, ls=":", zorder=4))
ax.add_patch(Rectangle((ESP_X - kx / 2, ESP_Z1 - BOARD_Z_BOT), kx, min(kl, H - (ESP_Z1 - BOARD_Z_BOT)), fc="none", ec="#c00", lw=0.6, ls=":", zorder=4))
ax.text(ESP_X, ESP_Z1 - BOARD_Z_BOT + 4.2, "USB plug\nkeep-out", ha="center", va="center", fontsize=5.0, color="#c00", zorder=6)
for side, col in (("L", ESP_L), ("R", ESP_R)):
    c = ESP_C[side]
    x0, y0 = xy(c, ESP_R0)
    ax.add_patch(Rectangle((x0 - 1.27, y0 - 1.27), 2.54, ESP_N * P, fc="#2b2b2b", ec="#000", lw=0.8, zorder=4))
    for i, nm in enumerate(col):
        x, y = xy(c, ESP_R0 + i)
        ax.add_patch(Circle((x, y), 0.5, fc="#ddd", ec="none", zorder=5))
        hot = nm in ("IO23", "IO18", "IO13", "IO14", "IO27", "VIN", "3V3", "GND")
        dx_ = 1.9 if side == "L" else -1.9
        ax.text(x + dx_, y, "%s %s" % (nm, L(c, ESP_R0 + i)) if hot else nm, fontsize=5.0, ha="left" if side == "L" else "right", va="center", zorder=6,
                color="#c00" if hot else "#444", fontweight="bold" if hot else "normal")
    ax.text(x0, xy(c, ESP_R0 + ESP_N - 1)[1] + 2.0, "column %s" % chr(65 + c), ha="center", va="bottom", fontsize=5.6, color="#2b2b2b", fontweight="bold", zorder=7,
            bbox=dict(fc="white", ec="none", pad=0.3, alpha=0.85))
ax.text(ESP_X, ESP_Z1 - BOARD_Z_BOT - 8.2, "micro-USB (" + ("down" if FLIP else "up") + ")", ha="center", fontsize=6.0, color="#2b2b2b", zorder=6)
ax.text(ESP_X + 4.5, ESP_Z0 - BOARD_Z_BOT + 28.0, ("U2  ESP32 DOIT\nDevKit V1, 30-pin\ncolumns I and S,\nrows %d-%d\nSOLDERED DIRECT\n(no headers; PCB\n2.5 mm above the\nboard; antenna\nend %s)"
        % (ESP_R0 + 1, ESP_R0 + ESP_N, "UP" if FLIP else "DOWN")), ha="center", va="center", fontsize=6.0, color="#2b2b2b", zorder=6)
ax.text(ESP_X, ESP_Z0 - BOARD_Z_BOT + 3.0, "antenna end", ha="center", fontsize=6.0, color="#2b2b2b", zorder=6)

# U1, drawn from its own pins (rev i: no literal columns), notch at the pin-1 end
xs1 = [xy(*U1[k])[0] for k in U1]
ys1 = [xy(*U1[k])[1] for k in U1]
ux0, ux1, uy0, uy1 = min(xs1), max(xs1), min(ys1), max(ys1)
ax.add_patch(Rectangle((ux0 - 1.0, uy0 - 1.27), (ux1 - ux0) + 2.0, (uy1 - uy0) + 2.54, fc="#3a3a3a", ec="#000", lw=0.8, zorder=4))
for k, (c, r) in U1.items():
    x, y = xy(c, r)
    left = c == U1[1][0]
    ax.add_patch(Circle((x, y), 0.5, fc="#ddd", ec="none", zorder=5))
    ax.text(x + (-1.3 if left else 1.3), y, "%d %s %s" % (k, U1_NAME[k], L(c, r)), fontsize=4.6, ha="right" if left else "left", va="center", zorder=7, color="#333",
            bbox=dict(fc="white", ec="none", pad=0.15, alpha=0.8))
ax.text((ux0 + ux1) / 2, (uy0 + uy1) / 2, "U1\n74AHCT\n125\nnotch " + ("v" if FLIP else "^") + "\npin 1\n%s" % L(*U1[1]), ha="center", va="center", fontsize=5.4, color="#fff", zorder=6)
px1, py1 = xy(*U1[1])
ax.add_patch(Circle((px1 - 0.2, py1 + 0.4), 0.45, fc="#fff", ec="none", zorder=6))      # pin-1 dot, top-left

for name, (holes, lab, col, kind, pnets) in parts.items():
    pts = [xy(c, r) for c, r in holes]
    where = run_label(holes)
    if kind in ("t254h", "t254v", "t254vx"):
        R = rects[name]
        ax.add_patch(Rectangle((R[0], R[2] - BOARD_Z_BOT), R[1] - R[0], R[3] - R[2], fc=col, ec="#135", lw=0.8, zorder=4, alpha=0.9))
        for i, (x, y) in enumerate(pts):
            ax.add_patch(Circle((x, y), 0.5, fc="#ddd", ec="none", zorder=5))
            # screw head over the clamp, between the pin and the entry face
            sx_, sy_ = (x, y - 1.6) if kind == "t254h" else ((x + 1.6, y) if kind == "t254vx" else (x - 1.6, y))
            ax.add_patch(Circle((sx_, sy_), 0.8, fc="none", ec="#135", lw=0.5, zorder=5))
            ax.plot([sx_ - 0.5, sx_ + 0.5], [sy_, sy_], color="#135", lw=0.5, zorder=5)
            if kind == "t254h":
                ax.text(x, R[2] - BOARD_Z_BOT - 1.2, str(i + 1), fontsize=4.8, ha="center", va="center", zorder=6)
            else:
                t = "5V" if i == 0 else "G"
                if kind == "t254v":
                    ax.text(R[0] - 0.6, y, t, fontsize=4.6, ha="right", va="center", zorder=6)
                else:
                    ax.text(R[1] + 0.6, y, t, fontsize=4.6, ha="left", va="center", zorder=6)
        if kind == "t254h":
            ax.text((R[0] + R[1]) / 2, R[3] - BOARD_Z_BOT + 0.7, "%s, %s" % (lab, where), ha="center", va="bottom", fontsize=5.4, zorder=6)
            ax.annotate("", xy=((R[0] + R[1]) / 2 + 1.0, R[2] - BOARD_Z_BOT - 2.4), xytext=((R[0] + R[1]) / 2 + 1.0, R[2] - BOARD_Z_BOT - 0.2),
                        arrowprops=dict(arrowstyle="<-", color="#135", lw=0.7), zorder=6)
        elif kind == "t254v":
            ax.text(R[1] - 3.0, R[3] - BOARD_Z_BOT + 0.5, "%s %s" % (lab, where), ha="center", va="bottom", fontsize=5.0, zorder=6)
            ax.annotate("", xy=(R[0] - 2.6, (R[2] + R[3]) / 2 - BOARD_Z_BOT + 0.9), xytext=(R[0] - 0.2, (R[2] + R[3]) / 2 - BOARD_Z_BOT + 0.9),
                        arrowprops=dict(arrowstyle="<-", color="#135", lw=0.7), zorder=6)
        else:
            ax.text(R[0] - 0.4, R[3] - BOARD_Z_BOT + 0.5, "%s %s" % (lab, where), ha="left", va="bottom", fontsize=5.0, zorder=6)
            ax.annotate("", xy=(R[1] + 2.6, (R[2] + R[3]) / 2 - BOARD_Z_BOT + 0.9), xytext=(R[1] + 0.2, (R[2] + R[3]) / 2 - BOARD_Z_BOT + 0.9),
                        arrowprops=dict(arrowstyle="<-", color="#135", lw=0.7), zorder=6)
    elif kind == "term":
        R = rects[name]
        (x0, y0), (xe, ye) = pts
        ax.add_patch(Rectangle((R[0], R[2] - BOARD_Z_BOT), R[1] - R[0], R[3] - R[2], fc=col, ec="#135", lw=0.8, zorder=4, alpha=0.9))
        if x0 < 0:
            ax.text(x0 + 4.2, (y0 + ye) / 2, "%s\n%s" % (lab, where), ha="left", va="center", fontsize=6.0, zorder=6)
        else:
            ax.text(W / 2 - 1.0, max(y0, ye) + 5.1, "%s, %s" % (lab.replace("\n", " "), where), ha="right", va="center", fontsize=5.2, zorder=7,
                    bbox=dict(fc="white", ec="none", pad=0.3, alpha=0.85))
        for i, (x, y) in enumerate(pts):
            ax.add_patch(Circle((x, y), 0.5, fc="#ddd", ec="none", zorder=5))
            ax.text(x, y + (1.4 if i == 0 else -1.4), "5V" if i == 0 else "GND", fontsize=4.6, ha="center", va="center", zorder=6)
    elif kind == "elco":
        (xp, yp), (xn, yn) = pts            # first hole is +
        ax.add_patch(Circle(((xp + xn) / 2, (yp + yn) / 2), 5.0, fc=col, ec="#135", lw=0.8, zorder=4, alpha=0.85))
        ax.text((xp + xn) / 2, (yp + yn) / 2, "%s\n+ %s" % (lab, L(*holes[0])), ha="center", va="center", fontsize=5.6, zorder=6)
        for x, y in pts:
            ax.add_patch(Circle((x, y), 0.5, fc="#ddd", ec="none", zorder=5))
        ax.text(xp + 1.5, yp, "+", fontsize=8, ha="center", va="center", zorder=6, fontweight="bold")
    elif kind == "tp":
        for (x, y), t, h in zip(pts, ("TP1 5V_A", "TP3 GND", "TP2 5V_B\n(junction)"), holes):
            ax.add_patch(Circle((x, y), 0.9, fc=col, ec="#135", lw=0.8, zorder=5))
            if t.startswith("TP2"):
                ax.text(x - 1.4, y, "TP2 5V_B %s\n(junction)" % L(*h), ha="right", va="center", fontsize=5.0, zorder=7,
                        bbox=dict(fc="white", ec="none", pad=0.2, alpha=0.8))
            else:
                ax.text(x, y + 1.2, "%s %s" % (t, L(*h)), ha="center", va="bottom", fontsize=5.0, zorder=6)
    else:
        (x0, y0), (xe, ye) = pts
        ax.plot([x0, xe], [y0, ye], color="#135", lw=0.8, zorder=4)
        if x0 == xe:
            ax.add_patch(Rectangle((x0 - 0.9, min(y0, ye) + 0.9), 1.8, abs(ye - y0) - 1.8, fc=col, ec="#135", lw=0.8, zorder=4, alpha=0.95))
            if name in ("R1", "R2", "R3", "R4"):
                ax.text(x0, (y0 + ye) / 2, name[1], fontsize=4.6, ha="center", va="center", zorder=6, fontweight="bold")
                if name == "R1":
                    r4 = parts["R4"][0]
                    ax.text((x0 + xy(*r4[0])[0]) / 2, max(y0, ye) + 1.1, "R1-R4 68: bodies on %s-%s,\nfolded leads into %s-%s" % (
                        L(*holes[0]), L(*r4[0]), L(*holes[1]), L(*r4[1])), fontsize=4.8, ha="center", va="bottom", zorder=7,
                        bbox=dict(fc="white", ec="none", pad=0.2, alpha=0.8))
            elif name == "C4":
                ax.text(x0 + 1.6, (y0 + ye) / 2, "%s\n%s" % (lab, where), fontsize=4.8, ha="left", va="center", zorder=7,
                        bbox=dict(fc="white", ec="none", pad=0.2, alpha=0.8))
            else:
                ax.text(x0, max(y0, ye) + 1.1, "%s\n%s" % (lab, where), fontsize=4.8, ha="center", va="bottom", zorder=7,
                        bbox=dict(fc="white", ec="none", pad=0.2, alpha=0.8))
        else:
            ax.add_patch(Rectangle((min(x0, xe) - 0.9, y0 - 0.9), abs(xe - x0) + 1.8, 1.8, fc=col, ec="#135", lw=0.8, zorder=4, alpha=0.95))
            ax.text((x0 + xe) / 2, y0 + 1.4, "%s %s" % (lab, where), fontsize=4.8, ha="center", va="bottom", zorder=6)
        for x, y in pts:
            ax.add_patch(Circle((x, y), 0.5, fc="#ddd", ec="none", zorder=5))
# R5-R8 note (solder-side, across the IC pins), in the 7.5 mm bottom margin
ax.text(0, 3.4, "R5-R8 10 k: SOLDER side, each across U1 pins A-OE (1-2 %s-%s, 4-5 %s-%s, 9-10 %s-%s, 12-13 %s-%s)" % (
    L(*U1[1]), L(*U1[2]), L(*U1[4]), L(*U1[5]), L(*U1[9]), L(*U1[10]), L(*U1[12]), L(*U1[13])), fontsize=4.9, ha="center", va="center", color="#333", zorder=7,
        bbox=dict(fc="white", ec="#999", lw=0.5, pad=1.2))
lk = next(p for n, g_, b_, d_, ps in nets if n == "LK1" for p in ps)
lk_gap = (int(lk[0][0]), int((lk[0][1] + lk[-1][1]) / 2))          # the empty hole LK1 jumps
lx, ly = xy(*lk_gap)
ax.text(lx - 1.4, ly, "LK1\n%s empty" % L(*lk_gap), fontsize=5.0, ha="right", va="center", zorder=7)
ly0 = H + 3.6
for i, (t, col) in enumerate((("5V_A bus / taps", V5A_C), ("5V_B bus / taps", V5B_C), ("GND ring", GND_C), ("clock / data", SIG_C), ("hall / 3V3", V33_C))):
    ax.plot([-W / 2 + i * 11.0, -W / 2 + i * 11.0 + 2.6], [ly0, ly0], color=col, lw=2.2)
    ax.text(-W / 2 + i * 11.0 + 3.1, ly0, t, fontsize=5.9, va="center")
ax.text(0, H + 5.6, ("Carrier board, FLIPPED view (board turned over top-to-bottom, the printed labels facing you): A1 top LEFT, Z1 top RIGHT, A31 bottom LEFT. "
         "Parts on the far side are drawn through the board." if FLIP else
         "Carrier board, COMPONENT-SIDE view: hole A1 at the bottom left, component side facing you; the row-1 end goes down into the sled. "
         "Solder-side wires drawn through the board (no mirror)."), ha="center", fontsize=6.9)
ax.text(0, H + 7.8, "Thick = bare tinned 22 AWG bus; thin = insulated. Screw terminals (2.54 mm, KF128-2.54): the small arrow is the wire entry (J3 / J5 / J4 from " + ("above" if FLIP else "below") + ", "
        "feeds from the ESP32 side); screws face " + ("away from you (they are on the parts side)" if FLIP else "you") + ".", ha="center", fontsize=6.4, color="#135")
ax.text(0, H + 9.9, "Rev i: Brian's 70 x 90 Rindion board as counted, 26 x 31 holes (A-Z across, 1-31 up), margins 3.25 / 3.25 across, 7.5 below row 1, 5.5 above row 31; "
        "the rev h layout with every row - 2.", ha="center", fontsize=6.4, color="#135")
ax.text(0, H + 12.0, "Hatched: the card guides grip the outer 1.5 mm of each long edge up to z 56 (beside rows 1-%d): no hole is in them. Dashed ticks: the board's centre "
        "line (between M and N); the DevKit is centred on column N, 1.27 mm right of it." % GUIDE_ROW, ha="center", fontsize=6.4, color="#555")
ax.text(W / 2 + 9.5, -7.6, "fig. elec_carrier_layout, " + REV, fontsize=6, color="#888", ha="right")
for ext in ("svg", "png"):
    fig.savefig(os.path.join(OUT, "elec_carrier_layout" + ("_flipped." if FLIP else ".") + ext), dpi=170 if ext == "png" else None, bbox_inches="tight", facecolor="white")
if FLIP:
    sys.exit(print("wrote docs/img/elec_carrier_layout_flipped.svg/.png"))

# ---------------------------------------------------------------- build list (text) and the tables as JSON for the CAD
with open(os.path.join(OUT, "elec_carrier_netlist.txt"), "w", encoding="utf-8") as f:
    f.write("Carrier board build list (%s): every hole as its PRINTED LABEL (column letter + row number) and its grid coordinates (c, r),\n"
            "c = 0..25 = A..Z across, r = 0..30 = row number - 1; see elec_carrier_layout.png.\n"
            "Board: UNCUT %.0f x %.0f mm Rindion double-sided perfboard (calipered), %d x %d holes (counted, measurements #31), margins %.2f / %.2f across,\n"
            "%.1f mm from the row-1 edge to row 1 and %.1f mm from the row-31 edge to row 31.\n"
            "ORIENTATION: hole A1 at the BOTTOM LEFT with the COMPONENT SIDE facing you; the row-1 end goes DOWN into the sled; USB end of the ESP32 up.\n"
            "(From the solder side A1 is at the bottom RIGHT and the letters run Z..A from left to right.)\n"
            "Rev i = the rev h layout hole for hole with every ROW - 2 (columns unchanged): columns C..X and rows 1..29 are used; A, B, Y, Z and rows 30-31 are spare.\n"
            "Component side faces -y (away from the bank); all wires on the solder side; hole-to-net check passed in elec_carrier.py.\n"
            "RULE: the sled's card guides grip the outer %.1f mm of each 90 mm edge from the bottom up to z %.1f (beside rows 1-%d); no hole is in that strip\n"
            "      (columns A / Z are %.2f mm from the edges); keep solder and parts off the edges anyway.\n"
            "RULE: nothing taller than 1.5 mm under the ESP32 board (columns I..S region, %.1f mm either side of column N, z %.0f..%.0f) or in the USB plug's path\n"
            "      above it (%.1f mm either side of column N, z %.0f..%.0f).\n\nPARTS\n"
            % (REV, W, H, NC, NR, MARGIN_X, MARGIN_X, MARGIN_ROW1, MARGIN_ROW31, GUIDE_GRIP, POST_TOP, GUIDE_ROW, MARGIN_X,
               ESP_BOARD[0] / 2, ESP_Z0, ESP_Z1, kx / 2, ESP_Z1, ESP_Z1 + kl))
    f.write("  U2 ESP32 DOIT DevKit V1 (30-pin), SOLDERED DIRECT, USB end up: left column %s (c=%d) rows %d..%d (bottom %s ... top %s); right column %s (c=%d) rows %d..%d "
            "(bottom %s ... top %s)\n" % (chr(65 + ESP_C["L"]), ESP_C["L"], ESP_R0 + 1, ESP_R0 + ESP_N, ESP_L[0], ESP_L[-1],
                                         chr(65 + ESP_C["R"]), ESP_C["R"], ESP_R0 + 1, ESP_R0 + ESP_N, ESP_R[0], ESP_R[-1]))
    for side, names_ in (("L", ESP_L), ("R", ESP_R)):
        f.write("       %s: %s\n" % (side, ", ".join("%s %s" % (hl((ESP_C[side], ESP_R0 + i)), nm) for i, nm in enumerate(names_))))
    f.write("  U1 74AHCT125, notch UP, pin 1 top-LEFT at %s: pins 1-7 down column %s to %s; pins 8-14 up column %s from %s to %s\n"
            % (hl(U1[1]), chr(65 + U1[1][0]), hl(U1[7]), chr(65 + U1[8][0]), hl(U1[8]), hl(U1[14])))
    for k in range(1, 15):
        f.write("       pin %2d %-4s %-10s net %s\n" % (k, U1_NAME[k], hl(U1[k]), U1_NET[k]))
    f.write("  R5-R8 10k: solder side, across pins 1-2 (%s-%s), 4-5 (%s-%s), 9-10 (%s-%s), 12-13 (%s-%s)\n"
            % (L(*U1[1]), L(*U1[2]), L(*U1[4]), L(*U1[5]), L(*U1[9]), L(*U1[10]), L(*U1[12]), L(*U1[13])))
    for name, (holes, lab, col, kind, pnets) in parts.items():
        nm_ = name if kind != "tp" else "TP"
        f.write("  %-4s %-38s %-6s holes %s\n" % (nm_, lab.replace("\n", " ") if kind != "tp" else "test points " + ", ".join(TP_NAMES), kind,
                                                 ", ".join("%s %s" % (hl(h), n) for h, n in zip(holes, pnets))))
    f.write("\nWIRES (solder side; ends are holes, fractional (c,r) points are the lane the insulated wire follows between them)\n")
    for net, gauge, bare, desc, paths in nets:
        f.write("  [%s] %s AWG %s%s\n" % (net, gauge, desc, "  [BARE WIRE]" if bare else ""))
        for path in paths:
            f.write("      %s\n" % " -> ".join(pl(p) for p in path))
    f.write("\nHoles with more than two wire ends (solder them in one go): %s\n" % (", ".join("%s x%d" % (hl(h), n) for h, n in sorted(busy.items())) or "none"))


def labs(holes):
    return [label(*h) for h in holes]


with open(os.path.join(OUT, "elec_carrier_netlist.json"), "w", encoding="utf-8") as f:
    json.dump({"rev": REV,
               "grid": {"pitch": P, "NC": NC, "NR": NR, "guide_row": GUIDE_ROW, "guide_cols": GUIDE_COLS, "c_centre": CC, "c_axis": C_AXIS, "board_x": round(BOARD_X, 4),
                        "z0": Z0, "board": [W, H], "board_z_bot": BOARD_Z_BOT, "margins": {"across": MARGIN_X, "row1_edge": MARGIN_ROW1, "row31_edge": MARGIN_ROW31},
                        "post_top": POST_TOP, "guide_grip": GUIDE_GRIP, "pad_r": PAD_R, "row_off_from_rev_h": ROW_OFF_REV_H, "col_off_from_rev_h": COL_OFF_REV_H,
                        "label_rule": "label = chr(65 + c) + str(r + 1): column letters A-Z across the 70 mm side, row numbers 1-31 along the 90 mm side",
                        "orientation": "hole A1 at the bottom left with the component side facing you; the row-1 end goes down into the sled",
                        "frames": "x_board = (c - c_centre) * pitch from the board's centre line; x_cad = (c - c_axis) * pitch (the DevKit's centre column on the "
                                  "rotor axis), the board outline centred at x_cad = board_x; z = z0 + pitch * r"},
               "esp": {"L": ESP_L, "R": ESP_R, "C": ESP_C, "R0": ESP_R0, "N": ESP_N, "board": ESP_BOARD, "ant_overhang": ESP_ANT_OVERHANG, "lift": ESP_LIFT,
                       "z0": ESP_Z0, "z1": ESP_Z1, "usb_keepout": USB_KEEPOUT, "x_board": ESP_X,
                       "L_labels": [label(ESP_C["L"], ESP_R0 + i) for i in range(ESP_N)], "R_labels": [label(ESP_C["R"], ESP_R0 + i) for i in range(ESP_N)]},
               "term254": TERM254, "term5": TERM5,
               "U1": {str(k): list(v) for k, v in U1.items()}, "U1_NAME": {str(k): v for k, v in U1_NAME.items()}, "U1_NET": {str(k): v for k, v in U1_NET.items()},
               "U1_LABEL": {str(k): label(*v) for k, v in U1.items()},
               "parts": {name: {"holes": [list(h) for h in holes], "labels": labs(holes), "kind": kind, "nets": pnets, "label": lab.replace("\n", " ")}
                         for name, (holes, lab, col, kind, pnets) in parts.items()},
               "tp_names": list(TP_NAMES),
               "nets": [{"net": net, "gauge": gauge, "bare": bare, "desc": desc, "paths": [[list(p) for p in path] for path in paths],
                         "end_labels": [[label(*path[0]), label(*path[-1])] for path in paths]}
                        for net, gauge, bare, desc, paths in nets],
               "busy_holes": [list(h) for h in sorted(busy)]}, f, indent=1)
print("wrote elec_carrier_layout.svg/.png + elec_carrier_netlist.txt + elec_carrier_netlist.json")
