"""Render a test clip through the whole caption chain into an MP4 (both modes, camera model, latency overlay, audio).

    py software/captions/render_clip.py take2                       # a clip in %LOCALAPPDATA%/POVColumn/captions/clips
    py software/captions/render_clip.py take2 --engine kroko --stills docs/img
    py software/captions/render_clip.py my16k.wav --ref my16k.ref.json

Chain (all on a simulated clock, so the result is deterministic and the latency is measured, not guessed):
  1. the recogniser runs on the clip in simulated real time (bench_asr.run_clip timing rules: a poll that takes c s
     of wall time delays everything after it), recording when each word became stable;
  2. each emitted word is matched to the reference transcript (large-v3 word times), which gives its true end time;
  3. two Sessions (word mode, ticker mode) run the driver, a 15 ms link estimate and the column model at 30 Hz ticks;
  4. every video frame is a 1/30 s camera exposure of the spinning column (225 rpm, sim.exposure + FastCylinder),
     so a word that changes mid-exposure appears half drawn, exactly as on the Sony at 30p, 1/30 s;
  5. the clip's audio is muxed in, so you can judge the delay by ear and eye.
Output: software/out/captions/<clip>_<engine>.mp4 (gitignored) and a metrics-only JSON next to bench/results.json.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "bench"))
import asr  # noqa: E402
from bench_asr import align, norm_words, read_wav  # noqa: E402
from column_model import COLS, ROWS, WIN_L, WIN_R, Config  # noqa: E402
from paths import CLIPS_DIR, OUT_DIR  # noqa: E402
from session import Session  # noqa: E402
from sim import FastCylinder, exposure, to_lin  # noqa: E402

CAM_PHASE = 0.4 / 30      # camera exposures start 0.4 tick after the column's tick boundary (arbitrary, fixed)
LINK_S = 0.015            # Wi-Fi + WebSocket + JSON parse on the ESP32: estimate until measured on hardware


def run_asr_events(eng, audio, sr=16000):
    """Simulated real-time run; returns [(t_emit, stable, stable_t, partial)]."""
    step, dur = eng.step_s, len(audio) / sr
    now, fed, ev = 0.0, 0.0, []
    while fed < dur:
        now = max(now, min(fed + step, dur))
        eng.accept(audio[int(fed * sr):int(now * sr)])
        fed = now
        w0 = time.perf_counter()
        p = eng.poll()
        now += time.perf_counter() - w0
        ev.append((now, p.stable, p.stable_t, p.partial))
    w0 = time.perf_counter()
    p = eng.finish()
    now += time.perf_counter() - w0
    ev.append((now, p.stable, p.stable_t, ""))
    return ev


def true_ends(events, ref_words):
    """Reference end time for every emitted word (None if it does not match the reference)."""
    hyp, owner = [], []
    for ei, (_, stable, _, _) in enumerate(events):
        for wi, w in enumerate(stable):
            for nw in norm_words(w):
                hyp.append(nw)
                owner.append((ei, wi))
    rt = [(nw, b) for w, a, b in ref_words for nw in norm_words(w)]
    _, _, _, matches = align([w for w, _ in rt], hyp)
    ends = {}
    for i, j in matches:
        ends[owner[j]] = rt[i][1]
    return ends


def flat_view(rgb, scale=3):
    img = np.zeros((ROWS * scale, COLS * scale, 3), np.uint8)
    up = np.repeat(np.repeat(rgb[::-1], scale, 0), scale, 1)
    img[:] = 22
    lit = up.max(axis=2) > 0
    img[lit] = up[lit]
    cv2.rectangle(img, (WIN_L * scale, 0), ((WIN_R + 1) * scale - 1, ROWS * scale - 1), (90, 90, 100), 1)
    return img[:, :, ::-1]


def put(img, text, xy, size=0.55, col=(220, 220, 220), thick=1):
    cv2.putText(img, text, xy, cv2.FONT_HERSHEY_SIMPLEX, size, col, thick, cv2.LINE_AA)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("clip")
    ap.add_argument("--ref")
    ap.add_argument("--engine", default=asr.DEFAULT_ENGINE)
    ap.add_argument("--threads", type=int, default=None)
    ap.add_argument("--seconds", type=float, default=0)
    ap.add_argument("--partial", action="store_true")
    ap.add_argument("--ticker-style", choices=["hybrid", "crawl"], default="hybrid")
    ap.add_argument("--scroll-style", choices=["jump", "smooth"], default="jump")
    ap.add_argument("--stills", default=None, help="folder for PNG stills (e.g. docs/img)")
    ap.add_argument("--still-times", default="", help="comma list of seconds for stills (default: 3 spread out)")
    ap.add_argument("--no-mp4", action="store_true")
    a = ap.parse_args(argv)

    wav = a.clip if a.clip.endswith(".wav") else os.path.join(CLIPS_DIR, a.clip + ".wav")
    name = os.path.splitext(os.path.basename(wav))[0]
    ref = json.load(open(a.ref or wav[:-4] + ".ref.json", encoding="utf-8"))
    audio = read_wav(wav)
    if a.seconds:
        audio = audio[:int(a.seconds * 16000)]
        ref["words"] = [w for w in ref["words"] if w[2] <= a.seconds]
    dur = len(audio) / 16000
    kw = {"threads": a.threads} if a.threads else {}
    eng = asr.make(a.engine, **kw)
    events = run_asr_events(eng, audio)
    ends = true_ends(events, ref["words"])

    sessions = {m: Session(m, partial=a.partial, link_s=LINK_S, cam_phase=CAM_PHASE,
                           cfg=Config(tick_style=a.ticker_style, scroll_style=a.scroll_style)) for m in ("word", "tick")}
    tag = "" if (a.ticker_style, a.scroll_style) == ("hybrid", "jump") else f"_{a.ticker_style}-{a.scroll_style}" 
    VW, VH = 600, 470
    views = {m: FastCylinder(width=VW, height=VH) for m in sessions}
    os.makedirs(OUT_DIR, exist_ok=True)
    mp4 = os.path.join(OUT_DIR, f"{name}_{a.engine}{tag}.mp4")
    W, H = 2 * VW, 30 + VH + 3 * ROWS + 16 + 96
    proc = None
    if not a.no_mp4:
        proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
                                 "-s", f"{W}x{H}", "-r", "30", "-i", "-", "-i", wav, "-map", "0:v", "-map", "1:a",
                                 "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
                                 "-movflags", "+faststart", mp4], stdin=subprocess.PIPE)
    still_t = [float(x) for x in a.still_times.split(",") if x] or [dur * 0.3, dur * 0.55, dur * 0.8]
    stills_done = {}
    clean = {m: [0, 0] for m in sessions}      # camera frames with text in the window: [all, unchanged in exposure]
    ei, transcript, partial = 0, [], ""
    n_frames = int(dur * 30)
    dt = 0.005
    t, j = 0.0, 0
    while j < n_frames:
        t += dt
        while ei < len(events) and events[ei][0] <= t:
            te, stable, stable_t, part = events[ei]
            e = [ends.get((ei, wi)) for wi in range(len(stable))]
            for s in sessions.values():
                s.on_asr(stable, part, te, e)
            transcript += stable
            partial = part
            ei += 1
        for s in sessions.values():
            s.advance(t)
        t_exp_end = j / 30 + CAM_PHASE + 1 / 30
        if t < t_exp_end:
            continue
        # legibility on camera: did anything in the visible window change during this frame's exposure?
        t_a = j / 30 + CAM_PHASE
        for m, s in sessions.items():
            k0 = math.floor((t_a - s.tick_phase) * 30)
            k1 = math.floor((t_a + 1 / 30 - 1e-9 - s.tick_phase) * 30)
            f0, f1 = s.frames.get(k0), s.frames.get(k1)
            if f0 is not None and f1 is not None and (f0[:, WIN_L - 8:WIN_R + 9].any() or f1[:, WIN_L - 8:WIN_R + 9].any()):
                clean[m][0] += 1
                clean[m][1] += int(np.array_equal(f0[:, WIN_L - 8:WIN_R + 9], f1[:, WIN_L - 8:WIN_R + 9]))
        if proc is None and all(st in stills_done or (not a.stills) for st in still_t):
            j += 1                                    # metrics only: no drawing needed
            continue
        panels = []
        for m, s in sessions.items():
            pal = s.model.cfg.palette()
            cache = {}

            def at(k, s=s, pal=pal, cache=cache):
                if k not in cache:
                    fr = s.frames.get(k)
                    cache[k] = to_lin(pal[fr if fr is not None else np.zeros((ROWS, COLS), np.uint8)])
                return cache[k]
            cyl = np.ascontiguousarray(views[m].render(exposure(at, j / 30 + CAM_PHASE, 1 / 30))[:, :, ::-1])
            put(cyl, "ONE WORD AT A TIME" if m == "word" else "SCROLLING TICKER", (12, 26), 0.6, (200, 200, 200))
            recs = [r for r in s.records.values() if "camera" in r and r["camera"] <= j / 30 + 1e-6 and r.get("end")]
            if recs:
                r = recs[-1]
                put(cyl, f"'{r['w']}'  said -> on camera {1000 * (r['camera'] - r['end']):.0f} ms", (12, VH - 34),
                    0.55, (120, 230, 120))
                put(cyl, f"ASR {1000 * (r['emit'] - r['end']):.0f} + queue {1000 * (r['out'] - r['emit']):.0f} + link "
                         f"{1000 * (r['arrive'] - r['out']):.0f} + {'tick' if m == 'word' else 'crawl'} "
                         f"{1000 * (r['shown'] - r['arrive']):.0f} + camera {1000 * (r['camera'] - r['shown']):.0f}",
                    (12, VH - 12), 0.45, (120, 200, 120))
            fl = flat_view(pal[s.frames[s.k]])
            pan = np.zeros((VH + fl.shape[0] + 16, VW, 3), np.uint8)
            pan[:VH] = cyl
            pan[VH + 8:VH + 8 + fl.shape[0], (VW - fl.shape[1]) // 2:(VW - fl.shape[1]) // 2 + fl.shape[1]] = fl
            panels.append(pan)
        img = np.zeros((H, W, 3), np.uint8)
        put(img, f"POV column live captions, simulated camera (225 rpm, 30p, 1/30 s) | ASR: {a.engine} | link {1000 * LINK_S:.0f} ms (est.)",
            (12, 21), 0.55, (170, 170, 170))
        img[30:30 + panels[0].shape[0]] = np.hstack(panels)
        y0 = 30 + panels[0].shape[0] + 8
        now_s = j / 30
        said = [w for w, a0, b in ref["words"] if b <= now_s][-14:]
        put(img, "said:  " + " ".join(said), (12, y0 + 22), 0.6, (235, 235, 235))
        put(img, "ASR:   " + " ".join(transcript[-14:]) + ("  [" + partial + "]" if partial else ""), (12, y0 + 50), 0.55,
            (150, 150, 150))
        put(img, f"t = {now_s:5.2f} s", (W - 120, y0 + 22), 0.55, (150, 150, 150))
        if proc:
            proc.stdin.write(img.tobytes())
        for st in still_t:
            if st not in stills_done and now_s >= st:
                stills_done[st] = img.copy()
        j += 1
    if proc:
        proc.stdin.close()
        proc.wait()

    summary = dict(clip=name, engine=a.engine, styles=f"{a.ticker_style}/{a.scroll_style}", dur=round(dur, 2),
                   link_ms=1000 * LINK_S, when=time.strftime("%Y-%m-%d %H:%M"))
    for m, s in sessions.items():
        recs = [r for r in s.records.values() if "camera" in r and r.get("end") is not None]
        if not recs:
            continue
        g = lambda f: np.array([f(r) for r in recs])
        tot, asr_l = g(lambda r: r["camera"] - r["end"]), g(lambda r: r["emit"] - r["end"])
        q, link = g(lambda r: r["out"] - r["emit"]), g(lambda r: r["arrive"] - r["out"])
        tick, cam = g(lambda r: r["shown"] - r["arrive"]), g(lambda r: r["camera"] - r["shown"])
        summary[m] = dict(words=len(recs), dropped=s.dropped(),
                          clean_frames=round(clean[m][1] / max(1, clean[m][0]), 3),
                          e2e_med=round(float(np.median(tot)), 3), e2e_p90=round(float(np.percentile(tot, 90)), 3),
                          e2e_mean=round(float(tot.mean()), 3), frac_under_1s=round(float((tot < 1.0).mean()), 3),
                          asr_med=round(float(np.median(asr_l)), 3), queue_med=round(float(np.median(q)), 3),
                          queue_p90=round(float(np.percentile(q, 90)), 3), link=round(float(np.median(link)), 3),
                          tick_or_crawl_med=round(float(np.median(tick)), 3),
                          tick_or_crawl_p90=round(float(np.percentile(tick, 90)), 3),
                          camera_med=round(float(np.median(cam)), 3))
        print(f"{m:5s}: {len(recs)} words, speech -> on camera median {1000 * summary[m]['e2e_med']:.0f} ms, "
              f"p90 {1000 * summary[m]['e2e_p90']:.0f} ms, {100 * summary[m]['frac_under_1s']:.0f}% under 1 s "
              f"(ASR {1000 * summary[m]['asr_med']:.0f}, queue {1000 * summary[m]['queue_med']:.0f}, link "
              f"{1000 * summary[m]['link']:.0f}, {'tick' if m == 'word' else 'crawl'} {1000 * summary[m]['tick_or_crawl_med']:.0f}, "
              f"camera {1000 * summary[m]['camera_med']:.0f}); dropped {s.dropped()}; "
              f"clean camera frames {100 * summary[m]['clean_frames']:.0f}%")
    lat_path = os.path.join(HERE, "bench", "latency.json")
    allr = json.load(open(lat_path, encoding="utf-8")) if os.path.exists(lat_path) else []
    allr = [r for r in allr if not (r["clip"] == name and r["engine"] == a.engine and r.get("styles") == summary["styles"])]
    allr.append(summary)
    json.dump(allr, open(lat_path, "w", encoding="utf-8"), indent=1)
    if a.stills:
        os.makedirs(a.stills, exist_ok=True)
        for i, (st, im) in enumerate(sorted(stills_done.items())):
            p = os.path.join(a.stills, f"cap_{name}_{a.engine}{tag}_{i}.png")
            cv2.imwrite(p, im)
            print("still:", p)
    if proc:
        print("mp4:", mp4)


if __name__ == "__main__":
    main()
