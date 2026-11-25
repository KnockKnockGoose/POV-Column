"""Measure the caption link to a column (or mock_column.py) without speech: network round trip and message -> ack.

    py software/captions/probe_link.py ws://pov.local/ws --seconds 60
    py software/captions/probe_link.py ws://<pi-ip>:8765/ws          # mock column on another Wi-Fi machine

Sends one {"ping":n} and one caption word every 1/3 s (a fast talker). ping -> pong is the pure WebSocket round trip;
word -> ack adds the wait for the next refresh tick (0-33 ms) and the render. One-way link ~ ping RTT / 2.
"""
from __future__ import annotations

import argparse
import json
import socket
import threading
import time

import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--seconds", type=float, default=60)
    ap.add_argument("--token", default="")
    a = ap.parse_args()
    from websockets.sync.client import connect
    ws = connect(a.url, additional_headers={"X-POV-Token": a.token} if a.token else None, compression=None)
    ws.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    sent_p, sent_w, rtt_p, rtt_w = {}, {}, [], []

    def reader():
        try:
            for raw in ws:
                m = json.loads(raw)
                now = time.perf_counter()
                if "pong" in m and m["pong"] in sent_p:
                    rtt_p.append(now - sent_p.pop(m["pong"]))
                if "ack" in m and m["ack"] in sent_w:
                    rtt_w.append(now - sent_w.pop(m["ack"]))
        except Exception:
            pass
    threading.Thread(target=reader, daemon=True).start()
    ws.send(json.dumps({"cap": "mode", "m": "word"}))
    t0, n = time.perf_counter(), 0
    words = "CAPTIONS ON THE COLUMN WHILE I TALK".split()
    while time.perf_counter() - t0 < a.seconds:
        n += 1
        sent_p[n] = time.perf_counter()
        ws.send(json.dumps({"ping": n}))
        time.sleep(0.05)
        sent_w[n] = time.perf_counter()
        ws.send(json.dumps({"cap": "word", "w": words[n % len(words)], "id": n}, separators=(",", ":")))
        time.sleep(1 / 3 - 0.05)
    time.sleep(0.5)
    ws.close()
    for name, r in (("ping RTT (network)", rtt_p), ("word -> ack (network + tick wait)", rtt_w)):
        r = 1000 * np.array(r)
        print(f"{name}: n={len(r)}  median {np.median(r):.1f} ms  p90 {np.percentile(r, 90):.1f}  max {r.max():.1f}")
    print(json.dumps(dict(url=a.url, n=len(rtt_p), ping_med_ms=round(1000 * float(np.median(rtt_p)), 1),
                          ping_p90_ms=round(1000 * float(np.percentile(rtt_p, 90)), 1),
                          ack_med_ms=round(1000 * float(np.median(rtt_w)), 1),
                          ack_p90_ms=round(1000 * float(np.percentile(rtt_w, 90)), 1))))


if __name__ == "__main__":
    main()
