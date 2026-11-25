#!/usr/bin/env python3
r"""pov_ctl.py - control the POV column's image firmware over Wi-Fi (Wi-Fi control review 2026-11-14), pure stdlib.

  py tools\pov_ctl.py status                  what it is doing: mode, animation, load, simulator, heap, link, crashes
  py tools\pov_ctl.py play bichon_shades_front  play a stored animation and time it (target < 2 s)
  py tools\pov_ctl.py stop
  py tools\pov_ctl.py sim 150 --persist       simulated hall at 150 rpm, kept across reboots (0 --persist = off)
  py tools\pov_ctl.py gb 12                   brightness request (1..31; the current cap may lower it)
  py tools\pov_ctl.py reboot [--force]        restart without opening the sled (refused in the first ~15 s after an
                                              OTA boot, when a reset would roll the new image back; --force overrides)
  py tools\pov_ctl.py prep [--secs 300]       pause the display for an update (ota_flash.py does this by itself)
  py tools\pov_ctl.py resume
  py tools\pov_ctl.py crash [--clear]         the last crash record, decoded to file:line with the matching firmware.elf
  py tools\pov_ctl.py net [--n 30]            link quality: HTTP status round trips + ping loss (read-only)
  py tools\pov_ctl.py ab [--secs 30]          diagnostic A/B (CHANGES THE DISPLAY, needs 0.4+): link quality with the
                                              picture on, LEDs dark (test_dark), no SPI (test_nospi), display paused
Exit code 0 = done, 1 = the board refused or failed, 2 = no answer. Board: --host or POV_HOST (default pov.local).
The API token comes from src/wifi_secrets.h (POV_TOKEN; "" = no token) and is never printed.
"""
import argparse, glob, hashlib, json, os, re, statistics, subprocess, sys, time, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
FW = os.path.dirname(HERE)
HTTP_PORT = int(os.environ.get("POV_HTTP_PORT", "80"))


def token():
    try:
        m = re.search(r'#define\s+POV_TOKEN\s+"([^"]*)"', open(os.path.join(FW, "src", "wifi_secrets.h"), encoding="utf-8").read())
        return m.group(1) if m else ""
    except OSError:
        return ""


class Board:
    def __init__(self, host):
        self.host = host
        self.base = f"http://{host}" if HTTP_PORT == 80 else f"http://{host}:{HTTP_PORT}"
        self.tok = token()

    def req(self, method, path, body=None, timeout=6, tries=3):
        """(status, parsed JSON or text); status None = no answer."""
        hdr = {"Content-Type": "application/json"}
        if self.tok:
            hdr["X-POV-Token"] = self.tok
        data = json.dumps(body).encode() if body is not None else (b"{}" if method == "POST" else None)
        last = None
        for _ in range(tries):
            try:
                r = urllib.request.Request(self.base + path, data=data, headers=hdr, method=method)
                with urllib.request.urlopen(r, timeout=timeout) as resp:
                    return resp.status, _parse(resp.read())
            except urllib.error.HTTPError as e:
                return e.code, _parse(e.read())
            except Exception as e:
                last = e
                time.sleep(0.5)
        return None, str(last)

    def status(self, timeout=5, tries=2):
        code, st = self.req("GET", "/api/status", timeout=timeout, tries=tries)
        return st if code == 200 and isinstance(st, dict) else None


def _parse(b):
    t = b.decode(errors="replace")
    try:
        return json.loads(t)
    except ValueError:
        return t


def summary(st):
    ld = st.get("load") or {}
    w = st.get("wifi") or {}
    g = st.get("diag") or {}
    c = st.get("crash") or {}
    lines = [
        f"fw {st.get('fw')}  elf {st.get('elf')}  ota {st.get('ota')}  uptime {st.get('uptime_s')} s  boot "
        f"{st.get('boot_count')} (reset: {st.get('reset', st.get('reset_reason'))})",
        f"mode {st.get('mode')}  anim '{st.get('anim')}' ({st.get('frames')} frames)  running {st.get('running')}  "
        f"rpm {st.get('rpm', 0):.0f}  sim {st.get('sim_rpm')} (saved {st.get('sim_saved', '-')})  gb {st.get('gb')}->"
        f"{st.get('gb_used')}  paused {st.get('paused', '-')}",
    ]
    if ld:
        lines.append(f"load {ld.get('state')} '{ld.get('name')}' {ld.get('ms')} ms  ok {ld.get('ok')} failed "
                     f"{ld.get('failed')}" + (f"  error: {ld.get('err')}" if ld.get("err") else ""))
    lines.append(f"heap {st.get('heap')} (min {st.get('heap_min')}, largest block {st.get('heap_max_block', '-')})  "
                 f"rssi {st.get('rssi')} dBm  tx {w.get('tx_dbm', '-')} dBm  wifi drops {w.get('disconnects', '-')}  "
                 f"ws {w.get('ws_clients', '-')}")
    if g:
        sf = g.get("stack_free") or {}
        lines.append(f"cpu: column {g.get('col_busy_pct')} % of core 1, core-0 lag {g.get('lag0_ms')} ms (max "
                     f"{g.get('lag0_max_ms')}), loop lag {g.get('lag1_ms')} ms (max {g.get('lag1_max_ms')})  "
                     f"live {g.get('live_frames')} ok / {g.get('live_bad')} bad  dark {g.get('test_dark')} nospi "
                     f"{g.get('test_nospi')}")
        if sf:
            lines.append("stack free: " + ", ".join(f"{k} {v}" for k, v in sf.items()))
    if c:
        lines.append(f"crashes recorded: {c.get('count')}" + (f"  last: {c.get('reason')} {c.get('msg', '')} "
                                                              f"(task {c.get('task')}, boot {c.get('boot')})"
                                                              if c.get("reason") else ""))
    return "\n".join(lines)


# ---------------------------------------------------------------------------------------------------------- crash decode
def find_elf(elf_id):
    """firmware.elf whose SHA-256 starts with elf_id (that is how esptool fills esp_app_desc_t.app_elf_sha256)."""
    cands = [os.path.join(FW, ".pio", "elf_archive", f"{elf_id}.elf")]
    cands += glob.glob(os.path.join(FW, ".pio", "build", "*", "firmware.elf"))
    if os.environ.get("PLATFORMIO_BUILD_DIR"):
        cands += glob.glob(os.path.join(os.environ["PLATFORMIO_BUILD_DIR"], "*", "firmware.elf"))
    for c in cands:
        if os.path.exists(c) and hashlib.sha256(open(c, "rb").read()).hexdigest()[:16] == elf_id:
            return c
    return None


def addr2line():
    for home in (os.environ.get("PLATFORMIO_CORE_DIR"), r"C:\pio", r"C:\pio\core", os.path.expanduser("~/.platformio")):
        if home:
            p = os.path.join(home, "packages", "toolchain-xtensa-esp-elf", "bin", "xtensa-esp32-elf-addr2line.exe")
            if os.path.exists(p):
                return p
    return None


def decode(elf, pcs):
    tool = addr2line()
    if not tool or not elf or not pcs:
        return None
    try:
        out = subprocess.run([tool, "-pfiaC", "-e", elf] + pcs, capture_output=True, text=True, timeout=30).stdout
        return out.strip().splitlines()
    except (OSError, subprocess.SubprocessError):
        return None


# ---------------------------------------------------------------------------------------------------------- link probe
def ping_loss(host, n):
    if host.startswith("127."):
        return None, None
    try:
        out = subprocess.run(["ping", "-n" if os.name == "nt" else "-c", str(n), host], capture_output=True, text=True,
                             timeout=n * 5 + 10).stdout
    except (OSError, subprocess.SubprocessError):
        return None, None
    # count real echo replies only: Windows counts "Destination host unreachable" (from this PC) as received
    rt = [float(x) for x in re.findall(r"time[=<](\d+(?:\.\d+)?)", out)]
    loss = round(100.0 * (n - min(n, len(rt))) / n, 1)
    return loss, (statistics.median(rt) if rt else None)


def probe(b, secs, label=""):
    """HTTP status round trips for `secs` (one at a time) + a short ping run. Returns a result dict."""
    t_end, rtts, fails = time.time() + secs, [], 0
    while time.time() < t_end:
        t = time.time()
        st = b.status(timeout=4, tries=1)
        if st is None:
            fails += 1
        else:
            rtts.append((time.time() - t) * 1000)
        time.sleep(0.3)
    loss, ping_ms = ping_loss(b.host, 10)
    r = {"label": label, "http_ok": len(rtts), "http_fail": fails,
         "http_med_ms": round(statistics.median(rtts)) if rtts else None,
         "http_p90_ms": round(sorted(rtts)[int(len(rtts) * 0.9) - 1]) if len(rtts) >= 3 else None,
         "ping_loss_pct": loss, "ping_med_ms": ping_ms}
    return r


def fmt_probe(r):
    return (f"{r['label']:<34s} http {r['http_ok']:3d} ok / {r['http_fail']:2d} failed, median {r['http_med_ms']} ms, "
            f"p90 {r['http_p90_ms']} ms | ping loss {r['ping_loss_pct']} %, median {r['ping_med_ms']} ms")


# ---------------------------------------------------------------------------------------------------------- commands
def cmd_play(b, a):
    st0 = b.status() or {}
    t0 = time.time()
    code, r = b.req("POST", "/api/play", {"name": a.name})
    if code != 200:
        print(f"play {a.name}: HTTP {code} {r}")
        return 1 if code else 2
    if not (st0.get("load") is not None or (r if isinstance(r, dict) else {}).get("queued")):
        print(f"playing {a.name} (pre-0.4 firmware: synchronous, {time.time() - t0:.2f} s)")
        return 0
    if a.no_wait:
        print(f"queued {a.name}")
        return 0
    while time.time() - t0 < a.timeout:
        st = b.status(timeout=3, tries=1) or {}
        ld = st.get("load") or {}
        if ld.get("name") == a.name and ld.get("state") == "ok" and st.get("anim") == a.name:
            print(f"playing {a.name}: {time.time() - t0:.2f} s from request to playing (board load {ld.get('ms')} ms, "
                  f"{st.get('frames')} frames, gb {st.get('gb_used')})")
            return 0
        if ld.get("name") == a.name and ld.get("state") == "error":
            print(f"play {a.name} FAILED: {ld.get('err')}")
            return 1
        time.sleep(0.1)
    print(f"play {a.name}: not playing after {a.timeout} s")
    return 1


def cmd_reboot(b, a):
    st0 = b.status() or {}
    code, r = b.req("POST", "/api/reboot" + ("?force=1" if a.force else ""), tries=1)
    if code != 200:
        print(f"reboot: HTTP {code} {r}")
        return 1 if code else 2
    t0, seen_down = time.time(), False
    while time.time() - t0 < 60:
        st = b.status(timeout=2, tries=1)
        if st is None:
            seen_down = True
        elif seen_down or st.get("boot_count") != st0.get("boot_count") or (st.get("uptime_s", 1e9) < st0.get("uptime_s", 0)):
            print(f"back after {time.time() - t0:.1f} s: boot {st.get('boot_count')}, mode {st.get('mode')}, sim "
                  f"{st.get('sim_rpm')} rpm, ota {st.get('ota')}")
            return 0
        time.sleep(1)
    print("rebooting, but no answer within 60 s")
    return 2


def cmd_crash(b, a):
    if a.clear:
        code, r = b.req("DELETE", "/api/crash")
        print(f"crash record cleared (HTTP {code})")
        return 0 if code == 200 else 1
    code, c = b.req("GET", "/api/crash")
    if code != 200 or not isinstance(c, dict):
        print(f"no crash endpoint (HTTP {code}): firmware older than 0.4")
        return 1
    if not c.get("have"):
        print(f"no crash recorded (count {c.get('count')}, running elf {c.get('running_elf')})")
        return 0
    print(f"crashes recorded: {c['count']}; last one at boot {c.get('boot')} ({c.get('reset')}), uptime "
          f"{c.get('uptime_ms', 0) / 1000:.1f} s, heap {c.get('heap')} B")
    print(f"  reason: {c.get('reason')}  {c.get('msg') or ''}")
    print(f"  task {c.get('task')} on core {c.get('core')}; our code was in: {c.get('op')} ({c.get('op_age_ms')} ms "
          f"before)")
    elf = a.elf or find_elf(c.get("elf", ""))
    pcs = c.get("bt") or []
    lines = decode(elf, pcs)
    if lines:
        print(f"  backtrace ({os.path.relpath(elf, FW)}):")
        for ln in lines:
            print("    " + ln)
    else:
        print(f"  backtrace: {' '.join(pcs)}{' (corrupt)' if c.get('bt_corrupt') else ''}")
        print(f"  (no firmware.elf with build id {c.get('elf')} here, or no addr2line: ota_flash.py keeps each flashed "
              f"ELF in .pio/elf_archive/; pass --elf)")
    return 0


def cmd_ab(b, a):
    st = b.status()
    if not st or "diag" not in st:
        print("ab needs firmware 0.4+ (test_dark / test_nospi switches)")
        return 1
    print(f"A/B link test, {a.secs} s per phase. Board: {st.get('mode')} '{st.get('anim')}', sim {st.get('sim_rpm')} "
          f"rpm, gb {st.get('gb_used')}, tx {st.get('wifi', {}).get('tx_dbm')} dBm")
    if not st.get("running"):
        print("  note: the display is not running (no rotation / simulator off): phase A equals the paused case")
    res = []
    try:
        res.append(probe(b, a.secs, "A picture on (as it is)"))
        print(fmt_probe(res[-1]), flush=True)
        b.req("POST", "/api/settings", {"test_dark": True})
        res.append(probe(b, a.secs, "B LEDs dark, SPI + CPU as A"))
        print(fmt_probe(res[-1]), flush=True)
        b.req("POST", "/api/settings", {"test_dark": False, "test_nospi": True})
        res.append(probe(b, a.secs, "C no SPI, CPU as A"))
        print(fmt_probe(res[-1]), flush=True)
        b.req("POST", "/api/settings", {"test_nospi": False})
        b.req("POST", f"/api/ota-prep?secs={a.secs + 30}")
        res.append(probe(b, a.secs, "D display paused (OTA prep)"))
        print(fmt_probe(res[-1]), flush=True)
    finally:
        b.req("POST", "/api/settings", {"test_dark": False, "test_nospi": False})
        b.req("POST", "/api/resume")
    st = b.status() or {}
    g = st.get("diag") or {}
    print(f"core-0 lag max {g.get('lag0_max_ms')} ms, loop lag max {g.get('lag1_max_ms')} ms, wifi drops "
          f"{(st.get('wifi') or {}).get('disconnects')}")
    print("Reading: A bad, B good -> LED current (supply ripple / bank) hurts the radio; B bad, C good -> the SPI lines "
          "radiate; C bad, D good -> CPU or software; all good -> today's trouble was the session state, not the display.")
    if a.json:
        print(json.dumps(res))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--host", default=os.environ.get("POV_HOST", "pov.local"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status").add_argument("--json", action="store_true")
    p = sub.add_parser("play"); p.add_argument("name"); p.add_argument("--no-wait", action="store_true")
    p.add_argument("--timeout", type=float, default=10)
    sub.add_parser("stop")
    p = sub.add_parser("sim"); p.add_argument("rpm", type=int); p.add_argument("--persist", action="store_true")
    p = sub.add_parser("gb"); p.add_argument("value", type=int)
    p = sub.add_parser("reboot"); p.add_argument("--force", action="store_true")
    p = sub.add_parser("prep"); p.add_argument("--secs", type=int, default=300)
    sub.add_parser("resume")
    p = sub.add_parser("crash"); p.add_argument("--clear", action="store_true"); p.add_argument("--elf")
    p = sub.add_parser("net"); p.add_argument("--secs", type=float, default=15)
    p = sub.add_parser("ab"); p.add_argument("--secs", type=float, default=30); p.add_argument("--json", action="store_true")
    a = ap.parse_args()
    b = Board(a.host)
    if a.cmd == "status":
        st = b.status(timeout=6, tries=3)
        if st is None:
            print(f"{a.host}: no answer")
            return 2
        print(json.dumps(st, indent=1) if a.json else summary(st))
        return 0
    if a.cmd == "play":
        return cmd_play(b, a)
    if a.cmd == "stop":
        code, _ = b.req("POST", "/api/stop")
        print(f"stop: HTTP {code}")
        return 0 if code == 200 else 1
    if a.cmd == "sim":
        body = {"sim_rpm": a.rpm}
        if a.persist:
            body["sim_persist"] = True
        code, st = b.req("POST", "/api/settings", body)
        if code == 200 and isinstance(st, dict):
            print(f"sim {st.get('sim_rpm')} rpm (saved {st.get('sim_saved', 'n/a: firmware < 0.4')})")
            return 0
        print(f"sim: HTTP {code} {st}")
        return 1
    if a.cmd == "gb":
        code, st = b.req("POST", "/api/settings", {"gb": a.value})
        print(f"gb {a.value}: HTTP {code}" + (f", in use {st.get('gb_used')}" if isinstance(st, dict) else ""))
        return 0 if code == 200 else 1
    if a.cmd == "reboot":
        return cmd_reboot(b, a)
    if a.cmd in ("prep", "resume"):
        code, r = b.req("POST", f"/api/ota-prep?secs={a.secs}" if a.cmd == "prep" else "/api/resume")
        print(f"{a.cmd}: HTTP {code} {r}")
        return 0 if code == 200 else 1
    if a.cmd == "crash":
        return cmd_crash(b, a)
    if a.cmd == "net":
        r = probe(b, a.secs, "link now")
        print(fmt_probe(r))
        return 0 if r["http_ok"] else 2
    if a.cmd == "ab":
        return cmd_ab(b, a)
    return 1


if __name__ == "__main__":
    sys.exit(main())
