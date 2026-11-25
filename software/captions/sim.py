"""Fast camera-model preview of caption frames on the spinning column (for the live window and MP4 renders).

Uses povsim's geometry (Camera.project: pinhole camera on the column's equator, lambertian fall-off, LED dash size)
and its persistence model (strip s of a row's set paints column c at ((c - 4 s) mod 96) * T/96 + m T), but
precomputes the projection as a sparse matrix so a 600 x 520 view renders in a few milliseconds instead of ~0.2 s.

Caption content changes with time, so exposure() takes a function tick_index -> linear frame: the column swaps its
frame buffer on refresh ticks (1/8 revolution = 1/30 s at 225 rpm), and a camera exposure that straddles a tick shows
part of the old and part of the new frame (that is the 33-67 ms "frame swap" term in the latency budget).
"""
from __future__ import annotations

import math
import os
import sys

import cv2
import numpy as np
from scipy import sparse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "povsim"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "povgen"))
from povanim import COLS, GAMMA, N_SETS, ROWS, RPM_DEFAULT, rev_period_s  # noqa: E402
from simulate import Camera  # noqa: E402


class FastCylinder:
    def __init__(self, width=600, height=520, yaw_deg=0.0, dist_mm=900.0, fill=0.78, bloom=True, ss=2):
        cam = Camera(width=width, height=height, dist_mm=dist_mm, yaw_deg=yaw_deg, fill=fill)
        self.W, self.H, self.bloom = width, height, bloom
        u, v, cos_e, w_px, h_px = cam.project()
        rows, cols, vals = [], [], []
        # soft-edged ellipse footprint per pixel, super-sampled ss x ss for smooth edges
        for r in range(ROWS):
            for c in range(COLS):
                if cos_e[c] <= 0.02:
                    continue
                x, y, a, b = u[r, c], v[r, c], w_px[c] / 2, h_px[c] / 2
                x0, x1 = int(math.floor(x - a)), int(math.ceil(x + a))
                y0, y1 = int(math.floor(y - b)), int(math.ceil(y + b))
                for py in range(max(0, y0), min(height, y1 + 1)):
                    for px in range(max(0, x0), min(width, x1 + 1)):
                        cov = 0.0
                        for sy in range(ss):
                            for sx in range(ss):
                                dx = (px + (sx + 0.5) / ss - 0.5 - x) / max(a, 0.5)
                                dy = (py + (sy + 0.5) / ss - 0.5 - y) / max(b, 0.5)
                                cov += dx * dx + dy * dy <= 1.0
                        if cov:
                            rows.append(py * width + px)
                            cols.append(r * COLS + c)
                            vals.append(cos_e[c] * cov / (ss * ss))
        self.M = sparse.csr_matrix((vals, (rows, cols)), shape=(width * height, ROWS * COLS), dtype=np.float32)
        # the faint tube outline, as in povsim
        from PIL import Image, ImageDraw
        bg = Image.new("RGB", (width, height), (0, 0, 0))
        cam.outline(ImageDraw.Draw(bg))
        self.bg = np.asarray(bg).astype(np.float32)

    def render(self, lin: np.ndarray) -> np.ndarray:
        """lin: (42, 96, 3) linear light (1.0 = full) -> (H, W, 3) uint8 RGB."""
        img = self.M @ lin.reshape(ROWS * COLS, 3).astype(np.float32)
        img = 255.0 * np.clip(img, 0, 1) ** (1 / GAMMA)
        img = img.reshape(self.H, self.W, 3)
        img = np.maximum(img, self.bg)
        if self.bloom:
            b1 = cv2.GaussianBlur(img, (0, 0), 3)
            b2 = cv2.GaussianBlur(img, (0, 0), 9)
            img = img + 0.45 * b1 + 0.25 * b2
        return np.clip(img, 0, 255).astype(np.uint8)


def paint_times(rpm: float = RPM_DEFAULT) -> np.ndarray:
    T = rev_period_s(rpm)
    r = np.arange(ROWS)[:, None]
    c = np.arange(COLS)[None, :]
    s = (r % N_SETS)[None, :, :] + 3 * np.arange(8)[:, None, None]
    return ((c[None] - 4 * s) % COLS) * (T / COLS)


_PT = {}


def exposure(frame_lin_at_tick, t0: float, tau: float = 1 / 30, rpm: float = RPM_DEFAULT,
             tick_phase: float = 0.0) -> np.ndarray:
    """Linear light a camera integrates over [t0, t0+tau]. frame_lin_at_tick(k) -> (42, 96, 3) for tick k, where tick
    k covers [k*tick + tick_phase, (k+1)*tick + tick_phase) (tick = T/8, the frame buffer swaps at tick starts)."""
    if rpm not in _PT:
        _PT[rpm] = paint_times(rpm)
    pt = _PT[rpm]
    T = rev_period_s(rpm)
    t_col, tick = T / COLS, T / 8
    out = np.zeros((ROWS, COLS, 3))
    rr = np.arange(ROWS)[None, :, None]
    cc = np.arange(COLS)[None, None, :]
    cache = {}
    for m in range(math.floor((t0 - T) / T), math.ceil((t0 + tau) / T) + 1):
        te = pt + m * T
        ov = np.clip(np.minimum(t0 + tau, te + t_col) - np.maximum(t0, te), 0, None) / t_col
        if not ov.any():
            continue
        ki = np.floor((te - tick_phase) / tick).astype(int)
        for k in np.unique(ki[ov > 0]):
            if k not in cache:
                cache[k] = frame_lin_at_tick(int(k))
            sel = (ki == k) * ov                                     # (8, 42, 96)
            out += (cache[k] * sel.sum(axis=0)[..., None])
    return out


def to_lin(rgb: np.ndarray) -> np.ndarray:
    return (rgb.astype(np.float32) / 255.0) ** GAMMA
