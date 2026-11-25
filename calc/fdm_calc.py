"""fdm_calc - numbers behind docs/2026-11-03-fdm-optimisation.md (POV LED Column rev f, FDM optimisation).

Sections: loads on the printed parts, the bolted joints (bearing stress under heads / nuts on PETG and PET-CF, insert pull-out,
friction torque), the hub-core split (seat flatness -> axis tilt -> unbalance), thermal clamp on the tie rods with PETG, the
H2D dual-nozzle alternative (swap count / time / waste estimate), and the print time / material table read from the sliced
`.gcode.3mf` files (Metadata/slice_info.config: prediction s, weight g).  Run: py calc/fdm_calc.py
"""
import math, os, re, zipfile, json

HERE = os.path.dirname(os.path.abspath(__file__))
PRINT = os.path.join(HERE, "..", "cad", "print")

# ---------------------------------------------------------------- rotor / speeds (rev f checks, script 125)
M_ROTOR = 0.986            # kg (script 125: 986 g incl. 6 g unmodelled)
I_ZZ = 3.776e-3            # kg m^2
Z_CG = 101.1               # mm above the cap plate top (z 0)
U_MEAS = 55.2              # g mm (geometric, rev f)
RPM = (225.0, 300.0)
T_MOTOR = 0.0265           # N m (Copkim 0.28 kgf cm)
G = 9.81

# ---------------------------------------------------------------- materials (typical datasheet-class values for printed parts, XY; +-20 %)
MAT = {  # E GPa, yield/strength MPa, Tg C, CTE ppm/K, density g/cm3, $/kg (Brian's spools, approx.), creep note
    "PETG (Bambu Matte)": (2.0, 50.0, 80.0, 70.0, 1.27, 22.0, "creeps above ~20 MPa sustained at RT; inserts OK"),
    "PET-CF (Fiberon)": (6.0, 90.0, 80.0, 30.0, 1.30, 45.0, "CF carries sustained load (creep ~3-4x lower), stiff, low shrink; abrasive, 300 C hardened nozzle"),
    "PLA (fit-check only)": (3.5, 60.0, 60.0, 70.0, 1.24, 20.0, "creeps badly under bolt preload, softens at 55-60 C; prototypes only"),
}


def torque_to_preload(T_Nm, d_m=0.003, K=0.2):
    """Nut-factor relation F = T / (K d)."""
    return T_Nm / (K * d_m)


def bearing(F, d_out, d_in):
    return F / (math.pi / 4 * (d_out ** 2 - d_in ** 2))


def main():
    print("=== POV LED Column rev f: FDM optimisation numbers ===\n")
    print("-- loads on the printed rotor parts")
    for rpm in RPM:
        w = 2 * math.pi * rpm / 60
        print("  %3.0f rpm: omega %.1f rad/s, rotor weight %.1f N, unbalance force at the G6.3 budget (%.0f g mm) %.2f N, at the geometric U %.0f g mm %.3f N, rim %.1f g" % (
            rpm, w, M_ROTOR * G, M_ROTOR * 6.3 / w * 1000, M_ROTOR * 6.3 / w * w ** 2 / 1000 * 1000 / 1000, U_MEAS, U_MEAS * 1e-6 * w ** 2, w ** 2 * 0.08 / G))
    alpha = T_MOTOR / I_ZZ
    print("  spin-up: alpha %.1f rad/s2, inertial torque on the rotor = motor torque %.3f N m; a hand grab stopping it in 0.2 s needs %.2f N m" % (alpha, T_MOTOR, I_ZZ * (2 * math.pi * 225 / 60) / 0.2))
    print("  the only torque into the printed parts is this %.3f N m through the coupling flange -> hub core -> cap plate -> tube" % T_MOTOR)

    print("\n-- bolted joints: preload from torque (K = 0.2, M3), bearing stress under the head / nut")
    for T in (0.1, 0.2, 0.5):
        F = torque_to_preload(T)
        print("  M3 at %.1f N m -> %.0f N preload: SHCS head d5.5 on a d3.4 hole %.1f MPa | with a d7 washer %.1f MPa | countersunk cone (d6.2/d3.4 projected) %.1f MPa | nyloc face (17 mm2) %.1f MPa" % (
            T, F, bearing(F, 5.5, 3.4), bearing(F, 7.0, 3.4), bearing(F, 6.2, 3.4), F / 17.0))
    print("  limits: PETG sustained ~20 MPa (creep), PET-CF ~40 MPa; so PETG joints get snug torque (0.1 N m) + threadlocker or a washer; PET-CF takes 0.2 N m")
    F_snug = torque_to_preload(0.1)
    print("  hub core <-> cap plate (4 x M3 x 8 csk into M3 x 6 inserts): preload %.0f N per screw vs insert pull-out in PET-CF ~400-600 N (factor %.1f); rotor weight adds %.1f N per screw" % (
        F_snug, 400 / F_snug, M_ROTOR * G / 4))
    print("  friction torque capacity of that joint: mu 0.3 x 4 x %.0f N x 0.018 m = %.2f N m = %.0f x the motor torque; shear capacity of 4 M3 at r 18: %.0f N m" % (
        F_snug, 0.3 * 4 * F_snug * 0.018, 0.3 * 4 * F_snug * 0.018 / T_MOTOR, 4 * 5.03 * 0.6 * 400 * 0.018))
    print("  coupling <-> core (4 x M3 x 8 into the 1.98 mm tapped flange): axial %.1f N per screw; thread shear in steel at 2 mm engagement ~%.0f N per screw" % (M_ROTOR * G / 4, 0.5 * 400 * math.pi * 3.0 * 2.0 * 0.6))

    print("\n-- seat flatness -> rotor axis tilt -> unbalance (the reason the core prints pocket-up)")
    for name, delta in (("printed top layer (inverted core)", 0.03), ("printed top layer, worse case", 0.05), ("bridged ceiling, rev e (sag)", 0.2), ("bridged ceiling, asymmetric sag", 0.4)):
        tilt = delta / 22.0
        shift = tilt * Z_CG
        U = M_ROTOR * 1000 * shift
        print("  seat error %.2f mm over d22: tilt %.2f mrad, CG shift %.2f mm, U %.0f g mm (%.0f %% of the 264 budget, %.1f M3 trim nuts), top-of-tube runout %.2f mm  [%s]" % (
            delta, tilt * 1000, shift, U, 100 * U / 264, U / 26, tilt * 250, name))
    print("  spigot d28 in d28.4 (0.2 radial): if the core sits hard to one side the rotor is 0.2 off the shaft axis -> %.0f g mm; the H2D prints the hole ~0.1 small, so expect <= 0.1 -> %.0f g mm, trimmed by the r 72 nuts" % (
        M_ROTOR * 1000 * 0.2, M_ROTOR * 1000 * 0.1))

    print("\n-- tie-rod clamp on a PETG cap (thermal mismatch, unchanged physics from rev e)")
    k_rod = 210e9 * math.pi * 1.5e-3 ** 2 / 0.2568
    k_tube = 2.0e9 * math.pi * (0.08 ** 2 - 0.0784 ** 2) / 0.25
    dF = (70e-6 - 17e-6) * 10 * 0.25 * (k_rod * k_tube / (k_rod + k_tube))
    print("  k_rod %.1f MN/m, k_tube (PETG, E 2 GPa) %.1f MN/m; +10 K adds %.0f N per rod (%.0f MPa on the nut face in PETG -> yields locally, relaxes; nylocs retain regardless)" % (
        k_rod / 1e6, k_tube / 1e6, dF, dF / 17.0))

    print("\n-- H2D dual nozzle as an alternative to splitting (estimate)")
    layers_mixed = int(round(8.0 / 0.2))
    print("  one-piece cap with a PET-CF hub region: both materials present in ~%d layers -> ~%d nozzle swaps; at ~20 s + ~0.8 g purge each: +%.0f min, +%.0f g waste; the seat stays a bridged ceiling (orientation unchanged)" % (
        layers_mixed, layers_mixed, layers_mixed * 20 / 60, layers_mixed * 0.8))
    print("  PLA-interface supports under the rev e seat (PETG part): ~%d layers with support -> ~%d swaps, +%.0f min; finish of a supported ceiling ~0.1-0.2 mm -> %.0f-%.0f g mm from the tilt table above" % (
        int(4.0 / 0.2), int(4.0 / 0.2), int(4.0 / 0.2) * 20 / 60, M_ROTOR * 1000 * 0.1 / 22 * Z_CG, M_ROTOR * 1000 * 0.2 / 22 * Z_CG))
    print("  verdict: use the two nozzles to print the PET-CF core and the PETG plate on ONE plate (print-by-object, no per-layer swaps), not to mix materials inside a part")

    print("\n-- print time / material from the sliced files (Metadata/slice_info.config)")
    rows = []
    for fn in sorted(os.listdir(PRINT)):
        if not fn.endswith(".gcode.3mf"):
            continue
        try:
            si = zipfile.ZipFile(os.path.join(PRINT, fn)).read("Metadata/slice_info.config").decode("utf-8", "replace")
        except Exception as e:
            print("  ", fn, "unreadable:", e); continue
        t = re.search(r'key="prediction" value="(\d+)"', si)
        g = re.search(r'key="weight" value="([\d.]+)"', si)
        ft = re.search(r'<filament [^>]*?\stype="([^"]+)"', si)
        rows.append((fn.replace(".gcode.3mf", ""), int(t.group(1)) / 3600 if t else float("nan"), float(g.group(1)) if g else float("nan"), ft.group(1) if ft else "?"))
    for stem, h, grams, ftype in rows:
        print("  %-36s %6.2f h %7.1f g  %s" % (stem, h, grams, ftype))
    sets = {
        "rev e production (hub + sled PET-CF, tube/top cap/base PETG, plate PLA)": ["rotor_tube_PETG", "rotor_top_cap_PETG", "base_shell_PETG", "base_bottom_plate_PLA", "rotor_bottom_cap_hub_PET-CF", "rotor_sled_PET-CF"],
        "rev f production (core PET-CF, everything else PETG)": ["rotor_tube_PETG", "rotor_top_cap_PETG", "base_shell_f_PETG", "base_bottom_plate_PETG", "rotor_bottom_cap_f_PETG", "rotor_hub_core_PET-CF", "rotor_sled_f_PETG"],
        "rev f production with the 0.28 mm tube": ["rotor_tube_PETG-0.28", "rotor_top_cap_PETG", "base_shell_f_PETG", "base_bottom_plate_PETG", "rotor_bottom_cap_f_PETG", "rotor_hub_core_PET-CF", "rotor_sled_f_PETG"],
        "rev f PLA fit-checks (new)": ["rotor_hub_core_PLA-fitcheck", "rotor_bottom_cap_f_PLA-fitcheck", "rotor_sled_f_PLA-fitcheck"],
    }
    by = {r[0]: r for r in rows}
    out = {"files": {r[0]: {"hours": r[1], "grams": r[2], "type": r[3]} for r in rows}, "sets": {}}
    for name, stems in sets.items():
        hrs = sum(by[s][1] for s in stems if s in by)
        gr = {}
        for s in stems:
            if s in by:
                gr[by[s][3]] = gr.get(by[s][3], 0.0) + by[s][2]
        missing = [s for s in stems if s not in by]
        print("  %-70s %6.2f h  %s %s" % (name, hrs, ", ".join("%s %.0f g" % kv for kv in sorted(gr.items())), ("MISSING " + ", ".join(missing)) if missing else ""))
        out["sets"][name] = {"hours": hrs, "grams_by_type": gr, "missing": missing}
    with open(os.path.join(HERE, "fdm_print_table.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print("  -> calc/fdm_print_table.json")


if __name__ == "__main__":
    main()
