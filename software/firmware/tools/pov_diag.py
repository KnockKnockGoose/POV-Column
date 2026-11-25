"""Diagonal stripes scrolling on the POV column via live mode (WebSocket /ws). Usage: py tools/pov_diag.py [--minutes 30]
Stripes 4 px wide every 16 px along (column + row), colours cycling, shifted one step per frame at ~15 fps."""
import argparse, json, re, time
from pathlib import Path
import websocket

ROWS, COLS = 42, 96
HERE = Path(__file__).resolve().parent.parent
tok = re.search(r'#define\s+POV_TOKEN\s+"([^"]*)"', (HERE / "src" / "wifi_secrets.h").read_text()).group(1)
ap = argparse.ArgumentParser(); ap.add_argument("--host", default="pov.local"); ap.add_argument("--minutes", type=float, default=30)
a = ap.parse_args()
pal = [[0, 0, 0], [255, 0, 0], [255, 140, 0], [0, 255, 0], [0, 140, 255], [180, 0, 255]]
PERIOD, WIDTH = 16, 4
ws = websocket.create_connection(f"ws://{a.host}/ws?token={tok}", timeout=5)
ws.send(json.dumps({"live": 1, "pal": pal}))
t, end = 0, time.time() + a.minutes * 60
while time.time() < end:
    fr = bytearray(ROWS * COLS)
    for r in range(ROWS):
        for c in range(COLS):
            k = (c + r + t) % (PERIOD * 5)
            if k % PERIOD < WIDTH:
                fr[r * COLS + c] = 1 + k // PERIOD
    ws.send_binary(bytes(fr)); t += 1; time.sleep(1 / 15)
ws.close()
