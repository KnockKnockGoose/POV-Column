"""biscuit_kit: the shared parts of Infinite Biscuit: Biscuit (Brian's white bichon), the 11-22 meadow, his props.

Every Infinite Biscuit clip draws the scene with `meadow()` and Biscuit with `biscuit()` (or one of the `*_ride()`
helpers, which call it), so he looks the same in every clip and only the action and the object change. Built on
scenekit; everything in scenekit is re-exported, so a clip script needs only `from biscuit_kit import *`.

A clip is orbit mode, one 8 s lap per loop. Biscuit starts BEHIND the column (column 0; the viewer faces column 48)
and passes the viewer at t = 0.5, so the runner swaps clips while he is out of sight and he comes back round doing
something new.

    from biscuit_kit import *

    def build():
        sc = biscuit_scene("Biscuit flies a kite")
        for k, t, cv in sc.frames():
            meadow(sc, cv, t)
            col, row = path(t)
            a = biscuit(sc, cv, col, row, t)
            kite(sc, cv, a["mouth"], t)
        return sc.done()

The frame count comes from the runner (env BISCUIT_FRAMES: 80 / 60 / 48 / 40 frames per 8 s lap = 10 / 7.5 / 6 / 5 fps,
each a whole number of 1/30 s refresh ticks at 225 rpm) so the file fits the column's 64 KB limit; scripts never set it.

Biscuit is Brian's own dog; the drawing is the original cartoon bichon from scenekit (no image model, no photo).
Every helper is loop-safe: all motion is a function of t in [0, 1) with whole cycles per loop.
"""
from __future__ import annotations

import math
import os

import numpy as np

import scenekit as _sk
from scenekit import *  # noqa: F401,F403  re-export: clip scripts import everything from here
from scenekit import (KX, Scene, bichon, butterfly, clouds, ground, hills, orbit_col, sun, wave, bob, _hash)
from povanim import COLS, FRONT_CENTRE, ROWS, Canvas, Sprite

TAU = 2 * math.pi
LAP_S = 8.0                                  # seconds per lap (= per loop)
FRAME_CHOICES = (80, 60, 48, 40)             # what the runner may pick: 10 / 7.5 / 6 / 5 fps
DEFAULT_FRAMES = 60
GROUND = 3                                   # Biscuit's feet row in the meadow
START = 0.0                                  # his column at t = 0: right behind the column
FRONT = FRONT_CENTRE                         # 48: the column facing the viewer (he passes it at t = 0.5)
NOTE = ("Infinite Biscuit: Biscuit is Brian's own dog (white bichon frise), drawn as the original scenekit cartoon "
        "in the 11-22 meadow; written as code, no image model")


# ================================================================ scene + colours
FRAMES: int | None = None                    # set by the runner's re-render wrapper (fit to 64 KB)


def biscuit_scene(prompt: str, note: str = "", **_ignored) -> Scene:
    """The clip's Scene: orbit mode, one 8 s lap per loop. The runner sets the frame count (FRAMES or env
    BISCUIT_FRAMES); seconds/fps arguments are ignored on purpose so every clip has the same lap time."""
    try:
        n = int(FRAMES or os.environ.get("BISCUIT_FRAMES", DEFAULT_FRAMES))
    except ValueError:
        n = DEFAULT_FRAMES
    n = n if 8 <= n <= 240 else DEFAULT_FRAMES
    sc = Scene(prompt, mode="orbit", n_frames=n, fps=n / LAP_S, note=(note + " | " if note else "") + NOTE)
    sc.anim.meta["series"] = "infinite_biscuit"
    return sc


KIT_RGB = {   # props share these; an identical colour already in the scene (meadow, Biscuit) is reused, so a clip
    # with several props stays under the 32-colour limit
    "red": (255, 30, 40), "pink": (255, 70, 130), "orange": (255, 150, 0), "yellow": (255, 220, 0),
    "gold": (255, 190, 30), "green": (40, 130, 30), "lime": (120, 230, 40), "blue": (40, 110, 255),
    "sky": (120, 140, 210), "cyan": (60, 220, 235), "violet": (130, 70, 200), "white": (235, 235, 235),
    "brown": (140, 70, 20), "tan": (220, 160, 90), "grey": (140, 140, 150), "dark": (40, 40, 52), "black": (0, 0, 0),
}


def kc(sc: Scene, name) -> int:
    """Palette index of a kit colour by name (see KIT_RGB) or an (r, g, b) tuple. Reuses an identical colour."""
    rgb = KIT_RGB[name] if isinstance(name, str) else tuple(int(v) for v in name)
    if rgb == (0, 0, 0):
        return 0
    for i, v in enumerate(sc.pal.rgb):
        if tuple(v) == rgb:
            return i
    return sc.col("kit_" + (name if isinstance(name, str) else "%02x%02x%02x" % rgb), rgb)


def _sprite(sc: Scene, rows: list[str], legend: dict) -> Sprite:
    """Sprite from text rows (top row first) whose legend maps letters to kit colour names / rgb tuples."""
    return Sprite.from_text(rows, {ch: kc(sc, v) for ch, v in legend.items()})


def _blit_c(cv: Canvas, sp: Sprite, row_bottom: float, col_centre: float, facing: int = 1) -> None:
    """Blit a sprite by its bottom row and centre column; facing=-1 mirrors it."""
    cv.blit(sp, int(round(row_bottom)), int(round(col_centre - (sp.w - 1) / 2)), flip=facing < 0)


# ================================================================ the meadow (11-22) and its variants
SKIES = ("day", "sunset", "dusk", "night", "rain", "snow")
_EXTRA_SKIES = {
    "rain": [(0, (24, 30, 46)), (14, (20, 25, 40)), (24, (16, 20, 34)), (33, (12, 15, 28))],
    "snow": [(0, (30, 38, 62)), (14, (24, 31, 54)), (24, (19, 25, 46)), (33, (14, 19, 38))],
}
FLOWERS = (("pink", (200, 60, 120)), ("yellow", (220, 190, 30)), ("violet", (130, 70, 200)))
_RR, _CC = np.mgrid[0:ROWS, 0:COLS]


def meadow(sc: Scene, cv: Canvas, t: float, sky: str = "day", rainbow: bool = False, butterflies: int = 2,
           mown: float | None = None, flowers: bool = True, sun_col: float = FRONT) -> None:
    """The 11-22 meadow right round the drum; draw it FIRST in every frame. Sky, sun with rays (moon at night),
    clouds, hills, grass, 24 swaying blades, 12 bobbing flowers (pink / yellow / violet), butterflies circling.
    sky: day | sunset | dusk | night (stars, moon, fireflies) | rain (grey sky, falling rain) | snow (falling snow)
    rainbow: a rainbow arc in the sky.  butterflies: 0, 1 or 2.
    mown: pass t when Biscuit mows the lawn (one lap per loop): the grass from behind the column up to his mower is
          cut short, and it grows back while he is out of sight."""
    _sky(sc, cv, sky, t)
    if sky in ("day", "sunset"):
        sun(sc, cv, sun_col, 34, t)
    elif sky in ("night", "dusk"):
        sun(sc, cv, sun_col, 34, t, kind="moon")
    if rainbow:
        rainbow_arc(sc, cv)
    if sky != "night":
        clouds(sc, cv, t, 1, n=7 if sky in ("rain", "snow") else 4)
    hills(sc, cv, t, base=2, height=6, laps=0)
    ground(sc, cv, t, "grass", row=3, laps=0)
    blade = sc.col("blade", (30, 140, 40))
    fl = [sc.col(n, rgb) for n, rgb in FLOWERS]
    cut_to = None if mown is None else (START + COLS * float(mown) + 14)        # the mower runs ~14 cols ahead
    for i in range(24):
        c = i * 4 + 1
        cut = cut_to is not None and ((c - START) % COLS) < (cut_to - START)
        sway = 0 if cut else round(wave(t, 2, i * 0.13))
        cv.line(3, c, 4 if cut else 6, c + sway, blade)
        if flowers and i % 2 == 0:
            ci = fl[(i // 2) % 3]
            fr = 7 + round(bob(t, 1, 3) * (1 if i % 4 else -1))
            cv.px(fr, c + sway, ci)
            cv.disc(fr, c + sway, 1.5, ci)
    for j in range(max(0, min(2, butterflies))):
        bc = orbit_col(t, (1, -1)[j], 20 + 48 * j)
        butterfly(sc, cv, bc, 24 + 4 * j + bob(t, 2, 4), t)
    if sky == "rain":
        rain(sc, cv, t)
    elif sky == "snow":
        snow(sc, cv, t)
    elif sky == "night":
        fireflies(sc, cv, t)


def _sky(sc: Scene, cv: Canvas, kind: str, t: float) -> None:
    if kind in _EXTRA_SKIES:
        sc.dark_bg, sc.bright_sky = True, False
        for r0, rgb in _EXTRA_SKIES[kind]:
            cv.a[r0:] = sc.col(f"sky_{kind}_{r0}", rgb)
    else:
        _sk.sky(sc, cv, kind if kind in _sk.SKIES else "day", t)


def rainbow_arc(sc: Scene, cv: Canvas, col: float = 72, row: float = 6, radius: float = 17) -> None:
    """A rainbow (red outside) standing on the hills, centred on column `col` (72 = to the viewer's right)."""
    bands = [kc(sc, n) for n in ("red", "orange", "yellow", "green", "blue", "violet")]
    dc = (((_CC - col + COLS // 2) % COLS) - COLS // 2) / KX
    d = np.sqrt(dc ** 2 + (_RR - row) ** 2)
    band = np.floor(radius - d).astype(int)
    for i, ci in enumerate(bands):
        cv.a[(band == i) & (_RR >= row)] = ci


def rain(sc: Scene, cv: Canvas, t: float, n: int = 44, seed: int = 7) -> None:
    """Raindrops falling right round the drum (2-pixel streaks)."""
    rng = np.random.default_rng(seed)
    ci = sc.col("rain", (90, 140, 255))
    for i in range(n):
        c, ph = rng.uniform(0, COLS), rng.uniform()
        r = ROWS - ((t * (3 + i % 2) + ph) % 1.0) * (ROWS - 2)
        cv.px(r, c, ci)
        cv.px(r + 1, c, ci)


def snow(sc: Scene, cv: Canvas, t: float, n: int = 40, seed: int = 8) -> None:
    """Snowflakes drifting down right round the drum."""
    rng = np.random.default_rng(seed)
    ci = sc.col("snowflake", (215, 225, 245))
    for i in range(n):
        c, ph = rng.uniform(0, COLS), rng.uniform()
        r = ROWS - ((t * (1 + i % 2) + ph) % 1.0) * (ROWS - 2)
        cv.px(r, c + 1.5 * wave(t, 2 + i % 2, ph), ci)


def fireflies(sc: Scene, cv: Canvas, t: float, n: int = 14, seed: int = 9) -> None:
    """Blinking fireflies over the grass (night)."""
    rng = np.random.default_rng(seed)
    ci = sc.col("firefly", (190, 255, 60))
    for i in range(n):
        c, r, ph = rng.uniform(0, COLS), rng.uniform(8, 22), rng.uniform()
        if wave(t, 3 + i % 3, ph) > 0.2:
            cv.px(r + bob(t, 1.5, 2, ph), c + 2 * wave(t, 1, ph), ci)


# ================================================================ Biscuit
POSES = ("walk", "prance", "run", "stand", "sit")
HATS = ("party", "crown", "cap", "chef", "helmet", "cowboy", "flower", "bow")


def path(t: float, laps: int = 1, start: float = START, ground: float = GROUND) -> tuple[float, float]:
    """(col, row) of Biscuit's feet: `laps` laps round the drum per loop (negative laps = the other way; then draw him
    with facing=-1), starting right behind the column at t = 0 and passing the viewer (column 48) at t = 0.5."""
    return orbit_col(t, laps, start), float(ground)


def biscuit(sc: Scene, cv: Canvas, col: float, row: float, t: float, pose: str = "walk", facing: int = 1,
            hat: str | None = None, shades: bool = False, strides: int = 8, hat_colour=None) -> dict:
    """Biscuit, Brian's white bichon: ALWAYS draw him with this (or a *_ride helper) so he looks the same in every clip.
    (col, row) = between his feet on the ground (use path(t)). About 15 rows tall and 24 columns long; he faces
    +columns with facing=1 (the way path() moves him).
    pose: walk (stepping, small bounce) | prance (bouncy, the 11-22 look) | run (legs only) | stand (still legs: on a
          board, in a car) | sit.   strides: steps per loop (whole number).
    hat: None | party | crown | cap | chef | helmet | cowboy | flower | bow.   shades: sunglasses.
    Returns anchor points, each (row, col): mouth (just in front of his muzzle: hold things here), nose, eyes,
    head_top (top of his head), back (top of his back), tail, chest (in front of his chest), feet."""
    strides = max(1, int(round(strides)))
    tb = t * strides / 8.0                                     # scenekit's bichon steps 8 times per unit of t
    moving = pose in ("walk", "prance", "run")
    bounce = {"walk": 0.6, "prance": 1.5}.get(pose, 0.0) * abs(wave(t, strides))
    rr = row + bounce
    bichon(sc, cv, col, rr, tb, pose="sit" if pose == "sit" else ("run" if moving else "stand"), facing=facing)
    f = 1 if facing >= 0 else -1
    if pose == "sit":
        base = int(rr)
        hx = (lambda x: int(col - 9) + x) if f > 0 else (lambda x: int(col - 10) + 19 - x)   # noqa: E731
        hy = lambda y: base + 11 - y                                                       # noqa: E731
        a = dict(eyes=(hy(3.5), hx(14)), nose=(hy(6), hx(14.5)), mouth=(hy(7), hx(19) + f),
                 head_top=(hy(0), hx(14)), back=(hy(5), hx(8)), tail=(hy(7), hx(3)), chest=(hy(9), hx(18)),
                 feet=(rr, col))
    else:
        ph = (tb * 8) % 1.0 if moving else 0.25
        lift = 0.6 * math.sin(TAU * 2 * ph) if moving else 0.0
        by = rr + 4.5 + lift
        hb = int(by + 2)                                                                   # head sprite bottom row
        hx = (lambda x: int(col - 7) + x) if f > 0 else (lambda x: int(col - 13) + 19 - x)  # noqa: E731
        hy = lambda y: hb + 8 - y                                                          # noqa: E731
        X = lambda dx: col + f * dx                                                        # noqa: E731
        a = dict(eyes=(hy(3.5), hx(14)), nose=(hy(6), hx(14.5)), mouth=(hy(7), hx(19) + f),
                 head_top=(hy(0), hx(14)), back=(by + 3.5, X(-3)), tail=(by + 3.5, X(-9.5)),
                 chest=(by + 0.5, X(5.5)), feet=(rr, col))
    if shades:
        _shades(sc, cv, hx, hy, t)
    if hat:
        draw_hat(sc, cv, hat, a, f, hat_colour)
    a["facing"] = f
    return a


def _shades(sc, cv, hx, hy, t) -> None:
    """Side-view sunglasses over both eyes (frame line on top, dark lenses, a glint sweeping once per lap)."""
    rim, lens = kc(sc, "pink"), sc.col("shade_lens", (22, 18, 40))
    for x in range(9, 19):
        cv.px(hy(2.6), hx(x), rim)
    for x in (10, 11, 12, 16, 17, 18):
        cv.px(hy(3), hx(x), lens)
        cv.px(hy(4), hx(x), lens)
    cv.px(hy(3), hx(8), rim)
    g = int((t * 2 % 1.0) * 12)                                  # the glint crosses the lenses twice per loop
    if g in (0, 1, 2, 6, 7, 8):
        cv.px(hy(3), hx(10 + g), kc(sc, "white"))


_HAT_SPRITES = {   # (rows top first, legend, sprite column that sits over the head-top anchor)
    "party": (["..y..", "..p..", ".pyp.", ".ypy.", "pypyp"], {"p": "pink", "y": "yellow"}, 2),
    "crown": (["y.y.y", "yyryy", "yyyyy"], {"y": "gold", "r": "red"}, 2),
    "cap": (["..bbbbb....", ".bbbbbbbbbb"], {"b": "blue"}, 4),
    "chef": ([".w.w.", "wwwww", "wwwww", ".ggg."], {"w": "white", "g": "grey"}, 2),
    "helmet": (["..rrr..", ".rrwrr.", "rrrrrrr"], {"r": "red", "w": "white"}, 3),
    "cowboy": (["...bbb...", "..btttb..", "bbbbbbbbb"], {"b": "brown", "t": "tan"}, 4),
    "bow": (["pp.pp", "ppypp", "pp.pp"], {"p": "pink", "y": "yellow"}, 2),
    "flower": ([".p.", "pyp", ".p."], {"p": "pink", "y": "yellow"}, 1),
}


def draw_hat(sc: Scene, cv: Canvas, kind: str, a: dict, facing: int = 1, colour=None) -> None:
    """A hat on Biscuit's head (biscuit(..., hat=kind) calls this). colour recolours the main part."""
    if kind not in _HAT_SPRITES:
        return
    rows, legend, cx = _HAT_SPRITES[kind]
    legend = dict(legend)
    if colour is not None:
        legend[next(iter(legend))] = colour
    sp = _sprite(sc, rows, legend)
    r, c = a["head_top"]
    if kind == "flower":                                        # tucked behind the ear
        r, c = r - 1, c - facing * 5
    left = c - cx if facing > 0 else c - (sp.w - 1 - cx)
    cv.blit(sp, int(r), int(left), flip=facing < 0)


# ================================================================ rides: draw the vehicle AND Biscuit, return anchors
def skateboard_ride(sc: Scene, cv: Canvas, col: float, row: float, t: float, facing: int = 1, **look) -> dict:
    """Biscuit standing on a skateboard (col, row = the board's wheels on the ground). look = hat / shades kwargs."""
    sr, _ = _sk.vehicle(sc, cv, "skateboard", col, row, t, facing)
    a = biscuit(sc, cv, col + 2 * facing, sr, t, pose="stand", facing=facing, **look)
    _sk.vehicle(sc, cv, "skateboard", col, row, t, facing)          # the deck over his paws
    return a


def scooter_ride(sc: Scene, cv: Canvas, col: float, row: float, t: float, facing: int = 1, colour="cyan",
                 **look) -> dict:
    """Biscuit on a kick scooter (col, row = the deck's middle on the ground)."""
    deck, metal, tyre = kc(sc, colour), kc(sc, "grey"), kc(sc, "dark")
    f = 1 if facing >= 0 else -1
    a = biscuit(sc, cv, col - 2 * f, row + 2, t, pose="stand", facing=f, **look)
    cv.line(row + 1, col - 7 * f, row + 1, col + 6 * f, deck)
    cv.line(row + 1, col + 6 * f, row + 12, col + 8 * f, metal)                # stem
    cv.line(row + 12, col + 7 * f, row + 12, col + 10 * f, deck)               # handlebar
    for wc in (col - 6 * f, col + 7 * f):
        cv.disc(row + 0.5, wc, 1.0, tyre)
    return a


def bike_ride(sc: Scene, cv: Canvas, col: float, row: float, t: float, facing: int = 1, colour="red",
              **look) -> dict:
    """Biscuit pedalling a bicycle (col, row = between the wheels on the ground); the wheels spin, his legs pedal.
    About 21 rows tall with him on it."""
    f = 1 if facing >= 0 else -1
    frame, tyre, spoke = kc(sc, colour), kc(sc, "grey"), kc(sc, "sky")
    rw, fw = (row + 3, col - 9 * f), (row + 3, col + 9 * f)
    crank = (row + 3, col)
    a = biscuit(sc, cv, col - 1 * f, row + 4.5, t, pose="run", facing=f, strides=12, **look)
    ang = -f * TAU * 6 * t                                                     # 6 wheel turns per lap
    for wr, wc in (rw, fw):
        for k in range(20):
            q = TAU * k / 20
            cv.px(wr + 3 * math.sin(q), wc + 3 * KX * math.cos(q), tyre)
        cv.line(wr - 2 * math.sin(ang), wc - 2 * math.cos(ang), wr + 2 * math.sin(ang), wc + 2 * math.cos(ang), spoke)
        cv.line(wr - 2 * math.cos(ang), wc + 2 * math.sin(ang), wr + 2 * math.cos(ang), wc - 2 * math.sin(ang), spoke)
    for (r0, c0), (r1, c1) in ((rw, crank), (crank, (row + 6, col - 3 * f)), (rw, (row + 6, col - 3 * f)),
                               (crank, (row + 6, col + 6 * f)), ((row + 6, col + 6 * f), fw)):
        cv.line(r0, c0, r1, c1, frame)
    cv.disc(crank[0], crank[1], 0.8, frame)
    return a


def car_ride(sc: Scene, cv: Canvas, col: float, row: float, t: float, facing: int = 1, colour="red", **look) -> dict:
    """Biscuit driving a little open-top car (col, row = the car's middle on the ground); puffs from the exhaust."""
    f = 1 if facing >= 0 else -1
    a = biscuit(sc, cv, col - 2 * f, row + 2, t, pose="stand", facing=f, **look)
    body, tyre, hub = kc(sc, colour), kc(sc, "dark"), kc(sc, "grey")
    cv.rect(row + 1, col - 9, 4, 19, body)                                     # the door / body hides his legs
    for k in range(4):                                                         # bonnet slope at the front
        cv.px(row + 5, col + f * (3 + k), body)
    cv.line(row + 5, col + 3 * f, row + 8, col + 5 * f, kc(sc, "cyan"))        # windscreen
    cv.px(row + 3, col + 10 * f, kc(sc, "yellow"))                             # headlight
    cv.px(row + 3, col - 10 * f, kc(sc, "orange"))                             # tail light
    for wc in (col - 6 * f, col + 6 * f):
        cv.disc(row + 1.2, wc, 1.6, tyre)
        cv.px(row + 1.2 + math.sin(TAU * 8 * t), wc + math.cos(TAU * 8 * t), hub)
    for i in range(3):                                                         # exhaust puffs drifting back
        p = (t * 8 + i / 3) % 1.0
        cv.px(row + 2 + 2 * p, col - f * (11 + 6 * p), kc(sc, "grey"))
    return a


def balloon_ride(sc: Scene, cv: Canvas, col: float, row: float, t: float, colours=("red", "yellow"), **look) -> dict:
    """Biscuit in the basket of a hot-air balloon (col, row = the basket's bottom; use row 9-11 so it floats over the
    meadow). The balloon is about 31 rows tall; a burner flame flickers."""
    c1, c2 = kc(sc, colours[0]), kc(sc, colours[1])
    rope, wicker, wick2 = kc(sc, "grey"), kc(sc, "brown"), kc(sc, "tan")
    er, ec = row + 22, col                                                     # envelope centre
    for r in range(int(er - 8), int(er + 9)):
        for c in range(int(ec - 9), int(ec + 10)):
            if ((r - er) / 8.2) ** 2 + ((c - ec) / 7.6) ** 2 <= 1.0 and r > er - 8 + 0.3 * abs(c - ec):
                cv.px(r, c, c1 if (int(round(c - ec)) // 2) % 2 == 0 else c2)
    for s in (-1, 1):
        cv.line(row + 3, col + 3 * s, er - 7, ec + 3 * s, rope)
    if wave(t, 4) > 0.3:
        cv.px(er - 7, ec, kc(sc, "orange"))
        cv.px(er - 6, ec, kc(sc, "yellow"))
    a = biscuit(sc, cv, col, row + 0.5, t, pose="stand", facing=1, **look)
    for r in range(int(row), int(row) + 4):                                    # basket over his legs
        for c in range(int(col - 4), int(col + 5)):
            cv.px(r, c, wicker if (r + c) % 2 else wick2)
    return a


# ================================================================ things he holds, carries, plays
def kite(sc: Scene, cv: Canvas, hold: tuple, t: float, facing: int = 1, height: float = 20, back: float = 15) -> None:
    """A big diamond kite flying high behind him on a long string from `hold` (e.g. his mouth anchor); its bow tail
    ripples. Draw it after Biscuit."""
    f = 1 if facing >= 0 else -1
    hr, hc = hold
    kr = min(ROWS - 6, hr + height + bob(t, 1.2, 3))                          # kite centre
    kcol = hc - f * back + 2 * wave(t, 2)
    string = kc(sc, "grey")
    cv.line(hr, hc, kr - 4, kcol, string)
    tail = [(kr - 4, kcol)]
    for i in range(1, 6):
        tail.append((kr - 4 - 1.4 * i, kcol - f * (1.4 * i) + 1.2 * wave(t, 3, i * 0.15)))
    for (r0, c0), (r1, c1) in zip(tail, tail[1:]):
        cv.line(r0, c0, r1, c1, string)
    for i, (r, c) in enumerate(tail[1:]):
        if i % 2 == 0:
            ci = kc(sc, ("yellow", "pink", "cyan")[(i // 2) % 3])
            cv.px(r, c - 1, ci)
            cv.px(r, c + 1, ci)
    sp = _sprite(sc, ["....a....", "...aab...", "..aaabb..", ".aaaabbb.", "aaaaabbbb", ".ccccdd..", "..cccdd..",
                      "...ccd...", "....c...."], {"a": "red", "b": "yellow", "c": "blue", "d": "green"})
    _blit_c(cv, sp, kr - 4, kcol, f)


def mower(sc: Scene, cv: Canvas, a: dict, t: float, facing: int = 1, colour="red") -> None:
    """A push mower in front of Biscuit, its handle in his mouth, cut grass flying (use with meadow(..., mown=t))."""
    f = 1 if facing >= 0 else -1
    fr, fc = a["feet"]
    mc = fc + 15 * f                                                           # mower body centre
    body, tyre, eng = kc(sc, colour), kc(sc, "dark"), kc(sc, "grey")
    mr, mcol = a["mouth"]
    cv.line(mr, mcol, fr + 4, mc - 3 * f, eng)                                 # handle
    cv.rect(fr + 1, mc - 3, 3, 7, body)
    cv.rect(fr + 4, mc - 1, 1, 3, eng)                                         # engine
    for wc in (mc - 3, mc + 3):
        cv.disc(fr + 0.8, wc, 1.0, tyre)
    if wave(t, 8) > 0:
        cv.px(fr + 5, mc + 1, kc(sc, "grey"))                                  # little puff
    for i in range(5):                                                         # clippings spray out behind
        p = (t * 16 + i / 5) % 1.0
        cv.px(fr + 2 + 4 * p - 3 * p * p, mc - f * (4 + 5 * p) + (i - 2) * 0.6, kc(sc, "lime"))


def cupcake(sc: Scene, cv: Canvas, col: float, row: float, bites: int = 0, facing: int = 1) -> None:
    """A cupcake (pink frosting, cherry, striped wrapper), (col, row) = bottom centre, 5 x 6. bites 0-3 take bites."""
    rows = ["..r..", ".ppp.", "ppppp", "ppppp", "tbtbt", ".tbt."]
    rows = list(rows)
    for b in range(max(0, min(3, bites))):
        rows[b] = "....." if b == 0 else rows[b][:3 - b] + "." * (2 + b)
    _blit_c(cv, _sprite(sc, rows, {"r": "red", "p": "pink", "t": "tan", "b": "brown"}), row, col, facing)


def ice_cream(sc: Scene, cv: Canvas, col: float, row: float, facing: int = 1) -> None:
    """An ice-cream cone with two scoops and a cherry, (col, row) = the tip of the cone, 5 x 9."""
    sp = _sprite(sc, ["..r..", ".ppp.", "ppppp", ".ccc.", "ccccc", ".ccc.", "ttttt", ".ttt.", "..t.."],
                 {"r": "red", "p": "pink", "c": "cyan", "t": "tan"})
    _blit_c(cv, sp, row, col, facing)


CARRY_ITEMS = {   # small things he carries in his mouth: rows, legend
    "bone": (["ww...ww", ".wwwww.", "ww...ww"], {"w": "white"}),
    "stick": (["..b....", ".bbbbbb", "b......"], {"b": "brown"}),
    "flower": ([".p.", "pyp", ".p.", ".g.", ".g."], {"p": "pink", "y": "yellow", "g": "green"}),
    "letter": (["wwwww", "wrwrw", "wwrww", "wwwww"], {"w": "white", "r": "red"}),
    "ball": ([".rr.", "rrrr", "rrrr", ".rr."], {"r": "red"}),
    "frisbee": ([".ooooo.", "ooooooo"], {"o": "orange"}),
    "cupcake": (["..r..", ".ppp.", "ppppp", "tbtbt", ".tbt."], {"r": "red", "p": "pink", "t": "tan", "b": "brown"}),
    "sandwich": (["ttttt", "ggggg", "ppppp", "ttttt"], {"t": "tan", "g": "lime", "p": "pink"}),
}


def carry(sc: Scene, cv: Canvas, a: dict, item: str, facing: int | None = None) -> None:
    """Something held in his mouth: bone | stick | flower | letter | ball | frisbee | cupcake | sandwich."""
    if item not in CARRY_ITEMS:
        item = "bone"
    rows, legend = CARRY_ITEMS[item]
    f = a.get("facing", 1) if facing is None else facing
    sp = _sprite(sc, rows, legend)
    r, c = a["mouth"]
    _blit_c(cv, sp, r - (sp.h - 1) // 2 - 0.4, c + f * (sp.w // 2 - 1), f)


def balloon(sc: Scene, cv: Canvas, tie: tuple, t: float, colour="red", height: float = 11, lean: float = -3,
            phase: float = 0.0) -> None:
    """A balloon on a string tied at `tie` (e.g. his back anchor), bobbing above him."""
    tr, tc = tie
    br, bc = min(ROWS - 3, tr + height + bob(t, 0.8, 4, phase)), tc + lean + wave(t, 2, phase)
    s = kc(sc, "grey")
    mid = ((tr + br) / 2, (tc + bc) / 2 + 0.8 * wave(t, 3, phase))
    cv.line(tr, tc, mid[0], mid[1], s)
    cv.line(mid[0], mid[1], br - 2.5, bc, s)
    ci = kc(sc, colour)
    cv.ellipse(br, bc, 2.6, 2.2, ci)
    cv.px(br - 2.8, bc, ci)                                                    # knot
    cv.px(br + 1, bc - 1, kc(sc, "white"))                                     # shine


def balloons(sc: Scene, cv: Canvas, tie: tuple, t: float, colours=("red", "yellow", "blue")) -> None:
    """A bunch of balloons fanned out above `tie`."""
    n = len(colours)
    for i, colour in enumerate(colours):
        balloon(sc, cv, tie, t, colour, height=10 + 2 * (i % 2), lean=-5 + 10 * i / max(1, n - 1), phase=i * 0.3)


def guitar(sc: Scene, cv: Canvas, a: dict, t: float, facing: int | None = None) -> None:
    """An acoustic guitar held across his chest, neck pointing up and forward; music notes rise as he strums."""
    f = a.get("facing", 1) if facing is None else facing
    r, c = a["chest"]
    body, dark, wood = kc(sc, "orange"), kc(sc, "dark"), kc(sc, "brown")
    cv.line(r + 1, c + f * 1, r + 7, c + f * 6, wood)                         # neck
    cv.px(r + 7, c + f * 7, dark)
    cv.px(r + 8, c + f * 7, dark)                                              # head
    cv.disc(r - 1.2, c - f * 1.5, 2.2, body)
    cv.disc(r + 0.8, c, 1.6, body)
    cv.px(r - 0.6, c - f * 1, dark)                                            # sound hole
    if wave(t, 16) > 0.5:
        cv.px(r + 1, c - f * 2, kc(sc, "white"))                               # strum flash
    notes(sc, cv, c, r + 4, t, facing=f)


def notes(sc: Scene, cv: Canvas, col: float, row: float, t: float, n: int = 3, facing: int = 1,
          colours=("yellow", "pink", "cyan"), rise: float = 14) -> None:
    """Music notes floating up from (col, row), drifting backwards as he moves forward."""
    f = 1 if facing >= 0 else -1
    for i in range(n):
        p = (t * 4 + i / n) % 1.0
        r, c = row + rise * p, col - f * 6 * p + 1.5 * wave(t, 4, i / n)
        sp = _sprite(sc, [".nn", ".n.", ".n.", "nn.", "nn."], {"n": colours[i % len(colours)]})
        _blit_c(cv, sp, r, c, 1)


def trumpet(sc: Scene, cv: Canvas, a: dict, t: float, facing: int | None = None) -> None:
    """A golden trumpet at his mouth, bell forward, notes coming out."""
    f = a.get("facing", 1) if facing is None else facing
    r, c = a["mouth"]
    g = kc(sc, "gold")
    cv.line(r, c - f, r, c + f * 5, g)
    for dr in (-1, 0, 1):
        cv.px(r + dr, c + f * 6, g)
    cv.px(r + 2, c + f * 6, g)
    cv.px(r - 2, c + f * 6, g)
    cv.px(r + 1, c + f * 2, g)
    cv.px(r + 1, c + f * 3, g)                                                 # valves
    notes(sc, cv, c + f * 7, r + 2, t, n=3, facing=f, rise=12)


def drum(sc: Scene, cv: Canvas, a: dict, t: float, facing: int | None = None) -> None:
    """A little marching drum at his chest, sticks beating 8 times per lap, a 'boom' star on each beat."""
    f = a.get("facing", 1) if facing is None else facing
    r, c = a["chest"]
    dc, top = c + f * 4, r + 1                                                 # drum hangs in front of his chest
    cv.rect(top - 5, dc - 3, 5, 7, kc(sc, "red"))
    for rr in (top - 5, top - 1):
        cv.line(rr, dc - 3, rr, dc + 3, kc(sc, "yellow"))
    cv.line(top - 4, dc - 2, top - 2, dc + 2, kc(sc, "yellow"))               # the cord zig-zag
    cv.line(top, dc - 3, top, dc + 3, kc(sc, "white"))                         # drum head
    up = wave(t, 8) > 0
    for s, lift in ((-1, up), (1, not up)):
        sr = top + (4 if lift else 1)
        cv.line(sr, dc + s * 3, sr - 3, dc + s * 1, kc(sc, "tan"))
    if abs(wave(t, 8)) < 0.4:
        _sk.sparkle(sc, cv, dc + f * 5, top + 3, 1, colour=(255, 240, 120))


def flag(sc: Scene, cv: Canvas, base: tuple, t: float, facing: int = 1, colours=("red", "yellow")) -> None:
    """A pennant on a pole standing up from `base` (e.g. his back anchor), rippling behind him."""
    f = 1 if facing >= 0 else -1
    br, bc = base
    cv.line(br, bc, br + 10, bc, kc(sc, "grey"))
    for i in range(7):
        h = 4 - i * 0.45
        top = br + 10 + 0.7 * wave(t, 4, -i * 0.12)
        for k in range(max(1, int(round(h)))):
            cv.px(top - k, bc - f * (i + 1), kc(sc, colours[(k * 2 // max(1, int(round(h)))) % len(colours)]))


def wagon(sc: Scene, cv: Canvas, a: dict, t: float, cargo: str = "flowers", facing: int | None = None) -> None:
    """A red wagon rolling behind him, its handle in his mouth. cargo: flowers | gifts | ball | none."""
    f = a.get("facing", 1) if facing is None else facing
    fr, fc = a["feet"]
    wc = fc - f * 19                                                           # wagon centre
    red, tyre = kc(sc, "red"), kc(sc, "dark")
    mr, mcol = a["mouth"]
    cv.line(mr, mcol, fr + 3, wc + f * 5, kc(sc, "grey"))                     # handle (from his mouth)
    cv.rect(fr + 2, wc - 4, 3, 9, red)
    for c0 in (wc - 3, wc + 3):
        cv.disc(fr + 1, c0, 1.0, tyre)
    if cargo == "flowers":
        for k, name in enumerate(("pink", "yellow", "violet")):
            cv.disc(fr + 6 + (k % 2), wc - 3 + 3 * k, 1.2, kc(sc, name))
    elif cargo == "gifts":
        cv.rect(fr + 5, wc - 3, 3, 3, kc(sc, "blue"))
        cv.rect(fr + 5, wc + 1, 2, 3, kc(sc, "yellow"))
        cv.px(fr + 8, wc - 2, kc(sc, "red"))
    elif cargo == "ball":
        cv.disc(fr + 6.5, wc, 2.0, kc(sc, "blue"))


def umbrella(sc: Scene, cv: Canvas, a: dict, t: float, colour="red", facing: int | None = None) -> None:
    """An umbrella over his head (its handle hooked on his back), striped canopy; good with meadow(sky='rain')."""
    f = a.get("facing", 1) if facing is None else facing
    br, bc = a["back"]
    hr = a["head_top"][0]
    cr, cc = hr + 2, (bc + a["head_top"][1]) / 2
    c1, c2 = kc(sc, colour), kc(sc, "white")
    for r in range(int(cr), int(cr) + 5):
        half = 7.5 * math.sqrt(max(0.0, 1 - ((r - cr) / 4.6) ** 2)) * KX
        for c in range(int(cc - half), int(cc + half) + 1):
            cv.px(r, c, c1 if (int(round(c - cc)) // 3) % 2 == 0 else c2)
    cv.line(br, bc + f * 1, cr, cc, kc(sc, "dark"))
    cv.px(br, bc, kc(sc, "dark"))


def bubbles(sc: Scene, cv: Canvas, col: float, row: float, t: float, n: int = 6, facing: int = 1) -> None:
    """Soap bubbles rising from (col, row) and drifting back; each pops at the top."""
    f = 1 if facing >= 0 else -1
    ring = kc(sc, "cyan")
    for i in range(n):
        p = (t * 3 + i / n) % 1.0
        r, c = row + 16 * p, col - f * 8 * p + 2 * wave(t, 3, i * 0.37)
        if p < 0.9:
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                cv.px(r + dr, c + dc, ring)
        else:
            _sk.sparkle(sc, cv, c, r, 1, colour=(200, 240, 255))


def frisbee(sc: Scene, cv: Canvas, col: float, row: float, colour="orange") -> None:
    """A flying disc centred at (col, row)."""
    cv.ellipse(row, col, 0.8, 3.2, kc(sc, colour))
    cv.px(row + 1, col, kc(sc, "white"))


def paper_plane(sc: Scene, cv: Canvas, col: float, row: float, facing: int = 1) -> None:
    """A white paper aeroplane, nose toward `facing`, (col, row) = its middle."""
    sp = _sprite(sc, ["ww.....", ".wwww..", "..wwwww", ".gg...."], {"w": "white", "g": "grey"})
    _blit_c(cv, sp, row - 2, col, facing)


def cape(sc: Scene, cv: Canvas, a: dict, t: float, colour="red", facing: int | None = None) -> None:
    """A superhero cape from his neck streaming back over his tail, fluttering."""
    f = a.get("facing", 1) if facing is None else facing
    br, bc = a["back"]
    nc = bc + f * 4
    ci = kc(sc, colour)
    for i in range(15):
        top = br + 0.6 - 0.08 * i + 0.8 * wave(t, 8, -i * 0.08) * (i / 14)
        h = 1 + i * 0.22
        for k in range(int(round(h))):
            cv.px(top - k, nc - f * i, ci)


def juggle(sc: Scene, cv: Canvas, a: dict, t: float, colours=("red", "yellow", "blue")) -> None:
    """Three balls juggled in a fountain above his head."""
    hr, hc = a["head_top"]
    for i, name in enumerate(colours):
        p = (t * 6 + i / len(colours)) % 1.0
        side = 1 if (int(t * 6 + i / len(colours)) % 2) else -1
        c = hc + side * (3 - 6 * p)
        r = hr + 1 + 8 * 4 * p * (1 - p)
        cv.disc(r, c, 1.0, kc(sc, name))


def hearts_rising(sc: Scene, cv: Canvas, col: float, row: float, t: float, n: int = 3) -> None:
    """Little hearts floating up from (col, row)."""
    for i in range(n):
        p = (t * 3 + i / n) % 1.0
        _sk.heart(sc, cv, col + 2 * wave(t, 3, i / n), row + 12 * p)


__all__ = [n for n in dir() if not n.startswith("_") and n not in ("annotations", "math", "np", "os")]
__all__ += ["math", "np"]
