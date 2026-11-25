"""Cut benchmark clips (16 kHz mono WAV) and build word-timed reference transcripts.

Audio and transcripts are personal data: they live in %LOCALAPPDATA%/POVColumn/captions/clips and are never committed.

    py software/captions/bench/make_clips.py --manifest %LOCALAPPDATA%/POVColumn/captions/clips/manifest.json

manifest.json: {"clips": [{"name": "take1", "src": "D:/.../C0038_clean_mono.wav", "start": 120, "dur": 40}, ...]}
Reference = faster-whisper large-v3 (int8, beam 5, word timestamps, no VAD) on the clip: a pseudo-reference, good to
about +-100 ms per word (knowledge base). Each clip gets <name>.wav and <name>.ref.json {text, words: [[w, t0, t1], ...]}.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import wave

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from paths import CLIPS_DIR  # noqa: E402


def cut(src: str, start: float, dur: float, dst: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(start), "-t", str(dur), "-i", src,
                    "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", dst], check=True)


def read_wav(path: str) -> np.ndarray:
    with wave.open(path, "rb") as w:
        assert w.getframerate() == 16000 and w.getnchannels() == 1
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0


def reference(model, audio: np.ndarray) -> dict:
    segs, _ = model.transcribe(audio, language="en", beam_size=5, word_timestamps=True, vad_filter=False,
                               condition_on_previous_text=True)
    words = []
    for s in segs:
        for w in s.words or []:
            words.append([w.word.strip(), round(w.start, 3), round(w.end, 3)])
    return {"text": " ".join(w[0] for w in words), "words": words, "model": "large-v3 int8 beam5"}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=os.path.join(CLIPS_DIR, "manifest.json"))
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    man = json.load(open(a.manifest, encoding="utf-8"))
    from faster_whisper import WhisperModel
    model = WhisperModel("large-v3", device="cpu", compute_type="int8", cpu_threads=8)
    for c in man["clips"]:
        wav = os.path.join(CLIPS_DIR, c["name"] + ".wav")
        ref = os.path.join(CLIPS_DIR, c["name"] + ".ref.json")
        if a.force or not os.path.exists(wav):
            cut(c["src"], c["start"], c["dur"], wav)
        if a.force or not os.path.exists(ref):
            r = reference(model, read_wav(wav))
            json.dump(r, open(ref, "w", encoding="utf-8"), indent=1)
        r = json.load(open(ref, encoding="utf-8"))
        n = len(r["words"])
        print(f"{c['name']}: {c['dur']} s, {n} words, {60 * n / c['dur']:.0f} wpm")


if __name__ == "__main__":
    main()
