"""The simulator's four stills (flat, contact sheet, cylinder, shutter comparison) at a chosen frame instead of frame 0.

simulate.py --stills always shows frame 0, which is the wrong moment for animations that open on a transition (an iris,
or a subject that starts behind the column in orbit mode). Same renderers, same file names, same sizes; existing files
are never overwritten.

    py software/povsim/stills_at.py software/content/public/bichon_shades_front.pova --frame 70 --out <dir>
"""
from __future__ import annotations

import argparse
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from simulate import (GAMMA, RPM_DEFAULT, Animation, Camera, contact_sheet, exposure, font, frame_hold_ticks,  # noqa: E402
                      ideal, parse_shutter, refresh_hz, render_cylinder, render_flat)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pova")
    ap.add_argument("--frame", type=int, required=True, help="hero frame for the flat, cylinder and shutter stills")
    ap.add_argument("--out", required=True)
    ap.add_argument("--rpm", type=float, default=RPM_DEFAULT)
    a = ap.parse_args(argv)
    anim = Animation.read(a.pova)
    name = os.path.splitext(os.path.basename(a.pova))[0]
    os.makedirs(a.out, exist_ok=True)
    pal_lin = (anim.palette.array() / 255.0) ** GAMMA
    hold = frame_hold_ticks(anim.fps, a.rpm) / refresh_hz(a.rpm)
    t0 = a.frame * hold + 0.1 * hold                     # an exposure that starts inside the hero frame
    jobs = {
        f"{name}_flat.png": lambda: render_flat(anim.rgb(a.frame), scale=8),
        f"{name}_sheet.png": lambda: contact_sheet(anim),
        f"{name}_cyl.png": lambda: render_cylinder(ideal(anim, a.frame, pal_lin), Camera(width=900, height=720)),
    }

    def shutter_strip():
        tiles = []
        for sh in ("1/30", "1/60", "1/250", "1/2000"):
            im = render_cylinder(exposure(anim, t0, parse_shutter(sh), a.rpm, pal_lin), Camera(width=460, height=400))
            ImageDraw.Draw(im).text((10, 8), f"shutter {sh} s", fill=(200, 200, 200), font=font(16))
            tiles.append(im)
        strip = Image.new("RGB", (sum(t.width for t in tiles) + 5 * 3, tiles[0].height), (12, 12, 14))
        x = 0
        for t in tiles:
            strip.paste(t, (x, 0))
            x += t.width + 5
        return strip

    jobs[f"{name}_shutter.png"] = shutter_strip
    for fn, make in jobs.items():
        p = os.path.join(a.out, fn)
        if os.path.exists(p):
            print("exists, skipped:", p)
            continue
        make().save(p)
        print("wrote", p)


if __name__ == "__main__":
    main()
