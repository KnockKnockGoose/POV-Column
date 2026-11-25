"""scenekit: high-level building blocks for POV column scenes (42 rows x 96 columns, row 0 = bottom, columns wrap).

Why it exists (2026-11-07 speed investigation): in the one-shot pipeline the LLM spent 100-175 s writing 130-200 lines
of pixel code (plus 6-13k thinking tokens) for every request. With ready-made backgrounds, characters, props, effects
and loop-safe motion helpers, a scene is 20-40 lines, so the model writes (and thinks) far less, and the art is the
tested art from the hand-built scenes instead of a fresh guess. `compose(spec)` goes one step further: a JSON spec
(subject, vehicle, background, effects, ...) renders a whole scene with no code at all (the "template" lane).

A scene script with scenekit:

    from scenekit import Scene, sky, sea, rider, splash, bob
    def build():
        sc = Scene("a bichon on a jet ski", mode="front", seconds=4)
        for k, t, cv in sc.frames():           # t runs 0..1 over the loop; the frame is added automatically
            sky(sc, cv, "sunset", t)
            h = sea(sc, cv, t, laps=2)          # water scrolls 2 pattern laps per loop -> closes exactly
            rider(sc, cv, "bichon", "jetski", col=48, row=h(48) + bob(t, 0.6, 8), t=t)
        return sc.done()

All helpers take (sc, cv, ...): `sc` owns the palette (helpers register their own named colours, so any mix of helpers
stays under the 32-colour limit) and `cv` is the frame's Canvas. Positions are (col, row) of a documented anchor,
usually the bottom-centre of the thing. Colours are deliberately dim for big areas (sky, water, buildings): the column's
current cap is 2.6 A, and dark backgrounds make the bright subject pop on a POV display.
"""
from __future__ import annotations

import math

import numpy as np

import bichon_head as bh
from characters import _leg, draw_dog, draw_goose, goose_sprites
from povanim import COLS, FRONT_CENTRE, ROWS, Animation, Canvas, Palette, Sprite

TAU = 2 * math.pi
KX = bh.KX                       # 1.06 columns per row of height (pixels are slightly taller than wide)
FRONT_LO, FRONT_HI = FRONT_CENTRE - 16, FRONT_CENTRE + 15     # the viewer's window, columns 32..63


# ================================================================ scene + palette
class Scene:
    """Owns the palette and the Animation. `for k, t, cv in sc.frames(): ...` then `return sc.done()`."""

    def __init__(self, prompt: str = "", mode: str = "front", seconds: float = 4.0, fps: float = 15.0,
                 name: str | None = None, scope: str = "public", note: str = "", n_frames: int | None = None):
        self.pal = Palette()
        self.c: dict[str, int] = {"off": 0}
        self.n = int(n_frames or max(2, round(seconds * fps)))
        self.fps, self.mode = fps, mode
        slug = "".join(ch if ch.isalnum() else "_" for ch in (name or prompt or "scene").lower())[:40].strip("_")
        self.anim = Animation(self.pal, fps=fps, loop=True, name=slug or "scene",
                              meta=dict(prompt=prompt, mode=mode, scope=scope, note=note, generator="scenekit"))

    def col(self, name: str, rgb) -> int:
        """Palette index for a named colour (added on first use)."""
        if name not in self.c:
            self.c[name] = self.pal.add(name, rgb)
        return self.c[name]

    def frames(self):
        """Yields (k, t, cv) per frame, t = k / n in [0, 1); each cv is appended to the animation after the loop body."""
        for k in range(self.n):
            cv = Canvas()
            yield k, k / self.n, cv
            self.anim.add(cv)

    def done(self) -> Animation:
        return self.anim


class _PalAdapter:
    """Lets characters.py helpers (which index a Palette by name) draw with namespaced scene colours."""

    def __init__(self, sc: Scene, prefix: str, rgb: dict):
        self.sc, self.prefix, self.rgb = sc, prefix, rgb

    def __getitem__(self, name):
        if self.rgb[name] == (0, 0, 0):
            return 0                                   # "off" draws as a black silhouette over a sky
        return self.sc.col(self.prefix + name, self.rgb[name])


# ================================================================ motion (all loop-safe when t runs 0..1)
def wave(t: float, cycles: int = 1, phase: float = 0.0) -> float:
    """sin over the loop; integer `cycles` closes the loop."""
    return math.sin(TAU * (cycles * t + phase))


def bob(t: float, amp: float = 1.0, cycles: int = 4, phase: float = 0.0) -> float:
    return amp * wave(t, cycles, phase)


def scroll(t: float, laps: int = 1, period: int = COLS) -> float:
    """Offset (columns) for something that moves `laps` x `period` columns per loop (closes exactly)."""
    return t * laps * period


def orbit_col(t: float, laps: int = 1, start: float = FRONT_CENTRE) -> float:
    """Column of something that travels round the drum `laps` times per loop (negative = the other way)."""
    return (start + t * laps * COLS) % COLS


def seg(t: float, a: float, b: float) -> float:
    """Progress 0..1 inside the beat [a, b] of the loop (clamped): `p = ease(seg(t, .2, .4))`."""
    return min(1.0, max(0.0, (t - a) / (b - a))) if b > a else float(t >= a)


def ease(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def ease_out(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 2


def ease_in(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return x * x


def jump(t: float, a: float, b: float, height: float) -> float:
    """Parabolic hop inside the beat [a, b] (0 outside it)."""
    p = seg(t, a, b)
    return height * 4 * p * (1 - p) if 0 < p < 1 else 0.0


def pingpong(t: float, cycles: int = 1) -> float:
    """0 -> 1 -> 0 triangle over the loop."""
    x = (t * cycles) % 1.0
    return 2 * x if x < 0.5 else 2 - 2 * x


def _hash(i: float) -> float:
    return (math.sin(i * 12.9898 + 78.233) * 43758.5453) % 1.0


def _wrapd(d: float) -> float:
    return (d + COLS / 2) % COLS - COLS / 2


# ================================================================ backgrounds
SKIES = {   # bands from the bottom up: (first row, rgb). Dim on purpose (current, contrast).
    "day": [(0, (20, 45, 95)), (14, (16, 36, 82)), (24, (12, 28, 70)), (33, (9, 20, 58))],
    "sunset": [(0, (110, 50, 20)), (6, (95, 32, 30)), (12, (78, 20, 48)), (19, (50, 12, 56)), (27, (28, 8, 50)),
               (34, (14, 4, 36))],
    "dusk": [(0, (40, 20, 50)), (10, (25, 14, 48)), (22, (14, 10, 40)), (32, (8, 6, 28))],
    "night": [(0, (6, 8, 26)), (16, (4, 5, 18)), (30, (2, 3, 12))],
}


def sky(sc: Scene, cv: Canvas, kind: str = "night", t: float = 0.0, stars_on: bool | None = None,
        sun_at: tuple | None = None) -> None:
    """Fill the whole drum with a dim sky ('day', 'sunset', 'dusk', 'night', or 'none'). Night/dusk get stars.
    sun_at = (col, row) adds a sun (a moon at night)."""
    sc.dark_bg = kind in SKIES
    sc.bright_sky = kind in ("day", "sunset")
    if kind in SKIES:
        for r0, rgb in SKIES[kind]:
            cv.a[r0:] = sc.col(f"sky_{kind}_{r0}", rgb)
    if stars_on or (stars_on is None and kind in ("night", "dusk")):
        stars(sc, cv, t)
    if sun_at is not None:
        sun(sc, cv, sun_at[0], sun_at[1], t, kind="moon" if kind == "night" else "sun")


def stars(sc: Scene, cv: Canvas, t: float = 0.0, n: int = 40, row_min: int = 18, seed: int = 3) -> None:
    """Fixed stars over the whole drum; a third of them twinkle (integer cycles per loop, so the loop closes)."""
    rng = np.random.default_rng(seed)
    for i in range(n):
        r, c = int(rng.integers(row_min, ROWS)), int(rng.integers(0, COLS))
        tw = i % 3 == 0
        on = (not tw) or wave(t, 1 + i % 3, _hash(i)) > -0.3
        if on and cv.a[r, c] in (0,) + tuple(v for k, v in sc.c.items() if k.startswith("sky_")):
            cv.px(r, c, sc.col("star", (85, 85, 105)) if i % 8 else sc.col("star_hi", (220, 215, 180)))


def sun(sc: Scene, cv: Canvas, col: float, row: float, t: float = 0.0, kind: str = "sun", radius: float = 2.5) -> None:
    if kind == "moon":
        cv.disc(row, col, radius, sc.col("moon", (230, 225, 190)))
        cv.disc(row + 0.8, col + 1.2, radius * 0.75, sc.col("sky_night_30", SKIES["night"][-1][1]))
        return
    cv.disc(row, col, radius, sc.col("sun", (255, 190, 30)))
    rays = ((0, 1), (0, -1), (1, 0), (-1, 0)) if wave(t, 4) > 0 else ((0.7, 0.7), (0.7, -0.7), (-0.7, 0.7), (-0.7, -0.7))
    for dr, dc in rays:
        cv.px(row + dr * (radius + 1.8), col + dc * (radius + 1.8) * KX, sc.col("sun_ray", (255, 150, 0)))


def clouds(sc: Scene, cv: Canvas, t: float, laps: int = 1, rows=(28, 36), n: int = 4, seed: int = 5) -> None:
    rng = np.random.default_rng(seed)
    ci = sc.col("cloud", (70, 75, 95))
    for i in range(n):
        c0 = rng.uniform(0, COLS) - scroll(t, laps)
        r0 = rng.uniform(*rows)
        w = rng.uniform(5, 9)
        cv.ellipse(r0, c0, 1.6, w, ci)
        cv.ellipse(r0 + 1.4, c0 + w * 0.2, 1.4, w * 0.5, ci)


def ground(sc: Scene, cv: Canvas, t: float = 0.0, kind: str = "grass", row: int = 2, laps: int = 0,
           dash: int = 4) -> None:
    """Fill below `row` with a dim ground and draw a dashed top line that scrolls `laps` x 96 columns per loop
    (front mode: the character runs in place while the ground moves; laps=0 for a still floor).
    kinds: grass, road, floor (wood), sand, snow."""
    fill, line = {"grass": ((0, 28, 0), (40, 130, 30)), "road": ((18, 18, 22), (200, 170, 40)),
                  "floor": ((40, 20, 8), (150, 85, 35)), "sand": ((60, 45, 15), (190, 150, 70)),
                  "snow": ((40, 45, 60), (200, 210, 230))}[kind]
    cv.a[:row] = sc.col(f"ground_{kind}", fill)
    off = int(round(scroll(t, laps)))
    li = sc.col(f"ground_{kind}_line", line)
    for c in range(COLS):
        if kind == "road":
            if ((c + off) // dash) % 3 == 0:
                cv.px(row // 2, c, li)
            cv.px(row, c, sc.col("road_edge", (70, 70, 80)))
        elif kind in ("grass", "sand", "snow"):
            cv.px(row, c, li if ((c + off) // dash) % 2 == 0 else sc.col(f"ground_{kind}", fill))
            if kind == "grass" and _hash((c + off) % COLS) > 0.7:
                cv.px(row + 1, c, li)
        else:
            cv.px(row, c, li)
            if (c + off) % 12 == 0:
                cv.px(row - 1, c, sc.col("floor_seam", (20, 10, 4)))


def skyline(sc: Scene, cv: Canvas, t: float = 0.0, base: int = 0, seed: int = 11, max_h: int = 16,
            windows: bool = True) -> None:
    """A city of dark buildings right round the drum, with lit windows (a few switch on and off over the loop)."""
    rng = np.random.default_rng(seed)
    body = (sc.col("bldg_a", (22, 22, 40)), sc.col("bldg_b", (30, 26, 52)))
    win = (sc.col("window", (200, 160, 60)), sc.col("window_dim", (110, 80, 30)))
    c = 0
    i = 0
    while c < COLS:
        w = int(rng.integers(5, 10))
        h = int(rng.integers(6, max_h + 1))
        w = min(w, COLS - c)
        cv.rect(base, c, h, w - 1, body[i % 2])
        if rng.random() < 0.3:                                    # antenna / spire
            cv.rect(base + h, c + w // 2 - 1, 2, 1, body[i % 2])
        if windows:
            for r in range(base + 2, base + h - 1, 2):
                for x in range(c + 1, c + w - 2, 2):
                    hsh = _hash(r * 97 + x)
                    if hsh < 0.45:
                        on = hsh > 0.06 or wave(t, 1, hsh * 7) > 0
                        if on:
                            cv.px(r, x, win[0] if hsh > 0.25 else win[1])
        c += w
        i += 1


def hills(sc: Scene, cv: Canvas, t: float = 0.0, base: int = 2, height: float = 6.0, laps: int = 0) -> None:
    ci = sc.col("hill", (10, 40, 18))
    off = scroll(t, laps)
    for c in range(COLS):
        x = c + off
        h = base + height * (0.55 + 0.25 * math.sin(TAU * x / 48) + 0.2 * math.sin(TAU * x / 32 + 1))
        cv.rect(base, c, int(h) - base, 1, ci)


# ---------------------------------------------------------------- water
def sea(sc: Scene, cv: Canvas, t: float, level: float = 5.0, laps: int = 1, chop: float = 0.8, swell: float = 0.0,
        colour: str = "blue"):
    """Water up to row `level` right round the drum, scrolling `laps` x 96 columns per loop (front mode: the rider
    stays put and the sea moves). Returns h(col) -> surface row at that column, for placing boats and riders."""
    deep = sc.col("sea_deep", (0, 30, 120) if colour == "blue" else (24, 8, 42))
    surf = sc.col("sea_surf", (0, 130, 230) if colour == "blue" else (200, 90, 40))
    foam = sc.col("foam", (200, 235, 255))
    off = scroll(t, laps)

    def h(col: float) -> float:
        x = col + off
        return level + chop * math.sin(TAU * x / 24) + swell * max(0.0, math.cos(TAU * x / 96)) ** 6

    for c in range(COLS):
        top = int(round(h(c)))
        cv.a[:max(0, top), c] = deep
        x = c + off
        cv.px(top, c, foam if math.sin(TAU * x / 24) > 0.85 else surf)
    return h


# ================================================================ characters (side view, facing +columns unless facing=-1)
BICHON_RGB = {"fur": (235, 235, 235), "shade": (120, 140, 210), "tongue": (255, 70, 130), "vest": (255, 120, 0)}
# The rider from content/public/bichon_jetski.py (W fur, s shade, k eyes/nose = off, p tongue, o vest); hip at col 9.
_BICHON_SIT = [
    "..........WW.WWW.WW.",
    ".........WWWWWWWWWWW",
    "........WWWWWWWWWWWW",
    "........sWWkkWWWkkWW",
    "........sWWkkWWWkkWW",
    "........sWWWWWWWWWWW",
    "...WW...ssWWWWkkWWWs",
    "..WWWW...sWWWWWpWWWs",
    "..WW......sWWWWWWWs.",
    "...WWWoooooooWWWWWWW",
    "....WWoooooooWW.....",
    "....WWWWWWWWWWW.....",
]
_BICHON_HEAD = _BICHON_SIT[:9]   # rows 0-8, face spans cols 8-19


def bichon(sc: Scene, cv: Canvas, col: float, row: float, t: float = 0.0, pose: str = "run", facing: int = 1,
           vest: bool = False) -> None:
    """Original cartoon bichon frise, side-on body with a front-facing cloud face (~13 rows, ~22 cols).
    (col, row) = between the feet, on the ground. pose: run | stand | sit."""
    W, s = sc.col("bichon_fur", BICHON_RGB["fur"]), sc.col("bichon_shade", BICHON_RGB["shade"])
    legend = {"W": W, "s": s, "k": 0, "p": sc.col("bichon_tongue", BICHON_RGB["tongue"]),
              "o": sc.col("bichon_vest", BICHON_RGB["vest"]) if vest else W}
    if pose == "sit":
        sp = Sprite.from_text(_BICHON_SIT, legend)
        cv.blit(sp, row, col - 9 if facing > 0 else col - (sp.w - 10), flip=facing < 0)
        return
    ph = (t * 8) % 1.0 if pose == "run" else 0.25
    lift = 0.6 * math.sin(TAU * 2 * ph) if pose == "run" else 0.0
    X = lambda x: col + facing * x                                          # noqa: E731
    by = row + 4.5 + lift
    for hx, p0 in ((-6, 0.15), (3, 0.65)):                                  # far legs (shade)
        _leg_at(cv, row, hx, 4.5 + lift, ph + p0, col, facing, s, pose)
    cv.ellipse(by + 1.0, X(-1.5), 3.2, 7.5, W)                              # cloud body
    for k in range(5):
        cv.disc(by + 3.2 - 0.3 * abs(k - 2), X(-6 + 3 * k), 1.6, W)          # fluffy back
    cv.disc(by + 3.5 + wave(t, 8) * 0.5, X(-9.5), 1.8, W)                    # pom tail
    for hx, p0 in ((-7, 0.0), (2, 0.5)):                                    # near legs
        _leg_at(cv, row, hx, 4.5 + lift, ph + p0, col, facing, W, pose)
    head = Sprite.from_text(_BICHON_HEAD, legend)
    hl = X(1) - 8 if facing > 0 else X(1) - (head.w - 8)
    cv.blit(head, by + 2, hl, flip=facing < 0)


def _leg_at(cv: Canvas, ground_row: float, hip_x, hip_y, phase, base_col, facing, colour, pose):
    """characters._leg draws relative to row 2; draw on a scratch canvas and move it to ground_row."""
    tmp = _scratch()
    if pose == "run":
        _leg(tmp, None, hip_x, hip_y, phase, base_col, facing, colour, colour, upper=2.6, lower=2.2, swing_deg=36, lift=1.0)
    else:
        _leg(tmp, None, hip_x, hip_y, 0.25, base_col, facing, colour, colour, upper=2.6, lower=2.2, swing_deg=0, lift=0.0)
    _paste_shifted(cv, tmp, ground_row - 2)


_EMPTY = 255   # scratch canvases start at 255 so characters can draw "off" (black) pixels over a background


def _scratch() -> Canvas:
    return Canvas(fill=_EMPTY)


def _paste_shifted(cv: Canvas, tmp: Canvas, drow: float) -> None:
    d = int(round(drow))
    src = tmp.a
    rows = np.nonzero((src != _EMPTY).any(axis=1))[0]
    for r in rows:
        rr = r + d
        if 0 <= rr < ROWS:
            m = src[r] != _EMPTY
            cv.a[rr, m] = src[r, m]


DOG_RGB = {"fur": (255, 140, 0), "dark": (150, 55, 0), "white": (255, 255, 255), "pink": (255, 60, 120),
           "collar": (0, 120, 255)}
GOOSE_RGB = {"navy": (0, 40, 170), "white": (255, 255, 255), "brown": (170, 95, 25), "brown_dk": (110, 55, 10),
             "belly": (240, 200, 120)}


def dog(sc: Scene, cv: Canvas, col: float, row: float, t: float = 0.0, pose: str = "run", facing: int = 1) -> None:
    """The original orange running dog from characters.py (~17 rows x 27 cols); (col, row) = chest, on the ground."""
    tmp = _scratch()
    ph = (t * 8) % 1.0 if pose == "run" else 0.0
    draw_dog(tmp, _PalAdapter(sc, "dog_", DOG_RGB), col, ph, facing)
    _paste_shifted(cv, tmp, row - 2)


def goose(sc: Scene, cv: Canvas, col: float, row: float, t: float = 0.0, pose: str = "run", facing: int = 1,
          honk: bool = False) -> None:
    """The KnockKnockGoose-style Canada goose (~20 rows x 24 cols); (col, row) = under the chest, on the ground.
    pose: run (legs cycle) | stand (both feet down: riding a board, standing)."""
    rgb = dict(GOOSE_RGB, navy=(0, 0, 0)) if getattr(sc, "dark_bg", False) else GOOSE_RGB
    pal = _PalAdapter(sc, "goose_" if rgb is GOOSE_RGB else "goose_k_", rgb)
    tmp = _scratch()
    if pose == "run":
        draw_goose(tmp, pal, col, (t * 8) % 1.0, facing, honk)
    else:
        head, body = goose_sprites(pal)
        if facing < 0:
            head, body = head.flipped(), body.flipped()
        left = col - 17 if facing > 0 else col - 4
        navy = pal["navy"]
        for lx in (-6, -4):                                                  # straight legs + feet
            x = col + facing * lx
            tmp.line(2, x, 2 + 5, x, navy)
            tmp.px(2, x + facing, navy)
        tmp.blit(body, 2 + 5, left)
        beat = wave(t, 4)
        tmp.line(2 + 9, col + facing * -8, 2 + 11 + 2 * beat, col + facing * -15, pal["brown_dk"], thick=2)   # wing (balance)
        tmp.blit(head, 2 + 9, left + 1)
        tmp.px(2 + 15, col + facing * -2, navy)
        if honk:
            tmp.px(2 + 15, col + facing * 3, navy)
            tmp.px(2 + 15, col + facing * 4, navy)
    _paste_shifted(cv, tmp, row - 2)


CAT_RGB = {"fur": (255, 130, 20), "stripe": (160, 60, 0), "belly": (255, 210, 150), "eye": (90, 230, 60),
           "nose": (255, 90, 140), "whisker": (150, 150, 150)}
_CAT_HEAD = [   # facing +columns; o fur, s stripe, e eye, k pupil (off), n nose, w whisker
    "o.....o..",
    "oo...oo..",
    "ooososoo.",
    "oeoooeoo.",
    "okoooko..",
    "ooonoooww",
    ".oooooo..",
]
_CAT_BODY = [
    "..s..s..s..s..",
    ".oooooooooooo.",
    "oooooooooooooo",
    "oooooooooooooo",
    ".llllllllllll.",
]


def cat(sc: Scene, cv: Canvas, col: float, row: float, t: float = 0.0, pose: str = "run", facing: int = 1,
        crouch: float = 0.0) -> None:
    """An original orange tabby (~13 rows x 26 cols incl. tail); (col, row) = under the chest, on the ground.
    pose: run | stand | pounce (body stretched, front paws up). crouch 0..1 lowers the body (stalking)."""
    leg = {k: sc.col("cat_" + k, v) for k, v in CAT_RGB.items()}
    legend = {"o": leg["fur"], "s": leg["stripe"], "l": leg["belly"], "e": leg["eye"], "k": 0, "n": leg["nose"],
              "w": leg["whisker"]}
    head, body = Sprite.from_text(_CAT_HEAD, legend), Sprite.from_text(_CAT_BODY, legend)
    ph = (t * 8) % 1.0 if pose == "run" else 0.25
    lift = 0.6 * math.sin(TAU * 2 * ph) if pose == "run" else 0.0
    hip_y = 4.0 + lift - 1.5 * crouch
    tilt = 2 if pose == "pounce" else 0
    X = lambda x: col + facing * x                                          # noqa: E731
    for hx, p0 in ((-11, 0.15), (-1, 0.65)):
        _leg_at(cv, row, hx, hip_y + (tilt if hx > -5 else 0), ph + p0, col, facing, leg["stripe"],
                pose if pose != "pounce" else "stand")
    left = X(-13) if facing > 0 else X(-13) - body.w + 1
    cv.blit(body, row + hip_y - 0.5, left, flip=facing < 0)
    if tilt:                                                               # front of the body raised
        cv.blit(Sprite(body.data[:, 9:] if facing > 0 else body.data[:, :5]), row + hip_y + 1.5,
                X(-4) if facing > 0 else X(-4) - 4, flip=facing < 0)
    # tail: a curve rising from the rump, swishing
    sw = wave(t, 2)
    pts = [(row + hip_y + 3 + 0.9 * i, X(-13 - 1.3 * i + 0.5 * sw * i * (i - 2) / 3)) for i in range(6)]
    for (r0, c0), (r1, c1) in zip(pts, pts[1:]):
        cv.line(r0, c0, r1, c1, leg["fur"])
    cv.px(pts[-1][0], pts[-1][1], leg["stripe"])
    hl = X(0) if facing > 0 else X(0) - head.w + 1
    cv.blit(head, row + hip_y + 2 + tilt, hl, flip=facing < 0)
    for hx, p0 in ((-10, 0.0), (0, 0.5)):
        _leg_at(cv, row, hx, hip_y + (tilt if hx > -5 else 0), ph + p0, col, facing, leg["fur"],
                pose if pose != "pounce" else "stand")


def bichon_head(sc: Scene, cv: Canvas, col: float = FRONT_CENTRE, row: float = 25.0, yaw: float = 0.0,
                blink: bool = False, squint: bool = False, smirk: bool = False, chest: bool = True) -> dict:
    """The big front-facing bichon bust from bichon_head.py (head ~26 rows; with chest it fills the drum's height).
    Returns feature positions: 'glasses' = (row, col) of the eye line for shades(), 'nose', 'eye_l', 'eye_r'."""
    return bh.draw_bichon(cv.a, _bh_colours(sc), int(round(col)), row, yaw, blink, squint, smirk, chest)


def shades(sc: Scene, cv: Canvas, row: float, col: float, glint: float | None = None, tilt: int = 0,
           sparkle: int = 0) -> None:
    """Dark sunglasses centred on the eye line (row, col) (use bichon_head(...)['glasses']); glint = column offset of
    a highlight sweeping across the lenses (-12..12), sparkle = size of a star at the frame's corner (0-3)."""
    bh.draw_shades(cv.a, _bh_colours(sc), row, col, 1.0, tilt, glint, sparkle)


def paw(sc: Scene, cv: Canvas, row: float, col: float) -> None:
    """A fluffy forepaw whose toes are at (row, col), its leg running off the bottom of the frame."""
    bh.draw_paw(cv.a, _bh_colours(sc), row, col)


def _bh_colours(sc: Scene, dim: float | None = None) -> dict:
    names = ["fur", "fur_shade", "fur_deep", "fur_rim", "muzzle", "eye_hi", "tongue", "shade_rim", "lens_refl",
             "glint", "sparkle"]
    pal, c = bh.make_palette()
    rgb = dict(zip(pal.names, pal.rgb))
    out = {"off": 0}
    if dim is None:
        dim = 0.76 if getattr(sc, "bright_sky", False) else 0.8
    for n in names:
        f = 1.0 if n in ("eye_hi", "glint", "sparkle", "shade_rim", "tongue") else dim
        out[n] = sc.col("bh_" + n, tuple(int(v * f) for v in rgb[n]))
    return out


# ================================================================ vehicles and props
_JETSKI = [   # g seat/handlebar, R hull, Y stripe; 25 cols, bottom row sits at the waterline
    ".....................gg..",
    ".....................g...",
    ".....................g...",
    ".....................g...",
    "....................RR...",
    "..gggggggggggggg...RRRR..",
    ".RRRRRRRRRRRRRRRRRRRRRRR.",
    "RRYYYYYYYYYYYYYYYYYYYRRRR",
    ".RRRRRRRRRRRRRRRRRRRRRRR.",
    "...RRRRRRRRRRRRRRRRRRRR..",
]
_SKATEBOARD = [
    "d.............d",
    ".ddddddddddddd.",
    "...w.......w...",
]
_SURFBOARD = [
    "..ssssssssssssss...",
    "bbbbbbbbbbbbbbbbbbb",
    ".bbbbbbbbbbbbbbbbb.",
]
VEHICLES = {  # name: (sprite, legend colours, seat row above the sprite bottom, seat col from the sprite's left)
    "jetski": (_JETSKI, {"g": (110, 110, 130), "R": (255, 20, 40), "Y": (255, 210, 0)}, 5, 9),
    "skateboard": (_SKATEBOARD, {"d": (220, 40, 160), "w": (255, 220, 0)}, 2, 7),
    "surfboard": (_SURFBOARD, {"s": (255, 255, 255), "b": (0, 200, 200)}, 3, 9),
}


def vehicle(sc: Scene, cv: Canvas, kind: str, col: float, row: float, t: float = 0.0, facing: int = 1) -> tuple:
    """Draw a jetski / skateboard / surfboard with its seat (or deck middle) above (col, row = its bottom).
    Returns (seat_row, seat_col) for the rider."""
    rows, rgb, seat_r, seat_c = VEHICLES[kind]
    legend = {k: sc.col(f"{kind}_{k}", v) for k, v in rgb.items()}
    sp = Sprite.from_text(rows, legend)
    left = col - seat_c if facing > 0 else col - (sp.w - 1 - seat_c)
    cv.blit(sp, row, left, flip=facing < 0)
    if kind == "skateboard":                                                 # spinning wheels: a dark spoke
        for wc in (3, 11):
            if wave(t, 16) > 0:
                cv.px(row, left + (wc if facing > 0 else sp.w - 1 - wc), 0)
    return row + seat_r, col


def rider(sc: Scene, cv: Canvas, who: str, kind: str, col: float, row: float, t: float = 0.0, facing: int = 1) -> tuple:
    """A character on a vehicle: who = bichon | dog | goose | cat, kind = jetski | skateboard | surfboard.
    (col, row) = the vehicle's bottom at its seat column. Returns (seat_row, seat_col)."""
    sr, scol = vehicle(sc, cv, kind, col, row, t, facing)
    if who == "bichon":
        if kind == "jetski":
            bichon(sc, cv, scol, sr, t, pose="sit", facing=facing, vest=True)
        else:
            bichon(sc, cv, scol + 2 * facing, sr, t, pose="stand", facing=facing)
    elif who == "goose":
        goose(sc, cv, scol + 5 * facing, sr, t, pose="stand", facing=facing)
    elif who == "dog":
        dog(sc, cv, scol + 7 * facing, sr - 1, t, pose="stand", facing=facing)
    elif who == "cat":
        cat(sc, cv, scol + 6 * facing, sr, t, pose="stand", facing=facing)
    if kind in ("skateboard",):                                             # redraw the deck over the paws
        vehicle(sc, cv, kind, col, row, t, facing)
    return sr, scol


def ball(sc: Scene, cv: Canvas, col: float, row: float, bounce: float = 0.0, height: float = 7.0, radius: float = 1.5,
         colour=(255, 0, 30)) -> None:
    """A bouncing ball resting on `row`; bounce = phase (0..1 per bounce, use t * n for n bounces per loop)."""
    h = bounce % 1.0
    y = row + radius - 0.5 + height * 4 * h * (1 - h)
    cv.disc(y, col, radius, sc.col("ball", colour))
    cv.px(y + 0.7, col - 0.7, sc.col("ball_hi", (255, 170, 170)))


def laser_dot(sc: Scene, cv: Canvas, col: float, row: float, t: float = 0.0) -> None:
    """A red laser dot with a flickering glow."""
    glow = sc.col("laser_glow", (120, 0, 0))
    for dr, dc in ((0, 2), (0, -2), (2, 0), (-2, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)):
        if wave(t, 30, (dr + 2 * dc) * 0.1) > -0.3:
            cv.px(row + dr, col + dc, glow)
    core = sc.col("laser", (255, 20, 20))
    for dr, dc in ((0, 0), (0, 1), (0, -1), (1, 0), (-1, 0)):
        cv.px(row + dr, col + dc, core)
    cv.px(row, col, sc.col("laser_hot", (255, 180, 180)))


def butterfly(sc: Scene, cv: Canvas, col: float, row: float, t: float = 0.0, colour=(255, 220, 0)) -> None:
    w = sc.col("butterfly", colour)
    flap = wave(t, 12) > 0
    cv.px(row, col, sc.col("butterfly_body", (60, 30, 10)))
    for s in (-1, 1):
        cv.px(row + (1 if flap else 0), col + s, w)
        cv.px(row + (1 if flap else 0), col + 2 * s, w if flap else 0)
        cv.px(row - (0 if flap else 1), col + s, w)


def heart(sc: Scene, cv: Canvas, col: float, row: float, colour=(255, 40, 90)) -> None:
    sp = Sprite.from_text([".h.h.", "hhhhh", ".hhh.", "..h.."], {"h": sc.col("heart", colour)})
    cv.blit(sp, row, col - 2)


# ================================================================ effects
FIREWORK_COLOURS = {"red": (255, 40, 40), "gold": (255, 190, 40), "green": (60, 255, 80), "blue": (60, 120, 255),
                    "magenta": (255, 60, 220), "cyan": (60, 240, 255), "white": (240, 240, 255)}


def firework(sc: Scene, cv: Canvas, col: float, row: float, p: float, colour: str = "gold", radius: float = 10.0,
             sparks: int = 20, launch_from: float = 2.0) -> None:
    """One firework, p = its own progress 0..1 (exclusive; 0-0.25 the rocket climbs from `launch_from` to `row`, then the burst
    grows to `radius`, droops and fades). p outside 0..1 draws nothing."""
    if not 0 < p < 1:
        return
    rgb = FIREWORK_COLOURS.get(colour, (255, 255, 255))
    hi = sc.col(f"fw_{colour}", rgb)
    mid = sc.col(f"fw_{colour}_mid", tuple(int(v * 0.5) for v in rgb))
    lo = sc.col(f"fw_{colour}_lo", tuple(int(v * 0.22) for v in rgb))
    if p < 0.25:
        q = ease_out(p / 0.25)
        y = launch_from + (row - launch_from) * q
        cv.px(y, col, sc.col("fw_trail", (255, 220, 160)))
        cv.px(y - 1, col, sc.col("fw_trail_lo", (120, 80, 40)))
        return
    q = (p - 0.25) / 0.75
    r = radius * ease_out(min(1.0, q * 2.2))
    droop = 4.0 * q * q
    shade = hi if q < 0.5 else mid if q < 0.8 else lo
    if q < 0.12:
        cv.disc(row, col, 1.5, sc.col("fw_flash", (255, 255, 230)))
    for i in range(sparks):                                                  # chrysanthemum: rays that become dots
        a = TAU * (i + 0.5 * (i % 2)) / sparks
        rr = r * (0.8 + 0.2 * (i % 3) / 2)
        y, x = row + rr * math.sin(a) - droop, col + rr * math.cos(a) * KX
        if q < 0.55:                                                         # a ray from 45 % of the radius out
            r0 = 0.3 * rr
            cv.line(row + r0 * math.sin(a) - droop, col + r0 * math.cos(a) * KX, y, x, mid)
        cv.px(y, x, shade)
        if q > 0.7 and _hash(i * 7 + int(q * 20)) > 0.5:                     # crackle at the end
            cv.px(y - 1, x, sc.col("fw_crackle", (255, 255, 200)))


def fireworks_show(sc: Scene, cv: Canvas, t: float, n: int = 5, cols=(FRONT_LO + 4, FRONT_HI - 4), rows=(24, 34),
                   colours=("gold", "red", "cyan", "magenta", "green", "blue"), seed: int = 2, radius: float = 12.0,
                   life: float = 0.5) -> None:
    """n fireworks staggered over the loop (each lasts `life` of the loop, wrapping round so the loop closes),
    launched at random columns inside `cols` (default: the viewer's window) and bursting between `rows`."""
    rng = np.random.default_rng(seed)
    for i in range(n):
        start = i / n + rng.uniform(-0.05, 0.05)
        c0, r0 = rng.uniform(*cols), rng.uniform(*rows)
        p = ((t - start) % 1.0) / life
        firework(sc, cv, c0, r0, p, colours[i % len(colours)], radius * rng.uniform(0.75, 1.1))


def splash(sc: Scene, cv: Canvas, col: float, row: float, p: float, size: float = 1.0) -> None:
    """Water droplets bursting both ways from (col, row); p = progress 0..1."""
    if not 0 < p < 1:
        return
    for j in range(10):
        side = -1 if j % 2 else 1
        h1, h2 = _hash(j * 2.3 + 11), _hash(j * 4.1 + 3)
        a = p * 6
        cc = col + side * (2 + (0.7 + 1.2 * h2) * a) * size
        rr = row + ((1.3 + 1.0 * h1) * a - 0.3 * a * a) * size
        if rr >= row - 0.5:
            cv.px(rr, cc, sc.col("foam", (200, 235, 255)) if p < 0.35 else sc.col("spray", (90, 190, 255)))


def spray(sc: Scene, cv: Canvas, col: float, row: float, t: float, facing: int = 1, length: int = 6) -> None:
    """A rooster tail of droplets trailing behind (col, row) (the stern of a boat moving toward `facing`)."""
    for age in range(length):
        for j in range(2):
            h1, h2 = _hash((int(t * 997) - age) * 7 + j * 3.1), _hash((int(t * 997) - age) * 13 + j * 5.7)
            cc = col - facing * (0.9 + 0.7 * h1) * age
            rr = row + (0.8 + 0.6 * h2) * age - 0.13 * age * age
            if rr >= row - 1:
                cv.px(rr, cc, sc.col("foam", (200, 235, 255)) if age < 3 else sc.col("spray", (90, 190, 255)))


def sparkle(sc: Scene, cv: Canvas, col: float, row: float, size: int = 2, colour=(255, 240, 120)) -> None:
    ci = sc.col("sparkle", colour)
    for k in range(-size, size + 1):
        cv.px(row + k, col, ci)
        cv.px(row, col + k, ci)


def speed_lines(sc: Scene, cv: Canvas, col: float, row: float, t: float, facing: int = 1, n: int = 3,
                length: int = 5) -> None:
    """Short horizontal streaks behind something moving toward `facing`."""
    ci = sc.col("speed", (140, 140, 160))
    for i in range(n):
        off = (t * 24 + i * 2.7) % 6
        r = row + 3 * (i - (n - 1) / 2)
        c0 = col - facing * (2 + off)
        cv.line(r, c0, r, c0 - facing * length, ci)


def confetti(sc: Scene, cv: Canvas, t: float, n: int = 30, seed: int = 9) -> None:
    rng = np.random.default_rng(seed)
    cols = [sc.col(f"confetti_{i}", rgb) for i, rgb in enumerate(((255, 60, 60), (255, 220, 0), (60, 200, 255), (120, 255, 80)))]
    for i in range(n):
        c0, ph = rng.uniform(FRONT_LO - 6, FRONT_HI + 6), rng.uniform()
        y = ROWS - ((t + ph) % 1.0) * (ROWS + 2)
        cv.px(y, c0 + 1.5 * math.sin(TAU * (t * 3 + ph)), cols[i % 4])


def iris(cv: Canvas, row: float, col: float, radius: float) -> None:
    """Cartoon iris: everything outside a circle of `radius` rows around (row, col) goes dark."""
    bh.iris(cv.a, row, col, radius)


# ================================================================ template lane: a whole scene from a JSON spec
SPEC_DOC = {
    "subject": "bichon | dog | cat | goose | bichon_head | none",
    "action": "run | ride | chase | stand | portrait | none  (portrait = the big bichon bust)",
    "vehicle": "jetski | skateboard | surfboard | null  (action ride)",
    "target": "ball | laser | butterfly | null  (action chase: the thing in front)",
    "background": "none | day | sunset | dusk | night",
    "scenery": "sea | grass | road | floor | sand | snow | city | hills | none",
    "effects": "list of: fireworks, sparkles, confetti, hearts, clouds, sun, moon, splash, speed_lines, shades_gag",
    "mode": "front | orbit",
    "seconds": "2-10",
    "facing": "1 (to the viewer's right) | -1",
}


def compose(spec: dict) -> Animation:
    """Render a scene from a spec (see SPEC_DOC). Unknown values fall back to safe defaults; never raises on content."""
    subj = spec.get("subject") or "none"
    action = spec.get("action") or ("portrait" if subj == "bichon_head" else "run" if subj != "none" else "none")
    veh = spec.get("vehicle")
    if action == "ride" and veh not in VEHICLES:
        veh = "skateboard"
    target = spec.get("target")
    bg = spec.get("background") or ("night" if "fireworks" in (spec.get("effects") or []) else "none")
    scenery = spec.get("scenery") or ("sea" if veh in ("jetski", "surfboard") else "road" if veh == "skateboard"
                                      else "city" if bg == "night" and subj == "none" else "grass")
    fx = list(spec.get("effects") or [])
    mode = spec.get("mode") if spec.get("mode") in ("front", "orbit") else "front"
    seconds = float(min(10.0, max(2.0, spec.get("seconds") or (8.0 if action == "portrait" else 4.0))))
    facing = -1 if spec.get("facing") == -1 else 1
    fps = 15.0
    n = int(round(seconds * fps / 8)) * 8 or 8                               # whole run cycles (8 frames each)
    sc = Scene(spec.get("prompt", ""), mode=mode, n_frames=n, fps=fps, name=spec.get("name"),
               scope=spec.get("scope", "public"), note="template: scenekit.compose")
    sc.anim.meta["spec"] = spec
    laps = max(1, round(n / 16))                                             # ~6 cols/frame scenery speed in front mode
    for k, t, cv in sc.frames():
        if action == "portrait":
            _portrait(sc, cv, t, bg, fx)
            continue
        sky(sc, cv, bg, t, sun_at=(FRONT_CENTRE + 13, 36) if ("sun" in fx or "moon" in fx) else None)
        if "clouds" in fx:
            clouds(sc, cv, t)
        moving = mode == "front" and action in ("run", "ride", "chase")
        sl = -facing * laps if moving else 0
        base_row = 2
        h = None
        if scenery == "sea":
            h = sea(sc, cv, t, level=5, laps=sl, swell=1.5)
        elif scenery == "city":
            skyline(sc, cv, t)
        elif scenery == "hills":
            hills(sc, cv, t, laps=sl)
            ground(sc, cv, t, "grass", laps=sl)
        elif scenery in ("grass", "road", "floor", "sand", "snow"):
            ground(sc, cv, t, scenery, laps=sl)
        if "fireworks" in fx:
            fireworks_show(sc, cv, t, n=5, rows=(24, 35) if scenery == "city" else (26, 36))
        if mode == "orbit":
            col = orbit_col(t, facing)
        else:
            col = FRONT_CENTRE + (2 if subj == 'cat' else -4) * facing if target else FRONT_CENTRE
        row = base_row + 1
        if h is not None:
            row = h(col) - 0.5
        if subj != "none":
            if action == "ride":
                rr = row + (bob(t, 0.6, 2 * laps) if veh != "skateboard" else 0)
                rider(sc, cv, subj, veh, col, rr, t, facing)
                if veh in ("jetski", "surfboard"):
                    spray(sc, cv, col - facing * 9, rr + 1, t, facing)
                    if "splash" in fx:
                        splash(sc, cv, col, rr, (t * 2) % 1.0)
            else:
                pose = "run" if action in ("run", "chase") else "stand"
                hop = jump(t % 0.5 * 2, 0.55, 0.95, 5) if (action == "chase" and target == "laser") else 0.0
                _draw_subject(sc, cv, subj, col, row + hop, t, pose, facing)
            if "speed_lines" in fx:
                speed_lines(sc, cv, col - facing * 12, row + 7, t, facing)
        if action == "chase" or target:
            tc = col + facing * (11 if target == "laser" else 16)
            if target == "laser":
                lr = row + 1 + 6 * abs(math.sin(TAU * t * 2)) + 3 * wave(t, 5)
                laser_dot(sc, cv, tc + 2 * wave(t, 3), max(row + 1, lr), t)
            elif target == "butterfly":
                butterfly(sc, cv, tc + 2 * wave(t, 2), row + 12 + 3 * wave(t, 3), t)
            else:
                ball(sc, cv, tc, row - 1, t * 4)
        if "sparkles" in fx:
            for i in range(3):
                if wave(t, 4, i / 3) > 0.6:
                    sparkle(sc, cv, FRONT_LO + 6 + 9 * i, 30 + 3 * (i % 2), 1)
        if "hearts" in fx:
            heart(sc, cv, col + 6, row + 20 + 4 * pingpong(t, 2), )
        if "confetti" in fx:
            confetti(sc, cv, t)
    return sc.done()


def _draw_subject(sc, cv, subj, col, row, t, pose, facing):
    {"bichon": bichon, "dog": dog, "cat": cat, "goose": goose}.get(subj, bichon)(sc, cv, col, row, t, pose=pose,
                                                                               facing=facing)


def _portrait(sc: Scene, cv: Canvas, t: float, bg: str, fx: list) -> None:
    """The big bichon bust; with 'shades_gag' a paw slides sunglasses on, a glint sweeps, then they come off."""
    sky(sc, cv, bg if bg != "none" else "sunset", t)
    blink = 0.48 < t < 0.5 or 0.9 < t < 0.92
    smirk = "shades_gag" in fx and 0.45 < t < 0.85
    f = bichon_head(sc, cv, FRONT_CENTRE, 26.0, yaw=0.12 * wave(t, 1) if "shades_gag" not in fx else 0.0,
                    blink=blink, smirk=smirk)
    gr, gc = f["glasses"]
    if "shades_gag" in fx:
        up = ease(seg(t, 0.08, 0.32))                                         # the paw brings them up from below
        off = ease(seg(t, 0.86, 0.98))                                        # and they drop away at the end
        y = gr - 20 * (1 - up) - 20 * off
        if up > 0 and off < 1:
            shades(sc, cv, y, gc, glint=(-14 + 28 * seg(t, 0.4, 0.55)) if 0.4 < t < 0.55 else None,
                   sparkle=2 if 0.55 < t < 0.62 else 0)
        if 0.05 < t < 0.4:
            pr = y - 4 - 6 * ease(seg(t, 0.32, 0.4))
            paw(sc, cv, pr, gc + 9)
    if "sparkles" in fx:
        for i in range(3):
            if wave(t, 4, i / 3) > 0.6:
                sparkle(sc, cv, FRONT_LO + 3 + 13 * i, 36 + 2 * (i % 2), 1)
