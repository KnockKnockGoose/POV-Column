"""Figures for docs/2026-11-23-live-demo-pipeline.md, from the saved benchmark data in docs/data/2026-11-23-live-demo/.

    py software/pipeline/live_demo_figs.py

Palette: the dataviz reference categorical slots in order (blue, orange, aqua, yellow), validated with its
validate_palette.js (light mode: all hard gates pass; aqua and yellow are under 3:1 on the surface, so every mark
carries a direct label in ink).
"""
from __future__ import annotations

import json
import statistics as st
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "docs" / "data" / "2026-11-23-live-demo"
IMG = REPO / "docs" / "img"
SLOTS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
PROMPTS = ["Biscuit riding a jet ski", "Biscuit wearing sunglasses", "Biscuit on a skateboard", "a goose skateboarding",
           "fireworks over a city skyline", "a rocket launching into space"]
plt.rcParams.update({"font.family": ["Segoe UI", "DejaVu Sans"], "font.size": 11, "axes.edgecolor": GRID,
                     "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK, "figure.facecolor": SURFACE,
                     "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE})


def rows(name):
    return [json.loads(ln) for ln in (DATA / name).read_text(encoding="utf-8").splitlines() if ln.strip()]


def played_before(r):
    up = r.get("upload")
    return isinstance(up, dict) and up.get("play") == 200


def fig_timings():
    before = [r for r in rows("baseline_0cf3f1f.jsonl") if r["kind"] == "warm"]
    after = [r for r in rows("after.jsonl") if r["kind"] == "warm"]
    fig, ax = plt.subplots(figsize=(10.5, 5.6), dpi=160)
    h = 0.34
    for i, p in enumerate(PROMPTS):
        y = len(PROMPTS) - 1 - i
        a = [r["playing_s"] for r in after if r["prompt"] == p and r.get("playing")]
        b = [r["playing_est_s"] for r in before if r["prompt"] == p and played_before(r)]
        nb = sum(1 for r in before if r["prompt"] == p)
        if a:
            va = st.median(a)
            ax.barh(y + h / 2 + 0.02, va, height=h, color=SLOTS[0], edgecolor=SURFACE, linewidth=2)
            ax.text(va + 0.25, y + h / 2 + 0.02, f"{va:.1f} s  ({len(a)}/{len(a)} played)", va="center", color=INK, fontsize=10)
        if b:
            vb = st.median(b)
            ax.barh(y - h / 2 - 0.02, vb, height=h, color=SLOTS[1], edgecolor=SURFACE, linewidth=2)
            miss = nb - len(b)
            ax.text(vb + 0.25, y - h / 2 - 0.02, f"{vb:.1f} s  ({len(b)}/{nb} played" + (", 1 refused: > 64 KB)" if miss else ")"),
                    va="center", color=INK, fontsize=10)
        else:
            ax.text(0.25, y - h / 2 - 0.02, f"never reached the column (0/{nb}: files over 64 KB)", va="center",
                    color=INK2, fontsize=10, style="italic")
    ax.set_yticks(range(len(PROMPTS)))
    ax.set_yticklabels(list(reversed(PROMPTS)))
    ax.set_xlim(0, 21)
    ax.set_xlabel("prompt -> playing on the column (s), warm daemon, median of the runs that played")
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=SLOTS[0]), plt.Rectangle((0, 0), 1, 1, color=SLOTS[1])],
              labels=["after (this build)", "before (0cf3f1f, 11-22)"], loc="upper right", frameon=False)
    ax.set_title("Prompt to light, before and after: 6 prompts x 2 warm runs, mock column with real-board delays",
                 loc="left", color=INK, fontsize=12.5, fontweight="bold", pad=12)
    fig.tight_layout()
    fig.savefig(IMG / "2026-11-23-live-demo-timings.png")
    plt.close(fig)


def fig_split():
    evs = rows("f9_take_events.jsonl")
    at = {f"{e['stage']}_{e['state']}": e["at"] for e in evs}
    t0 = next(e.get("release_at") for e in evs if e["stage"] == "heard" and e.get("release_at"))
    segs = [("Whisper, on this PC", at["heard_done"] - t0),
            ("Claude writes the code", at["llm_done"] - at["heard_done"]),
            ("sandbox, check, pack", at["pack_done"] - at["llm_done"]),
            ("Wi-Fi upload + board load", at["playing_done"] - at["pack_done"])]
    fig, ax = plt.subplots(figsize=(10.5, 3.0), dpi=160)
    x = 0.0
    for i, (lab, d) in enumerate(segs):
        ax.barh(0, d, left=x, height=0.42, color=SLOTS[i], edgecolor=SURFACE, linewidth=2)
        below = d < 0.8                                   # a narrow segment's label goes under the bar
        ax.text(x + d / 2, -0.3 if below else 0.3, f"{lab}\n{d:.2f} s", ha="center", va="top" if below else "bottom",
                color=INK, fontsize=9.5)
        x += d
    ax.text(x + 0.12, 0, f"{x:.1f} s\nvoice -> light", va="center", color=INK, fontsize=11, fontweight="bold")
    ax.set_xlim(0, x + 1.3)
    ax.set_ylim(-0.95, 1.0)
    ax.set_yticks([])
    ax.set_xlabel("seconds after F9 is released (simulated F9 take: Whisper's 2.4 s median, mock column)")
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_title("Where the time goes: \"Biscuit riding a jet ski\" through the warm daemon", loc="left", color=INK,
                 fontsize=12.5, fontweight="bold", pad=8)
    fig.tight_layout()
    fig.savefig(IMG / "2026-11-23-live-demo-time-split.png")
    plt.close(fig)


if __name__ == "__main__":
    fig_timings()
    fig_split()
    print("wrote", IMG / "2026-11-23-live-demo-timings.png", IMG / "2026-11-23-live-demo-time-split.png")
