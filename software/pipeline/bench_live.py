"""bench_live.py - prompt -> playing timings for the live demo (2026-11-23), one-shot CLI and/or the warm daemon.

    py software/pipeline/mock_column.py                                 # or the real column (check it's free first)
    py software/pipeline/pov_serve.py --port 8791 --target http://127.0.0.1:18080 --out-root <dir> \
        --args "--scope public --no-cache --placeholder-kind thinking --no-preview --wait-playing"
    py software/pipeline/bench_live.py --target http://127.0.0.1:18080 --serve http://127.0.0.1:8791 --runs 2 --out <dir>

"cold" runs `pov_request.py --fast` as a fresh process per prompt (how Main runs it); "warm" POSTs to pov_serve.py.
Both wait for the board to report the animation loaded (--wait-playing), so playing_s is prompt -> on the LEDs.
Writes <out>/bench_live.jsonl and prints a table with medians.
"""
from __future__ import annotations

import argparse
import json
import statistics as stats
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROMPTS = ["Biscuit riding a jet ski", "Biscuit wearing sunglasses", "Biscuit on a skateboard",
           "a goose skateboarding", "fireworks over a city skyline", "a rocket launching into space"]
ARGS = ["--scope", "public", "--no-cache", "--placeholder-kind", "thinking", "--no-preview", "--wait-playing"]


def row(rep: dict, kind: str, prompt: str, run: int, wall: float) -> dict:
    st = rep.get("stages", {})
    llm = st.get("llm") or {}
    u = llm.get("usage") or {}
    up = rep.get("upload") if isinstance(rep.get("upload"), dict) else {}
    return dict(kind=kind, prompt=prompt, run=run, wall=round(wall, 2), exit=rep.get("exit"),
                playable_s=rep.get("playable_s"), playing_s=rep.get("playing_s"), total_s=rep.get("total_s"),
                llm_s=llm.get("seconds"), api_s=llm.get("api_s"), first_token_s=llm.get("first_token_s"),
                result_s=llm.get("result_s"), warm=llm.get("warm"), out_tok=u.get("output_tokens"),
                in_tok=(u.get("input_tokens") or 0) + (u.get("cache_read_input_tokens") or 0) + (u.get("cache_creation_input_tokens") or 0),
                cache_read=u.get("cache_read_input_tokens"), render_s=(st.get("render") or {}).get("wall_s"),
                attempts=(st.get("render") or {}).get("attempts"), bytes=up.get("bytes"), fit=bool(st.get("fit")),
                upload_s=up.get("upload_s"), load_ms=up.get("load_ms"), playing=up.get("playing"),
                error=rep.get("error"), source=rep.get("source"))


def cold(prompt: str, run: int, a, out: Path) -> dict:
    od = out / f"cold_r{run}_{abs(hash(prompt)) % 10**6}"
    rf = od / "rep.json"
    od.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    subprocess.run([sys.executable, "-X", "utf8", str(HERE / "pov_request.py"), prompt, "--fast", "--target", a.target,
                    "--out-dir", str(od), "--no-log", "--report", str(rf)] + ARGS + a.extra,
                   capture_output=True, text=True, encoding="utf-8")
    rep = json.loads(rf.read_text(encoding="utf-8")) if rf.exists() else {}
    return row(rep, "cold", prompt, run, time.time() - t0)


def warm(prompt: str, run: int, a) -> dict:
    import requests
    t0 = time.time()
    rep = requests.post(a.serve.rstrip("/") + "/pov", json={"prompt": prompt, "args": a.extra}, timeout=300).json()
    return row(rep or {}, "warm", prompt, run, time.time() - t0)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", default="http://127.0.0.1:18080")
    ap.add_argument("--serve", default=None, help="pov_serve.py URL for the warm runs (omit: cold only)")
    ap.add_argument("--modes", default="cold,warm")
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--gap", type=float, default=5.0, help="seconds between warm requests (the pool re-warms)")
    ap.add_argument("--prompts", nargs="*", default=PROMPTS)
    ap.add_argument("--extra", default="", help="more pov_request args, e.g. \"--model claude-opus-5-5\"")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    a.extra = a.extra.split()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    modes = [m for m in a.modes.split(",") if m and (m != "warm" or a.serve)]
    for run in range(a.runs):
        for p in a.prompts:
            for m in modes:
                r = cold(p, run, a, out) if m == "cold" else warm(p, run, a)
                rows.append(r)
                print(json.dumps(r), flush=True)
                with open(out / "bench_live.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps(r) + "\n")
                if m == "warm":
                    time.sleep(a.gap)
    for m in modes:
        rs = [r for r in rows if r["kind"] == m]
        ok = [r["playing_s"] for r in rs if r.get("playing")]
        print(f"{m}: {len(ok)}/{len(rs)} played; median prompt->playing {stats.median(ok) if ok else '-'} s; "
              f"median LLM {stats.median([r['llm_s'] for r in rs if r.get('llm_s')]) if rs else '-'} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
