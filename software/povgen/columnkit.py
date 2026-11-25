"""columnkit: the POV LED Column itself (rev o) as a prop the column can draw, for "the display showing itself".

Made 2026-11-23 for the POV-on-POV animations (software/content/public/pov_on_pov/). The column is drawn from the real
rev o dimensions in fusionclaude/lib/povlib.py (mm; z = 0 at the bottom of the tube, the rev k / rev o model frame),
seen from the front and a little above (ELEV_DEG), with a tiny ray caster:

  * every pixel is SS x SS samples; each sample's camera ray finds the nearest surface (D-shaped base with the speed
    knob, 6820 bearing collar, rotor ring, cap skirts, tube, top cap); the surface normal picks one of three shades (light
    from the upper left) and the pixel takes the majority material, so edges stay crisp pixel art;
  * the LED strips are NOT ray cast: like the real thing they are a POV display in miniature (`paint_rotor`). The drawn
    rotor carries 12 strips (the real one has 24: half density reads better at 17 columns wide) of 12 LED dots, the rotor
    angle is sampled K times per frame, and each LED lights with the colour of the picture at the screen point it is
    passing (ideal persistence: the mean over the frame). Slow: strips and dots slide round. Fast: the strips blur away
    and the picture appears, exactly as on the column.

Proportions kept: tube d160 x 250, cap skirts d168.8 x 7, rotor ring d182, collar/base d200 with the front flat at
y -90 (knob d15 at z -64), base 85.5 tall, 4 nyloc nuts on the top cap at r 60. Stylised: the drive zone between the base
and the tube (collar rim, bearing recess, rotor ring, skirt: 33 mm in all) is drawn 1.6 x taller so each ring gets a
whole pixel row, the strips are at half density, and the LED dots sit at a 2-pixel pitch.
"""
from __future__ import annotations

import math

import numpy as np

from povanim import COL_ARC_MM, COLS, FRONT_CENTRE, ROW_PITCH_MM, ROWS

# ---------------------------------------------------------------- rev o geometry, mm (povlib names in brackets)
TUBE_R = 80.0            # [R_OUT]
TUBE_TOP = 250.0         # [H_TUBE]
CAP_R = 84.4             # [SKIRT_IR 83.2 + SKIRT_T 1.2]
SKIRT_H = 7.0            # [SKIRT_H]
CAP_T = 2.0              # [CAP_T]
RING_R = 91.0            # rotor ring [RR_OR]
BOSS_R = 67.5            # collar boss round the 6820 [COL_BOSS_OR]
BASE_R = 100.0           # [BASE_R]
BASE_FLAT = 90.0         # front / back flats at y = -+90 [BASE_FLAT_Y]
BASE_TOP = -23.5         # deck top, rev k frame [DECK_TOP - K_DROP]
BASE_BOT = -109.0        # [BASE_Z_BOT - K_DROP]
COLLAR_RIM_TOP = -15.0   # collar plate 2.5 + rim 6 [COL_BASE_T, COL_RIM_H]
KNOB_Z, KNOB_R = -64.0, 7.5     # speed pot [POT_Z - K_DROP, KNOB_D / 2]
NUT_R, NUT_TOP = 60.0, 255.0    # tie-rod nylocs on the top cap [ROD_R; cap top 252 + 3 proud]
DRIVE_STRETCH = 2.0      # drive zone (BASE_TOP .. tube bottom + skirt) drawn this much taller (see the docstring)

STRIPS_DRAWN = 12        # every other one of the 24
LEDS_DRAWN = 12          # per drawn strip, 2 px pitch
TAU = 2 * math.pi


def _z(z: float) -> float:
    """Stretch the drive zone (BASE_TOP .. 5 mm up the tube) and shift everything above it up by the extra height."""
    lo, hi = BASE_TOP, SKIRT_H - CAP_T
    if z <= lo:
        return z
    if z <= hi:
        return lo + (z - lo) * DRIVE_STRETCH
    return z + (hi - lo) * (DRIVE_STRETCH - 1)


# parts: (name, radius, z0, z1, front/back flat half-depth or None, material). Painted by nearest hit, so order is free.
PARTS = [
    ("base", BASE_R, BASE_BOT, _z(BASE_TOP), BASE_FLAT, "base"),
    ("collar", BASE_R - 3.0, _z(BASE_TOP), _z(COLLAR_RIM_TOP), BASE_FLAT - 3.0, "collar"),
    ("boss", BOSS_R, _z(COLLAR_RIM_TOP), _z(-7.0), None, "recess"),
    ("ring", RING_R, _z(-7.0), _z(-CAP_T), None, "ring"),
    ("skirt_b", CAP_R, _z(-CAP_T), _z(SKIRT_H - CAP_T), None, "cap"),
    ("tube", TUBE_R, _z(SKIRT_H - CAP_T), _z(TUBE_TOP - SKIRT_H + CAP_T), None, "tube"),
    ("skirt_t", CAP_R, _z(TUBE_TOP - SKIRT_H + CAP_T), _z(TUBE_TOP + CAP_T), None, "cap"),
]
FACE_Z = (_z(SKIRT_H - CAP_T), _z(TUBE_TOP - SKIRT_H + CAP_T))     # the visible tube between the skirts
TOP_Z = _z(TUBE_TOP + CAP_T)

# three shades per material (dark, mid, light), dim on purpose: the column's current cap, and the LEDs must pop.
# The real parts are black PETG-CF / PET-CF; on the display "black" is "off", so the body is a dim slate.
MATERIAL_RGB = {
    "base": [(14, 14, 20), (30, 30, 38), (52, 52, 62)],
    "collar": [(26, 26, 32), (48, 48, 56), (74, 74, 84)],
    "recess": [(6, 6, 10), (12, 12, 18), (20, 20, 28)],
    "ring": [(40, 40, 50), (66, 66, 78), (96, 96, 110)],
    "cap": [(26, 30, 44), (46, 52, 72), (78, 86, 112)],
    "tube": [(12, 14, 24), (22, 26, 42), (36, 42, 64)],
}
EXTRA_RGB = {
    "knob": (110, 110, 120), "knob_hi": (190, 190, 200), "nut": (150, 150, 160), "floor": (30, 22, 14),
    "led_pkg": (120, 118, 106), "strip": (0, 0, 0), "nut_blur": (120, 120, 138),
}


class Column:
    """The column drawn into a Scene's palette. Display coordinates: (col, row), row 0 = bottom.

    elev_deg: camera elevation (how much of the top cap you see); centre_col / floor_row / top_row place it."""

    def __init__(self, sc, centre_col: float = FRONT_CENTRE, floor_row: float = 1.0, top_row: float = 40.8,
                 elev_deg: float = 15.0, light=(-0.35, -0.85, 0.40), ss: int = 4, gain: float = 1.6):
        self.sc, self.ss = sc, ss
        self.e = math.radians(elev_deg)
        self.se, self.ce = math.sin(self.e), math.cos(self.e)
        L = np.array(light, dtype=float)
        self.L = L / np.linalg.norm(L)
        # screen-plane mm: u = X, v = Z cos e + Y sin e (Y points away from the viewer)
        v_lo = BASE_BOT * self.ce - BASE_FLAT * self.se
        v_hi = TOP_Z * self.ce + CAP_R * self.se
        self.cz = (top_row - floor_row) / (v_hi - v_lo)                 # display rows per screen mm
        self.cx = self.cz * ROW_PITCH_MM / COL_ARC_MM                    # display columns per screen mm (pixels 5.24 x 5.56)
        self.c0, self.r0, self.v_lo = centre_col, floor_row, v_lo
        self.mat_names = list(MATERIAL_RGB)
        self.pal = {}
        # gain: the body is the subject here, not a background sky; after the ESP32's gamma 2.2 the raw shades would sit
        # at 1-5 % PWM duty, so they are lifted (1.6 x: the lightest slate ~ (58, 67, 102) -> ~10 % blue duty)
        for m, shades in MATERIAL_RGB.items():
            for k, rgb in enumerate(shades):
                self.pal[(m, k)] = sc.col(f"col_{m}{k}", tuple(min(255, int(round(v * gain))) for v in rgb))
        for name, rgb in EXTRA_RGB.items():
            self.pal[name] = 0 if rgb == (0, 0, 0) else sc.col(f"col_{name}", rgb)
        self._static = None

    # ---- coordinates
    def screen_of(self, X, Y, Z):
        """World mm (X right, Y away from the viewer, Z up; drawn z) -> display (col, row), floats."""
        v = Z * self.ce + Y * self.se
        return self.c0 + X * self.cx, self.r0 + (v - self.v_lo) * self.cz

    def surface(self, theta, z, r: float = TUBE_R):
        """Point on a vertical cylinder of radius r at azimuth theta (rad, 0 = facing the viewer, + = to the viewer's
        right) and drawn height z -> (col, row, facing) where facing = cos(theta) (> 0 on the visible half)."""
        theta, z = np.broadcast_arrays(np.asarray(theta, float), np.asarray(z, float))
        X, Y = r * np.sin(theta), -r * np.cos(theta)
        c, rr = self.screen_of(X, Y, z)
        return c, rr, np.cos(theta)

    def _to_uv(self, cols, rows):
        return (cols - self.c0) / self.cx, (rows - self.r0) / self.cz + self.v_lo

    # ---- ray caster
    def materials(self, cols, rows, full: bool = False):
        """Material id (index into mat_names, -1 = nothing) and shade (0..2) at display points (float arrays); with
        full=True also the hit point (X, Y, Z, mm) and whether it is a top face."""
        u, v = self._to_uv(np.asarray(cols, float), np.asarray(rows, float))
        best = np.full(u.shape, np.inf)
        mat = np.full(u.shape, -1, dtype=np.int16)
        shade = np.zeros(u.shape, dtype=np.int16)
        hz = np.zeros(u.shape)
        htop = np.zeros(u.shape, bool)
        se, ce = self.se, self.ce
        for name, R, z0, z1, flat, m in PARTS:
            mi = self.mat_names.index(m)
            inside = np.abs(u) < R
            ys = -np.sqrt(np.clip(R * R - u * u, 0, None))
            on_flat = np.zeros(u.shape, bool)
            if flat is not None:
                on_flat = ys < -flat
                ys = np.where(on_flat, -flat, ys)
            zs = (v - ys * se) / ce
            side = inside & (zs >= z0) & (zs <= z1)
            yt = (v - z1 * ce) / se
            top = (u * u + yt * yt <= R * R)
            if flat is not None:
                top &= np.abs(yt) <= flat
            # side normal: (sin th, -cos th, 0); flat: (0, -1, 0); top: (0, 0, 1)
            nx = np.where(on_flat, 0.0, u / R)
            ny = np.where(on_flat, -1.0, ys / R)
            lit_side = np.clip(nx * self.L[0] + ny * self.L[1], 0, None)
            lit_top = max(0.0, self.L[2])
            for hit, depth, lit, is_top in ((side, ys, lit_side, False), (top, yt, lit_top, True)):
                closer = hit & (depth < best)
                if not closer.any():
                    continue
                best = np.where(closer, depth, best)
                mat = np.where(closer, mi, mat)
                hz = np.where(closer, z1 if is_top else zs, hz)
                htop = np.where(closer, is_top, htop)
                lv = 0.25 + 0.95 * lit if not is_top else np.full(u.shape, 0.25 + 0.95 * lit_top + 0.15)
                sh = np.where(lv > 0.82, 2, np.where(lv > 0.48, 1, 0))
                shade = np.where(closer, sh, shade)
        if full:
            return mat, shade, u, best, hz, htop
        return mat, shade

    def index_at(self, cols, rows, tube_shift: int = 0, screen_rim: float | None = None) -> np.ndarray:
        """Palette index of the column (rotor at speed: no strips, the nylocs blurred into a ring) at display points,
        -1 = background. tube_shift = 1..3 darkens the tube face one shade per step (3 = off), for fades.
        screen_rim = r: the face is a dark screen (off, as a spinning column's is) except a rim where |X| > r * TUBE_R."""
        mat, shade, X, Y, Z, top = self.materials(cols, rows, full=True)
        idx = np.full(mat.shape, -1, np.int16)
        ramp = [0, self.pal[("recess", 0)]] + [self.pal[("tube", k)] for k in range(3)]   # darkest .. lightest
        for mi, m in enumerate(self.mat_names):
            for k in range(3):
                sel = (mat == mi) & (shade == k)
                if m == "tube":
                    idx[sel] = ramp[max(0, k + 2 - tube_shift)]
                else:
                    idx[sel] = self.pal[(m, k)]
        if screen_rim is not None:
            tube = self.mat_names.index("tube")
            idx[(mat == tube) & (np.abs(X) < screen_rim * TUBE_R)] = 0
        cap, base = self.mat_names.index("cap"), self.mat_names.index("base")
        idx[(mat == cap) & top & (np.abs(np.hypot(X, Y) - NUT_R) < 6.0)] = self.pal["nut_blur"]
        rk = max(KNOB_R, 1.1 / self.cz)
        knob = (mat == base) & ~top & (Y <= -BASE_FLAT + 0.01) & (X ** 2 + (Z - KNOB_Z) ** 2 <= rk * rk)
        idx[knob] = self.pal["knob"]
        return idx

    def render_static(self, col_lo: int = 30, col_hi: int = 66):
        """Palette-index image (ROWS, COLS) of the column at rest (no strips / LEDs / nuts), plus the material map.
        Cached: the body does not move (only the rotor's strips, LEDs and nuts do)."""
        if self._static is not None:
            return self._static
        ss = self.ss
        off = (np.arange(ss) + 0.5) / ss - 0.5
        cols = np.arange(col_lo, col_hi)
        rr, cc = np.meshgrid(np.arange(ROWS), cols, indexing="ij")
        R = rr[:, :, None, None] + off[None, None, :, None]
        C = cc[:, :, None, None] + off[None, None, None, :]
        mat, shade = self.materials(C, R)
        code = np.where(mat >= 0, mat * 3 + shade, -1).reshape(ROWS, len(cols), ss * ss)
        n_codes = len(self.mat_names) * 3
        counts = np.stack([(code == k).sum(-1) for k in range(-1, n_codes)], -1)   # (-1 = nothing) first
        win = counts.argmax(-1) - 1
        img = np.zeros((ROWS, COLS), np.uint8)
        mats = np.full((ROWS, COLS), -1, np.int16)
        lut = np.zeros(n_codes + 1, np.uint8)
        for k in range(n_codes):
            lut[k] = self.pal[(self.mat_names[k // 3], k % 3)]
        sub = np.where(win >= 0, lut[np.clip(win, 0, None)], 0)
        img[:, col_lo:col_hi] = sub
        mats[:, col_lo:col_hi] = np.where(win >= 0, win // 3, -1)
        # creases where the base's front flat meets its round sides (reads as the front panel)
        x_fl = math.sqrt(BASE_R ** 2 - BASE_FLAT ** 2)
        base_i = self.mat_names.index("base")
        for sx in (-1, 1):
            c = int(round(self.c0 + sx * x_fl * self.cx - (0.5 if sx > 0 else -0.5) * 0))
            col_m = mats[:, c] == base_i
            img[col_m, c] = self.pal[("base", 0 if sx > 0 else 1)]
        # the speed knob on the front flat (a disc with a highlight)
        kc, kr = self.screen_of(0.0, -BASE_FLAT, KNOB_Z)
        kr_px = max(0.9, KNOB_R * self.cz)
        for r in range(int(kr - 2), int(kr + 3)):
            for c in range(int(kc - 2), int(kc + 3)):
                if ((r - kr) / kr_px) ** 2 + ((c - kc) / (kr_px * self.cx / self.cz)) ** 2 <= 1.0:
                    img[r, c] = self.pal["knob"]
        img[int(round(kr + 0.3)), int(round(kc - 0.3))] = self.pal["knob_hi"]
        self._static = (img, mats)
        return self._static

    def face_mask(self) -> np.ndarray:
        """Pixels where the tube itself is the nearest surface (where strips and LEDs may be drawn)."""
        _, mats = self.render_static()
        return mats == self.mat_names.index("tube")

    def face_box(self):
        """(row_lo, row_hi, col_lo, col_hi) of the tube face, inclusive."""
        rr, cc = np.nonzero(self.face_mask())
        return int(rr.min()), int(rr.max()), int(cc.min()), int(cc.max())

    # ---- the rotor as a POV display in miniature
    def led_layout(self):
        """(theta0 per drawn strip, z per LED per strip): 12 strips at 30 deg, LEDs at a 2-row pitch, odd strips half a
        pitch up (the real column interleaves 3 sets the same way)."""
        th0 = np.arange(STRIPS_DRAWN) * TAU / STRIPS_DRAWN
        z_lo, z_hi = FACE_Z
        pitch = 2.0 / self.cz / self.ce                       # 2 display rows in drawn mm
        n = LEDS_DRAWN
        mid = 0.5 * (z_lo + z_hi)
        z_even = mid + (np.arange(n) - (n - 1) / 2) * pitch - 0.25 * pitch
        z = np.stack([z_even + (0.5 * pitch if s % 2 else 0.0) for s in range(STRIPS_DRAWN)])
        return th0, z

    def paint_rotor(self, img: np.ndarray, phis, image_fn=None, leds_on=None, nuts: bool = True,
                    pkg_min: float = 0.45, strip_min: float = 0.5) -> np.ndarray:
        """Draw the spinning rotor into img (in place) for one frame.

        phis: rotor angles (rad) at the frame's K sub-sample times (the exposure). image_fn(cols, rows, k) -> rgb
        array (..., 3) of the picture the drawn column shows at sub-sample k (screen coordinates; black = LED off);
        leds_on: per sub-sample bool (default all on when image_fn is given). Ideal persistence: a pixel any lit LED
        passes takes the mean colour of those passes (nearest palette colour). Strip PCBs and dark LED packages are
        drawn where they cover the pixel for >= strip_min / pkg_min of the exposure, so they show when slow and blur
        away when fast."""
        phis = np.atleast_1d(np.asarray(phis, float))
        K = len(phis)
        face = self.face_mask()
        th0, zl = self.led_layout()
        if leds_on is None:
            leds_on = np.full(K, image_fn is not None)
        strip_cov = np.zeros((ROWS, COLS))
        pkg_cov = np.zeros((ROWS, COLS))
        emit_sum = np.zeros((ROWS, COLS, 3))
        emit_n = np.zeros((ROWS, COLS))
        z_lo, z_hi = FACE_Z
        zs_strip = np.linspace(z_lo, z_hi, 64)
        for k, phi in enumerate(phis):
            th = th0 + phi                                                      # (S,)
            # strip PCBs: vertical lines following the cylinder's curvature
            c, r, f = self.surface(th[:, None], zs_strip[None, :])
            vis = f > 0.15
            ci, ri = np.rint(c).astype(int) % COLS, np.rint(r).astype(int)
            hit = np.zeros((ROWS, COLS), bool)
            ok = vis & (ri >= 0) & (ri < ROWS)
            hit[ri[ok], ci[ok]] = True
            strip_cov += hit
            # LEDs
            c, r, f = self.surface(np.repeat(th[:, None], zl.shape[1], 1), zl)
            vis = f > 0.15
            ci, ri = np.rint(c).astype(int) % COLS, np.rint(r).astype(int)
            ok = vis & (ri >= 0) & (ri < ROWS)
            ci, ri = ci[ok], ri[ok]
            pk = np.zeros((ROWS, COLS), bool)
            pk[ri, ci] = True
            pkg_cov += pk
            if leds_on[k] and image_fn is not None:
                rgb = np.asarray(image_fn(ci, ri, k), float)
                lit = rgb.sum(-1) > 0
                np.add.at(emit_sum, (ri[lit], ci[lit]), rgb[lit])
                np.add.at(emit_n, (ri[lit], ci[lit]), 1)
        strip_cov /= K
        pkg_cov /= K
        out = img
        tube_mid = self.pal[("tube", 1)]
        out[face & (strip_cov >= strip_min)] = self.pal["strip"]
        out[face & (pkg_cov >= pkg_min)] = self.pal["led_pkg"]
        lit = face & (emit_n > 0)
        if lit.any():
            mean = emit_sum[lit] / emit_n[lit][:, None]
            out[lit] = self.nearest(mean)
        if nuts:
            self.paint_nuts(out, phis)
        _ = tube_mid
        return out

    def paint_nuts(self, img: np.ndarray, phis) -> None:
        """The four tie-rod nylocs on the top cap: dots that orbit with the rotor (a ring of blur when fast)."""
        phis = np.atleast_1d(np.asarray(phis, float))
        cov = np.zeros((ROWS, COLS))
        for phi in phis:
            th = np.arange(4) * TAU / 4 + phi + TAU / 8
            X, Y = NUT_R * np.sin(th), -NUT_R * np.cos(th)
            c, r = self.screen_of(X, Y, TOP_Z)
            hit = np.zeros((ROWS, COLS), bool)
            ci, ri = np.rint(c).astype(int) % COLS, np.rint(r).astype(int)
            ok = (ri >= 0) & (ri < ROWS)
            hit[ri[ok], ci[ok]] = True
            cov += hit
        cov /= len(phis)
        top = self.render_static()[1] >= 0
        img[top & (cov > 0) & (cov < 0.45)] = self.pal["nut_blur"]     # fast: the four nuts smear into a ring
        img[cov >= 0.45] = self.pal["nut"]

    def nearest(self, rgb) -> np.ndarray:
        """Nearest palette index (never 0 = off) for rgb rows (n, 3)."""
        pal = np.array(self.sc.pal.rgb, float)
        d = ((np.asarray(rgb, float)[:, None, :] - pal[None, 1:, :]) ** 2).sum(-1)
        return (d.argmin(-1) + 1).astype(np.uint8)
