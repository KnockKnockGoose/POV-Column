"""Caption engine checks (no models or audio needed):  py -m pytest software/tests -q"""
import os
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "captions"))
sys.path.insert(0, os.path.join(HERE, "..", "povgen"))

import font  # noqa: E402
from column_model import (TICK_HZ, WIN_L, WIN_R, ColumnCaptions, Config, layout_word,  # noqa: E402
                          scroll_ticks)
from engine import CaptionDriver, normalize_word  # noqa: E402
from session import Session  # noqa: E402

TICK = 1 / TICK_HZ


# ---------------------------------------------------------------- fonts and fit
def test_fonts_cover_the_charset():
    for ch in font.CHARSET:
        g5, g7 = font.glyph(ch, "5x7"), font.glyph(ch, "7x9")
        assert g5 is not None and g5.shape[0] == 7, ch
        assert g7 is not None and g7.shape[0] == 9 and g7.shape[1] <= 7, ch
    for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789":
        assert ch in font.G7, f"7x9 should draw {ch} natively"
        assert font.glyph(ch, "7x9").any(axis=0).all() or ch in "1IT", ch   # no blank columns inside glyphs


def test_text_width_matches_raster():
    for w in ["HI", "HELLO", "F9", "IT'S", "3.5%"]:
        for f in ("5x7", "7x9"):
            assert font.rasterize(w, f).shape[1] == font.text_width(w, f)


def test_auto_font_choice():
    assert layout_word("HI")[0] == "7x9"
    assert layout_word("SO")[:2] == ("7x9", 15)            # 7 + gap + 7
    assert layout_word("HELLO") == ("5x7", 29, False)          # 7x9 would be 39 columns
    f, w, scroll = layout_word("TRANSCRIPTION")
    assert f == "5x7" and scroll and w > 32
    assert scroll_ticks("TRANSCRIPTION") > 0 and scroll_ticks("HELLO") == 0
    # boundary: exactly 32 columns fits without a scroll
    word = "WWWWW"                                            # 5 x 5 + 4 gaps = 29 in 5x7
    assert layout_word(word)[2] is False


@pytest.mark.parametrize("word", ["HI", "WORD", "HELLO", "COLUMN", "CAPTIONS"])
def test_word_stays_inside_the_window(word):
    m = ColumnCaptions(mode="word")
    m.receive({"cap": "word", "w": word})
    fr = m.tick(0.0)
    lit = np.nonzero(fr.any(axis=0))[0]
    assert lit.min() >= WIN_L - 8 and lit.max() <= WIN_R + 8
    if not layout_word(word)[2]:
        assert lit.min() >= WIN_L and lit.max() <= WIN_R
        centre = (lit.min() + lit.max()) / 2
        assert abs(centre - 47.5) <= 1.0


@pytest.mark.parametrize("style", ["jump", "smooth"])
def test_mini_scroll_reaches_the_end_of_a_long_word(style):
    word = "TRANSCRIPTION"
    m = ColumnCaptions(mode="word", cfg=Config(scroll_style=style))
    m.receive({"cap": "word", "w": word})
    frames = [m.tick(k * TICK) for k in range(scroll_ticks(word, m.cfg) + 2)]
    bm = font.rasterize(word, "5x7")
    W = bm.shape[1]
    vs = m.cfg.word_vs
    base = (42 - 7 * vs) // 2
    # first frame: the word's first column at the window's left edge; last frame: its last column at the right edge
    assert frames[0][base:base + 7 * vs, WIN_L].any() == bm[:, 0].any()
    assert (frames[-1][base + vs * 0:base + 7 * vs, WIN_R] > 0).any() == bm[:, W - 1].any()
    first_lit = [np.nonzero(f.any(axis=0))[0].min() for f in frames]
    assert first_lit[0] >= WIN_L - 8


def test_normalize_light_punctuation_and_digits():
    assert normalize_word("hello,") == "HELLO,"
    assert normalize_word('"Yes!"') == "YES!"
    assert normalize_word("it’s") == "IT'S"
    assert normalize_word("3.5%") == "3.5%"
    assert normalize_word("$20") == "$20"
    assert normalize_word("F9") == "F9"
    assert normalize_word("...") == ""
    assert normalize_word("wait...") == "WAIT."
    assert normalize_word("uh—") == "UH"
    assert normalize_word("naïve") == "NAVE" or normalize_word("naïve") == "NAIVE"


# ---------------------------------------------------------------- word mode timing
def run_driver(drv, arrivals, t_end, dt=0.005):
    """arrivals: [(t, [words])]. Returns [(t, msg)]."""
    out, ai, t = [], 0, 0.0
    while t < t_end:
        while ai < len(arrivals) and arrivals[ai][0] <= t:
            drv.on_asr(arrivals[ai][1], "", t)
            ai += 1
        out += [(t, m) for m in drv.update(t)]
        t += dt
    return out


def test_word_shown_as_soon_as_it_arrives_and_held():
    drv = CaptionDriver("word")
    out = run_driver(drv, [(0.50, ["hello"]), (0.95, ["world"])], 1.5)
    words = [(t, m["w"]) for t, m in out if m["cap"] == "word"]
    assert words[0][1] == "HELLO" and abs(words[0][0] - 0.50) < 0.006
    assert words[1][1] == "WORLD" and abs(words[1][0] - 0.95) < 0.006
    assert not any(m["cap"] == "clear" for _, m in out)          # held between words, no flicker


def test_burst_is_paced_not_dropped():
    drv = CaptionDriver("word", min_dwell=0.15)
    out = run_driver(drv, [(1.0, ["so", "the", "other", "input"])], 2.5)
    ts = [t for t, m in out if m["cap"] == "word"]
    assert len(ts) == 4
    gaps = np.diff(ts)
    assert (gaps >= 0.15 - 0.006).all() and (gaps <= 0.15 + 0.011).all()
    assert drv.dropped == 0


def test_word_mode_never_falls_more_than_max_behind():
    drv = CaptionDriver("word", min_dwell=0.15, max_behind=1.0)
    burst = [f"w{i}" for i in range(20)]
    out = run_driver(drv, [(1.0, burst)], 4.0)
    shown = [(t, m["w"]) for t, m in out if m["cap"] == "word"]
    assert drv.dropped > 0
    assert shown[-1][1] == "W19"                                  # the newest word is always shown
    for h in drv.history:
        if h.get("t_out") is not None:
            assert h["t_out"] - h["t_arr"] <= 1.0 + 0.15 + 0.01


def test_silence_clears_after_two_seconds():
    drv = CaptionDriver("word", silence_clear=2.0)
    out = run_driver(drv, [(0.2, ["hello"])], 3.0)
    clears = [t for t, m in out if m["cap"] == "clear"]
    assert len(clears) == 1 and abs(clears[0] - 2.2) < 0.011


def test_session_word_reaches_the_next_tick():
    s = Session("word", link_s=0.015, cam_phase=0.0)
    s.on_asr(["hello"], "", 0.50, [0.30])
    t = 0.5
    while t < 0.7:
        s.advance(t)
        t += 0.001
    (rec,) = s.records.values()
    assert rec["out"] == pytest.approx(0.50, abs=0.002)
    assert 0 <= rec["shown"] - rec["arrive"] <= TICK + 1e-6        # waits at most one refresh tick
    assert 0 <= rec["camera"] - rec["shown"] <= 1 / 30 + 1e-6     # and at most one camera frame
    assert rec["camera"] - rec["end"] < 0.35


# ---------------------------------------------------------------- ticker
def sim_ticker(word_times, t_end, cfg=None):
    m = ColumnCaptions(cfg=cfg or Config(tick_style="crawl"), mode="tick")
    k, wi = 0, 0
    while k * TICK < t_end:
        t = k * TICK
        while wi < len(word_times) and word_times[wi][0] <= t:
            m.receive({"cap": "tick", "append": word_times[wi][1] + " "})
            wi += 1
        m.tick(t)
        k += 1
    return m


def speech(rate_wps, seconds, words=("CAPTIONS", "ON", "THE", "COLUMN", "WHILE", "I", "TALK", "ABOUT", "IT")):
    return [(i / rate_wps, words[i % len(words)]) for i in range(int(rate_wps * seconds))]


def test_ticker_keeps_up_with_normal_speech():
    m = sim_ticker(speech(2.2, 20), 23)                          # ~130 wpm (Brian's median F9 rate is 133)
    lags = [e["lag"] for e in m.log if e["ev"] == "entered"]
    assert m.dropped == 0 and len(lags) == 44
    assert max(lags) <= 1.5


def test_ticker_catches_up_by_dropping_when_speech_is_too_fast():
    m = sim_ticker(speech(5.0, 20), 23)                          # 300 wpm: more than v_max can show
    lags = [e["lag"] for e in m.log if e["ev"] == "entered"]
    assert m.dropped > 0
    assert max(lags) <= 1.5 + TICK + 1e-6                         # never more than 1.5 s behind
    assert any(e["ev"] == "entered" and e["w"] == "TALK" for e in m.log[-40:])   # still showing new words
    assert m.v <= m.cfg.v_max + 1e-9


def test_ticker_speeds_up_with_backlog_and_idles_at_v_min():
    m = ColumnCaptions(mode="tick", cfg=Config(tick_style="crawl"))
    m.receive({"cap": "tick", "append": "A LONG BURST OF WORDS ARRIVES ALL AT ONCE "})
    m.tick(0.0)
    m.tick(TICK)
    assert m.v > m.cfg.v_min
    vs = []
    for k in range(2, 300):
        m.tick(k * TICK)
        vs.append((m.v, bool(m.tape)))
    assert any(v == pytest.approx(m.cfg.v_min) and tape for v, tape in vs)   # all in: crawls out at v_min
    assert vs[-1] == (0.0, False)                                            # then gone, and stopped
    lags = [e["lag"] for e in m.log if e["ev"] == "entered"]
    assert max(lags) <= m.cfg.max_behind + TICK          # a 230-column burst: v_max + drops keep it inside 1.5 s


@pytest.mark.parametrize("style", ["hybrid", "crawl"])
def test_ticker_text_crawls_right_to_left_and_leaves(style):
    m = ColumnCaptions(mode="tick", cfg=Config(tick_style=style))
    m.receive({"cap": "tick", "append": "HI "})
    xs = []
    for k in range(150):
        fr = m.tick(k * TICK)
        cols = np.nonzero(fr.any(axis=0))[0]
        win = cols[(cols >= WIN_L) & (cols <= WIN_R)]
        xs.append(win.mean() if len(win) else np.nan)
    seen = np.array([x for x in xs if not np.isnan(x)])
    assert len(seen) > 5 and (np.diff(seen) <= 0).all()           # moves towards the viewer's left
    assert np.isnan(xs[-1]) and not m.tape                        # gone and forgotten after ~5 s


def test_jump_scroll_moves_in_whole_characters_and_holds_between():
    cfg = Config(scroll_style="jump")
    from column_model import scroll_offset
    offs = [scroll_offset(k, 45, cfg) for k in range(40)]
    assert offs[0] == 0 and offs[-1] == 45
    steps = [b - a for a, b in zip(offs, offs[1:]) if b != a]
    assert all(s <= cfg.scroll_jump_cols for s in steps)
    changes = [k for k in range(1, 40) if offs[k] != offs[k - 1]]
    assert all(b - a >= cfg.scroll_jump_ticks for a, b in zip(changes, changes[1:]))   # static frames in between


def test_hybrid_ticker_is_legible_and_low_latency():
    m = sim_ticker(speech(2.2, 20), 23, cfg=Config(tick_style="hybrid"))
    lags = [e["lag"] for e in m.log if e["ev"] == "entered"]
    assert m.dropped == 0 and len(lags) == 44
    assert max(lags) <= TICK + 1e-9                               # every word fully in at the tick it arrives
    xs = []
    m2 = ColumnCaptions(mode="tick", cfg=Config(tick_style="hybrid"))
    m2.receive({"cap": "tick", "append": "HI "})
    for k in range(90):
        m2.tick(k * TICK)
        xs.append(m2.x)
    moves = np.diff(xs)
    idle = int(m2.cfg.crawl_idle_s * TICK_HZ)
    assert (moves[1:idle - 1] == 0).all()                         # holds still (crisp on camera) while recent
    assert (moves[idle + 1:] == 1).all()                          # then drifts away at 1 column per tick


def test_hybrid_ticker_keeps_up_with_very_fast_speech_by_jumping():
    m = sim_ticker(speech(5.0, 20), 23, cfg=Config(tick_style="hybrid"))
    lags = [e["lag"] for e in m.log if e["ev"] == "entered"]
    jumps = [e for e in m.log if e["ev"] == "jump"]
    assert m.dropped == 0 and len(lags) == 100 and max(lags) <= TICK + 1e-9
    assert len(jumps) > 20


def test_current_limiter_keeps_a_full_white_ticker_under_the_cap():
    import povanim as pa
    m = ColumnCaptions(mode="tick", cfg=Config(rgb=(255, 255, 255)))
    m.receive({"cap": "tick", "append": "WWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWW "})
    worst, gbs = 0.0, []
    for k in range(90):
        fr = m.tick(k * TICK)
        assert m.peak_ma <= pa.CAP_MA + 1e-6
        assert m.peak_ma == pytest.approx(pa.current_profile(fr, m.cfg.palette(), gb=m.gb).max())
        worst = max(worst, pa.current_profile(fr, m.cfg.palette(), gb=31).max())
        gbs.append(m.gb)
    assert worst > pa.CAP_MA and min(gbs) < 31          # the worst case really needs the limiter


def test_limiter_releases_slowly_and_leaves_normal_words_alone():
    m = ColumnCaptions(mode="word")
    m.receive({"cap": "word", "w": "HI"})
    m.tick(0.0)
    assert m.gb == 31                                   # one word in the window is far below 2 A
    m.cfg.gb_max = 31
    m.gb = 10
    for k in range(1, 7):
        m.tick(k * TICK)
    assert m.gb == 12                                   # +1 per 3 ticks, no jump back to full brightness


# ---------------------------------------------------------------- ASR stability logic (no model needed)
def test_local_agreement_commits_only_what_two_hypotheses_agree_on():
    import asr
    la = asr.WhisperLA.__new__(asr.WhisperLA)
    la.step_s, la.beam, la.trim_s, la.hot = 0.5, 1, 12.0, ""
    la.reset()
    la.audio = np.zeros(16000, np.float32)
    hyps = iter([
        [(0.0, 0.3, "the"), (0.3, 0.6, "cat")],
        [(0.0, 0.3, "the"), (0.3, 0.6, "cap"), (0.6, 0.9, "shuns")],
        [(0.0, 0.3, "the"), (0.3, 0.6, "cap"), (0.6, 0.9, "shuns"), (0.9, 1.2, "work")],
    ])
    la._transcribe = lambda: next(hyps)
    assert la.poll().stable == []                       # nothing to agree with yet
    p = la.poll()
    assert p.stable == ["the"] and p.partial == "cap shuns"
    p = la.poll()
    assert p.stable == ["cap", "shuns"] and p.stable_t == [0.6, 0.9]


def test_font_header_is_generated(tmp_path):
    p = tmp_path / "captions_font.h"
    font.write_header(str(p))
    s = p.read_text()
    assert "CAPF_5X7[" in s and "CAPF_7X9[" in s and "'A'" in s
