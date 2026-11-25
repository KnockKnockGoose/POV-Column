"""Check-pack-send audit runner (2026-11-23, docs/2026-11-23-check-pack-send-audit.md). Offline: no Claude call, no board.

    py software/tests/checkpack_audit.py                 # -> software/out/checkpack_audit/ (results.json + table.md)
    py software/tests/checkpack_audit.py --no-pipeline   # skip the pov_request.py dry runs and the mock-board upload

Per worst-case animation (software/tests/checkpack_cases.py) it runs, in the order a request meets them:
  1. the pipeline's checks: povanim.validate at gb 31, then pov_request.auto_fix (on by default since --fast)
  2. the firmware's own check code on the same .pova: tools/cap_audit_host.cpp, compiled here with the PlatformIO MinGW
     g++ (upload check, a copy of valid_name, the do_load current cap at brightness 31 / 23 / 12 / 4)
  3. a calibrated estimate of the REAL current at the brightness the firmware picks (CAL below: SK9822 datasheet and
     Brian's 11-04 single-strip readings), worst rotor position and the revolution average a meter would show
  4. pov_request.py itself, end to end with --script --dry-run (sandbox render -> validate -> auto_fix -> file)
  5. pov_request.upload_and_play against tools/mock_board.py on localhost (what the pipeline reports for a 413)
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOFTWARE = HERE.parent
FIRMWARE = SOFTWARE / "firmware"
sys.path.insert(0, str(SOFTWARE / "povgen"))
sys.path.insert(0, str(SOFTWARE / "pipeline"))
sys.path.insert(0, str(HERE))
import povanim as pa  # noqa: E402
import checkpack_cases as cc  # noqa: E402

MINGW = Path(r"C:\pio\packages\toolchain-gccmingw32\bin")
# Calibration (mA). "model" = the cap's own numbers (povframe.h / povanim). "bench" = Brian's 11-04 single-strip readings
# at 1 MHz, field 4 (docs/2026-11-04-spi-signal-investigation.md: red / green / blue 2.29 / 2.21 / 2.21 mA per LED,
# dark strip 8 mA per 14 LEDs) scaled to field 31 with the datasheet's linear table (2.324 mA at 4/31 ... 18 mA at 31/31);
# "datasheet" = 18 mA per colour. ESP32: the model's 120 mA, and 170 mA with modem sleep off (QA review 2, finding m-b).
CAL = {
    "model":     dict(ch=(20.0, 20.0, 20.0), idle=1.00, esp=120.0),
    "bench":     dict(ch=(2.29 * 31 / 4, 2.21 * 31 / 4, 2.21 * 31 / 4), idle=8.0 / 14, esp=120.0),
    "datasheet": dict(ch=(18.0, 18.0, 18.0), idle=1.00, esp=170.0),
}
LUT = pa.gamma_lut() / 255.0           # the firmware's POV_GAMMA22 table (same rounding), as a duty fraction


def cal_profile(anim: pa.Animation, gb: int, cal: dict) -> np.ndarray:
    """(frames, 96) current in mA at every rotor position with per-colour channel currents cal['ch']."""
    rows, offs = pa.ledmap_arrays()
    cols = (np.arange(pa.COLS)[:, None, None] + offs[None]) % pa.COLS
    pal = anim.palette.array().astype(int)
    duty = LUT[pal]                                                   # (npal, 3)
    i_pix = (duty * np.array(cal["ch"])).sum(axis=1) * gb / 31.0      # mA per LED per palette entry
    fixed = pa.N_STRIPS * pa.LEDS_PER_STRIP * cal["idle"] + cal["esp"]
    return np.array([i_pix[np.minimum(f[rows[None], cols], len(pal) - 1)].sum(axis=(1, 2)) + fixed for f in anim.frames])


# ---------------------------------------------------------------- firmware harness
def build_harness(out: Path) -> Path | None:
    exe = out / "cap_audit_host.exe"
    gxx = MINGW / "g++.exe"
    if not gxx.exists():
        print("MinGW g++ not found at", gxx, "- skipping the firmware harness")
        return None
    env = dict(os.environ, PATH=str(MINGW) + os.pathsep + os.environ.get("PATH", ""))
    r = subprocess.run([str(gxx), "-std=gnu++14", "-O2", "-Wall", "-Wextra", "-mfpmath=sse", "-msse2", "-static", "-static-libgcc",
                        "-static-libstdc++", "-I", str(FIRMWARE / "lib" / "povcore"), "-o", str(exe),
                        str(FIRMWARE / "tools" / "cap_audit_host.cpp")], capture_output=True, text=True, env=env)
    if r.returncode != 0:
        raise RuntimeError("harness build failed:\n" + r.stderr[-2000:])
    return exe


def run_harness(exe: Path, items: list[str]) -> list[dict]:
    r = subprocess.run([str(exe)] + items, capture_output=True, text=True, timeout=300)
    return [json.loads(line) for line in r.stdout.splitlines() if line.strip()]


# ---------------------------------------------------------------- pipeline side
def pipeline_checks(anim: pa.Animation) -> dict:
    """What pov_request.py does after the render: validate, then auto_fix (default since --fast)."""
    import pov_request as pr
    out = {}
    try:
        val = pa.validate(anim, mode=anim.meta.get("mode", "front"))
    except Exception as e:                     # noqa: BLE001 - the audit records any crash as a finding
        return dict(validate_error=f"{type(e).__name__}: {e}")
    out.update(peak_ma_gb31=val["current_peak_ma"], warnings=val["warnings"], ok=val["ok"])
    if not val["ok"]:
        fixed, val2, fixes = pr.auto_fix(anim, val, anim.meta.get("mode", "front"))
        out.update(autofix=fixes, meta_gb=fixed.meta.get("gb"), after_ok=val2["ok"], after_warnings=val2["warnings"],
                   after_peak_ma=val2["current_peak_ma"], after_frames=fixed.n, after_bytes=len(fixed.to_bytes()))
    return out


def dry_run(case: str, work: Path) -> dict:
    """pov_request.py end to end with --script (no Claude), --dry-run (no upload), into a scratch folder."""
    scene = work / f"scene_{case}.py"
    scene.write_text(f"import sys\nsys.path.insert(0, r'{HERE}')\nfrom checkpack_cases import build_case\n\n\n"
                     f"def build():\n    return build_case({case!r})\n", encoding="utf-8")
    rep = work / f"report_{case}.json"
    t0 = time.time()
    r = subprocess.run([sys.executable, str(SOFTWARE / "pipeline" / "pov_request.py"), f"checkpack audit {case}",
                        "--script", str(scene), "--dry-run", "--no-log", "--no-preview", "--out-dir", str(work / "out"),
                        "--report", str(rep)], capture_output=True, text=True, timeout=300)
    res = dict(exit=r.returncode, wall_s=round(time.time() - t0, 1))
    if rep.exists():
        j = json.loads(rep.read_text(encoding="utf-8"))
        st = j.get("stages", {})
        res.update(validate_ok=st.get("validate", {}).get("ok"), warnings=st.get("validate", {}).get("warnings"),
                   autofix=st.get("autofix", {}).get("fixes"), warning=j.get("warning"), upload=j.get("upload"),
                   file=j.get("file"), bytes=os.path.getsize(j["file"]) if j.get("file") and os.path.exists(j["file"]) else None)
    else:
        res["stderr_tail"] = r.stderr.strip().splitlines()[-3:]
    return res


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def mock_uploads(files: dict[str, Path], work: Path) -> dict:
    """pov_request.upload_and_play (the real function) against tools/mock_board.py on localhost."""
    import pov_request as pr
    port = free_port()
    mock = subprocess.Popen([sys.executable, str(FIRMWARE / "tools" / "mock_board.py"), "--http-port", str(port),
                             "--no-arduino-ota", "--anims", ""], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=0.5).read()
                break
            except OSError:
                time.sleep(0.1)
        conf = dict(target=f"http://127.0.0.1:{port}", token="")
        out = {}
        for label, f in files.items():
            dst = work / "upload" / f.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(f, dst)
            if label == "bad_crc":                     # one flipped byte: the board answers 400 (CRC mismatch)
                b = bytearray(dst.read_bytes())
                b[len(b) // 2] ^= 0xFF
                dst.write_bytes(bytes(b))
            try:
                res = pr.upload_and_play(dst, conf)
            except Exception as e:                     # noqa: BLE001 - a crash in the upload step is a finding
                res = dict(crash=f"{type(e).__name__}: {e}")
            out[label] = dict(sent=f.name, bytes=dst.stat().st_size, result=res)
        ev = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/mock/events", timeout=2).read())
        out["_mock_events"] = [e for e in ev if e.get("what") in ("upload", "play")][:20]
        return out
    finally:
        mock.terminate()


def names_check(exe: Path | None, some_file: Path) -> list[dict]:
    """The upload names pov_request.py builds (same expressions as upload_and_play / slugify / main), and whether the
    firmware's valid_name accepts them."""
    import re
    import pov_request as pr
    prompts = ["Biscuit riding a jet ski at sunset", "Biscuit riding a jet ski at sunrise",
               "a wobbly jelly that jiggles", "POV, Biscuit prancing through a meadow all the way round the column"]
    rows = []
    for p in prompts:
        slug = pr.slugify(p)
        for scope, stem in (("home", "20261123-101500_" + slug), ("public", slug)):
            if hasattr(pr, "board_name"):              # 11-23 WIP: the upload name has its own function
                name = pr.board_name(Path(stem + ".pova"))
            else:                                      # b9abc7c: the expression inside upload_and_play
                name = re.sub(r"^\d{8}-\d{6}_", "", stem)[:28].strip("_.-") or "anim"
            rows.append(dict(prompt=p, scope=scope, stem=stem, upload_name=name, length=len(name)))
    if exe is not None:
        res = run_harness(exe, [f"{some_file}={r['upload_name']}" for r in rows])
        for r, h in zip(rows, res):
            r["firmware_valid_name"] = h["name_ok"]
    seen = {}
    for r in rows:
        seen.setdefault(r["upload_name"], set()).add(r["prompt"])
    for r in rows:
        r["collides_with_other_prompt"] = len(seen[r["upload_name"]]) > 1
    return rows


# ---------------------------------------------------------------- main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(SOFTWARE / "out" / "checkpack_audit"))
    ap.add_argument("--no-pipeline", action="store_true")
    a = ap.parse_args(argv)
    out = Path(a.out)
    (out / "pova").mkdir(parents=True, exist_ok=True)
    exe = build_harness(out)

    # the cases, plus the public animations that are on the column today
    anims = {k: f() for k, f in cc.CASES.items()}
    files = {}
    for k, an in anims.items():
        p = out / "pova" / f"cp_{k}.pova"
        an.write(p, sidecar=False)
        files[k] = p
    for p in sorted((SOFTWARE / "content" / "public").glob("*.pova")):
        files["public:" + p.stem] = p
        anims["public:" + p.stem] = pa.Animation.read(p)

    fw = {}
    if exe is not None:
        for k, h in zip(files, run_harness(exe, [str(p) for p in files.values()])):
            fw[k] = h
    rows = {}
    for k, an in anims.items():
        r = dict(case=k, bytes=files[k].stat().st_size, frames=an.n, palette=len(an.palette))
        r["pipeline"] = pipeline_checks(pa.Animation.from_bytes(an.to_bytes()))   # a copy: auto_fix edits in place
        r["firmware"] = fw.get(k)
        f = fw.get(k) or {}
        if f.get("fit"):
            est = {}
            for req in ("31", "12"):
                gb = f["fit"][req]["gb_used"]
                e = {}
                for cname, cal in CAL.items():
                    prof = cal_profile(an, gb, cal)
                    e[cname] = dict(peak_ma=round(float(prof.max())), mean_ma=round(float(prof.mean())))
                est[req] = dict(gb=gb, **e)
            r["current_estimate"] = est
        rows[k] = r

    report = dict(when=time.strftime("%Y-%m-%dT%H:%M:%S"), cap_ma_firmware=2600, cap_note="LED drive + idle; ESP32 on top",
                  validator_cap_ma=pa.CAP_MA, cal=CAL, cases=rows)
    if exe is not None:
        report["names"] = names_check(exe, files["dark"])
    if not a.no_pipeline:
        work = Path(tempfile.mkdtemp(prefix="cp_dry_", dir=str(out)))
        report["dry_runs"] = {c: dry_run(c, work) for c in ("white_full", "white_stripes4", "noise_big", "pal_33",
                                                              "bad_index", "frames_257")}
        report["mock_upload"] = mock_uploads({"public_jetski": files["public:biscuit_jetski"],
                                              "at_64k": files["at_64k"], "over_64k_by_1": files["over_64k_by_1"],
                                              "noise_big": files["noise_big"], "bad_crc": files["white_full"]}, work)
    (out / "results.json").write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")

    # compact table
    lines = ["| case | bytes | validator peak @31 (mA) | auto_fix | firmware upload | firmware gb @31 / @12 | model total @31-cap (mA) | "
             "real est. peak @31-cap (A) | real est. avg @12 (A) |", "|---|---|---|---|---|---|---|---|---|"]
    for k, r in rows.items():
        p, f, e = r["pipeline"], r["firmware"] or {}, r.get("current_estimate") or {}
        up = f"{f.get('upload_http')} {f.get('upload_err') or ''}".strip()
        gbs = f"{f['fit']['31']['gb_used']} / {f['fit']['12']['gb_used']}" if f.get("fit") else f.get("load_err", "")
        mt = f["fit"]["31"]["total_ma"] if f.get("fit") else ""
        re31 = (f"{e['31']['bench']['peak_ma'] / 1000:.2f}-{e['31']['datasheet']['peak_ma'] / 1000:.2f}" if e else "")
        re12 = (f"{e['12']['bench']['mean_ma'] / 1000:.2f}-{e['12']['datasheet']['mean_ma'] / 1000:.2f}" if e else "")
        fix = "; ".join(p.get("autofix", []) or []) if "autofix" in p else ("crash: " + p["validate_error"] if "validate_error" in p else "-")
        lines.append(f"| {k} | {r['bytes']:,} | {p.get('peak_ma_gb31', '')} | {fix} | {up} | {gbs} | {mt} | {re31} | {re12} |")
    (out / "table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print("\nwrote", out / "results.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
