#!/usr/bin/env python3
r"""pov_soak.py - acceptance test for Wi-Fi control of the POV column (Wi-Fi control review 2026-11-14).
CHANGES WHAT THE COLUMN SHOWS: run it only when the board is free for testing.

  py tools\pov_soak.py --minutes 30                    switch test over the stored animations, then a 30-min live soak
  py tools\pov_soak.py --minutes 0 --switch a,b,c      only the switch test, these animations
  py tools\pov_soak.py --minutes 30 --no-switch        only the live soak

Targets (from the 11-14 brief): every stored animation playing < 2 s after the request; no reboot, no panic and no
new crash record during the live soak; OTA < 90 s while playing is tools/ota_flash.py's own timing.
Phase 1 plays each animation (largest first: the 62-64 KB files are the ones that failed on 11-14) and times
request -> board reports it playing. Phase 2 streams live frames with tools/pov_stream.py's paced streamer while a
monitor polls /api/status every 10 s for reboots (uptime / boot_count / reset reason) and the crash counter.
Afterwards it puts back the animation that was playing. Result: console + .pio/soak_logs/<time>.json; exit 0 = PASS.
"""
import argparse, json, os, sys, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
FW = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import pov_ctl  # noqa: E402
import pov_stream  # noqa: E402


def log(m):
    print(time.strftime("%H:%M:%S ") + m, flush=True)


def switch_test(b, names, limit_s):
    res = []
    for n in names:
        t0 = time.time()
        code, r = b.req("POST", "/api/play", {"name": n})
        if code != 200:
            res.append({"name": n, "ok": False, "s": None, "err": f"HTTP {code} {r}"})
            log(f"  {n}: HTTP {code} {r}")
            continue
        ok, err, ms = False, "", None
        while time.time() - t0 < 10:
            st = b.status(timeout=3, tries=1) or {}
            ld = st.get("load") or {}
            if "load" not in st:                       # pre-0.4: 200 already means playing
                ok = st.get("anim") == n
                break
            if ld.get("name") == n and ld.get("state") == "ok" and st.get("anim") == n:
                ok, ms = True, ld.get("ms")
                break
            if ld.get("name") == n and ld.get("state") == "error":
                err = ld.get("err")
                break
            time.sleep(0.1)
        s = round(time.time() - t0, 2)
        res.append({"name": n, "ok": ok, "s": s, "board_ms": ms, "err": err})
        log(f"  {n}: {'playing' if ok else 'FAILED'} after {s} s" + (f" (board load {ms} ms)" if ms else "") +
            (f" {err}" if err else ""))
        time.sleep(1.5)                                # let it play a moment
    return res


def monitor(b, stop, events, period):
    last = b.status(timeout=5, tries=3) or {}
    while not stop.wait(period):
        st = b.status(timeout=5, tries=2)
        if st is None:
            events.append({"t": time.time(), "what": "no answer"})
            continue
        rebooted = (st.get("boot_count") != last.get("boot_count") or st.get("uptime_s", 0) < last.get("uptime_s", 0))
        if rebooted:
            e = {"t": time.time(), "what": "REBOOT", "reset": st.get("reset", st.get("reset_reason")),
                 "crash": st.get("crash")}
            events.append(e)
            log(f"  !! board rebooted: reset {e['reset']}, crash {e['crash']}")
        elif (st.get("crash") or {}).get("count", 0) > (last.get("crash") or {}).get("count", 0):
            events.append({"t": time.time(), "what": "CRASH RECORD", "crash": st.get("crash")})
        last = st


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--host", default=os.environ.get("POV_HOST", "pov.local"))
    ap.add_argument("--minutes", type=float, default=30)
    ap.add_argument("--switch", help="comma-separated animations (default: all stored, largest first, max 6)")
    ap.add_argument("--no-switch", action="store_true")
    ap.add_argument("--fps", type=float, default=6.0)
    ap.add_argument("--pattern", default="stripes", choices=sorted(pov_stream.PATTERNS))
    ap.add_argument("--switch-limit", type=float, default=2.0)
    ap.add_argument("--poll", type=float, default=10.0, help="status poll period during the soak (s)")
    a = ap.parse_args()
    b = pov_ctl.Board(a.host)
    st0 = b.status(timeout=6, tries=3)
    if st0 is None:
        log(f"{a.host}: no answer")
        return 2
    log(f"board: fw {st0.get('fw')}, mode {st0.get('mode')} '{st0.get('anim')}', sim {st0.get('sim_rpm')} rpm, "
        f"crashes {(st0.get('crash') or {}).get('count', '-')}, uptime {st0.get('uptime_s')} s")
    if not st0.get("sim_rpm") and not st0.get("rpm"):
        log("  note: no rotation and no simulator: the column draws nothing (set one: pov_ctl.py sim 150)")
    report = {"host": a.host, "start": time.strftime("%Y-%m-%d %H:%M:%S"), "fw": st0.get("fw"), "elf": st0.get("elf")}
    ok = True
    if not a.no_switch:
        names = a.switch.split(",") if a.switch else None
        if not names:
            code, lst = b.req("GET", "/api/anims")
            lst = lst if isinstance(lst, list) else []
            names = [x["name"] for x in sorted(lst, key=lambda x: -x.get("bytes", 0))][:6]
        log(f"phase 1: switch test over {len(names)} animations (target < {a.switch_limit} s each)")
        res = switch_test(b, names, a.switch_limit)
        report["switch"] = res
        worst = max([r["s"] for r in res if r["s"] is not None] or [0])
        sw_ok = all(r["ok"] for r in res) and worst < a.switch_limit
        log(f"  switch test {'PASS' if sw_ok else 'FAIL'}: worst {worst} s")
        ok &= sw_ok
    if a.minutes > 0:
        log(f"phase 2: live soak {a.minutes} min ({a.pattern}, max {a.fps} frames/s, paced by acks)")
        stop, events = threading.Event(), []
        th = threading.Thread(target=monitor, args=(b, stop, events, a.poll), daemon=True)
        th.start()
        stats = pov_stream.run(a.host, a.pattern, a.minutes, a.fps, log=lambda m: log("  " + m))
        stop.set()
        th.join(a.poll + 10)
        st1 = b.status(timeout=6, tries=3) or {}
        reboots = [e for e in events if e["what"] == "REBOOT"]
        crash_new = (st1.get("crash") or {}).get("count", 0) - (st0.get("crash") or {}).get("count", 0)
        report["soak"] = {"stream": stats, "events": events, "new_crash_records": crash_new,
                          "end_status": {k: st1.get(k) for k in ("uptime_s", "boot_count", "reset", "heap", "heap_min",
                                                                  "heap_max_block", "wifi", "diag")}}
        soak_ok = not reboots and crash_new <= 0 and stats["frames"] > 0
        log(f"  stream: {stats['frames']} frames, {stats['fps']} frames/s ({stats['kb_s']} KB/s), ack median "
            f"{stats['ack_med_ms']} ms / max {stats['ack_max_ms']} ms, {stats['reconnects']} reconnects")
        log(f"  soak {'PASS' if soak_ok else 'FAIL'}: {len(reboots)} reboots, {crash_new} new crash records, "
            f"{len([e for e in events if e['what'] == 'no answer'])} unanswered polls")
        ok &= soak_ok
    if st0.get("mode") == "anim" and st0.get("anim"):
        b.req("POST", "/api/play", {"name": st0["anim"]})
        log(f"put back: {st0['anim']}")
    report["pass"] = ok
    out = os.path.join(FW, ".pio", "soak_logs")
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, time.strftime("%Y%m%d-%H%M%S") + ".json")
    json.dump(report, open(path, "w", encoding="utf-8"), indent=1)
    log(f"{'PASS' if ok else 'FAIL'}; report {path}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
