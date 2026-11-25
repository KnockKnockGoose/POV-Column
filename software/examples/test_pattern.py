"""A neutral test pattern for the POV LED Column: the smallest complete example of the animation DSL.

    py software/examples/test_pattern.py                      # -> software/out/test_pattern/test_pattern.pova (+ .json)
    py software/povsim/simulate.py software/out/test_pattern/test_pattern.pova --stills --gif

What it draws (42 rows x 96 columns, row 0 at the bottom, column 48 facing the viewer):
  * bottom: eight colour bars, 12 columns (45 degrees) each: which way round is the picture, and is the colour order right?
  * a ruler: a tick every 8 columns, a longer one at column 48 (the front)
  * middle: two lines of text in the front window, and a white mark that sweeps once round the column per loop
  * top: a rainbow that scrolls round the cylinder (every column and every hue gets exercised)

It is also what a "scene script" looks like: a function build() that returns an Animation, using only povanim.
The pipeline's language model writes files of this shape (against the higher-level kits in povgen/); the sandbox
imports the file, calls build(), and the validator decides whether the result may go to the column. This file runs
through that same path:

    py software/pipeline/pov_request.py "test pattern" --script software/examples/test_pattern.py --dry-run
"""
from __future__ import annotations

import colorsys
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "povgen"))

from povanim import COLS, FRONT_CENTRE, Animation, Canvas, Palette, Sprite, validate  # noqa: E402

BARS = [("red", (255, 0, 0)), ("yellow", (255, 200, 0)), ("green", (0, 255, 0)), ("cyan", (0, 220, 255)),
        ("blue", (0, 40, 255)), ("magenta", (255, 0, 200)), ("white", (255, 255, 255)), ("grey", (70, 70, 70))]
N_HUES = 16
FRAMES = 48                       # at 15 fps: a 3.2 s loop, and every frame is exactly 2 refresh ticks at 225 rpm

# A sprite is authored as a text grid, top row first: '#' is lit, '.' is transparent. Seven rows of five.
GLYPHS = {
    "H": ["#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "E": ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    "L": ["#....", "#....", "#....", "#....", "#....", "#....", "#####"],
    "O": [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "X": ["#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"],
    "9": [".###.", "#...#", "#...#", ".####", "....#", "...#.", ".##.."],
    "6": ["..##.", ".#...", "#....", "####.", "#...#", "#...#", ".###."],
    "4": ["...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."],
    "2": [".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"],
}


def text_sprite(text: str, colour: int) -> Sprite:
    """One line of text as a sprite: the glyph grids side by side, one empty column between letters."""
    rows = [".".join(GLYPHS[ch][y] for ch in text) for y in range(7)]
    return Sprite.from_text(rows, {"#": colour})


def build(fps: float = 15.0, n_frames: int = FRAMES) -> Animation:
    pal = Palette()
    for name, rgb in BARS:
        pal.add(name, rgb)
    for i in range(N_HUES):
        r, g, b = colorsys.hsv_to_rgb(i / N_HUES, 1.0, 1.0)
        pal.add(f"hue{i}", (round(255 * r), round(255 * g), round(255 * b)))
    amber = pal.add("amber", (255, 150, 30))
    hello, size = text_sprite("HELLO", pal["white"]), text_sprite("96X42", amber)

    anim = Animation(pal, fps=fps, loop=True, name="test_pattern", meta=dict(
        prompt="(none: a hand-written test pattern)", mode="orbit", scope="public",
        generator="software/examples/test_pattern.py", license="MIT"))
    bar_w = COLS // len(BARS)                           # 12 columns
    hue_w = COLS // N_HUES                              # 6 columns
    for k in range(n_frames):
        cv = Canvas()
        # colour bars (rows 0-1), fixed to the column: bar 0 starts at column 0
        for i, (name, _) in enumerate(BARS):
            cv.rect(0, i * bar_w, 2, bar_w, pal[name])
        # ruler (row 4, longer at the front)
        for c in range(0, COLS, 8):
            cv.px(4, c, pal["grey"])
        cv.rect(4, FRONT_CENTRE, 3, 1, pal["white"])
        # two lines of text, centred on the front (blit places a sprite by its bottom-left pixel)
        cv.blit(hello, 25, FRONT_CENTRE - hello.w // 2)
        cv.blit(size, 14, FRONT_CENTRE - size.w // 2)
        # the sweep: one lap per loop, with a short grey tail behind it
        sweep = (k * COLS) // n_frames
        for d, colour in ((0, pal["white"]), (1, pal["grey"]), (2, pal["grey"])):
            for r in (9, 10, 11, 33, 34, 35):
                cv.px(r, sweep - d, colour)
        # scrolling rainbow (rows 40-41). Two rows, not three: every LED of a full-circle row is lit at every
        # rotor angle, so wide bands are what the 2.6 A current check counts first
        shift = (k * COLS) // n_frames
        for c in range(COLS):
            cv.rect(40, c, 2, 1, pal[f"hue{((c + shift) // hue_w) % N_HUES}"])
        anim.add(cv)
    return anim


def main(argv=None) -> int:
    import argparse
    import json
    import time
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out",
                                                   "test_pattern"))
    ap.add_argument("--gb", type=int, default=31, help="5-bit global brightness assumed by the validator (31 = full)")
    a = ap.parse_args(argv)
    t0 = time.time()
    anim = build()
    os.makedirs(a.out, exist_ok=True)
    info = anim.write(os.path.join(a.out, anim.name + ".pova"))
    report = validate(anim, gb=a.gb, mode="orbit")
    info["render_s"] = round(time.time() - t0, 3)
    print(json.dumps(dict(file=info, validation=report), indent=1))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
