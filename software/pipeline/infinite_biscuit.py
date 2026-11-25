"""Infinite Biscuit: an endless live gallery for the POV column (Part 3's live-request section).

Biscuit walks round the column through the 11-22 meadow. Every two laps he comes back round doing something new:
each clip is one sentence from infinite_biscuit_sentences.csv ("Biscuit" + verb + object, e.g. "Biscuit flies a kite")
that Claude turns into a short scene script through the pov_request pipeline (used as a library: same headless
`claude -p` call, sandbox render, validator and uploader), with biscuit_kit so Biscuit looks the same in every clip.
Each clip is fitted to the column's 64 KB, filed in the home folder (AI media, not in git) and played back to back.
A cached library keeps the playlist smooth on camera; the live generator keeps making new ones in the background and
queues each as soon as it is ready. Every generation's timings go to gen_log.jsonl ("seconds, not minutes").

    py software/pipeline/infinite_biscuit.py start            # Main's one-liner: gallery + live generation (own tab)
    py software/pipeline/infinite_biscuit.py stop             # Main's one-liner: stop; the column goes back to what it showed
    py software/pipeline/infinite_biscuit.py next             # skip to the next clip now
    py software/pipeline/infinite_biscuit.py add "rides a dinosaur"   # generate a new sentence, plays next
    py software/pipeline/infinite_biscuit.py status           # what is playing, queue, library, timing stats
    py software/pipeline/infinite_biscuit.py pregen 18        # fill the cache (skips sentences already cached)
    py software/pipeline/infinite_biscuit.py stats            # generation times (median / range) for the video
    py software/pipeline/infinite_biscuit.py review           # one PNG of every clip (Biscuit in front) for curation
    py software/pipeline/infinite_biscuit.py drop 12          # take clip 12 out of the playlist (undrop to restore)
    py software/pipeline/infinite_biscuit.py run --sim        # foreground, no column: prints the schedule

Column rules (shared rig): the runner only uploads, plays and deletes its own clips (names start with "ib"); it never
deletes anyone else's animation, never reboots or flashes. If another animation shows up on the column while it runs,
it pauses instead of fighting over the column; `start` again takes it back. `stop` restores whatever was playing.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import math
import os
import random
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pov_request as pr  # noqa: E402  (the pipeline, used as a library; it also puts software/povgen on sys.path)
import fastlane  # noqa: E402
import povanim  # noqa: E402

pr.ALLOWED_IMPORTS.add("biscuit_kit")   # also being added upstream by pov-pipeline-live (2026-11-23)

TABLE = HERE / "infinite_biscuit_sentences.csv"
SYSTEM_PROMPT = HERE / "prompts" / "infinite_biscuit.md"
MODEL, EFFORT = pr.FAST["model"], pr.FAST["effort"]      # Sonnet, low effort: the --fast lane (2026-11-07)
LIMIT = 65536                     # firmware POVA_MAX_FILE
BUDGET = 62_000                   # what we aim for (margin under the limit)
FRAME_LADDER = (80, 60, 48, 40)   # frames per 8 s lap: 10 / 7.5 / 6 / 5 fps, whole 225-rpm refresh ticks
DEFAULT_FRAMES = 60
PREFIX = "ib"                     # our clips on the column: ibNN_<action>
TAKEOVER_ANIM = ("off", "")       # modes / names that count as "nothing playing"
SKIES = ("day", "sunset", "dusk", "night", "rain", "snow")
REMIX = [dict(sky="sunset"), dict(sky="night"), dict(sky="dusk"), dict(sky="day", extra="with a rainbow in the sky"),
         dict(sky="day", extra="wearing sunglasses"), dict(sky="day", extra="wearing a party hat"),
         dict(sky="snow"), dict(sky="day", extra="wearing a crown")]
ANSI = os.environ.get("NO_COLOR") is None
C = dict(dim="\033[2m", b="\033[1m", g="\033[32m", y="\033[33m", c="\033[36m", m="\033[35m", r="\033[31m", x="\033[0m")


def paint(s: str, *styles: str) -> str:
    return ("".join(C[k] for k in styles) + s + C["x"]) if ANSI else s


def say(msg: str) -> None:
    print(time.strftime("[%H:%M:%S] ") + msg, flush=True)


def home() -> Path:
    h = Path(pr.load_conf()["home_dir"]) / "infinite_biscuit"
    (h / "clips").mkdir(parents=True, exist_ok=True)
    (h / "requests").mkdir(exist_ok=True)
    return h


def slug(s: str, n: int = 40) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:n] or "clip"


def clean_action(text: str) -> str:
    """'Biscuit rides a dinosaur!' / 'rides a dinosaur' -> 'rides a dinosaur'."""
    s = re.sub(r"^\s*(biscuit|the dog|he)\s+", "", text.strip(), flags=re.I)
    return re.sub(r"[.!?]+$", "", s).strip()


# ================================================================ sentence table
def load_table() -> list[dict]:
    rows = []
    with open(TABLE, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if str(r.get("enabled", "1")).strip() not in ("0", "no", "false"):
                rows.append(dict(id=int(r["id"]), action=r["action"].strip(), staging=r.get("staging", "").strip(),
                                 sky=(r.get("sky") or "day").strip() or "day", uses=r.get("uses", "").strip()))
    return rows


def variant_key(action: str, sky: str, extra: str = "") -> str:
    return slug(f"{action} {sky} {extra}", 80)


# ================================================================ library (home folder, never in git)
class Library:
    """library.json: one entry per generated clip; gen_log.jsonl: one line per generation attempt (ok or not)."""

    def __init__(self, root: Path):
        self.root, self.lock = root, threading.RLock()
        self.index, self.log = root / "library.json", root / "gen_log.jsonl"

    def entries(self) -> list[dict]:
        with self.lock:
            if not self.index.exists():
                return []
            try:
                return json.loads(self.index.read_text(encoding="utf-8"))
            except ValueError:
                return []

    def save(self, entries: list[dict]) -> None:
        with self.lock:
            tmp = self.index.with_suffix(".tmp")
            tmp.write_text(json.dumps(entries, indent=1), encoding="utf-8")
            os.replace(tmp, self.index)

    def add(self, e: dict) -> None:
        with self.lock:
            es = self.entries()
            es.append(e)
            self.save(es)

    def next_id(self) -> int:
        with self.lock:
            return max([e["id"] for e in self.entries()] + [0]) + 1

    def playable(self) -> list[dict]:
        return [e for e in self.entries() if e.get("status") == "ok" and Path(e["file"]).exists()]

    def playlist(self) -> list[int]:
        """The curated running order (playlist.json); clips not in it play after it, in id order."""
        p = self.root / "playlist.json"
        try:
            return [int(x) for x in json.loads(p.read_text(encoding="utf-8"))]
        except (OSError, ValueError, TypeError):
            return []

    def ordered(self) -> list[dict]:
        pl = {e["id"]: e for e in self.playable()}
        order = [i for i in self.playlist() if i in pl]
        return [pl[i] for i in order] + [pl[i] for i in sorted(pl) if i not in set(order)]

    def has(self, key: str) -> bool:
        return any(e.get("key") == key and e.get("status") in ("ok", "drop") for e in self.entries())

    def set_status(self, cid: int, status: str) -> bool:
        with self.lock:
            es = self.entries()
            hit = False
            for e in es:
                if e["id"] == cid:
                    e["status"], hit = status, True
            self.save(es)
            return hit

    def log_gen(self, rec: dict) -> None:
        with self.lock:
            with open(self.log, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")

    def gen_records(self) -> list[dict]:
        if not self.log.exists():
            return []
        out = []
        for line in self.log.read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
        return out


# ================================================================ generation (pov_request as a library)
_POOL_LOCK = threading.Lock()


def warm_pool(conf: dict) -> None:
    """One pre-spawned claude process for our system prompt (saves the CLI's ~1 s start per generation)."""
    with _POOL_LOCK:
        if pr._POOL is None:
            pr._POOL = pr.WarmPool(conf)
        pr._POOL.prewarm(MODEL, EFFORT, SYSTEM_PROMPT.read_text(encoding="utf-8"))


def close_pool() -> None:
    with _POOL_LOCK:
        if pr._POOL is not None:
            pr._POOL.close()
            pr._POOL = None


WRAPPER = """import sys, importlib.util
import biscuit_kit
biscuit_kit.FRAMES = {frames}
_spec = importlib.util.spec_from_file_location("clip", {script!r})
_m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_m)
build = _m.build
"""


def render_frames(script: Path, frames: int, out: Path, conf: dict) -> Path:
    """Re-render a clip script at another frame count (same loop, finer or coarser sampling) in the sandbox."""
    wrap = out.with_suffix(f".f{frames}.py")
    wrap.write_text(WRAPPER.format(frames=frames, script=str(script)), encoding="utf-8")
    pr.render_script(wrap, out, conf)
    return out


def decimate(anim: povanim.Animation, k: int) -> povanim.Animation:
    """Every k-th frame at fps / k (duration kept): Main's 11-22 fix, used only if re-rendering is not enough."""
    anim.frames, anim.holds = anim.frames[::k], anim.holds[::k]
    anim.fps = anim.fps / k
    return anim


def fit_clip(script: Path, pova: Path, work: Path, conf: dict) -> tuple[Path, dict]:
    """Pick the largest frame count from FRAME_LADDER whose file fits BUDGET (re-rendering the script), so smooth
    clips stay smooth and busy ones still fit. Returns (pova, info)."""
    info: dict = dict(tried={})
    size0 = pova.stat().st_size
    n0 = povanim.Animation.read(pova).n
    info["tried"][n0] = size0
    best = (n0, pova) if size0 <= BUDGET else None
    per_frame = size0 / max(1, n0)
    for n in FRAME_LADDER:
        if n == n0 or (best and n < best[0]):
            continue
        if n > n0 and per_frame * n > BUDGET * 1.02:          # clearly too big: do not bother rendering
            continue
        if n < n0 and best:
            break
        out = work / f"fit{n}.pova"
        try:
            render_frames(script, n, out, conf)
        except RuntimeError as e:
            info["error"] = str(e)[-200:]
            continue
        sz = out.stat().st_size
        info["tried"][n] = sz
        if sz <= BUDGET and (best is None or n > best[0]):
            best = (n, out)
            if n < n0:
                break
    if best is None:                                          # still too big at 40 frames: decimate the smallest
        smallest = min(info["tried"], key=lambda k: info["tried"][k])
        src = pova if smallest == n0 else work / f"fit{smallest}.pova"
        anim = povanim.Animation.read(src)
        fit_size = getattr(pr, "fit_size", None)
        if fit_size is not None:
            anim, notes = fit_size(anim, limit=BUDGET)
            info["fit_size"] = notes
        else:
            while len(anim.to_bytes()) > BUDGET and anim.n >= 8:
                anim = decimate(anim, 2)
            info["decimated"] = True
        out = work / "fit_last.pova"
        anim.write(out)
        best = (anim.n, out)
    info["frames"] = best[0]
    return best[1], info


def biscuit_pixels(anim: povanim.Animation) -> int:
    """Fewest Biscuit-white pixels in any frame (a sanity check that he is actually in every frame)."""
    rgb = [tuple(v) for v in anim.palette.rgb]
    fur = [i for i, v in enumerate(rgb) if v == (235, 235, 235)]
    if not fur:
        return 0
    return int(min(sum(int((f == i).sum()) for i in fur) for f in anim.frames))


def device_name(cid: int, action: str) -> str:
    return f"{PREFIX}{cid:02d}_{slug(action, 24)}"[:28].rstrip("_")


def generate(job: dict, lib: Library, conf: dict, quiet: bool = False) -> dict | None:
    """One clip: Claude writes the script (kit prompt) -> sandbox render -> validate -> fit 64 KB -> file it.
    job: action, staging, sky, extra, source. Returns the library entry, or None on failure (logged either way)."""
    t0 = time.time()
    action, sky = job["action"], job.get("sky") or "day"
    sentence = f"Biscuit {action}" + (f", {job['extra']}" if job.get("extra") else "")
    rec = dict(started=time.strftime("%Y-%m-%dT%H:%M:%S"), sentence=sentence, sky=sky, source=job.get("source"),
               model=MODEL, effort=EFFORT)
    note = pr.ip_check(sentence)
    if note:
        rec.update(ok=False, error="refused: " + note, total_s=0.0)
        lib.log_gen(rec)
        if not quiet:
            say(paint(f"refused: {note}", "r"))
        return None
    system = SYSTEM_PROMPT.read_text(encoding="utf-8")
    user = (f"## Request\nclip: {sentence}\nstaging: {job.get('staging') or 'your choice: make the action obvious'}\n"
            f"sky: {sky}\nscope: public (original characters only)\n")
    work = Path(tempfile.mkdtemp(prefix="ib_"))
    rep: dict = dict(stages={})
    try:
        def gen_fn(extra: str = ""):
            return pr.call_claude(user + extra, conf, MODEL, EFFORT, system=system)
        t1 = time.time()
        res = pr.codegen(1, gen_fn, work, work / "clip.pova", conf, rep)
        t2 = time.time()
        if res is None:
            errs = [v for k, v in rep["stages"].items() if "error" in k]
            rec.update(ok=False, error=(rep.get("refused") or (errs[-1] if errs else "no script"))[-300:],
                       total_s=round(time.time() - t0, 1))
            lib.log_gen(rec)
            if not quiet:
                say(paint(f"failed: {sentence}: {rec['error'][:160]}", "r"))
            return None
        llm = res["llm"] or {}
        script = Path(res["script"])
        lines = len([ln for ln in script.read_text(encoding="utf-8").splitlines() if ln.strip()])
        pova, fit = fit_clip(script, work / "clip.pova", work, conf)
        t3 = time.time()
        anim = povanim.Animation.read(pova)
        val = povanim.validate(anim, mode="orbit")
        val_nos = dict(val, warnings=[w for w in val["warnings"] if "loop seam" not in w])  # orbit: seam is behind the column
        fixes = []
        if val_nos["warnings"]:
            anim, val2, fixes = pr.auto_fix(anim, val_nos, "orbit")
            val = dict(val2, warnings=val2["warnings"] + [w for w in val["warnings"] if "loop seam" in w])
        bpx = biscuit_pixels(anim)
        with lib.lock:                                        # id + files + index entry in one step (parallel workers)
            cid = lib.next_id()
            name = device_name(cid, action + ("_" + slug(job["extra"], 10) if job.get("extra") else "")
                               + ("" if sky == "day" else "_" + sky))
            anim.meta.update(name=name, prompt=sentence, series="infinite_biscuit", scope="public",
                             scope_reason="original character (Brian's own dog), filed in home: Brian decides what "
                                          "goes public", pipeline="infinite_biscuit.py via pov_request.py v0.2",
                             generator="claude -p (biscuit_kit)", model=llm.get("model"), sky=sky)
            final = home() / "clips" / f"{name}.pova"
            anim.write(final)
            shutil.copy(script, final.with_suffix(".py"))
            size = final.stat().st_size
            t4 = time.time()
            ok = size <= LIMIT and bpx >= 40
            rec.update(ok=ok, id=cid, name=name, file=str(final), bytes=size, frames=anim.n, fps=anim.fps,
                       script_lines=lines, llm_s=llm.get("seconds"), api_s=llm.get("api_s"), warm=llm.get("warm"),
                       output_tokens=(llm.get("usage") or {}).get("output_tokens"), cost_usd=llm.get("cost_usd"),
                       attempts=rep["stages"].get("render", {}).get("attempts"), codegen_s=round(t2 - t1, 2),
                       fit_s=round(t3 - t2, 2), file_s=round(t4 - t3, 2), playable_s=round(t4 - t0, 1),
                       total_s=round(t4 - t0, 1), fit=fit, fixes=fixes, warnings=val["warnings"],
                       peak_ma=val["current_peak_ma"], biscuit_px=bpx)
            if not ok:
                rec["error"] = "too big" if size > LIMIT else f"Biscuit barely visible ({bpx} px)"
            entry = dict(id=cid, key=variant_key(action, sky, job.get("extra", "")), action=action, sky=sky,
                         extra=job.get("extra", ""), sentence=sentence, name=name, file=str(final), bytes=size,
                         frames=anim.n, fps=anim.fps, loop_s=round(anim.duration_s, 3), created=rec["started"],
                         source=job.get("source"), status="ok" if ok else "bad", gen_s=rec["playable_s"],
                         llm_s=rec["llm_s"], warnings=val["warnings"], gb=anim.meta.get("gb"))
            lib.add(entry)
        lib.log_gen(rec)
        try:
            fastlane.contact_strip(final, final.with_suffix(".png"))
        except Exception:                                     # noqa: BLE001  (a preview must never sink a clip)
            pass
        if not quiet:
            say(paint(f"ready  #{cid:02d} {sentence}", "g", "b") + paint(
                f"  in {rec['playable_s']} s (Claude {rec['llm_s']} s, {lines} lines; render + fit {rec['fit_s'] + rec['codegen_s'] - (rec['llm_s'] or 0):.1f} s;"
                f" {anim.n} frames, {size / 1024:.1f} KB)", "dim"))
        return entry if ok else None
    except Exception as e:                                    # noqa: BLE001  (log and carry on: the gallery must not stop)
        rec.update(ok=False, error=f"{type(e).__name__}: {str(e)[-300:]}", total_s=round(time.time() - t0, 1))
        lib.log_gen(rec)
        if not quiet:
            say(paint(f"failed: {sentence}: {rec['error'][:160]}", "r"))
        return None
    finally:
        shutil.rmtree(work, ignore_errors=True)


def pending_jobs(lib: Library, remix: bool = True) -> list[dict]:
    """Table rows not generated yet (table order), then remixes (same action, another sky or accessory)."""
    jobs = [dict(r, source="table", extra="") for r in load_table() if not lib.has(variant_key(r["action"], r["sky"]))]
    if remix:
        rng = random.Random(len(lib.entries()))
        rows = load_table()
        rng.shuffle(rows)
        for r in rows:
            v = rng.choice(REMIX)
            if v["sky"] == r["sky"] and not v.get("extra"):
                continue
            j = dict(r, sky=v["sky"], extra=v.get("extra", ""), source="remix")
            if not lib.has(variant_key(j["action"], j["sky"], j["extra"])):
                jobs.append(j)
    return jobs


# ================================================================ the column
class Column:
    """Minimal REST client for the ESP32 (only our own clips are ever uploaded, played or deleted)."""

    def __init__(self, conf: dict, sim: bool = False):
        self.conf, self.sim = conf, sim
        self.base = conf["target"].rstrip("/")
        self.headers = {"X-POV-Token": conf.get("token", "")}

    def _req(self, method: str, path: str, timeout: float = 3.0, **kw):
        import requests
        return requests.request(method, self.base + path, headers=self.headers, timeout=timeout, **kw)

    def status(self) -> dict | None:
        if self.sim:
            return dict(sim=True, mode="anim", rpm=225.0, period_us=266667, valid=True, anim="", load={})
        try:
            r = self._req("GET", "/api/status", 2.5)
            return r.json() if r.ok else None
        except Exception:                                     # noqa: BLE001
            return None

    def anims(self) -> list[dict] | None:
        if self.sim:
            return []
        try:
            r = self._req("GET", "/api/anims", 3.0)
            return r.json() if r.ok else None
        except Exception:                                     # noqa: BLE001
            return None

    def upload(self, pova: Path) -> dict:
        if self.sim:
            return dict(upload=200, name=pova.stem, sim=True)
        return pr.upload_and_play(pova, self.conf, play=False)

    def play(self, name: str) -> bool:
        if self.sim:
            return True
        try:
            return self._req("POST", "/api/play", 4.0, json={"name": name}).ok
        except Exception:                                     # noqa: BLE001
            return False

    def delete(self, name: str) -> bool:
        if not name.startswith(PREFIX):                       # never anyone else's
            return False
        if self.sim:
            return True
        try:
            return self._req("DELETE", f"/api/anims?name={name}", 4.0).ok
        except Exception:                                     # noqa: BLE001
            return False


def ours(name: str | None) -> bool:
    return bool(name) and bool(re.match(rf"^{PREFIX}\d", name))


def device_loop_s(entry: dict, st: dict | None) -> float:
    """How long one loop really takes on the column: the firmware rounds each frame to whole 1/8-revolution ticks."""
    try:
        anim = povanim.Animation.read(entry["file"])
    except (OSError, ValueError):
        return float(entry.get("loop_s") or 8.0)
    rev_us = int((st or {}).get("period_us") or 0) or 266667
    tick_us = rev_us // povanim.K_PASSES
    fps_x10 = int(round(anim.fps * 10)) or 150
    frame_us = 10_000_000 // fps_x10
    ticks = max(1, (frame_us + tick_us // 2) // tick_us)
    return sum(h or 1 for h in anim.holds) * ticks * tick_us / 1e6


# ================================================================ the player (run)
class Runner:
    def __init__(self, a, conf: dict):
        self.a, self.conf = a, (dict(conf, target=a.target) if a.target else conf)
        self.h = home()
        self.lib = Library(self.h)
        self.col = Column(self.conf, sim=a.sim)
        self.fresh: collections.deque = collections.deque()   # newly generated, play next
        self.rotation_pos = 0
        self.played: list[int] = []
        self.uploaded: list[str] = []                         # our clips on the column, oldest first
        self.stop_ev = threading.Event()
        self.col_lock = threading.Lock()
        self.state: dict = dict(pid=os.getpid(), started=time.strftime("%Y-%m-%dT%H:%M:%S"), sim=a.sim, laps=a.laps,
                                live=a.live, playing=None, generated=0, failed=0, paused=None, column=None)
        self.prev: dict | None = None
        self.new_count = 0
        self.live_ids: set[int] = set()                       # generated during this run (they join the rotation)

    # ---- control files ----
    def flag(self, name: str) -> Path:
        return self.h / f"{name}.flag"

    def write_state(self, **kw) -> None:
        self.state.update(kw, heartbeat=time.time())
        tmp = self.h / "runner_state.tmp"
        tmp.write_text(json.dumps(self.state, indent=1), encoding="utf-8")
        os.replace(tmp, self.h / "runner_state.json")

    def wait(self, seconds: float) -> str | None:
        """Sleep, waking for stop / skip; returns 'stop', 'skip' or None."""
        end = time.time() + seconds / max(0.01, self.a.speed)          # --speed: a testing aid
        last = time.time()
        while time.time() < end:
            if self.flag("stop").exists() or self.stop_ev.is_set():
                return "stop"
            if self.flag("skip").exists():
                self.flag("skip").unlink(missing_ok=True)
                return "skip"
            if self.state.get("paused") and self.flag("takeover").exists():
                return "skip"
            time.sleep(0.2)
            if time.time() - last > 4:
                self.write_state()
                last = time.time()
        return None

    # ---- generation thread ----
    def generator(self) -> None:
        warm_pool(self.conf)
        idle_logged = False
        while not self.stop_ev.is_set():
            job = self.next_request()
            if job is None and (self.new_count >= self.a.max_new or len(self.fresh) >= 3):
                if not idle_logged and self.new_count >= self.a.max_new:
                    say(paint(f"live generation paused: {self.new_count} new clips this run (--max-new {self.a.max_new});"
                              " `add` requests still run", "dim"))
                    idle_logged = True
                self.stop_ev.wait(0.5)
                continue
            if job is None:
                todo = pending_jobs(self.lib)
                if not todo:
                    self.stop_ev.wait(5.0)
                    continue
                job = todo[0]
            say(paint(f"thinking  Biscuit {job['action']}" + (f", {job['extra']}" if job.get('extra') else "")
                      + (f" ({job['sky']})" if job.get('sky', 'day') != 'day' else "") + " ...", "c"))
            self.write_state(generating=f"Biscuit {job['action']}")
            e = generate(job, self.lib, self.conf)
            self.write_state(generating=None)
            if e:
                self.state["generated"] += 1
                self.live_ids.add(e["id"])
                self.new_count += 1 if job.get("source") != "add" else 0
                self.fresh.append(e) if job.get("source") != "add" else self.fresh.appendleft(e)
                if job.get("now"):
                    self.flag("skip").touch()
            else:
                self.state["failed"] += 1
                self.gap(20.0)                                # back off after a failure
            self.gap(self.a.gen_gap)

    def gap(self, seconds: float) -> None:
        """Wait between live generations, but start an `add` request at once."""
        end = time.time() + seconds
        while time.time() < end and not self.stop_ev.is_set():
            if any((self.h / "requests").glob("*.json")):
                return
            self.stop_ev.wait(0.3)

    def next_request(self) -> dict | None:
        reqs = sorted((self.h / "requests").glob("*.json"))
        for p in reqs:
            try:
                job = json.loads(p.read_text(encoding="utf-8"))
            except ValueError:
                job = None
            p.unlink(missing_ok=True)
            if job:
                job["source"] = "add"
                return job
        return None

    # ---- playlist ----
    def rotation(self) -> list[dict]:
        pl = self.lib.ordered()
        if self.a.only:
            pl = [e for e in pl if e["id"] in self.a.only]
        elif self.a.featured:
            feat = set(self.lib.playlist())
            pl = [e for e in pl if e["id"] in feat or e.get("source") in ("add", "remix") or e["id"] in self.live_ids] or pl
        return pl

    def next_clip(self) -> dict | None:
        if self.fresh:
            return self.fresh.popleft()
        pl = self.rotation()
        if not pl:
            return None
        if self.a.shuffle:
            recent = set(self.played[-max(1, len(pl) // 2):])
            choices = [e for e in pl if e["id"] not in recent] or pl
            return random.choice(choices)
        last = self.played[-1] if self.played else None
        for _ in range(len(pl)):
            e = pl[self.rotation_pos % len(pl)]
            self.rotation_pos += 1
            if e["id"] != last or len(pl) == 1:
                return e
        return pl[0]

    # ---- column helpers ----
    def ensure_on_column(self, e: dict) -> bool:
        with self.col_lock:                                   # the peek upload runs in a thread: one at a time
            return self._ensure_on_column(e)

    def _ensure_on_column(self, e: dict) -> bool:
        if e["name"] in self.uploaded:
            return True
        st = self.col.status()
        free = ((st or {}).get("diag") or {}).get("fs_free")
        need = e["bytes"] + 8192
        while free is not None and free < need and len(self.uploaded) > 1:
            old = self.uploaded.pop(0)
            if old != (self.state.get("playing") or {}).get("name"):
                self.col.delete(old)
                free += next((x["bytes"] for x in self.lib.entries() if x["name"] == old), 60000)
            else:
                self.uploaded.append(old)
                break
        r = self.col.upload(Path(e["file"]))
        if r.get("error"):
            say(paint(f"upload failed for {e['name']}: {r['error']}", "r"))
            return False
        self.uploaded.append(e["name"])
        while len(self.uploaded) > self.a.window:            # keep at most `window` of ours on the column
            old = self.uploaded.pop(0)
            if old in (e["name"], (self.state.get("playing") or {}).get("name")):
                self.uploaded.insert(0, old)
                break
            self.col.delete(old)
        return True

    def foreign(self, st: dict | None) -> str | None:
        """Someone else's animation / mode on the column, or someone stopped it (we never fight over the column)."""
        if not st or st.get("sim"):
            return None
        mode, ld = st.get("mode"), (st.get("load") or {})
        if mode == "anim":
            name = st.get("anim") or ""
            if ours(name) or (ld.get("state") in ("queued", "loading") and ours(ld.get("name"))):
                return None
            return name or ld.get("name") or "another animation"
        if mode == "off":
            if ld.get("state") == "error" and ours(ld.get("name")):
                return None                                   # our own clip failed to load: just move on
            return "nothing (someone stopped the column)"
        return f"{mode} mode"

    # ---- main loop ----
    def run(self) -> int:
        a = self.a
        for f in ("stop", "skip"):
            self.flag(f).unlink(missing_ok=True)
        self.write_state()
        banner = ("INFINITE BISCUIT: Biscuit walks round the column; every " + str(a.laps) +
                  " laps the AI gives him something new to do")
        print(paint(banner, "b", "y"), flush=True)
        print(paint(f"library: {len(self.lib.playable())} clips | live generation: {'on' if a.live else 'off'} | "
                    f"column: {'SIMULATED' if a.sim else self.conf['target']} | stop: infinite_biscuit.py stop", "dim"),
              flush=True)
        st = self.col.status()
        if st is None:
            say(paint(f"column not answering at {self.conf['target']}: generating anyway, playing as soon as it is up", "y"))
        else:
            name = (st.get("load") or {}).get("name") or st.get("anim")
            self.prev = dict(mode=st.get("mode"), file=name, anim=st.get("anim"))
            if not st.get("sim") and st.get("mode") not in TAKEOVER_ANIM and not ours(name):
                say(paint(f"taking over the column from '{name or st.get('mode')}' (restored on stop)", "y"))
            self.write_state(prev=self.prev)
            playing_now = st.get("anim") or ""
            for x in (self.col.anims() or []):                # our leftovers from an earlier run free the space
                n = x.get("name") or ""
                if ours(n) and n != playing_now:
                    self.col.delete(n)
        gen_thread = None
        if a.live:
            gen_thread = threading.Thread(target=self.generator, daemon=True)
            gen_thread.start()
        rc = 0
        try:
            rc = self.loop()
        except KeyboardInterrupt:
            rc = 0
        finally:
            self.stop_ev.set()
            self.cleanup()
            close_pool()
        return rc

    def loop(self) -> int:
        a = self.a
        current = None
        offline_since = None
        while True:
            if self.flag("stop").exists():
                return 0
            e = self.next_clip()
            if e is None:
                if not a.live:
                    say(paint("library is empty: run `infinite_biscuit.py pregen 18` first (or start with --live)", "r"))
                    return 2
                self.write_state(playing=None, waiting="first clip")
                if self.wait(1.0) == "stop":
                    return 0
                continue
            st = self.col.status()
            if st is None:
                if offline_since is None:
                    offline_since = time.time()
                    say(paint("column offline: waiting (generation continues)", "y"))
                self.fresh.appendleft(e)
                self.write_state(column="offline")
                if self.wait(5.0) == "stop":
                    return 0
                continue
            if offline_since is not None:
                say(paint(f"column back online after {time.time() - offline_since:.0f} s", "g"))
                offline_since = None
            other = self.foreign(st) if current is not None else None
            if other and self.flag("takeover").exists():
                self.flag("takeover").unlink(missing_ok=True)
                say(paint(f"taking the column back from '{other}'", "y"))
                other = None
            if other:
                if self.state.get("paused") != other:
                    say(paint(f"paused: the column is showing '{other}' (someone else); `start` takes it back", "y"))
                self.write_state(paused=other)
                self.fresh.appendleft(e)
                if self.wait(5.0) == "stop":
                    return 0
                continue
            if self.state.get("paused"):
                self.write_state(paused=None)
            if not self.ensure_on_column(e):
                if self.wait(3.0) == "stop":
                    return 0
                continue
            if not self.col.play(e["name"]):
                say(paint(f"play failed for {e['name']}", "r"))
                if self.wait(3.0) == "stop":
                    return 0
                continue
            current = e
            self.played.append(e["id"])
            loop_s = device_loop_s(e, st)
            dur = a.laps * loop_s
            rpm = st.get("rpm")
            self.write_state(playing=dict(id=e["id"], name=e["name"], sentence=e["sentence"], since=time.time(),
                                          until=time.time() + dur, loop_s=round(loop_s, 2)),
                             column=dict(rpm=round(rpm, 1) if rpm else None), waiting=None)
            say(paint(f"now    #{e['id']:02d} {e['sentence']}", "m", "b") +
                paint(f"  ({a.laps} laps, {dur:.1f} s{', gen ' + str(e.get('gen_s')) + ' s' if e.get('gen_s') else ''})", "dim"))
            peek = self.peek()
            if peek is not None:                              # upload the next one while this one plays
                threading.Thread(target=self.ensure_on_column, args=(peek,), daemon=True).start()
            why = self.wait(dur)
            if why == "stop":
                return 0

    def peek(self) -> dict | None:
        if self.fresh:
            return self.fresh[0]
        pl = self.rotation()
        if not pl or self.a.shuffle:
            return None
        return pl[self.rotation_pos % len(pl)]

    def cleanup(self) -> None:
        """Stop: restore what the column showed before (if it is still there), delete our other clips."""
        playing = (self.state.get("playing") or {}).get("name")
        keep = playing
        st = self.col.status() if not self.a.sim else None
        if self.prev and not self.a.keep and st is not None:
            pf = self.prev.get("file")
            if self.prev.get("mode") == "anim" and pf and not ours(pf):
                names = {x.get("name") for x in (self.col.anims() or [])}
                if pf in names and self.foreign(st) is None and self.col.play(pf):
                    say(paint(f"restored '{pf}' on the column", "g"))
                    keep = None
            elif self.prev.get("mode") == "off" and self.foreign(st) is None:
                pass                                          # it was off: leave Biscuit on (nicer than black)
        if st is not None:
            for n in [x.get("name") for x in (self.col.anims() or []) if ours(x.get("name"))]:
                if n != keep:
                    self.col.delete(n)
        self.write_state(stopped=time.strftime("%Y-%m-%dT%H:%M:%S"), playing=None if keep is None else self.state.get("playing"))
        say(paint("stopped", "b"))


# ================================================================ commands
def pid_alive(pid: int) -> bool:
    if not pid:
        return False
    if os.name == "nt":
        import ctypes
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))   # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong()
        ok = ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(h)
        return bool(ok) and code.value == 259                              # STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def read_state() -> dict:
    p = home() / "runner_state.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def running() -> dict | None:
    s = read_state()
    if s and not s.get("stopped") and pid_alive(s.get("pid", 0)):
        return s
    return None


def cmd_start(a) -> int:
    s = running()
    if s:
        if s.get("paused"):
            (home() / "takeover.flag").touch()
        print(f"already running (pid {s['pid']}), playing: {(s.get('playing') or {}).get('sentence')}")
        return 0
    lib = Library(home())
    if not lib.playable() and not a.live:
        print("library is empty: run `infinite_biscuit.py pregen 18` first")
        return 2
    args = [sys.executable, "-X", "utf8", str(Path(__file__).resolve()), "run", "--laps", str(a.laps),
            "--max-new", str(a.max_new), "--gen-gap", str(a.gen_gap)]
    if not a.live:
        args.append("--no-live")
    if a.sim:
        args.append("--sim")
    if a.shuffle:
        args.append("--shuffle")
    if a.featured:
        args.append("--featured")
    if a.target:
        args += ["--target", a.target]
    wt = shutil.which("wt.exe") or shutil.which("wt")
    if wt and not a.hidden:
        subprocess.Popen([wt, "-w", "0", "nt", "--title", "Infinite Biscuit", "-d", str(HERE)] + args,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        where = "a new Windows Terminal tab 'Infinite Biscuit'"
    else:
        log = open(home() / "run.log", "a", encoding="utf-8")
        flags = 0
        if os.name == "nt":
            flags = 0x00000008 | 0x00000200                                # DETACHED_PROCESS | NEW_PROCESS_GROUP
            try:
                subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                 creationflags=flags | 0x01000000, close_fds=True)   # + BREAKAWAY_FROM_JOB
            except OSError:
                subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                 creationflags=flags, close_fds=True)
        else:
            subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        where = f"the background (log: {home() / 'run.log'})"
    for _ in range(40):
        time.sleep(0.25)
        s = running()
        if s:
            print(f"Infinite Biscuit started in {where}, pid {s['pid']}. Stop: py {Path(__file__).name} stop")
            return 0
    print(f"launched in {where}; it has not reported in yet (check that tab / run.log)")
    return 0


def cmd_stop(a) -> int:
    s = running()
    if not s:
        print("not running")
        return 0
    flag = home() / "stop.flag"
    flag.touch()
    for _ in range(60):
        time.sleep(0.25)
        if not pid_alive(s["pid"]):
            break
    if pid_alive(s["pid"]):
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(s["pid"]), "/T", "/F"], capture_output=True)
        print(f"stopped (forced, pid {s['pid']})")
    else:
        print("stopped")
    flag.unlink(missing_ok=True)
    return 0


def cmd_next(a) -> int:
    if not running():
        print("not running")
        return 1
    (home() / "skip.flag").touch()
    print("skipping to the next clip")
    return 0


def cmd_add(a) -> int:
    action = clean_action(" ".join(a.sentence))
    if not action:
        print("say what Biscuit does, e.g. add \"rides a dinosaur\"")
        return 2
    job = dict(action=action, staging=a.staging or "", sky=a.sky, extra="", now=a.now)
    if running():
        p = home() / "requests" / f"{time.strftime('%Y%m%d-%H%M%S')}_{slug(action, 30)}.json"
        p.write_text(json.dumps(job), encoding="utf-8")
        print(f"queued: Biscuit {action} (generating now, plays {'immediately' if a.now else 'next'})")
        return 0
    lib = Library(home())
    e = generate(dict(job, source="add"), lib, pr.load_conf())
    return 0 if e else 1


def cmd_pregen(a) -> int:
    conf = pr.load_conf()
    lib = Library(home())
    jobs = pending_jobs(lib, remix=a.remix)
    if a.ids:
        jobs = [j for j in jobs if j.get("id") in a.ids]
    jobs = jobs[:a.n]
    if not jobs:
        print("nothing to generate (every table row is cached; use --remix for variants)")
        return 0
    say(f"generating {len(jobs)} clips with {a.workers} worker(s) ({MODEL}, effort {EFFORT})")
    warm_pool(conf)
    t0 = time.time()
    ok = 0
    try:
        if a.workers <= 1:
            for j in jobs:
                say(paint(f"thinking  Biscuit {j['action']} ({j['sky']}) ...", "c"))
                ok += generate(j, lib, conf) is not None
        else:
            import concurrent.futures as cf
            with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
                for res in ex.map(lambda j: generate(j, lib, conf), jobs):
                    ok += res is not None
    finally:
        close_pool()
    say(f"done: {ok}/{len(jobs)} clips in {time.time() - t0:.0f} s")
    return 0 if ok else 1


def gen_stats(lib: Library) -> dict:
    recs = [r for r in lib.gen_records() if r.get("ok")]
    if not recs:
        return {}

    def summ(key):
        v = [r[key] for r in recs if isinstance(r.get(key), (int, float))]
        if not v:
            return None
        return dict(median=round(statistics.median(v), 1), min=round(min(v), 1), max=round(max(v), 1), n=len(v))
    allr = lib.gen_records()
    return dict(ok=len(recs), failed=len([r for r in allr if not r.get("ok")]), playable_s=summ("playable_s"),
                llm_s=summ("llm_s"), fit_s=summ("fit_s"), script_lines=summ("script_lines"),
                kb=summ("bytes") and {k: (round(v / 1024, 1) if k != "n" else v) for k, v in summ("bytes").items()},
                frames=summ("frames"))


def cmd_stats(a) -> int:
    lib = Library(home())
    s = gen_stats(lib)
    if not s:
        print("no generations logged yet")
        return 0
    if a.md:
        print("| # | Sentence | Sentence to playable file (s) | Claude (s) | Script lines | Frames | KB |")
        print("|---|---|---|---|---|---|---|")
        for r in lib.gen_records():
            if r.get("ok"):
                print(f"| {r['id']} | {r['sentence']} | {r['playable_s']} | {r['llm_s']} | {r['script_lines']} | "
                      f"{r['frames']} | {r['bytes'] / 1024:.1f} |")
        print()
    p = s["playable_s"]
    print(f"{s['ok']} clips generated ({s['failed']} failed attempts). Sentence to playable file: median {p['median']} s "
          f"(range {p['min']}-{p['max']} s); Claude's part median {s['llm_s']['median']} s; scripts median "
          f"{s['script_lines']['median']} lines; files median {s['kb']['median']} KB.")
    if a.json:
        print(json.dumps(s, indent=1))
    return 0


def cmd_status(a) -> int:
    s = read_state()
    alive = running()
    lib = Library(home())
    pl = lib.playable()
    print(f"runner: {'RUNNING pid ' + str(s.get('pid')) if alive else 'not running'}")
    if alive:
        p = s.get("playing") or {}
        if p:
            left = max(0, p.get("until", 0) - time.time())
            print(f"playing: #{p.get('id')} {p.get('sentence')} ({left:.0f} s left)")
        for k in ("generating", "paused", "waiting"):
            if s.get(k):
                print(f"{k}: {s[k]}")
        print(f"generated this run: {s.get('generated', 0)}, failed: {s.get('failed', 0)}")
    print(f"library: {len(pl)} playable clips in {home() / 'clips'}")
    st = gen_stats(lib)
    if st:
        print(f"generation: median {st['playable_s']['median']} s (range {st['playable_s']['min']}-{st['playable_s']['max']} s), "
              f"Claude median {st['llm_s']['median']} s")
    return 0


def cmd_list(a) -> int:
    for e in sorted(Library(home()).entries(), key=lambda e: e["id"]):
        print(f"#{e['id']:02d} {e['status']:4} {e['sentence'][:46]:46} {e['sky']:6} {e['frames']:3} fr "
              f"{e['bytes'] / 1024:5.1f} KB  gen {e.get('gen_s')} s  {e['name']}")
    return 0


def cmd_playlist(a) -> int:
    lib = Library(home())
    if a.ids:
        known = {e["id"] for e in lib.entries()}
        bad = [i for i in a.ids if i not in known]
        if bad:
            print(f"no such clips: {bad}")
            return 2
        (home() / "playlist.json").write_text(json.dumps(a.ids), encoding="utf-8")
    by = {e["id"]: e for e in lib.entries()}
    order = lib.ordered()
    feat = set(lib.playlist())
    for i, e in enumerate(order, 1):
        print(f"{i:2d}. #{e['id']:02d} {e['sentence']}{'' if e['sky'] == 'day' else ' (' + e['sky'] + ')'}"
              f"{'' if e['id'] in feat else '   [after the featured list]'}")
    dropped = [by[i]["sentence"] for i in by if by[i]["status"] != "ok"]
    if dropped:
        print(f"not played: {', '.join(dropped)}")
    return 0


def cmd_drop(a, status: str) -> int:
    lib = Library(home())
    for cid in a.ids:
        print(f"#{cid}: {'ok' if lib.set_status(cid, status) else 'no such clip'}")
    return 0


def cmd_review(a) -> int:
    """One sheet: each clip at t = 0.4 / 0.5 / 0.6 (Biscuit passing the viewer), labelled."""
    import numpy as np
    from PIL import Image, ImageDraw
    lib = Library(home())
    es = sorted([e for e in lib.entries() if Path(e["file"]).exists() and (a.all or e["status"] == "ok")],
                key=lambda e: e["id"])
    if a.ids:
        es = [e for e in es if e["id"] in a.ids]
    if not es:
        print("nothing to review")
        return 0
    s, c0, c1 = 3, 12, 84
    w, h = (c1 - c0) * s, povanim.ROWS * s
    tiles = []
    for e in es:
        anim = povanim.Animation.read(e["file"])
        row = []
        for frac in (0.4, 0.5, 0.6):
            rgb = anim.rgb(int(frac * anim.n) % anim.n)[::-1, c0:c1]
            big = np.kron(rgb, np.ones((s, s, 1), dtype=np.uint8))
            row.append(Image.fromarray(big.astype("uint8")))
        tiles.append((e, row))
    per = 2
    W = per * (3 * w + 2 * 4 + 16)
    H = ((len(tiles) + per - 1) // per) * (h + 20)
    sheet = Image.new("RGB", (W, H), (28, 28, 34))
    d = ImageDraw.Draw(sheet)
    for i, (e, row) in enumerate(tiles):
        x0, y0 = (i % per) * (3 * w + 8 + 16), (i // per) * (h + 20)
        for j, im in enumerate(row):
            sheet.paste(im, (x0 + j * (w + 4), y0 + 18))
        d.text((x0 + 2, y0 + 3), f"#{e['id']} {e['sentence']}  [{e['sky']}, {e['frames']} fr, {e['bytes'] / 1024:.0f} KB, "
                                 f"gen {e.get('gen_s')} s]{'' if e['status'] == 'ok' else '  (' + e['status'] + ')'}",
               fill=(235, 235, 235))
    out = Path(a.out) if a.out else home() / "review.png"
    sheet.save(out)
    print(out)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def player_args(p):
        p.add_argument("--laps", type=int, default=2, help="laps per clip (default 2)")
        p.add_argument("--no-live", dest="live", action="store_false", help="only play the cached library")
        p.add_argument("--max-new", type=int, default=25, help="new clips the live generator makes per run (default 25)")
        p.add_argument("--gen-gap", type=float, default=8.0, help="seconds between live generations (default 8)")
        p.add_argument("--sim", action="store_true", help="no column: print the schedule (and --speed it up)")
        p.add_argument("--shuffle", action="store_true", help="random order (no repeats within half the playlist)")
        p.add_argument("--featured", action="store_true", help="only the curated playlist (+ clips made this run)")
        p.add_argument("--target", default=None, help="column URL (default: pov_config.json target), e.g. a mock")
    p = sub.add_parser("start", help="start the gallery in its own terminal tab (Main's one-liner)")
    player_args(p)
    p.add_argument("--hidden", action="store_true", help="background process instead of a terminal tab")
    p = sub.add_parser("run", help="the gallery in the foreground (what start launches)")
    player_args(p)
    p.add_argument("--speed", type=float, default=1.0, help="testing: run the clock this many times faster")
    p.add_argument("--window", type=int, default=3, help="our clips kept on the column at once (default 3)")
    p.add_argument("--keep", action="store_true", help="on stop, leave Biscuit playing instead of restoring")
    p.add_argument("--only", type=int, nargs="*", help="play only these clip ids")
    sub.add_parser("stop", help="stop the gallery (restores what the column showed before)")
    sub.add_parser("next", help="skip to the next clip now")
    p = sub.add_parser("add", help='generate a new sentence and play it next: add "rides a dinosaur"')
    p.add_argument("sentence", nargs="+")
    p.add_argument("--staging", default="")
    p.add_argument("--sky", default="day", choices=SKIES)
    p.add_argument("--now", action="store_true", help="cut to it as soon as it is ready")
    p = sub.add_parser("pregen", help="generate N clips for the cache")
    p.add_argument("n", type=int, nargs="?", default=18)
    p.add_argument("--workers", type=int, default=2)
    p.add_argument("--remix", action="store_true", help="also make variants once the table is done")
    p.add_argument("--ids", type=int, nargs="*", help="only these table ids")
    sub.add_parser("status")
    p = sub.add_parser("stats", help="generation timings")
    p.add_argument("--md", action="store_true", help="also print a markdown table of every clip")
    p.add_argument("--json", action="store_true")
    sub.add_parser("list")
    p = sub.add_parser("drop", help="take clips out of the playlist")
    p.add_argument("ids", type=int, nargs="+")
    p = sub.add_parser("undrop", help="put clips back in the playlist")
    p.add_argument("ids", type=int, nargs="+")
    p = sub.add_parser("playlist", help="show, or set, the curated running order: playlist 14 2 10 4 ...")
    p.add_argument("ids", type=int, nargs="*")
    p = sub.add_parser("review", help="PNG sheet of the clips for curation")
    p.add_argument("--out", default=None)
    p.add_argument("--all", action="store_true", help="include dropped / bad clips")
    p.add_argument("--ids", type=int, nargs="*")
    a = ap.parse_args(argv)
    if a.cmd == "run":
        if running():
            print("already running")
            return 1
        return Runner(a, pr.load_conf()).run()
    return {"start": cmd_start, "stop": cmd_stop, "next": cmd_next, "add": cmd_add, "pregen": cmd_pregen,
            "status": cmd_status, "stats": cmd_stats, "list": cmd_list, "review": cmd_review, "playlist": cmd_playlist,
            "drop": lambda x: cmd_drop(x, "drop"), "undrop": lambda x: cmd_drop(x, "ok")}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
