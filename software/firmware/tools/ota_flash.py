#!/usr/bin/env python3
r"""ota_flash.py - flash the POV column's ESP32 over Wi-Fi and prove the new build is running.

Rewritten after the OTA failure review (docs/2026-11-13-ota-failure-review.md). The old wrapper ran the framework's
espota.py and filtered its output; espota writes its ERROR line onto the same line as the progress bar, so the filter
threw away every real error and a failed transfer looked like "Authenticating... OK" and then nothing.

What this does differently
  * Speaks the ArduinoOTA protocol itself (same PBKDF2-HMAC-SHA256 auth as arduino-esp32 3.3.x espota.py), but STREAMS
    the image instead of espota's send-1-KB-then-wait lock-step: lost packets are repaired by TCP fast retransmit
    instead of each one costing a full retransmit timeout (which the board's 1 s x 3 receive timeout could not survive).
  * Retries the whole invitation/auth/transfer up to --tries times; resets the board's OTA state machine first.
  * Falls back to the web endpoint POST /update (image firmware only) when ArduinoOTA keeps failing; --http forces it.
  * Verifies: reads the build id (app ELF SHA-256, first 16 hex) out of firmware.bin and waits until the board reports
    that id (GET /api/status "elf" for pov, the `i` line on TCP 23 for phase0) and a confirmed ("valid") OTA image.
  * Logs the full trace to .pio/ota_logs/ ; the OTA password and API token never appear in the console or the log.
  * (Wi-Fi control review 2026-11-14) Pauses the display before the first packet: POST /api/ota-prep on 0.4+ firmware,
    or /api/settings {"sim_rpm":0} + /api/stop on older images. On 11-14 three ArduinoOTA tries died at the
    authentication while an animation ran with the simulated hall at 150 rpm (66 % ping loss); with the display stopped
    the same update took 61 s. Afterwards it puts the picture back (simulator rpm + animation; --no-restore skips it)
    and keeps a copy of firmware.elf in .pio/elf_archive/ so tools/pov_ctl.py crash can decode a later crash record.

  py tools\ota_flash.py --env pov                build first: tools\pio.cmd run -e pov
  py tools\ota_flash.py --env phase0
  py tools\ota_flash.py --env pov --http         web /update instead of ArduinoOTA
  py tools\ota_flash.py --check                  no flashing: what is running, local build ids, firewall path
  py tools\ota_flash.py --env pov_crashtest --expect-rollback     rollback self-test (see the review, section 6)
Exit codes: 0 new build verified running | 1 upload failed (board unchanged) | 2 uploaded, but the board is not running
the new build (rolled back / not back) | 3 set-up error (no image, no password, board not found).

Secrets: the OTA password comes from platformio_local.ini (--auth=..., gitignored; env POV_OTA_PASS overrides, for the
simulator), the API token from src/wifi_secrets.h (POV_TOKEN; "" = the board checks no token, which is how it runs on
2026-11-14). Board: pov.local unless --host or POV_HOST gives another name or address.
The board connects BACK to this PC on TCP --local-port (default 53232): the Python running this script needs an inbound
firewall allow (any port, or that port). --check tests that path from the Pi.
"""
import argparse, hashlib, http.client, json, os, re, shutil, socket, struct, subprocess, sys, threading, time
import urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
FW = os.path.dirname(HERE)
OTA_PORT = 3232
HTTP_PORT = int(os.environ.get("POV_HTTP_PORT", "80"))     # tests: tools/mock_board.py serves the API on another port


def base_url(host):
    return f"http://{host}" if HTTP_PORT == 80 else f"http://{host}:{HTTP_PORT}"
U_FLASH, U_AUTH = 0, 200


# ---------------------------------------------------------------------------------------------------------- logging
class Log:
    def __init__(self, path, secrets):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.f = open(path, "a", encoding="utf-8")
        self.secrets = [s for s in secrets if s]
        self.path = path

    def _scrub(self, s):
        for x in self.secrets:
            s = s.replace(x, "<secret>")
        return s

    def __call__(self, msg, console=True):
        msg = self._scrub(str(msg))
        self.f.write(time.strftime("%H:%M:%S ") + msg + "\n")
        self.f.flush()
        if console:
            print(msg, flush=True)


# ---------------------------------------------------------------------------------------------------------- inputs
def read_secret(path, pattern):
    """The first match of `pattern` in the file. None = no file or no match; "" = present but empty. Callers must keep
    those apart: POV_TOKEN "" is a real setting (the board checks no token), not a missing secret (bug of 2026-11-14:
    the /update fallback refused to run with "no POV_TOKEN in src/wifi_secrets.h")."""
    try:
        m = re.search(pattern, open(path, encoding="utf-8", errors="replace").read())
        return m.group(1) if m else None
    except OSError:
        return None


def find_bin(env, explicit):
    if explicit:
        return explicit if os.path.exists(explicit) else None
    roots = [os.environ.get("PLATFORMIO_BUILD_DIR"), os.path.join(FW, ".pio", "build")]
    cands = [os.path.join(r, e, "firmware.bin") for r in roots if r for e in (env, env + "_ota")]
    cands = [c for c in cands if os.path.exists(c)]
    return max(cands, key=os.path.getmtime) if cands else None


def app_desc(path):
    """esp_app_desc_t from an ESP32 app image: 24-byte image header + 8-byte segment header, then the descriptor.
    Only 'elf' identifies OUR build (esptool patches it per ELF); version/date/time come from the prebuilt Arduino libs."""
    b = open(path, "rb").read(512)
    if len(b) < 256 or b[0] != 0xE9:
        raise ValueError(f"{path} is not an ESP32 app image")
    o = 32
    if struct.unpack_from("<I", b, o)[0] != 0xABCD5432:
        raise ValueError(f"{path}: no app descriptor")
    cstr = lambda a, n: b[o + a:o + a + n].split(b"\0")[0].decode(errors="replace")
    return {"version": cstr(16, 32), "project": cstr(48, 32), "time": cstr(80, 16), "date": cstr(96, 16),
            "idf": cstr(112, 32), "elf": b[o + 144:o + 152].hex()}


# ---------------------------------------------------------------------------------------------------------- board state
def pov_status(host, timeout=4):
    try:
        with urllib.request.urlopen(f"{base_url(host)}/api/status", timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def api_post(host, path, token, body=None, timeout=8, tries=3):
    """POST to the image firmware's API. Returns (status, text); status None = no answer after `tries`. TCP rides out
    a lossy link (retransmits); the retries cover a request the board dropped."""
    data = json.dumps(body if body is not None else {}).encode()
    hdr = {"Content-Type": "application/json"}
    if token:
        hdr["X-POV-Token"] = token
    last = None
    for _ in range(tries):
        try:
            req = urllib.request.Request(f"{base_url(host)}{path}", data=data, headers=hdr, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read().decode(errors="replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode(errors="replace")
        except Exception as e:
            last = e
            time.sleep(1)
    return None, str(last)


def pause_display(host, token, before, log):
    """Stop the picture before the update so the radio has the link to itself (review 2026-11-14). Returns what to put
    back afterwards: {"sim_rpm": n, "anim": name} (empty values = nothing to restore)."""
    before = before or {}
    keep = {"sim_rpm": before.get("sim_rpm") or 0, "anim": before.get("anim") if before.get("mode") == "anim" else ""}
    code, txt = api_post(host, "/api/ota-prep?secs=300", token)
    if code == 200:
        log(f"display paused for the update (/api/ota-prep): {txt[:160]}")
    elif code == 401:
        log("WARNING: /api/ota-prep answered 401: POV_TOKEN differs from the running image; display left running")
        return keep
    else:                                              # pre-0.4 firmware: no ota-prep endpoint
        c1, _ = api_post(host, "/api/settings", token, {"sim_rpm": 0})
        c2, _ = api_post(host, "/api/stop", token)
        log(f"display stopped the old way (no /api/ota-prep: HTTP {code}): sim_rpm 0 -> {c1}, stop -> {c2}")
    if keep["sim_rpm"] or keep["anim"]:
        log(f"  will restore afterwards: sim {keep['sim_rpm']} rpm, animation '{keep['anim']}'")
    time.sleep(1.5)                                    # let the LEDs go dark and the link settle
    n_ok, rtts = 0, []
    for _ in range(3):
        t = time.time()
        if pov_status(host, timeout=4) is not None:
            n_ok += 1
            rtts.append(time.time() - t)
    if rtts:
        log(f"  link check: {n_ok}/3 status calls answered, median {sorted(rtts)[len(rtts) // 2] * 1000:.0f} ms")
    else:
        log("  link check: no status answers in 3 tries (the update may still get through: TCP retries)")
    return keep


def restore_display(host, token, keep, log, after_reboot):
    """Put the picture back: on a new 0.4+ image a saved simulator starts by itself; older state is re-applied here."""
    if not keep or not (keep.get("sim_rpm") or keep.get("anim")):
        if not after_reboot:
            api_post(host, "/api/resume", token, tries=2)
        return
    st = pov_status(host) or {}
    if keep.get("sim_rpm") and not st.get("sim_rpm"):
        c, _ = api_post(host, "/api/settings", token, {"sim_rpm": keep["sim_rpm"]})
        log(f"restored the simulated hall: {keep['sim_rpm']} rpm (HTTP {c})")
    elif not after_reboot:
        api_post(host, "/api/resume", token, tries=2)
    if keep.get("anim") and (st.get("mode") != "anim" or st.get("anim") != keep["anim"]):
        c, _ = api_post(host, "/api/play", token, {"name": keep["anim"]})
        log(f"restored the animation '{keep['anim']}' (HTTP {c})")


def phase0_info(host, timeout=4):
    """phase0: connect to the TCP 23 command port, send `i` (read-only info), parse elf / ota state."""
    try:
        with socket.create_connection((host, 23), timeout=timeout) as s:
            s.sendall(b"i\n")
            s.settimeout(1.0)
            buf, t_end = b"", time.time() + timeout
            while time.time() < t_end:
                try:
                    d = s.recv(4096)
                    if not d:
                        break
                    buf += d
                    if b"frame resends" in buf:
                        break
                except socket.timeout:
                    if buf:
                        break
            txt = buf.decode(errors="replace")
            m = re.search(r"elf ([0-9a-f]{16}), ota image (\w+)", txt)
            v = re.search(r"firmware (\S+)", txt)
            return {"kind": "phase0", "elf": m.group(1) if m else None, "ota": m.group(2) if m else None,
                    "fw": v.group(1).rstrip(",") if v else "phase0 (pre-review build)"}
    except Exception:
        return None


def running(host):
    st = pov_status(host)
    if st is not None:
        return {"kind": "pov", "elf": st.get("elf"), "ota": st.get("ota"), "fw": st.get("fw"),
                "uptime": st.get("uptime_s"), "boot_count": st.get("boot_count"), "rssi": st.get("rssi"),
                "rpm": st.get("rpm"), "mode": st.get("mode")}
    return phase0_info(host)


def describe(r):
    if not r:
        return "not answering (no HTTP status, no TCP 23)"
    s = f"{r['kind']} fw {r.get('fw')}, elf {r.get('elf') or '?'} (pre-review builds report none), ota {r.get('ota') or '?'}"
    if r.get("uptime") is not None:
        s += f", uptime {r['uptime']} s, rssi {r.get('rssi')} dBm, rpm {r.get('rpm')}, mode {r.get('mode')}"
    return s


def local_ip_for(ip):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((ip, OTA_PORT))
        return s.getsockname()[0]
    finally:
        s.close()


# ---------------------------------------------------------------------------------------------------------- ArduinoOTA
def auth_response(password, nonce, cnonce):
    """arduino-esp32 >= 3.3.1: board stores sha256(password) hex; PBKDF2-HMAC-SHA256(that, nonce:cnonce, 10000)."""
    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    key = hashlib.pbkdf2_hmac("sha256", pw_hash.encode(), f"{nonce}:{cnonce}".encode(), 10000).hex()
    return hashlib.sha256(f"{key}:{nonce}:{cnonce}".encode()).hexdigest()


class AuthRejected(Exception):
    pass


def udp_exchange(sock, ip, port, msg, wait):
    sock.sendto(msg.encode(), (ip, port))
    sock.settimeout(wait)
    try:
        data, _ = sock.recvfrom(128)
        return data.decode(errors="replace")
    except socket.timeout:
        return None


def arduino_ota_once(ip, port, password, image, local_port, log):
    size, md5 = len(image), hashlib.md5(image).hexdigest()
    lst = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    lst.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    lst.bind(("0.0.0.0", local_port))
    lst.listen(1)
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # a stray packet first: puts a board left in WAIT-AUTH by an earlier try back to idle (ignored when idle)
        udp.sendto(b"999\n", (ip, port))
        time.sleep(0.3)
        reply = None
        for k in range(2):                                 # one invitation, one repeat; the board may be busy
            reply = udp_exchange(udp, ip, port, f"{U_FLASH} {local_port} {size} {md5}\n", 12)
            if reply:
                break
            log(f"  no answer to the invitation ({k + 1}/2)")
        if not reply:
            return "no answer to the invitation (board off, wrong IP, or its loop is blocked)"
        log(f"  invitation answered: {reply[:5]}...", console=False)
        if reply.startswith("AUTH"):
            nonce = reply.split()[1].strip()
            if len(nonce) != 64:
                return f"board sent a {len(nonce)}-char nonce: it runs a pre-3.3.1 core (MD5 auth), use espota.py"
            cnonce = hashlib.sha256(f"{size}{md5}{ip}{time.time()}".encode()).hexdigest()
            t0 = time.time()
            ans = udp_exchange(udp, ip, port, f"{U_AUTH} {cnonce} {auth_response(password, nonce, cnonce)}\n", 25)
            log(f"  auth answer after {time.time() - t0:.1f} s: {ans!r}", console=False)
            if ans is None:
                return ("no answer to the authentication: ArduinoOTA sends it once and never repeats it, so one lost "
                        "datagram ends the try (or the board's loop() was blocked; 0.4 reports diag.lag1_max_ms)")
            if ans.strip() != "OK":
                raise AuthRejected(ans.strip())
            log(f"  authenticated ({time.time() - t0:.1f} s)")
        elif reply.strip() != "OK":
            return f"unexpected answer to the invitation: {reply!r}"
        lst.settimeout(20)
        try:
            conn, addr = lst.accept()
        except socket.timeout:
            return (f"the board never connected back to this PC on TCP {local_port}: inbound firewall for "
                    f"{sys.executable}? (run --check)")
        log(f"  board connected back from {addr[0]}; streaming {size} B")
        got = bytearray()
        done = threading.Event()

        def reader():
            conn.settimeout(1.0)
            while not done.is_set():
                try:
                    d = conn.recv(256)
                    if not d:
                        break
                    got.extend(d)
                except socket.timeout:
                    continue
                except OSError:
                    break
            done.set()

        th = threading.Thread(target=reader, daemon=True)
        th.start()
        conn.settimeout(30)
        t0, sent, next_pct = time.time(), 0, 20
        try:
            for i in range(0, size, 4096):
                conn.sendall(image[i:i + 4096])
                sent = min(size, i + 4096)
                pct = sent * 100 // size
                if pct >= next_pct:
                    log(f"  {pct:3d} %  {sent / 1024 / max(0.001, time.time() - t0):5.1f} KB/s")
                    next_pct += 20
        except OSError as e:
            done.set()
            tail = bytes(got[-80:]).decode(errors="replace")
            return f"transfer broke at {sent}/{size} B after {time.time() - t0:.1f} s: {e} (board said: {tail!r})"
        t_end = time.time() + 60                          # the board verifies the image, writes otadata, says OK
        while time.time() < t_end and not done.is_set():
            if b"OK" in got or b"ERROR" in got or b"rror" in got:
                break
            time.sleep(0.2)
        done.set()
        tail = bytes(got[-120:]).decode(errors="replace")
        conn.close()
        if b"OK" in got:
            log(f"  board accepted the image ({time.time() - t0:.1f} s): rebooting into it")
            return None
        return f"sent all {size} B but the board did not confirm (last words: {tail!r})"
    finally:
        udp.close()
        lst.close()


def arduino_ota(ip, port, password, image, local_port, tries, log):
    last = None
    for t in range(1, tries + 1):
        log(f"ArduinoOTA try {t}/{tries}")
        try:
            last = arduino_ota_once(ip, port, password, image, local_port, log)
        except AuthRejected as e:
            log(f"  board REJECTED the password ({e}): the running image was built with a different OTA_PASS than "
                f"platformio_local.ini. One USB flash of the current build fixes it.")
            return "password rejected"
        except OSError as e:
            last = f"socket error: {e}"
        if last is None:
            return None
        log(f"  failed: {last}")
        time.sleep(3)
    return last


# ---------------------------------------------------------------------------------------------------------- HTTP /update
def http_update(host, token, image, log):
    if token is None:
        log("  (no POV_TOKEN define in src/wifi_secrets.h: sending no token; the board answers 401 if it wants one)")
    boundary = "----povota" + hashlib.md5(image).hexdigest()[:16]
    head = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"fw\"; filename=\"firmware.bin\"\r\n"
            f"Content-Type: application/octet-stream\r\n\r\n").encode()
    tail = f"\r\n--{boundary}--\r\n".encode()
    body_len = len(head) + len(image) + len(tail)
    log(f"HTTP POST /update ({len(image)} B)")
    try:
        c = http.client.HTTPConnection(host, HTTP_PORT, timeout=60)
        c.putrequest("POST", "/update")
        if token:
            c.putheader("X-POV-Token", token)
        c.putheader("Content-Type", f"multipart/form-data; boundary={boundary}")
        c.putheader("Content-Length", str(body_len))
        c.endheaders()
        c.send(head)
        t0, next_pct = time.time(), 20
        for i in range(0, len(image), 8192):
            c.send(image[i:i + 8192])
            pct = min(100, (i + 8192) * 100 // len(image))
            if pct >= next_pct:
                log(f"  {pct:3d} %  {(i + 8192) / 1024 / max(0.001, time.time() - t0):5.1f} KB/s")
                next_pct = pct + 20
        c.send(tail)
        r = c.getresponse()
        txt = r.read().decode(errors="replace").strip()
        log(f"  board answered {r.status}: {txt}")
        if r.status == 401:
            return ("token rejected (the running image was built with a different POV_TOKEN than src/wifi_secrets.h)"
                    if token else 'the board wants a token, and src/wifi_secrets.h has POV_TOKEN ""')
        return None if r.status == 200 else f"HTTP {r.status}: {txt}"
    except http.client.RemoteDisconnected:
        return ("the board closed the connection without an answer (old firmware: its web server drops a request "
                "after a 3 s stall, and a dropped upload leaves the column dark until a reboot)")
    except OSError as e:
        return f"HTTP upload failed: {e}"


# ---------------------------------------------------------------------------------------------------------- verify
def wait_for_build(host, before, want_elf, expect_rollback, log, secs=120):
    """Wait for the reboot, then for the board to report the expected build and a confirmed OTA image."""
    t0 = time.time()
    seen_down, last = False, None
    while time.time() - t0 < secs:
        r = running(host)
        if r is None:
            if not seen_down:
                log("  board rebooting...")
            seen_down = True
        else:
            rebooted = seen_down or (before and before.get("uptime") is not None and r.get("uptime") is not None
                                     and r["uptime"] < before["uptime"])
            if rebooted or r.get("elf") != (before or {}).get("elf"):
                if expect_rollback:
                    if r.get("elf") != want_elf:
                        log(f"  rolled back as expected: {describe(r)}")
                        return True
                elif r.get("elf") == want_elf:
                    if r.get("ota") in ("valid", "usb", None):
                        log(f"  verified: {describe(r)}")
                        return True
                    if r != last:
                        log(f"  new build up, OTA image '{r.get('ota')}' (confirms ~15 s after Wi-Fi joins)")
                elif rebooted and before and before.get("elf") and r.get("elf") == before["elf"]:
                    log(f"  board came back on the OLD build (rolled back: the new image crashed or never got Wi-Fi): "
                        f"{describe(r)}")
                    return False
                elif r != last:
                    log(f"  board is back on a different build: {describe(r)}")
            last = r
        time.sleep(2)
    log(f"  gave up after {secs} s; last seen: {describe(last)}")
    return False


def archive_elf(bin_path, elf_id, log):
    """Keep firmware.elf under its build id so a crash record (GET /api/crash) can be decoded later (tools/pov_ctl.py)."""
    elf = os.path.join(os.path.dirname(bin_path), "firmware.elf")
    if not os.path.exists(elf):
        return
    try:
        dst = os.path.join(FW, ".pio", "elf_archive")
        os.makedirs(dst, exist_ok=True)
        shutil.copy2(elf, os.path.join(dst, f"{elf_id}.elf"))
        log(f"  firmware.elf kept as .pio/elf_archive/{elf_id}.elf (crash decoding)", console=False)
    except OSError as e:
        log(f"  could not archive firmware.elf: {e}", console=False)


# ---------------------------------------------------------------------------------------------------------- firewall check
# A second machine on the board's LAN that this PC can reach with key-based SSH. It is used to test whether this
# PC's firewall lets the board connect back: POV_PROBE_SSH=user@host[,user@host]. Unset = the test is skipped.
PROBE_SSH = [t.strip() for t in os.environ.get("POV_PROBE_SSH", "").split(",") if t.strip()]


def firewall_check(ip, local_port, log):
    me = local_ip_for(ip)
    if not PROBE_SSH:
        log(f"This PC is {me} on the board's network; the board must reach {me}:{local_port} (TCP, inbound).")
        log("  inbound-firewall test skipped: set POV_PROBE_SSH=user@host (a machine on the board's LAN) to run it")
        return None
    log(f"This PC is {me} on the board's network; the board must reach {me}:{local_port} (TCP, inbound).")
    lst = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    lst.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    lst.bind(("0.0.0.0", local_port))
    lst.listen(1)
    lst.settimeout(15)
    res = {}

    def acc():
        try:
            c, a = lst.accept()
            res["from"] = a[0]
            c.close()
        except Exception as e:
            res["err"] = str(e)

    th = threading.Thread(target=acc, daemon=True)
    th.start()
    probe = (f"python3 -c \"import socket;socket.create_connection(('{me}',{local_port}),5).close();print('connected')\"")
    out = []
    for target in PROBE_SSH:
        try:
            p = subprocess.run(["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes", target, probe],
                               capture_output=True, text=True, timeout=25)
            out = (p.stdout + p.stderr).strip().splitlines()
            if p.returncode == 0 or "from" in res:
                break
        except Exception as e:
            out = [f"ssh {target} failed: {e}"]
    th.join(16)
    lst.close()
    if "from" in res:
        log(f"  firewall OK: a connection from {res['from']} (the probe host, same LAN as the board) reached {sys.executable}")
        return True
    log(f"  firewall BLOCKS (or the probe host is unreachable): {out[-1] if out else res.get('err')}")
    log(f"  fix (admin PowerShell): New-NetFirewallRule -DisplayName \"POV OTA {local_port}\" -Direction Inbound "
        f"-Protocol TCP -LocalPort {local_port} -Action Allow -Profile Any")
    return False


# ---------------------------------------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--env", default="pov", help="build env whose firmware.bin to send (pov, phase0, pov_crashtest)")
    ap.add_argument("--bin", help="explicit firmware.bin (default: newest of .pio/build/<env>[_ota]/ and PLATFORMIO_BUILD_DIR)")
    ap.add_argument("--host", default=os.environ.get("POV_HOST", "pov.local"))
    ap.add_argument("--ota-port", type=int, default=OTA_PORT)
    ap.add_argument("--local-port", type=int, default=53232, help="TCP port the board connects back to")
    ap.add_argument("--tries", type=int, default=3)
    ap.add_argument("--http", action="store_true", help="use POST /update (image firmware) instead of ArduinoOTA")
    ap.add_argument("--no-fallback", action="store_true", help="do not fall back to /update when ArduinoOTA fails")
    ap.add_argument("--no-verify", action="store_true", help="skip the post-flash check (simulator tests)")
    ap.add_argument("--expect-rollback", action="store_true", help="crash-test image: success = previous build returns")
    ap.add_argument("--force", action="store_true", help="flash even if the board already runs this build")
    ap.add_argument("--check", action="store_true", help="no flashing: board, build ids, firewall path")
    ap.add_argument("--no-pause", action="store_true", help="do not pause the display before the update")
    ap.add_argument("--no-restore", action="store_true", help="leave the display off after the update")
    a = ap.parse_args()
    t_start = time.time()

    pw = os.environ.get("POV_OTA_PASS") or read_secret(os.path.join(FW, "platformio_local.ini"), r"--auth=(\S+)")
    token = read_secret(os.path.join(FW, "src", "wifi_secrets.h"), r'#define\s+POV_TOKEN\s+"([^"]*)"')
    log = Log(os.path.join(FW, ".pio", "ota_logs", time.strftime("%Y%m%d-%H%M%S") + f"-{a.env}.log"), [pw, token])
    try:
        ip = socket.gethostbyname(a.host)
    except OSError:
        log(f"cannot resolve {a.host}")
        return 3

    before = None if a.no_verify else running(a.host)
    if not a.no_verify:
        log(f"board {a.host}: {describe(before)}")

    if a.check:
        for env in ("pov", "phase0", "pov_crashtest"):
            b = find_bin(env, None)
            if b:
                d = app_desc(b)
                log(f"local {env:13s} elf {d['elf']}  file {time.strftime('%Y-%m-%d %H:%M', time.localtime(os.path.getmtime(b)))}  {b}")
        firewall_check(ip, a.local_port, log)
        log(f"log: {log.path}")
        return 0

    path = find_bin(a.env, a.bin)
    if not path:
        log(f"no firmware.bin for env '{a.env}': build it first (tools\\pio.cmd run -e {a.env})")
        return 3
    desc = app_desc(path)
    image = open(path, "rb").read()
    log(f"image {path}\n  {len(image)} B, elf {desc['elf']}, file time "
        f"{time.strftime('%Y-%m-%d %H:%M', time.localtime(os.path.getmtime(path)))}")
    if before and before.get("elf") == desc["elf"] and not a.force and not a.expect_rollback:
        log("the board already runs this build; nothing to do (--force to flash anyway)")
        return 0
    full = pov_status(a.host) if (before or {}).get("kind") == "pov" else None
    if before and before.get("rpm") and not (full or {}).get("sim_rpm"):
        log(f"WARNING: rotor at {before['rpm']:.0f} rpm: stop the motor for OTA (a spinning rotor dropped a transfer on 11-12)")
    keep = None
    if (before or {}).get("kind") == "pov" and not a.no_pause and not a.no_verify:
        keep = pause_display(a.host, token, full, log)

    err = "not tried"
    if not a.http:
        if not pw:
            log("no OTA password: platformio_local.ini needs  upload_flags = --auth=<OTA_PASS>")
            return 3
        err = arduino_ota(ip, a.ota_port, pw, image, a.local_port, a.tries, log)
    if err and (a.http or (not a.no_fallback and err != "password rejected" and (before or {}).get("kind") == "pov")):
        if not a.http:
            log("ArduinoOTA failed; falling back to the web /update endpoint")
        err = http_update(a.host, token, image, log)
    if err:
        log(f"FAILED: {err}\n  board unchanged; full trace: {log.path}")
        if keep is not None and not a.no_restore:
            restore_display(a.host, token, keep, log, after_reboot=False)
        return 1
    if a.no_verify:
        log("uploaded (not verified: --no-verify)")
        return 0
    archive_elf(path, desc["elf"], log)
    ok = wait_for_build(a.host, before, desc["elf"], a.expect_rollback, log)
    if keep is not None and not a.no_restore:
        restore_display(a.host, token, keep, log, after_reboot=True)
    log(("OK" if ok else "NOT VERIFIED") + f" in {time.time() - t_start:.0f} s; trace: {log.path}")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
