"""Warm POV request server + live step view (2026-11-07 prototype; live-demo build 2026-11-23).

    py software/pipeline/pov_serve.py --shoot          # the cold open: warm lanes, F9 watcher, step view window
    shoot.cmd                                          # the same, double-clickable (software/pipeline/shoot.cmd)
    py software/pipeline/pov_serve.py                  # plain daemon on http://127.0.0.1:8790 (POST /pov)
    py software/pipeline/pov_serve.py --demo "a goose skateboarding" --args "--dry-run --no-preview"

It keeps one pre-spawned `claude` ready per lane (the CLI's ~1 s start-up is paid before the request), runs
pov_request.py's pipeline in-process and publishes every stage as it happens to the step view (GET / -> stepview.html,
GET /events = server-sent events), which OBS captures for the split screen.

With --f9 the daemon reads Brian's F9 transcripts from the Brain-Dump-Button inbox itself, read-only: it never claims,
moves or types anything (the panel's voice router still delivers every line to Main as usual). It sees the clip the
moment F9 is released (ptt.py writes last_clip-<host>.wav before Whisper starts), shows "transcribing" and, in --f9 all
mode, starts the column's thinking dots; the transcript then becomes the request. While it runs it writes
%LOCALAPPDATA%\\POVColumn\\shoot_mode.json so Main can tell the line is already being handled.

HTTP: POST /pov {"prompt", "args"?, "async"?} | POST /reset {"stop"?} | POST /replay {"run"?} | GET /state | GET /runs
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import queue
import re
import shlex
import shutil
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pov_request as pr  # noqa: E402

LOCAL = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "POVColumn"
SHOOT_DIR = LOCAL / "shoot"
RUNS_DIR = SHOOT_DIR / "runs"
SHOOT_FLAG = LOCAL / "shoot_mode.json"
INBOX = HERE.parents[2] / "Brain-Dump-Button" / "inbox"
HOST = socket.gethostname().lower()
VOICE_RE = re.compile(r"^(?P<stamp>\d{8}-\d{6})-(?P<host>[a-z0-9]+)\.txt$")     # F9 clips only (no panel/relay/phone)
TRIGGER_RE = re.compile(r"^\s*(?:hey\s+)?(?:p[.\-]?\s?o[.\-]?\s?v\b\.?|(?:the\s+)?column\b)[\s,.:;!-]*", re.I)
ADDRESSED_RE = re.compile(r"^\s*(main|[a-z]+(?:\s+[a-z]+)?\s+agent)\b\s*[,:]", re.I)   # "Main, ..." / "Fusion agent, ..."
PRESET = "--fast"
SHOOT_ARGS = ["--scope", "public", "--no-cache", "--placeholder-kind", "thinking", "--no-preview", "--wait-playing"]


def start_pool(conf: dict, fast: dict, template_lane: bool = True) -> pr.WarmPool:
    pool = pr.WarmPool(conf)
    if template_lane:
        pool.prewarm(pr.TEMPLATE_MODEL, "low", (HERE / "prompts" / "template_spec.md").read_text(encoding="utf-8"))
    system, _ = pr.build_prompts("x", "public", fast["variant"])
    pool.prewarm(fast["model"], fast["effort"], system)
    pr._POOL = pool
    if pr._RENDER_POOL is None:                           # the sandbox interpreter, pre-started too (~0.2 s a take)
        pr._RENDER_POOL = pr.RenderPool()
    return pool


LAST_LLM = {"at": 0.0}


def prime(conf: dict, preset: dict) -> None:
    """One throwaway call with the generator's system prompt, outside the warm pool, so the prompt sits in the API's
    prompt cache (1 h) before the first take: measured 11-23, a cache-cold first token took 1.7-2.6 s, a cached one
    0.85 s. Re-run by refresh_forever after 50 idle minutes."""
    system, _ = pr.build_prompts("x", "public", preset["variant"])
    try:
        _, info = pr.call_claude("Reply with the single word OK (cache warm-up, not a scene request).", conf,
                                 preset["model"], preset.get("effort"), system=system, use_pool=False)
        LAST_LLM["at"] = time.time()
        print(f"  prompt cache primed ({info.get('seconds')} s)", flush=True)
    except RuntimeError as e:
        print(f"  prompt cache priming failed: {str(e)[-200:]}", flush=True)


# ---------------------------------------------------------------- events -> step view
class Hub:
    """Fans pipeline events out to every connected step view (server-sent events) and keeps the current run, so a page
    opened mid-run catches up. Each finished run is saved as JSONL in RUNS_DIR for replay (re-record the split screen
    later from a real take's exact timings)."""

    def __init__(self):
        self.lock = threading.Lock()
        self.subs: list[queue.Queue] = []
        self.run: list[dict] = []
        self.run_id: str | None = None
        self.info: dict = {}

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue()
        with self.lock:
            self.subs.append(q)
            q.put(dict(stage="hello", state="done", at=time.time(), info=self.info, snapshot=list(self.run)))
        return q

    def unsubscribe(self, q) -> None:
        with self.lock:
            if q in self.subs:
                self.subs.remove(q)

    def publish(self, ev: dict) -> None:
        ev = {k: v for k, v in ev.items() if v is not None}
        ev.setdefault("at", time.time())
        with self.lock:
            if ev.get("stage") == "heard" and ev.get("state") in ("start", "done"):
                last = self.run[-1] if self.run else {}
                if ev["state"] == "done" and last.get("stage") == "heard" and last.get("state") == "start":
                    ev["continues"] = True                    # F9: "transcribing" -> the words, one run
                    self.run_id = ev.get("run") or self.run_id
                elif not self.run or last.get("stage") in ("done", "reset") or ev.get("new_run"):
                    self.run, self.run_id = [], ev.get("run") or time.strftime("%Y%m%d-%H%M%S")
            if ev.get("stage") == "reset":
                self.run, self.run_id = [], None
            ev["run"] = self.run_id
            if ev.get("stage") not in ("reset", "column"):
                self.run.append(ev)
            subs = list(self.subs)
        for q in subs:
            q.put(ev)
        if ev.get("stage") == "done" and self.run_id:
            self.save()

    def save(self) -> None:
        try:
            RUNS_DIR.mkdir(parents=True, exist_ok=True)
            with self.lock:
                rid, evs = self.run_id, list(self.run)
            (RUNS_DIR / f"{rid}.jsonl").write_text("\n".join(json.dumps(e) for e in evs) + "\n", encoding="utf-8")
        except OSError:
            pass


HUB = Hub()


# ---------------------------------------------------------------- the pipeline, one request at a time
def handle(prompt: str, args: list[str]) -> dict:
    """Run the pipeline in-process (preset + args); returns the stage report. Events go to HUB."""
    fd, name = pr.tempfile.mkstemp(prefix="pov_rep_", suffix=".json")
    pr.os.close(fd)
    rep_file = Path(name)
    buf = io.StringIO()
    pr.EVENT_SINK = HUB.publish
    try:
        with contextlib.redirect_stdout(buf):
            code = pr.main([prompt, PRESET, "--report", str(rep_file)] + args)
    except Exception as e:                                   # never take the daemon down with one bad request
        HUB.publish(dict(stage="done", state="error", error=f"{type(e).__name__}: {e}", code=99))
        code = 99
    finally:
        pr.EVENT_SINK = None
    rep = json.loads(rep_file.read_text(encoding="utf-8")) if rep_file.stat().st_size else dict(exit=code)
    rep_file.unlink(missing_ok=True)
    return rep


class Runner:
    """A queue of requests served by one worker thread: the pipeline keeps module state (pool, event sink), so requests
    run one after another. A request arriving mid-run waits; a duplicate of the running prompt is dropped."""

    def __init__(self, extra_args: list[str], out_root: Path | None, column):
        self.q: queue.Queue = queue.Queue()
        self.extra_args, self.out_root, self.column = extra_args, out_root, column
        self.busy_prompt: str | None = None
        self.last: dict = {}
        self.recent: dict[str, float] = {}             # F9 prompt -> when it finished (drops Main re-posting it)
        threading.Thread(target=self.work, daemon=True).start()

    def submit(self, prompt: str, source: str = "http", heard: dict | None = None, args: list[str] | None = None,
               wait: bool = False) -> dict | None:
        prompt = " ".join(str(prompt).split())
        if not prompt:
            return dict(error="empty prompt")
        if self.busy_prompt and prompt.lower() == self.busy_prompt.lower():
            return dict(dropped="duplicate of the running request")
        if source == "http" and time.time() - self.recent.get(prompt.lower(), 0) < 90:
            return dict(dropped="the same request finished less than 90 s ago (F9 already handled it)")
        done = threading.Event() if wait else None
        box: dict = {}
        self.q.put((prompt, source, heard or {}, args or [], done, box))
        if done:
            done.wait()
            return box.get("rep")
        return dict(queued=prompt, position=self.q.qsize())

    def work(self):
        while True:
            prompt, source, heard, args, done, box = self.q.get()
            self.busy_prompt = prompt
            try:
                HUB.publish(dict(stage="heard", state="done", text=prompt, source=source, new_run=True,
                                 run=time.strftime("%Y%m%d-%H%M%S_") + pr.slugify(prompt)[:40], **heard))
                run_args = list(self.extra_args) + list(args)
                if self.out_root is not None and "--out-dir" not in run_args:
                    run_args += ["--out-dir", str(self.out_root / time.strftime("%Y-%m-%d") / time.strftime("%H%M%S"))]
                if self.column.thinking_on_board and "--thinking-on-board" not in run_args:
                    run_args.append("--thinking-on-board")
                if heard.get("early_thinking") and "--no-placeholder" not in run_args:
                    run_args.append("--no-placeholder")       # the dots went up when F9 was released
                rep = handle(prompt, run_args)
                LAST_LLM["at"] = time.time()
                self.last = dict(prompt=prompt, exit=rep.get("exit"), total_s=rep.get("total_s"),
                                 playing_s=rep.get("playing_s"), file=rep.get("file"), error=rep.get("error"))
                box["rep"] = rep
            finally:
                if source == "F9":                        # Main may get the same line from the router and POST it
                    self.recent[prompt.lower()] = time.time()
                self.busy_prompt = None
                if done:
                    done.set()


# ---------------------------------------------------------------- the column (or the mock)
class Column:
    """Polls GET /api/status every few seconds for the step view's header, and stores the thinking-dots loop on the
    board once whenever it comes online (then a request only sends /api/play for it)."""

    def __init__(self, conf: dict, store_thinking: bool):
        self.conf, self.store_thinking = conf, store_thinking
        self.status: dict | None = None
        self.thinking_on_board = False
        self.mock = bool(re.search(r"//(127\.0\.0\.1|localhost)[:/]", conf["target"] + "/"))
        threading.Thread(target=self.poll, daemon=True).start()

    def poll(self):
        while True:
            st = pr.column_status(self.conf, timeout=1.5)
            was_online, self.status = self.status is not None, st
            if st is not None and not was_online:
                HUB.info.update(column=self.summary())
                if self.store_thinking:
                    r = pr.ensure_on_board(pr.thinking_anim(), pr.THINKING_NAME, self.conf)
                    self.thinking_on_board = r.get("stored") in ("already", 200)
            if st is None:
                self.thinking_on_board = False
            summ = self.summary()
            if summ != HUB.info.get("column"):
                HUB.info.update(column=summ)
                HUB.publish(dict(stage="column", state="done", column=summ))
            time.sleep(4.0)

    def summary(self) -> dict:
        st = self.status or {}
        return dict(target=self.conf["target"], online=self.status is not None, mock=self.mock,
                    rpm=5 * round((st.get("rpm") or 0) / 5), anim=st.get("anim"), fw=st.get("fw"),
                    gb_used=st.get("gb_used"))

    def play_thinking(self) -> None:
        if self.thinking_on_board:
            threading.Thread(target=pr.play_only, args=(pr.THINKING_NAME, self.conf), daemon=True).start()

    def stop(self) -> dict:
        import requests
        try:
            r = requests.post(f"{self.conf['target'].rstrip('/')}/api/stop",
                              headers={"X-POV-Token": self.conf.get("token", "")}, timeout=3)
            return dict(stop=r.status_code)
        except requests.RequestException as e:
            return dict(error=type(e).__name__)


# ---------------------------------------------------------------- F9 lines, read-only
class F9Watcher:
    """Reads new F9 transcripts from the Brain-Dump-Button inbox without claiming them. mode "all": every F9 line is a
    request (except "Main, ..." / "<name> agent, ..." lines and long ones); "prefix": only lines that start with
    "POV" or "Column" (the word is dropped)."""

    def __init__(self, runner: Runner, column: Column, mode: str, inbox: Path, host: str, early_thinking: bool):
        self.runner, self.column, self.mode, self.inbox, self.host = runner, column, mode, inbox, host
        self.early_thinking = early_thinking and mode == "all"
        self.seen = {p.name for p in inbox.glob(f"*-{host}.txt")} if inbox.exists() else set()
        self.wav = inbox / f"last_clip-{host}.wav"
        self.wav_mtime = self._mtime(self.wav)
        self.release: dict | None = None
        threading.Thread(target=self.watch, daemon=True).start()

    @staticmethod
    def _mtime(p: Path) -> float:
        try:
            return p.stat().st_mtime
        except OSError:
            return 0.0

    def watch(self):
        while True:
            try:
                self.tick()
            except Exception:
                pass
            time.sleep(0.05)

    def tick(self):
        if self.release and time.time() - self.release["at"] > 20:   # Whisper heard nothing (no transcript came)
            self.undo_dots(self.release)
            self.release = None
            HUB.publish(dict(stage="heard", state="skip", reason="no transcript"))
        mt = self._mtime(self.wav)
        if mt and mt != self.wav_mtime:                       # F9 released: ptt.py saved the clip, Whisper starts now
            self.wav_mtime = mt
            self.release = dict(at=time.time(), early=False, prev=(self.column.status or {}).get("anim"))
            if not self.runner.busy_prompt:
                HUB.publish(dict(stage="heard", state="start", source="F9", release_at=mt, new_run=True))
                if self.early_thinking:
                    self.column.play_thinking()
                    self.release["early"] = self.column.thinking_on_board
        for p in sorted(self.inbox.glob(f"*-{self.host}.txt")):
            if p.name in self.seen:
                continue
            m = VOICE_RE.match(p.name)
            if not m or m.group("host") != self.host:
                self.seen.add(p.name)
                continue
            try:
                raw = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if not raw.endswith("\n") and time.time() - self._mtime(p) < 1.0:
                continue                                      # still being written
            log = self.ptt_log(m.group("stamp"))
            if log is None and time.time() - self._mtime(p) < 1.5:
                continue                                      # the log line follows the text by a few ms
            self.seen.add(p.name)
            if log is None:                                   # not from ptt.py: never act on it
                continue
            self.take(" ".join(raw.split()), log)

    def undo_dots(self, rel: dict | None) -> None:
        """The dots went up at the F9 release but the line was not for the column: put back what was playing."""
        if rel and rel.get("early") and rel.get("prev") and rel["prev"] != pr.THINKING_NAME:
            threading.Thread(target=pr.play_only, args=(rel["prev"], self.column.conf), daemon=True).start()

    def ptt_log(self, stamp: str) -> dict | None:
        try:
            lines = (self.inbox / f"log-{self.host}.jsonl").read_text(encoding="utf-8", errors="replace").splitlines()[-50:]
        except OSError:
            return None
        for ln in reversed(lines):
            if f'"at": "{stamp}"' in ln:
                try:
                    return json.loads(ln)
                except ValueError:
                    return {}
        return None

    def take(self, text: str, log: dict) -> None:
        rel = self.release or {}
        self.release = None
        trig = TRIGGER_RE.match(text)
        prompt = text[trig.end():] if trig else text
        prompt = prompt.strip(" .,!?:;-").strip()
        skip = None
        if self.mode == "prefix" and not trig:
            skip = "no 'POV' / 'Column' at the start"
        elif ADDRESSED_RE.match(text):
            skip = "addressed to a session"
        elif len(prompt.split()) > 40 or len(prompt) < 3:
            skip = "not a request (length)"
        if skip:
            self.undo_dots(rel)
            HUB.publish(dict(stage="heard", state="skip", text=text, reason=skip))
            return
        heard = dict(whisper_s=log.get("transcribe_s"), clip_s=log.get("seconds"), release_at=self.wav_mtime or None,
                     early_thinking=bool(rel.get("early")), spoken=text)
        self.runner.submit(prompt, source="F9", heard=heard)


def write_shoot_flag(on: bool, info: dict) -> None:
    try:
        if on:
            LOCAL.mkdir(parents=True, exist_ok=True)
            SHOOT_FLAG.write_text(json.dumps(dict(active=True, since=time.strftime("%Y-%m-%dT%H:%M:%S"), pid=os.getpid(),
                                                  note="pov_serve.py takes F9 lines as column requests; Main: don't "
                                                       "run the pipeline for them", **info), indent=1), encoding="utf-8")
        elif SHOOT_FLAG.exists():
            SHOOT_FLAG.unlink()
    except OSError:
        pass


# ---------------------------------------------------------------- HTTP
class Handler(BaseHTTPRequestHandler):
    runner: Runner = None
    column: Column = None

    def _json(self, code: int, obj) -> None:
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _body(self) -> dict:
        try:
            return json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0) or 0)) or b"{}")
        except ValueError:
            return {}

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html", "/stepview.html"):
            data = (HERE / "stepview.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
        elif path == "/events":
            self.events()
        elif path == "/state":
            self._json(200, dict(HUB.info, busy=self.runner.busy_prompt, queued=self.runner.q.qsize(),
                                 last=self.runner.last, pool_ready=pr._POOL.ready_count() if pr._POOL else 0))
        elif path.startswith("/run/"):
            rid = path[len("/run/"):]
            runs = sorted(RUNS_DIR.glob("*.jsonl")) if RUNS_DIR.exists() else []
            f = runs[-1] if (rid == "latest" and runs) else RUNS_DIR / f"{Path(rid).name}.jsonl"
            if not f.exists():
                return self.send_error(404)
            data = f.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif path == "/runs":
            runs = sorted(RUNS_DIR.glob("*.jsonl"), reverse=True)[:50] if RUNS_DIR.exists() else []
            self._json(200, [p.stem for p in runs])
        else:
            self.send_error(404)

    def events(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        q = HUB.subscribe()
        try:
            while True:
                try:
                    ev = q.get(timeout=15)
                    self.wfile.write(b"data: " + json.dumps(ev).encode() + b"\n\n")
                except queue.Empty:
                    self.wfile.write(b": keepalive\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            pass
        finally:
            HUB.unsubscribe(q)

    def do_POST(self):
        path, body = self.path.split("?")[0], self._body()
        if path == "/pov":
            args = [str(x) for x in body.get("args", [])]
            if body.get("async"):
                self._json(202, self.runner.submit(str(body.get("prompt", "")), source=body.get("source", "typed"),
                                                   args=args))
            else:
                self._json(200, self.runner.submit(str(body.get("prompt", "")), source=body.get("source", "http"),
                                                   args=args, wait=True) or {})
        elif path == "/reset":
            out = dict(reset=True)
            if body.get("stop"):
                out.update(self.column.stop())
            HUB.publish(dict(stage="reset", state="done"))
            self._json(200, out)
        elif path == "/replay":
            rid = body.get("run")
            runs = sorted(RUNS_DIR.glob("*.jsonl")) if RUNS_DIR.exists() else []
            f = (RUNS_DIR / f"{rid}.jsonl") if rid else (runs[-1] if runs else None)
            if not f or not f.exists():
                return self._json(404, dict(error="no saved run"))
            threading.Thread(target=replay, args=(f, float(body.get("speed", 1.0))), daemon=True).start()
            self._json(202, dict(replaying=f.stem))
        else:
            self.send_error(404)

    def log_message(self, *a):
        pass


def replay(f: Path, speed: float = 1.0) -> None:
    """Re-publish a saved run with its original timing (as a fresh run, so the step view animates it again)."""
    evs = [json.loads(ln) for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not evs:
        return
    t0, now0 = evs[0]["at"], time.time()
    for i, ev in enumerate(evs):
        delay = (ev["at"] - t0) / max(speed, 0.01) - (time.time() - now0)
        if delay > 0:
            time.sleep(delay)
        ev = dict(ev, at=now0 + (ev["at"] - t0) / max(speed, 0.01), replay=True)
        if "release_at" in ev:
            ev["release_at"] = now0 + (ev["release_at"] - t0) / max(speed, 0.01)
        if i == 0:
            ev["new_run"] = True
        ev.pop("run", None)
        HUB.publish(ev)


def preflight(column: "Column", a) -> None:
    """One READY line for the shoot: warm lane up, column answering (rpm, what it plays now), thinking dots stored."""
    t0 = time.time()
    while time.time() - t0 < 30:
        if pr._POOL is not None and pr._POOL.ready_count() >= 1 and column.status is not None and (
                column.thinking_on_board or not column.store_thinking):
            break
        time.sleep(0.5)
    st = column.status or {}
    lines = [f"  warm lanes ready: {pr._POOL.ready_count() if pr._POOL else 0}",
             ("  column: OFFLINE at " + column.conf["target"]) if column.status is None else
             f"  column: {'MOCK ' if column.mock else ''}fw {st.get('fw')}, {round(st.get('rpm') or 0)} rpm, "
             f"playing '{st.get('anim') or '-'}', thinking dots {'stored' if column.thinking_on_board else 'NOT stored'}"]
    ok = (pr._POOL is not None and pr._POOL.ready_count() >= 1 and column.status is not None)
    print("\n".join(lines) + ("\n  READY: say it (F9)" if ok and a.f9 != "off" else "\n  READY" if ok else
                               "\n  NOT READY (see above); the step view still works for typed prompts (T)"), flush=True)


def refresh_forever(pool, conf: dict | None = None, preset: dict | None = None) -> None:
    while True:
        time.sleep(60)
        try:
            pool.refresh()
            if conf is not None and LAST_LLM["at"] and time.time() - LAST_LLM["at"] > 50 * 60:
                prime(conf, preset)
        except Exception:
            pass


def open_window(url: str, width: int, height: int) -> str | None:
    """The step view as its own app window (no tabs or address bar), in a separate browser profile, for OBS."""
    cands = [shutil.which("chrome"), shutil.which("msedge"),
             r"C:\Program Files\Google\Chrome\Application\chrome.exe",
             r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
             r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
             r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]
    exe = next((c for c in cands if c and Path(c).exists()), None)
    if exe is None:
        return None
    prof = LOCAL / "stepview-browser"
    prof.mkdir(parents=True, exist_ok=True)
    subprocess.Popen([exe, f"--app={url}", f"--window-size={width},{height}", "--window-position=40,0",
                      f"--user-data-dir={prof}", "--no-first-run", "--no-default-browser-check"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return exe


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8790)
    ap.add_argument("--demo", nargs="*", help="run these prompts one after another (warm), print the timings, exit")
    ap.add_argument("--args", default="", help="extra pov_request args (for every request, and for --demo)")
    ap.add_argument("--preset", choices=("fast", "fastest"), default="fast")
    ap.add_argument("--model", default=None, help="generator model for the warm code lane (default: the preset's)")
    ap.add_argument("--gap", type=float, default=6.0, help="--demo: seconds between requests (lets the pool re-warm)")
    ap.add_argument("--target", default=None, help="column URL (default pov_config.json; mock: http://127.0.0.1:18080)")
    ap.add_argument("--f9", choices=("off", "prefix", "all"), default="off",
                    help="take F9 transcripts as requests (read-only): all = every line, prefix = lines starting "
                         "'POV' / 'Column'")
    ap.add_argument("--inbox", default=str(INBOX), help="the Brain-Dump-Button inbox (F9 transcripts)")
    ap.add_argument("--out-root", default=None, help="each request writes into <out-root>/<date>/<time>/")
    ap.add_argument("--open", action="store_true", help="open the step view in its own browser window")
    ap.add_argument("--no-open", action="store_true", help="with --shoot: don't open the window (OBS browser source)")
    ap.add_argument("--window", default="960x1080", help="step view window size for --open")
    ap.add_argument("--prime", action="store_true", help="warm the prompt cache at start (on with --shoot)")
    ap.add_argument("--rehearse", action="store_true",
                    help="start mock_column.py (port 18080) and use it as the column: rehearse with the board off")
    ap.add_argument("--shoot", action="store_true",
                    help="the cold-open setup: " + " ".join(SHOOT_ARGS) + ", --f9 all, out-root "
                         f"{SHOOT_DIR}, the thinking dots stored on the column, --open")
    a = ap.parse_args(argv)
    global PRESET
    PRESET = "--" + a.preset
    conf = pr.load_conf()
    mock_proc = None
    if a.rehearse:
        a.target = a.target or "http://127.0.0.1:18080"
        if pr.column_status(dict(conf, target=a.target), timeout=0.5) is None:
            mock_proc = subprocess.Popen([sys.executable, "-X", "utf8", str(HERE / "mock_column.py"), "--port",
                                          a.target.rsplit(":", 1)[-1].strip("/")],
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1.0)
    if a.target:
        conf["target"] = a.target
        os.environ["POV_TARGET"] = a.target                  # pr.main() re-reads the config per request
    extra = shlex.split(a.args)
    out_root = Path(a.out_root) if a.out_root else None
    if a.shoot:
        extra = SHOOT_ARGS + extra
        out_root = out_root or SHOOT_DIR
        a.f9 = "all" if a.f9 == "off" else a.f9
        a.open = not a.no_open
    if a.model:
        extra += ["--model", a.model]
    global RUNS_DIR
    RUNS_DIR = (out_root or SHOOT_DIR) / "runs"           # saved takes, for replay (P key, ?run=)
    preset = dict(pr.FASTEST if a.preset == "fastest" else pr.FAST)
    if a.model:
        preset["model"] = a.model
    pool = start_pool(conf, preset, template_lane=(a.preset == "fastest"))
    try:
        if a.demo is not None:
            time.sleep(a.gap)
            rows = []
            for p in a.demo:
                t0 = time.time()
                rep = handle(p, extra)
                llm = rep.get("stages", {}).get("llm") or rep.get("stages", {}).get("template") or {}
                rows.append(dict(prompt=p, wall=round(time.time() - t0, 2), playable_s=rep.get("playable_s"),
                                 playing_s=rep.get("playing_s"), source=rep.get("source"), warm=llm.get("warm"),
                                 exit=rep.get("exit")))
                print(json.dumps(rows[-1]), flush=True)
                time.sleep(a.gap)
            return 0
        column = Column(conf, store_thinking="thinking" in " ".join(extra))
        runner = Runner(extra, out_root, column)
        Handler.runner, Handler.column = runner, column
        HUB.info.update(model=preset["model"], effort=preset.get("effort"), preset=a.preset, f9=a.f9,
                        column=column.summary(), shoot=a.shoot)
        threading.Thread(target=refresh_forever, args=(pool, conf, preset), daemon=True).start()
        if a.shoot or a.prime:
            threading.Thread(target=prime, args=(conf, preset), daemon=True).start()
        if a.f9 != "off":
            inbox = Path(a.inbox)
            if not inbox.exists():
                print(f"F9 inbox not found: {inbox} (F9 off)", flush=True)
            else:
                F9Watcher(runner, column, a.f9, inbox, HOST, early_thinking=a.shoot)
                if inbox.resolve() == INBOX.resolve():         # tests use their own inbox: no flag for Main
                    write_shoot_flag(True, dict(f9=a.f9, port=a.port))
        srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
        srv.daemon_threads = True
        url = f"http://127.0.0.1:{a.port}/"
        print(f"pov_serve on {url}  (step view: {url} | POST {url}pov)\n"
              f"  lanes: code {preset['model']} {preset.get('effort')}" + (f", template {pr.TEMPLATE_MODEL}" if a.preset == "fastest" else "") +
              f"\n  column: {conf['target']}" + ("  [MOCK]" if column.mock else "") +
              f"\n  F9: {a.f9}" + (f" (reading {a.inbox}, read-only)" if a.f9 != "off" else "") +
              f"\n  args: {' '.join(extra) or '-'}" + (f"\n  outputs: {out_root}" if out_root else ""), flush=True)
        if a.open:
            w, h = (int(x) for x in a.window.lower().split("x"))
            exe = open_window(url, w, h)
            print(f"  step view window: {exe or 'no Chrome/Edge found: open ' + url + ' yourself'}", flush=True)
        threading.Thread(target=preflight, args=(column, a), daemon=True).start()
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        write_shoot_flag(False, {})
        pool.close()
        if pr._RENDER_POOL is not None:
            pr._RENDER_POOL.close()
        if mock_proc is not None:
            mock_proc.kill()
    return 0


if __name__ == "__main__":
    sys.exit(main())
