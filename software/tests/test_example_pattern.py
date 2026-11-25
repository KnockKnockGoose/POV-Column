"""The quick start's example (software/examples/test_pattern.py) must stay a valid, sendable animation."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "povgen"))
sys.path.insert(0, os.path.join(HERE, "..", "examples"))

import povanim as pa  # noqa: E402
import test_pattern  # noqa: E402


def test_pattern_passes_the_validator_at_full_brightness():
    anim = test_pattern.build()
    rep = pa.validate(anim, gb=31, mode="orbit")
    assert rep["ok"], rep["warnings"]
    assert rep["current_peak_ma"] <= pa.CAP_MA
    assert rep["seam_ratio"] <= 1.5                    # the loop closes: every moving part does whole laps


def test_pattern_fits_the_board():
    anim = test_pattern.build()
    data = anim.to_bytes()
    assert len(data) <= 64 * 1024                      # the firmware's upload limit
    assert anim.n <= 256 and len(anim.palette) <= 32
    assert 1 <= len(anim.name) <= 28                   # the firmware's name rule
    assert pa.frame_hold_ticks(anim.fps) * anim.fps == pa.refresh_hz()   # 15 fps = 2 refresh ticks at 225 rpm


def test_pattern_round_trips_through_the_file_format():
    anim = test_pattern.build()
    back = pa.Animation.from_bytes(anim.to_bytes())
    assert back.n == anim.n and back.fps == anim.fps and back.loop
    assert all((a == b).all() for a, b in zip(anim.frames, back.frames))
    assert (back.palette.array() == anim.palette.array()).all()


def test_colour_bars_are_fixed_to_the_column():
    anim = test_pattern.build()
    bottom = [f[0] for f in anim.frames]               # row 0 of every frame
    assert all((b == bottom[0]).all() for b in bottom)
    assert len(set(bottom[0].tolist())) == len(test_pattern.BARS)
