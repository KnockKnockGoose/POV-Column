#!/usr/bin/env python3
r"""orbit_rally.py - Orbit Rally, a one-player paddle-and-ball game on the POV LED Column (2026-11-24, our own design).

The paddle stands on the front of the column (image column 48, the column the front-mode animations face the viewer
with) and moves up and down. The ball flies right round the cylinder (96 columns = 360 deg), bouncing off the top and
bottom rows, and comes back from the other side: the paddle has to be at its height when it gets back to the front.
A return scores a point, sends the ball back the other way round and speeds it up a little; three misses end the
game, and a new one starts by itself.

    py software/games/orbit_rally.py --pot          knob 4 (rightmost, firmware pot1) on the Brain Dump panel -> column
    py software/games/orbit_rally.py --keys         Up/Down (or W/S) in the game window -> column
    py software/games/orbit_rally.py --sim          no column: the simulator window only (knob if the panel answers)
    py software/games/orbit_rally.py --bench 20     a bot plays 20 s on the column: fps, ack round trip, board counters
    py software/games/orbit_rally.py --selftest     headless: 10 simulated minutes with a bot; frame + current checks

Keys (game window focused): Up/Down or W/S move the paddle (and override the knob until it is turned again),
Space = new game, P = pause, Esc/Q = quit. The window shows the simulated column (front view + the unwrapped 360 deg
strip) and the link numbers. When the game ends it puts the column back the way it found it.

Display path: the firmware's live mode (firmware 0.4, src/main.cpp on_ws). {"live":1,"pal":[...]} sets the 14-colour
palette, then each binary WebSocket message is one 42 x 96 palette-index frame (4,032 B, row 0 = bottom). After each
frame the sender asks {"live":1,"ack":n}; the board answers {"live_ack":n} as soon as it has staged that frame, and the
sender keeps at most --window (default 1) frames unacknowledged. So frames never queue in the link, and the frame that
goes is rendered from the newest game state at the moment it can go: latency = one frame's transfer + a round trip +
the board's next refresh tick (1/8 turn: 33 ms at 225 rpm). The board caps the LED current per frame (cap_ma 2,600):
game frames light at most 3.5 % of the pixels (worst rotor position 0.89 A at full brightness, idle LEDs and the ESP32
included; --selftest checks it), so the cap never dims them.
A raw frame is 4,032 B: on the sled's measured 20-50 kB/s link that is 5-12 frames/s. Firmware 0.4.1 (branch
fw-live-rle, not flashed yet) also takes RLE live frames, b"R" + (run, index) pairs (~130-150 B for a game frame), and
reports diag.live_rle; --rle auto (default) uses them when the board offers them: 30 frames/s, ~20 ms ack.

Controller: panel.py (Brain-Dump-Button/breadboard, run by the "Brain Dump Panel" logon task) owns the Nano's COM port,
so the game does not open it: it asks panel.py's UDP channel (127.0.0.1:8767) "POTS" and gets
"OK pot1=..,pot2=..,pot3=..,pot4=.." (raw 0-1023; read-only, ~0.1 ms). Polled at 125 Hz, smoothed with a One Euro
filter, the middle 70 % of the knob's turn is mapped onto the paddle's travel, with a hysteresis band so the paddle
never flickers between two rows.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import os
import random
import signal
import socket
import statistics
import sys
import threading
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SOFTWARE = os.path.dirname(HERE)
for _p in (os.path.join(SOFTWARE, "povgen"), os.path.join(SOFTWARE, "povsim"), os.path.join(SOFTWARE, "firmware", "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
from povanim import CAP_MA, COLS, FRONT_CENTRE, FRONT_WIDTH, ROWS  # noqa: E402

# ---------------------------------------------------------------- rules and feel
PADDLE_H, PADDLE_W = 8, 2          # rows, columns (the paddle covers columns front-1 and front)
BALL_R = 1.5                       # half size of the 3 x 3 ball
GRACE = 1                          # rows: a ball one row past a paddle end still counts (latency is not the player's fault)
LIVES = 3
V0, V_GAIN, V_MAX = 20.0, 1.04, 55.0   # horizontal ball speed, columns/s: start (4.8 s a lap), x per return, cap (slowed 11-24, Brian: "just hard")
SLOPE_MIN, SLOPE_MAX = 0.12, 0.85      # |vertical / horizontal| after a return: centre hit .. paddle end
VY_MAX = 40.0                      # rows/s
SERVE_S, MISS_S, SCORE_S, OVER_S, HIT_FLASH_S = 1.3, 0.9, 1.3, 5.0, 0.10
KEY_SPEED = 42.0                   # rows/s while an arrow key is held
HYST = 0.2                         # rows beyond half a row before the drawn paddle moves to the next row
DT = 1.0 / 120.0                   # physics step (s); the ball moves <= 0.7 column per step

# ---------------------------------------------------------------- look
# sRGB palette (the board applies gamma 2.2 and its brightness field). 0 = off. Saturated, solid shapes read best on
# camera; everything but the paddle and the ball is dim, and most of the frame is dark.
OFF, PADDLE, PADDLE_HIT, BALL, BALL_EDGE, TRAIL1, TRAIL2, TRAIL3, TRAIL4, HUD, HUD_LIFE, MISS, BIG, PADDLE_MISS = range(14)
PAL = [
    (0, 0, 0),          # OFF
    (0, 225, 255),      # PADDLE: cyan
    (255, 255, 255),    # PADDLE_HIT: white for 0.1 s on a return
    (255, 150, 0),      # BALL: amber
    (150, 75, 0),       # BALL_EDGE: the 3 x 3 ball's corners, so it reads round
    (175, 98, 0),       # TRAIL1 (newest)
    (120, 66, 0),       # TRAIL2
    (80, 43, 0),        # TRAIL3
    (50, 26, 0),        # TRAIL4 (oldest)
    (20, 38, 115),      # HUD: score digits, dim blue
    (115, 14, 30),      # HUD_LIFE: one dim red dot per life left
    (255, 0, 0),        # MISS: the red bar
    (255, 190, 0),      # BIG: the score between rallies
    (255, 40, 40),      # PADDLE_MISS
]
TRAIL = (TRAIL1, TRAIL2, TRAIL3, TRAIL4)

FONT = {  # 3 x 5, top line first
    "0": ("###", "#.#", "#.#", "#.#", "###"), "1": (".#.", "##.", ".#.", ".#.", "###"),
    "2": ("###", "..#", "###", "#..", "###"), "3": ("###", "..#", ".##", "..#", "###"),
    "4": ("#.#", "#.#", "###", "..#", "..#"), "5": ("###", "#..", "###", "..#", "###"),
    "6": ("###", "#..", "###", "#.#", "###"), "7": ("###", "..#", "..#", ".#.", ".#."),
    "8": ("###", "#.#", "###", "#.#", "###"), "9": ("###", "#.#", "###", "..#", "###"),
    "H": ("#.#", "#.#", "###", "#.#", "#.#"), "I": ("###", ".#.", ".#.", ".#.", "###"),
    " ": ("...", "...", "...", "...", "..."),
}


def put(f, r, c, idx):
    """Set one pixel: rows clip (it is a column), columns wrap (it is a cylinder)."""
    if 0 <= r < ROWS:
        f[r, c % COLS] = idx


def fill(f, r0, r1, c0, c1, idx):
    """Inclusive rectangle, rows clipped, columns wrapped."""
    for c in range(c0, c1 + 1):
        f[max(0, r0):min(ROWS, r1 + 1), c % COLS] = idx


def text_width(s, scale=1):
    return (4 * len(s) - 1) * scale


def draw_text(f, s, left, top, idx, scale=1):
    """3 x 5 digits (x scale), `top` = the row of the glyphs' top line (row 0 is the bottom of the column)."""
    for i, ch in enumerate(s):
        for gr, line in enumerate(FONT.get(ch, FONT[" "])):
            for gc, px in enumerate(line):
                if px == "#":
                    fill(f, top - (gr + 1) * scale + 1, top - gr * scale, left + (4 * i + gc) * scale,
                         left + (4 * i + gc + 1) * scale - 1, idx)


def blink(t, hz):
    return (t * hz) % 1.0 < 0.5


def reflect(y, lo, hi):
    """Fold y into [lo, hi] the way the ball bounces off the top and bottom rows."""
    span = hi - lo
    m = (y - lo) % (2 * span)
    return lo + (m if m <= span else 2 * span - m)


# ---------------------------------------------------------------- the game
class Game:
    """All the game state. step() advances it by dt, render() draws a 42 x 96 frame of palette indices. One lock: the
    game thread steps it, the column sender and the preview window render it."""

    def __init__(self, seed=None, front=FRONT_CENTRE, grace=GRACE, lives=LIVES):
        self.rng = random.Random(seed)
        self.front, self.grace, self.lives_per_game = front, grace, lives
        self.lock = threading.RLock()
        self.t = 0.0
        self.best = 0
        self.paused = False
        self.trail = collections.deque(maxlen=240)
        self.trail_s = 0.15                       # set from the link's frame interval (set_frame_interval)
        self.games = self.returns_total = self.misses_total = 0
        self.events = collections.deque(maxlen=200)   # (t, "return" | "miss" | "over")
        self.py = (ROWS - PADDLE_H) / 2.0         # paddle bottom row, continuous
        self.prow = int(round(self.py))           # the drawn paddle's bottom row (quantised with hysteresis)
        self.direction = self.rng.choice((-1, 1))
        self.new_game()

    # ---- state changes
    def new_game(self):
        with self.lock:
            self.score, self.lives, self.speed = 0, self.lives_per_game, V0
            self.games += 1
            self._serve()

    def _serve(self):
        self.state, self.state_t, self.flash_t = "serve", 0.0, 0.0
        self.trail.clear()
        self._park_ball()

    def _park_ball(self):
        """The ball rests against the paddle face it will leave from and rides along with the paddle."""
        self.bx = (self.front + self.direction * (PADDLE_W / 2 + BALL_R)) % COLS
        self.by = self.prow + PADDLE_H / 2.0
        self.vx = self.vy = 0.0

    def _launch(self):
        self.vx = self.direction * self.speed
        self.vy = self.rng.choice((-1, 1)) * self.rng.uniform(0.25, 0.55) * self.speed
        self.state, self.state_t = "play", 0.0

    def set_frame_interval(self, dt):
        """The trail covers ~1.6 link frames, so on a slow link it bridges the jump between two frames (motion blur)."""
        self.trail_s = min(0.35, max(0.12, 1.6 * dt))

    def toggle_pause(self):
        with self.lock:
            self.paused = not self.paused

    # ---- physics
    def rel(self, x):
        """Signed distance (columns) from the paddle's centre line, in (-48, 48]."""
        r = (x - self.front) % COLS
        return r - COLS if r > COLS / 2 else r

    def ball_r0(self):
        return int(math.floor(self.by - 1.0))     # the 3 x 3 ball covers rows r0..r0+2

    def step(self, dt, target=None, vel=0.0):
        """Advance by dt. target = paddle bottom row from the knob (absolute), else vel = rows/s from keys / the bot."""
        with self.lock:
            if self.paused:
                return
            self.t += dt
            self.state_t += dt
            self.flash_t = max(0.0, self.flash_t - dt)
            top = float(ROWS - PADDLE_H)
            self.py = min(top, max(0.0, target if target is not None else self.py + vel * dt))
            if abs(self.py - self.prow) >= 0.5 + HYST:
                self.prow = int(math.floor(self.py + 0.5))
            st = self.state
            if st == "serve":
                self._park_ball()
                if self.state_t >= SERVE_S:
                    self._launch()
            elif st == "play":
                self._move_ball(dt)
            elif st == "miss":
                self._move_ball(dt)
                if self.state_t >= MISS_S:
                    if self.lives > 0:
                        self.state, self.state_t = "score", 0.0
                    else:
                        self.best = max(self.best, self.score)
                        self.state, self.state_t = "over", 0.0
                        self.events.append((self.t, "over"))
            elif st == "score":
                if self.state_t >= SCORE_S:
                    self.direction = -self.direction
                    self._serve()
            elif st == "over":
                if self.state_t >= OVER_S:
                    self.new_game()

    def _move_ball(self, dt):
        rel0 = self.rel(self.bx)
        self.bx = (self.bx + self.vx * dt) % COLS
        self.by += self.vy * dt
        lo, hi = BALL_R, ROWS - BALL_R
        if self.by < lo:
            self.by, self.vy = 2 * lo - self.by, abs(self.vy)
        elif self.by > hi:
            self.by, self.vy = 2 * hi - self.by, -abs(self.vy)
        if self.state == "play":
            rel1, half = self.rel(self.bx), PADDLE_W / 2
            if self.vx > 0 and rel0 + BALL_R < -half <= rel1 + BALL_R:       # leading edge reached the left face
                self._at_paddle(+1, rel1 + BALL_R + half)
            elif self.vx < 0 and rel0 - BALL_R > half >= rel1 - BALL_R:     # ... the right face
                self._at_paddle(-1, half - (rel1 - BALL_R))
        self.trail.append((self.t, self.bx, self.by))

    def _at_paddle(self, d, over):
        """The ball (travelling in direction d) touches the paddle face: return it, or it is a miss."""
        r0 = self.ball_r0()
        if r0 + 2 >= self.prow - self.grace and r0 <= self.prow + PADDLE_H - 1 + self.grace:
            self.bx = (self.front - d * (PADDLE_W / 2 + BALL_R + over)) % COLS    # bounce off the face
            # Pong's "english": where it hit the paddle sets the new angle (centre = flat, ends = steep)
            o = max(-1.0, min(1.0, (self.by - (self.prow + PADDLE_H / 2.0)) / (PADDLE_H / 2.0 + BALL_R)))
            slope = SLOPE_MIN + (SLOPE_MAX - SLOPE_MIN) * abs(o) + self.rng.uniform(-0.04, 0.04)
            sign = (1 if o > 0 else -1) if abs(o) > 0.1 else self.rng.choice((-1, 1))
            self.speed = min(V_MAX, self.speed * V_GAIN)
            self.vx = -d * self.speed
            self.vy = sign * min(VY_MAX, slope * self.speed)
            self.score += 1
            self.returns_total += 1
            self.flash_t = HIT_FLASH_S
            self.events.append((self.t, "return"))
        else:
            self.lives -= 1
            self.misses_total += 1
            self.state, self.state_t = "miss", 0.0
            self.events.append((self.t, "miss"))

    # ---- drawing
    def render(self) -> np.ndarray:
        with self.lock:
            st, t, st_t = self.state, self.t, self.state_t
            bx, by, prow, flash = self.bx, self.by, self.prow, self.flash_t
            score, lives, best, trail_s = self.score, self.lives, self.best, self.trail_s
            trail = [p for p in self.trail if t - p[0] <= trail_s]
        f = np.zeros((ROWS, COLS), np.uint8)
        F = self.front
        if st in ("serve", "play", "miss"):
            s = str(score)                                        # dim HUD at the top: score left, lives right
            draw_text(f, s, F - 3 - text_width(s), ROWS - 2, HUD)
            for i in range(self.lives_per_game):
                lost_now = st == "miss" and i == lives
                if i < lives or (lost_now and blink(st_t, 6.0)):
                    fill(f, ROWS - 3, ROWS - 2, F + 3 + 3 * i, F + 4 + 3 * i, MISS if lost_now else HUD_LIFE)
            for (tt, x, y) in trail:                              # oldest first: newer, brighter pixels win
                put(f, int(math.floor(y)), int(math.floor(x)), TRAIL[min(3, int(4 * (t - tt) / trail_s))])
            r0, c0 = int(math.floor(by - 1.0)), int(math.floor(bx - 1.0))
            for dr in range(3):
                for dc in range(3):
                    put(f, r0 + dr, c0 + dc, BALL_EDGE if (dr != 1 and dc != 1) else BALL)
            if st == "miss" and blink(st_t, 6.0):
                fill(f, 0, ROWS - 1, F - 1, F, MISS)              # missed: the whole front line flashes red
            else:
                col = PADDLE_HIT if flash > 0 else (PADDLE_MISS if st == "miss" else PADDLE)
                fill(f, prow, prow + PADDLE_H - 1, F - 1, F, col)
        elif st == "score":                                       # between rallies: the score, big
            s = str(score)
            draw_text(f, s, F - text_width(s, 2) // 2, 29, BIG, scale=2)
            x0 = F - (3 * lives - 1) // 2
            for i in range(lives):
                fill(f, 14, 15, x0 + 3 * i, x0 + 3 * i + 1, HUD_LIFE)
        elif st == "over":                                        # final score: red, then blinking gold; best below
            s = str(score)
            if st_t < 1.5 or blink(st_t, 1.2):
                draw_text(f, s, F - text_width(s, 2) // 2, 29, MISS if st_t < 1.5 else BIG, scale=2)
            hs = "HI " + str(max(best, score))
            draw_text(f, hs, F - text_width(hs) // 2, 14, HUD)
        return f

    def summary(self):
        with self.lock:
            return dict(games=self.games, score=self.score, best=max(self.best, self.score), lives=self.lives,
                        returns=self.returns_total, misses=self.misses_total, speed=round(self.speed, 1),
                        state=self.state)


def predict_arrival(g):
    """Where (row) the ball's centre will be when it next reaches the paddle face (unwrapping the bounces)."""
    rel = g.rel(g.bx)
    dist = ((-PADDLE_W / 2 - BALL_R) - rel) if g.vx > 0 else (rel - (PADDLE_W / 2 + BALL_R))
    if dist < 0:
        dist += COLS
    return reflect(g.by + g.vy * dist / max(1e-6, abs(g.vx)), BALL_R, ROWS - BALL_R)


class Bot:
    """Plays for --demo / --bench / --selftest: aims at the predicted arrival row with a fresh error each rally leg."""

    def __init__(self, sigma=1.5, speed=60.0, seed=None):
        self.rng, self.sigma, self.speed = random.Random(seed), sigma, speed
        self.err, self._leg = 0.0, 0

    def vel(self, g):
        if g.state == "play":
            leg = 1 if g.vx > 0 else -1
            if leg != self._leg:
                self._leg, self.err = leg, self.rng.gauss(0.0, self.sigma)
            target = predict_arrival(g) - PADDLE_H / 2.0 + self.err
        else:
            self._leg, target = 0, (ROWS - PADDLE_H) / 2.0
        return max(-self.speed, min(self.speed, 12.0 * (target - g.py)))


# ---------------------------------------------------------------- inputs
class OneEuro:
    """One Euro filter (Casiez, Roussel, Vogel, CHI 2012): a low-pass whose cutoff rises with speed, so the paddle is
    steady when the knob rests and keeps up when it is turned fast."""

    def __init__(self, mincutoff=2.5, beta=0.08, dcutoff=1.0):
        self.mincutoff, self.beta, self.dcutoff = mincutoff, beta, dcutoff
        self.x = self.dx = self.t = None

    @staticmethod
    def _alpha(dt, fc):
        return 1.0 / (1.0 + 1.0 / (2 * math.pi * fc * dt))

    def __call__(self, x, t):
        if self.t is None:
            self.x, self.dx, self.t = x, 0.0, t
            return x
        dt = max(1e-4, t - self.t)
        self.dx += self._alpha(dt, self.dcutoff) * ((x - self.x) / dt - self.dx)
        self.x += self._alpha(dt, self.mincutoff + self.beta * abs(self.dx)) * (x - self.x)
        self.t = t
        return self.x


def parse_pots(reply):
    """"OK pot1=1,pot2=4,pot3=1023,pot4=1023" -> {"pot1": 1, ...}; {} when the panel has no values (Nano unplugged)."""
    if not reply.startswith("OK"):
        return {}
    out = {}
    for item in reply[2:].strip().split(","):
        k, _, v = item.partition("=")
        if k.strip().startswith("pot") and v.strip().lstrip("-").isdigit():
            out[k.strip()] = int(v)
    return out


class PotReader:
    """Reads one panel knob through panel.py's UDP "POTS" query (read-only; panel.py keeps the COM port)."""

    KNOB = {"pot1": "knob 4, rightmost", "pot2": "knob 3", "pot3": "knob 2", "pot4": "knob 1, leftmost"}

    def __init__(self, pot="pot1", addr="127.0.0.1:8767", span=(0.15, 0.85), invert=False, rate=125.0,
                 filt=(2.5, 0.08)):
        host, _, port = addr.partition(":")
        self.pot, self.addr, self.span, self.invert, self.period = pot, (host, int(port or 8767)), span, invert, 1.0 / rate
        self.filt = OneEuro(*filt) if filt else None
        self.raw = None
        self.y = None                 # filtered paddle bottom row (continuous)
        self.t_ok = 0.0
        self.polls = self.fails = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="pot", daemon=True)

    def label(self):
        return f"{self.pot} ({self.KNOB.get(self.pot, '?')})"

    def map(self, raw):
        """Raw 0-1023 -> paddle bottom row: the span's ends saturate, so the paddle reaches top and bottom easily."""
        lo, hi = self.span
        u = min(1.0, max(0.0, (raw / 1023.0 - lo) / (hi - lo)))
        return (1.0 - u if self.invert else u) * (ROWS - PADDLE_H)

    def start(self):
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()

    def ok(self):
        return self.y is not None and time.perf_counter() - self.t_ok < 1.0

    def wait_ok(self, timeout):
        t_end = time.perf_counter() + timeout
        while time.perf_counter() < t_end and not self.ok():
            time.sleep(0.02)
        return self.ok()

    def target(self):
        return self.y if self.ok() else None

    def _run(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.05)
        while not self._stop.is_set():
            t0 = time.perf_counter()
            self.polls += 1
            try:
                s.sendto(b"POTS", self.addr)
                v = parse_pots(s.recvfrom(512)[0].decode("utf-8", "replace")).get(self.pot)
                if v is not None:
                    now = time.perf_counter()
                    self.raw = v
                    y = self.map(v)
                    self.y = self.filt(y, now) if self.filt else y
                    self.t_ok = now
                else:
                    self.fails += 1
            except OSError:           # timeout, or WSAECONNRESET when panel.py is not running
                self.fails += 1
                time.sleep(0.2)
            time.sleep(max(0.0, self.period - (time.perf_counter() - t0)))
        s.close()


class Controls:
    """Who moves the paddle: held arrow keys win; the knob takes over again once it is turned ~1 row; the bot plays
    in --demo / --bench."""

    UP, DOWN = {"Up", "w", "W"}, {"Down", "s", "S"}

    def __init__(self, pot=None, bot=None):
        self.pot, self.bot = pot, bot
        self.keys = set()
        self._anchor = None
        self.source = "bot" if bot else "keys"

    def read(self, g):
        if self.bot:
            return None, self.bot.vel(g)
        keys = set(self.keys)
        v = KEY_SPEED * ((1 if keys & self.UP else 0) - (1 if keys & self.DOWN else 0))
        pt = self.pot.target() if self.pot else None
        if v:
            self._anchor, self.source = pt, "keys"
            return None, v
        if pt is not None and (self._anchor is None or abs(pt - self._anchor) > 1.0):
            self._anchor, self.source = None, self.pot.pot
            return pt, 0.0
        return None, 0.0


def game_loop(game, ctl, stop):
    """Fixed 120 Hz physics on its own thread (input is read every step: knob or keys -> paddle within 8 ms)."""
    last, acc = time.perf_counter(), 0.0
    while not stop.is_set():
        now = time.perf_counter()
        acc += min(0.1, now - last)
        last = now
        while acc >= DT:
            target, vel = ctl.read(game)
            game.step(DT, target, vel)
            acc -= DT
        time.sleep(0.002)


# ---------------------------------------------------------------- the column (live mode)
RLE_MAX = 2049                        # firmware POV_LIVE_RLE_MAX


def rle_frame(b):
    """RLE live frame (firmware 0.4.1+, pova.h pov_live_rle_decode): b"R" + (run, index) pairs, row-major, runs <= 255.
    Odd length by construction, so the board never mistakes it for a raw 4,032-byte frame. A game frame: ~150 B."""
    out = bytearray(b"R")
    i, n = 0, len(b)
    while i < n:
        j, v = i, b[i]
        while j < n and b[j] == v and j - i < 255:
            j += 1
        out += bytes((j - i, v))
        i = j
    return bytes(out)


def _board(host):
    import pov_ctl                     # software/firmware/tools: HTTP helper + the API token (never printed)
    return pov_ctl.Board(host)


def board_check(host, strict, force, log=print):
    """Status before streaming. Returns the status to restore at the end, or None (no answer / busy / OTA)."""
    b = _board(host)
    st = b.status(timeout=3, tries=1)
    if not st:
        log(f"column {host}: no answer (switched off or out of range)")
        return None
    mode, anim = st.get("mode", "?"), st.get("anim", "")
    log(f"column {host}: fw {st.get('fw')}, mode {mode}{' ' + anim if anim else ''}, {st.get('rpm', 0):.0f} rpm, "
        f"brightness gb {st.get('gb')}, front_only {st.get('front_only')}, rssi {st.get('rssi')}")
    if st.get("ota_active") or st.get("paused"):
        log("column: the display is paused for an OTA update; leaving it alone")
        return None
    busy = mode not in ("off", "live")
    if mode == "live":                                   # another live sender still streaming?
        n0 = (st.get("diag") or {}).get("live_frames", 0)
        time.sleep(1.0)
        st2 = b.status(timeout=3, tries=1) or {}
        if (st2.get("diag") or {}).get("live_frames", 0) > n0:
            log("column: another program is streaming live frames to it")
            if not force:
                log("column: not taking over (use --force)")
                return None
    if busy and strict and not force:
        log(f"column: busy ({mode} {anim}); the bench only runs on an idle column (use --force)")
        return None
    if busy:
        log(f"column: taking over from {mode} {anim}; it goes back when the game ends")
    return st


def board_restore(host, st0, log=print):
    b = _board(host)
    if st0.get("mode") == "anim" and st0.get("anim"):
        code, _ = b.req("POST", "/api/play", {"name": st0["anim"]}, timeout=4, tries=2)
        log(f"column: back to {st0['anim']} (HTTP {code})")
    else:
        code, _ = b.req("POST", "/api/stop", timeout=4, tries=2)
        log(f"column: stopped, mode off (HTTP {code})")


def board_counters(host):
    st = _board(host).status(timeout=3, tries=1) or {}
    d = st.get("diag") or {}
    return dict(live_frames=d.get("live_frames"), live_bad=d.get("live_bad"), rpm=st.get("rpm"), gb_used=st.get("gb_used"),
                rssi=st.get("rssi"), mode=st.get("mode"), lag1_ms=d.get("lag1_ms"), col_busy_pct=d.get("col_busy_pct"))


class ColumnLink:
    """Streams frames to the column's live mode, paced by the board's acks (see the module docstring). Runs on its
    own thread: waits until fewer than `window` frames are unacknowledged, renders the newest state, sends it."""

    def __init__(self, host, palette, get_frame, max_fps=30.0, window=1, log=print, on_interval=None, rle=False):
        import pov_ctl
        tok = pov_ctl.token()
        self.url = f"ws://{host}/ws" + (f"?token={tok}" if tok else "")
        self.host, self.pal, self.get_frame = host, [list(c) for c in palette], get_frame
        self.max_fps, self.window, self.log, self.on_interval = max_fps, max(1, window), log, on_interval
        self.rle = rle                # send RLE frames (the board reported diag.live_rle)
        self.bytes = 0
        self.ws = None
        self.cv = threading.Condition()
        self.seq = self.acked = 0
        self.sent_at = {}
        self.rtts = collections.deque(maxlen=2000)
        self.send_times = collections.deque(maxlen=240)
        self.frames = self.reconnects = self.skipped = 0
        self.acks = None              # True: the firmware answers live acks (0.4+)
        self.errors = []
        self.state = "connecting"
        self.t0 = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="column-link", daemon=True)

    def start(self):
        self.t0 = time.perf_counter()
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        with self.cv:
            self.cv.notify_all()
        self._drop()
        self._thread.join(timeout=3)

    def _drop(self):
        ws, self.ws = self.ws, None
        if ws is not None:
            try:
                ws.shutdown()         # plain TCP close, NO WebSocket close handshake (Wi-Fi review 2026-11-14, 3.2)
            except Exception:
                pass
        with self.cv:
            self.sent_at.clear()
            self.acked = self.seq
            self.cv.notify_all()

    def _broken(self, ws, why):
        if ws is not self.ws:
            return                    # already handled (the other thread saw it first)
        self.errors.append(why)
        self.reconnects += 1
        self.log(f"column link broke ({why}); reconnecting")
        self._drop()

    def _connect(self):
        import websocket              # websocket-client
        ws = websocket.create_connection(self.url, timeout=5, enable_multithread=True)
        ws.send(json.dumps({"live": 1, "pal": self.pal}))
        if self.acks is None:
            ws.send(json.dumps({"live": 1, "ack": 0}))
            self.acks = False
            t_end = time.time() + 2.0
            while time.time() < t_end:
                ws.settimeout(max(0.05, t_end - time.time()))
                try:
                    m = ws.recv()
                except Exception:
                    break
                if isinstance(m, str) and "live_ack" in m:
                    self.acks = True
                    break
            ws.settimeout(5)
            self.log("column: live mode on, acks on (paced by the board)" if self.acks else
                     "column: no live acks (firmware < 0.4): fixed pace, max 4 frames/s")
        self.ws = ws
        threading.Thread(target=self._reader, args=(ws,), name="column-acks", daemon=True).start()

    def _reader(self, ws):
        import websocket
        while not self._stop.is_set() and ws is self.ws:
            try:
                m = ws.recv()
            except websocket.WebSocketTimeoutException:
                continue
            except Exception as e:
                self._broken(ws, f"recv: {type(e).__name__}: {e}")
                return
            if not isinstance(m, str) or "live_ack" not in m:
                continue
            try:
                n = int(json.loads(m)["live_ack"])
            except (ValueError, KeyError, TypeError):
                continue
            now = time.perf_counter()
            with self.cv:
                for k in [k for k in self.sent_at if k <= n]:
                    t_sent = self.sent_at.pop(k)
                    if k == n:
                        self.rtts.append(now - t_sent)
                self.acked = max(self.acked, n)
                self.cv.notify_all()

    def _run(self):
        backoff, last_frame, t_last = 1.0, None, 0.0
        while not self._stop.is_set():
            if self.ws is None:
                self.state = "connecting"
                try:
                    self._connect()
                    backoff, last_frame, self.state = 1.0, None, "streaming"
                except Exception as e:
                    self.state = f"no link ({type(e).__name__})"
                    self.errors.append(f"connect: {e}")
                    self._stop.wait(backoff)
                    backoff = min(8.0, backoff * 2)
                    continue
            ws = self.ws
            with self.cv:             # 1) at most `window` frames unacknowledged
                ok = self.cv.wait_for(lambda: self._stop.is_set() or self.ws is not ws or not self.acks
                                      or self.seq - self.acked < self.window, timeout=3.0)
            if self._stop.is_set():
                break
            if self.ws is not ws:
                continue
            if not ok:
                self._broken(ws, "no ack for 3 s (link stalled)")
                continue
            fps = self.max_fps if self.acks else min(self.max_fps, 4.0)
            wait = t_last + 1.0 / fps - time.perf_counter()     # 2) no faster than --fps
            if wait > 0:
                time.sleep(wait)
            frame = self.get_frame()                             # 3) the newest game state, rendered now
            if frame == last_frame and time.perf_counter() - t_last < 1.0:
                self.skipped += 1                                # unchanged: send nothing (keep-alive once a second)
                time.sleep(0.004)
                continue
            msg = frame
            if self.rle:
                packed = rle_frame(frame)
                if len(packed) <= RLE_MAX:
                    msg = packed
            try:
                ws.send_binary(msg)
                self.bytes += len(msg)
                t_sent = time.perf_counter()
                if self.acks:
                    with self.cv:
                        self.seq += 1
                        n = self.seq
                        self.sent_at[n] = t_sent
                    ws.send(json.dumps({"live": 1, "ack": n}))
            except Exception as e:
                self._broken(ws, f"send: {type(e).__name__}: {e}")
                self._stop.wait(backoff)
                backoff = min(8.0, backoff * 2)
                continue
            if t_last and self.on_interval:
                self.on_interval(t_sent - t_last)
            last_frame, t_last = frame, t_sent
            self.frames += 1
            self.send_times.append(t_sent)

    def stats(self):
        now = time.perf_counter()
        recent = [t for t in self.send_times if now - t <= 2.0]
        fps_now = (len(recent) - 1) / (recent[-1] - recent[0]) if len(recent) > 2 and recent[-1] > recent[0] else 0.0
        r = sorted(self.rtts)
        el = now - self.t0 if self.t0 else 0.0
        ms = lambda x: round(1000 * x, 1)  # noqa: E731
        return dict(state=self.state, frames=self.frames, secs=round(el, 1), fps_avg=round(self.frames / el, 2) if el else 0,
                    fps_now=round(fps_now, 1), kb_s=round(self.bytes / 1024 / el, 1) if el else 0, rle=self.rle,
                    bytes_per_frame=round(self.bytes / self.frames) if self.frames else None,
                    acks=self.acks, ack_med_ms=ms(statistics.median(r)) if r else None,
                    ack_p95_ms=ms(r[max(0, int(len(r) * 0.95) - 1)]) if len(r) >= 20 else None,
                    ack_max_ms=ms(r[-1]) if r else None, reconnects=self.reconnects, skipped=self.skipped,
                    window=self.window, errors=self.errors[-3:])


# ---------------------------------------------------------------- the simulator view
class SimView:
    """What the column shows, drawn on the PC: the column seen from the front (povsim's Camera: ideal persistence,
    lambertian fall-off, a soft glow) over the unwrapped 360 deg strip (front window boxed, paddle column marked)."""

    S = 5                             # strip scale, px per LED

    def __init__(self, front=FRONT_CENTRE):
        from PIL import Image, ImageDraw, ImageFilter
        from simulate import Camera
        self.Image, self.ImageDraw, self.ImageFilter = Image, ImageDraw, ImageFilter
        self.front = front
        self.W, self.HC = COLS * self.S, 420
        self.cam = Camera(width=self.W, height=self.HC, dist_mm=900.0, view_col=front, fill=0.82)
        self.u, self.v, self.cos_e, self.wpx, self.hpx = self.cam.project()
        self.pal = np.array(PAL, np.uint8)
        self.pal_lin = (self.pal / 255.0) ** 2.2

    def image(self, f):
        Image, ImageDraw = self.Image, self.ImageDraw
        img = Image.new("RGB", (self.W, self.HC), (0, 0, 0))
        d = ImageDraw.Draw(img)
        self.cam.outline(d)
        lin = self.pal_lin[f] * self.cos_e[None, :, None]
        srgb = (255 * np.clip(lin, 0, 1) ** (1 / 2.2)).astype(np.uint8)
        for r, c in zip(*np.nonzero((f != 0) & (self.cos_e[None, :] > 0.02))):
            x, y, w, h = self.u[r, c], self.v[r, c], self.wpx[c] / 2, self.hpx[c] / 2
            d.ellipse([x - w, y - h, x + w, y + h], fill=tuple(int(q) for q in srgb[r, c]))
        glow = img.resize((self.W // 4, self.HC // 4), Image.BILINEAR).filter(self.ImageFilter.GaussianBlur(2))
        a = np.asarray(img).astype(np.int16) + (0.8 * np.asarray(glow.resize((self.W, self.HC), Image.BILINEAR))).astype(np.int16)
        cyl = np.clip(a, 0, 255).astype(np.uint8)
        S = self.S                                       # the unwrapped strip, row 0 at the bottom, LED grid lines
        big = np.repeat(np.repeat(self.pal[f[::-1]], S, 0), S, 1)
        big[np.repeat(np.repeat(f[::-1] == 0, S, 0), S, 1)] = (18, 18, 22)
        big[::S, :] = 0
        big[:, ::S] = 0
        out = np.zeros((self.HC + 8 + ROWS * S + 8, self.W, 3), np.uint8)
        out[:self.HC] = cyl
        out[self.HC + 8:self.HC + 8 + ROWS * S] = big
        img = Image.fromarray(out)
        d = ImageDraw.Draw(img)
        y0, F = self.HC + 8, self.front
        x0, x1 = (F - FRONT_WIDTH // 2) * S, (F + FRONT_WIDTH // 2) * S
        d.rectangle([x0, y0 - 2, x1, y0 + ROWS * S + 1], outline=(70, 70, 80))
        d.polygon([(F * S - 4, y0 + ROWS * S + 7), (F * S + 4, y0 + ROWS * S + 7), (F * S, y0 + ROWS * S + 2)], fill=(0, 160, 190))
        return img


def stills(out_dir, seconds=8.0, fps=15.0, seed=5, log=print):
    """Headless b-roll: a bot game drawn by SimView, one PNG per frame + an animated GIF (software/out by default)."""
    os.makedirs(out_dir, exist_ok=True)
    g, view = Game(seed=seed), SimView()
    ctl = Controls(None, Bot(sigma=1.2, seed=seed))
    frames, per = [], max(1, int(round(1.0 / (fps * DT))))
    g.set_frame_interval(1.0 / fps)
    for i in range(int(seconds / DT)):
        target, vel = ctl.read(g)
        g.step(DT, target, vel)
        if i % per == 0:
            img = view.image(g.render())
            img.save(os.path.join(out_dir, f"orbit_rally_{len(frames):04d}.png"))
            frames.append(img)
    gif = os.path.join(out_dir, "orbit_rally.gif")
    frames[0].save(gif, save_all=True, append_images=frames[1:], duration=int(1000 / fps), loop=0)
    log(f"{len(frames)} frames -> {out_dir} (+ orbit_rally.gif)")
    return 0


# ---------------------------------------------------------------- the window
class Preview:
    """The game window: SimView of the newest frame (the same frame the column gets) + status lines; keys."""

    def __init__(self, game, ctl, link=None, pot=None, stop=None, fps=30.0, where=""):
        import tkinter as tk
        from PIL import ImageTk
        self.ImageTk = ImageTk
        self.game, self.ctl, self.link, self.pot, self.stop = game, ctl, link, pot, stop or threading.Event()
        self.period, self.where = int(1000 / fps), where
        self.view_ = SimView(game.front)
        self.root = tk.Tk()
        self.root.title("Orbit Rally - POV LED Column")
        self.root.configure(bg="#000000")
        self.view = tk.Label(self.root, bg="#000000", bd=0)
        self.view.pack()
        self.text = tk.Label(self.root, bg="#000000", fg="#c8c8c8", font=("Consolas", 10), justify="left", anchor="w")
        self.text.pack(fill="x", padx=6, pady=(2, 6))
        self.root.bind("<KeyPress>", self._key_down)
        self.root.bind("<KeyRelease>", self._key_up)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(150, self.root.focus_force)
        self._photo = None

    def _key_down(self, e):
        k = e.keysym
        if k in ("Escape", "q", "Q"):
            self.close()
        elif k == "space":
            self.game.new_game()
        elif k in ("p", "P"):
            self.game.toggle_pause()
        else:
            self.ctl.keys.add(k)

    def _key_up(self, e):
        self.ctl.keys.discard(e.keysym)

    def close(self):
        self.stop.set()

    def status(self):
        g = self.game.summary()
        st = "PAUSED" if self.game.paused else g["state"].upper()
        lines = [f"ORBIT RALLY   score {g['score']}   best {g['best']}   lives {g['lives']}   "
                 f"ball {g['speed']:.0f} col/s   [{st}]"]
        src = self.ctl.source
        if self.pot is not None:
            pot = f"{self.pot.label()} raw {self.pot.raw}" if self.pot.ok() else f"{self.pot.pot}: panel not answering"
            lines.append(f"control: {'keys' if src == 'keys' else 'knob'}   {pot}")
        else:
            lines.append(f"control: {src}")
        if self.link is not None:
            s = self.link.stats()
            ack = f"ack {s['ack_med_ms']} ms (p95 {s['ack_p95_ms']})" if s["ack_med_ms"] is not None else "ack -"
            lines.append(f"column {self.where}: {s['state']}  {s['fps_now']} fps  {ack}  frames {s['frames']}  "
                         f"reconnects {s['reconnects']}")
        else:
            lines.append("simulator only (no column)")
        lines.append("Up/Down or W/S paddle   Space new game   P pause   Esc quit")
        return "\n".join(lines)

    def _tick(self):
        if self.stop.is_set() or (self.quit_at and time.perf_counter() >= self.quit_at):
            if self.snap and self.last_img is not None:
                self.last_img.save(self.snap)
            self.stop.set()
            self.root.destroy()
            return
        self.last_img = self.view_.image(self.game.render())
        self._photo = self.ImageTk.PhotoImage(self.last_img)
        self.view.configure(image=self._photo)
        self.text.configure(text=self.status())
        self.root.after(self.period, self._tick)

    def run(self, quit_after=None, snap=None):
        """quit_after (s) / snap (PNG of the last view) are for tests and screenshots."""
        self.quit_at = time.perf_counter() + quit_after if quit_after else None
        self.snap, self.last_img = snap, None
        self.root.after(0, self._tick)
        self.root.mainloop()


# ---------------------------------------------------------------- headless checks
def selftest(minutes=10.0, seed=7, log=print):
    """A bot plays `minutes` of game time as fast as it computes; every 0.2 s of game time the frame is checked:
    4,032 bytes, palette indices in range, and the board's current model (povanim.current_profile = povframe.h, incl.
    idle + ESP32) at full brightness under the 2,600 mA cap, so the firmware never has to dim a game frame."""
    from povanim import current_profile
    g, bot = Game(seed=seed), Bot(sigma=3.0, seed=seed)
    ctl = Controls(None, bot)
    pal = np.array(PAL, float)
    worst_ma, lit_max, checked, problems = 0.0, 0.0, 0, []
    for i in range(int(minutes * 60 / DT)):
        target, vel = ctl.read(g)
        g.step(DT, target, vel)
        if i % 24 == 0:
            f = g.render()
            checked += 1
            if f.shape != (ROWS, COLS) or len(f.tobytes()) != ROWS * COLS or int(f.max()) >= len(PAL):
                problems.append(f"bad frame at t={g.t:.2f}")
            worst_ma = max(worst_ma, float(current_profile(f, pal, 31).max()))
            lit_max = max(lit_max, float((f != 0).mean()))
    s = g.summary()
    rep = dict(minutes=minutes, frames_checked=checked, returns=s["returns"], misses=s["misses"], games=s["games"],
               best=s["best"], worst_ma_gb31=round(worst_ma), cap_ma=CAP_MA, lit_max_pct=round(100 * lit_max, 2),
               problems=problems[:5])
    ok = (not problems and worst_ma < CAP_MA and s["returns"] > 20 and s["misses"] > 0
          and (s["games"] > 1 or minutes < 5))          # a game over takes 3 misses: only in longer runs
    log(json.dumps(rep))
    log("selftest " + ("PASSED" if ok else "FAILED"))
    return 0 if ok else 1


# ---------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="Start: --pot (knob), --keys (arrows) or --sim (window only).")
    ap.add_argument("--pot", nargs="?", const="pot1", default=None, metavar="POTn",
                    help="knob control (default pot1 = knob 4, the rightmost); keys still work")
    ap.add_argument("--keys", action="store_true", help="arrow keys / W-S only (do not read the panel)")
    ap.add_argument("--sim", action="store_true", help="simulator window only, no column")
    ap.add_argument("--demo", action="store_true", help="the bot plays (attract mode / b-roll)")
    ap.add_argument("--bench", type=float, metavar="SECONDS", help="bot plays on the column; prints link numbers")
    ap.add_argument("--selftest", nargs="?", type=float, const=10.0, metavar="MINUTES", help="headless bot run + checks")
    ap.add_argument("--host", default=os.environ.get("POV_HOST", "pov.local"), help="column address [host[:port]]")
    ap.add_argument("--fps", type=float, default=30.0, help="max frames/s to the column (its refresh is ~30 Hz)")
    ap.add_argument("--window", type=int, default=1, help="max unacknowledged frames (1 = least latency)")
    ap.add_argument("--rle", choices=["auto", "on", "off"], default="auto",
                    help="RLE frames (~150 B instead of 4,032 B): auto = when the firmware reports live_rle (0.4.1+)")
    ap.add_argument("--force", action="store_true", help="take the column even if it is busy")
    ap.add_argument("--no-restore", action="store_true", help="leave the column dark/live at the end")
    ap.add_argument("--front", type=int, default=FRONT_CENTRE, help="paddle image column (default 48 = front)")
    ap.add_argument("--panel", default="127.0.0.1:8767", help="panel.py UDP control channel")
    ap.add_argument("--pot-span", default="0.15,0.85", help="part of the knob's turn mapped to the paddle travel")
    ap.add_argument("--pot-invert", action="store_true", help="turning the knob the other way moves the paddle up")
    ap.add_argument("--grace", type=int, default=GRACE, help="rows of forgiveness at the paddle ends")
    ap.add_argument("--headless", action="store_true", help="no window (bench / demo on the column)")
    ap.add_argument("--stills", nargs="?", const=os.path.join(SOFTWARE, "out", "orbit_rally"), metavar="DIR",
                    help="headless b-roll: a bot game as PNGs + GIF (default software/out/orbit_rally)")
    ap.add_argument("--seconds", type=float, default=8.0, help="length of --stills")
    ap.add_argument("--quit-after", type=float, metavar="S", help=argparse.SUPPRESS)   # tests / screenshots
    ap.add_argument("--snap", metavar="PNG", help=argparse.SUPPRESS)
    ap.add_argument("--seed", type=int)
    ap.add_argument("--speed", type=float, default=1.0, help="ball speed multiplier (start and cap), e.g. 1.4")
    a = ap.parse_args(argv)
    if a.speed != 1.0:
        global V0, V_MAX
        V0, V_MAX = V0 * a.speed, V_MAX * a.speed

    if a.selftest is not None:
        return selftest(a.selftest, seed=a.seed if a.seed is not None else 7)
    if a.stills:
        return stills(a.stills, a.seconds, seed=a.seed if a.seed is not None else 5)
    game = Game(seed=a.seed, front=a.front, grace=a.grace)
    bot = Bot(sigma=1.2, seed=a.seed) if (a.demo or a.bench) else None
    pot = None
    if not a.keys and not bot:
        lo, hi = (float(x) for x in a.pot_span.split(","))
        pot = PotReader(a.pot or "pot1", a.panel, span=(lo, hi), invert=a.pot_invert).start()
        if pot.wait_ok(0.6):
            print(f"knob: {pot.label()} via panel.py UDP {a.panel} (raw {pot.raw}); arrow keys override")
        else:
            print(f"knob: panel.py not answering on {a.panel} with {pot.pot}; arrow keys / W-S play "
                  "(the knob joins as soon as the panel answers)")
    ctl = Controls(pot, bot)
    stop = threading.Event()
    link = st0 = None
    if not a.sim:
        st0 = board_check(a.host, strict=bool(a.bench), force=a.force)
        if st0 is None:
            if a.bench or a.headless:
                return 2
            print("running in the simulator window only")
        else:
            c0 = board_counters(a.host)
            rle = a.rle == "on" or (a.rle == "auto" and bool((st0.get("diag") or {}).get("live_rle")))
            print(f"column: {'RLE frames (~150 B)' if rle else 'raw 4,032-byte frames'}")
            link = ColumnLink(a.host, PAL, lambda: game.render().tobytes(), max_fps=a.fps, window=a.window,
                              on_interval=game.set_frame_interval, rle=rle).start()
    threading.Thread(target=game_loop, args=(game, ctl, stop), name="game", daemon=True).start()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    rc = 0
    try:
        if a.headless or a.bench:
            t_end = time.time() + (a.bench or a.quit_after or 1e9)
            while time.time() < t_end and not stop.is_set():
                time.sleep(0.25)
        else:
            Preview(game, ctl, link=link, pot=pot, stop=stop, where=a.host).run(a.quit_after, a.snap)
    finally:
        stop.set()
        if pot:
            pot.stop()
        if link:
            link.stop()
            s = link.stats()
            c1 = board_counters(a.host)
            if c0.get("live_frames") is not None and c1.get("live_frames") is not None:
                s["board_live_frames"] = c1["live_frames"] - c0["live_frames"]
                s["board_live_bad"] = (c1.get("live_bad") or 0) - (c0.get("live_bad") or 0)
            s["board"] = {k: c1.get(k) for k in ("rpm", "gb_used", "rssi", "lag1_ms", "col_busy_pct")}
            s["game"] = game.summary()
            print("link: " + json.dumps(s))
            if not a.no_restore:
                board_restore(a.host, st0)
            if a.bench and (s["frames"] == 0 or s.get("board_live_bad")):
                rc = 1
        print("game: " + json.dumps(game.summary()))
    return rc


if __name__ == "__main__":
    sys.exit(main())
