"""LIVE CAPTIONS for the POV column: talk, and the column shows what you say.

    py software/captions/live.py --mode word                                  # preview window only (no hardware)
    py software/captions/live.py --mode tick
    py software/captions/live.py --mode both                                  # both modes side by side
    py software/captions/live.py --mode word --to ws://pov.local/ws           # + send to the column (caption msgs)
    py software/captions/live.py --mode word --to frames:ws://pov.local/ws    # fallback: PC-rendered frames
    py software/captions/live.py --mode both --file clip.wav                  # replay a 16 kHz WAV in real time
Options: --engine (default fastconformer; see asr.ENGINES), --device "<mic name part>", --partial (show the unstable
word dimmer), --no-preview, --seconds N, --token (X-POV-Token for the column).

Preview: povsim's camera model (30p, 1/30 s shutter, 225 rpm) of the column as the Sony would film it, with a latency
overlay per word: ASR (word end -> stable) + queue + link (estimated 15 ms until the hardware exists) + tick wait.
Keys: q / Esc quits. A JSONL log of every word and its latency terms goes to %LOCALAPPDATA%/POVColumn/captions/logs.
"""
from __future__ import annotations

import argparse
import json
import os
import queue
import sys
import threading
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import asr  # noqa: E402
import transport  # noqa: E402
from audio import SR, FileSource, MicSource  # noqa: E402
from column_model import Config  # noqa: E402
from paths import LOG_DIR  # noqa: E402
from session import Session  # noqa: E402
from sim import FastCylinder, exposure, to_lin  # noqa: E402

TITLE = "POV column live captions (simulated camera: 225 rpm, 30p, 1/30 s)"


def asr_thread(eng, src, out: queue.Queue, stop: threading.Event):
    buf, fed = [], 0.0
    while not stop.is_set():
        try:
            buf.append(src.q.get(timeout=0.1))
        except queue.Empty:
            if getattr(src, "done", False):
                p = eng.finish()
                out.put((p, time.perf_counter(), fed))
                stop.set()
            continue
        n = sum(len(b) for b in buf)
        if n >= eng.step_s * SR:
            x = np.concatenate(buf)
            buf = []
            fed += len(x) / SR
            eng.accept(x)
            p = eng.poll()
            if p.stable or p.partial is not None:
                out.put((p, time.perf_counter(), fed))


def overlay_lines(sess: Session, n=3):
    recs = [r for r in sess.records.values() if "shown" in r][-n:]
    out = []
    for r in recs:
        parts = []
        if r.get("end") is not None:
            parts.append(f"ASR {1000 * (r['emit'] - r['end']):4.0f}")
            total = r["shown"] - r["end"]
        else:
            total = None
        parts += [f"queue {1000 * (r['out'] - r['emit']):3.0f}", f"link {1000 * (r['arrive'] - r['out']):3.0f}",
                  f"{'tick' if sess.mode == 'word' else 'crawl'} {1000 * (r['shown'] - r['arrive']):3.0f}"]
        tot = f" = {1000 * total:4.0f} ms" if total is not None else ""
        out.append(f"{r['w'][:14]:14s} " + " + ".join(parts) + tot)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=["word", "tick", "both"], default="word")
    ap.add_argument("--engine", default=asr.DEFAULT_ENGINE, choices=list(asr.ENGINES))
    ap.add_argument("--threads", type=int, default=None)
    ap.add_argument("--to", default="sim", help="sim | null | ws://pov.local/ws | frames:ws://pov.local/ws")
    ap.add_argument("--token", default=os.environ.get("POV_TOKEN", ""))
    ap.add_argument("--device", default=None, help="substring of the microphone name (default: system default)")
    ap.add_argument("--file", default=None, help="replay a 16 kHz mono WAV in real time instead of the mic")
    ap.add_argument("--partial", action="store_true", help="also show the unstable word, dimmer")
    ap.add_argument("--ticker-style", choices=["hybrid", "crawl"], default="hybrid",
                    help="hybrid: still while talking, each word jumps in (legible on camera); crawl: smooth speed-controlled")
    ap.add_argument("--scroll-style", choices=["jump", "smooth"], default="jump", help="long words in word mode")
    ap.add_argument("--link-ms", type=float, default=15.0, help="assumed Wi-Fi + parse delay for the preview")
    ap.add_argument("--no-preview", action="store_true")
    ap.add_argument("--seconds", type=float, default=0, help="stop after N s (0 = until q)")
    ap.add_argument("--snapshot", default=None, help="save the last preview frame to this PNG on exit")
    a = ap.parse_args(argv)

    kw = {"threads": a.threads} if a.threads else {}
    print(f"loading {a.engine}: {asr.ENGINES[a.engine][1]}", flush=True)
    eng = asr.make(a.engine, **kw)
    src = FileSource(a.file) if a.file else MicSource(a.device)
    modes = ["word", "tick"] if a.mode == "both" else [a.mode]
    sink = None if a.to in ("sim", "null") else transport.make(a.to, token=a.token)
    sessions = {m: Session(m, partial=a.partial, link_s=a.link_ms / 1000, sink=sink if i == 0 else None,
                           cfg=Config(tick_style=a.ticker_style, scroll_style=a.scroll_style))
                for i, m in enumerate(modes)}
    views = {} if a.no_preview else {m: FastCylinder(width=560, height=470) for m in modes}
    res: queue.Queue = queue.Queue()
    stop = threading.Event()
    src.start()
    th = threading.Thread(target=asr_thread, args=(eng, src, res, stop), daemon=True)
    th.start()
    T0 = time.perf_counter()
    log = open(os.path.join(LOG_DIR, time.strftime("live-%Y%m%d-%H%M%S.jsonl")), "w", encoding="utf-8")
    print(f"listening on: {src.dev_name}  ->  {a.to}   (q to quit)", flush=True)
    transcript, partial, logged, img = [], "", set(), None
    next_draw = 0.0
    while True:
        t = time.perf_counter() - T0
        while not res.empty():
            p, tw, fed = res.get()
            te = tw - T0
            ends = None
            if p.stable_t and src.t0 is not None:
                ends = [src.t0 - T0 + e for e in p.stable_t]
            for s in sessions.values():
                s.on_asr(p.stable, p.partial, te, ends)
            transcript += p.stable
            partial = p.partial
        for s in sessions.values():
            s.advance(t)
            for key, r in s.records.items():
                if "shown" in r and (s.mode, key) not in logged:
                    logged.add((s.mode, key))
                    log.write(json.dumps(dict(mode=s.mode, **r)) + "\n")
        if views and t >= next_draw:
            next_draw = t + 1 / 30
            panels = []
            for m, s in sessions.items():
                fr_cache = {}

                def at(k, s=s):
                    if k not in fr_cache:
                        fr = s.frames.get(k)
                        if fr is None:
                            fr = s.frames[max(s.frames)] if s.frames else np.zeros((42, 96), np.uint8)
                        fr_cache[k] = to_lin(s.model.cfg.palette()[fr])
                    return fr_cache[k]
                pan = views[m].render(exposure(at, t - 1 / 30, 1 / 30))
                pan = np.ascontiguousarray(pan[:, :, ::-1])
                cv2.putText(pan, f"mode: {'one word at a time' if m == 'word' else 'scrolling ticker'}", (10, 22),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1, cv2.LINE_AA)
                for i, ln in enumerate(overlay_lines(s)):
                    cv2.putText(pan, ln, (10, 400 + 18 * i), cv2.FONT_HERSHEY_PLAIN, 1.0, (120, 220, 120), 1, cv2.LINE_AA)
                if s.dropped():
                    cv2.putText(pan, f"dropped {s.dropped()}", (440, 22), cv2.FONT_HERSHEY_PLAIN, 1.0, (80, 80, 230), 1)
                panels.append(pan)
            img = np.hstack(panels)
            bar = np.zeros((60, img.shape[1], 3), np.uint8)
            line = " ".join(transcript[-12:])
            cv2.putText(bar, line[-110:], (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (230, 230, 230), 1, cv2.LINE_AA)
            cv2.putText(bar, partial[-60:], (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (120, 120, 120), 1, cv2.LINE_AA)
            img = np.vstack([img, bar])
            cv2.imshow(TITLE, img)
            k = cv2.waitKey(1) & 0xFF
            if k in (ord("q"), 27):
                break
        else:
            time.sleep(0.004)
        if (a.seconds and t > a.seconds) or (stop.is_set() and res.empty() and t > (src.audio.size / SR + 2.5 if a.file else 1e9)):
            break
    stop.set()
    src.stop()
    if a.snapshot and img is not None:
        cv2.imwrite(a.snapshot, img)
    if sink:
        print("transport:", sink.stats())
        sink.close()
    log.close()
    for m, s in sessions.items():
        recs = [r for r in s.records.values() if "shown" in r and r.get("end") is not None]
        if recs:
            tot = np.array([r["shown"] - r["end"] for r in recs])
            asr_l = np.array([r["emit"] - r["end"] for r in recs])
            print(f"{m}: {len(recs)} words, speech->column median {1000 * np.median(tot):.0f} ms "
                  f"(ASR {1000 * np.median(asr_l):.0f} ms), p90 {1000 * np.percentile(tot, 90):.0f} ms, dropped {s.dropped()}")
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
