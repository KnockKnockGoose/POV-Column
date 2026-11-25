#!/usr/bin/env python3
r"""ota_sim.py - a fake ESP32 ArduinoOTA receiver, for testing tools/ota_flash.py with no board (OTA review 2026-11-13).

Implements the board side of arduino-esp32 3.3.12 ArduinoOTA.cpp: UDP invitation -> "AUTH <nonce>" -> PBKDF2-HMAC-SHA256
check -> connect back to the uploader -> read the image, answering each read with the byte count -> MD5 check -> "OK".
It also copies the library's receive timeout (wait --rx-timeout ms for data, re-send the count 3 times, abort), so a
stall can be injected to show what kills a transfer:

  py tools\ota_sim.py --password simtest                         well-behaved board on 127.0.0.1:3232
  py tools\ota_sim.py --password simtest --stall-at 300000 --stall-s 5            one 5 s stall (old 1 s timeout: dies)
  py tools\ota_sim.py --password simtest --stall-at 300000 --stall-s 5 --rx-timeout 8000   the fixed firmware: survives
then, in another terminal:
  set POV_OTA_PASS=simtest & py tools\ota_flash.py --host 127.0.0.1 --no-verify --no-fallback --env pov
or the framework's own uploader (checks that this simulator matches espota's auth maths):
  py C:\pio\packages\framework-arduinoespressif32\tools\espota.py -i 127.0.0.1 -a simtest -f .pio\build\pov\firmware.bin

serve() is also used by tools/mock_board.py (2026-11-14), which adds the image firmware's HTTP API and WebSocket around
it so the whole ota_flash.py flow (pause the display, update, verify the build id, restore the picture) runs on the PC.
"""
import argparse, hashlib, os, socket, sys, time


def serve(password, port=3232, rx_timeout=1000, stall_at=-1, stall_s=0.0, once=False, on_result=None, log=print,
          stop=None, host="127.0.0.1"):
    """Answer ArduinoOTA invitations on udp host:port. on_result(result, image_bytes) after each update attempt.
    Returns after one attempt if once=True, or when stop (a threading.Event) is set."""
    pw_hash = hashlib.sha256(password.encode()).hexdigest()   # setPassword() stores sha256(password) as hex
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.bind((host, port))
    udp.settimeout(0.5)
    log(f"sim board on udp {host}:{port}, rx timeout {rx_timeout} ms")
    state, nonce, size, md5, ota_port = "IDLE", "", 0, "", 0
    try:
        while not (stop and stop.is_set()):
            try:
                data, peer = udp.recvfrom(512)
            except socket.timeout:
                continue
            txt = data.decode(errors="replace")
            parts = txt.split()
            cmd = int(parts[0]) if parts and parts[0].isdigit() else -1
            if state == "IDLE":
                if cmd not in (0, 100) or len(parts) < 4:
                    continue
                ota_port, size, md5 = int(parts[1]), int(parts[2]), parts[3].strip()
                if len(md5) != 32:
                    continue
                nonce = hashlib.sha256(f"{time.time()}{os.urandom(8).hex()}".encode()).hexdigest()
                udp.sendto(f"AUTH {nonce}".encode(), peer)
                state = "WAITAUTH"
                log(f"invitation: {size} B, md5 {md5[:8]}..., back to port {ota_port}")
                continue
            # WAITAUTH
            if cmd != 200:
                log(f"200 was expected, got {cmd}: back to idle")
                state = "IDLE"
                continue
            cnonce, resp = (parts[1], parts[2]) if len(parts) >= 3 else ("", "")
            if len(cnonce) != 64 or len(resp) != 64:
                log("auth param fail")
                state = "IDLE"
                continue
            key = hashlib.pbkdf2_hmac("sha256", pw_hash.encode(), f"{nonce}:{cnonce}".encode(), 10000).hex()
            if hashlib.sha256(f"{key}:{nonce}:{cnonce}".encode()).hexdigest() != resp:
                udp.sendto(b"Authentication Failed", peer)
                log("Authentication Failed")
                state = "IDLE"
                continue
            udp.sendto(b"OK", peer)
            state = "IDLE"
            log("auth OK, connecting back")
            result, image = run_update(peer[0], ota_port, size, md5, rx_timeout, stall_at, stall_s, log)
            log(f"update: {result}")
            if on_result:
                on_result(result, image)
            if once:
                return result
    finally:
        udp.close()
    return None


def run_update(ip, port, size, md5, rx_timeout=1000, stall_at=-1, stall_s=0.0, log=print):
    c = socket.create_connection((ip, port), timeout=5)
    h, total, tried, stalled = hashlib.md5(), 0, 0, False
    image = bytearray()
    try:
        while total < size:
            if not stalled and stall_at >= 0 and total >= stall_at:
                # a Wi-Fi stall: nothing arrives for stall_s. Model the library's wait loop over that silence:
                # each rx_timeout without data re-sends the count; the 4th timeout aborts.
                stalled = True
                log(f"  {stall_s} s of silence at {total} B")
                quiet = 0.0
                while quiet + rx_timeout / 1000 <= stall_s:
                    time.sleep(rx_timeout / 1000)
                    quiet += rx_timeout / 1000
                    if tried >= 3:
                        return (f"Receive Failed at {total}/{size} B after {quiet:.0f} s of silence (aborted, old image "
                                f"kept)"), None
                    tried += 1
                    c.sendall(str(total).encode())
                time.sleep(max(0.0, stall_s - quiet))
            c.settimeout(rx_timeout / 1000)
            try:
                d = c.recv(min(1460, size - total))
            except socket.timeout:
                if total and tried < 3:                   # ArduinoOTA: re-send the count, up to 3 times
                    tried += 1
                    c.sendall(str(total).encode())
                    continue
                return f"Receive Failed at {total}/{size} B (aborted, the board keeps its old image)", None
            if not d:
                return f"uploader closed at {total}/{size} B", None
            tried = 0
            h.update(d)
            image.extend(d)
            total += len(d)
            c.sendall(str(len(d)).encode())
        if h.hexdigest() != md5:
            c.sendall(b"ERROR[5]: MD5 Check Failed")
            return "MD5 mismatch", None
        time.sleep(0.5)                                   # image verify + otadata write
        c.sendall(b"OK")
        return "OK", bytes(image)
    finally:
        c.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--password", required=True)
    ap.add_argument("--port", type=int, default=3232)
    ap.add_argument("--rx-timeout", type=int, default=1000, help="ms, ArduinoOTA _ota_timeout (library default 1000)")
    ap.add_argument("--stall-at", type=int, default=-1, help="stop reading for --stall-s once this many bytes arrived")
    ap.add_argument("--stall-s", type=float, default=0)
    ap.add_argument("--once", action="store_true", help="exit after one update attempt (for scripted tests)")
    a = ap.parse_args()
    res = serve(a.password, a.port, a.rx_timeout, a.stall_at, a.stall_s, a.once,
                log=lambda m: print(m, flush=True))
    if a.once:
        return 0 if res == "OK" else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
