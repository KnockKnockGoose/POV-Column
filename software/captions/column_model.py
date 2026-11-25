"""Reference model of the ESP32 caption mode: what the column draws for each caption message, tick by tick.

The firmware's procedural caption mode (software/firmware/src/captions.h) is a port of this file; the simulator, the PC
frame-streaming fallback and the tests all use this code, so what Brian previews is what the rotor will draw.

Time base: the refresh tick, one eighth of a revolution (1/30 s at 225 rpm). Messages that arrive between ticks take
effect at the next tick, which is when the firmware swaps its frame buffer (all 24 strips change together).

Messages (JSON over the column's WebSocket; see transport.py):
    {"cap":"mode","m":"word"|"tick"}                  switch mode (clears)
    {"cap":"word","w":"HELLO"}                        word mode: show this word (auto font, centred in the window)
    {"cap":"word","w":"HEL","dim":1}                  ... an unstable partial, drawn dim (optional feature)
    {"cap":"tick","append":"HELLO "}                  ticker: append text to the marquee
    {"cap":"tick","partial":"WOR"}                    ticker: dim, uncommitted tail (optional; "" removes it)
    {"cap":"clear"}                                   blank (word mode after ~2 s of silence)
    {"cap":"cfg","rgb":[255,214,160],"dim":0.3,...}   colour and tuning (keys of Config)
Index frame: 0 = off, 1 = caption colour, 2 = dim colour.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass

import numpy as np

from font import rasterize, text_width

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "povgen"))
from povanim import I_DARK_MA, I_ESP_MA, N_STRIPS, LEDS_PER_STRIP, current_profile  # noqa: E402

ROWS, COLS = 42, 96
WIN_C, WIN_W = 48, 32                      # the viewer's window: columns 32..63 (centre 48), as in povanim
WIN_L, WIN_R = WIN_C - WIN_W // 2, WIN_C + WIN_W // 2 - 1
TICK_HZ = 30.0                             # refresh ticks per second at 225 rpm (8 strips per row x 3.75 rev/s)


@dataclass
class Config:
    rgb: tuple = (255, 214, 160)           # warm white reads well on camera; any colour works
    dim: float = 0.30                      # brightness of partial (unstable) text
    word_vs: int = 2                       # vertical scale of word-mode text (7x9 -> 18 rows tall)
    tick_vs: int = 2                       # vertical scale of the ticker (5x7 -> 14 rows)
    tick_font: str = "5x7"
    # Camera legibility rule (2026-11-02 simulator finding): a 1/30 s exposure captures each column at a different
    # instant within the exposure, so text moving v col/s is torn by ~v/30 columns at the 8 sector boundaries. Smooth
    # motion reads only at <= 1 column per tick; faster motion must be discrete jumps (one torn frame per jump).
    # word mode, long words: fast mini-scroll through the window
    scroll_style: str = "jump"             # "jump": one character every scroll_jump_ticks; "smooth": scroll_cpt per tick
    scroll_jump_cols: int = 6              # one 5x7 character
    scroll_jump_ticks: int = 3             # 60 col/s on average, 2 of 3 camera frames crisp
    scroll_cpt: int = 4                    # smooth style: columns per tick (120 col/s, torn on camera)
    scroll_pause: int = 4                  # ticks to hold the start before scrolling (and the end after)
    # ticker
    tick_style: str = "hybrid"             # "hybrid": still while talking, each word jumps in; "crawl": smooth
    crawl_cpt: int = 1                     # hybrid: drift speed once idle (columns per tick, 30 col/s at 225 rpm)
    crawl_idle_s: float = 1.5              # hybrid: start drifting the text away after this long without a word
    # crawl style: deadline-driven speed controller (columns per second)
    v_min: float = 40.0                    # crawl speed with nothing waiting (the text drifts on and out)
    v_max: float = 110.0                   # legibility limit; 150 wpm needs ~85 col/s in 5x7
    target_lag: float = 1.0                # aim: every word fully in the window within 1.0 s of arriving
    max_behind: float = 1.5                # hard limit: if v_max cannot make it, drop the oldest waiting words
    # current limiter (captions are live, so the per-animation cap of .pova playback does not apply)
    cap_ma: float = 2000.0                 # LEDs incl. idle current + ESP32, as povanim.current_profile counts it
    gb_max: int = 31                       # 5-bit SK9822 current field requested by the user
    gb_release_ticks: int = 3              # raise gb by 1 every 3 ticks after a dense frame (no pumping)

    def palette(self) -> np.ndarray:
        on = np.array(self.rgb, float)
        return np.array([[0, 0, 0], on, on * self.dim], dtype=np.uint8)


def layout_word(word: str, window: int = WIN_W) -> tuple[str, int, bool]:
    """Auto font: 7x9 if the word fits the window, else 5x7, else 5x7 with a mini-scroll. -> (font, width, scroll)."""
    for f in ("7x9", "5x7"):
        w = text_width(word, f)
        if w <= window:
            return f, w, False
    return "5x7", text_width(word, "5x7"), True


def scroll_ticks(word: str, cfg: Config = Config(), window: int = WIN_W) -> int:
    """How long a word takes on screen before it has been fully read (0 for words that fit)."""
    f, w, scroll = layout_word(word, window)
    if not scroll:
        return 0
    if cfg.scroll_style == "jump":
        return cfg.scroll_pause + -(-(w - window) // cfg.scroll_jump_cols) * cfg.scroll_jump_ticks + cfg.scroll_pause
    return cfg.scroll_pause + -(-(w - window) // cfg.scroll_cpt) + cfg.scroll_pause


def scroll_offset(word_ticks: int, overflow: int, cfg: Config) -> int:
    """Columns the long word has scrolled after word_ticks ticks on screen (0 .. overflow)."""
    k = max(0, word_ticks - cfg.scroll_pause)
    if cfg.scroll_style == "jump":
        return min(overflow, (k // cfg.scroll_jump_ticks) * cfg.scroll_jump_cols)
    return min(overflow, k * cfg.scroll_cpt)


def _blit(frame: np.ndarray, bm: np.ndarray, col0: int, vs: int, ci: int, clip=(0, COLS), wrap=False) -> None:
    """Draw a (h, W) bitmap (top row first) with its left edge at column col0, vertically centred, scaled vs."""
    h, W = bm.shape
    base = (ROWS - h * vs) // 2
    for x in range(W):
        c = col0 + x
        if wrap:
            c %= COLS
        elif not clip[0] <= c < clip[1]:
            continue
        colbits = bm[:, x]
        if not colbits.any():
            continue
        for i in np.nonzero(colbits)[0]:
            r = base + (h - 1 - i) * vs
            frame[r:r + vs, c] = ci


@dataclass
class TapeWord:
    text: str
    start: int            # tape column of its first column
    width: int
    t_append: float       # tick time it was appended
    t_entered: float | None = None   # tick time its last column entered the window (fully shown)
    mid: int | None = None           # id of the message that appended it


class ColumnCaptions:
    def __init__(self, cfg: Config | None = None, mode: str = "word"):
        self.cfg = cfg or Config()
        self.mode = mode
        self.t = 0.0                    # time of the current tick (s)
        self.pending: list[dict] = []   # messages received since the last tick
        self.log: list[dict] = []       # what was shown when (for latency measurement and tests)
        self.gb = self.cfg.gb_max       # current field actually used (current limiter)
        self.peak_ma = 0.0              # instantaneous peak of the last frame at self.gb
        self._rel = 0
        self._clear()

    def _clear(self):
        self.word, self.word_dim, self.word_t, self.word_scroll_x = "", False, 0.0, 0
        self.word_tick0 = 0
        self.tape: list[TapeWord] = []
        self.tape_end = 0               # next free tape column
        self.x = 0.0                    # tape column that is at the window's right edge now
        self.v = 0.0
        self.last_append = -1e9
        self.partial = ""
        self.dropped = 0

    # ------------------------------------------------------------ messages
    def receive(self, msg: dict) -> None:
        self.pending.append(msg)

    def _apply(self, m: dict) -> None:
        cap = m.get("cap")
        if cap == "mode":
            self.mode = m.get("m", "word")
            self._clear()
        elif cap == "clear":
            self._clear()
        elif cap == "cfg":
            for k, v in m.items():
                if k != "cap" and hasattr(self.cfg, k):
                    setattr(self.cfg, k, tuple(v) if isinstance(v, list) else v)
        elif cap == "word":
            self.word, self.word_dim = m.get("w", ""), bool(m.get("dim", 0))
            self.word_t, self.word_scroll_x, self.word_tick0 = self.t, 0, 0
            if not self.word_dim and self.word:
                self.log.append(dict(ev="word", w=self.word, t=self.t, id=m.get("id")))
        elif cap == "tick":
            if "append" in m:
                self._append(m["append"], m.get("id"))
            if "partial" in m:
                self.partial = m["partial"]

    def _sep(self) -> int:
        """Columns between ticker words: a space glyph plus its gap."""
        return text_width(" ", self.cfg.tick_font) + 1

    def _append(self, text: str, mid=None) -> None:
        f, sw = self.cfg.tick_font, self._sep()
        for w in text.split():
            width = text_width(w, f)
            start = self.tape_end
            if start < self.x:                       # the tape ran dry: start entering right now
                start = int(np.ceil(self.x))
            self.tape.append(TapeWord(w, start, width, self.t, mid=mid))
            self.last_append = self.t
            self.tape_end = start + width + sw
            self.log.append(dict(ev="append", w=w, t=self.t, id=mid))

    # ------------------------------------------------------------ one refresh tick
    def tick(self, t: float) -> np.ndarray:
        """Advance to tick time t, apply pending messages, return the (42, 96) index frame for this tick."""
        dt = t - self.t if t > self.t else 1.0 / TICK_HZ
        self.t = t
        msgs, self.pending = self.pending, []
        for m in msgs:
            self._apply(m)
        if self.mode == "tick":
            self._ticker_step(dt)
        else:
            self.word_tick0 += 1
        fr = self.frame()
        self._limit(fr)
        return fr

    def _limit(self, fr: np.ndarray) -> None:
        """Current limiter: the largest gb (<= gb_max) whose worst rotor position stays under cap_ma; drop at once,
        recover one step every gb_release_ticks. Same model as povanim.current_profile (20 mA/channel, gamma 2.2)."""
        c = self.cfg
        fixed = N_STRIPS * LEDS_PER_STRIP * I_DARK_MA + I_ESP_MA
        led = current_profile(fr, c.palette(), gb=31).max() - fixed       # LED drive current at full field
        fit = c.gb_max if led <= 0 else int(min(c.gb_max, 31 * (c.cap_ma - fixed) / led))
        fit = max(1, fit)
        if fit < self.gb:
            self.gb, self._rel = fit, 0
        elif fit > self.gb:
            self._rel += 1
            if self._rel >= c.gb_release_ticks:
                self.gb, self._rel = self.gb + 1, 0
        self.peak_ma = fixed + led * self.gb / 31

    def _need(self, waiting, lag: float, dt: float) -> float:
        """Speed (col/s) that gets every waiting word fully into the window within `lag` s of its arrival."""
        return max((w.start + w.width - self.x) / max(w.t_append + lag - self.t + dt, dt) for w in waiting)

    def _ticker_step(self, dt: float) -> None:
        """Deadline controller: v = the speed the most urgent waiting word needs (v_min..v_max). If even v_max cannot
        meet the hard limit (max_behind), drop the oldest word that has not started to enter and close the gap."""
        c = self.cfg
        waiting = [w for w in self.tape if w.t_entered is None]
        if c.tick_style == "hybrid":
            # On camera any motion tears the text, so: hold still while words arrive, and when one arrives jump the
            # tape so it is fully in the window at this tick (older words shift left, around the drum). Only after
            # crawl_idle_s without a new word does the text drift away at crawl_cpt columns per tick.
            step = 0
            if waiting:
                target = waiting[-1].start + waiting[-1].width
                step = max(0, int(np.ceil(target - self.x)))
                self.log.append(dict(ev="jump", cols=step, t=self.t))
            elif self.tape and self.t - self.last_append >= c.crawl_idle_s:
                step = c.crawl_cpt
            self.v = step / dt if dt > 0 else 0.0
            self.x += step
            self._entered()
            return
        while waiting and self._need(waiting, c.max_behind, dt) > c.v_max:
            cand = [w for w in waiting if w.start >= self.x and w is not waiting[-1]]
            if not cand:
                break
            d = cand[0]
            gap = d.width + self._sep()
            for w in self.tape:                      # later words move up into its place
                if w.start > d.start:
                    w.start -= gap
            self.tape.remove(d)
            waiting.remove(d)
            self.tape_end -= gap
            self.dropped += 1
            self.log.append(dict(ev="drop", w=d.text, t=self.t))
        if waiting:
            self.v = min(c.v_max, max(c.v_min, self._need(waiting, c.target_lag, dt)))
        else:
            self.v = c.v_min if self.tape else 0.0
        self.x += self.v * dt
        self._entered()

    def _entered(self) -> None:
        for w in self.tape:
            if w.t_entered is None and self.x >= w.start + w.width:
                w.t_entered = self.t
                self.log.append(dict(ev="entered", w=w.text, t=self.t, lag=self.t - w.t_append, id=w.mid))
        # forget words that have gone all the way round (keep memory bounded, like the ring buffer on the ESP32)
        self.tape = [w for w in self.tape if self.x - (w.start + w.width) < 64]

    # ------------------------------------------------------------ drawing
    def frame(self) -> np.ndarray:
        fr = np.zeros((ROWS, COLS), np.uint8)
        c = self.cfg
        if self.mode == "word" and self.word:
            f, w, scroll = layout_word(self.word)
            bm = rasterize(self.word, f)
            ci = 2 if self.word_dim else 1
            if not scroll:
                _blit(fr, bm, WIN_C - w // 2, c.word_vs, ci)
            else:
                off = scroll_offset(self.word_tick0, w - WIN_W, c)
                _blit(fr, bm, WIN_L - off, c.word_vs, ci, clip=(WIN_L - 8, WIN_R + 9))
        elif self.mode == "tick":
            for tw in self.tape:                             # column of its first glyph column right now
                self._tape_blit(fr, rasterize(tw.text, c.tick_font), int(np.floor(WIN_R - (self.x - tw.start))), 1)
            if self.partial:
                col0 = int(np.floor(WIN_R - (self.x - max(self.tape_end, np.ceil(self.x)))))
                self._tape_blit(fr, rasterize(self.partial, c.tick_font), col0, 2)
        return fr

    def _tape_blit(self, fr, bm, col0, ci):
        """Ticker columns live on the whole drum: d = travel past the right window edge in [-32, 64)."""
        h, W = bm.shape
        base = (ROWS - h * self.cfg.tick_vs) // 2
        for x in range(W):
            s = col0 + x
            d = WIN_R - s
            if not -32 <= d < 64:
                continue
            col = bm[:, x]
            for i in np.nonzero(col)[0]:
                r = base + (h - 1 - i) * self.cfg.tick_vs
                fr[r:r + self.cfg.tick_vs, s % COLS] = ci

    def rgb(self, fr: np.ndarray | None = None) -> np.ndarray:
        fr = self.frame() if fr is None else fr
        return self.cfg.palette()[fr]
