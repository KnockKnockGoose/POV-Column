"""Latency budget chart for the report: median of each term, speech -> on camera, per engine and mode.

    py software/captions/bench/plot_latency.py docs/img/cap_latency_budget.png

Reads bench/latency.json (written by render_clip.py), pooling all clips by word count. Terms are medians, so the bar
total is close to (not exactly) the end-to-end median printed at the right of each bar.
"""
import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
TERMS = [("asr_med", "ASR (word end -> stable)"), ("queue_med", "driver queue"), ("link", "Wi-Fi link (est.)"),
         ("tick_or_crawl_med", "tick wait / ticker crawl-in"), ("camera_med", "camera frame (30p)")]
COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]   # validated categorical slots 1-5 (dataviz skill)


def pooled(rows, engine, mode, styles="hybrid/jump"):
    rs = [r for r in rows if r["engine"] == engine and r.get("styles", styles) == styles and mode in r]
    if not rs:
        return None
    w = np.array([r[mode]["words"] for r in rs], float)
    out = {k: float(np.average([r[mode][k] for r in rs], weights=w)) for k, _ in TERMS}
    out["e2e_med"] = float(np.average([r[mode]["e2e_med"] for r in rs], weights=w))
    out["under1"] = float(np.average([r[mode]["frac_under_1s"] for r in rs], weights=w))
    out["words"] = int(w.sum())
    return out


def main(path):
    rows = json.load(open(os.path.join(HERE, "latency.json"), encoding="utf-8"))
    bars = []
    for eng in ("fastconformer", "nemotron", "kroko"):
        for mode, mlabel in (("word", "word"), ("tick", "ticker")):
            p = pooled(rows, eng, mode)
            if p:
                bars.append((f"{eng} / {mlabel}", p))
    fig, ax = plt.subplots(figsize=(10, 0.55 * len(bars) + 1.6), dpi=150)
    y = np.arange(len(bars))[::-1]
    for yi, (lab, p) in zip(y, bars):
        left = 0.0
        for (k, name), col in zip(TERMS, COLORS):
            v = 1000 * p[k]
            ax.barh(yi, v, left=left, height=0.6, color=col, edgecolor="white", linewidth=2)
            left += v
        ax.text(left + 15, yi, f"{1000 * p['e2e_med']:.0f} ms median, {100 * p['under1']:.0f}% < 1 s",
                va="center", fontsize=8.5, color="#333333")
    ax.set_yticks(y, [b[0] for b in bars], fontsize=9)
    ax.axvline(1000, color="#888888", linewidth=1, linestyle="--")
    ax.text(1005, y[0] + 0.45, "1 s target", fontsize=8, color="#666666")
    ax.set_xlabel("ms from the end of a spoken word to the word fully visible on camera (median of each term)")
    ax.set_xlim(0, 3200)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="x", color="#e6e6e6", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.legend([plt.Rectangle((0, 0), 1, 1, color=c) for c in COLORS], [n for _, n in TERMS], ncol=3, fontsize=8,
              frameon=False, loc="upper center", bbox_to_anchor=(0.45, -0.18 - 0.02 * (8 - len(bars))))
    ax.set_title("Live captions: latency budget per engine and mode (5 test clips, simulated real time on the desktop PC)",
                 fontsize=10, loc="left")
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    print(path)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "cap_latency_budget.png")
