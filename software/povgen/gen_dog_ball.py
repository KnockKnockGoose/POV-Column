"""Generator prototype, approach (a): render "a dog running after a ball, looped" (and a goose variant) as a 42 x 96
cylindrical animation with the povanim DSL, write the .pova file + JSON sidecar, print the validator's report.

    py software/povgen/gen_dog_ball.py --character dog   --mode orbit --out software/content/public
    py software/povgen/gen_dog_ball.py --character goose --mode front --out software/content/public
    py software/povgen/gen_dog_ball.py --povmap software/firmware/src/povmap.h      # regenerate the firmware table

Modes: 'orbit' = the chase travels once around the column per loop (uses the cylinder); 'front' = the character runs in
place inside the viewer's window (columns 32..63) while the ground scrolls under it.

This file is also the worked example the LLM generator prompt shows Claude (see pipeline/prompts/generator_system.md):
a scene script is a function build(...) -> Animation using only povanim + characters-style helpers.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from povanim import COLS, FRONT_CENTRE, Animation, Canvas, validate, write_povmap_header  # noqa: E402
from characters import draw_ball, draw_dog, draw_goose, draw_ground, make_palette  # noqa: E402

PROMPTS = {"dog": "a dog running after a ball, looped", "goose": "a goose running after a ball, looped"}


def build(character: str = "dog", mode: str = "orbit", fps: float = 15.0, n_frames: int | None = None,
          scope: str = "public") -> Animation:
    pal = make_palette()
    if n_frames is None:
        n_frames = 24 if mode == "orbit" else 16
    stride_frames = 8                                   # one run cycle = 8 frames
    cols_per_frame = COLS / n_frames                    # orbit: one lap per loop (closes exactly)
    ground_speed = 3                                    # front: columns per frame; 16 x 3 = 48 = 6 dash periods -> seamless
    draw_char = draw_dog if character == "dog" else draw_goose
    gap = 12 if character == "dog" else 11              # ball runs this far ahead of the chest (orbit)
    if mode == "front":                                 # the whole chase must fit the 32-column window
        gap = 10
        front_base = 50 if character == "dog" else 49
    anim = Animation(pal, fps=fps, loop=True, name=f"{character}_ball_{mode}", meta=dict(
        prompt=PROMPTS[character], character=f"original stylised {character} (no third-party IP)", scope=scope,
        mode=mode, approach="a: procedural primitives" if character == "dog" else "b: text-grid sprite + procedural legs",
        generator="povgen/gen_dog_ball.py (hand-written by Claude Fable 5.1, 2026-11-02)", license="original art, CC0",
        front_centre=FRONT_CENTRE))
    for k in range(n_frames):
        cv = Canvas()
        phase = (k % stride_frames) / stride_frames
        if mode == "orbit":
            base = (FRONT_CENTRE - 6 + k * cols_per_frame) % COLS
            draw_ground(cv, pal, 0)
            draw_ball(cv, pal, base + gap, (k / n_frames) * 6)            # 6 bounces per lap
        else:
            base = front_base
            draw_ground(cv, pal, -k * ground_speed)
            draw_ball(cv, pal, base + gap, (k / n_frames) * 4)            # 4 bounces per loop
        kwargs = dict(honk=(k % stride_frames) in (2, 3)) if character == "goose" else {}
        draw_char(cv, pal, base, phase, **kwargs)
        anim.add(cv)
    return anim


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--character", choices=("dog", "goose"), default="dog")
    ap.add_argument("--mode", choices=("orbit", "front"), default="orbit")
    ap.add_argument("--fps", type=float, default=15.0)
    ap.add_argument("--frames", type=int, default=None)
    ap.add_argument("--scope", choices=("home", "public"), default="public")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "content", "public"))
    ap.add_argument("--gb", type=int, default=31, help="5-bit global brightness assumed by the validator")
    ap.add_argument("--povmap", default=None, help="write the firmware mapping header to this path and exit")
    a = ap.parse_args(argv)
    if a.povmap:
        write_povmap_header(a.povmap)
        print("wrote", a.povmap)
        return 0
    t0 = time.time()
    anim = build(a.character, a.mode, a.fps, a.frames, a.scope)
    os.makedirs(a.out, exist_ok=True)
    info = anim.write(os.path.join(a.out, anim.name + ".pova"))
    rep = validate(anim, gb=a.gb, mode=a.mode)
    info["render_s"] = round(time.time() - t0, 3)
    print(json.dumps(dict(file=info, validation=rep), indent=1))
    return 0 if rep["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
