#!/usr/bin/env python3
r"""ota_sim_test.py - OTA self-test step 1, no board: run tools/ota_flash.py and the framework's espota.py against
tools/ota_sim.py (a fake ArduinoOTA receiver on 127.0.0.1) in six scenarios. All six must match "expect".

  py tools\ota_sim_test.py            needs a built image (tools\pio.cmd run -e pov) and the PlatformIO framework

Results on the desktop PC, 2026-11-13: 6/6 as expected (OTA failure review, docs/2026-11-13-ota-failure-review.md section 6).
"""
import os, subprocess, sys, time

FW = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(FW, "tools"))
import ota_flash  # noqa: E402  (find_bin)

PY = sys.executable
BIN = ota_flash.find_bin("pov", None)
_ESPOTA = os.path.join("packages", "framework-arduinoespressif32", "tools", "espota.py")
ESPOTA = next((os.path.join(c, _ESPOTA) for c in (os.environ.get("PLATFORMIO_CORE_DIR"), r"C:\pio", r"C:\pio\core")
               if c and os.path.exists(os.path.join(c, _ESPOTA))), None)


def run(name, sim_args, up_cmd, expect_ok, pw="simtest"):
    sim = subprocess.Popen([PY, os.path.join(FW, "tools", "ota_sim.py"), "--password", "simtest", "--once"] + sim_args,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    time.sleep(1.0)
    env = dict(os.environ, POV_OTA_PASS=pw, PYTHONUTF8="1")
    up = subprocess.run(up_cmd, capture_output=True, text=True, env=env, cwd=FW, timeout=300)
    try:
        so, _ = sim.communicate(timeout=30)
    except subprocess.TimeoutExpired:
        sim.kill()
        so, _ = sim.communicate()
    res = [l for l in so.splitlines() if l.startswith("update:") or "Failed" in l]
    ok = (up.returncode == 0) == expect_ok
    print(f"{'PASS' if ok else 'FAIL'}  {name}\n      uploader rc {up.returncode}; board: {res[-1] if res else '?'}")
    return ok


def main():
    if not BIN:
        print("build first: tools\\pio.cmd run -e pov")
        return 3
    of = [PY, os.path.join(FW, "tools", "ota_flash.py"), "--host", "127.0.0.1", "--no-verify", "--no-fallback",
          "--bin", BIN, "--tries", "1"]
    stall = ["--stall-at", "300000", "--stall-s", "5"]
    results = []
    if ESPOTA:
        eo = [PY, ESPOTA, "-i", "127.0.0.1", "-a", "simtest", "-f", BIN]
        results.append(run("espota.py vs the simulator (auth maths agree)", [], eo, True))
        results.append(run("espota.py, 5 s silence, library 1 s timeout (the old failure)", stall, eo, False))
    results.append(run("ota_flash.py vs the simulator", [], of, True))
    results.append(run("ota_flash.py, 5 s silence, 1 s timeout (old firmware still aborts)", stall, of, False))
    results.append(run("ota_flash.py, 5 s silence, 8 s timeout (fixed firmware survives)", stall + ["--rx-timeout", "8000"], of, True))
    results.append(run("ota_flash.py, wrong password (clear message, no retries)", [], of, False, pw="wrong"))
    print(f"\n{sum(results)}/{len(results)} as expected")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
