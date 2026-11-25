"""POV column simulator: renders a .pova animation as (i) the flat 96 x 42 unwrapped grid and (ii) a perspective view of
the spinning cylinder (LED dots on black) with a physical persistence model, and exports PNG stills, GIF and MP4.

    py software/povsim/simulate.py software/content/public/dog_ball_orbit.pova --out software/out/dog --gif --mp4 --stills
    py software/povsim/simulate.py <file.pova> --shutter 1/2000 --still reveal.png      # the "how it really works" frame

Persistence model (section 6 of the report): at `rpm` the rotor period is T; image column c is painted by the eight strips of
its row's set at times t = ((c - 4 s) mod 96) * T/96 + m T, each paint lasting one column time T/96 and every pixel being
repainted every T/8 (= 1/30 s at 225 rpm). A camera with shutter tau integrates the paint events inside its window, so
tau = T/8 captures every pixel exactly once (a complete picture), tau = T/16 catches half of them (a dashed picture) and
tau = 1/2000 s freezes the 24 strips with a few lit LEDs each. Brightness falls off with the LED's emission angle (lambertian)
and the front ~32 columns are the ones a viewer sees well. The GIF preview uses ideal persistence (what a viewer sees);
the MP4 uses the camera model at 30 fps so frame changes mid-exposure show up as they would on the Sony.
"""
from __future__ import annotations

import argparse
import math
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "povgen"))
from povanim import (COL_ARC_MM, COLS, FRONT_CENTRE, FRONT_WIDTH, GAMMA, H_TUBE_MM, LED_BODY_MM, N_SETS, R_LED_MM,  # noqa: E402
                     ROW_PITCH_MM, ROWS, RPM_DEFAULT, Z0_MM, Animation, frame_hold_ticks, refresh_hz, rev_period_s)

FFMPEG = shutil.which("ffmpeg")


def font(size=16):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # older Pillow
        return ImageFont.load_default()


# ---------------------------------------------------------------- flat (unwrapped) view
def render_flat(rgb: np.ndarray, scale: int = 6, label: bool = True, front: bool = True) -> Image.Image:
    """rgb: (42, 96, 3) uint8 sRGB as stored in the file. Row 0 (bottom LED row) is drawn at the bottom."""
    m, top = 14, (26 if label else 4)
    W, H = COLS * scale + 2 * m, ROWS * scale + top + (22 if front else 4)
    img = Image.new("RGB", (W, H), (8, 8, 10))
    d = ImageDraw.Draw(img)
    for r in range(ROWS):
        y = top + (ROWS - 1 - r) * scale
        for c in range(COLS):
            col = tuple(int(v) for v in rgb[r, c])
            x = m + c * scale
            if col == (0, 0, 0):
                d.rectangle([x, y, x + scale - 2, y + scale - 2], fill=(20, 20, 24))
            else:
                d.rounded_rectangle([x, y, x + scale - 2, y + scale - 2], radius=max(1, scale // 3), fill=col)
    if label:
        f = font(12)
        d.text((m, 4), "column 0", fill=(150, 150, 150), font=f)
        d.text((m + 48 * scale - 20, 4), "48 (viewer)", fill=(150, 150, 150), font=f)
        d.text((m + 95 * scale - 10, 4), "95", fill=(150, 150, 150), font=f)
        d.text((W - 92, H - 18), "row 0 = bottom", fill=(110, 110, 110), font=f)
    if front:
        c0, c1 = FRONT_CENTRE - FRONT_WIDTH // 2, FRONT_CENTRE + FRONT_WIDTH // 2
        y = top + ROWS * scale + 3
        d.line([m + c0 * scale, y, m + c1 * scale - 2, y], fill=(90, 90, 100), width=2)
        d.line([m + c0 * scale, y - 4, m + c0 * scale, y + 4], fill=(90, 90, 100), width=2)
        d.line([m + c1 * scale - 2, y - 4, m + c1 * scale - 2, y + 4], fill=(90, 90, 100), width=2)
        d.text((m + c0 * scale + 4, y + 4), f"front window: columns {c0}-{c1 - 1} (what a viewer sees)",
               fill=(120, 120, 130), font=font(12))
    return img


def contact_sheet(anim: Animation, per_row: int = 6, scale: int = 3) -> Image.Image:
    tiles = [render_flat(anim.rgb(i), scale=scale, label=False, front=False) for i in range(anim.n)]
    tw, th = tiles[0].size
    rows = math.ceil(len(tiles) / per_row)
    sheet = Image.new("RGB", (per_row * (tw + 4) + 4, rows * (th + 18) + 4), (30, 30, 34))
    d = ImageDraw.Draw(sheet)
    for i, t in enumerate(tiles):
        x, y = 4 + (i % per_row) * (tw + 4), 4 + (i // per_row) * (th + 18)
        sheet.paste(t, (x, y + 14))
        d.text((x + 2, y), f"frame {i}", fill=(180, 180, 180), font=font(11))
    return sheet


# ---------------------------------------------------------------- cylinder view
class Camera:
    """Pinhole camera on the column's equator looking at image column `view_col`."""

    def __init__(self, width=900, height=720, dist_mm=900.0, view_col=FRONT_CENTRE, yaw_deg=0.0, fill=0.78):
        self.W, self.H, self.D = width, height, dist_mm
        self.view_col, self.yaw = view_col, math.radians(yaw_deg)
        self.f = fill * height * dist_mm / H_TUBE_MM

    def project(self):
        c = np.arange(COLS)
        th = (c - self.view_col) * (2 * math.pi / COLS) + self.yaw        # angle from the view axis
        x = R_LED_MM * np.sin(th)
        depth = self.D - R_LED_MM * np.cos(th)
        z = Z0_MM + np.arange(ROWS) * ROW_PITCH_MM - H_TUBE_MM / 2
        u = np.broadcast_to(self.W / 2 + self.f * x[None, :] / depth[None, :], (ROWS, COLS))
        v = self.H / 2 - self.f * z[:, None] / depth[None, :]
        cos_e = (self.D * np.cos(th) - R_LED_MM) / np.sqrt((R_LED_MM * np.sin(th)) ** 2 + depth ** 2)
        w_px = self.f * (COL_ARC_MM + 0.6 * LED_BODY_MM) * np.abs(np.cos(th)) / depth
        h_px = self.f * LED_BODY_MM / depth
        return u, v, np.clip(cos_e, 0, None), np.maximum(w_px, 1.5), np.maximum(h_px, 1.5)

    def outline(self, d: ImageDraw.ImageDraw):
        """Faint silhouette of the black tube so the eye reads a cylinder."""
        r_px = self.f * R_LED_MM / self.D
        for zz in (-H_TUBE_MM / 2, H_TUBE_MM / 2):
            y = self.H / 2 - self.f * zz / self.D
            ry = r_px * 0.10
            d.ellipse([self.W / 2 - r_px, y - ry, self.W / 2 + r_px, y + ry], outline=(34, 34, 40))
        d.line([self.W / 2 - r_px, self.H / 2 + self.f * H_TUBE_MM / 2 / self.D, self.W / 2 - r_px,
                self.H / 2 - self.f * H_TUBE_MM / 2 / self.D], fill=(34, 34, 40))
        d.line([self.W / 2 + r_px, self.H / 2 + self.f * H_TUBE_MM / 2 / self.D, self.W / 2 + r_px,
                self.H / 2 - self.f * H_TUBE_MM / 2 / self.D], fill=(34, 34, 40))


def render_cylinder(lin: np.ndarray, cam: Camera, bloom: bool = True) -> Image.Image:
    """lin: (42, 96, 3) linear light 0..~1 already multiplied by the persistence weights."""
    u, v, cos_e, w_px, h_px = cam.project()
    img = Image.new("RGB", (cam.W, cam.H), (0, 0, 0))
    d = ImageDraw.Draw(img)
    cam.outline(d)
    vis = cos_e > 0.02
    L = lin * cos_e[None, :, None]
    srgb = np.clip(255 * np.clip(L, 0, 1) ** (1 / GAMMA), 0, 255).astype(np.uint8)
    rr, cc = np.nonzero(vis[None, :].repeat(ROWS, 0) & (lin.max(axis=2) > 0.002))
    # draw far-to-near is irrelevant on a convex surface; draw in column order
    for r, c in zip(rr, cc):
        col = tuple(int(x) for x in srgb[r, c])
        x, y, w, h = u[r, c], v[r, c], w_px[c] / 2, h_px[c] / 2
        d.ellipse([x - w, y - h, x + w, y + h], fill=col)
    if bloom:
        a = np.asarray(img).astype(np.float32)
        b1 = np.asarray(img.filter(ImageFilter.GaussianBlur(3))).astype(np.float32)
        b2 = np.asarray(img.filter(ImageFilter.GaussianBlur(9))).astype(np.float32)
        img = Image.fromarray(np.clip(a + 0.45 * b1 + 0.25 * b2, 0, 255).astype(np.uint8))
    return img


# ---------------------------------------------------------------- persistence / shutter model
def paint_times(rpm: float = RPM_DEFAULT) -> np.ndarray:
    """(8, 42, 96): within one revolution, when (s) each of the 8 strips of a row's set starts painting column c."""
    T = rev_period_s(rpm)
    t_col = T / COLS
    r = np.arange(ROWS)[:, None]
    c = np.arange(COLS)[None, :]
    s = (r % N_SETS)[None, :, :] + 3 * np.arange(8)[:, None, None]          # strips of this row's set (8, 42, 96)
    return ((c[None] - 4 * s) % COLS) * t_col


def exposure(anim: Animation, t0: float, tau: float, rpm: float = RPM_DEFAULT, pal_lin=None) -> np.ndarray:
    """Linear-light image (42, 96, 3) a camera integrates over [t0, t0 + tau], frames advancing on 1/8-rev ticks."""
    T = rev_period_s(rpm)
    t_col = T / COLS
    tick = 1.0 / refresh_hz(rpm)
    hold = frame_hold_ticks(anim.fps, rpm) * tick
    if pal_lin is None:
        pal_lin = (anim.palette.array() / 255.0) ** GAMMA
    frames_lin = np.stack([pal_lin[f] for f in anim.frames])                 # (n, 42, 96, 3)
    pt = paint_times(rpm)
    out = np.zeros((ROWS, COLS, 3))
    m0 = math.floor((t0 - T) / T)
    m1 = math.ceil((t0 + tau) / T)
    rr = np.arange(ROWS)[None, :, None]
    cc = np.arange(COLS)[None, None, :]
    for m in range(m0, m1 + 1):
        te = pt + m * T
        ov = np.clip(np.minimum(t0 + tau, te + t_col) - np.maximum(t0, te), 0, None) / t_col     # (8, 42, 96)
        if not ov.any():
            continue
        fi = (np.floor(te / hold).astype(int)) % anim.n
        out += (frames_lin[fi, rr, cc] * ov[..., None]).sum(axis=0)
    return out


def ideal(anim: Animation, i: int, pal_lin=None) -> np.ndarray:
    if pal_lin is None:
        pal_lin = (anim.palette.array() / 255.0) ** GAMMA
    return pal_lin[anim.frames[i]]


# ---------------------------------------------------------------- composition + export
def compose(flat: Image.Image, cyl: Image.Image, title_l: str, title_r: str, width: int = 1280) -> Image.Image:
    h = max(flat.height + 40, cyl.height + 40)
    img = Image.new("RGB", (width, h), (12, 12, 14))
    half = width // 2
    img.paste(flat, ((half - flat.width) // 2, 30 + (h - 40 - flat.height) // 2))
    img.paste(cyl, (half + (half - cyl.width) // 2, 30 + (h - 40 - cyl.height) // 2))
    d = ImageDraw.Draw(img)
    d.text((12, 6), title_l, fill=(190, 190, 190), font=font(15))
    d.text((half + 12, 6), title_r, fill=(190, 190, 190), font=font(15))
    return img


def write_gif(frames: list[Image.Image], path: str, fps: float):
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=int(round(1000 / fps)), loop=0, optimize=True)


def write_mp4(frames: list[Image.Image], path: str, fps: int = 30, crf: int = 18):
    if not FFMPEG:
        raise RuntimeError("ffmpeg not found")
    with tempfile.TemporaryDirectory() as td:
        for i, fr in enumerate(frames):
            fr.save(os.path.join(td, f"{i:05d}.png"))
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-framerate", str(fps), "-i", os.path.join(td, "%05d.png"),
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", str(crf), "-movflags", "+faststart", path],
                       check=True)


def parse_shutter(s: str) -> float:
    if "/" in s:
        a, b = s.split("/")
        return float(a) / float(b)
    return float(s)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pova")
    ap.add_argument("--out", default=None, help="output folder (default: software/out/<name>)")
    ap.add_argument("--rpm", type=float, default=RPM_DEFAULT)
    ap.add_argument("--gif", action="store_true", help="composite GIF at the animation's frame rate (ideal persistence)")
    ap.add_argument("--mp4", action="store_true", help="30 fps composite MP4 with the camera model (1/30 s shutter)")
    ap.add_argument("--seconds", type=float, default=6.0, help="MP4 length")
    ap.add_argument("--stills", action="store_true", help="flat frame 0, contact sheet, cylinder, shutter comparison")
    ap.add_argument("--shutter", default=None, help="render one still with this shutter, e.g. 1/2000 (with --still)")
    ap.add_argument("--still", default=None, help="path of the single still for --shutter")
    ap.add_argument("--t0", type=float, default=0.137, help="exposure start (s) for --shutter")
    ap.add_argument("--yaw", type=float, default=0.0, help="camera yaw around the column (deg) for the MP4 start")
    ap.add_argument("--orbit-camera", type=float, default=0.0, help="deg of camera yaw per second in the MP4 (B-roll)")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--scale", type=int, default=6)
    a = ap.parse_args(argv)
    anim = Animation.read(a.pova)
    name = os.path.splitext(os.path.basename(a.pova))[0]
    out = a.out or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out", name)
    os.makedirs(out, exist_ok=True)
    pal_lin = (anim.palette.array() / 255.0) ** GAMMA
    cam = Camera(width=a.width // 2 - 20, height=int(a.width * 0.45), yaw_deg=a.yaw)
    cap_r = f"what the camera sees: {a.rpm:g} rpm, 30p, 1/30 s shutter"
    cap_l = f"unwrapped 96 x 42 frame (what the .pova holds), {anim.fps:g} fps"
    written = []
    if a.shutter and a.still:
        tau = parse_shutter(a.shutter)
        img = render_cylinder(exposure(anim, a.t0, tau, a.rpm, pal_lin), cam)
        img.save(a.still)
        written.append(a.still)
    if a.stills:
        render_flat(anim.rgb(0), scale=8).save(os.path.join(out, f"{name}_flat.png"))
        contact_sheet(anim).save(os.path.join(out, f"{name}_sheet.png"))
        big = Camera(width=900, height=720)
        render_cylinder(ideal(anim, 0, pal_lin), big).save(os.path.join(out, f"{name}_cyl.png"))
        # shutter comparison: 1/30, 1/60, 1/250, 1/2000 s at the same instant
        tiles = []
        for sh in ("1/30", "1/60", "1/250", "1/2000"):
            im = render_cylinder(exposure(anim, a.t0, parse_shutter(sh), a.rpm, pal_lin), Camera(width=460, height=400))
            ImageDraw.Draw(im).text((10, 8), f"shutter {sh} s", fill=(200, 200, 200), font=font(16))
            tiles.append(im)
        strip = Image.new("RGB", (sum(t.width for t in tiles) + 5 * 3, tiles[0].height), (12, 12, 14))
        x = 0
        for t in tiles:
            strip.paste(t, (x, 0))
            x += t.width + 5
        strip.save(os.path.join(out, f"{name}_shutter.png"))
        written += [f"{name}_flat.png", f"{name}_sheet.png", f"{name}_cyl.png", f"{name}_shutter.png"]
    if a.gif:
        frames = []
        for i in range(anim.n):
            fl = render_flat(anim.rgb(i), scale=a.scale)
            cy = render_cylinder(ideal(anim, i, pal_lin), cam)
            frames.append(compose(fl, cy, cap_l, "what a viewer sees (ideal persistence)", a.width))
        p = os.path.join(out, f"{name}_sim.gif")
        write_gif(frames, p, anim.fps)
        written.append(p)
    if a.mp4:
        if not FFMPEG:
            print("ffmpeg not found: skipping MP4")
        else:
            n = int(round(a.seconds * 30))
            frames = []
            for k in range(n):
                t0 = k / 30.0
                cam_k = Camera(width=a.width // 2 - 20, height=int(a.width * 0.45), yaw_deg=a.yaw + a.orbit_camera * t0)
                tick = 1.0 / refresh_hz(a.rpm)
                fi = int(t0 // (frame_hold_ticks(anim.fps, a.rpm) * tick)) % anim.n
                fl = render_flat(anim.rgb(fi), scale=a.scale)
                cy = render_cylinder(exposure(anim, t0, 1 / 30.0, a.rpm, pal_lin), cam_k)
                frames.append(compose(fl, cy, cap_l, cap_r, a.width))
            p = os.path.join(out, f"{name}_sim.mp4")
            write_mp4(frames, p)
            written.append(p)
    print("written:", *written, sep="\n  ")


if __name__ == "__main__":
    main()
