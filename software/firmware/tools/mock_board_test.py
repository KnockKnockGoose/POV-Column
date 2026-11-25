#!/usr/bin/env python3
r"""mock_board_test.py - the Wi-Fi control review's host tests (2026-11-14): tools/ota_flash.py, pov_ctl.py,
pov_stream.py and pov_soak.py against tools/mock_board.py (the image firmware's API, WebSocket and ArduinoOTA on the PC).
No board needed, nothing is sent to pov.local.

  py tools\mock_board_test.py            needs a built image (tools\pio.cmd run -e pov) for the OTA scenarios
  py tools\mock_board_test.py -k stream  only scenarios whose name contains "stream"

Each scenario starts its own mock (http 127.0.0.1:18080, udp 127.0.0.1:3232) and checks what the tools did, in order.
"""
import argparse, json, os, subprocess, sys, threading, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
FW = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import ota_flash  # noqa: E402

PY = sys.executable
PORT = 18080
os.environ["POV_HTTP_PORT"] = str(PORT)          # the in-process streamer (s_stream_*) reads it too
BIN = ota_flash.find_bin("pov", None)
ENV = dict(os.environ, POV_HTTP_PORT=str(PORT), POV_OTA_PASS="simtest", PYTHONUTF8="1", POV_HOST="127.0.0.1")


class Mock:
    def __init__(self, *args):
        self.args = list(args)

    def __enter__(self):
        self.p = subprocess.Popen([PY, os.path.join(HERE, "mock_board.py"), "--http-port", str(PORT)] + self.args,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=ENV)
        for _ in range(50):
            if self.events() is not None:
                return self
            time.sleep(0.1)
        raise RuntimeError("mock did not start")

    def __exit__(self, *exc):
        self.p.kill()
        self.p.communicate()

    def events(self):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/mock/events", timeout=2) as r:
                return json.loads(r.read())
        except Exception:
            return None

    def status(self):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/status", timeout=2) as r:
                return json.loads(r.read())
        except Exception:
            return None

    def post(self, path):
        req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", data=b"{}", method="POST")
        with urllib.request.urlopen(req, timeout=3) as r:
            return r.read()


def tool(name, *args, timeout=300):
    r = subprocess.run([PY, os.path.join(HERE, name)] + list(args), capture_output=True, text=True, env=ENV,
                       cwd=FW, timeout=timeout)
    return r.returncode, r.stdout + r.stderr


def first(events, what, **kw):
    for i, e in enumerate(events):
        if e["what"] == what and all(e.get(k) == v for k, v in kw.items()):
            return i
    return None


def wait_status(m, pred, secs=15):
    t0 = time.time()
    while time.time() - t0 < secs:
        st = m.status()
        if st and pred(st):
            return st
        time.sleep(0.3)
    return m.status()


# ---------------------------------------------------------------------------------------------------------- scenarios
def s_ota_04_playing():
    """ota_flash.py on a 0.4 board playing an animation with the simulator at 150 rpm: the display is paused BEFORE
    the ArduinoOTA invitation, the new build is verified, and the picture (sim 150 + animation) comes back."""
    elf = ota_flash.app_desc(BIN)["elf"]
    with Mock("--fw", "0.4", "--mode", "anim", "--anim", "dog_ball_front", "--sim", "150") as m:
        rc, out = tool("ota_flash.py", "--host", "127.0.0.1", "--bin", BIN, "--tries", "1")
        ev = m.events()
        st = wait_status(m, lambda s: s.get("mode") == "anim")
    i_prep, i_inv = first(ev, "ota-prep"), first(ev, "invitation")
    checks = {"exit 0": rc == 0, "ota-prep before invitation": i_prep is not None and i_inv is not None and i_prep < i_inv,
              "new build running": st.get("elf") == elf, "sim back at 150": st.get("sim_rpm") == 150,
              "animation back": st.get("anim") == "dog_ball_front"}
    return checks, out


def s_ota_02_playing():
    """The same against today's 0.2 build (no /api/ota-prep): stopped with sim_rpm 0 + /api/stop, restored after."""
    with Mock("--fw", "0.2", "--mode", "anim", "--anim", "goose_ball_orbit", "--sim", "150") as m:
        rc, out = tool("ota_flash.py", "--host", "127.0.0.1", "--bin", BIN, "--tries", "1")
        ev = m.events()
        st = wait_status(m, lambda s: s.get("mode") == "anim")
    i_set, i_stop, i_inv = first(ev, "settings", sim_rpm=0), first(ev, "stop"), first(ev, "invitation")
    checks = {"exit 0": rc == 0, "sim 0 + stop before invitation": None not in (i_set, i_stop, i_inv) and max(i_set, i_stop) < i_inv,
              "sim back at 150": st.get("sim_rpm") == 150, "animation back": st.get("anim") == "goose_ball_orbit"}
    return checks, out


def s_ota_http_fallback_empty_token():
    """ArduinoOTA unreachable: the /update fallback runs with POV_TOKEN "" (the 11-14 bug refused: 'no POV_TOKEN')."""
    with Mock("--fw", "0.2", "--no-arduino-ota", "--mode", "anim", "--anim", "dog_ball_front", "--sim", "150") as m:
        rc, out = tool("ota_flash.py", "--host", "127.0.0.1", "--bin", BIN, "--tries", "1")
        ev = m.events()
    checks = {"exit 0": rc == 0, "/update used": first(ev, "http-update") is not None,
              "no 'no POV_TOKEN' refusal": "no POV_TOKEN" not in out}
    return checks, out


def s_ota_token_required():
    """A board that wants a token while wifi_secrets.h has POV_TOKEN "": exit 1 with a message that says so."""
    with Mock("--fw", "0.4", "--no-arduino-ota", "--token", "sekrit") as m:
        rc, out = tool("ota_flash.py", "--host", "127.0.0.1", "--bin", BIN, "--tries", "1")
    checks = {"exit 1": rc == 1, "says the board wants a token": "wants a token" in out}
    return checks, out


def s_ctl_play_timed():
    """pov_ctl play: request -> queued -> playing, timed (0.4 loads in the player task; the mock takes 400 ms)."""
    with Mock("--fw", "0.4", "--load-ms", "400", "--sim", "150") as m:
        rc, out = tool("pov_ctl.py", "play", "bichon_shades_orbit")
        rc2, out2 = tool("pov_ctl.py", "play", "no_such_anim")
    t = None
    for w in out.split():
        try:
            t = float(w)
            break
        except ValueError:
            pass
    checks = {"exit 0": rc == 0, "under 2 s": t is not None and t < 2.0, "missing anim -> exit 1": rc2 == 1}
    return checks, out + out2


def s_ctl_reboot_guard():
    """pov_ctl reboot: refused (409) while a fresh OTA image is unconfirmed, then reboots and comes back."""
    with Mock("--fw", "0.4", "--start-pending", "--confirm-s", "3", "--sim", "150", "--sim-saved") as m:
        rc1, out1 = tool("pov_ctl.py", "reboot")
        time.sleep(3.5)
        rc2, out2 = tool("pov_ctl.py", "reboot")
        st = m.status()
    checks = {"refused while pending": rc1 == 1 and "409" in out1, "reboot after confirm": rc2 == 0,
              "saved sim restarts at boot": (st or {}).get("sim_rpm") == 150}
    return checks, out1 + out2


def s_ctl_crash_record():
    """A panic leaves a record that pov_ctl crash reads back after the reboot."""
    with Mock("--fw", "0.4") as m:
        m.post("/mock/panic")
        time.sleep(2.5)
        rc, out = tool("pov_ctl.py", "crash")
        rc2, out2 = tool("pov_ctl.py", "status")
    checks = {"exit 0": rc == 0, "reason shown": "LoadProhibited" in out, "task shown": "async_tcp" in out,
              "status counts it": "crashes recorded: 1" in out2}
    return checks, out + out2


def s_stream_paced_reconnect():
    """pov_stream: paced by acks, survives a cut link, and never sends a WebSocket close frame (review 3.2)."""
    import pov_stream
    pov_stream.HTTP_PORT = PORT
    with Mock("--fw", "0.4", "--sim", "150") as m:
        res = {}
        lines = []
        th = threading.Thread(target=lambda: res.update(pov_stream.run("127.0.0.1", "stripes", 0.2, 10,
                                                                        log=lines.append)), daemon=True)
        th.start()
        time.sleep(4)
        m.post("/mock/drop_ws")
        th.join(60)
        ev = m.events()
        st = m.status()
    n_open = len([e for e in ev if e["what"] == "ws-open"])
    checks = {"frames sent": res.get("frames", 0) > 40, "acks used": res.get("acks") is True,
              "reconnected": res.get("reconnects", 0) >= 1 and n_open >= 2,
              "no close frames": first(ev, "ws-close-frame") is None,
              "board counted frames": (st or {}).get("diag", {}).get("live_frames", 0) > 30}
    return checks, "\n".join(lines) + "\n" + json.dumps(res)


def s_soak_pass():
    """pov_soak: switch test + 20 s live soak on a healthy board -> PASS."""
    with Mock("--fw", "0.4", "--sim", "150", "--load-ms", "300"):
        rc, out = tool("pov_soak.py", "--minutes", "0.34", "--switch", "dog_ball_front,bichon_shades_orbit", "--poll", "3")
    return {"exit 0 (PASS)": rc == 0, "switch timed": "playing after" in out}, out


def s_soak_detects_panic():
    """pov_soak: a panic reboot during the soak is caught -> FAIL."""
    with Mock("--fw", "0.4", "--sim", "150", "--sim-saved") as m:
        p = subprocess.Popen([PY, os.path.join(HERE, "pov_soak.py"), "--minutes", "0.4", "--no-switch", "--poll", "2"],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=ENV, cwd=FW)
        time.sleep(8)
        m.post("/mock/panic")
        out, _ = p.communicate(timeout=120)
    return {"exit 1 (FAIL)": p.returncode == 1, "reboot reported": "rebooted" in out}, out


SCENARIOS = [s_ota_04_playing, s_ota_02_playing, s_ota_http_fallback_empty_token, s_ota_token_required,
             s_ctl_play_timed, s_ctl_reboot_guard, s_ctl_crash_record, s_stream_paced_reconnect, s_soak_pass,
             s_soak_detects_panic]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-k", default="", help="run scenarios whose name contains this")
    ap.add_argument("-v", action="store_true", help="print tool output for passing scenarios too")
    a = ap.parse_args()
    if not BIN:
        print("build first: tools\\pio.cmd run -e pov")
        return 3
    n_ok = n = 0
    for s in SCENARIOS:
        if a.k not in s.__name__:
            continue
        n += 1
        t0 = time.time()
        try:
            checks, out = s()
        except Exception as e:
            checks, out = {"ran": False}, repr(e)
        ok = all(checks.values())
        n_ok += ok
        print(f"{'PASS' if ok else 'FAIL'}  {s.__name__} ({time.time() - t0:.0f} s): {s.__doc__.split(chr(10))[0]}")
        for k, v in checks.items():
            if not v or a.v:
                print(f"      {'ok ' if v else 'NO '} {k}")
        if not ok or a.v:
            print("      " + "\n      ".join(out.strip().splitlines()[-25:]))
    print(f"\n{n_ok}/{n} scenarios passed")
    return 0 if n_ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
