"""Figures for the software report: the top-view strip/chain/set map and the F9 -> column pipeline flow.

    py software/povsim/diagrams.py --out docs/img
"""
from __future__ import annotations

import argparse
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "povgen"))
from povanim import COLS_PER_STRIP, FRONT_CENTRE, FRONT_WIDTH, N_STRIPS, STRIPS_PER_CHAIN, chain_of, strip_set  # noqa: E402

SET_COL = {0: (230, 70, 70), 1: (70, 200, 90), 2: (80, 140, 255)}
SET_NAME = "ABC"


def font(size=14):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def topview(path: str, size: int = 980):
    img = Image.new("RGB", (size + 180, size), (250, 250, 250))
    d = ImageDraw.Draw(img)
    cx, cy = size // 2 + 80, size // 2 - 40
    R = size * 0.30
    # front window shading: image columns 32..63 = spatial angles 120..240 deg from the hall reference
    a0 = (FRONT_CENTRE - FRONT_WIDTH // 2) * 360 / 96
    a1 = (FRONT_CENTRE + FRONT_WIDTH // 2) * 360 / 96
    d.pieslice([cx - R * 1.28, cy - R * 1.28, cx + R * 1.28, cy + R * 1.28], start=-a1, end=-a0, fill=(236, 240, 250))
    d.ellipse([cx - R, cy - R, cx + R, cy + R], outline=(40, 40, 40), width=3)
    d.ellipse([cx - R * 0.96, cy - R * 0.96, cx + R * 0.96, cy + R * 0.96], outline=(140, 140, 140), width=1)
    # hall reference + viewer
    d.line([cx, cy, cx + R * 1.22, cy], fill=(120, 120, 120), width=2)
    d.text((cx + R * 1.24, cy - 30), "hall pulse: strip 0 here\n= image column 0", fill=(80, 80, 80), font=font(13))
    vx, vy = cx + R * 1.18 * math.cos(math.radians(FRONT_CENTRE * 3.75)), cy - R * 1.18 * math.sin(
        math.radians(FRONT_CENTRE * 3.75))
    d.ellipse([vx - 9, vy - 9, vx + 9, vy + 9], fill=(60, 60, 60))
    d.text((vx - 120, vy + 16), "viewer / camera:\nimage column 48 (offset trim)\nsees ~32 columns (shaded)",
           fill=(60, 60, 60), font=font(13))
    for s in range(N_STRIPS):
        ang = math.radians(15 * s)
        x, y = cx + R * math.cos(ang), cy - R * math.sin(ang)
        col = SET_COL[strip_set(s)]
        r = 13
        if chain_of(s) == 0:
            d.ellipse([x - r, y - r, x + r, y + r], fill=col, outline=(0, 0, 0), width=2)
        else:
            d.rectangle([x - r, y - r, x + r, y + r], fill=col, outline=(0, 0, 0), width=2)
        # data direction: even strips data in at the bottom (up), odd inverted (down)
        arrow = "^" if s % 2 == 0 else "v"
        d.text((x - 4, y - 9), arrow, fill=(0, 0, 0), font=font(15))
        lx, ly = cx + R * 1.09 * math.cos(ang), cy - R * 1.09 * math.sin(ang)
        d.text((lx - 8, ly - 8), str(s), fill=(20, 20, 20), font=font(13))
        if s % 3 == 0:  # power feed
            px, py = cx + R * 0.88 * math.cos(ang), cy - R * 0.88 * math.sin(ang)
            d.ellipse([px - 5, py - 5, px + 5, py + 5], fill=(240, 190, 0), outline=(0, 0, 0))
        # inter-strip jumper arcs: chain 0 (0..11) and chain 1 (12..23)
    for c0 in (0, 12):
        d.arc([cx - R * 0.80, cy - R * 0.80, cx + R * 0.80, cy + R * 0.80], start=-(15 * (c0 + 11) + 2),
              end=-(15 * c0 - 2), fill=(90, 90, 90) if c0 == 0 else (170, 90, 170), width=4)
    d.text((cx - 70, cy - R * 0.70), "chain 0 (VSPI 23/18)\nstrips 0-11, 168 LEDs", fill=(90, 90, 90), font=font(13))
    d.text((cx - 70, cy + R * 0.58), "chain 1 (HSPI 13/14)\nstrips 12-23, 168 LEDs", fill=(150, 70, 150), font=font(13))
    # legend
    lx, ly = 18, size - 150
    d.rectangle([lx - 8, ly - 8, lx + 440, ly + 140], outline=(120, 120, 120), fill=(255, 255, 255))
    for k in range(3):
        d.ellipse([lx, ly + 22 * k, lx + 16, ly + 16 + 22 * k], fill=SET_COL[k], outline=(0, 0, 0))
        d.text((lx + 24, ly + 22 * k), f"set {SET_NAME[k]} = strips with s mod 3 = {k}: rows {k}, {k + 3}, {k + 6}, ... "
               f"(LED0 at z {11.11 + 5.556 * k:.2f} mm)", fill=(20, 20, 20), font=font(12))
    d.text((lx, ly + 68), "circle = chain 0, square = chain 1;  ^ data enters at the bottom (even strips),  v strip mounted "
                          "inverted (odd)", fill=(20, 20, 20), font=font(12))
    d.text((lx, ly + 88), "yellow = 5 V feed at the bottom of every third strip (0, 3, ... 21)", fill=(20, 20, 20),
           font=font(12))
    d.text((lx, ly + 108), f"strip s shows image column (c + {COLS_PER_STRIP} s) mod 96 when strip 0 is at column c;"
                           f" LED i -> row 3 (i | 13-i) + s mod 3", fill=(20, 20, 20), font=font(12))
    d.text((18, 14), "POV column v2, seen from above: 24 SK9822 strips at 15 deg, 3 interleaved sets, 2 serpentine SPI chains",
           fill=(20, 20, 20), font=font(16))
    img.save(path)


def _box(d, x, y, w, h, title, body, fill, f_t, f_b, outline=(60, 60, 60)):
    d.rounded_rectangle([x, y, x + w, y + h], radius=10, fill=fill, outline=outline, width=2)
    d.text((x + 10, y + 8), title, fill=(10, 10, 10), font=f_t)
    yy = y + 30
    for line in body:
        d.text((x + 10, yy), line, fill=(40, 40, 40), font=f_b)
        yy += 16


def pipeline(path: str):
    W, H = 1720, 760
    img = Image.new("RGB", (W, H), (252, 252, 252))
    d = ImageDraw.Draw(img)
    f_t, f_b, f_l = font(15), font(12), font(16)
    lanes = [("F9 box + mic (Brian)", (255, 247, 230)), ("Desktop PC: Brain-Dump-Button panel + Claude Code", (236, 244, 255)),
             ("Desktop PC: POV pipeline (software/pipeline)", (236, 250, 238)), ("ESP32 on the rotor (pov.local)", (250, 236, 240))]
    lane_h = 150
    for i, (name, col) in enumerate(lanes):
        y = 60 + i * (lane_h + 14)
        d.rectangle([10, y, W - 10, y + lane_h], fill=col, outline=(200, 200, 200))
        d.text((18, y + 6), name, fill=(70, 70, 70), font=f_l)
    d.text((18, 14), "The F9 -> column pipeline: \"POV, a dog running after a ball, looped\"  (times are estimates for the "
                     "desktop path; the ESP32 never generates content)", fill=(20, 20, 20), font=f_l)
    bw, bh = 300, 100
    y0 = 60 + 36
    boxes = [
        (0, 40, "1  hold F9, speak, release", ["panel Talk button sends F13 today, keyboard F9", "says 'POV,' first so the router knows", "optionally '... for the video' = public scope"], (255, 240, 210)),
        (1, 40, "2  ptt_service.pyw (logon task)", ["faster-whisper small, int8, local", "inbox/<stamp>-HOST.txt + log-HOST.jsonl", "~2-3 s after release"], (225, 236, 255)),
        (1, 380, "3  panel voice router (screen/voice.py)", ["claims the file once, prefix 'POV' -> library card", "types the line into Main's console", "(or a running 'POV' session); <= 2 s when idle"], (225, 236, 255)),
        (1, 720, "4  Main (Claude Code)", ["rule in screen/agents/main.md:", "'POV, <prompt>' -> run pov_request.py", "5-10 s to launch; reports back in the terminal"], (225, 236, 255)),
        (2, 40, "5  scope + guard", ["default home; 'public'/'for the video' or", "OBS recording = public: original characters only", "home files stay out of git/Drive/video folders"], (222, 245, 226)),
        (2, 380, "6  generator", ["claude -p (Opus 5.5) + generator_system.md", "writes a povanim scene script (approach a/b)", "20-60 s; cache by prompt; retry on traceback"], (222, 245, 226)),
        (2, 720, "7  sandbox run -> .pova", ["subprocess, 20 s timeout, no network", "42 x 96 x N frames, palette, loop flag, meta", "~0.1 s"], (222, 245, 226)),
        (2, 1060, "8  validate + preview", ["loop seam, peak current vs 2.0 A, framing,", "flicker; simulator GIF for the panel", "1-3 s; fail -> one fix round, else library"], (222, 245, 226)),
        (2, 1400, "9  upload + play", ["POST /api/anims (file) then POST /api/play", "X-POV-Token header; ~0.5 s on Wi-Fi", "home items refused while OBS records"], (222, 245, 226)),
        (3, 1400, "10  ESP32 plays it", ["LittleFS -> palette + RLE frames -> RAM", "core 1 column engine swaps frames at the", "hall pulse; next revolution shows it (0.27 s)"], (250, 222, 230)),
    ]
    pos = {}
    for lane, x, title, body, fill in boxes:
        y = y0 + lane * (lane_h + 14)
        _box(d, x, y, bw, bh, title, body, fill, f_t, f_b)
        pos[title[:2].strip()] = (x, y)
    order = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]
    for a, b in zip(order, order[1:]):
        xa, ya = pos[a]
        xb, yb = pos[b]
        if ya == yb:
            d.line([xa + bw, ya + bh / 2, xb, yb + bh / 2], fill=(50, 50, 50), width=3)
            d.polygon([(xb, yb + bh / 2), (xb - 10, yb + bh / 2 - 6), (xb - 10, yb + bh / 2 + 6)], fill=(50, 50, 50))
        else:
            sx, sy = xa + bw / 2, ya + bh
            ex, ey = xb + bw / 2, yb
            if xb < xa:   # wrap to the next lane's first box, routed below the lane title
                d.line([sx, sy, sx, sy + 14, ex + 40, sy + 14, ex + 40, ey - 4, ex, ey - 4, ex, ey], fill=(50, 50, 50),
                       width=3)
            else:
                d.line([sx, sy, ex, ey], fill=(50, 50, 50), width=3)
            d.polygon([(ex, ey), (ex - 6, ey - 10), (ex + 6, ey - 10)], fill=(50, 50, 50))
    d.text((40, H - 46), "End to end: ~40-90 s for a new animation (dominated by the LLM), ~5 s for a library hit "
                         "('POV, play the goose'). Phone path: Brain Dump App -> Pi server -> steps 5-9 on the Pi.",
           fill=(40, 40, 40), font=f_b)
    img.save(path)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=".")
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    topview(os.path.join(a.out, "sw_fig_topview_mapping.png"))
    pipeline(os.path.join(a.out, "sw_fig_pipeline.png"))
    print("wrote diagrams to", a.out)


if __name__ == "__main__":
    main()
