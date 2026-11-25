#!/usr/bin/env python3
r"""mock_board.py - a stand-in for the column's image firmware on the PC (Wi-Fi control review 2026-11-14), so the
host tools can be tested end to end without the board: tools/ota_flash.py, tools/pov_ctl.py, tools/pov_stream.py,
tools/pov_soak.py (tests: tools/mock_board_test.py).

It serves the firmware's HTTP API on 127.0.0.1:--http-port (status, anims, play, stop, settings, ota-prep, resume,
reboot, crash, /update), the WebSocket /ws on the same port (live mode: binary 4,032-byte frames, {"live":..,"ack":n}
-> {"live_ack":n}) and, unless --no-arduino-ota, the ArduinoOTA receiver of tools/ota_sim.py on udp 127.0.0.1:3232.
A completed update "reboots" the mock into the image's build id (read from the uploaded firmware.bin like the board's
esp_app_desc_t), with the boot behaviour of the chosen firmware: --fw 0.4 (this review: saved simulator rpm starts at
boot, /api/ota-prep, /api/reboot, /api/crash, play is queued) or --fw 0.2 (the build on the board on 2026-11-14: none
of those, play is synchronous, sim_rpm is lost at reboot).

  py tools\mock_board.py --http-port 18080 --password simtest --mode anim --anim dog_ball_front --sim 150
Test hooks: GET /mock/events (what happened, in order), POST /mock/panic (reboot with reset_reason 4 and a crash
record), POST /mock/drop_ws (cut every WebSocket without a close frame).
"""
import argparse, base64, hashlib, json, os, re, socket, struct, sys, threading, time, zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ota_sim  # noqa: E402

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def elf_of_image(img):
    """The 16-hex build id of an app image (esp_app_desc_t.app_elf_sha256[0:8]), as ota_flash.app_desc reads it."""
    if not img or len(img) < 200 or img[0] != 0xE9:
        return None
    return img[32 + 144:32 + 152].hex()


def live_rle_ok(d):
    """Python mirror of pova.h pov_live_rle_decode (firmware 0.4.1): 'R' + (run, index) pairs filling 4,032 pixels."""
    if len(d) < 3 or not len(d) & 1 or len(d) > 2049 or d[0] != ord("R"):
        return False
    return sum(d[1::2]) == 4032


def pova_ok(b):
    """Python mirror of the firmware's upload check (pova_check_*: size, magic, header, CRC)."""
    if len(b) > 65536:
        return "too big (max 65536 B)"
    if len(b) < 24 or b[:4] != b"POVA":
        return "not a .pova file (magic)"
    if zlib.crc32(b[:-4]) & 0xFFFFFFFF != struct.unpack("<I", b[-4:])[0]:
        return "CRC mismatch (file damaged in transfer)"
    return None


class Board:
    def __init__(self, a):
        self.a = a
        self.lock = threading.RLock()
        self.events = []
        self.t0 = time.time()
        self.elf = a.elf
        self.fw = "0.4-2026-11-14" if a.fw == "0.4" else "0.2-2026-11-03"
        self.boot_count, self.reset_reason = 1, 3
        self.mode, self.anim, self.last = a.mode, a.anim if a.mode == "anim" else "", a.anim
        self.sim_rpm, self.sim_saved = a.sim, (a.sim if a.sim_saved else 0)
        self.gb, self.autoplay, self.paused, self.pause_until = 12, False, False, 0
        self.load = {"state": "ok" if self.anim else "idle", "name": self.anim, "err": "", "ms": 0, "ok": 0, "failed": 0}
        self.anims = {n: b"POVA" for n in a.anims.split(",") if n}
        self.ota_state, self.confirm_at = "valid", 0
        self.down_until = 0.0
        self.crash = None
        self.n_crashes = 0
        self.live_frames = self.live_bad = 0
        self.ws_socks = []
        self.ws_close_frames = 0

    def ev(self, what, **kw):
        with self.lock:
            self.events.append(dict(t=round(time.time() - self.t0, 3), what=what, **kw))

    def up(self):
        return time.time() >= self.down_until

    def uptime(self):
        return int(time.time() - self.t0)

    def reboot(self, reason=3, new_elf=None, delay=2.0):
        with self.lock:
            for s in list(self.ws_socks):
                try:
                    s.close()
                except OSError:
                    pass
            self.ws_socks.clear()
            self.down_until = time.time() + delay
            self.t0 = time.time() + delay
            self.boot_count += 1
            self.reset_reason = reason
            if new_elf and new_elf != self.elf:
                self.elf = new_elf
                self.ota_state, self.confirm_at = "pending", time.time() + delay + self.a.confirm_s
            self.paused, self.mode, self.anim = False, "off", ""
            self.sim_rpm = self.sim_saved if self.a.fw == "0.4" else 0
            self.load = dict(self.load, state="idle", name="", err="")
            if self.autoplay and self.last:
                self.mode, self.anim = "anim", self.last
            self.ev("reboot", reason=reason, elf=self.elf)

    def status(self):
        with self.lock:
            if self.ota_state == "pending" and time.time() >= self.confirm_at:
                self.ota_state = "valid"
            if self.paused and self.pause_until and time.time() > self.pause_until:
                self.resume("timeout")
            running = bool(self.sim_rpm) and self.mode != "off" and not self.paused
            st = {"fw": self.fw, "elf": self.elf, "ota": self.ota_state, "ota_active": False, "mode": self.mode,
                  "rpm": float(self.sim_rpm), "valid": bool(self.sim_rpm), "running": running, "gb": self.gb,
                  "anim": self.anim, "frames": 24 if self.anim else 0, "heap": 90000, "heap_min": 47000,
                  "sim_rpm": self.sim_rpm, "boot_count": self.boot_count, "reset_reason": self.reset_reason,
                  "ip": "127.0.0.1", "rssi": -61, "uptime_s": self.uptime(), "autoplay": self.autoplay}
            if self.a.fw == "0.4":
                st.update({"sim_saved": self.sim_saved, "paused": self.paused, "last": self.last,
                           "heap_max_block": 60000, "load": dict(self.load),
                           "wifi": {"tx_dbm": 13.0, "disconnects": 0, "ws_clients": len(self.ws_socks)},
                           "diag": {"lag0_ms": 0.1, "lag1_ms": 0.2, "col_busy_pct": 5.0, "live_frames": self.live_frames,
                                    "live_bad": self.live_bad, "test_dark": False, "test_nospi": False,
                                    **({"live_rle": True} if self.a.live_rle else {})},
                           "crash": {"count": self.n_crashes, **({"reason": self.crash["reason"]} if self.crash else {})}})
            return st

    def resume(self, why):
        if self.paused:
            self.paused = False
            self.sim_rpm = self.sim_before
            self.ev("resume", why=why)

    def finish_load(self, name):
        time.sleep(self.a.load_ms / 1000)
        with self.lock:
            if self.load.get("name") != name or self.load["state"] != "queued":
                return
            self.mode, self.anim, self.last = "anim", name, name
            self.load.update(state="ok", ms=self.a.load_ms, ok=self.load["ok"] + 1)
            self.ev("playing", name=name)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    board: Board = None

    def log_message(self, *args):
        pass

    # ---------------------------------------------------------------- helpers
    def send(self, code, body="", ctype="application/json"):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def authed(self):
        tok = self.board.a.token
        if not tok:
            return True
        q = parse_qs(urlparse(self.path).query)
        return self.headers.get("X-POV-Token") == tok or q.get("token", [""])[0] == tok

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def drop(self):                                  # a rebooting board: the connection just dies
        self.close_connection = True
        try:
            self.connection.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

    def multipart_file(self, raw):
        """(filename, bytes) of the first file part of a multipart/form-data body (Python 3.13 removed cgi)."""
        m = re.search(r'boundary="?([^";]+)"?', self.headers.get("Content-Type", ""))
        if not m:
            return None, None
        sep = b"--" + m.group(1).encode()
        for part in raw.split(sep):
            head, _, data = part.partition(b"\r\n\r\n")
            fn = re.search(rb'filename="([^"]*)"', head)
            if fn and data.endswith(b"\r\n"):
                return fn.group(1).decode(errors="replace"), data[:-2]
        return None, None

    # ---------------------------------------------------------------- GET / DELETE
    def do_GET(self):
        b = self.board
        u = urlparse(self.path)
        if u.path == "/mock/events":
            return self.send(200, json.dumps(b.events))
        if not b.up():
            return self.drop()
        if u.path == "/ws" and self.headers.get("Upgrade", "").lower() == "websocket":
            return self.websocket()
        if u.path == "/api/status":
            return self.send(200, json.dumps(b.status()))
        if u.path == "/api/anims":
            return self.send(200, json.dumps([{"name": n, "bytes": len(v)} for n, v in b.anims.items()]))
        if u.path == "/api/crash" and b.a.fw == "0.4":
            d = {"count": b.n_crashes, "have": bool(b.crash), "running_elf": b.elf, "boot_count": b.boot_count}
            if b.crash:
                d.update(b.crash)
            return self.send(200, json.dumps(d))
        self.send(404, "not found", "text/plain")

    def do_DELETE(self):
        b = self.board
        if not b.up():
            return self.drop()
        u = urlparse(self.path)
        if not self.authed():
            return self.send(401)
        if u.path == "/api/crash" and b.a.fw == "0.4":
            b.crash, b.n_crashes = None, 0
            return self.send(200, '{"ok":true}')
        if u.path == "/api/anims":
            n = parse_qs(u.query).get("name", [""])[0]
            return self.send(200 if b.anims.pop(n, None) is not None else 404)
        self.send(404, "not found", "text/plain")

    # ---------------------------------------------------------------- POST
    def do_POST(self):
        b = self.board
        u = urlparse(self.path)
        raw = self.body()
        if u.path == "/mock/panic":
            b.crash = {"reset": "panic", "reset_reason": 4, "reason": "LoadProhibited", "msg": "", "task": "async_tcp",
                       "core": 0, "pc": "0x400d1234", "bt": ["0x400d1234", "0x400d5678"], "bt_corrupt": False,
                       "uptime_ms": b.uptime() * 1000, "heap": 52000, "boot": b.boot_count + 1, "elf": b.elf,
                       "op": "ws binary frame", "op_age_ms": 3}
            b.n_crashes += 1
            self.send(200, '{"ok":true}')
            b.reboot(reason=4)
            return
        if u.path == "/mock/drop_ws":
            with b.lock:
                for s in list(b.ws_socks):
                    try:
                        s.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
            b.ev("drop_ws")
            return self.send(200, '{"ok":true}')
        if not b.up():
            return self.drop()
        if not self.authed():
            return self.send(401)
        try:
            j = json.loads(raw or b"{}") if raw[:1] in (b"{", b"[") else {}
        except ValueError:
            j = {}
        q = parse_qs(u.query)
        new04 = b.a.fw == "0.4"
        if u.path == "/api/play":
            name = j.get("name", "")
            b.ev("play", name=name)
            if name not in b.anims:
                return self.send(404, '{"error":"not found"}')
            with b.lock:
                if new04:
                    b.paused = False
                    b.load.update(state="queued", name=name, err="")
                    threading.Thread(target=b.finish_load, args=(name,), daemon=True).start()
                    return self.send(200, json.dumps({"ok": True, "queued": name}))
                b.mode, b.anim, b.last = "anim", name, name
            return self.send(200, '{"ok":true}')
        if u.path == "/api/stop":
            with b.lock:
                b.mode = "off"
            b.ev("stop")
            return self.send(200)
        if u.path == "/api/settings":
            with b.lock:
                if "sim_rpm" in j:
                    rpm = max(0, min(1200, int(j["sim_rpm"])))
                    if b.paused:
                        b.sim_before = rpm
                    else:
                        b.sim_rpm = rpm
                    if new04 and "sim_persist" in j:
                        b.sim_saved = rpm if j["sim_persist"] else 0
                    b.ev("settings", sim_rpm=rpm, persist=j.get("sim_persist"))
                if "gb" in j:
                    b.gb = int(j["gb"])
                if "autoplay" in j:
                    b.autoplay = bool(j["autoplay"])
            return self.send(200, json.dumps(b.status()))
        if new04 and u.path == "/api/ota-prep":
            secs = int(q.get("secs", ["180"])[0])
            with b.lock:
                if not b.paused:
                    b.sim_before = b.sim_rpm
                b.paused, b.sim_rpm = True, 0
                b.pause_until = time.time() + secs if secs else 0
                for s in list(b.ws_socks):
                    try:
                        s.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
            b.ev("ota-prep", secs=secs)
            return self.send(200, json.dumps({"ok": True, "paused_s": secs, "rssi": -61}))
        if new04 and u.path == "/api/resume":
            with b.lock:
                b.resume("api")
            return self.send(200, '{"ok":true}')
        if new04 and u.path == "/api/reboot":
            if b.ota_state == "pending" and q.get("force", ["0"])[0] != "1":
                b.ev("reboot-refused")
                return self.send(409, '{"error":"new OTA image not confirmed yet"}')
            self.send(200, '{"ok":true,"rebooting":true}')
            b.reboot(reason=3)
            return
        if u.path == "/api/anims":
            name, data = self.multipart_file(raw)
            if not name:
                return self.send(400, '{"error":"no file"}')
            base = os.path.basename(name)
            base = base[:-5] if base.endswith(".pova") else base
            why = pova_ok(data) if new04 else (None if len(data) <= 65536 else "bad file")
            b.ev("upload", name=base, bytes=len(data), ok=why is None)
            if why:
                return self.send(413 if "too big" in why else 400, json.dumps({"error": f"bad file: {why}"}))
            b.anims[base] = data
            return self.send(200, json.dumps({"ok": True, "name": base, "bytes": len(data)}))
        if u.path == "/update":
            name, data = self.multipart_file(raw)
            elf = elf_of_image(data)
            b.ev("http-update", bytes=len(data or b""), elf=elf)
            if not elf:
                return self.send(500, "update failed: not an app image", "text/plain")
            self.send(200, "OK, rebooting", "text/plain")
            b.reboot(reason=3, new_elf=elf)
            return
        self.send(404, "not found", "text/plain")

    # ---------------------------------------------------------------- WebSocket (RFC 6455, server side, minimal)
    def websocket(self):
        b = self.board
        if not self.authed():
            return self.send(401)
        key = self.headers.get("Sec-WebSocket-Key", "")
        acc = base64.b64encode(hashlib.sha1((key + WS_GUID).encode()).digest()).decode()
        self.send_response(101)
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", acc)
        self.end_headers()
        sock = self.connection
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)   # as the board (setNoDelay on WS connect)
        with b.lock:
            b.ws_socks.append(sock)
        b.ev("ws-open")
        rf = self.rfile
        try:
            while True:
                h = rf.read(2)
                if len(h) < 2:
                    b.ev("ws-drop")                      # the peer went away without a close frame
                    break
                op, n = h[0] & 0x0F, h[1] & 0x7F
                if n == 126:
                    n = struct.unpack(">H", rf.read(2))[0]
                elif n == 127:
                    n = struct.unpack(">Q", rf.read(8))[0]
                mask = rf.read(4) if h[1] & 0x80 else b"\0\0\0\0"
                data = bytearray(rf.read(n))
                for i in range(len(data)):
                    data[i] ^= mask[i % 4]
                if op == 0x8:                            # close frame: answer it (as the board does) and stop
                    b.ws_close_frames += 1
                    b.ev("ws-close-frame")
                    sock.sendall(b"\x88\x00")
                    break
                if op == 0x9:
                    sock.sendall(bytes([0x8A, len(data)]) + bytes(data))
                    continue
                if op == 0x2:
                    if b.mode == "live" and not b.paused:
                        if len(data) == 4032 or (b.a.live_rle and live_rle_ok(data)):
                            b.live_frames += 1
                        else:
                            b.live_bad += 1
                    continue
                if op == 0x1:
                    try:
                        m = json.loads(data.decode())
                    except ValueError:
                        continue
                    if "live" in m:
                        with b.lock:
                            b.mode = "live"
                            b.load["state"] = "idle" if b.load["state"] == "queued" else b.load["state"]
                        if "ack" in m:
                            out = json.dumps({"live_ack": m["ack"], "frames": b.live_frames}).encode()
                            sock.sendall(bytes([0x81, len(out)]) + out)
        except OSError:
            b.ev("ws-drop")
        finally:
            with b.lock:
                if sock in b.ws_socks:
                    b.ws_socks.remove(sock)
            self.close_connection = True


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--http-port", type=int, default=18080)
    ap.add_argument("--fw", choices=["0.4", "0.2"], default="0.4")
    ap.add_argument("--token", default="")
    ap.add_argument("--password", default="simtest", help="ArduinoOTA password")
    ap.add_argument("--no-arduino-ota", action="store_true", help="no UDP 3232 receiver (forces the /update fallback)")
    ap.add_argument("--elf", default="c0034fba81ef88d3", help="build id the mock starts with")
    ap.add_argument("--mode", default="off")
    ap.add_argument("--anim", default="")
    ap.add_argument("--anims", default="dog_ball_front,goose_ball_orbit,bichon_shades_front,bichon_shades_orbit")
    ap.add_argument("--sim", type=int, default=0)
    ap.add_argument("--live-rle", action="store_true", help="firmware 0.4.1: RLE live frames + diag.live_rle")
    ap.add_argument("--sim-saved", action="store_true")
    ap.add_argument("--load-ms", type=int, default=300)
    ap.add_argument("--confirm-s", type=float, default=3.0, help="pending -> valid this long after a reboot")
    ap.add_argument("--start-pending", action="store_true", help="start as a fresh, unconfirmed OTA image")
    a = ap.parse_args()
    board = Board(a)
    if a.start_pending:
        board.ota_state, board.confirm_at = "pending", time.time() + a.confirm_s
    Handler.board = board
    srv = ThreadingHTTPServer(("127.0.0.1", a.http_port), Handler)
    srv.daemon_threads = True
    if not a.no_arduino_ota:
        def on_result(res, img):
            board.ev("arduino-ota", result=res)
            if res == "OK":
                board.reboot(reason=3, new_elf=elf_of_image(img))

        def ota_log(m):
            if m.startswith("invitation"):
                board.ev("invitation")
            print(m, flush=True)
        threading.Thread(target=ota_sim.serve, kwargs=dict(password=a.password, on_result=on_result, log=ota_log),
                         daemon=True).start()
    print(f"mock board {a.fw} on http://127.0.0.1:{a.http_port} (mode {a.mode}, sim {a.sim})", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
