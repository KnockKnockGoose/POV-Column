"""Offline checks for the povanim prototype:  py -m pytest software/tests -q"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "povgen"))

import povanim as pa  # noqa: E402
from gen_dog_ball import build  # noqa: E402


def test_mapping_covers_every_row_eight_times():
    m = pa.ledmap()
    assert len(m) == 336
    rows = np.zeros(pa.ROWS, int)
    for e in m:
        rows[e["row"]] += 1
    assert (rows == 8).all()
    # the 8 LEDs of a row sit 45 deg apart: offsets 12 columns apart
    offs = sorted(e["col_off"] % 96 for e in m if e["row"] == 17)
    assert offs == list(range(offs[0], offs[0] + 96, 12))


def test_odd_strips_are_inverted_and_sets_interleave():
    # strip s is in interleave set (s + SET_SHIFT) % 3: SET_SHIFT is 0 in the design numbering and 2 as built (the
    # strips sit one rail back since 2026-11-12), so the expected rows are written in terms of it
    def base(s):
        return (s + pa.SET_SHIFT) % pa.N_SETS

    assert pa.led_row(0, 0) == base(0) and pa.led_row(0, 13) == 39 + base(0)       # even strip: LED 0 at the bottom
    assert pa.led_row(1, 0) == 39 + base(1) and pa.led_row(1, 13) == base(1)       # odd strip: mounted upside down
    assert pa.led_row(2, 0) == base(2) and pa.led_row(5, 0) == 39 + base(5)
    assert sorted({pa.led_row(s, 0) % pa.N_SETS for s in range(3)}) == [0, 1, 2]   # three neighbours, three sets
    assert pa.chain_of(11) == 0 and pa.chain_of(12) == 1
    assert pa.strip_col_offset(23) == 92


def test_column_indices_match_brute_force():
    frame = np.arange(pa.ROWS * pa.COLS, dtype=np.int32).reshape(pa.ROWS, pa.COLS) % 251
    frame = frame.astype(np.uint8)
    idx = pa.column_indices(frame, 7)
    for e in pa.ledmap():
        assert idx[e["chain"], e["pos"]] == frame[e["row"], (7 + e["col_off"]) % 96]


def test_pova_roundtrip(tmp_path):
    anim = build("goose", "front", fps=15.0, n_frames=8)
    p = tmp_path / "g.pova"
    info = anim.write(p)
    back = pa.Animation.read(p)
    assert back.n == anim.n and back.fps == anim.fps and back.loop
    assert back.meta["prompt"] == anim.meta["prompt"]
    assert all((a == b).all() for a, b in zip(anim.frames, back.frames))
    assert (back.palette.array() == anim.palette.array()).all()
    assert info["bytes"] < 40_000


def test_rle_roundtrip():
    rng = np.random.default_rng(1)
    a = (rng.random(pa.ROWS * pa.COLS) > 0.9).astype(np.uint8) * rng.integers(1, 5, pa.ROWS * pa.COLS).astype(np.uint8)
    assert (pa.rle_decode(pa.rle_encode(a), a.size) == a).all()


def test_current_model_limits():
    pal = np.array([[0, 0, 0], [255, 255, 255]], dtype=np.uint8)
    off = np.zeros((pa.ROWS, pa.COLS), np.uint8)
    on = np.ones((pa.ROWS, pa.COLS), np.uint8)
    base = 336 * pa.I_DARK_MA + pa.I_ESP_MA
    assert np.allclose(pa.current_profile(off, pal), base)
    assert np.allclose(pa.current_profile(on, pal), base + 336 * 60.0)
    assert np.allclose(pa.current_profile(on, pal, gb=15), base + 336 * 60.0 * 15 / 31)


def test_validator_flags_seam_and_cap():
    pal = pa.Palette()
    w = pal.add("w", (255, 255, 255))
    anim = pa.Animation(pal, fps=10, loop=True)
    for k in range(10):                      # a bar that marches but never returns: bad loop
        cv = pa.Canvas()
        cv.rect(0, 40 + 3 * k, 42, 3, w)
        anim.add(cv)
    rep = pa.validate(anim, mode="orbit")
    assert any("loop seam" in s for s in rep["warnings"])
    full = pa.Animation(pal, fps=10)
    full.add(np.ones((pa.ROWS, pa.COLS), np.uint8) * w)
    rep = pa.validate(full, mode="orbit")
    assert rep["current_peak_ma"] > pa.CAP_MA and rep["gb_recommended"] < 31


def test_dog_and_goose_validate_clean():
    for ch, mode in (("dog", "orbit"), ("goose", "front")):
        anim = build(ch, mode)
        rep = pa.validate(anim, mode=mode)
        assert rep["ok"], rep["warnings"]
        assert rep["current_peak_ma"] < pa.CAP_MA
