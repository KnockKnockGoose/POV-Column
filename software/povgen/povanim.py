"""povanim: a tiny sprite/animation DSL for the POV LED Column (v2 hardware: 42 rows x 96 columns on a cylinder).

Prototype for the software report (docs/2026-11-02-software-and-ai-content.md). It is the single source of truth for:
  * the display geometry and the LED -> (row, column-offset) mapping (24 SK9822 strips, 3 interleaved sets, 2 serpentine
    SPI chains, odd strips mounted upside down), exported to the firmware as povmap.h;
  * the drawing primitives an LLM-written "scene script" may use (Canvas, Sprite from text grids, Palette);
  * the .pova animation file format (header + JSON meta + palette + RLE frames + CRC32) and its JSON sidecar;
  * the validator (loop seam, instantaneous current at the chosen global brightness, front-window framing, flicker).

Conventions: row 0 is the BOTTOM LED row (set A, LED0 at z 11.11 mm); column c is the image column that sits at spatial angle
3.75 deg * c from the hall-pulse reference; column 48 faces the viewer by convention (the ESP32's offset trim rotates the
whole image). Colours in a file are sRGB 0-255; the ESP32 applies gamma and the 5-bit SK9822 current field.
"""
from __future__ import annotations

import json
import math
import struct
import time
import zlib
from dataclasses import dataclass, field

import numpy as np

# ---------------------------------------------------------------- display geometry (from docs/2026-11-02-v2-24-strips-tie-rods.md)
ROWS, COLS = 42, 96
N_STRIPS, N_SETS, LEDS_PER_STRIP, N_CHAINS = 24, 3, 14, 2
STRIPS_PER_CHAIN = N_STRIPS // N_CHAINS            # 12
LEDS_PER_CHAIN = STRIPS_PER_CHAIN * LEDS_PER_STRIP  # 168
COLS_PER_STRIP = COLS // N_STRIPS                   # 4 columns per 15 deg strip step
K_PASSES = N_STRIPS // N_SETS                       # 8 strips share every row -> refresh = 8 x f_rot
FRONT_CENTRE, FRONT_WIDTH = 48, 32                  # the viewer's window: columns 32..63 (+-60 deg)
R_TUBE_MM, R_LED_MM, H_TUBE_MM = 80.0, 82.0, 250.0
LED_PITCH_MM = 1000.0 / 60.0
ROW_PITCH_MM = LED_PITCH_MM / N_SETS                # 5.556
Z0_MM = 11.11                                       # row 0 centre height above the tube bottom
COL_ARC_MM = 2 * math.pi * R_TUBE_MM / COLS         # 5.24
LED_BODY_MM = 5.0
RPM_DEFAULT = 225.0
GAMMA = 2.2
I_CH_MA, I_DARK_MA, I_ESP_MA = 20.0, 1.0, 120.0     # per channel at full, per LED idle, controller
CAP_MA = 2600.0                                     # FastLED-style cap, LEDs incl. dark current: INIU USB-A port label 5 V 3 A (2026-11-03; + 0.12 A ESP32 = 2.72 A, 9 % headroom; was 2000 for the listed 2.4 A)

POVA_MAGIC, POVA_VERSION = b"POVA", 1
FLAG_LOOP, FLAG_RLE = 0x01, 0x02


def rev_period_s(rpm: float = RPM_DEFAULT) -> float:
    return 60.0 / rpm


def column_time_s(rpm: float = RPM_DEFAULT) -> float:
    return rev_period_s(rpm) / COLS


def refresh_hz(rpm: float = RPM_DEFAULT) -> float:
    return K_PASSES * rpm / 60.0


# ---------------------------------------------------------------- LED mapping (firmware single source of truth)
# As built (2026-11-12): the strips sit one rail back from the design, so strip 0 is in a set-C rail (its bottom slot is the
# highest of the three) and strip s is in set (s + 2) % 3. The whole column is just rotated 15 deg (absorbed by the hall
# offset trim); only the row interleave changes. Set 0 to return to the design numbering (strip 0 in set A).
SET_SHIFT = 2


def strip_set(s: int) -> int:
    """Interleave set of strip s: A=0, B=1, C=2 (set offsets p/3 = 5.556 mm), including the as-built SET_SHIFT."""
    return (s + SET_SHIFT) % N_SETS


def chain_of(s: int) -> int:
    return s // STRIPS_PER_CHAIN


def led_row(s: int, i: int) -> int:
    """Image row shown by LED i (index along the data direction) of strip s. Odd strips are mounted upside down
    (data in at the top), so their index is reversed: v2 report section 9 item 5."""
    k = i if s % 2 == 0 else LEDS_PER_STRIP - 1 - i
    return N_SETS * k + strip_set(s)


def strip_col_offset(s: int) -> int:
    """Strip s sits 15 deg * s ahead of strip 0, i.e. 4 columns per strip at M = 96."""
    return COLS_PER_STRIP * s


def ledmap() -> list[dict]:
    """One entry per LED in chain order: chain c, position k (0..167), strip, led index, row, column offset."""
    out = []
    for c in range(N_CHAINS):
        for pos in range(LEDS_PER_CHAIN):
            s = c * STRIPS_PER_CHAIN + pos // LEDS_PER_STRIP
            i = pos % LEDS_PER_STRIP
            out.append(dict(chain=c, pos=pos, strip=s, led=i, set=strip_set(s), row=led_row(s, i),
                            col_off=strip_col_offset(s)))
    return out


def ledmap_arrays() -> tuple[np.ndarray, np.ndarray]:
    """(rows, col_offs) as (N_CHAINS, LEDS_PER_CHAIN) int arrays."""
    rows = np.zeros((N_CHAINS, LEDS_PER_CHAIN), dtype=np.int16)
    offs = np.zeros((N_CHAINS, LEDS_PER_CHAIN), dtype=np.int16)
    for e in ledmap():
        rows[e["chain"], e["pos"]] = e["row"]
        offs[e["chain"], e["pos"]] = e["col_off"]
    return rows, offs


def column_indices(frame: np.ndarray, col: int, offset: int = 0) -> np.ndarray:
    """Palette indices the two chains must show when strip 0 points at image column `col` (shape (2, 168))."""
    rows, offs = ledmap_arrays()
    return frame[rows, (col + offs + offset) % COLS]


def write_povmap_header(path) -> None:
    """Emit povmap.h for the firmware: row and column offset per (chain, pos), plus the constants."""
    rows, offs = ledmap_arrays()
    lines = ["// Generated by software/povgen/povanim.py - do not edit by hand.",
             "#pragma once", "#include <stdint.h>",
             f"#define POV_ROWS {ROWS}", f"#define POV_COLS {COLS}", f"#define POV_CHAINS {N_CHAINS}",
             f"#define POV_LEDS_PER_CHAIN {LEDS_PER_CHAIN}", f"#define POV_STRIPS {N_STRIPS}",
             f"#define POV_COLS_PER_STRIP {COLS_PER_STRIP}", f"#define POV_K_PASSES {K_PASSES}",
             f"#define POV_SET_SHIFT {SET_SHIFT}",
             "// row shown by LED pos of each chain",
             "static const uint8_t POV_LED_ROW[POV_CHAINS][POV_LEDS_PER_CHAIN] = {"]
    for c in range(N_CHAINS):
        lines.append("  {" + ", ".join(str(int(v)) for v in rows[c]) + "},")
    lines += ["};", "// column offset (added to the current column index) of the strip that LED pos belongs to",
              "static const uint8_t POV_LED_COLOFF[POV_CHAINS][POV_LEDS_PER_CHAIN] = {"]
    for c in range(N_CHAINS):
        lines.append("  {" + ", ".join(str(int(v)) for v in offs[c]) + "},")
    lines.append("};")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------- colour helpers
def gamma_lut(gamma: float = GAMMA) -> np.ndarray:
    v = np.arange(256) / 255.0
    return np.clip(np.round(255 * v ** gamma), 0, 255).astype(np.uint8)


def pixel_current_ma(rgb: np.ndarray, gb: int = 31, gamma: float = GAMMA) -> np.ndarray:
    """LED current (mA, without the 1 mA idle term) for sRGB colours (..., 3) at 5-bit global brightness gb.
    SK9822: current ~ duty (8-bit PWM of the gamma-corrected value) x (gb / 31)."""
    duty = (np.asarray(rgb, dtype=np.float64) / 255.0) ** gamma
    return I_CH_MA * duty.sum(axis=-1) * (gb / 31.0)


# ---------------------------------------------------------------- palette, sprites, canvas
class Palette:
    """Index 0 is always 'off' (black). Up to 255 named colours."""

    def __init__(self):
        self.names = ["off"]
        self.rgb = [(0, 0, 0)]

    def add(self, name: str, rgb) -> int:
        if name in self.names:
            return self.names.index(name)
        if len(self.names) >= 255:
            raise ValueError("palette full")
        self.names.append(name)
        self.rgb.append(tuple(int(v) for v in rgb))
        return len(self.names) - 1

    def __getitem__(self, name: str) -> int:
        return self.names.index(name)

    def __len__(self):
        return len(self.names)

    def array(self) -> np.ndarray:
        return np.array(self.rgb, dtype=np.uint8)


@dataclass
class Sprite:
    """A small image with transparency, authored as a text grid (top row first). -1 = transparent."""
    data: np.ndarray  # (h, w) int16, top row first

    @classmethod
    def from_text(cls, rows: list[str], legend: dict[str, int], transparent: str = ". ") -> "Sprite":
        w = max(len(r) for r in rows)
        data = np.full((len(rows), w), -1, dtype=np.int16)
        for y, line in enumerate(rows):
            for x, ch in enumerate(line):
                if ch in transparent:
                    continue
                if ch not in legend:
                    raise KeyError(f"sprite char {ch!r} not in legend")
                data[y, x] = legend[ch]
        return cls(data)

    @property
    def h(self):
        return self.data.shape[0]

    @property
    def w(self):
        return self.data.shape[1]

    def flipped(self) -> "Sprite":
        return Sprite(self.data[:, ::-1].copy())


class Canvas:
    """42 x 96 palette-index image. Columns wrap (it is a cylinder); rows clip. row 0 = bottom."""

    def __init__(self, fill: int = 0):
        self.a = np.full((ROWS, COLS), fill, dtype=np.uint8)

    def copy(self) -> np.ndarray:
        return self.a.copy()

    def px(self, r, c, ci: int) -> None:
        r, c = int(round(r)), int(round(c))
        if 0 <= r < ROWS:
            self.a[r, c % COLS] = ci

    def rect(self, r0, c0, h, w, ci: int) -> None:
        for r in range(int(r0), int(r0) + int(h)):
            for c in range(int(c0), int(c0) + int(w)):
                self.px(r, c, ci)

    def hline(self, r, c0, c1, ci: int, dash: int = 0, phase: int = 0) -> None:
        for c in range(int(c0), int(c1) + 1):
            if dash and ((c + phase) // dash) % 2:
                continue
            self.px(r, c, ci)

    def line(self, r0, c0, r1, c1, ci: int, thick: int = 1) -> None:
        """Bresenham in (col, row); thick=2 doubles the line one row up / one column right."""
        x0, y0, x1, y1 = int(round(c0)), int(round(r0)), int(round(c1)), int(round(r1))
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx + dy
        while True:
            self.px(y0, x0, ci)
            if thick > 1:
                if dx >= -dy:
                    self.px(y0 + 1, x0, ci)
                else:
                    self.px(y0, x0 + 1, ci)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def ellipse(self, rc, cc, rr, rcol, ci: int) -> None:
        """Filled ellipse centred (rc, cc) with radii rr (rows) and rcol (columns)."""
        for r in range(int(math.floor(rc - rr)), int(math.ceil(rc + rr)) + 1):
            for c in range(int(math.floor(cc - rcol)), int(math.ceil(cc + rcol)) + 1):
                if ((r - rc) / rr) ** 2 + ((c - cc) / rcol) ** 2 <= 1.0:
                    self.px(r, c, ci)

    def disc(self, rc, cc, radius, ci: int) -> None:
        # pixels are 5.24 x 5.56 mm: nearly square, so one radius is fine for a ball
        self.ellipse(rc, cc, radius, radius * (ROW_PITCH_MM / COL_ARC_MM), ci)

    def blit(self, sp: Sprite, r_bottom, c_left, flip: bool = False) -> None:
        """Place a sprite with its bottom-left pixel at (r_bottom, c_left)."""
        d = sp.data[:, ::-1] if flip else sp.data
        h, w = d.shape
        for y in range(h):
            r = int(r_bottom) + h - 1 - y
            if not 0 <= r < ROWS:
                continue
            for x in range(w):
                v = d[y, x]
                if v >= 0:
                    self.a[r, (int(c_left) + x) % COLS] = v

    def shift(self, cols: int) -> None:
        """Rotate the whole image around the cylinder."""
        self.a = np.roll(self.a, int(cols), axis=1)


# ---------------------------------------------------------------- animation + file format
def rle_encode(idx: np.ndarray) -> bytes:
    flat = np.asarray(idx, dtype=np.uint8).ravel()
    out = bytearray()
    n = len(flat)
    i = 0
    while i < n:
        v = flat[i]
        run = 1
        while i + run < n and flat[i + run] == v and run < 255:
            run += 1
        out += bytes((run, int(v)))
        i += run
    return bytes(out)


def rle_decode(data: bytes, count: int) -> np.ndarray:
    out = np.empty(count, dtype=np.uint8)
    pos = 0
    for k in range(0, len(data), 2):
        run, v = data[k], data[k + 1]
        out[pos:pos + run] = v
        pos += run
    if pos != count:
        raise ValueError(f"RLE decoded {pos} of {count} pixels")
    return out


@dataclass
class Animation:
    palette: Palette
    fps: float = 7.5
    loop: bool = True
    name: str = "anim"
    meta: dict = field(default_factory=dict)
    frames: list = field(default_factory=list)   # uint8 (ROWS, COLS)
    holds: list = field(default_factory=list)    # frame hold multipliers (1 = one frame period)

    def add(self, frame, hold: int = 1) -> None:
        a = frame.a if isinstance(frame, Canvas) else np.asarray(frame)
        if a.shape != (ROWS, COLS):
            raise ValueError(f"frame must be {ROWS}x{COLS}, got {a.shape}")
        self.frames.append(a.astype(np.uint8).copy())
        self.holds.append(int(hold))

    @property
    def n(self):
        return len(self.frames)

    @property
    def duration_s(self):
        return sum(self.holds) / self.fps

    def rgb(self, i: int) -> np.ndarray:
        return self.palette.array()[self.frames[i]]

    def rgb_frames(self) -> np.ndarray:
        pal = self.palette.array()
        return np.stack([pal[f] for f in self.frames])

    # ---- .pova binary ----
    def to_bytes(self, rle: bool = True) -> bytes:
        meta = dict(self.meta)
        meta.setdefault("name", self.name)
        meta.setdefault("created", time.strftime("%Y-%m-%dT%H:%M:%S"))
        meta_b = json.dumps(meta, separators=(",", ":")).encode("utf-8")
        flags = (FLAG_LOOP if self.loop else 0) | (FLAG_RLE if rle else 0)
        pal = self.palette.array()
        out = bytearray()
        out += struct.pack("<4sBBBBHHBBH", POVA_MAGIC, POVA_VERSION, flags, ROWS, COLS, self.n,
                           int(round(self.fps * 10)), len(pal), 0, len(meta_b))
        out += meta_b
        out += pal.tobytes()
        for f, hold in zip(self.frames, self.holds):
            data = rle_encode(f) if rle else f.tobytes()
            out += struct.pack("<BBH", hold, 0, len(data))
            out += data
        out += struct.pack("<I", zlib.crc32(bytes(out)) & 0xFFFFFFFF)
        return bytes(out)

    def write(self, path, sidecar: bool = True, rle: bool = True) -> dict:
        path = str(path)
        data = self.to_bytes(rle=rle)
        with open(path, "wb") as f:
            f.write(data)
        info = dict(path=path, bytes=len(data), frames=self.n, fps=self.fps, loop=self.loop,
                    duration_s=round(self.duration_s, 3), palette=len(self.palette))
        if sidecar:
            side = dict(info, meta=self.meta, palette_names=self.palette.names, palette_rgb=self.palette.rgb)
            with open(path.rsplit(".", 1)[0] + ".json", "w", encoding="utf-8") as f:
                json.dump(side, f, indent=1)
        return info

    @classmethod
    def from_bytes(cls, data: bytes) -> "Animation":
        if len(data) < 20 or data[:4] != POVA_MAGIC:
            raise ValueError("not a POVA file")
        (crc,) = struct.unpack("<I", data[-4:])
        if zlib.crc32(data[:-4]) & 0xFFFFFFFF != crc:
            raise ValueError("POVA CRC mismatch")
        magic, ver, flags, rows, cols, n, fps10, npal, _res, meta_len = struct.unpack("<4sBBBBHHBBH", data[:16])
        if ver != POVA_VERSION or rows != ROWS or cols != COLS:
            raise ValueError(f"unsupported POVA v{ver} {rows}x{cols}")
        p = 16
        meta = json.loads(data[p:p + meta_len].decode("utf-8")) if meta_len else {}
        p += meta_len
        pal = Palette()
        rgb = np.frombuffer(data[p:p + 3 * npal], dtype=np.uint8).reshape(npal, 3)
        p += 3 * npal
        pal.names, pal.rgb = [f"c{i}" for i in range(npal)], [tuple(int(v) for v in row) for row in rgb]
        pal.names[0] = "off"
        anim = cls(pal, fps=fps10 / 10.0, loop=bool(flags & FLAG_LOOP), name=meta.get("name", "anim"), meta=meta)
        for _ in range(n):
            hold, _r, dlen = struct.unpack("<BBH", data[p:p + 4])
            p += 4
            raw = data[p:p + dlen]
            p += dlen
            idx = rle_decode(raw, ROWS * COLS) if flags & FLAG_RLE else np.frombuffer(raw, dtype=np.uint8)
            anim.add(idx.reshape(ROWS, COLS), hold)
        return anim

    @classmethod
    def read(cls, path) -> "Animation":
        with open(path, "rb") as f:
            return cls.from_bytes(f.read())


# ---------------------------------------------------------------- validator
def _blur(fr: np.ndarray, k_c: int = 7, k_r: int = 5) -> np.ndarray:
    """Separable box blur over (frames, rows, cols, 3); columns wrap (cylinder)."""
    out = np.zeros_like(fr)
    for dc in range(-(k_c // 2), k_c // 2 + 1):
        out += np.roll(fr, dc, axis=2)
    out2 = np.zeros_like(out)
    for dr in range(-(k_r // 2), k_r // 2 + 1):
        out2 += np.roll(out, dr, axis=1)
    return out2 / (k_c * k_r)


def current_profile(frame: np.ndarray, palette: np.ndarray, gb: int = 31) -> np.ndarray:
    """Instantaneous LED current (mA, incl. idle current and the ESP32) for each of the 96 rotor positions."""
    rows, offs = ledmap_arrays()
    cols = (np.arange(COLS)[:, None, None] + offs[None]) % COLS            # (96, 2, 168)
    idx = frame[rows[None], cols]                                           # (96, 2, 168)
    i_pix = pixel_current_ma(palette, gb)                                   # per palette entry
    return i_pix[idx].sum(axis=(1, 2)) + N_STRIPS * LEDS_PER_STRIP * I_DARK_MA + I_ESP_MA


def validate(anim: Animation, gb: int = 31, cap_ma: float = CAP_MA, mode: str = "front",
             window=(FRONT_CENTRE - FRONT_WIDTH // 2, FRONT_CENTRE + FRONT_WIDTH // 2)) -> dict:
    """Checks an animation against the display's physics and the content rules. Returns numbers + warnings."""
    pal = anim.palette.array()
    warn = []
    n = anim.n
    lit = np.array([(f != 0).mean() for f in anim.frames])
    prof = np.array([current_profile(f, pal, gb) for f in anim.frames])     # (n, 96)
    i_max, i_mean = float(prof.max()), float(prof.mean())
    scale = min(1.0, cap_ma / i_max) if i_max > 0 else 1.0
    gb_ok = int(math.floor(gb * scale))
    # loop seam: how different is last->first compared with the typical frame step. Frames are box-blurred first
    # (7 columns x 5 rows, wrapping around the cylinder) so a small motion step scores lower than a jump.
    # Two scales: fine (7 x 5) catches a pose jump inside a sprite, coarse (21 x 7) catches a position jump.
    raw = anim.rgb_frames().astype(np.float32)
    seam = typical = 0.0
    seam_ratio = 0.0
    for kc, kr in ((7, 5), (21, 7)):
        rgbf = _blur(raw, kc, kr)
        steps = [float(np.abs(rgbf[(i + 1) % n] - rgbf[i]).mean()) for i in range(n)] if n > 1 else [0.0]
        s_k, t_k = steps[-1], (float(np.median(steps[:-1])) if n > 2 else steps[-1])
        r_k = s_k / t_k if t_k > 1e-6 else (0.0 if s_k < 1e-6 else float("inf"))
        if r_k >= seam_ratio:
            seam, typical, seam_ratio = s_k, t_k, r_k
    if anim.loop and n > 2 and seam_ratio > 2.5 and seam > 0.3:
        warn.append(f"loop seam: last->first frame differs {seam_ratio:.1f}x more than a typical step")
    # framing: subject pixels = lit pixels in rows that are not background bands (ground line, dashes, stars:
    # rows lit across >= 45 % of the circumference)
    c_lo, c_hi = window
    in_win = []
    for f in anim.frames:
        on = f != 0
        subject_rows = on.sum(axis=1) < 0.45 * COLS
        subj = on & subject_rows[:, None]
        tot = subj.sum()
        in_win.append(1.0 if tot == 0 else float(subj[:, c_lo:c_hi].sum() / tot))
    in_win = np.array(in_win)
    if mode == "front" and in_win.min() < 0.9:
        warn.append(f"front mode but only {in_win.min() * 100:.0f} % of the subject's pixels are inside columns "
                    f"{c_lo}-{c_hi - 1}")
    # flicker: pixels toggling nearly every frame
    if n > 3:
        on = np.stack([f != 0 for f in anim.frames])
        toggles = (on != np.roll(on, 1, axis=0)).sum(axis=0)
        flick = int((toggles >= max(4, n - 2)).sum())
        if flick > 12:
            warn.append(f"{flick} pixels toggle on/off almost every frame (reads as noise on a POV display)")
    # thin diagonals / isolated pixels (smear risk) are a style note, not a failure
    iso = 0
    for f in anim.frames:
        on = (f != 0).astype(np.int8)
        nb = (np.roll(on, 1, 0) + np.roll(on, -1, 0) + np.roll(on, 1, 1) + np.roll(on, -1, 1))
        iso += int(((on == 1) & (nb == 0)).sum())
    if i_max > cap_ma:
        warn.append(f"peak current {i_max:.0f} mA > cap {cap_ma:.0f} mA at gb {gb}: scale to gb {gb_ok}")
    if len(anim.palette) > 32:
        warn.append(f"{len(anim.palette)} palette entries (> 32)")
    if n > 2 and anim.duration_s < 0.5:
        warn.append(f"very short loop ({anim.duration_s:.2f} s)")
    return dict(frames=n, fps=anim.fps, duration_s=round(anim.duration_s, 3), palette=len(anim.palette),
                lit_fraction_mean=round(float(lit.mean()), 4), lit_fraction_max=round(float(lit.max()), 4),
                current_mean_ma=round(i_mean), current_peak_ma=round(i_max), current_profile_ripple=round(
                    float((prof.max(axis=1) - prof.min(axis=1)).mean()), 1),
                cap_ma=cap_ma, gb=gb, gb_recommended=gb_ok, seam_rgb_delta=round(float(seam), 3),
                typical_step_rgb_delta=round(float(typical), 3), seam_ratio=round(float(seam_ratio), 2),
                front_window_fraction_min=round(float(in_win.min()), 3), isolated_pixels_total=iso,
                mode=mode, warnings=warn, ok=not warn)


def frame_hold_ticks(fps: float, rpm: float = RPM_DEFAULT) -> int:
    """The firmware advances frames on 1/8-revolution ticks (the refresh period); the nearest tick count >= 1."""
    tick = 1.0 / refresh_hz(rpm)
    return max(1, int(round((1.0 / fps) / tick)))
