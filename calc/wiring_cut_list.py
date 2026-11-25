"""Wire cut list from the CAD routes (wiring CAD, 2026-11-02; rev g 2026-11-03). Run: py calc/wiring_cut_list.py

Reads calc/wiring_cad_routes.json (rotor) and wiring_cad_routes_base.json (base) written by the Fusion scripts 093 / 094 (rotor wiring
rebuilt by 103, 130), groups the individual wire bodies into the items Brian cuts, and writes
  docs/img/wiring_cut_list.csv      one row per cut item: qty, gauge, colour, from, to, CAD routed length, cut length, the electrical
                                     report's table value, note
  docs/img/elec_wiring_table.csv    the electrical report's wiring table with the cut lengths replaced by the CAD values (old value kept
                                     in a second column). The CAD column is ALWAYS rewritten from the current routes (QA finding M6: the
                                     first version only filled it when it was absent, so a later route iteration never refreshed it).
Cut length = routed centreline length + 2 x 5 mm (strip / solder) + 10 % handling slack, rounded UP to 5 mm. Jumpers: the routed length
already includes the rev g slack loop (the ribbon pulled out of the second slot to solder that end pads-up), so cut = routed + 2 x 4 mm,
rounded up to 5 mm, no extra slack.
"""
import csv
import json
import math
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(HERE, "..", "docs", "img")


def cut_len(routed, ends=5.0, slack=0.10, step=5.0):
    return math.ceil((routed + 2 * ends + slack * routed) / step) * step


routes = []
for fn in ("wiring_cad_routes.json", "wiring_cad_routes_base.json"):
    p = os.path.join(HERE, fn)
    if os.path.exists(p):
        routes += json.load(open(p, encoding="utf-8"))["routes"]

items = {}      # key -> dict
for r in routes:
    n = r["name"]
    if n.startswith("jumper_"):
        m = re.match(r"jumper_(\d\d)_(\d\d)_(top|bottom)_(\w+)", n)
        key = "jumper %d-%d" % (int(m.group(1)), int(m.group(2)))
        it = items.setdefault(key, dict(item=key, qty=0, gauge="4 x 28 AWG ribbon", colour="red, orange, yellow, green (5V, CLK, DATA, GND)", frm=r["from"], to=r["to"].split(" (")[0], routed=0.0,
                                        note="%s end: first end soldered on the bench, ribbon in through strip %d's slot, out through strip %d's slot, second end soldered pads-up beside the tube with the ribbon pulled out ~27 mm, slack pushed back in as a loop past the slot; tape over both slots and the loop" % (m.group(3), int(m.group(1)), int(m.group(2)))))
        it["qty"] = 1; it["routed"] = max(it["routed"], r["length_mm"]); it["n"] = it.get("n", 0) + 1
    elif n.startswith("feed_"):
        m = re.match(r"feed_(\d\d)_(\w+)", n)
        key = "feed %d" % int(m.group(1))
        it = items.setdefault(key, dict(item=key, qty=2, gauge="26 AWG silicone", colour="red (5V), black (GND)", frm=r["to"].split(" pin")[0], to="strip %d bottom 5V / GND pads" % int(m.group(1)), routed=0.0, note="2.54 mm screw terminal at the carrier (wire enters from the ESP32 side); through the sled slot, under the plate in its lane, up through the bottom wall slot beside the ribbon"))
        it["routed"] = max(it["routed"], r["length_mm"])
    elif n.startswith("start_"):
        m = re.match(r"start_(\d\d)_(\w+)", n)
        s = int(m.group(1))
        lab = m.group(2)
        if lab in ("5V", "GND"):
            key = "start lead %d power pair" % s
            it = items.setdefault(key, dict(item=key, qty=2, gauge="26 AWG silicone", colour="red (5V), black (GND)", frm="J3 pins 1-2" if s == 0 else "J4 pins 1-2", to="strip %d bottom 5V / GND pads" % s, routed=0.0, note="with the 4 signal wires in one bundle (2 x 3) under the plate; into the 6P screw terminal from below"))
        else:
            key = "start lead %d signal wires" % s
            it = items.setdefault(key, dict(item=key, qty=4, gauge="28 AWG silicone", colour="orange (CLK) + black, yellow (DATA) + black, twisted pairs", frm="J3 pins 3-6" if s == 0 else "J4 pins 3-6", to="strip %d bottom CI / DI pads; the two blacks spliced into the 26 AWG GND 30 mm before the pad" % s, routed=0.0, note="the two signal GNDs are 30 mm shorter (splice); tin and fold the 28 AWG ends for the 2.54 mm terminal clamps"))
        it["routed"] = max(it["routed"], r["length_mm"])
    elif n.startswith("hall_lead"):
        key = "hall lead"
        it = items.setdefault(key, dict(item=key, qty=3, gauge="28 AWG silicone, twisted", colour="white (OUT), black (GND), red (5V)", frm="J5 pins 1-3", to="A3144 legs 3 / 2 / 1 at the cap's lead slot", routed=0.0, note="under the plate in its lane, out through the -x sled slot; into the 3P screw terminal from below (tin + fold the 28 AWG ends)"))
        it["routed"] = max(it["routed"], r["length_mm"])
    elif n.startswith("switch_loop"):
        key = "switch loop"
        it = items.setdefault(key, dict(item=key, qty=2, gauge="22 AWG silicone", colour="red, red (both 5 V)", frm="J2 pins 1-2 (2P screw terminal, wires enter from the board edge)", to="KCD11 spade tabs", routed=0.0, note="across to the wall at theta 352.5 deg, up the inside wall (Kapton every 50 mm, inward step at the mid ring), under the cap to the tabs"))
        it["routed"] = max(it["routed"], r["length_mm"])
    elif n.startswith("pigtail_cable"):
        key = "pigtail (as bought)"
        it = items.setdefault(key, dict(item=key, qty=1, gauge="22 AWG 2-core USB-A pigtail", colour="black jacket; red / black tails (verify with a meter)", frm="bank USB-A (+x port)", to="J1 screw terminal", routed=0.0, note="plug -> up -> inline fuse holder F1 over the bank top (x -33..7) -> down the -x side -> J1; zip tie at the cradle window"))
        it["routed"] = max(it["routed"], r["length_mm"])
    elif n.startswith("pigtail_"):
        items["pigtail (as bought)"]["tails"] = max(items["pigtail (as bought)"].get("tails", 0.0), r["length_mm"])
    elif n in ("jack_pos", "jack_neg"):
        key = "jack leads"
        it = items.setdefault(key, dict(item=key, qty=2, gauge="22 AWG", colour="red (+), black (-)", frm="DC jack centre / sleeve", to="PWM IN+ / IN-", routed=0.0, note="base: along the inside of the drum wall (-x half) at z -62"))
        it["routed"] = max(it["routed"], r["length_mm"])
    elif n in ("supply_pos", "supply_neg"):                                   # v4 (2026-11-03): no DC jack, the bench supply's pair enters through the back-flat notch
        key = "supply leads (base)"
        it = items.setdefault(key, dict(item=key, qty=2, gauge="22 AWG", colour="red (+), black (-)", frm="bench supply leads, from the notch in the back flat", to="PWM IN+ / IN-", routed=0.0, note="base: through the 8 x 6 notch under the IN terminal, under the staple bar on the bottom plate (zip tie), straight up into the terminal; the routed length is the inside part only"))
        it["routed"] = max(it["routed"], r["length_mm"])
    elif n.startswith("pot_cable"):
        key = "pot cable (base)"
        it = items.setdefault(key, dict(item=key, qty=1, gauge="3-wire cable (kit)", colour="as supplied", frm="WH148 pot terminals (front flat)", to="PWM pot connector (-x end)", routed=0.0, note="base: along the drum wall at r 92 above the standoff webs; the kit cable must be >= the routed length + 40"))
        it["routed"] = max(it["routed"], r["length_mm"])
    elif n in ("motor_pos", "motor_neg"):
        key = "motor leads"
        it = items.setdefault(key, dict(item=key, qty=2, gauge="22 AWG", colour="red (+), black (-)", frm="PWM OUT+ / OUT-", to="motor tabs (C7 100 nF across)", routed=0.0, note="base: under the motor's rear cap"))
        it["routed"] = max(it["routed"], r["length_mm"])

REPORT = {"start lead": 200, "feed 3": 150, "feed 6": 200, "feed 9": 200, "feed 15": 150, "feed 18": 150, "feed 21": 150, "jumper": 45, "hall lead": 120,
          "switch loop": 250, "pigtail (as bought)": 280, "motor leads": 200, "jack leads": 150}


def report_val(key):
    for k, v in REPORT.items():
        if key.startswith(k):
            return v
    return ""


rows = []
for key in sorted(items, key=lambda k: (not k.startswith("start"), not k.startswith("feed"), not k.startswith("jumper"), k)):
    it = items[key]
    if key.startswith("jumper"):
        cut = cut_len(it["routed"], ends=4.0, slack=0.0, step=5.0)
    elif key.startswith("pigtail"):
        cut = it["routed"] + it.get("tails", 0.0)
    else:
        cut = cut_len(it["routed"])
    rep = report_val(key)
    delta = (cut - rep) if rep != "" else ""
    rows.append([it["item"], it["qty"], it["gauge"], it["colour"], it["frm"], it["to"], round(it["routed"] + it.get("tails", 0.0), 0), int(cut), rep, delta, it["note"]])

with open(os.path.join(IMG, "wiring_cut_list.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["item", "qty (wires)", "gauge / type", "colour", "from", "to", "CAD routed length mm", "cut length mm (CAD)", "electrical report cut mm", "delta mm", "route / note"])
    w.writerows(rows)

# update the electrical report's wiring table with the CAD cut lengths. The CAD column is ALWAYS rebuilt from the current routes
# (QA finding M6: the first version only filled it when absent, so a later route iteration never refreshed it); the "before" column
# (the electrical report's own estimate) is kept as it was.
src = os.path.join(IMG, "elec_wiring_table.csv")
old = list(csv.reader(open(src, encoding="utf-8")))
hdr, body = old[0], old[1:]
CAD_COL, OLD_COL = "cut length mm (CAD, current routes)", "cut length mm (electrical report, before the wiring CAD)"
if OLD_COL in hdr:                          # drop the stale CAD column (whatever its label); the "before" column follows it
    i = hdr.index(OLD_COL) - 1
    hdr = hdr[:i] + hdr[i + 1:]
    body = [r[:i] + r[i + 1:] for r in body]
hdr = hdr[:5] + [CAD_COL, OLD_COL] + hdr[6:]
new_body = []
for r in body:
    name = r[0]
    cad = ""
    if name.startswith("start lead"):
        s = int(name.split()[-1]); cad = max(int(x[7]) for x in rows if x[0].startswith("start lead %d" % s))
    elif name.startswith("feed"):
        cad = next(int(x[7]) for x in rows if x[0] == name)
    elif name.startswith("jumper"):
        cad = max(int(x[7]) for x in rows if x[0].startswith("jumper"))
    elif name == "hall lead":
        cad = next(int(x[7]) for x in rows if x[0] == "hall lead")
    elif name == "switch loop":
        cad = 2 * next((int(x[7]) for x in rows if x[0] == "switch loop"), 0) or ""
    elif name == "pigtail":
        cad = next(int(x[7]) for x in rows if x[0].startswith("pigtail"))
    elif name == "motor leads":
        cad = next((int(x[7]) for x in rows if x[0] == "motor leads"), "")
    elif name == "jack leads":                                              # v4: the jack is gone; the supply pair's inside run stands in
        cad = next((int(x[7]) for x in rows if x[0] in ("jack leads", "supply leads (base)")), "")
    new_body.append(r[:5] + [cad, r[5]] + r[6:])
with open(src, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(hdr)
    w.writerows(new_body)
print("elec_wiring_table.csv: CAD cut-length column rewritten from the current routes (old column kept)")
tot = {}
for r in rows:
    tot[r[2]] = tot.get(r[2], 0) + r[1] * r[7]
print("wiring_cut_list.csv: %d items" % len(rows))
for r in rows:
    print("  %-30s x%d %-26s routed %4.0f -> cut %4d (report %s, delta %s)" % (r[0], r[1], r[2], r[6], r[7], r[8], r[9]))
print("total wire by type (mm): " + ", ".join("%s %d" % (k, v) for k, v in tot.items()))
