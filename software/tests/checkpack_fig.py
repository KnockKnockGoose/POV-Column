"""Figure for the check-pack-send audit: what each test animation asks for at full brightness (the current model) next to
what the column draws once the firmware's cap has picked its brightness (calibrated estimate, bench -> datasheet).

    py software/tests/checkpack_fig.py      # reads software/out/checkpack_audit/results.json (run checkpack_audit.py first)
"""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
RES = HERE.parent / "out" / "checkpack_audit" / "results.json"
OUT = REPO / "docs" / "img" / "2026-11-23-checkpack-current.png"

SURFACE, INK, INK2, MUTED, SERIES = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984", "#2a78d6"
ROWS = [  # (case key, label)
    ("white_full", "Full white, every LED"),
    ("white_stripes4", "White on every 4th column"),
    ("red_full", "Full red, every LED"),
    ("white_front_third", "White over the front third"),
    ("public:bichon_shades_front", "Biscuit in sunglasses (AI)"),
    ("public:biscuit_jetski", "Biscuit on a jet ski (AI)"),
    ("public:dog_ball_front", "Dog chasing a ball"),
    ("dark", "Everything off"),
]


def main() -> int:
    r = json.loads(RES.read_text(encoding="utf-8"))["cases"]
    labels = [lab for _, lab in ROWS][::-1]
    asked = [r[k]["firmware"]["total_ma_gb31"] / 1000 for k, _ in ROWS][::-1]
    lo = [r[k]["current_estimate"]["31"]["bench"]["peak_ma"] / 1000 for k, _ in ROWS][::-1]
    hi = [r[k]["current_estimate"]["31"]["datasheet"]["peak_ma"] / 1000 for k, _ in ROWS][::-1]
    gbs = [r[k]["firmware"]["fit"]["31"]["gb_used"] for k, _ in ROWS][::-1]
    y = range(len(ROWS))

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10.5, "text.color": INK, "axes.labelcolor": INK2,
                         "xtick.color": INK2, "ytick.color": INK})
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.5, 4.6), gridspec_kw=dict(width_ratios=[1, 1.15], wspace=0.08),
                                 sharey=True)
    fig.patch.set_facecolor(SURFACE)
    for ax in (a1, a2):
        ax.set_facecolor(SURFACE)
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
        ax.spines["bottom"].set_color(MUTED)
        ax.tick_params(axis="y", length=0)
        ax.grid(axis="x", color="#e6e5e1", linewidth=0.8)
        ax.set_axisbelow(True)

    # left: what the frames ask for at brightness 31 (the model: 20 mA per colour, 1 mA idle per LED, 120 mA ESP32)
    a1.barh(list(y), asked, height=0.52, color=SERIES, edgecolor=SURFACE, linewidth=2)
    for yi, v in zip(y, asked):
        a1.text(v + 0.3, yi, f"{v:.1f} A", va="center", ha="left", color=INK2, fontsize=9.5)
    a1.set_xlim(0, 24)
    a1.set_yticks(list(y), labels)
    a1.set_xlabel("amps (model)")
    a1.set_title("What the animation asks for at full brightness", loc="left", fontsize=11.5, color=INK, pad=10)

    # right: after the firmware cap, worst rotor angle: bench-calibrated (low) to datasheet + 170 mA ESP32 (high)
    for yi, l, h in zip(y, lo, hi):
        a2.plot([l, h], [yi, yi], color=SERIES, linewidth=7, solid_capstyle="round")
    for yi, l, g in zip(y, lo, gbs):
        a2.text(l - 0.07, yi, f"plays at {g}/31", va="center", ha="right", color=INK2, fontsize=9.5)
    a2.axvline(3.0, color=INK, linewidth=1.6)
    a2.text(3.04, len(ROWS) - 0.35, "3 A fuse", ha="left", va="bottom", color=INK, fontsize=10, fontweight="bold")
    a2.axvline(2.72, color=INK2, linewidth=1.2, linestyle=(0, (4, 3)))
    a2.text(2.68, len(ROWS) - 0.35, "cap: 2.72 A by the model", ha="right", va="bottom", color=INK2, fontsize=9.5)
    a2.set_xlim(0, 3.6)
    a2.set_ylim(-0.6, len(ROWS) - 0.1)
    a1.set_ylim(-0.6, len(ROWS) - 0.1)
    a2.set_xlabel("amps (estimate at the worst rotor angle)")
    a2.set_title("What the column draws after the firmware's cap", loc="left", fontsize=11.5, color=INK, pad=10)

    fig.text(0.01, 0.005, "Model: 20 mA per colour channel, 1 mA idle per LED, 120 mA ESP32 (povframe.h). Estimate range: "
             "Brian's 11-04 strip readings (17.1-17.7 mA per colour,\n0.57 mA idle) up to the SK9822 datasheet's 18 mA "
             "with 1 mA idle and a 170 mA ESP32. Brightness requested: 31/31; the firmware lowers it per animation.",
             fontsize=8.3, color=INK2)
    fig.subplots_adjust(left=0.19, right=0.985, top=0.88, bottom=0.2)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=160, facecolor=SURFACE)
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
