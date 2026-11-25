"""Getting captions to the rotor's ESP32 with as little delay as possible.

Primary path (CaptionWS): small JSON caption messages over the column's existing WebSocket (`ws://pov.local/ws`),
e.g. {"cap":"word","w":"HELLO","id":17,"t":12.345}. 30-60 bytes per word instead of 4,032-byte frames; the ESP32
draws them with its built-in fonts in a procedural mode (firmware/src/captions.h) and swaps at the next refresh tick.
The firmware echoes {"ack":id,"tick_us":...} after the swap, so the PC can log the real transport + swap delay once
the hardware exists (rtt/2 is the one-way estimate).
TCP_NODELAY is set (Nagle would hold a 40-byte message for up to ~200 ms waiting for the ACK of the previous one).

Fallback (FrameStreamWS): the PC runs the same column model (column_model.py) at 30 Hz and streams the rendered
4,032-byte palette-index frames over the existing live mode (binary WebSocket messages; the palette is sent once as
{"live":"palette","pal":[[r,g,b],...]}). ~121 KB/s; use it if the caption mode misbehaves on the ESP32.

Local (LocalColumn): delivers messages straight into an in-process ColumnCaptions (the simulator preview), with an
optional artificial delay standing in for Wi-Fi.
"""
from __future__ import annotations

import json
import queue
import socket
import threading
import time

import numpy as np

from column_model import TICK_HZ, ColumnCaptions


class Transport:
    name = "null"

    def send(self, msg: dict) -> None:
        pass

    def close(self) -> None:
        pass

    def stats(self) -> dict:
        return {}


class LocalColumn(Transport):
    """In-process column model (used by the preview); `delay` simulates Wi-Fi + parsing (s)."""
    name = "sim"

    def __init__(self, model: ColumnCaptions, delay: float = 0.010):
        self.model, self.delay, self.q = model, delay, []
        self.lock = threading.Lock()

    def send(self, msg: dict) -> None:
        with self.lock:
            self.q.append((time.perf_counter() + self.delay, msg))

    def deliver(self, now: float | None = None) -> None:
        now = time.perf_counter() if now is None else now
        with self.lock:
            due = [m for t, m in self.q if t <= now]
            self.q = [(t, m) for t, m in self.q if t > now]
        for m in due:
            self.model.receive(m)


class _WSBase(Transport):
    def __init__(self, url: str, token: str = "", keepalive: float = 0.25):
        self.url, self.token, self.keepalive = url, token, keepalive
        self.q: queue.Queue = queue.Queue()
        self.sent: dict[int, float] = {}
        self.rtts: list[float] = []
        self.err = None
        self.alive = True
        self.th = threading.Thread(target=self._run, daemon=True)
        self.th.start()

    def _connect(self):
        from websockets.sync.client import connect
        hdr = {"X-POV-Token": self.token} if self.token else None
        ws = connect(self.url, additional_headers=hdr, open_timeout=5, max_size=None, compression=None)
        try:
            ws.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass
        return ws

    def _reader(self, ws):
        try:
            for raw in ws:
                if isinstance(raw, str):
                    try:
                        m = json.loads(raw)
                    except ValueError:
                        continue
                    if "ack" in m and m["ack"] in self.sent:
                        self.rtts.append(time.perf_counter() - self.sent.pop(m["ack"]))
        except Exception:
            pass

    def _run(self):
        while self.alive:
            try:
                ws = self._connect()
                threading.Thread(target=self._reader, args=(ws,), daemon=True).start()
                self.err = None
                k = 0
                while self.alive:
                    try:
                        item = self.q.get(timeout=self.keepalive) if self.keepalive else self.q.get()
                    except queue.Empty:
                        # keep both radios awake between words: Wi-Fi power save on the far end added up to
                        # ~0.5 s to the first message after a pause (measured to a Pi with power_save on)
                        k += 1
                        ws.send('{"ping":%d}' % k)
                        continue
                    if item is None:
                        break
                    if isinstance(item, (bytes, bytearray)):
                        ws.send(item)
                    else:
                        if "id" in item:
                            self.sent[item["id"]] = time.perf_counter()
                        ws.send(json.dumps(item, separators=(",", ":")))
                ws.close()
            except Exception as e:      # column off / rebooting: keep trying, drop what queued up meanwhile
                self.err = str(e)
                while not self.q.empty():
                    self.q.get_nowait()
                time.sleep(1.0)

    def close(self):
        self.alive = False
        self.q.put(None)

    def stats(self):
        r = np.array(self.rtts) if self.rtts else None
        return dict(acks=len(self.rtts), rtt_med_ms=round(1000 * float(np.median(r)), 1) if r is not None else None,
                    rtt_p90_ms=round(1000 * float(np.percentile(r, 90)), 1) if r is not None else None, err=self.err)


class CaptionWS(_WSBase):
    name = "ws"

    def send(self, msg: dict) -> None:
        self.q.put(msg)


class FrameStreamWS(_WSBase):
    """PC-rendered fallback: run the column model here at 30 Hz, stream index frames over the live mode."""
    name = "frames"

    def __init__(self, url: str, token: str = "", model: ColumnCaptions | None = None):
        super().__init__(url, token)
        self.model = model or ColumnCaptions()
        self.q.put({"live": "start"})
        self.q.put({"live": "palette", "pal": self.model.cfg.palette().tolist()})
        self.t0 = time.perf_counter()
        self.ticker = threading.Thread(target=self._tick_loop, daemon=True)
        self.ticker.start()

    def send(self, msg: dict) -> None:
        self.model.receive(msg)

    def _tick_loop(self):
        k = 0
        while self.alive:
            t_next = self.t0 + k / TICK_HZ
            time.sleep(max(0.0, t_next - time.perf_counter()))
            fr = self.model.tick(k / TICK_HZ)
            if self.q.qsize() < 3:            # never queue stale frames behind a slow link
                self.q.put(fr.astype(np.uint8).tobytes())
            k += 1


def make(spec: str, model: ColumnCaptions | None = None, token: str = "") -> Transport:
    """'sim' | 'null' | 'ws://pov.local/ws' (caption messages) | 'frames:ws://pov.local/ws' (PC-rendered frames)."""
    if spec == "null":
        return Transport()
    if spec == "sim":
        return LocalColumn(model or ColumnCaptions())
    if spec.startswith("frames:"):
        return FrameStreamWS(spec[len("frames:"):], token, model)
    if spec.startswith("ws://") or spec.startswith("wss://"):
        return CaptionWS(spec, token)
    raise ValueError(spec)
