"""Worst-case animations for the check-pack-send audit (docs/2026-11-23-check-pack-send-audit.md).

Each case is a povanim.Animation built to hit one check as hard as possible: the current cap (full white, full red,
white on every 4th column, white over the viewer's third), the firmware's file limits (65,536 B, 256 frames, 32 colours,
palette indices) and the 28-character name. A scene script can use them like any generated scene:

    import sys; sys.path.insert(0, r"<software/tests>")
    from checkpack_cases import build_case
    def build():
        return build_case("white_full")
"""
from __future__ import annotations

import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "povgen"))
import povanim as pa  # noqa: E402

ROWS, COLS = pa.ROWS, pa.COLS


def _anim(name: str, colours: list, frames: list, fps: float = 10.0, mode: str = "front") -> pa.Animation:
    pal = pa.Palette()
    for i, rgb in enumerate(colours):
        pal.add(f"c{i + 1}", rgb)
    a = pa.Animation(pal, fps=fps, loop=True, name=name, meta=dict(mode=mode, test="checkpack_audit"))
    for f in frames:
        a.add(np.asarray(f, dtype=np.uint8))
    return a


def _fill(v: int) -> np.ndarray:
    return np.full((ROWS, COLS), v, dtype=np.uint8)


def white_full() -> pa.Animation:
    """Every LED full white at every angle: the most current the model can ask for (20.2 A at gb 31)."""
    return _anim("cp_white_full", [(255, 255, 255)], [_fill(1), _fill(1)])


def red_full() -> pa.Animation:
    """Every LED full red: the colour whose bench current is closest to the model (17.7 of 20 mA)."""
    return _anim("cp_red_full", [(255, 0, 0)], [_fill(1), _fill(1)])


def white_stripes4() -> pa.Animation:
    """White on image columns 0, 4, 8 ... 92 only. Strip s shows column (c + 4 s) at rotor position c, so at every 4th
    position all 24 strips land on a white column at once (all 336 LEDs white, like white_full) and at the other three
    every LED is dark. Average 25 %, peak 100 %: a check that averaged the picture would allow ~4x too much."""
    f = np.zeros((ROWS, COLS), dtype=np.uint8)
    f[:, 0::4] = 1
    return _anim("cp_white_stripes4", [(255, 255, 255)], [f, f])


def white_front_third() -> pa.Animation:
    """White over the viewer's window (columns 32-63) only: a bright front-mode scene, about 1/3 of the LEDs at a time."""
    f = np.zeros((ROWS, COLS), dtype=np.uint8)
    f[:, 32:64] = 1
    return _anim("cp_white_front_third", [(255, 255, 255)], [f, f])


def dark() -> pa.Animation:
    """All off: the idle current (LEDs at duty 0 plus the ESP32)."""
    return _anim("cp_dark", [(0, 0, 1)], [_fill(0), _fill(0)])


def noise_big(n: int = 256) -> pa.Animation:
    """256 frames of 32-colour noise: run-length coding cannot shrink it (about 2 MB), far over the board's 64 KiB."""
    rng = np.random.default_rng(1123)
    cols = [tuple(int(v) for v in rng.integers(0, 256, 3)) for _ in range(31)]
    frames = [rng.integers(0, 32, (ROWS, COLS)).astype(np.uint8) for _ in range(n)]
    return _anim("cp_noise_big", cols, frames)


def frames_257() -> pa.Animation:
    """257 small frames (a dot walking up): under 64 KiB, but one frame over the firmware's 256-frame table."""
    frames = []
    for i in range(257):
        f = np.zeros((ROWS, COLS), dtype=np.uint8)
        f[i % ROWS, 48] = 1
        frames.append(f)
    return _anim("cp_frames_257", [(255, 128, 0)], frames)


def pal_33() -> pa.Animation:
    """33 colours (one over the firmware's 32-entry palette), each in its own band."""
    cols = [(7 * i, 255 - 7 * i, 100) for i in range(33)]
    f = np.zeros((ROWS, COLS), dtype=np.uint8)
    for i in range(33):
        f[i % ROWS, (i * 3) % COLS:(i * 3) % COLS + 3] = i + 1
    a = _anim("cp_pal_33", cols, [f, f])
    return a


def bad_index() -> pa.Animation:
    """A frame that uses palette index 5 with only 2 colours defined: what a script gets if it writes a colour number
    it never added to the palette."""
    f = np.zeros((ROWS, COLS), dtype=np.uint8)
    f[10:20, 40:56] = 1
    f[20:30, 40:56] = 5
    return _anim("cp_bad_index", [(255, 255, 255)], [f, f])


def sized(target_bytes: int, name: str) -> pa.Animation:
    """Exactly target_bytes, for the 65,536-byte boundary: sparse sparkle frames (about 3 KB each) up to just under the
    target, then a short pad in the JSON meta for the last few hundred bytes (a real file's meta is ~300 B)."""
    rng = np.random.default_rng(65536)
    a = _anim(name, [(0, 160, 255), (255, 200, 0)], [])
    a.meta["created"] = "2026-11-23T00:00:00"
    a.meta["pad"] = ""
    while True:
        f = np.zeros((ROWS, COLS), dtype=np.uint8)
        f[rng.random((ROWS, COLS)) < 0.18] = 1
        f[rng.random((ROWS, COLS)) < 0.05] = 2
        a.add(f)
        if len(a.to_bytes()) > target_bytes - 300:
            a.frames.pop()
            a.holds.pop()
            break
    a.meta["pad"] = "x" * (target_bytes - len(a.to_bytes()))
    assert len(a.to_bytes()) == target_bytes, (len(a.to_bytes()), target_bytes)
    return a


CASES = {
    "dark": dark,
    "white_full": white_full,
    "red_full": red_full,
    "white_stripes4": white_stripes4,
    "white_front_third": white_front_third,
    "noise_big": noise_big,
    "at_64k": lambda: sized(65536, "cp_at_64k"),
    "over_64k_by_1": lambda: sized(65537, "cp_over_64k_by_1"),
    "frames_257": frames_257,
    "pal_33": pal_33,
    "bad_index": bad_index,
}


def build_case(name: str) -> pa.Animation:
    return CASES[name]()
