"""Benchmark streaming ASR engines on the local test clips: word-emission latency, WER, CPU load.

    py software/captions/bench/bench_asr.py --engine kroko                 # one engine, all clips
    py software/captions/bench/bench_asr.py --all                          # every preset, one subprocess each
    py software/captions/bench/bench_asr.py --summary                      # print the table from saved results

Simulated real time: audio "arrives" at 1 s per second. The harness waits until `step_s` of new audio exists, feeds it,
and times the engine's poll() with the wall clock; a poll that takes c seconds delays everything after it (the engine
falls behind if it is slower than real time). A word's emission time is the audio-clock time at which the poll that
made it stable returned. Latency of a word = emission time - the word's end in the reference (large-v3 word
timestamps, +-0.1 s). WER is against the same large-v3 reference after light normalisation (a pseudo-reference: it
compares engines, it is not an absolute accuracy). CPU = process CPU seconds / audio seconds (1.0 = one core busy).

Per-clip transcripts go to %LOCALAPPDATA%/POVColumn/captions/bench/ (never committed); the metrics-only summary goes to
software/captions/bench/results.json.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import asr  # noqa: E402
from paths import CLIPS_DIR, ROOT  # noqa: E402

LOCAL = os.path.join(ROOT, "bench")
SUMMARY = os.path.join(HERE, "results.json")
os.makedirs(LOCAL, exist_ok=True)

NUM = {"zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7",
       "eight": "8", "nine": "9", "ten": "10"}


def norm_words(text_or_words) -> list[str]:
    s = " ".join(text_or_words) if isinstance(text_or_words, list) else text_or_words
    s = s.lower().replace("%", " percent").replace("-", " ").replace("’", "'")
    s = re.sub(r"[^a-z0-9' ]", " ", s)
    out = []
    for w in s.split():
        w = w.strip("'")
        if w:
            out.append(NUM.get(w, w))
    return out


def align(ref: list[str], hyp: list[str]):
    """Levenshtein alignment. Returns (S, D, I, matches) with matches = [(i_ref, j_hyp)] of equal words."""
    n, m = len(ref), len(hyp)
    d = np.zeros((n + 1, m + 1), np.int32)
    d[:, 0] = np.arange(n + 1)
    d[0, :] = np.arange(m + 1)
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i, j] = min(d[i - 1, j] + 1, d[i, j - 1] + 1, d[i - 1, j - 1] + (ref[i - 1] != hyp[j - 1]))
    i, j, S, D, I, matches = n, m, 0, 0, 0, []
    while i > 0 or j > 0:
        if i > 0 and j > 0 and d[i, j] == d[i - 1, j - 1] + (ref[i - 1] != hyp[j - 1]):
            if ref[i - 1] == hyp[j - 1]:
                matches.append((i - 1, j - 1))
            else:
                S += 1
            i, j = i - 1, j - 1
        elif i > 0 and d[i, j] == d[i - 1, j] + 1:
            D, i = D + 1, i - 1
        else:
            I, j = I + 1, j - 1
    return S, D, I, matches[::-1]


def read_wav(path):
    with wave.open(path, "rb") as w:
        return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768.0


def run_clip(eng: asr.StreamingASR, audio: np.ndarray, step_s: float | None = None):
    """Simulated real-time run. Returns emitted [(word, t_emit)], cpu_s, busy_s, max_lag_s."""
    sr = asr.SR
    step = step_s or eng.step_s
    dur = len(audio) / sr
    now, fed, emitted, cpu, busy, max_lag = 0.0, 0.0, [], 0.0, 0.0, 0.0
    while fed < dur:
        now = max(now, min(fed + step, dur))        # wait for the next chunk to exist
        k0, k1 = int(fed * sr), int(now * sr)
        eng.accept(audio[k0:k1])
        fed = now
        c0, w0 = time.process_time(), time.perf_counter()
        p = eng.poll()
        cw = time.perf_counter() - w0
        cpu += time.process_time() - c0
        busy += cw
        now += cw
        max_lag = max(max_lag, now - fed)
        emitted += [(w, now) for w in p.stable]
    c0, w0 = time.process_time(), time.perf_counter()
    p = eng.finish()
    now += time.perf_counter() - w0
    cpu += time.process_time() - c0
    emitted += [(w, now) for w in p.stable]
    return emitted, cpu, busy, max_lag


def flatten_emitted(emitted):
    """Engines emit display words; normalisation can split one into several tokens (e.g. 'well-known')."""
    out = []
    for w, t in emitted:
        for nw in norm_words(w):
            out.append((nw, t))
    return out


def bench_engine(name: str, clips: list[str], kw: dict, label: str | None = None):
    t0 = time.perf_counter()
    eng = asr.make(name, **kw)
    load_s = time.perf_counter() - t0
    import psutil
    rss = psutil.Process().memory_info().rss / 1e6
    per, lat_all, S_, D_, I_, N_, cpu_t, busy_t, dur_t, lags = [], [], 0, 0, 0, 0, 0.0, 0.0, 0.0, []
    for c in clips:
        audio = read_wav(os.path.join(CLIPS_DIR, c + ".wav"))
        ref = json.load(open(os.path.join(CLIPS_DIR, c + ".ref.json"), encoding="utf-8"))
        eng.reset()
        emitted, cpu, busy, max_lag = run_clip(eng, audio)
        # reference tokens with end times
        rt = []
        for w, a, b in ref["words"]:
            for nw in norm_words(w):
                rt.append((nw, b))
        ht = flatten_emitted(emitted)
        S, D, I, matches = align([w for w, _ in rt], [w for w, _ in ht])
        lat = [ht[j][1] - rt[i][1] for i, j in matches]
        dur = len(audio) / asr.SR
        per.append(dict(clip=c, dur=dur, ref_words=len(rt), wer=(S + D + I) / max(1, len(rt)),
                        lat_med=float(np.median(lat)) if lat else None, cpu=cpu / dur, max_lag=max_lag))
        json.dump(dict(engine=label or name, clip=c, emitted=emitted, ref=ref["words"]),
                  open(os.path.join(LOCAL, f"{label or name}__{c}.json"), "w", encoding="utf-8"))
        lat_all += lat
        S_, D_, I_, N_ = S_ + S, D_ + D, I_ + I, N_ + len(rt)
        cpu_t, busy_t, dur_t = cpu_t + cpu, busy_t + busy, dur_t + dur
        lags.append(max_lag)
    lat_all = np.array(lat_all)
    rss2 = psutil.Process().memory_info().rss / 1e6
    res = dict(engine=label or name, preset=name, kw=kw, desc=asr.ENGINES[name][1], load_s=round(load_s, 2),
               rss_mb=round(max(rss, rss2)), clips=per, words=int(N_),
               wer=round((S_ + D_ + I_) / N_, 4), sub=S_, dele=D_, ins=I_,
               lat_med=round(float(np.median(lat_all)), 3), lat_p90=round(float(np.percentile(lat_all, 90)), 3),
               lat_mean=round(float(lat_all.mean()), 3), lat_p10=round(float(np.percentile(lat_all, 10)), 3),
               cpu_cores=round(cpu_t / dur_t, 3), rtf=round(busy_t / dur_t, 3), max_lag=round(max(lags), 2),
               late_ext=getattr(eng, "late_extensions", None), host=os.environ.get("COMPUTERNAME", ""),
               when=time.strftime("%Y-%m-%d %H:%M"))
    return res


CONFIGS = [  # label, preset, kwargs
    ("kroko-t1", "kroko", dict(threads=1)),
    ("kroko-t1-hold0.25", "kroko", dict(threads=1, tail_hold=0.25)),
    ("fastconformer-t1", "fastconformer", dict(threads=1)),
    ("nemotron-t2", "nemotron", dict(threads=2)),
    ("whisper-base-t2-s0.5", "whisper-base", dict(threads=2, step_s=0.5)),
    ("whisper-small-t4-s1.0", "whisper-small", dict(threads=4, step_s=1.0)),
    ("whisper-distil-t4-s1.0", "whisper-distil", dict(threads=4, step_s=1.0)),
    ("whisper-base-t4-s1.0-trim8", "whisper-base", dict(threads=4, step_s=1.0, trim_s=8.0)),
    ("fastconformer-t1-hold0.25", "fastconformer", dict(threads=1, tail_hold=0.25)),
    ("fastconformer-t2", "fastconformer", dict(threads=2)),
]


def summary_table(results):
    print(f"{'engine':28s} {'WER':>6s} {'lat med':>8s} {'p90':>6s} {'CPU':>6s} {'RTF':>6s} {'lag':>5s} {'RSS':>6s}")
    for r in results:
        print(f"{r['engine']:28s} {100 * r['wer']:5.1f}% {r['lat_med']:7.2f}s {r['lat_p90']:5.2f}s "
              f"{r['cpu_cores']:6.2f} {r['rtf']:6.2f} {r['max_lag']:5.1f} {r['rss_mb']:5d}M")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine")
    ap.add_argument("--label")
    ap.add_argument("--kw", default="{}", help="JSON kwargs for the engine")
    ap.add_argument("--clips", default="take1,take2,take3,desk1,desk2")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--only", default="", help="comma list of config labels for --all")
    ap.add_argument("--summary", action="store_true")
    a = ap.parse_args(argv)
    clips = a.clips.split(",")
    allres = json.load(open(SUMMARY, encoding="utf-8")) if os.path.exists(SUMMARY) else []
    if a.summary:
        summary_table(allres)
        return
    if a.all:
        for label, preset, kw in CONFIGS:
            if a.only and label not in a.only.split(","):
                continue
            print(f"--- {label}", flush=True)
            subprocess.run([sys.executable, __file__, "--engine", preset, "--label", label, "--kw", json.dumps(kw),
                            "--clips", a.clips], check=False)
        summary_table(json.load(open(SUMMARY, encoding="utf-8")))
        return
    res = bench_engine(a.engine, clips, json.loads(a.kw), a.label)
    allres = [r for r in allres if r["engine"] != res["engine"]] + [res]
    json.dump(allres, open(SUMMARY, "w", encoding="utf-8"), indent=1)
    summary_table([res])
    for c in res["clips"]:
        print(f"   {c['clip']:6s} wer {100 * c['wer']:5.1f}%  lat {c['lat_med']}  cpu {c['cpu']:.2f}  lag {c['max_lag']:.2f}")


if __name__ == "__main__":
    main()
