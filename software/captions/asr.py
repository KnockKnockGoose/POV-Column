"""Streaming speech recognisers behind one small interface, for live captions on the POV column.

Every engine takes 16 kHz mono float32 audio through `accept()` and, on `poll()`, returns the words that have become
STABLE since the last poll (they will never be revised) plus the current unstable tail (`partial`). The caption engine
shows stable words only by default; the partial can be drawn dimmer as an option.

Engines
  * SherpaTransducer: sherpa-onnx streaming transducers (kroko Zipformer, NeMo FastConformer, Nemotron). Greedy
    transducer decoding is append-only: tokens are never revised, so a word is stable as soon as the next word starts
    (a token with a leading space), at an endpoint, or after `tail_hold` s of decoded audio with no new token.
  * WhisperLA: faster-whisper re-transcribing a growing buffer, committing words with the LocalAgreement-2 policy
    (a word is stable when two consecutive hypotheses agree on it; Machacek, Dabre & Bojar 2023, "Turning Whisper into
    Real-Time Transcription System", the whisper_streaming design). Written from the paper's description.

Models live in %LOCALAPPDATA%/POVColumn/captions/models (see paths.py); `ENGINES` names the presets.
"""
from __future__ import annotations

import glob
import os
import re
import time
from dataclasses import dataclass, field

import numpy as np

from paths import MODELS_DIR

SR = 16000


# ---------------------------------------------------------------- common
@dataclass
class Poll:
    stable: list[str] = field(default_factory=list)   # newly stable words, in order
    stable_t: list[float] = field(default_factory=list)  # engine's estimate of each word's end (audio s)
    partial: str = ""                                  # unstable tail (may change or vanish)
    endpoint: bool = False                             # the engine detected the end of an utterance


class StreamingASR:
    name = "base"
    step_s = 0.1          # how often the harness should poll (seconds of new audio)

    def accept(self, audio: np.ndarray) -> None:
        raise NotImplementedError

    def poll(self) -> Poll:
        raise NotImplementedError

    def finish(self) -> Poll:
        """End of input: flush everything as stable."""
        raise NotImplementedError

    def reset(self) -> None:
        raise NotImplementedError


# ---------------------------------------------------------------- sherpa-onnx streaming transducers
class SherpaTransducer(StreamingASR):
    step_s = 0.1

    def __init__(self, model_dir: str, name: str, threads: int = 1, tail_hold: float = 0.35,
                 idle_reset: float = 4.0):
        import sherpa_onnx
        f = lambda p: sorted(glob.glob(os.path.join(model_dir, p)))[0]
        self.name, self.tail_hold, self.idle_reset = name, tail_hold, idle_reset
        # No endpoint-driven resets: on 2026-11-02 a reset after 0.6 s of silence lost the first word of the next
        # utterance on every model (Nemotron: 63 deletions in 301 words). The stream is only recreated after
        # idle_reset s without a token (nothing in flight) once its history is long.
        self.rec = sherpa_onnx.OnlineRecognizer.from_transducer(
            tokens=f("tokens.txt"), encoder=f("encoder*.onnx"), decoder=f("decoder*.onnx"), joiner=f("joiner*.onnx"),
            num_threads=threads, decoding_method="greedy_search", enable_endpoint_detection=False)
        self.reset()

    def reset(self):
        self.s = self.rec.create_stream()
        self.t0 = 0.0                # audio time at which this stream started
        self.ts = []
        self.n_emitted = 0           # words of the current utterance already emitted as stable
        self.last_ntok = 0
        self.fed = 0.0               # seconds of audio accepted in this utterance
        self.dec_t = 0.0             # audio time up to which the decoder has run (advances only when it decodes)
        self.last_change = 0.0       # decoded-audio time of the last token change
        self.early = False           # the last emitted word was committed by the tail timer
        self.early_word = ""
        if not hasattr(self, "late_extensions"):
            self.late_extensions = 0  # a word grew after an early commit (counted across utterances, not shown)

    def accept(self, audio):
        self.s.accept_waveform(SR, audio)
        self.fed += len(audio) / SR

    def _decode(self):
        ran = False
        while self.rec.is_ready(self.s):
            self.rec.decode_stream(self.s)
            ran = True
        if ran:
            self.dec_t = self.fed

    def _words(self):
        r = self.rec.get_result_all(self.s)
        toks = list(r.tokens)
        if len(toks) != self.last_ntok:
            self.last_ntok, self.last_change = len(toks), self.dec_t
        self.ts = list(r.timestamps)
        return "".join(toks).split(), toks

    def _word_ends(self, toks):
        """End time (audio s, this utterance's clock + offset) of each word: its last token's time + one frame."""
        ends, cur = [], None
        for tok, t in zip(toks, self.ts):
            if tok.startswith(" ") and tok.strip():
                if cur is not None:
                    ends.append(cur)
                cur = t
            elif tok.strip():
                cur = t if cur is None else t
        if cur is not None:
            ends.append(cur)
        return [self.t0 + e + 0.08 for e in ends]

    def poll(self) -> Poll:
        self._decode()
        words, toks = self._words()
        out = Poll()
        # complete words: all but the last (a later token with a leading space started a new word)
        n_done = max(0, len(words) - 1)
        if words and self.dec_t - self.last_change >= self.tail_hold:
            n_done = len(words)                         # decoder ran tail_hold s further, no new token: finished
        if self.early and self.n_emitted and len(words) >= self.n_emitted and \
                words[self.n_emitted - 1] != self.early_word:
            # the word committed by the tail timer grew afterwards ("comp" -> "computer"); it is not re-shown
            self.late_extensions += 1
            self.early = False
        if n_done > self.n_emitted:
            out.stable = words[self.n_emitted:n_done]
            out.stable_t = self._word_ends(toks)[self.n_emitted:n_done]
            self.early = n_done == len(words)
            self.early_word = words[n_done - 1]
            self.n_emitted = n_done
        out.partial = " ".join(words[self.n_emitted:])
        if self.n_emitted == len(words) and self.last_ntok > 400 and self.dec_t - self.last_change > self.idle_reset:
            t0 = self.t0 + self.fed                      # long idle with a long history: start a fresh stream
            self.reset()
            self.t0 = t0
            out.endpoint = True
        return out

    def finish(self) -> Poll:
        tail = np.zeros(int(0.8 * SR), np.float32)        # flush the encoder's right context
        self.s.accept_waveform(SR, tail)
        self.s.input_finished()
        self._decode()
        words, toks = self._words()
        out = Poll(stable=words[self.n_emitted:], stable_t=self._word_ends(toks)[self.n_emitted:], endpoint=True)
        self.reset()
        return out


# ---------------------------------------------------------------- faster-whisper + LocalAgreement-2
class WhisperLA(StreamingASR):
    def __init__(self, model: str = "base.en", threads: int = 2, step_s: float = 0.5, beam: int = 1,
                 trim_s: float = 12.0, compute_type: str = "int8", hot_words: str = ""):
        from faster_whisper import WhisperModel
        self.name = f"whisper-{model}"
        self.model = WhisperModel(model, device="cpu", compute_type=compute_type, cpu_threads=threads)
        self.step_s, self.beam, self.trim_s, self.hot = step_s, beam, trim_s, hot_words
        self.reset()

    def reset(self):
        self.audio = np.zeros(0, np.float32)
        self.offset = 0.0                    # audio time of self.audio[0]
        self.committed: list[tuple[float, float, str]] = []   # all committed words (t0, t1, w)
        self.prev: list[tuple[float, float, str]] = []         # previous hypothesis, uncommitted part
        self.last_t = 0.0                    # end time of the last committed word

    def accept(self, audio):
        self.audio = np.concatenate([self.audio, audio.astype(np.float32)])

    def _transcribe(self):
        # prompt = committed text that is no longer in the buffer (words inside it are being re-transcribed)
        prompt_words = [w for _, t1, w in self.committed if t1 <= self.offset][-40:]
        prompt = (self.hot + " " + " ".join(prompt_words)).strip()
        segs, _ = self.model.transcribe(self.audio, language="en", beam_size=self.beam, word_timestamps=True,
                                        vad_filter=True, condition_on_previous_text=False,
                                        initial_prompt=prompt or None)
        return [(self.offset + w.start, self.offset + w.end, w.word.strip()) for s in segs for w in (s.words or [])]

    @staticmethod
    def _norm(w):
        return re.sub(r"[^\w']", "", w.lower())

    def _new_part(self, hyp):
        """Drop words of `hyp` that are already committed (by time, then by an n-gram overlap with the tail)."""
        new = [h for h in hyp if h[0] > self.last_t - 0.1]
        if new and self.committed and abs(new[0][0] - self.last_t) < 1.0:
            for n in range(min(5, len(self.committed), len(new)), 0, -1):
                tail = [self._norm(w) for _, _, w in self.committed[-n:]]
                head = [self._norm(w) for _, _, w in new[:n]]
                if tail == head:
                    new = new[n:]
                    break
        return new

    def poll(self) -> Poll:
        if len(self.audio) < 0.3 * SR:
            return Poll()
        hyp = self._new_part(self._transcribe())
        # LocalAgreement-2: commit the longest common prefix of this and the previous hypothesis
        n = 0
        while n < len(hyp) and n < len(self.prev) and self._norm(hyp[n][2]) == self._norm(self.prev[n][2]):
            n += 1
        commit = hyp[:n]
        self.prev = hyp[n:]
        if commit:
            self.committed += commit
            self.last_t = commit[-1][1]
        self._trim()
        return Poll(stable=[w for _, _, w in commit], stable_t=[b for _, b, _ in commit],
                    partial=" ".join(w for _, _, w in self.prev))

    def _trim(self):
        """Keep the buffer short: cut at the end of the last committed word once it exceeds trim_s."""
        dur = len(self.audio) / SR
        if dur > self.trim_s and self.committed:
            cut = self.last_t - self.offset
            if cut > 1.0:
                k = int(cut * SR)
                self.audio = self.audio[k:]
                self.offset += k / SR
        if dur > 2 * self.trim_s:          # no commits for a long time (noise): hard cut
            k = len(self.audio) - int(self.trim_s * SR)
            self.audio = self.audio[k:]
            self.offset += k / SR

    def finish(self) -> Poll:
        hyp = self._new_part(self._transcribe()) if len(self.audio) > 0.3 * SR else []
        out = Poll(stable=[w for _, _, w in hyp], stable_t=[b for _, b, _ in hyp], endpoint=True)
        self.reset()
        return out


# ---------------------------------------------------------------- presets
def _sherpa(dirpart):
    hits = sorted(glob.glob(os.path.join(MODELS_DIR, f"*{dirpart}*")))
    if not hits:
        raise FileNotFoundError(f"model '*{dirpart}*' not in {MODELS_DIR}: see captions/README.md 'Models'")
    return hits[0]


ENGINES = {
    # name: (factory, description)
    "kroko": (lambda **k: SherpaTransducer(_sherpa("zipformer-en-kroko"), "kroko-zipformer", **k),
              "sherpa-onnx streaming Zipformer EN (Banafo Kroko 2025-08-06), 70 MB, cased + punctuation"),
    "fastconformer": (lambda **k: SherpaTransducer(_sherpa("fast-conformer-transducer-en-80ms"), "nemo-fastconformer-80ms",
                                                   **{"tail_hold": 0.25, **k}),
                      "sherpa-onnx NeMo FastConformer streaming transducer EN, 80 ms chunks, int8, lowercase"),
    "nemotron": (lambda **k: SherpaTransducer(_sherpa("nemotron-3.5-asr-streaming-0.6b-160ms"), "nemotron-3.5-0.6b-160ms", **k),
                 "sherpa-onnx NVIDIA Nemotron-3.5 ASR streaming 0.6B, 160 ms chunks, int8, cased + punctuation"),
    "whisper-base": (lambda **k: WhisperLA("base.en", **k), "faster-whisper base.en int8 + LocalAgreement-2"),
    "whisper-small": (lambda **k: WhisperLA("small.en", **k), "faster-whisper small.en int8 + LocalAgreement-2"),
    "whisper-distil": (lambda **k: WhisperLA("distil-small.en", **k), "faster-whisper distil-small.en int8 + LocalAgreement-2"),
}
DEFAULT_ENGINE = "fastconformer"   # chosen 2026-11-02: lowest latency at ~0.2 cores (bench/results.json)


def make(name: str = DEFAULT_ENGINE, **kw) -> StreamingASR:
    return ENGINES[name][0](**kw)
