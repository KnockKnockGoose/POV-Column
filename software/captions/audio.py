"""Audio input for live captions: the microphone (sounddevice) or a WAV file paced in real time.

Device handling follows Brain-Dump-Button/ptt/ptt.py (the F9 service): pick an input by a substring of its name,
prefer the MME host API (it resamples for us), capture at the device's native rate and resample to 16 kHz, and
re-scan the device list once if PortAudio fails to open (indices shift after a reboot or a USB re-plug).
Unlike the F9 service this streams: 20 ms blocks go into a queue the recogniser drains continuously.
"""
from __future__ import annotations

import queue
import threading
import time
import wave

import numpy as np

SR = 16000
BLOCK_S = 0.02


def resample(x: np.ndarray, src: int, dst: int = SR) -> np.ndarray:
    if src == dst or len(x) == 0:
        return x.astype(np.float32)
    n = int(round(len(x) * dst / src))
    return np.interp(np.linspace(0, len(x), n, endpoint=False), np.arange(len(x)), x).astype(np.float32)


def pick_device(name_part: str | None):
    import sounddevice as sd
    if not name_part:
        return None
    devices, apis, best = sd.query_devices(), sd.query_hostapis(), None
    for i, d in enumerate(devices):
        if d["max_input_channels"] <= 0 or name_part.lower() not in d["name"].lower():
            continue
        api = apis[d["hostapi"]]["name"]
        score = 2 if "MME" in api else 1 if "WASAPI" in api else 0
        if best is None or score > best[0]:
            best = (score, i)
    return best[1] if best else None


class MicSource:
    """Blocks of 16 kHz float32 audio in .q; .t0 = wall time (perf_counter) of audio sample 0."""

    def __init__(self, device: str | None = None):
        import sounddevice as sd
        self.sd, self.name_part = sd, device
        self.q: queue.Queue = queue.Queue()
        self.t0 = None
        self.n = 0

    def start(self):
        sd = self.sd
        try:
            self._open()
        except sd.PortAudioError:
            sd._terminate()
            sd._initialize()
            self._open()

    def _open(self):
        sd = self.sd
        dev = pick_device(self.name_part)
        self.rate = int(sd.query_devices(dev, "input")["default_samplerate"])
        self.dev_name = sd.query_devices(dev, "input")["name"]

        def cb(indata, frames, t, status):
            x = resample(indata[:, 0].copy(), self.rate)
            if self.t0 is None:
                self.t0 = time.perf_counter() - len(x) / SR
            self.q.put(x)

        self.stream = sd.InputStream(samplerate=self.rate, channels=1, dtype="float32", device=dev,
                                     blocksize=int(self.rate * BLOCK_S), latency="low", callback=cb)
        self.stream.start()

    def stop(self):
        self.stream.stop()
        self.stream.close()


class FileSource:
    """A 16 kHz mono WAV delivered in 20 ms blocks at real-time pace (to test the live path without talking)."""

    def __init__(self, path: str, speed: float = 1.0):
        with wave.open(path, "rb") as w:
            assert w.getframerate() == SR and w.getnchannels() == 1, "convert to 16 kHz mono first"
            self.audio = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768.0
        self.q: queue.Queue = queue.Queue()
        self.speed, self.t0, self.dev_name, self.done = speed, None, path, False

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        blk = int(SR * BLOCK_S)
        self.t0 = time.perf_counter()
        for k in range(0, len(self.audio), blk):
            due = self.t0 + (k + blk) / SR / self.speed
            time.sleep(max(0.0, due - time.perf_counter()))
            self.q.put(self.audio[k:k + blk])
        self.done = True

    def stop(self):
        pass
