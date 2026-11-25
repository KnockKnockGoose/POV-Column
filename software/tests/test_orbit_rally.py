"""Orbit Rally (software/games/orbit_rally.py): rules, frame format, current, knob path and the live-mode sender.

The sender test runs against tools/mock_board.py (the firmware's live mode on 127.0.0.1); the real column is never
touched. py -m pytest software/tests/test_orbit_rally.py -q
"""
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import json

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
SOFTWARE = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(SOFTWARE, "games"))
import orbit_rally as o  # noqa: E402


def approach(g, side, row, paddle_row, speed=40.0):
    """Put the ball 0.3 column short of a paddle face, flying at it."""
    g.state, g.state_t = "play", 0.0
    g.prow, g.py = paddle_row, float(paddle_row)
    d = 1 if side == "left" else -1
    g.bx = (g.front - d * (o.PADDLE_W / 2 + o.BALL_R + 0.3)) % o.COLS
    g.by, g.vx, g.vy = row, d * speed, 0.0


def run(g, steps, target=None):
    for _ in range(steps):
        g.step(o.DT, target=target if target is not None else g.py)


@pytest.mark.parametrize("side", ["left", "right"])
def test_return_reverses_and_scores(side):
    g = o.Game(seed=1)
    approach(g, side, row=20.5, paddle_row=17)        # ball rows 19-21, paddle rows 17-24
    vx0 = g.vx
    run(g, 6)
    assert g.score == 1 and g.state == "play" and g.lives == o.LIVES
    assert np.sign(g.vx) == -np.sign(vx0) and abs(g.vx) == pytest.approx(min(o.V_MAX, o.V0 * o.V_GAIN))
    assert abs(g.rel(g.bx)) >= o.PADDLE_W / 2 + o.BALL_R  # bounced off the face, not inside the paddle


def test_miss_costs_a_life_then_shows_score_and_serves():
    g = o.Game(seed=2)
    approach(g, "left", row=35.5, paddle_row=2)       # ball rows 34-36, paddle rows 2-9: miss
    run(g, 6)
    assert g.state == "miss" and g.lives == o.LIVES - 1 and g.score == 0
    run(g, int((o.MISS_S + 0.05) / o.DT))
    assert g.state == "score"
    run(g, int((o.SCORE_S + 0.05) / o.DT))
    assert g.state == "serve"


def test_grace_row_counts_as_a_hit():
    g = o.Game(seed=3)
    approach(g, "left", row=11.5, paddle_row=12)      # ball rows 10-12... touches paddle row 12
    run(g, 6)
    assert g.score == 1
    g = o.Game(seed=3)
    approach(g, "left", row=10.5, paddle_row=12)      # ball rows 9-11: one row short, inside GRACE = 1
    run(g, 6)
    assert g.score == 1
    g = o.Game(seed=3)
    approach(g, "left", row=9.5, paddle_row=12)       # ball rows 8-10: two rows short = miss
    run(g, 6)
    assert g.state == "miss"


def test_ball_wraps_round_the_back_without_a_paddle_check():
    g = o.Game(seed=4)
    g.state, g.prow, g.py = "play", 0, 0.0
    g.bx, g.by, g.vx, g.vy = (g.front + 47.0) % o.COLS, 30.0, 40.0, 0.0   # behind the column, heading on round
    run(g, 12)
    assert g.state == "play" and g.score == 0 and g.lives == o.LIVES


def test_game_over_restarts_by_itself():
    g = o.Game(seed=5)
    g.lives = 1
    approach(g, "left", row=35.5, paddle_row=2)
    run(g, int((o.MISS_S + 0.1) / o.DT))
    assert g.state == "over"
    run(g, int((o.OVER_S + 0.1) / o.DT))
    assert g.state == "serve" and g.lives == o.LIVES and g.games == 2


def test_frame_format_and_orientation():
    g = o.Game(seed=6)
    g.prow = g.py = 0                                  # paddle at the bottom
    run(g, 2, target=0.0)
    f = g.render()
    b = f.tobytes()
    assert f.dtype == np.uint8 and f.shape == (42, 96) and len(b) == 4032 and int(f.max()) < len(o.PAL) <= 32
    # row 0 = bottom = first 96 bytes on the wire (firmware frame[row * 96 + c]); the paddle is in columns 47-48
    assert b[0 * 96 + 47] == o.PADDLE and b[0 * 96 + 48] == o.PADDLE and b[8 * 96 + 47] != o.PADDLE


def test_selftest_bot_and_current_cap():
    assert o.selftest(minutes=6.0, seed=11, log=lambda *_: None) == 0     # ~1.5 s: covers game over too


def test_parse_pots_and_mapping():
    assert o.parse_pots("OK pot1=1,pot2=4,pot3=1023,pot4=1023") == {"pot1": 1, "pot2": 4, "pot3": 1023, "pot4": 1023}
    assert o.parse_pots("OK ") == {} and o.parse_pots("ERR music mode is OFF") == {}
    p = o.PotReader("pot1", span=(0.15, 0.85))
    top = o.ROWS - o.PADDLE_H
    assert p.map(0) == 0 and p.map(1023) == top and p.map(512) == pytest.approx(top / 2, abs=0.2)
    p.invert = True
    assert p.map(0) == top


def test_pot_reader_against_a_fake_panel():
    """A UDP stand-in for panel.py's POTS channel: the reader parses, maps and filters the right knob."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    srv.bind(("127.0.0.1", 0))
    port = srv.getsockname()[1]
    value = {"v": 1023}
    stop = threading.Event()

    def serve():
        srv.settimeout(0.1)
        while not stop.is_set():
            try:
                _, addr = srv.recvfrom(64)
            except OSError:
                continue
            srv.sendto(f"OK pot1={value['v']},pot2=4,pot3=0,pot4=0".encode(), addr)

    threading.Thread(target=serve, daemon=True).start()
    p = o.PotReader("pot1", f"127.0.0.1:{port}").start()
    try:
        assert p.wait_ok(1.0) and p.target() == pytest.approx(o.ROWS - o.PADDLE_H, abs=0.01)
        value["v"] = 0
        time.sleep(0.25)                                # One Euro: a full swing settles in ~50 ms
        assert p.target() == pytest.approx(0.0, abs=0.3)
    finally:
        p.stop()
        stop.set()


def test_keys_override_the_knob_until_it_moves():
    class FakePot:
        pot, y = "pot1", 10.0

        def target(self):
            return self.y

    pot = FakePot()
    c = o.Controls(pot)
    g = o.Game(seed=7)
    assert c.read(g) == (10.0, 0.0)
    c.keys.add("Up")
    assert c.read(g) == (None, o.KEY_SPEED) and c.source == "keys"
    c.keys.clear()
    assert c.read(g) == (None, 0.0)                   # knob still where it was: keys keep the paddle
    pot.y = 11.5
    assert c.read(g) == (11.5, 0.0) and c.source == "pot1"


def test_physics_thread_keeps_real_time():
    g = o.Game(seed=8)
    stop = threading.Event()
    th = threading.Thread(target=o.game_loop, args=(g, o.Controls(), stop), daemon=True)
    t0 = time.perf_counter()
    th.start()
    time.sleep(1.5)
    stop.set()
    th.join(1)
    assert g.t == pytest.approx(time.perf_counter() - t0, abs=0.08)


def start_mock(*extra):
    tools = os.path.join(SOFTWARE, "firmware", "tools")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    p = subprocess.Popen([sys.executable, os.path.join(tools, "mock_board.py"), "--http-port", str(port),
                          "--no-arduino-ota", "--mode", "anim", "--anim", "dog_ball_front", *extra],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    host = f"127.0.0.1:{port}"
    for _ in range(50):
        try:
            urllib.request.urlopen(f"http://{host}/api/status", timeout=0.5).read()
            break
        except OSError:
            time.sleep(0.1)
    return p, host


@pytest.fixture
def mock_board():
    p, host = start_mock()
    yield host
    p.kill()


@pytest.fixture
def mock_board_rle():
    p, host = start_mock("--live-rle")
    yield host
    p.kill()


def test_streams_to_the_mock_board_and_puts_it_back(mock_board):
    host = mock_board
    st0 = o.board_check(host, strict=False, force=False, log=lambda *_: None)
    assert st0 and st0["mode"] == "anim"                 # interactive play takes over a playing animation...
    assert o.board_check(host, strict=True, force=False, log=lambda *_: None) is None   # ...the bench does not
    g = o.Game(seed=9)
    stop = threading.Event()
    threading.Thread(target=o.game_loop, args=(g, o.Controls(None, o.Bot(seed=9)), stop), daemon=True).start()
    link = o.ColumnLink(host, o.PAL, lambda: g.render().tobytes(), max_fps=30, window=1, log=lambda *_: None).start()
    time.sleep(3.0)
    link.stop()
    stop.set()
    s = link.stats()
    c = o.board_counters(host)
    assert s["acks"] and s["reconnects"] == 0 and s["frames"] >= 20
    assert c["live_bad"] == 0 and s["frames"] - 1 <= c["live_frames"] <= s["frames"]
    o.board_restore(host, st0, log=lambda *_: None)
    events = json.loads(urllib.request.urlopen(f"http://{host}/mock/events", timeout=2).read())
    names = [e if isinstance(e, str) else e.get("what", "") for e in (events if isinstance(events, list) else events.get("events", []))]
    assert "ws-close-frame" not in names                 # closed without the WebSocket close handshake
    assert "play" in names                               # the animation that was playing is put back


def test_rle_frame_format():
    """Live RLE frames (firmware 0.4.1, pova.h pov_live_rle_decode): 'R' + (run, index) pairs, odd length, 4032 px."""
    dark = o.rle_frame(bytes(4032))
    assert dark == b"R" + bytes((255, 0)) * 15 + bytes((207, 0))          # the vector test_pova checks in C++
    g = o.Game(seed=12)
    ctl = o.Controls(None, o.Bot(seed=12))
    for _ in range(600):
        t, v = ctl.read(g)
        g.step(o.DT, t, v)
    raw = g.render().tobytes()
    msg = o.rle_frame(raw)
    assert len(msg) % 2 == 1 and len(msg) <= o.RLE_MAX and msg[0] == ord("R")
    out = b"".join(bytes((msg[k + 1],)) * msg[k] for k in range(1, len(msg), 2))
    assert out == raw


def test_streams_rle_frames_when_the_board_offers_them(mock_board_rle):
    host = mock_board_rle
    st0 = o.board_check(host, strict=False, force=False, log=lambda *_: None)
    assert (st0.get("diag") or {}).get("live_rle") is True
    g = o.Game(seed=13)
    stop = threading.Event()
    threading.Thread(target=o.game_loop, args=(g, o.Controls(None, o.Bot(seed=13)), stop), daemon=True).start()
    link = o.ColumnLink(host, o.PAL, lambda: g.render().tobytes(), max_fps=30, window=1, log=lambda *_: None,
                        rle=True).start()
    time.sleep(3.0)
    link.stop()
    stop.set()
    s, c = link.stats(), o.board_counters(host)
    assert s["frames"] >= 20 and c["live_bad"] == 0 and s["frames"] - 1 <= c["live_frames"] <= s["frames"]
    assert s["bytes_per_frame"] < 400
    o.board_restore(host, st0, log=lambda *_: None)
