"""Carrier-board build model for the wiring guide, read from docs/img/elec_carrier_netlist.json (rev i, written by
software/elec/elec_carrier.py after its hole-to-net checks). Nothing here changes a net: it numbers the wires in build
order (W01..), gives each a colour, a cut length and a strip length, marks the one-hole hops that can be a bare link,
flags the ends that land on an ESP32 pin hole (soldered after the DevKit is in), and lists the bus tack holes.
Rev i (2026-11-04): every hole is named by Brian's printed label (column letter A-Z + row number 1-31, label(c, r) =
chr(65 + c) + str(r + 1)), with the grid coordinates (c, r) beside it in the CSV; the W numbering is the rev h one (same
wires in the same order, every row - 2).

  py software/elec/guide/carrier_data.py          -> docs/img/guide_carrier_wires.csv + markdown tables on stdout
"""
import csv
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from guide_common import IMG, load_netlist   # noqa: E402

N = load_netlist()
P = N["grid"]["pitch"]
PARTS = N["parts"]
U1 = {int(k): tuple(v) for k, v in N["U1"].items()}
U1_NAME = {int(k): v for k, v in N["U1_NAME"].items()}
ESP = N["esp"]
STRIP_MM = 3          # carrier wire ends: strip 3 mm, tin (electrical 7.3)
SLACK_MM = 3          # bends and the drop into the hole / onto the stub

STEP_OF = {"GND": "C7a", "5V_A": "C7b", "5V_B": "C7b", "LK1": "C7b",
           "IO18": "C7c", "IO23": "C7c", "IO14": "C7c", "IO13": "C7c", "Y1": "C7c", "Y2": "C7c", "Y3": "C7c", "Y4": "C7c",
           "CLK0": "C7c", "DATA0": "C7c", "CLK1": "C7c", "DATA1": "C7c", "HALL": "C7d", "3V3": "C7d"}
STEP_TITLE = {"C7a": "GND wires", "C7b": "5 V wires (bus A, bus B, LK1)", "C7c": "clock and data wires", "C7d": "hall and 3V3 wires"}
CLK_NETS = {"IO18", "Y1", "CLK0", "IO14", "Y3", "CLK1"}
DATA_NETS = {"IO23", "Y2", "DATA0", "IO13", "Y4", "DATA1"}


def colour_of(net):
    if net == "GND":
        return "black"
    if net in ("5V_A", "5V_B"):
        return "red"
    if net == "LK1":
        return "yellow"
    if net in CLK_NETS:
        return "yellow"      # Brian 2026-11-04: yellow = CLK, orange = DATA everywhere
    if net in DATA_NETS:
        return "orange"
    if net == "HALL":
        return "white"
    if net == "3V3":
        return "violet"
    raise KeyError(net)


def wire_spec(net, gauge):
    if gauge == "22":
        return "22 AWG silicone"
    if gauge == "26":
        return "26 AWG silicone"
    return "28 AWG (one conductor peeled from the rainbow ribbon)"


# ---------------------------------------------------------------- what sits in each hole
hole_what = {}


def add(h, what):
    hole_what.setdefault((int(h[0]), int(h[1])), []).append(what)


esp_holes = {}
for side in ("L", "R"):
    for i, nm in enumerate(ESP[side]):
        h = (ESP["C"][side], ESP["R0"] + i)
        esp_holes[h] = nm
        add(h, "ESP %s" % nm)
for k, h in U1.items():
    add(h, "U1.%d %s" % (k, U1_NAME[k]))
TP_NAMES = {tuple(h): nm for h, nm in zip(PARTS["TP"]["holes"], N.get("tp_names", ["TP1", "TP3", "TP2"]))}


def label(c, r):
    """Brian's printed label: column letter + row number (rev i grid: c 0..25 = A..Z, r 0..30 = rows 1..31)."""
    return "%s%d" % (chr(65 + int(c)), int(r) + 1)


def hl(h):
    return "%s (%d,%d)" % (label(*h), int(h[0]), int(h[1]))
for name, p in PARTS.items():
    for i, h in enumerate(p["holes"]):
        h = tuple(h)
        if name == "TP":
            add(h, TP_NAMES[h])
        elif p["kind"] == "elco":
            add(h, "%s%s" % (name, "+" if i == 0 else "-"))
        elif p["kind"] in ("small", "axial"):
            add(h, "%s.%s" % (name, ("top" if h[1] >= p["holes"][1 - i][1] else "bottom") if h[0] == p["holes"][1 - i][0] else str(i + 1)))
        else:
            add(h, "%s.%d" % (name, i + 1))
bus_holes = {}
BUSES = []
for n in N["nets"]:
    if not n["bare"]:
        continue
    for path in n["paths"]:
        segs = []
        for (c0, r0), (c1, r1) in zip(path, path[1:]):
            if c0 == c1:
                hs = [(int(c0), r) for r in range(int(min(r0, r1)), int(max(r0, r1)) + 1)]
            else:
                hs = [(c, int(r0)) for c in range(int(min(c0, c1)), int(max(c0, c1)) + 1)]
            for h in hs:
                bus_holes[h] = n["net"]
            segs.append(((c0, r0), (c1, r1), math.hypot(c1 - c0, r1 - r0) * P))
        BUSES.append((n["net"], path, segs))


def describe(h):
    h = (int(h[0]), int(h[1]))
    parts = list(hole_what.get(h, []))
    bus_name = {"GND": "GND bus", "5V_A": "bus A", "5V_B": "bus B"}
    if h in bus_holes and not parts:
        parts.append(bus_name[bus_holes[h]])
    elif h in bus_holes:
        parts.append("on " + bus_name[bus_holes[h]])
    return "%s %s" % (" / ".join(parts) if parts else "hole", label(*h))


def plen(path):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(path, path[1:])) * P


def ceil5(x):
    return int(math.ceil(x / 5.0) * 5)


# ---------------------------------------------------------------- wires in build order
WIRES = []
for step in ("C7a", "C7b", "C7c", "C7d"):
    for n in N["nets"]:
        if n["bare"] or STEP_OF[n["net"]] != step:
            continue
        for path in n["paths"]:
            a, b = tuple(path[0]), tuple(path[-1])
            L = plen(path)
            hop = len(path) == 2 and abs(L - P) < 1e-6
            esp_end = [h for h in (a, b) if (int(h[0]), int(h[1])) in esp_holes]
            w = dict(step=step, net=n["net"], gauge=n["gauge"], colour=colour_of(n["net"]), path=path, a=a, b=b,
                     frm=describe(a), to=describe(b), path_mm=L, hop=hop,
                     cut=None if hop else max(15, ceil5(L + 2 * STRIP_MM + SLACK_MM)),
                     strip="bare link" if hop else "%d / %d" % (STRIP_MM, STRIP_MM),
                     esp_end=esp_end)
            WIRES.append(w)
for i, w in enumerate(WIRES, 1):
    w["id"] = "W%02d" % i


def is_hole(p):
    return float(p[0]).is_integer() and float(p[1]).is_integer()


def route_text(path, coords=False):
    """Holes by label (with (c,r) when coords), lane points between holes as (c,r)."""
    pts = []
    for p in path:
        if is_hole(p):
            pts.append(hl(p) if coords else label(*p))
        else:
            pts.append("(%g,%g)" % (p[0], p[1]))
    return " → ".join(pts)


LK1_GAP = None
for _n in N["nets"]:
    if _n["net"] == "LK1":
        _a, _b = _n["paths"][0][0], _n["paths"][0][-1]
        LK1_GAP = (int(_a[0]), int((_a[1] + _b[1]) / 2))      # the empty hole the link jumps


def write_csv():
    out = os.path.join(IMG, "guide_carrier_wires.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["id", "step", "net", "type", "gauge / material", "colour", "from (printed label)", "to (printed label)", "from (c,r)", "to (c,r)",
                     "route (holes as label (c,r); fractional (c,r) = lane between holes)", "path mm", "cut mm", "strip each end mm", "note"])
        for w in WIRES:
            typ = "bare link (one-hole hop)" if w["hop"] else "insulated"
            mat = "bare tinned wire offcut (22 AWG solid or a resistor lead)" if w["hop"] else wire_spec(w["net"], w["gauge"])
            note_ = ""
            if w["esp_end"]:
                note_ = "ESP32 end %s: leave free (tinned) until the DevKit is soldered in (step C9), then lap it onto the pin stub" % \
                        ", ".join(hl(h) for h in w["esp_end"])
            if w["net"] == "LK1":
                note_ = "LK1: the one wire to snip for the two-pigtail option; leave %s empty" % hl(LK1_GAP)
            wr.writerow([w["id"], w["step"], w["net"], typ, mat, "bare" if w["hop"] else w["colour"], w["frm"], w["to"],
                         "(%d,%d)" % (int(w["a"][0]), int(w["a"][1])), "(%d,%d)" % (int(w["b"][0]), int(w["b"][1])), route_text(w["path"], coords=True),
                         "%.1f" % w["path_mm"], "" if w["hop"] else w["cut"], "-" if w["hop"] else w["strip"], note_])
        for net, path, segs in BUSES:
            L = sum(s[2] for s in segs)
            wr.writerow(["BUS-%s" % net, "C3", net, "bare bus", "22 AWG solid (TUOFENG), stripped bare, tinned", "bare", label(*path[0]), label(*path[-1]),
                         "(%d,%d)" % tuple(int(v) for v in path[0]), "(%d,%d)" % tuple(int(v) for v in path[-1]),
                         route_text(path, coords=True), "%.1f" % L, ceil5(L + 10), "-", "lay tangent to the pads; tack at both ends and at every tap hole"])
    print("wrote", out)
    return out


def tack_holes():
    """Bus holes that carry a wire end or a part lead (where the bus must be soldered)."""
    res = {}
    for w in WIRES:
        for h in (w["a"], w["b"]):
            hh = (int(h[0]), int(h[1]))
            if hh in bus_holes:
                res.setdefault(bus_holes[hh], set()).add(hh)
    for name, p in PARTS.items():
        for h in p["holes"]:
            hh = tuple(h)
            if hh in bus_holes:
                res.setdefault(bus_holes[hh], set()).add(hh)
    return {k: sorted(v) for k, v in res.items()}


def md_tables():
    lines = []
    for step in ("C7a", "C7b", "C7c", "C7d"):
        ws = [w for w in WIRES if w["step"] == step]
        lines.append("\n#### %s: %s (%d wires)\n" % (step, STEP_TITLE[step], len(ws)))
        lines.append("| W | Net | Wire | From | To | Route (lanes) | Cut mm | Strip mm |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for w in ws:
            if w["hop"]:
                wire_ = "bare link"
            else:
                g = {"22": "22", "26": "26", "28": "28"}[w["gauge"]]
                wire_ = "%s %s" % (g, w["colour"])
            fr, to = w["frm"], w["to"]
            if w["esp_end"]:
                for h in w["esp_end"]:
                    tag = label(*h)
                    fr = fr + " **C9**" if fr.endswith(" " + tag) else fr
                    to = to + " **C9**" if to.endswith(" " + tag) else to
            route = "adjacent hole" if w["hop"] else route_text(w["path"])
            lines.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (w["id"], w["net"], wire_, fr, to, route,
                                                                       "≈ 5" if w["hop"] else w["cut"], "-" if w["hop"] else w["strip"]))
    return "\n".join(lines)


def summary():
    from collections import Counter
    cnt = Counter()
    tot = Counter()
    for w in WIRES:
        if w["hop"]:
            cnt[("bare link", "")] += 1
            continue
        cnt[(w["gauge"], w["colour"])] += 1
        tot[(w["gauge"], w["colour"])] += w["cut"]
    return cnt, tot


if __name__ == "__main__":
    write_csv()
    print(md_tables())
    cnt, tot = summary()
    print("\nSUMMARY (gauge, colour): count, total cut mm")
    for k in sorted(cnt):
        print(k, cnt[k], tot.get(k, 0))
    print("\nBUS LENGTHS")
    for net, path, segs in BUSES:
        print(net, route_text(path), "%.1f mm" % sum(s[2] for s in segs))
    print("\nTACK HOLES", tack_holes())
    lens = {}
    for w in WIRES:
        if not w["hop"]:
            lens.setdefault((w["gauge"], w["colour"]), []).append(w["cut"])
    print("\nLENGTHS BY GROUP")
    for k, v in sorted(lens.items()):
        from collections import Counter as C2
        print(k, sorted(C2(v).items()))
