"""One caption session on an explicit clock: ASR output -> driver -> (link delay) -> column model ticks.

Used by live.py (clock = wall time) and render_clip.py (clock = simulated audio time), so the live preview and the
offline MP4 run exactly the same logic. Every word gets a latency record:

    end      the word's end in the audio (engine estimate live; reference word time offline)
    emit     the recogniser returned it as stable                -> ASR term
    out      the driver sent it (word mode may pace bursts)      -> queue term
    arrive   it reached the column (out + link delay)            -> link term (estimate until the hardware exists)
    shown    the tick at which it was drawn (word mode) or fully crawled into the window (ticker)
    camera   start of the first 30p/(1/30 s) camera frame that shows it completely (if a camera phase is given)
"""
from __future__ import annotations

import math

from column_model import TICK_HZ, ColumnCaptions, Config
from engine import CaptionDriver


class Session:
    def __init__(self, mode: str, partial: bool = False, link_s: float = 0.015, tick_phase: float = 0.0,
                 cam_phase: float | None = None, cfg: Config | None = None, sink=None):
        self.mode, self.link_s, self.tick_phase, self.cam_phase = mode, link_s, tick_phase, cam_phase
        self.drv = CaptionDriver(mode, partial=partial, cfg=cfg)
        self.model = ColumnCaptions(cfg=cfg, mode=mode)
        self.sink = sink                     # optional real transport: gets every message as it is sent
        self.link: list[tuple[float, dict]] = []
        self.k = -1                          # last tick index processed
        self.frames: dict[int, object] = {}  # tick -> index frame (recent ones only)
        self.records: dict[int, dict] = {}   # msg id -> latency record (word mode); for ticker, one per word
        self._log_pos = 0
        for m in self.drv.start_msgs():
            self.model.receive(m)
            if sink:
                sink.send(m)

    def on_asr(self, stable, partial, t, ends=None):
        meta = [dict(end=e, emit=t) for e in (ends or [None] * len(stable))]
        self.drv.on_asr(stable, partial, t, meta)

    def advance(self, t: float) -> list[int]:
        """Run the driver and the column up to time t. Returns the new tick indices (frames in self.frames)."""
        for m in self.drv.update(t):
            self.link.append((t + self.link_s, m))
            if self.sink:
                self.sink.send(m)
        new = []
        k_now = math.floor((t - self.tick_phase) * TICK_HZ)
        while self.k < k_now:
            self.k += 1
            tk = self.k / TICK_HZ + self.tick_phase
            due = [m for ta, m in self.link if ta <= tk]
            self.link = [(ta, m) for ta, m in self.link if ta > tk]
            for m in due:
                self.model.receive(m)
                if m.get("cap") in ("word", "tick") and not m.get("dim") and "partial" not in m:
                    for h in self.drv.history[-80:]:
                        if h.get("id") == m["id"]:
                            rec = self.records.setdefault((m["id"], h["w"]), dict(w=h["w"], **(h["meta"] or {})))
                            rec.update(out=h["t_out"], arrive=h["t_out"] + self.link_s)
            self.frames[self.k] = self.model.tick(tk)
            self.frames.pop(self.k - 120, None)
            self._scan_log()
            new.append(self.k)
        return new

    def _scan_log(self):
        for ev in self.model.log[self._log_pos:]:
            kind = "word" if self.mode == "word" else "entered"
            if ev["ev"] == kind:
                rec = self.records.get((ev.get("id"), ev["w"]))
                if rec is not None and "shown" not in rec:
                    rec["shown"] = ev["t"]
                    if self.cam_phase is not None:
                        rec["camera"] = math.ceil((ev["t"] - self.cam_phase) * 30 - 1e-9) / 30 + self.cam_phase
        self._log_pos = len(self.model.log)

    def dropped(self) -> int:
        return self.drv.dropped + self.model.dropped
