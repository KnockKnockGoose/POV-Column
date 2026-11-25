"""PC-side caption driver: turns ASR output (stable words + partial) into caption messages for the column.

    drv = CaptionDriver(mode="word")            # or "tick"
    drv.on_asr(poll.stable, poll.partial, t)    # whenever the recogniser returns something (t = wall/audio clock, s)
    for msg in drv.update(t): send(msg)         # call often (every 10-30 ms); returns messages due now

Word mode: each stable word is shown the moment it arrives and held until the next one. Words that arrive in a burst
(Whisper commits 2-4 at once) are paced at >= `min_dwell` each, and a long word gets its mini-scroll time; if the queue
would leave the column more than `max_behind` s behind the speech, the oldest queued words are dropped (the newest
are what matter live). After `silence_clear` s without a new word the column is cleared.
Ticker mode: stable words are appended at once; the column's own speed controller (column_model.py) keeps the crawl
within ~1.5 s of the speech.
Text: UPPERCASE, light punctuation (. , ? ! ' and characters the font has inside numbers like 3.5, 50%, $20), digits
stay digits. Words with nothing drawable are skipped.
"""
from __future__ import annotations

import re
from collections import deque

from column_model import Config, TICK_HZ, scroll_ticks
from font import CHARSET

KEEP_END = ".,?!"


def normalize_word(w: str) -> str:
    """'hello,' -> 'HELLO,'  '"Yes!"' -> 'YES!'  'it's' -> 'IT'S'  '3.5%' -> '3.5%'  '...' -> ''"""
    w = w.strip().upper().replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    w = w.strip('"()[]{}*_~`')
    w = "".join(c for c in w if c in CHARSET and c != " ")
    w = re.sub(r"([.,?!])[.,?!]+$", r"\1", w)          # "?!" / "..." -> one mark
    w = w.lstrip(".,?!:;-'")
    w = re.sub(r"[:;\-]+$", "", w)                      # trailing dashes/colons are noise on a 32-column window
    return w if re.search(r"[A-Z0-9]", w) else ""


class CaptionDriver:
    def __init__(self, mode: str = "word", partial: bool = False, min_dwell: float = 0.15, max_behind: float = 1.0,
                 silence_clear: float = 2.0, cfg: Config | None = None):
        self.mode, self.partial_on = mode, partial
        self.min_dwell, self.max_behind, self.silence_clear = min_dwell, max_behind, silence_clear
        self.cfg = cfg or Config()
        self.q: deque = deque()          # (word, t_arrival, meta)
        self.out: list[dict] = []
        self.shown_until = -1e9          # earliest time the next word may replace the current one
        self.last_word_t = None          # when the last word was shown (for the silence clear)
        self.showing = ""
        self.partial = ""
        self.sent_partial = ""
        self.dropped = 0
        self.seq = 0
        self.history: list[dict] = []    # every word: arrival, shown/appended time, dropped

    def start_msgs(self) -> list[dict]:
        c = self.cfg
        return [{"cap": "mode", "m": self.mode},
                {"cap": "cfg", "rgb": list(c.rgb), "tick_style": c.tick_style, "scroll_style": c.scroll_style}]

    def _msg(self, m: dict, t: float) -> dict:
        self.seq += 1
        m["id"] = self.seq
        m["t"] = round(t, 3)
        return m

    def on_asr(self, stable: list[str], partial: str, t: float, meta: list | None = None) -> None:
        meta = meta or [None] * len(stable)
        words = [(normalize_word(w), m) for w, m in zip(stable, meta)]
        words = [(w, m) for w, m in words if w]
        self.partial = " ".join(x for x in (normalize_word(p) for p in partial.split()) if x)
        if self.mode == "tick":
            if words:
                self.out.append(self._msg({"cap": "tick", "append": " ".join(w for w, _ in words) + " "}, t))
                for w, m in words:
                    self.history.append(dict(w=w, t_arr=t, t_out=t, meta=m, id=self.seq))
            if self.partial_on and self.partial != self.sent_partial:
                self.out.append(self._msg({"cap": "tick", "partial": self.partial}, t))
                self.sent_partial = self.partial
            return
        for w, m in words:
            self.q.append((w, t, m))

    def update(self, t: float) -> list[dict]:
        if self.mode == "word":
            # drop the oldest queued words if showing them would leave us more than max_behind behind
            while len(self.q) > 1 and t - self.q[0][1] > self.max_behind:
                w, ta, m = self.q.popleft()
                self.dropped += 1
                self.history.append(dict(w=w, t_arr=ta, t_out=None, meta=m, dropped=True))
            if self.q and t >= self.shown_until:
                w, ta, m = self.q.popleft()
                self.out.append(self._msg({"cap": "word", "w": w}, t))
                dwell = max(self.min_dwell, scroll_ticks(w, self.cfg) / TICK_HZ)
                self.shown_until, self.last_word_t, self.showing = t + dwell, t, w
                self.sent_partial = ""
                self.history.append(dict(w=w, t_arr=ta, t_out=t, meta=m, id=self.seq))
            elif self.partial_on and not self.q and self.partial and t >= self.shown_until:
                nxt = self.partial.split()[0]
                if nxt != self.sent_partial:
                    self.out.append(self._msg({"cap": "word", "w": nxt, "dim": 1}, t))
                    self.sent_partial = nxt
            if self.showing and not self.q and self.last_word_t is not None and \
                    t - self.last_word_t >= self.silence_clear and not (self.partial_on and self.partial):
                self.out.append(self._msg({"cap": "clear"}, t))
                self.showing, self.last_word_t = "", None
        out, self.out = self.out, []
        return out
