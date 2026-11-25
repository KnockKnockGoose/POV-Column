"""An original cartoon bichon frise head for the 42 x 96 POV column, plus a sunset backdrop and a pair of sunglasses.

Generic cartoon dog (no name on screen, no third-party IP). Used by content/public/bichon_shades_{front,orbit}.py;
reusable for any other bichon scene (call draw_bichon on a Canvas-sized index array).

Design notes (why it looks like this at 42 rows):
  * A white "cloud" head: one disc plus twelve puffs round the rim and two hanging ear lobes, all unioned into one
    silhouette, then ringed with a 1-pixel OFF outline. On an LED display black is "LED off", so the outline is
    free current-wise and it is what lets white fur read against a coloured sky.
  * Volume from three fur tones only: lavender shadow on the side away from the low sun, a warm rim light on the
    sun side, and fixed curl marks (seeded, in head-local coordinates, so they never flicker).
  * Head turn = features on a sphere: eyes, nose and muzzle sit at (longitude, latitude) and move with sin(lon + yaw);
    the nose sits on a bigger radius than the eyes, so it travels further (parallax sells the turn at 3 px/eye).
  * Sunglasses: solid OFF lenses (they read on white fur), a bright top bar and a sunset reflection streak so they
    also read over the dark sky, and a glint band that sweeps the lenses once.
Rows count up from the bottom (row 0 = bottom LED row), columns wrap round the cylinder.
"""
from __future__ import annotations

import math

import numpy as np

from povanim import COL_ARC_MM, COLS, ROW_PITCH_MM, ROWS, Palette

KX = ROW_PITCH_MM / COL_ARC_MM          # 1.06 columns per row of height: pixels are 5.24 mm wide x 5.56 mm tall
RH = 12.5                                # head radius in rows
HORIZON = 8                              # sea below, sky above

SKY = [  # (first row, colour) from the horizon up; dim on purpose: the white head must be the brightest thing
    (HORIZON + 1, "sky_gold", (235, 125, 35)),
    (HORIZON + 4, "sky_orange", (200, 75, 32)),
    (HORIZON + 8, "sky_rose", (165, 42, 70)),
    (HORIZON + 14, "sky_magenta", (105, 22, 88)),
    (HORIZON + 20, "sky_purple", (55, 12, 82)),
    (HORIZON + 26, "sky_indigo", (22, 6, 55)),
]


def make_palette() -> tuple[Palette, dict]:
    pal = Palette()
    c = {"off": 0}
    for _, name, rgb in SKY:
        c[name] = pal.add(name, rgb)
    for name, rgb in [
        ("sea", (24, 8, 42)), ("shimmer", (200, 90, 40)), ("sun", (255, 205, 90)), ("sun_core", (255, 240, 170)),
        ("fur", (205, 205, 218)), ("fur_shade", (125, 120, 175)), ("fur_deep", (95, 90, 135)),
        ("fur_rim", (245, 190, 140)), ("muzzle", (232, 224, 208)), ("eye_hi", (255, 255, 255)),
        ("tongue", (255, 90, 130)),
        ("shade_rim", (120, 215, 255)), ("lens_refl", (190, 80, 45)), ("glint", (255, 255, 255)),
        ("sparkle", (255, 235, 90)),
    ]:
        c[name] = pal.add(name, rgb)
    return pal, c


# ---------------------------------------------------------------- grids
_RR, _CC = np.mgrid[0:ROWS, 0:COLS]


def _rel(hc: int, hr: float):
    """Column and row offsets of every pixel from (hr, hc); columns wrap the cylinder (-48..47)."""
    dx = ((_CC - hc + COLS // 2) % COLS) - COLS // 2
    dy = _RR - hr
    return dx.astype(float), dy.astype(float)


def _ell(dx, dy, cx, cy, rx, ry):
    return ((dx - cx) / rx) ** 2 + ((dy - cy) / ry) ** 2 <= 1.0


def _ring(mask: np.ndarray) -> np.ndarray:
    """Pixels outside `mask` with a 4-neighbour inside it (columns wrap, rows clip)."""
    n = np.zeros_like(mask)
    n |= np.roll(mask, 1, 1) | np.roll(mask, -1, 1)
    n[1:] |= mask[:-1]
    n[:-1] |= mask[1:]
    return n & ~mask


def _put(a, r, c, ci):
    r, c = int(round(r)), int(round(c))
    if 0 <= r < ROWS:
        a[r, c % COLS] = ci


# ---------------------------------------------------------------- backdrop
def draw_sunset(a: np.ndarray, c: dict, sun_col: int = 66) -> None:
    """Sky bands over the full circumference, a half-set sun at `sun_col` and a dark sea with a static shimmer."""
    a[:] = c["sea"]
    for r0, name, _ in SKY:
        a[r0:] = c[name]
    dx, dy = _rel(sun_col, HORIZON + 1)
    disc = (dx / (5.0 * KX)) ** 2 + (dy / 5.0) ** 2 <= 1.0
    a[disc & (_RR > HORIZON)] = c["sun"]
    a[((dx / (3.0 * KX)) ** 2 + (dy / 3.0) ** 2 <= 1.0) & (_RR > HORIZON)] = c["sun_core"]
    for r, segs in ((7, (-5, -4, -1, 0, 1)), (5, (-2, -1, 2, 3)), (3, (-1, 0)), (1, (1,))):  # glitter under the sun
        for k in segs:
            _put(a, r, sun_col + k, c["shimmer"])


# ---------------------------------------------------------------- the dog
_RNG = np.random.default_rng(7)
_CURLS = []                                 # fixed curl marks (head-local), outer ring only so the face stays clean
while len(_CURLS) < 11:
    ang, rad = _RNG.uniform(0, 2 * math.pi), _RNG.uniform(0.62, 0.9) * RH
    _CURLS.append((rad * math.cos(ang) * KX, rad * math.sin(ang), int(_RNG.integers(0, 2))))


def _sphere(lon, lat, radius, yaw):
    """Screen offset (cols, rows) and facing (cos) of a feature on the head sphere after turning by `yaw` (rad)."""
    th = lon + yaw
    return radius * KX * math.sin(th) * math.cos(lat), radius * math.sin(lat), math.cos(th) * math.cos(lat)


def face_points(yaw: float) -> dict:
    """Head-local positions of the features for a given yaw (0 = facing the viewer, + = looking to viewer's right)."""
    el = _sphere(-0.36, 0.2, RH, yaw)
    er = _sphere(0.36, 0.2, RH, yaw)
    nose = _sphere(0.0, -0.24, RH + 2.0, yaw)
    muz = _sphere(0.0, -0.3, RH + 0.5, yaw)
    mid = _sphere(0.0, 0.2, RH + 0.8, yaw)
    return dict(eye_l=el, eye_r=er, nose=nose, muzzle=muz, glasses=mid)


def draw_bichon(a: np.ndarray, c: dict, hc: int, hr: float = 25.0, yaw: float = 0.0, blink: bool = False,
                squint: bool = False, smirk: bool = False, chest: bool = True) -> dict:
    """Draw the head (and chest fluff) centred at row hr, column hc. Returns the feature positions (absolute)."""
    dx, dy = _rel(hc, hr)
    fp = face_points(yaw)
    # --- silhouette: head disc + rim puffs + ear lobes + muzzle bulge (+ chest below)
    head = _ell(dx, dy, 0, 0, (RH - 0.4) * KX, RH - 0.4)
    for k in range(12):
        t = k * math.pi / 6 + 0.26
        head |= _ell(dx, dy, (RH - 1.6) * KX * math.cos(t), (RH - 1.6) * math.sin(t), 3.3 * KX, 3.2)
    ears = []
    for lon in (-1.2, 1.2):
        ex = RH * 0.92 * KX * math.sin(lon + 0.55 * yaw)
        e = _ell(dx, dy, ex, -4.5, 5.0, 7.4)
        e |= _ell(dx, dy, ex * 1.04, -10.0, 3.6, 2.6)                                     # fluffy ear tip
        ears.append(e)
        head |= e
    mx, my, _ = fp["muzzle"]
    muzzle = _ell(dx, dy, mx, my, 5.6, 4.1)
    head |= muzzle
    body = np.zeros_like(head)
    if chest:
        body = _ell(dx, dy, 0, -28.0, 15.5 * KX, 13.0) | _ell(dx, dy, 0, -11.5, 9.5 * KX, 4.5)
        for k in (-2, -1, 0, 1, 2):                                                       # scalloped bib edge
            body |= _ell(dx, dy, 4.4 * k * KX, -14.6 - 0.5 * abs(k), 2.4 * KX, 2.2)
    sil = head | body
    # --- fill + shading (light: the low sun on the viewer's right)
    a[sil] = c["fur"]
    nx, ny = dx / (RH * KX), dy / RH
    rr = np.sqrt(nx ** 2 + ny ** 2)
    lx, ly = 0.92, 0.38
    nd = (nx * lx + ny * ly) / np.maximum(rr, 1e-6)
    a[head & (nd < -0.5) & (rr > 0.8)] = c["fur_shade"]
    a[head & (nd > 0.62) & (rr > 0.9)] = c["fur_rim"]
    if chest:
        bx, by = dx / (15.5 * KX), (dy + 28.0) / 13.0
        a[body & ~head & (bx < -0.62)] = c["fur_shade"]
        under = body & ~head & np.roll(head, 2, axis=0)                                   # shadow under the chin
        under[:2] = False
        a[under] = c["fur_shade"]
        a[body & ~head & (bx > 0.68) & (by > -0.4)] = c["fur_rim"]
    for ear, lon in zip(ears, (-1.2, 1.2)):                                               # ear seam: an inner arc
        seam = _ring(ear) & head & ~ears[1 - (lon > 0)] & ~muzzle & (dy < -1.0) & (dy > -9.5)
        a[seam] = c["fur_shade"]
    for cx_, cy_, kind in _CURLS:                                                          # curls
        r0, c0 = int(round(hr + cy_)), hc + int(round(cx_))
        for (ddr, ddc) in (((0, 0), (1, 1)) if kind else ((0, 0), (-1, 1))):
            rp, cp = r0 + ddr, c0 + ddc
            if 0 <= rp < ROWS and head[rp, cp % COLS] and not muzzle[rp, cp % COLS]:
                if a[rp, cp % COLS] == c["fur"]:
                    a[rp, cp % COLS] = c["fur_shade"]
                elif a[rp, cp % COLS] == c["fur_shade"]:
                    a[rp, cp % COLS] = c["fur_deep"]
    a[muzzle & (dy > my - 3.2)] = c["muzzle"]
    # --- outline
    a[_ring(sil)] = c["off"]
    if chest:                                                                             # chin line over the bib
        chin = _ring(head) & body
        a[chin] = c["fur_deep"]
    # --- eyes
    out = dict(hc=hc, hr=hr)
    for key, hi_side in (("eye_l", 1), ("eye_r", 1)):
        ex, ey, face = fp[key]
        if face < 0.12:
            continue
        w = 3 if face > 0.72 else 2
        c0 = hc + int(round(ex - (w - 1) / 2))
        r0 = int(round(hr + ey))
        if blink:
            for cc_ in range(c0 - 1, c0 + w + 1):
                _put(a, r0, cc_, c["fur_deep"])
            continue
        for rr_ in range(r0 - 1, r0 + 2):
            for cc_ in range(c0, c0 + w):
                _put(a, rr_, cc_, c["off"])
        if squint:
            for cc_ in range(c0 - 1, c0 + w + 1):
                _put(a, r0 + 1, cc_, c["fur_deep"])
            _put(a, r0, c0 + w - 1 if hi_side > 0 else c0, c["eye_hi"])
        else:
            _put(a, r0 + 1, c0 + w - 1 if hi_side > 0 else c0, c["eye_hi"])
        out[key] = (r0, c0, w)
    # --- nose + mouth
    nx_, ny_, _ = fp["nose"]
    ncol, nrow = hc + int(round(nx_)), int(round(hr + ny_))
    for cc_ in range(ncol - 2, ncol + 2):
        _put(a, nrow, cc_, c["off"])
        _put(a, nrow - 1, cc_, c["off"])
    _put(a, nrow - 2, ncol - 1, c["off"])
    _put(a, nrow - 2, ncol, c["off"])
    _put(a, nrow, ncol + 1, c["eye_hi"])
    _put(a, nrow - 3, ncol, c["fur_deep"])
    for k in (-2, -1, 1, 2):
        _put(a, nrow - 4, ncol + k, c["fur_deep"])
    if smirk:
        _put(a, nrow - 3, ncol + 3, c["fur_deep"])
        _put(a, nrow - 4, ncol + 2, c["off"])
    out.update(nose=(nrow, ncol))
    gx, gy, _ = fp["glasses"]
    out["glasses"] = (hr + gy, hc + gx)
    out["head_mask"] = head
    return out


# ---------------------------------------------------------------- sunglasses + paw
LENS_ROWS = {1: (-10, -2), 0: (-10, -2), -1: (-10, -3), -2: (-9, -4)}   # row offset -> (col from, col to), left lens


def draw_shades(a: np.ndarray, c: dict, gr: float, gc: float, squash: float = 1.0, tilt: int = 0,
                glint: float | None = None, sparkle: int = 0) -> None:
    """Sunglasses centred at (gr, gc) (the eye line). squash < 1 narrows them for a turned head; tilt raises the right
    half by that many rows (held from the right by the paw). glint = position (cols) of the sweeping highlight band."""
    gr_i, gc_i = int(round(gr)), int(round(gc))

    def col(x):
        return gc_i + int(round(x * squash))

    lens = []
    for side in (-1, 1):
        t = tilt if side > 0 else 0
        for dr, (c0, c1) in LENS_ROWS.items():
            lo, hi = (c0, c1) if side < 0 else (-c1, -c0)
            for x in range(col(lo), col(hi) + 1):
                lens.append((gr_i + dr + t, x, x - gc_i, dr))
                _put(a, gr_i + dr + t, x, c["off"])
        # reflection streak (sunset in the lens), upper inner part of each lens
        x0 = col(-8 if side < 0 else 4)
        _put(a, gr_i + 1 + t, x0, c["lens_refl"])
        _put(a, gr_i + t, x0 + 1, c["lens_refl"])
        # arm towards the ear
        for k in (11, 12):
            _put(a, gr_i + 2 + t, col(side * k), c["off"])
        _put(a, gr_i + 3 + t, col(side * 13), c["off"])
    for x in range(col(-11), col(11) + 1):                                   # bright top bar = frame
        _put(a, gr_i + 2 + (tilt if x > gc_i else 0), x, c["shade_rim"])
    for x in (col(-1), gc_i, col(1)):                                         # bridge
        _put(a, gr_i + 1 + (tilt if x > gc_i else 0), x, c["off"])
    if glint is not None:
        for (r, x, dxl, dr) in lens:
            if abs((dxl / max(squash, 0.3)) + 0.9 * dr - glint) <= 0.8:
                _put(a, r, x, c["glint"])
    if sparkle:
        sr, sc = gr_i + 2 + tilt, col(11)
        for k in range(-sparkle, sparkle + 1):
            _put(a, sr + k, sc, c["sparkle"])
            _put(a, sr, sc + k, c["sparkle"])


def draw_paw(a: np.ndarray, c: dict, pr: float, pc: float) -> None:
    """A fluffy forepaw whose toes are at (pr, pc), with its leg running down out of the bottom of the frame."""
    dx, dy = _rel(int(round(pc)), pr)
    paw = _ell(dx, dy, 0, 0, 4.6, 2.6)
    leg = (np.abs(dx) <= 2.6) & (dy < 0)
    for k in (-1, 0, 1):                                                     # three toe bumps
        paw |= _ell(dx, dy, 2.6 * k, 2.0, 1.45, 1.25)
    m = paw | leg
    a[m] = c["fur"]
    a[m & (dx < -1.5) & (dy < 1)] = c["fur_shade"]
    a[m & (dx > 2.4) & (dy > -6) & (dy < 2)] = c["fur_rim"]
    for k in (-1, 1):                                                        # toe separations
        _put(a, pr + 2, pc + k * 1.3, c["off"])
        _put(a, pr + 1, pc + k * 1.3, c["fur_deep"])
    a[_ring(m)] = c["off"]


def iris(a: np.ndarray, r: float, c: float, radius: float) -> None:
    """Classic cartoon iris: everything outside a circle of `radius` rows round (r, c) goes dark."""
    dx, dy = _rel(int(round(c)), r)
    a[(dx / KX) ** 2 + dy ** 2 > radius ** 2] = 0


def ease(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def ease_out(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 2
