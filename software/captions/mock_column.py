"""A stand-in for the rotor's ESP32 on the caption WebSocket, to exercise the transport without hardware.

    py software/captions/mock_column.py                    # ws://localhost:8765/ws
    py software/captions/live.py --mode word --to ws://localhost:8765/ws --file <clip.wav> --no-preview

It speaks the firmware's protocol: {"cap":...} messages go into a ColumnCaptions model (the reference the firmware is
ported from) ticked at 30 Hz; after the tick that shows a message it replies {"ack":id,"swap_us":...}, like the
firmware does after its buffer swap. {"live":...} + binary 4,032-byte frames are accepted as in live mode. The
round trip it measures is PC -> socket -> parse -> wait for the next tick -> ack: the same terms as the real column
minus Wi-Fi. Prints a summary on Ctrl+C.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from column_model import TICK_HZ, ColumnCaptions  # noqa: E402


async def serve(host: str, port: int):
    import websockets
    model = ColumnCaptions()
    stats = dict(msgs=0, frames=0, bytes=0)
    clients = set()
    pending_acks: list[int] = []

    async def handler(ws):
        clients.add(ws)
        try:
            async for raw in ws:
                stats["bytes"] += len(raw)
                if isinstance(raw, bytes):
                    stats["frames"] += 1
                    continue
                m = json.loads(raw)
                if "ping" in m:                      # network-only round trip (no tick wait)
                    await ws.send(json.dumps({"pong": m["ping"]}))
                elif "cap" in m:
                    stats["msgs"] += 1
                    model.receive(m)
                    if m.get("id") and not m.get("dim"):
                        pending_acks.append(m["id"])
        finally:
            clients.discard(ws)

    async def ticker():
        t0, k = time.perf_counter(), 0
        while True:
            k += 1
            await asyncio.sleep(max(0.0, t0 + k / TICK_HZ - time.perf_counter()))
            acks = list(pending_acks)
            pending_acks.clear()
            model.tick(k / TICK_HZ)
            for a in acks:
                msg = json.dumps({"ack": a, "swap_us": int(1e6 * (time.perf_counter() - t0))})
                for c in list(clients):
                    try:
                        await c.send(msg)
                    except Exception:
                        pass

    async with websockets.serve(handler, host, port, compression=None):
        print(f"mock column on ws://{host}:{port}/ws", flush=True)
        try:
            await ticker()
        finally:
            print("mock column:", stats, "words shown:", sum(1 for e in model.log if e["ev"] in ("word", "append")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    try:
        asyncio.run(serve(a.host, a.port))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
