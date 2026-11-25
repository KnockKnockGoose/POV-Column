"""Integration test: Infinite Biscuit against the firmware mock (software/firmware/tools/mock_board.py) on port 18099:
takeover, the 3-clip window on the column, yielding to another agent, `start` taking it back, stop + restore + cleanup.

    py software/tests/infinite_biscuit_mock_test.py      # needs a populated library (infinite_biscuit.py pregen);
                                                         # do not run while the real gallery is running
2026-11-23: 8 / 8 passed.
"""
import json
import os
import subprocess
import sys
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # software/
PORT = 18099
BASE = f"http://127.0.0.1:{PORT}"
IB = [sys.executable, "-X", "utf8", os.path.join(ROOT, "pipeline", "infinite_biscuit.py")]
STATE = os.path.join(os.environ["LOCALAPPDATA"], "POVColumn", "home", "infinite_biscuit", "runner_state.json")
env = dict(os.environ, NO_COLOR="1")
results = []


def st():
    return requests.get(BASE + "/api/status", timeout=3).json()


def anims():
    return [a["name"] for a in requests.get(BASE + "/api/anims", timeout=3).json()]


def ib(*args, timeout=60):
    r = subprocess.run(IB + list(args), capture_output=True, text=True, timeout=timeout, env=env)
    return (r.stdout + r.stderr).strip()


def check(name, ok, detail=""):
    results.append((name, ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""), flush=True)


def main() -> int:
    mock = subprocess.Popen([sys.executable, os.path.join(ROOT, "firmware", "tools", "mock_board.py"), "--http-port",
                             str(PORT), "--no-arduino-ota", "--mode", "anim", "--anim", "bichon_shades_front",
                             "--load-ms", "150"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    run = None
    try:
        for _ in range(40):
            try:
                st()
                break
            except Exception:                                                   # noqa: BLE001
                time.sleep(0.25)
        run = subprocess.Popen(IB + ["run", "--target", BASE, "--no-live", "--laps", "1", "--speed", "4"],
                               stdout=open(os.path.join(os.environ.get("TEMP", "."), "ib_mock_run.log"), "w"),
                               stderr=subprocess.STDOUT, env=env)
        time.sleep(9)
        s1, a1 = st(), anims()
        ours = [n for n in a1 if n.startswith("ib")]
        check("takes over: an ib clip is playing", s1["anim"].startswith("ib"), s1["anim"])
        check("others' anims untouched", all(n in a1 for n in ("dog_ball_front", "bichon_shades_front")), str(a1))
        check("at most 3 of ours on the column", 1 <= len(ours) <= 3, str(ours))
        requests.post(BASE + "/api/play", json={"name": "dog_ball_front"}, timeout=3)     # another agent plays
        time.sleep(6)
        s2 = st()
        state = json.load(open(STATE, encoding="utf-8"))
        check("yields to another agent (paused, not overwritten)",
              s2["anim"] == "dog_ball_front" and bool(state.get("paused")), f"anim={s2['anim']} paused={state.get('paused')}")
        out = ib("start", "--target", BASE)
        time.sleep(6)
        s3 = st()
        check("start takes the column back", s3["anim"].startswith("ib"), f"{out} / anim={s3['anim']}")
        print(ib("stop"))
        time.sleep(1)
        s4, a4 = st(), anims()
        check("stop restores the animation that was playing before", s4["anim"] == "bichon_shades_front", s4["anim"])
        check("stop removes our clips", not [n for n in a4 if n.startswith("ib")], str(a4))
        check("runner exited", run.poll() is not None, str(run.poll()))
    finally:
        mock.kill()
        if run is not None and run.poll() is None:
            run.kill()
    passed = sum(ok for _, ok in results)
    print("RESULT:", passed, "/", len(results), "passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
