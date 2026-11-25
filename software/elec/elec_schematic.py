"""Schematic sheets for the electrical report (schemdraw 0.23, matplotlib backend) -> docs/img/elec_sch_*.svg/.png.
Run: py software/elec/elec_schematic.py
Sheet A: rotor power entry, ESP32, hall.   Sheet B: level shifter, chain connectors, the serpentine strip chain.   Sheet C: base.
schemdraw notes: every Ic/Header gets an explicit .right() (elements otherwise inherit the drawing's current direction, so a
Ground drawn .down() just before would rotate the next IC); Ic pins listed first end up at the BOTTOM of their side.
"""
import os
import schemdraw
import schemdraw.elements as elm

schemdraw.use("matplotlib")
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "img")
os.makedirs(OUT, exist_ok=True)
PF = 7.0      # pin label font


def save(d, name):
    for ext in ("svg", "png"):
        d.save(os.path.join(OUT, name + "." + ext), dpi=170)
    print("wrote", name)


def pin(name, num, side, anchor):
    return elm.IcPin(name=name, pin=str(num), side=side, anchorname=anchor, lblsize=PF)


def header(rows, left=None, right=None):
    return elm.Header(rows=rows, cols=1, pinsleft=left or [], pinsright=right or [], shownumber=True, pinfill="#ddd",
                      pinfontsizeleft=PF, pinfontsizeright=PF, pinspacing=0.6).right()


def note(d, xy, text, fs=7.5, halign="left"):
    d += elm.Label().at(xy).label(text, fontsize=fs, halign=halign)


# ====================================================================== Sheet A: power entry, ESP32, hall
d = schemdraw.Drawing(unit=2.2, fontsize=9)
note(d, (0, 12.8), "Sheet A  -  ROTOR: power entry, ESP32, hall sensor   (POV LED Column v2, 2026-11-03 rev d: no switch, the pigtail plug is the on/off)", 12)
Y = 8.6
bt = d.add(elm.Ic(pins=[pin("GND", "", "right", "g"), pin("5 V", "", "right", "p5")], size=(2.6, 2.2), pinspacing=1.0, leadlen=0.5).right()
           .at((1.3, Y - 0.5)).anchor("center").label("BT1\nINIU BI-B61\n10 Ah bank\nUSB-A port\n5 V / 2.4 A", loc="center", fontsize=7.5))
d += elm.Line().at(bt.p5).right(0.7).label("pigtail\n22 AWG", loc="top", fontsize=7)
d += elm.Fuse().right().label("F1  3 A fast-blow, inline\nholder on the pigtail (optional)", loc="top", fontsize=7)
d += elm.Line().right(0.5)
j1 = d.add(header(2, right=["5 V", "GND"]).anchor("pin1").at(d.here).label("J1 screw\nterminal", loc="bottom", fontsize=7.5))
d += elm.Wire("-|").at(bt.g).to((j1.pin2.x - 0.35, j1.pin2.y))
d += elm.Line().to(j1.pin2)
d += elm.Line().at(j1.pin2).down(1.0)
d += elm.Ground()
# rev d (2026-11-03): no SW1 / J2 / switch loop. J1 pin 1 lands straight on bus A; plugging the pigtail into the bank is the on/off.
d += elm.Line().at(j1.pin1).right(4.2)
note(d, (0, 11.4), "rev d: NO SWITCH. ON = plug the pigtail into the bank (cap off, plug in, cap on); OFF / charge = unplug.\nJ1 pin 1 lands straight on bus A (one short 22 AWG tap); SW1, J2 and the switch loop are deleted.", 7.5)
nv = d.add(elm.Dot())
d += elm.Line().right(1.6)
na = d.add(elm.Dot().label("5V_A", loc="top", fontsize=8.5, ofst=0.3))
d.push()
d += elm.Capacitor(polar=True).down(2.0).label("C1\n1000 uF\n10 V", loc="bottom", fontsize=7.5)
d += elm.Ground()
d.pop()
d += elm.Line().right(2.0)
d += elm.Dot()
d += elm.Line().right(1.6).linestyle("--").label("LK1 wire link\n(cut for two pigtails)", loc="top", fontsize=7.5)
nb = d.add(elm.Dot().label("5V_B", loc="top", fontsize=8.5, ofst=0.3))
d.push()
d += elm.Capacitor(polar=True).down(2.0).label("C2\n1000 uF\n10 V", loc="bottom", fontsize=7.5)
d += elm.Ground()
d.pop()
d += elm.Line().right(1.8)
j12 = d.add(header(2, left=["5 V", "GND"]).anchor("pin1").at(d.here).label("J12 optional\n2nd pigtail in\n(bus B only)", loc="bottom", fontsize=7.5))
d += elm.Line().at(j12.pin2).down(0.8)
d += elm.Ground()
note(d, (13.6, 11.2), "bus A (5V_A) feeds the ESP32, U1, J3 and the J6-J8 strip feeds; bus B (5V_B) feeds J4 and J9-J11.\n"
                      "TP1 5V_A · TP2 5V_B · TP3 GND: bare-wire loops on the carrier next to C1 / C2 / the GND bus.", 7.5)

# ESP32: pins listed bottom -> top
ex, ey = 15.0, 2.0
esp = d.add(elm.Ic(pins=[pin("IO0 (BOOT button only)", "", "left", "io0"), pin("EN", "R1", "left", "en"), pin("3V3", "L15", "left", "v33"),
                         pin("GND", "L14, R14", "left", "gnd"), pin("VIN (5 V)", "R15", "left", "vin"),
                         pin("IO2 (LED), IO5 open", "L12, L8", "right", "io2"), pin("IO15 open", "L13", "right", "io15"), pin("IO12 open", "R12", "right", "io12"),
                         pin("IO14 CLK1", "R11", "right", "io14"), pin("IO13 DATA1", "R13", "right", "io13"),
                         pin("IO18 CLK0", "L7", "right", "io18"), pin("IO23 DATA0", "L1", "right", "io23"), pin("IO27 HALL", "R10", "right", "io27")],
                   size=(5.2, 5.6), pinspacing=0.62, leadlen=0.7, edgepadH=0.3).right().at((ex, ey)).anchor("center")
            .label("U2  ESP32-WROOM-32\nDOIT DevKit V1 (30-pin)\nsoldered to the carrier\npin = row L/R, # from the\nantenna end; USB points up", loc="center", fontsize=7.5))
d += elm.Line().at(esp.vin).left(0.5)
d += elm.Wire("|-").to((nv.center.x, nv.center.y))
note(d, (nv.center.x - 3.3, 6.2), "5V_A goes straight to the\nESP32's VIN pin: no series\ndiode (the on-board LDO\nneeds every 0.1 V)", 7)
d += elm.Line().at(esp.gnd).left(0.6)
d += elm.Ground()
d += elm.Line().at(esp.v33).left(0.7)
d += elm.Dot(open=True).label("3V3 net -> R9", loc="left", fontsize=7.5)
d += elm.Line().at(esp.en).left(0.4)
d += elm.Dot(open=True).label("EN: on-board 10 k pull-up + button", loc="left", fontsize=7)
d += elm.Line().at(esp.io0).left(0.4)
d += elm.Dot(open=True).label("IO0: BOOT button only", loc="left", fontsize=7)
for a, t in (("io23", "DATA0 > U1 pin 5 (sheet B)"), ("io18", "CLK0 > U1 pin 2"), ("io13", "DATA1 > U1 pin 12"), ("io14", "CLK1 > U1 pin 9")):
    d += elm.Line().at(getattr(esp, a)).right(0.6)
    d += elm.Dot(open=True).label(t, loc="right", fontsize=7.5)
note(d, (esp.io12.x + 0.3, esp.io12.y - 0.9), "strapping / JTAG pins: nothing connected\n(12 high at boot = no boot; 13/14/15 wiggle at reset)", 7)
note(d, (ex - 4.8, ey - 4.0), "Inside the DevKit: micro-USB VBUS -> D1 (Schottky?) -> VIN pin -> AMS1117 -> 3V3.  Verify D1 with a diode test BEFORE soldering the board in (report 2.7).\n"
                              "Espressif's rule: never power from USB and the VIN pin at the same time.  Practice here: pigtail UNPLUGGED whenever a USB cable is plugged in.\n"
                              "USB then feeds the whole 5V_A/5V_B bus through D1 (ESP32 + dark strips ~0.3-0.5 A): use a USB 3 port or a powered hub, keep the LEDs blank.", 7)

# hall network, up and to the right of the ESP32's signal labels
hn_xy = (esp.io27.x + 5.6, esp.io27.y + 1.6)
d += elm.Wire("-|").at(esp.io27).to(hn_xy)
hn = d.add(elm.Dot().at(hn_xy))
d.push()
d += elm.Resistor().at(hn_xy).up(1.8).label("R9 10 k", loc="left", fontsize=7.5)
d += elm.Vdd().label("3V3", fontsize=7.5)
d.pop()
d += elm.Capacitor().at(hn_xy).down(1.5).label("C4 1 nF", loc="left", fontsize=7.5)
d += elm.Ground()
d += elm.Line().at(hn_xy).right(1.4)
j5 = d.add(header(3, right=["OUT", "GND", "5 V"]).anchor("pin1").at(d.here).label("J5 screw terminal 3P\nhall lead: 3 x 28 AWG,\n0.155 m, twisted", loc="bottom", fontsize=7.5))
d += elm.Line().at(j5.pin2).left(0.5)
d += elm.Ground()
d += elm.Line().at(j5.pin3).left(0.5)
d += elm.Vdd().label("5V_A", fontsize=7.5)
u4 = d.add(elm.Ic(pins=[pin("VCC", "1", "left", "vcc"), pin("GND", "2", "left", "gnd"), pin("OUT", "3", "left", "out")], size=(2.2, 2.0), pinspacing=0.6, leadlen=0.6).right()
            .anchor("out").at((j5.pin1.x + 4.8, j5.pin1.y)).label("U4  A3144\nhall switch\nbottom cap,\nr 42, 90 deg", loc="center", fontsize=7.5))
for a, b in ((j5.pin1, u4.out), (j5.pin2, u4.gnd), (j5.pin3, u4.vcc)):
    d += elm.Line().at((j5.pin1.x + 2.3, a.y)).to(b)
d += elm.Capacitor().at((u4.vcc.x - 0.5, u4.vcc.y)).down(1.0).label("C5 100 nF\nat the sensor", loc="right", fontsize=7)
note(d, (hn_xy[0] - 1.0, hn_xy[1] - 3.4), "A3144: open collector, sinks 25 mA; the 10 k pull-up to 3.3 V means GPIO 27 never sees 5 V.\n"
                                        "Firmware triggers on the FALLING edge (magnet arrives). RC = 10 us; the pulse is ~10 ms at 225 rpm.", 7)
save(d, "elec_sch_a_power_esp32")

# ====================================================================== Sheet B: level shifter and chains
d = schemdraw.Drawing(unit=2.2, fontsize=9)
note(d, (0, 14.4), "Sheet B  -  ROTOR: 74AHCT125 level shifter, chain-start connectors, the serpentine chain", 12)
u1 = d.add(elm.Ic(pins=[pin("1A", "2", "left", "a1"), pin("1OE", "1", "left", "oe1"), pin("2A", "5", "left", "a2"), pin("2OE", "4", "left", "oe2"),
                        pin("3A", "9", "left", "a3"), pin("3OE", "10", "left", "oe3"), pin("4A", "12", "left", "a4"), pin("4OE", "13", "left", "oe4"),
                        pin("1Y", "3", "right", "y1"), pin("2Y", "6", "right", "y2"), pin("3Y", "8", "right", "y3"), pin("4Y", "11", "right", "y4"),
                        pin("VCC", "14", "top", "vcc"), pin("GND", "7", "bottom", "gnd")],
                  size=(3.4, 9.6), pinspacing=1.1, leadlen=0.8).right().at((5.0, 7.4)).anchor("center")
            .label("U1  SN74AHCT125N\nDIP-14, VCC = 5V_A\nTTL inputs: 3.3 V\nreads as HIGH", loc="center", fontsize=7.5))
d += elm.Line().at(u1.vcc).up(0.6)
d += elm.Vdd().label("5V_A", fontsize=7.5)
d += elm.Capacitor().at((u1.vcc.x + 1.2, u1.vcc.y + 0.5)).down(1.0).label("C3 100 nF\n(pins 14-7,\nas close as\npossible)", loc="right", fontsize=7)
d += elm.Line().at((u1.vcc.x, u1.vcc.y + 0.5)).to((u1.vcc.x + 1.2, u1.vcc.y + 0.5))
d += elm.Line().at(u1.gnd).down(0.5)
d += elm.Ground()
for a, net, r in (("a1", "CLK0 < IO18", "R5"), ("a2", "DATA0 < IO23", "R6"), ("a3", "CLK1 < IO14", "R7"), ("a4", "DATA1 < IO13", "R8")):
    p = getattr(u1, a)
    d += elm.Line().at(p).left(0.9)
    n = d.add(elm.Dot())
    d += elm.Line().left(1.2)
    d += elm.Dot(open=True).label(net, loc="left", fontsize=7.5)
    d += elm.Resistor().at(n.center).down(0.9).label(r + " 10 k", loc="right", fontsize=7)
    d += elm.Ground()
for a in ("oe1", "oe2", "oe3", "oe4"):
    d += elm.Line().at(getattr(u1, a)).left(0.4)
    d += elm.Ground()
note(d, (0.2, 1.6), "All four /OE to GND: outputs always enabled.\nR5-R8 hold the inputs LOW while the ESP32 boots\n(IO13/14 carry weak internal pull-ups at reset),\nso the strips are clocked zeros, not noise.\nOn the perfboard each R sits across pins A-OE.", 7)
ys = {}
for a, r, net in (("y1", "R1", "CLK0"), ("y2", "R2", "DATA0"), ("y3", "R3", "CLK1"), ("y4", "R4", "DATA1")):
    d += elm.Line().at(getattr(u1, a)).right(0.5)
    d += elm.Resistor().right().label(r + " 68 R", loc="top", fontsize=7)
    d += elm.Line().right(0.4)
    ys[net] = d.add(elm.Dot())
jx = ys["CLK0"].center.x + 2.9
j3 = d.add(header(6, right=["5V_A", "GND", "CLK0", "GND", "DATA0", "GND"]).anchor("pin1").at((jx, 12.6)))
j4 = d.add(header(6, right=["5V_B", "GND", "CLK1", "GND", "DATA1", "GND"]).anchor("pin1").at((jx, 5.6)))
note(d, (jx + 0.9, 12.9), "J3 (2.54 mm screw terminal, 6P): chain-0 start lead", 7.5)
note(d, (jx + 0.9, 5.9), "J4 (2.54 mm screw terminal, 6P): chain-1 start lead", 7.5)
route = {"CLK0": (j3.pin3, jx - 1.4), "DATA0": (j3.pin5, jx - 1.0), "CLK1": (j4.pin3, jx - 1.0), "DATA1": (j4.pin5, jx - 1.4)}
for net, (p, xv) in route.items():
    d += elm.Line().at(ys[net].center).to((xv, ys[net].center.y))
    d += elm.Line().to((xv, p.y))
    d += elm.Line().to(p)
for j, bus in ((j3, "5V_A"), (j4, "5V_B")):
    d += elm.Line().at(j.pin1).left(0.5)
    d += elm.Vdd().label(bus, fontsize=7)
    gx = j.pin2.x - 1.9
    d += elm.Line().at((gx, j.pin2.y)).to((gx, j.pin6.y))
    d += elm.Ground().at((gx, j.pin6.y))
    for k in (2, 4, 6):
        d += elm.Line().at(getattr(j, "pin%d" % k)).to((gx, getattr(j, "pin%d" % k).y))
note(d, (0.2, -0.9), "Feeds (2P 2.54 mm screw terminals, 26 AWG 5V/GND pairs, 105-240 mm): J6 -> strip 3, J7 -> strip 6, J8 -> strip 9 (bus A);  J9 -> 15, J10 -> 18, J11 -> 21 (bus B). "
                     "Each feed is spliced into the 5V/GND of the jumper at that strip's bottom end, so every pad still takes one wire.", 7.5)

sx, sy = jx + 7.4, 7.4


def strip(x, y, s, inverted):
    bottom = [pin("5V", "", "bottom", "b5"), pin("CO" if inverted else "CI", "", "bottom", "bc"), pin("DO" if inverted else "DI", "", "bottom", "bd"), pin("GND", "", "bottom", "bg")]
    top = [pin("5V", "", "top", "t5"), pin("CI" if inverted else "CO", "", "top", "tc"), pin("DI" if inverted else "DO", "", "top", "td"), pin("GND", "", "top", "tg")]
    return d.add(elm.Ic(pins=bottom + top, size=(3.0, 3.0), pinspacing=0.65, leadlen=0.5).right().at((x, y)).anchor("center")
                 .label("strip %d\n14 x SK9822\narrow %s" % (s, "DOWN" if inverted else "UP"), loc="center", fontsize=7.5))


s0 = strip(sx, sy, 0, False)
s1 = strip(sx + 4.2, sy, 1, True)
s2 = strip(sx + 8.4, sy, 2, False)
for a, lbl in (("b5", "5V_A"), ("bc", "CLK0"), ("bd", "DATA0"), ("bg", "GND")):
    p = getattr(s0, a)
    d += elm.Line().at(p).down(0.5)
    d += elm.Dot(open=True).label(lbl, loc="bottom", fontsize=6.5)
note(d, (sx - 1.9, sy - 3.0), "from J3", 7)
for a in ("t5", "tc", "td", "tg"):
    pa, pb = getattr(s0, a), getattr(s1, a)
    h = 0.45 + {"t5": 0.0, "tc": 0.3, "td": 0.6, "tg": 0.9}[a]
    d += elm.Line().at(pa).up(h)
    d += elm.Line().to((pb.x, pa.y + h))
    d += elm.Line().to(pb)
note(d, (sx + 0.2, sy + 3.9), "top jumper 0 -> 1: 4 x 28 AWG ribbon, 45 mm (5V, clock, data, GND straight across)", 7)
for a in ("b5", "bc", "bd", "bg"):
    pa, pb = getattr(s1, a), getattr(s2, a)
    h = 0.45 + {"b5": 0.0, "bc": 0.3, "bd": 0.6, "bg": 0.9}[a]
    d += elm.Line().at(pa).down(h)
    d += elm.Line().to((pb.x, pa.y - h))
    d += elm.Line().to(pb)
note(d, (sx + 4.4, sy - 4.0), "bottom jumper 1 -> 2 (same ribbon)", 7)
note(d, (sx + 10.6, sy + 0.5), "... 2->3 top, 3->4 bottom (+ feed J6),\n4->5 top, 5->6 bottom (+ J7), 6->7 top,\n7->8 bottom, 8->9 top, 9->10 bottom (+ J8),\n10->11 top; strip 11 bottom: CO/DO open.\n"
                                "Chain 1 (strips 12-23) is identical, from J4.", 7.5)
note(d, (sx - 2.0, 13.6), "Chain 0 = strips 0..11 at 0..165 deg. EVEN strips: input at the BOTTOM, data runs UP. ODD strips are mounted inverted (arrow down): input at the TOP.\n"
                          "Pad order on BTF SK9822 strips is typically 5V | CI | DI | GND at the input end and 5V | CO | DO | GND at the output end: read the silkscreen first.", 7.5)
note(d, (sx - 2.0, 1.6), "Start leads (2): 26 AWG 5V + GND pair, CLK twisted with a 28 AWG GND, DATA twisted with a 28 AWG GND; 0.20 m;\nboth signal GNDs join the feed GND 30 mm before the strip's GND pad (one wire per pad).", 7)
save(d, "elec_sch_b_shifter_chains")

# ====================================================================== Sheet C: base
d = schemdraw.Drawing(unit=2.2, fontsize=9)
note(d, (0, 6.2), "Sheet C  -  BASE: 12 V jack, PWM controller, gearmotor  (shares no conductor with the rotor)", 12)
YP, YN = 3.4, 0.8
src = d.add(elm.Ic(pins=[pin("0 V", "", "right", "n"), pin("+12 V", "", "right", "p")], size=(2.8, 2.4), pinspacing=1.2, leadlen=0.5).right().at((1.4, 2.8)).anchor("center")
            .label("12 V / 2 A\nwall adapter or\nbench supply\n(5.5 x 2.1 mm plug,\ncentre positive)", loc="center", fontsize=7.5))
d += elm.Line().at(src.p).right(1.0)
j13 = d.add(header(2, right=["+ (centre)", "- (sleeve)"]).anchor("pin1").at(d.here).label("J13  DC jack DC-022B\nin the back flat", loc="bottom", fontsize=7.5))
d += elm.Wire("-|").at(src.n).to((j13.pin2.x - 0.35, j13.pin2.y))
d += elm.Line().to(j13.pin2)
d += elm.Line().at(j13.pin1).right(2.4)
n1 = d.add(elm.Dot())
d += elm.Line().at(j13.pin2).right(0.6)
d += elm.Wire("|-").to((n1.center.x, YN))
n0 = d.add(elm.Dot())
d += elm.Capacitor(polar=True).at(n1.center).to(n0.center).label("C6 470 uF 25 V\n(optional: only if the\nsupply lead is long)", loc="left", fontsize=7)
d += elm.Line().at(n1.center).right(1.4)
u5 = d.add(elm.Ic(pins=[pin("IN-", "", "left", "im"), pin("IN+", "", "left", "ip"), pin("OUT- (M-)", "", "right", "om"), pin("OUT+ (M+)", "", "right", "op")],
                  size=(4.6, 2.8), pinspacing=1.2, leadlen=0.6).right().anchor("ip").at(d.here)
            .label("U5  PWM speed controller\n(kit's CCM6N; 1203B class)\nRV1 knob through the front flat\n~40-45 % duty for 225 rpm", loc="center", fontsize=7.5))
d += elm.Line().at(n0.center).to((u5.im.x - 0.6, YN))
d += elm.Wire("|-").to(u5.im)
d += elm.Line().at(u5.op).right(1.6)
n2 = d.add(elm.Dot())
d += elm.Line().at(u5.om).right(1.6)
n3 = d.add(elm.Dot())
d += elm.Capacitor().at(n2.center).to(n3.center).label("C7 100 nF X7R 50 V\nsoldered across the\nmotor terminals", loc="left", fontsize=7)
d += elm.Line().at(n2.center).right(1.6)
m1 = d.add(elm.Ic(pins=[pin("-", "", "left", "n"), pin("+", "", "left", "p")], size=(3.0, 2.4), pinspacing=1.2, leadlen=0.4).right().anchor("p").at(d.here)
            .label("M1  JGB37-520\n12 V, 600 rpm no-load\n0.6 A rated, 1.65 A stall\n22 AWG leads, 0.2 m", loc="center", fontsize=7.5))
d += elm.Line().at(n3.center).to(m1.n)
note(d, (0, -1.4), "B06: two 6 x 3 mm magnets glued in the deck pocket at r 42, theta 90 deg. The A3144 switches on one pole only: if it never triggers, flip the stack.\n"
                   "Nothing else is electrical in the base. The rotor's 5 V system and this 12 V system share no conductor, so no slip ring and no common ground: the only\n"
                   "coupling is the magnet's field once per revolution (and the motor's brush noise, radiated, which C7 tames).", 7.5)
save(d, "elec_sch_c_base")
