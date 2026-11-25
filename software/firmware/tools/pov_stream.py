#!/usr/bin/env python3
r"""pov_stream.py - stream live frames to the POV column without overrunning the link (Wi-Fi control review 2026-11-14).

  py tools\pov_stream.py rowwalk [--fps 6] [--minutes 5]     one lit row stepping bottom -> top (pov_rowwalk.py)
  py tools\pov_stream.py stripes [--fps 6] [--minutes 30]    diagonal colour stripes (pov_diag.py)
  py tools\pov_stream.py solid --minutes 1                   every pixel palette 1 (white): a current test, careful

Why a new streamer: on 11-14 pov_rowwalk.py sent each 4,032-byte frame three times per 0.3 s step (40 KB/s) and
pov_diag.py sends 15 frames/s (60 KB/s), over a link that carried ~20 KB/s in the sled. The socket backed up until a
send timed out (WebSocketTimeoutException after ~40 s); the reconnects that followed closed each socket with a
WebSocket close handshake, the path in which the web server library frees the connection object while it is still
in use (review section 3.2). This one
  * paces itself on the board's acknowledgements: after each frame it sends {"live":1,"ack":n}; firmware 0.4 answers
    {"live_ack":n}; no more than --window frames are ever unacknowledged (older firmware: fixed pace, max 4 frames/s),
  * reconnects with backoff (1, 2, 4, 8 s) and closes sockets WITHOUT the close handshake (a plain TCP close),
  * prints frames/s, ack round trip and reconnects at the end (also the library for tools/pov_soak.py).
The token comes from src/wifi_secrets.h (POV_TOKEN, "" = none) and is never printed.
"""
import argparse, json, os, re, statistics, sys, time

import websocket  # websocket-client

ROWS, COLS = 42, 96
HERE = os.path.dirname(os.path.abspath(__file__))
FW = os.path.dirname(HERE)
HTTP_PORT = int(os.environ.get("POV_HTTP_PORT", "80"))


def token():
    try:
        m = re.search(r'#define\s+POV_TOKEN\s+"([^"]*)"', open(os.path.join(FW, "src", "wifi_secrets.h"), encoding="utf-8").read())
        return m.group(1) if m else ""
    except OSError:
        return ""


PATTERNS = {
    "rowwalk": [[0, 0, 0], [255, 255, 255]],
    "stripes": [[0, 0, 0], [255, 0, 0], [255, 140, 0], [0, 255, 0], [0, 140, 255], [180, 0, 255]],
    "solid": [[0, 0, 0], [255, 255, 255]],
}


def frame(pattern, t):
    fr = bytearray(ROWS * COLS)
    if pattern == "rowwalk":
        r = t % ROWS
        fr[r * COLS:(r + 1) * COLS] = b"\x01" * COLS
    elif pattern == "stripes":
        for r in range(ROWS):
            for c in range(COLS):
                k = (c + r + t) % 80
                if k % 16 < 4:
                    fr[r * COLS + c] = 1 + k // 16
    elif pattern == "solid":
        fr[:] = b"\x01" * (ROWS * COLS)
    return bytes(fr)


class Streamer:
    def __init__(self, host, pal, fps=6.0, window=2, log=print):
        self.host, self.pal, self.fps, self.window, self.log = host, pal, fps, window, log
        port = "" if HTTP_PORT == 80 else f":{HTTP_PORT}"
        tok = token()
        self.url = f"ws://{host}{port}/ws" + (f"?token={tok}" if tok else "")
        self.ws = None
        self.acks = None              # True: firmware answers live_ack; False: old firmware (fixed pace)
        self.seq = 0
        self.outstanding = {}         # ack seq -> send time
        self.rtts = []
        self.sent = 0
        self.reconnects = 0
        self.errors = []
        self.t_last = 0.0
        self.backoff = 1.0
        self.deadline = None          # give up reconnecting after this time (run() sets it to the end of the run)

    # ---------------------------------------------------------------- connection
    def _drop(self):
        """Close WITHOUT a WebSocket close frame (see the docstring): the board takes the plain TCP close path."""
        if self.ws is not None:
            try:
                self.ws.shutdown()
            except Exception:
                pass
        self.ws = None
        self.outstanding.clear()

    def connect(self):
        self.ws = websocket.create_connection(self.url, timeout=5, enable_multithread=False)
        self.ws.send(json.dumps({"live": 1, "pal": self.pal}))
        if self.acks is None:                        # does this firmware answer live acks?
            self.ws.send(json.dumps({"live": 1, "ack": 0}))
            self.acks = self._wait_ack(0, 2.0)
            self.log(f"connected to {self.url.split('?')[0]}: " + ("acks on (paced by the board)" if self.acks else
                                                                  "no acks (firmware < 0.4): fixed pace, max 4 frames/s"))
        self.backoff = 1.0

    def ensure(self):
        """Connect if needed; False once the deadline has passed with the board unreachable."""
        while self.ws is None:
            if self.deadline and time.time() > self.deadline:
                return False
            try:
                self.connect()
            except Exception as e:
                self.errors.append(f"connect: {e}")
                self.log(f"connect failed ({e}); retry in {self.backoff:.0f} s")
                self._drop()
                time.sleep(self.backoff)
                self.backoff = min(8.0, self.backoff * 2)
        return True

    def _wait_ack(self, want, timeout):
        """Read until live_ack `want` (or any later one) arrives; True if it did within timeout."""
        t_end = time.time() + timeout
        while time.time() < t_end:
            self.ws.settimeout(max(0.05, t_end - time.time()))
            try:
                m = self.ws.recv()
            except websocket.WebSocketTimeoutException:
                return False
            if isinstance(m, bytes):
                continue
            try:
                j = json.loads(m)
            except ValueError:
                continue
            if "live_ack" in j:
                n = j["live_ack"]
                for k in [k for k in self.outstanding if k <= n]:
                    self.rtts.append(time.time() - self.outstanding.pop(k))
                if n >= want:
                    return True
        return False

    # ---------------------------------------------------------------- frames
    def send(self, data):
        """Send one frame, paced. Returns False if the link broke (it reconnects on the next call)."""
        if not self.ensure():
            return False
        fps = self.fps if self.acks else min(self.fps, 4.0)
        wait = self.t_last + 1.0 / fps - time.time()
        if wait > 0:
            time.sleep(wait)
        try:
            self.ws.send_binary(data)
            self.t_last = time.time()
            self.sent += 1
            if self.acks:
                self.seq += 1
                self.outstanding[self.seq] = time.time()
                self.ws.send(json.dumps({"live": 1, "ack": self.seq}))
                if len(self.outstanding) > self.window:          # too far ahead: wait for the oldest to be shown
                    oldest = min(self.outstanding)
                    if not self._wait_ack(oldest, 5.0):
                        raise TimeoutError(f"no ack for frame {oldest} in 5 s (link stalled)")
            elif self.sent % 20 == 0:                            # old firmware pushes status text: read it away
                self._wait_ack(1 << 30, 0.01)
            return True
        except Exception as e:
            self.errors.append(f"send: {e}")
            self.reconnects += 1
            self.log(f"link broke ({type(e).__name__}: {e}); reconnecting (abrupt close, backoff {self.backoff:.0f} s)")
            self._drop()
            time.sleep(self.backoff)
            self.backoff = min(8.0, self.backoff * 2)
            return False

    def close(self):
        self._drop()

    def stats(self, secs):
        r = sorted(self.rtts)
        return {"frames": self.sent, "secs": round(secs, 1), "fps": round(self.sent / secs, 2) if secs else 0,
                "kb_s": round(self.sent * ROWS * COLS / 1024 / secs, 1) if secs else 0, "acks": self.acks,
                "ack_med_ms": round(1000 * statistics.median(r)) if r else None,
                "ack_p95_ms": round(1000 * r[int(len(r) * 0.95) - 1]) if len(r) >= 20 else None,
                "ack_max_ms": round(1000 * r[-1]) if r else None, "reconnects": self.reconnects,
                "errors": self.errors[-5:]}


def run(host, pattern, minutes, fps, window=2, log=print, stop=None):
    s = Streamer(host, PATTERNS[pattern], fps=fps, window=window, log=log)
    t0, t = time.time(), 0
    s.deadline = t0 + minutes * 60
    try:
        while time.time() - t0 < minutes * 60 and not (stop and stop.is_set()):
            if s.send(frame(pattern, t)):
                t += 1
    except KeyboardInterrupt:
        pass
    finally:
        s.close()
    return s.stats(time.time() - t0)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("pattern", choices=sorted(PATTERNS))
    ap.add_argument("--host", default=os.environ.get("POV_HOST", "pov.local"))
    ap.add_argument("--minutes", type=float, default=5)
    ap.add_argument("--fps", type=float, default=6.0, help="upper limit; acks slow it further on a weak link")
    ap.add_argument("--window", type=int, default=2, help="frames allowed in flight without an ack")
    a = ap.parse_args()
    st = run(a.host, a.pattern, a.minutes, a.fps, a.window, log=lambda m: print(m, flush=True))
    print(json.dumps(st))
    return 0 if st["frames"] else 1


if __name__ == "__main__":
    sys.exit(main())
