"""mock_column.py - a stand-in for the POV column while it is off (battery charging), for rehearsing the live demo and
for measuring prompt -> playing without the board (2026-11-23, live-demo pipeline).

It is the firmware team's tools/mock_board.py (the 0.4 API: /api/status, /api/anims, /api/play queued, /api/stop, the
64 KiB and name checks) plus the delays the real board adds, so the step view and the timings look like the real thing:

  upload   0.30 s + 1 s per 50 kB   (11-22 pipeline log: 2.7 KB -> 0.4 s, 20-22 KB -> 0.8 s for upload + play)
  load     0.25 s + 2 ms per frame  (firmware do_load: read the file, decode every frame for the current cap, ~2 ms each)

    py software/pipeline/mock_column.py                 # http://127.0.0.1:18080
    py software/pipeline/pov_serve.py --shoot --target http://127.0.0.1:18080

Numbers measured against it are labelled "mock column" in the reports: real Wi-Fi and flash timings come from the
board itself (GET /api/status "load".ms).
"""
from __future__ import annotations

import argparse
import struct
import sys
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent / "firmware" / "tools"
sys.path.insert(0, str(TOOLS))
import mock_board  # noqa: E402

UPLOAD_BASE_S, UPLOAD_PER_BYTE_S = 0.30, 1 / 50_000
LOAD_BASE_S, LOAD_PER_FRAME_S = 0.25, 0.002


def frames_of(data: bytes) -> int:
    try:
        return struct.unpack("<H", data[8:10])[0] if data[:4] == b"POVA" else 0
    except struct.error:
        return 0


class SlowHandler(mock_board.Handler):
    def do_POST(self):
        if self.path.split("?")[0] == "/api/anims":
            n = int(self.headers.get("Content-Length", 0) or 0)
            time.sleep(UPLOAD_BASE_S + n * UPLOAD_PER_BYTE_S)     # Wi-Fi transfer + LittleFS writes + read-back check
        return super().do_POST()


def slow_finish_load(self, name):
    data = self.anims.get(name, b"")
    self.a.load_ms = int(1000 * (LOAD_BASE_S + LOAD_PER_FRAME_S * frames_of(data)))
    return _orig_finish_load(self, name)


_orig_finish_load = mock_board.Board.finish_load
mock_board.Board.finish_load = slow_finish_load


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--port", type=int, default=18080)
    ap.add_argument("--fast", action="store_true", help="no added delays (plain mock_board timings)")
    a = ap.parse_args(argv)
    if a.fast:
        global UPLOAD_BASE_S, UPLOAD_PER_BYTE_S, LOAD_BASE_S, LOAD_PER_FRAME_S
        UPLOAD_BASE_S = UPLOAD_PER_BYTE_S = LOAD_BASE_S = LOAD_PER_FRAME_S = 0.0
    sys.argv = [sys.argv[0], "--http-port", str(a.port), "--no-arduino-ota", "--fw", "0.4", "--sim", "225",
                "--mode", "off", "--anims", ""]
    mock_board.Handler = SlowHandler                               # main() builds its server from mock_board.Handler
    return mock_board.main()


if __name__ == "__main__":
    sys.exit(main())
