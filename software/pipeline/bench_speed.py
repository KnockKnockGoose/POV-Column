"""Speed benchmark for the prompt-to-animation pipeline (2026-11-07 investigation).

    py software/pipeline/bench_speed.py run --configs opus,sonnet-low --prompts jetski,goose --runs 2 --parallel 4
    py software/pipeline/bench_speed.py summary                 # table: config -> median times, tokens, validator
    py software/pipeline/bench_speed.py grid goose              # blind comparison sheet of every run for one prompt
    py software/pipeline/bench_speed.py scores                  # join scores.json (from the blind grids) back to configs

Each job runs pov_request.py as a subprocess (so the timing is the real end-to-end path: Python start, claude -p,
sandbox render, validator) with --dry-run --no-preview --no-log and writes its stage report next to the .pova. A judge
strip (6 frames of the flat 96 x 42 grid, upscaled) is made afterwards for the quality score; it is not timed.
Outputs go to --root (default software/out/bench_speed, which git ignores).
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import random
import statistics as st
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOFTWARE = HERE.parent
sys.path.insert(0, str(SOFTWARE / "povgen"))
sys.path.insert(0, str(HERE))
import povanim  # noqa: E402

ROOT = Path(__file__).resolve().parents[1] / "out" / "bench_speed"
PROMPTS = {
    "jetski": "a fluffy white bichon frise riding a jet ski over waves, looped, for the video",
    "shades": "a big fluffy bichon frise head; a paw comes up and slides dark black sunglasses on, like the start of CSI, for the video",
    "goose": "a goose skateboarding",
    "fireworks": "fireworks over a city skyline",
    "laser": "a cat chasing a laser dot",
    # off-vocabulary prompts (nothing in scenekit draws these): test the template lane's honesty and the fallback
    "rocket": "a rocket launching into space",
    "dragon": "a dragon breathing fire",
    "snowman": "a snowman waving in the snow",
}
O, S, H = "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"
CONFIGS = {   # name -> extra pov_request.py args
    "opus": ["--model", O],                                   # 11-06 baseline (CLI default effort, prompt on stdin)
    "opus-low": ["--model", O, "--effort", "low"],
    "opus-med": ["--model", O, "--effort", "medium"],
    "sonnet": ["--model", S],
    "sonnet-low": ["--model", S, "--effort", "low"],
    "haiku": ["--model", H],
    "haiku-low": ["--model", H, "--effort", "low"],
    # 2026-11-07 round 2: scenekit prompt (short scripts against the helper library), prompt as --system-prompt-file
    "kit-opus-low": ["--model", O, "--effort", "low", "--variant", "kit", "--sys", "system"],
    "kit-sonnet": ["--model", S, "--variant", "kit", "--sys", "system"],
    "kit-sonnet-low": ["--model", S, "--effort", "low", "--variant", "kit", "--sys", "system"],
    "kit-haiku-low": ["--model", H, "--effort", "low", "--variant", "kit", "--sys", "system"],
    "v01-sonnet-low-sys": ["--model", S, "--effort", "low", "--sys", "system"],
    # template lanes (fall back to kit-sonnet-low code generation when the request does not fit)
    "tpl-keyword": ["--template", "keyword", "--model", S, "--effort", "low", "--variant", "kit", "--sys", "system"],
    "fast": ["--fast"],                                       # = template llm (Haiku JSON) -> kit-sonnet-low
    "fast-tpl-sonnet": ["--fast", "--template-model", S],
    # round 3: same kit configs after the 11-07 library fixes (bigger fireworks, dimmer stars, whiter bust)
    "kit2-opus-low": ["--model", O, "--effort", "low", "--variant", "kit", "--sys", "system"],
    "kit2-sonnet-low": ["--model", S, "--effort", "low", "--variant", "kit", "--sys", "system"],
    "kit2-haiku-low": ["--model", H, "--effort", "low", "--variant", "kit", "--sys", "system"],
    # final round: the two presets as shipped (progressive placeholder + kit code / template-first)
    "final-fast": ["--fast"],
    "final-fastest": ["--fastest"],
    "kit-sonnet-low-x2": ["--model", S, "--effort", "low", "--variant", "kit", "--sys", "system", "--candidates", "2"],
    "kit-sonnet-low-check": ["--model", S, "--effort", "low", "--variant", "kit", "--sys", "system", "--self-check"],
}


def job_dir(root: Path, config: str, prompt: str, run: int) -> Path:
    return root / "runs" / config / prompt / f"run{run}"


def run_job(root: Path, config: str, extra: list[str], key: str, run: int) -> dict:
    d = job_dir(root, config, key, run)
    d.mkdir(parents=True, exist_ok=True)
    rep_path = d / "report.json"
    cmd = [sys.executable, "-X", "utf8", str(HERE / "pov_request.py"), PROMPTS[key], "--scope", "public", "--dry-run",
           "--no-preview", "--no-log", "--out-dir", str(d), "--report", str(rep_path)] + extra
    if "--fast" not in extra and "--fastest" not in extra:
        cmd.append("--classic")   # configs without a preset measure the bare pipeline (--fast became the default 11-09)
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=900)
    wall = time.time() - t0
    rep = json.loads(rep_path.read_text(encoding="utf-8")) if rep_path.exists() else dict(exit=r.returncode, error=r.stderr[-800:])
    row = summarise(config, key, run, rep, wall)
    if row.get("pova"):
        try:
            judge_strip(Path(row["pova"]), d / "judge.png")
        except Exception as e:  # noqa: BLE001
            row["judge_error"] = str(e)
    with open(root / "results.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    return row


def summarise(config: str, key: str, run: int, rep: dict, wall: float) -> dict:
    st_ = rep.get("stages", {})
    llm = st_.get("llm", {})
    u = llm.get("usage") or {}
    val = st_.get("validate", {})
    out_tok = u.get("output_tokens")
    think = (u.get("output_tokens_details") or {}).get("thinking_tokens")
    attempts = 1 + sum(1 for k in st_ if k.startswith("render_error")) if "llm" in st_ else 0
    llm_s = (llm.get("seconds") or 0) + (st_.get("llm_repair", {}).get("seconds") or 0)
    pova = rep.get("file") if rep.get("exit") == 0 else None
    lines = None
    if pova and Path(pova).with_suffix(".py").exists():
        lines = len(Path(pova).with_suffix(".py").read_text(encoding="utf-8").splitlines())
    return dict(config=config, prompt=key, run=run, exit=rep.get("exit"), wall_s=round(wall, 1),
                playable_s=rep.get("playable_s"), llm_s=round(llm_s, 1), api_s=llm.get("api_s"), out_tok=out_tok,
                think_tok=think, in_tok=sum(u.get(k, 0) for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")),
                cache_read=u.get("cache_read_input_tokens"), cost=llm.get("cost_usd"), attempts=attempts,
                val_ok=val.get("ok"), warnings=val.get("warnings"), duration_s=val.get("duration_s"), frames=val.get("frames"),
                lit=val.get("lit_fraction_mean"), gb_rec=val.get("gb_recommended"), lines=lines, pova=pova,
                refused=rep.get("refused"), error=(rep.get("error") or "")[-300:] or None)


# ---------------------------------------------------------------- judge images
def judge_strip(pova: Path, out: Path, k: int = 6, scale: int = 3) -> None:
    import fastlane
    fastlane.contact_strip(pova, out, k, scale)


def blind_grid(root: Path, key: str, configs: list[str] | None = None, tag: str = "r1") -> Path:
    """All judge strips for one prompt, shuffled, labelled A, B, C...; the key goes to grids/<prompt>_key.json."""
    from PIL import Image, ImageDraw
    strips = sorted((root / "runs").glob(f"*/{key}/run*/judge.png"))
    if configs:
        strips = [s for s in strips if s.parts[-4] in configs]
    rnd = random.Random(sum(map(ord, key + tag)))
    rnd.shuffle(strips)
    ims = [Image.open(s) for s in strips]
    w = max(im.size[0] for im in ims)
    h = ims[0].size[1]
    grid = Image.new("RGB", (w + 40, len(ims) * (h + 6)), (20, 20, 24))
    d = ImageDraw.Draw(grid)
    mapping = {"_prompt": key}
    for i, (s, im) in enumerate(zip(strips, ims)):
        label = chr(ord("A") + i) if i < 26 else f"Z{i}"
        mapping[label] = f"{s.parts[-4]}/{s.parts[-2]}"
        grid.paste(im, (40, i * (h + 6)))
        d.text((8, i * (h + 6) + h // 2 - 6), label, fill=(255, 255, 0))
    (root / "grids").mkdir(exist_ok=True)
    out = root / "grids" / f"{key}_{tag}.png"
    grid.save(out)
    (root / "grids" / f"{key}_{tag}_key.json").write_text(json.dumps(mapping, indent=1), encoding="utf-8")
    return out


# ---------------------------------------------------------------- tables
def load_rows(root: Path) -> list[dict]:
    rows = {}
    p = root / "results.jsonl"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            rows[(r["config"], r["prompt"], r["run"])] = r      # later rows replace reruns
    return list(rows.values())


def load_scores(root: Path) -> dict:
    """scores.json: {"<prompt>_<tag>": {"A": 4, ...}} graded on the blind grids -> {(config, prompt, run): score}."""
    out = {}
    p = root / "scores.json"
    if not p.exists():
        return out
    for grid, marks in json.loads(p.read_text(encoding="utf-8")).items():
        kp = root / "grids" / f"{grid}_key.json"
        if not kp.exists():
            continue
        mapping = json.loads(kp.read_text(encoding="utf-8"))
        key = mapping["_prompt"]
        for label, score in marks.items():
            if label in mapping and not label.startswith("_"):
                cfg, run = mapping[label].split("/")
                out[(cfg, key, int(run[3:]))] = score
    return out


def med(xs):
    xs = [x for x in xs if x is not None]
    return round(st.median(xs), 1) if xs else None


def summary(root: Path, prompts: list[str] | None = None) -> list[dict]:
    rows, scores = load_rows(root), load_scores(root)
    if prompts:
        rows = [r for r in rows if r["prompt"] in prompts]
    table = []
    for cfg in sorted({r["config"] for r in rows}, key=lambda c: list(CONFIGS).index(c) if c in CONFIGS else 99):
        rs = [r for r in rows if r["config"] == cfg]
        ok = [r for r in rs if r["exit"] == 0]
        sc = [scores.get((r["config"], r["prompt"], r["run"])) for r in rs]
        sc_ok = [s for s in sc if s is not None]
        table.append(dict(config=cfg, n=len(rs), ok=len(ok), playable_med=med(r["playable_s"] for r in ok),
                          playable_max=max((r["playable_s"] for r in ok), default=None), llm_med=med(r["llm_s"] for r in rs),
                          out_tok_med=med(r["out_tok"] for r in rs), think_med=med(r["think_tok"] for r in rs),
                          attempts_mean=round(st.mean(r["attempts"] for r in rs), 2) if rs else None,
                          val_ok=sum(1 for r in ok if r["val_ok"]), loop_s_med=med(r["duration_s"] for r in ok),
                          cost_sum=round(sum(r["cost"] or 0 for r in rs), 2),
                          score_mean=round(st.mean(sc_ok), 2) if sc_ok else None, scored=len(sc_ok),
                          score_fail_as_1=round(st.mean([s if s is not None else (1 if r["exit"] != 0 else None) for s, r in zip(sc, rs)
                                                          if (s is not None or r["exit"] != 0)]), 2) if (sc_ok or any(r["exit"] for r in rs)) else None))
    return table


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("run", "summary", "grid", "scores", "strips"))
    ap.add_argument("arg", nargs="?")
    ap.add_argument("--configs", default="")
    ap.add_argument("--prompts", default="jetski,shades,goose,fireworks,laser")
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--first-run", type=int, default=1)
    ap.add_argument("--parallel", type=int, default=4)
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--tag", default="r1", help="grid: name of this grading round")
    ap.add_argument("--extra", default="", help="extra pov_request args for every job, e.g. '--sys system'")
    a = ap.parse_args(argv)
    root = Path(a.root)
    root.mkdir(parents=True, exist_ok=True)
    if a.cmd == "run":
        jobs = []
        for run in range(a.first_run, a.first_run + a.runs):
            for key in a.prompts.split(","):
                for cfg in a.configs.split(","):
                    jobs.append((cfg, CONFIGS[cfg] + (a.extra.split() if a.extra else []), key, run))
        print(f"{len(jobs)} jobs, {a.parallel} at a time", flush=True)
        with cf.ThreadPoolExecutor(a.parallel) as ex:
            futs = {ex.submit(run_job, root, *j): j for j in jobs}
            for f in cf.as_completed(futs):
                try:
                    r = f.result()
                    print(f"{r['config']:>14} {r['prompt']:>9} run{r['run']} exit={r['exit']} playable={r['playable_s']} "
                          f"llm={r['llm_s']} out={r['out_tok']} think={r['think_tok']} att={r['attempts']} ok={r['val_ok']}", flush=True)
                except Exception as e:  # noqa: BLE001
                    print("job failed", futs[f], e, flush=True)
    elif a.cmd == "summary":
        t = summary(root, a.prompts.split(","))
        print(json.dumps(t, indent=1))
        (root / ("summary.json" if a.prompts == "jetski,shades,goose,fireworks,laser" else "summary_" + a.prompts.replace(",", "_") + ".json")).write_text(json.dumps(t, indent=1), encoding="utf-8")
    elif a.cmd == "grid":
        print(blind_grid(root, a.arg, a.configs.split(",") if a.configs else None, a.tag))
    elif a.cmd == "strips":
        for r in load_rows(root):
            if r.get("pova"):
                judge_strip(Path(r["pova"]), Path(r["pova"]).parent / "judge.png")
    elif a.cmd == "scores":
        for k, v in sorted(load_scores(root).items()):
            print(k, v)
    return 0


if __name__ == "__main__":
    sys.exit(main())
