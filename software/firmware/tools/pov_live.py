"""Stream a still image to the POV column's live mode (WebSocket /ws). Usage: py tools/pov_live.py usa|canada [--host IP]
Frame: 42 rows x 96 columns of palette indices, row 0 = bottom. The token is read from src/wifi_secrets.h, never printed."""
import argparse, json, re, time
from pathlib import Path
import websocket  # websocket-client

ROWS, COLS = 42, 96
HERE = Path(__file__).resolve().parent.parent

def token():
    m = re.search(r'#define\s+POV_TOKEN\s+"([^"]*)"', (HERE / "src" / "wifi_secrets.h").read_text())
    return m.group(1) if m else ""

def usa():
    pal = [[0, 0, 0], [255, 0, 0], [255, 255, 255], [0, 0, 255]]
    fr = bytearray(ROWS * COLS)
    for half in (0, 48):                       # two flags around the circumference
        for r in range(ROWS):
            top = ROWS - 1 - r                 # 0 = top row
            for c in range(48):
                stripe = 1 if (top // 3) % 2 == 0 else 2
                v = stripe
                if top < 21 and c < 19:        # canton
                    v = 2 if (top % 4 == 1 and c % 4 == 1) or (top % 4 == 3 and c % 4 == 3) else 3
                fr[r * COLS + half + c] = v
    return pal, fr

def canada():
    pal = [[0, 0, 0], [255, 0, 0], [255, 255, 255]]
    fr = bytearray(ROWS * COLS)
    for half in (0, 48):
        for r in range(ROWS):
            for c in range(48):
                v = 1 if c < 12 or c >= 36 else 2
                dx, dy = abs(c - 23.5), abs(r - 21)
                if 12 <= c < 36 and dx + dy * 0.8 < 10 and not (dy > 6 and dx > 3):
                    v = 1                      # simple red leaf-ish diamond with a stem gap
                if 12 <= c < 36 and r < 12 and dx < 1.5 and r > 5:
                    v = 1                      # stem
                fr[r * COLS + half + c] = v
    return pal, fr

ap = argparse.ArgumentParser()
ap.add_argument("image", choices=["usa", "canada"])
ap.add_argument("--host", default="pov.local")
a = ap.parse_args()
pal, fr = {"usa": usa, "canada": canada}[a.image]()
ws = websocket.create_connection(f"ws://{a.host}/ws?token={token()}", timeout=5)
ws.send(json.dumps({"live": 1, "pal": pal}))
for _ in range(3):
    ws.send_binary(bytes(fr)); time.sleep(0.2)
ws.close()
print(f"sent {a.image} ({len(fr)} px, {len(pal)} colours) to {a.host}")
