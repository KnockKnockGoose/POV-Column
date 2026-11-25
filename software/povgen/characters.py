"""Original characters for the POV column prototypes: a stylised running dog (approach a: procedural primitives) and a
KnockKnockGoose-style Canada goose (approach b: text-grid sprites + procedural legs/wing). No third-party IP.

Coordinates inside a character: x = columns in the facing direction (+ = forward), y = rows up, origin at the ground
contact point under the chest. draw_* functions map that onto the Canvas at (ground_row, base_col)."""
from __future__ import annotations

import math

from povanim import Canvas, Palette, Sprite

GROUND_ROW = 2


def make_palette() -> Palette:
    pal = Palette()
    pal.add("fur", (255, 140, 0))
    pal.add("dark", (150, 55, 0))
    pal.add("white", (255, 255, 255))
    pal.add("pink", (255, 60, 120))
    pal.add("collar", (0, 120, 255))
    pal.add("ball", (255, 0, 30))
    pal.add("ball_hi", (255, 170, 170))
    pal.add("ground", (0, 90, 0))
    pal.add("navy", (0, 40, 170))       # the goose's "black"
    pal.add("brown", (170, 95, 25))
    pal.add("brown_dk", (110, 55, 10))
    pal.add("belly", (240, 200, 120))
    return pal


# ------------------------------------------------------------------ helpers
def _leg(cv: Canvas, pal: Palette, hip_x, hip_y, phase, base_col, facing, colour, foot_colour, upper=3.5, lower=3.0,
         swing_deg=38.0, lift=1.6):
    """Two-segment leg. phase 0..1: 0 = foot forward touching down, 0.5 = foot back, swing in between (knee bends on the
    forward swing). Returns nothing; draws thigh, shin and a paw pixel."""
    a = math.radians(swing_deg) * math.cos(2 * math.pi * phase)           # +forward
    swinging = math.sin(2 * math.pi * phase) < 0                           # second half of the cycle = leg in the air
    bend = math.radians(55.0) * (0.5 - 0.5 * math.cos(2 * math.pi * phase)) if swinging else math.radians(8.0)
    kx, ky = hip_x + upper * math.sin(a), hip_y - upper * math.cos(a)
    fx, fy = kx + lower * math.sin(a - bend), ky - lower * math.cos(a - bend)
    if swinging:
        fy += lift * (0.5 - 0.5 * math.cos(2 * math.pi * phase))
        ky += 0.5 * lift
    fy = max(fy, 0.0)
    cv.line(GROUND_ROW + hip_y, base_col + facing * hip_x, GROUND_ROW + ky, base_col + facing * kx, colour)
    cv.line(GROUND_ROW + ky, base_col + facing * kx, GROUND_ROW + fy, base_col + facing * fx, colour)
    cv.px(GROUND_ROW + fy, base_col + facing * fx, foot_colour)


def draw_ground(cv: Canvas, pal: Palette, scroll_cols: int = 0, dash: int = 4):
    cv.hline(0, 0, 95, pal["ground"], dash=dash, phase=scroll_cols)


def draw_ball(cv: Canvas, pal: Palette, x_col, bounce_phase, height=7.0, radius=1.5):
    h = bounce_phase % 1.0
    y = GROUND_ROW + radius - 0.5 + height * 4 * h * (1 - h)              # parabola per bounce
    cv.disc(y, x_col, radius, pal["ball"])
    cv.px(y + 0.7, x_col - 0.7, pal["ball_hi"])


# ------------------------------------------------------------------ the dog (procedural)
def draw_dog(cv: Canvas, pal: Palette, base_col, phase, facing=1):
    """A stylised running dog (greyhound-ish), ~27 columns x 17 rows, chest at base_col, facing +columns by default."""
    fur, dark, white, pink, collar = pal["fur"], pal["dark"], pal["white"], pal["pink"], pal["collar"]
    bob = 0.7 * math.sin(4 * math.pi * phase)                              # two bounces per stride
    X = lambda x: base_col + facing * x                                    # noqa: E731
    Y = lambda y: GROUND_ROW + y + bob                                     # noqa: E731
    # far legs first (darker) so the near legs read on top
    _leg(cv, pal, -13, 7 + bob, phase + 0.15, base_col, facing, dark, dark)
    _leg(cv, pal, -2, 7 + bob, phase + 0.65, base_col, facing, dark, dark)
    # body, neck, head
    cv.ellipse(Y(9.2), X(-8.5), 3.0, 8.5, fur)
    cv.line(Y(10), X(-1), Y(14), X(3), fur, thick=2)
    cv.ellipse(Y(15.0), X(4.5), 2.3, 3.2, fur)
    cv.rect(Y(14), X(7) if facing > 0 else X(9), 2, 3, fur)                # snout
    cv.px(Y(15), X(10), dark)                                              # nose
    cv.px(Y(16), X(5), dark)                                               # eye
    flap = 0.6 * math.sin(2 * math.pi * phase)
    cv.ellipse(Y(17.3 + flap), X(2.2), 1.1, 1.6, dark)                     # ear
    if 0.25 <= phase % 1.0 < 0.75:
        cv.px(Y(13), X(9), pink)                                           # tongue out on the stretch
    cv.px(Y(11), X(0), collar)
    cv.px(Y(12), X(1), collar)
    cv.px(Y(11), X(1), collar)
    # tail
    wag = 1.5 * math.sin(2 * math.pi * phase)
    cv.line(Y(11), X(-16.5), Y(14 + wag), X(-21), fur)
    cv.px(Y(14.5 + wag), X(-21.5), dark)
    # near legs
    _leg(cv, pal, -14, 7 + bob, phase, base_col, facing, fur, dark)
    _leg(cv, pal, -3, 7 + bob, phase + 0.5, base_col, facing, fur, dark)
    # white chest patch
    cv.px(Y(9), X(-1), white)
    cv.px(Y(8), X(-1), white)


# ------------------------------------------------------------------ the goose (text-grid sprites)
_GOOSE_HEAD = [
    "..............nnnn....",
    ".............nnnnnn...",
    ".............nwwnnnnnn",
    ".............nwwn.....",
    "..............nnn.....",
    "..............nnn.....",
    "..............nnn.....",
    ".............nnn......",
    "............nnn.......",
]
_GOOSE_BODY = [
    "...........bbbb.......",
    "tt.....bbbbbbbbb......",
    ".ttbbbbbbbbbbbbb......",
    "..bbbbbbbbbbbbb.......",
    "..llllllllllll........",
    "...llllllllll.........",
    ".....llllll...........",
]


def goose_sprites(pal: Palette) -> tuple[Sprite, Sprite]:
    legend = {"n": pal["navy"], "w": pal["white"], "b": pal["brown"], "t": pal["brown_dk"], "l": pal["belly"]}
    return Sprite.from_text(_GOOSE_HEAD, legend), Sprite.from_text(_GOOSE_BODY, legend)


def draw_goose(cv: Canvas, pal: Palette, base_col, phase, facing=1, honk=False):
    """A running Canada goose, ~24 columns x 20 rows. base_col = column under the chest."""
    head, body = goose_sprites(pal)
    if facing < 0:
        head, body = head.flipped(), body.flipped()
    navy, dk = pal["navy"], pal["brown_dk"]
    bob = round(0.9 * math.sin(4 * math.pi * phase))
    left = base_col - 17 if facing > 0 else base_col - 4
    # legs (far one darker is not possible with one colour; offset it by a column instead)
    _leg(cv, pal, -6, 6 + bob, phase + 0.5, base_col, facing, navy, navy, upper=3.0, lower=2.5, swing_deg=45, lift=1.2)
    _leg(cv, pal, -5, 6 + bob, phase, base_col, facing, navy, navy, upper=3.0, lower=2.5, swing_deg=45, lift=1.2)
    cv.blit(body, GROUND_ROW + 5 + bob, left)
    # wing: a dark brown blade that beats twice per stride
    beat = math.sin(2 * math.pi * phase)
    wx0, wy0 = -8, 9 + bob
    cv.line(GROUND_ROW + wy0, base_col + facing * wx0, GROUND_ROW + wy0 + 2 + 3 * beat, base_col + facing * (wx0 - 7),
            dk, thick=2)
    cv.blit(head, GROUND_ROW + 9 + bob, left + 1)
    cv.px(GROUND_ROW + 15 + bob, base_col + facing * (-3 + 1), navy)     # eye inside the white cheek
    if honk:
        cv.px(GROUND_ROW + 15 + bob, base_col + facing * 3, navy)
        cv.px(GROUND_ROW + 15 + bob, base_col + facing * 4, navy)
