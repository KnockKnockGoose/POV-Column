"""POV request pipeline (prototype): prompt -> scope/guard -> generator -> sandbox render -> validate -> preview -> upload -> play.

    py software/pipeline/pov_request.py "a dog running after a ball, looped" --dry-run
    py software/pipeline/pov_request.py "a goose running after a ball" --script software/povgen/gen_dog_ball.py --dry-run
    py software/pipeline/pov_request.py "play the goose" --dry-run                     # library hit, no LLM
    py software/pipeline/pov_request.py "snoopy chasing a ball" --scope public --dry-run # refused with a substitute

This is the script Main (the Claude Code session that receives Brian's F9 lines) runs for "POV, <prompt>". It is a
prototype for the software report: the LLM step shells out to `claude -p` (subscription CLI, no API key) with
prompts/generator_system.md, the sandbox is a subprocess with an import allow-list and a timeout (not a security
boundary against a hostile model; it catches honest mistakes), the upload talks to the ESP32's planned REST API and
tolerates its absence (`--dry-run`, or "no column at pov.local" while the hardware does not exist yet).

Content scope (Brian, 2026-11-02): default `home` = anything he asks for, generated on demand, kept out of git /
Drive-public / video folders; `public` = original characters only, provenance note
kept, files under software/content/public. The spoken line picks it ("... for the video" / "public" -> public);
an OBS recording in progress forces public (recording guard); `--scope` overrides. Home animations are refused for
playback while recording unless `--allow-home-on-air` is given.

Live demo (2026-11-23, docs/2026-11-23-live-demo-pipeline.md): every stage reports to `EVENT_SINK` (pov_serve.py's
step view sets it), the model's code streams in as it is written, the file is fitted to the board's 64 KiB before it
is uploaded (`fit_size`), the upload comes before the preview, and `claude -p` runs from an empty folder so it is not
sent this project's auto-memory with every request.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOFTWARE = HERE.parent
POVGEN, POVSIM = SOFTWARE / "povgen", SOFTWARE / "povsim"
PUBLIC_DIR = SOFTWARE / "content" / "public"
sys.path.insert(0, str(POVGEN))
sys.path.insert(0, str(HERE))
import fastlane  # noqa: E402
import povanim  # noqa: E402

DEFAULT_CONF = dict(
    target="http://pov.local", token="", model="claude-opus-5-5", home_dir=str(Path(os.environ.get("LOCALAPPDATA", "~")).expanduser() / "POVColumn" / "home"),
    recording_flag=str(Path(os.environ.get("LOCALAPPDATA", "~")).expanduser() / "ClaudePanel" / "recording.json"),
    claude="claude", timeout_llm_s=240, timeout_render_s=20, max_repairs=1, effort=None, variant="v01")
PUBLIC_WORDS = ("for the video", "for youtube", "public", "on camera", "for the channel")
# A denylist is only the first line of defence in public scope; the generator prompt and an LLM check back it up.
IP_RE = re.compile(r"\b(snoopy|woodstock|charlie brown|peanuts|mickey|minnie|donald duck|goofy|pluto|disney|pixar|pikachu|"
                   r"pok[eé]mon|mario|luigi|yoshi|sonic|garfield|odie|scooby|tom and jerry|simpsons|homer|bart|spongebob|"
                   r"hello kitty|minion|grogu|baby yoda|star wars|marvel|spider-?man|batman|superman|elmo|kermit|"
                   r"bugs bunny|looney|peppa|bluey|paw patrol|totoro|ghibli|among us|minecraft|creeper|fortnite)\b", re.I)
SUBSTITUTE = {"dog": "an original white beagle-type dog with black ears", "bird": "an original yellow bird",
              "mouse": "an original grey mouse", "cat": "an original orange cat"}
ALLOWED_IMPORTS = {"__future__", "math", "numpy", "np", "povanim", "characters", "scenekit", "bichon_head", "biscuit_kit"}
# Firmware limits (lib/povcore/pova.h): the whole file sits in a 64 KiB RAM arena while it plays, <= 256 frames,
# <= 32 palette entries (POV_MAX_PAL).
MAX_FILE, MAX_FRAMES, MAX_COLOURS = 65536, 256, 32
PINGPONG_MAX_FRAMES = 128          # a ping-pong seam fix doubles the loop: only when the result stays <= MAX_FRAMES
MIN_FIT_FPS = 3.75                 # fit_size stops halving here (8 ticks per frame at 225 rpm) and merges colours instead
# Generator prompt variants: (system prompt file in prompts/, worked example appended to it). v01 = the 11-02 prompt.
VARIANTS = {"v01": ("generator_system.md", POVGEN / "gen_dog_ball.py"),
            "kit": ("generator_kit.md", None)}   # kit = scenekit helpers, 20-60 line scripts (2026-11-07)
# --fast preset (2026-11-07 speed investigation; see docs/2026-11-07-pipeline-speed-investigation.md)
# --fast: progressive. An instant keyword-template placeholder (~0.5 s), then Sonnet (low effort) writes a short
#   scenekit script (median 5 s in-vocabulary, 9 s for things the library cannot draw), zero-latency auto-fixes, cache.
# --fastest: a Haiku JSON spec renders a ready-made template when the request fits (median 2.9 s), code only otherwise.
FAST = dict(model="claude-sonnet-5-5", effort="low", variant="kit", sys="system", template="off", placeholder=True,
            cache=True, autofix=True, candidates=1)
FASTEST = dict(FAST, template="llm")
TEMPLATE_MODEL = "claude-haiku-5-5"
SESSION_MARKERS = ("CLAUDECODE", "CLAUDE_CODE_CHILD_SESSION", "CLAUDE_PID", "CLAUDE_CODE_SESSION_ID",
                   "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SSE_PORT", "CLAUDE_AGENT_SDK_VERSION")
# claude -p picks up the auto-memory (and any CLAUDE.md) of the folder it starts in. Started from this repo it sent the
# project's memory index (~3.1k tokens, uncached) with every generator request (2026-11-23). It starts here instead.
CLI_CWD = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "POVColumn" / "cli"

# ---------------------------------------------------------------- live events (pov_serve.py's step view)
EVENT_SINK = None       # callable(dict) or None. Stages: scope, placeholder, source, llm, render, check, pack, upload,
                        # playing, preview, done; states: start | delta | done | skip | error


def emit(stage: str, state: str = "done", **data) -> None:
    if EVENT_SINK is None:
        return
    try:
        EVENT_SINK(dict(stage=stage, state=state, at=time.time(), **data))
    except Exception:
        pass                             # the step view must never break the pipeline


def load_conf() -> dict:
    conf = dict(DEFAULT_CONF)
    p = HERE / "pov_config.json"
    if p.exists():
        conf.update(json.loads(p.read_text(encoding="utf-8")))
    if os.environ.get("POV_TARGET"):     # rehearsal against mock_column.py, without touching pov_config.json
        conf["target"] = os.environ["POV_TARGET"]
    return conf


def clean_env() -> dict:
    """A `claude` started from inside a Claude Code tool inherits session markers and runs as a child session."""
    env = dict(os.environ)
    for k in list(env):
        if k in SESSION_MARKERS or k.startswith("CLAUDE_CODE_"):
            env.pop(k, None)
    return env


def cli_cwd() -> str:
    CLI_CWD.mkdir(parents=True, exist_ok=True)
    return str(CLI_CWD)


# ---------------------------------------------------------------- scope
def recording(conf: dict) -> bool:
    """Is OBS recording? env override, then the panel's flag file (TODO: wire to the panel's OBS state / obs-websocket)."""
    if os.environ.get("POV_RECORDING") == "1":
        return True
    p = Path(conf["recording_flag"])
    try:
        if p.exists():
            j = json.loads(p.read_text(encoding="utf-8"))
            return bool(j.get("recording"))
    except (OSError, ValueError):
        pass
    return False


def resolve_scope(prompt: str, explicit: str | None, conf: dict) -> tuple[str, str]:
    low = prompt.lower()
    if explicit:
        scope, why = explicit, "--scope"
    elif any(w in low for w in PUBLIC_WORDS):
        scope, why = "public", "spoken: " + next(w for w in PUBLIC_WORDS if w in low)
    elif os.environ.get("POV_SCOPE") in ("home", "public"):
        scope, why = os.environ["POV_SCOPE"], "env POV_SCOPE"
    else:
        scope, why = "home", "default"
    if recording(conf) and scope != "public":
        scope, why = "public", "OBS is recording (guard)"
    return scope, why


def ip_check(prompt: str) -> str | None:
    m = IP_RE.search(prompt)
    if not m:
        return None
    kind = "dog" if re.search(r"snoopy|pluto|odie|scooby|bluey", m.group(0), re.I) else \
        "mouse" if re.search(r"mickey|minnie|jerry", m.group(0), re.I) else \
        "bird" if re.search(r"woodstock|donald|tweety", m.group(0), re.I) else "cat" if "garfield" in m.group(0).lower() else "dog"
    return f"'{m.group(0)}' is a recognisable third-party character: public scope needs an original one, e.g. {SUBSTITUTE[kind]}"


# ---------------------------------------------------------------- generation
def library_hit(prompt: str) -> Path | None:
    """'play the goose' / 'the dog again' -> an existing public animation."""
    low = prompt.lower()
    if not re.search(r"\b(play|again|show|the usual)\b", low):
        return None
    for side in sorted(PUBLIC_DIR.glob("*.json")):
        name = side.stem
        key = name.split("_")[0]
        if key in low and (side.with_suffix(".pova")).exists():
            return side.with_suffix(".pova")
    return None


def build_prompts(prompt: str, scope: str, variant: str = "v01") -> tuple[str, str]:
    """(system, user): the system part is stable across requests, so the CLI can cache it; the user part is the request."""
    sys_file, example = VARIANTS[variant]
    system = (HERE / "prompts" / sys_file).read_text(encoding="utf-8")
    if example is not None:
        system += f"\n\n## Worked example (a complete scene script)\n```python\n{Path(example).read_text(encoding='utf-8')}\n```\n"
    return system, f"## Request\nscope: {scope}\nprompt: {prompt}\n"


def build_messages(prompt: str, scope: str, example_src: str | None = None, variant: str = "v01") -> str:
    """The 11-02 single-message form (everything on stdin, Claude Code's default system prompt in front of it)."""
    system, user = build_prompts(prompt, scope, variant)
    return f"{system}\n{user}"


def claude_exe(conf: dict) -> str:
    return shutil.which(conf["claude"]) or conf["claude"]


STREAM_ARGS = ["--output-format", "stream-json", "--verbose", "--include-partial-messages"]
QUIET_ARGS = ["--tools", "", "--no-session-persistence", "--setting-sources", "", "--strict-mcp-config",
              "--disable-slash-commands"]


def call_claude(user: str, conf: dict, model: str, effort: str | None = None, system: str | None = None,
                on_text=None, on_think=None, use_pool: bool = True) -> tuple[str, dict]:
    """One headless call, streamed: `on_text(chunk)` sees the reply as it is written (the step view shows the code
    appearing), and the call returns at the result line instead of waiting for claude.exe to shut down. `system`
    replaces Claude Code's own coding-agent system prompt (smaller input, cacheable prefix); without it the whole
    prompt goes on stdin as in v0.1. No shell: argv goes straight to claude.exe."""
    if _POOL is not None and system and use_pool:
        warm = _POOL.take(model, effort, system)
        if warm is not None:                    # a pre-spawned process (pov_serve.py): skips the ~1 s CLI start
            return _POOL.ask(warm, user, conf, model, effort, on_text=on_text, on_think=on_think)
    cmd = [claude_exe(conf), "-p", "--model", model] + STREAM_ARGS + QUIET_ARGS
    if effort:
        cmd += ["--effort", effort]
    sp_file = None
    if system:
        fd, sp_file = tempfile.mkstemp(prefix="pov_sys_", suffix=".md")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(system)
        cmd += ["--system-prompt-file", sp_file]
    t0 = time.time()
    p = _spawn(cmd)
    res, timing, err = _stream_reply(p, user, conf["timeout_llm_s"], on_text, cleanup=sp_file, on_think=on_think)
    if res is None or res.get("is_error"):
        raise RuntimeError(f"claude -p failed ({p.returncode}): {err[-800:]} {str((res or {}).get('result', ''))[-300:]}")
    return res.get("result", ""), _llm_info(res, model, effort, t0, timing)


_LIVE: set = set()                     # running claude processes, so losing parallel candidates can be killed
_LIVE_LOCK = threading.Lock()
EXIT_LAGS: list = []                   # seconds from the result line to claude.exe's exit (what streaming saves)


def _spawn(cmd: list) -> subprocess.Popen:
    return subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            encoding="utf-8", env=clean_env(), cwd=cli_cwd())


def _llm_info(res: dict, model: str, effort: str | None, t0: float, timing: dict) -> dict:
    return dict(model=model, effort=effort, seconds=round(time.time() - t0, 1),
                api_s=round(res.get("duration_api_ms", 0) / 1000, 1), cost_usd=res.get("total_cost_usd"),
                usage=res.get("usage"), **timing)


def _reap(p, cleanup: str | None, t_result: float | None) -> None:
    try:
        p.wait(timeout=60)
    except subprocess.TimeoutExpired:
        p.kill()
    if t_result is not None:
        EXIT_LAGS.append(round(time.time() - t_result, 2))
        del EXIT_LAGS[:-50]
    if cleanup:
        try:
            os.unlink(cleanup)
        except OSError:
            pass


def _stream_reply(p, stdin_text: str, timeout: float, on_text=None, cleanup: str | None = None, on_think=None) -> tuple:
    """Send the request and read stream-json lines until the result line. Returns (result dict | None, timing,
    stderr tail). claude.exe is left to finish on its own (a reaper thread collects it and the temp prompt file)."""
    t0 = time.time()
    lines: queue.Queue = queue.Queue()
    err_chunks: list = []

    def pump_out():
        try:
            for line in p.stdout:
                lines.put(line)
        except (OSError, ValueError):
            pass
        lines.put(None)

    def pump_err():
        try:
            err_chunks.append(p.stderr.read() or "")
        except (OSError, ValueError):
            pass

    threading.Thread(target=pump_out, daemon=True).start()
    t_err = threading.Thread(target=pump_err, daemon=True)
    t_err.start()
    with _LIVE_LOCK:
        _LIVE.add(p)
    res, timing, t_result = None, {}, None
    try:
        try:
            p.stdin.write(stdin_text)
            p.stdin.close()
        except OSError:
            pass
        deadline = t0 + timeout
        while True:
            left = deadline - time.time()
            if left <= 0:
                p.kill()
                err_chunks.append(f" timeout after {timeout} s")
                break
            try:
                line = lines.get(timeout=min(left, 1.0))
            except queue.Empty:
                continue
            if line is None:
                break
            try:
                j = json.loads(line)
            except ValueError:
                continue
            ty = j.get("type")
            if ty == "stream_event":
                ev = j.get("event") or {}
                d = ev.get("delta") or {}
                if ev.get("type") == "content_block_start" and \
                        (ev.get("content_block") or {}).get("type") in ("thinking", "redacted_thinking"):
                    if "thinking_s" not in timing:
                        timing["thinking_s"] = round(time.time() - t0, 2)
                        if on_think is not None:
                            try:
                                on_think()
                            except Exception:
                                pass
                if ev.get("type") == "content_block_delta" and d.get("type") == "text_delta":
                    timing.setdefault("first_token_s", round(time.time() - t0, 2))
                    if on_text is not None:
                        try:
                            on_text(d.get("text", ""))
                        except Exception:
                            pass
            elif ty == "result":
                res, t_result = j, time.time()
                timing["result_s"] = round(t_result - t0, 2)
                break
    finally:
        with _LIVE_LOCK:
            _LIVE.discard(p)
        threading.Thread(target=_reap, args=(p, cleanup, t_result), daemon=True).start()
    if res is None:
        t_err.join(timeout=3)
    return res, timing, "".join(err_chunks)


class WarmPool:
    """Pre-spawned `claude -p --input-format stream-json` processes, one per (model, effort, system prompt), each used
    for exactly one request and replaced in the background. Measured 11-07: a spawned-and-idle process answers a
    trivial Haiku turn in 0.8 s vs 1.9 s cold (the CLI's boot is done before the request arrives). Only useful in a
    long-lived process (pov_serve.py); a one-shot pov_request.py run has nothing to pre-spawn into."""

    def __init__(self, conf: dict, max_age_s: float = 1200.0):
        self.conf, self.ready, self.lock, self.max_age_s = conf, {}, threading.Lock(), max_age_s

    @staticmethod
    def key(model, effort, system):
        return model, effort, hashlib.sha1(system.encode()).hexdigest()

    def prewarm(self, model: str, effort: str | None, system: str) -> None:
        fd, sp_file = tempfile.mkstemp(prefix="pov_warm_", suffix=".md")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(system)
        cmd = [claude_exe(self.conf), "-p", "--model", model, "--input-format", "stream-json"] + STREAM_ARGS + \
            QUIET_ARGS + ["--system-prompt-file", sp_file]
        if effort:
            cmd += ["--effort", effort]
        p = _spawn(cmd)
        p.pov_sys_file, p.pov_key, p.pov_spec = sp_file, self.key(model, effort, system), (model, effort, system)
        p.pov_born = time.time()
        with self.lock:
            old = self.ready.pop(p.pov_key, None)
            self.ready[p.pov_key] = p
        if old is not None:
            _retire(old)

    def take(self, model, effort, system):
        with self.lock:
            p = self.ready.pop(self.key(model, effort, system), None)
        if p is not None and p.poll() is not None:            # it died while waiting
            threading.Thread(target=self.prewarm, args=p.pov_spec, daemon=True).start()
            return None
        return p

    def refresh(self) -> int:
        """Replace processes idle longer than max_age_s (pov_serve calls this every minute), so a take after a long
        pause between shots still finds a fresh, live process. Returns how many were replaced."""
        with self.lock:
            stale = [p for p in self.ready.values() if p.poll() is not None or time.time() - p.pov_born > self.max_age_s]
        for p in stale:
            self.prewarm(*p.pov_spec)                         # swaps it out of `ready` and retires the old one
        return len(stale)

    def ready_count(self) -> int:
        with self.lock:
            return sum(1 for p in self.ready.values() if p.poll() is None)

    def ask(self, p, user: str, conf: dict, model: str, effort: str | None, on_text=None, on_think=None) -> tuple[str, dict]:
        t0 = time.time()
        threading.Thread(target=self.prewarm, args=p.pov_spec, daemon=True).start()   # the next one boots meanwhile
        msg = {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": user}]}}
        res, timing, err = _stream_reply(p, json.dumps(msg) + "\n", conf["timeout_llm_s"], on_text, cleanup=p.pov_sys_file,
                                         on_think=on_think)
        if res is None or res.get("is_error"):
            raise RuntimeError(f"warm claude failed ({p.returncode}): {(err or '')[-400:]}")
        return res.get("result", ""), dict(_llm_info(res, model, effort, t0, timing), warm=True,
                                           warm_age_s=round(t0 - p.pov_born, 1))

    def close(self):
        with self.lock:
            procs, self.ready = list(self.ready.values()), {}
        for p in procs:
            _retire(p)


def _retire(p) -> None:
    p.kill()
    try:
        os.unlink(p.pov_sys_file)
    except OSError:
        pass


_POOL: WarmPool | None = None


def _run_live(cmd: list, stdin_text: str, timeout: float, cleanup: str | None = None) -> tuple[str, str, int]:
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                         encoding="utf-8", env=clean_env(), cwd=cli_cwd())
    with _LIVE_LOCK:
        _LIVE.add(p)
    try:
        out, err = p.communicate(stdin_text, timeout=timeout)
    except subprocess.TimeoutExpired:
        p.kill()
        out, err = p.communicate()
        err = f"timeout after {timeout} s; " + (err or "")
    finally:
        with _LIVE_LOCK:
            _LIVE.discard(p)
        if cleanup:
            try:
                os.unlink(cleanup)
            except OSError:
                pass
    return out or "", err or "", p.returncode if p.returncode is not None else -1


def kill_live() -> int:
    with _LIVE_LOCK:
        procs = list(_LIVE)
    for p in procs:
        try:
            p.kill()
        except OSError:
            pass
    return len(procs)


def call_claude_image(text: str, png: Path, conf: dict, model: str, effort: str | None = None,
                      system: str | None = None) -> tuple[str, dict]:
    """claude -p with one image: stream-json in/out (json output is rejected with stream-json input)."""
    import base64
    cmd = [claude_exe(conf), "-p", "--model", model, "--input-format", "stream-json"] + STREAM_ARGS + QUIET_ARGS
    if effort:
        cmd += ["--effort", effort]
    sp_file = None
    if system:
        fd, sp_file = tempfile.mkstemp(prefix="pov_sys_", suffix=".md")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(system)
        cmd += ["--system-prompt-file", sp_file]
    msg = {"type": "user", "message": {"role": "user", "content": [
        {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                     "data": base64.b64encode(Path(png).read_bytes()).decode()}},
        {"type": "text", "text": text}]}}
    t0 = time.time()
    p = _spawn(cmd)
    res, timing, err = _stream_reply(p, json.dumps(msg) + "\n", conf["timeout_llm_s"], cleanup=sp_file)
    if res is None or res.get("is_error"):
        raise RuntimeError(f"claude -p (image) failed ({p.returncode}): {err[-600:]}")
    return res.get("result", ""), _llm_info(res, model, effort, t0, timing)


def check_indices(anim) -> None:
    """A script that draws with a colour number it never added crashes the validator (IndexError) and the board's
    decoder refuses it: make it a RuntimeError the repair round can act on (audit 2026-11-23, finding 2)."""
    npal = len(anim.palette)
    for i, f in enumerate(anim.frames):
        m = int(f.max()) if f.size else 0
        if m >= npal:
            raise RuntimeError(f"frame {i} draws with colour index {m}, but only {npal} colours are defined "
                               f"(0..{npal - 1}): get every colour index from sc.col(name, rgb)")


def _b64(path) -> str:
    import base64
    return base64.b64encode(Path(path).read_bytes()).decode()


def extract_code(text: str) -> str:
    m = re.search(r"```python\s*(.*?)```", text, re.S)
    return (m.group(1) if m else text).strip() + "\n"


def lint_imports(src: str) -> list[str]:
    bad = []
    for m in re.finditer(r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))", src, re.M):
        mod = (m.group(1) or m.group(2)).split(".")[0]
        if mod not in ALLOWED_IMPORTS:
            bad.append(mod)
    for word in ("open(", "subprocess", "socket", "__import__", "eval(", "exec(", "os.", "sys."):
        if word in src:
            bad.append(word)
    return bad


RUNNER = r"""
import sys, importlib.util
sys.path.insert(0, sys.argv[3])
spec = importlib.util.spec_from_file_location("scene", sys.argv[1]); scene = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scene)
anim = scene.build()
info = anim.write(sys.argv[2])
print("OK", info["frames"], info["bytes"])
"""


RUNNER_WARM = r"""
import sys, json, importlib.util
sys.path.insert(0, sys.argv[1])
import numpy, povanim, scenekit            # the slow part (~0.2 s), done before the script arrives
line = sys.stdin.readline()
if not line.strip():
    sys.exit(0)
job = json.loads(line)
spec = importlib.util.spec_from_file_location("scene", job["script"]); scene = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scene)
anim = scene.build()
info = anim.write(job["out"])
print("OK", info["frames"], info["bytes"], flush=True)
"""


class RenderPool:
    """The sandbox, pre-started: one isolated interpreter (-I) with numpy and scenekit already imported, waiting for a
    script path on stdin. Each process renders exactly one script and is replaced in the background, so scripts are as
    isolated from each other as with the cold runner; it only skips the interpreter start and imports (pov_serve.py)."""

    def __init__(self):
        self.td = tempfile.mkdtemp(prefix="pov_render_")
        self.runner = Path(self.td) / "runner_warm.py"
        self.runner.write_text(RUNNER_WARM, encoding="utf-8")
        self.lock, self.p = threading.Lock(), None
        self.spawn()

    def spawn(self) -> None:
        p = subprocess.Popen([sys.executable, "-I", str(self.runner), str(POVGEN)], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", cwd=self.td)
        with self.lock:
            old, self.p = self.p, p
        if old is not None:
            old.kill()

    def take(self):
        with self.lock:
            p, self.p = self.p, None
        threading.Thread(target=self.spawn, daemon=True).start()
        return p if p is not None and p.poll() is None else None

    def close(self) -> None:
        with self.lock:
            p, self.p = self.p, None
        if p is not None:
            p.kill()


_RENDER_POOL: RenderPool | None = None


def render_script(script: Path, out_pova: Path, conf: dict) -> str:
    """Run the scene script in a fresh interpreter (-I: isolated, no user site, no PYTHONPATH; numpy from the system
    site-packages). pov_serve.py keeps one such interpreter pre-started (RenderPool)."""
    warm = _RENDER_POOL.take() if _RENDER_POOL is not None else None
    if warm is not None:
        try:
            out, err = warm.communicate(json.dumps(dict(script=str(script), out=str(out_pova))) + "\n",
                                        timeout=conf["timeout_render_s"])
        except subprocess.TimeoutExpired:
            warm.kill()
            raise RuntimeError(f"scene script failed:\ntimed out after {conf['timeout_render_s']} s")
        if warm.returncode != 0:
            raise RuntimeError("scene script failed:\n" + (err or "")[-1500:])
        return (out or "").strip()
    with tempfile.TemporaryDirectory() as td:
        runner = Path(td) / "runner.py"
        runner.write_text(RUNNER, encoding="utf-8")
        r = subprocess.run([sys.executable, "-I", str(runner), str(script), str(out_pova), str(POVGEN)],
                           capture_output=True, text=True, timeout=conf["timeout_render_s"], cwd=td)
    if r.returncode != 0:
        raise RuntimeError("scene script failed:\n" + r.stderr[-1500:])
    return r.stdout.strip()


def preview(pova: Path, out_dir: Path) -> list[str]:
    r = subprocess.run([sys.executable, str(POVSIM / "simulate.py"), str(pova), "--out", str(out_dir), "--gif", "--stills",
                        "--width", "960", "--scale", "4"], capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        raise RuntimeError("simulator failed: " + r.stderr[-800:])
    return [str(p) for p in sorted(out_dir.glob("*"))]


# ---------------------------------------------------------------- speed lanes (2026-11-07)
def _merge_palette(anim, limit: int = 32) -> int:
    """Merge the closest pair of colours (never index 0) until the palette fits; remaps every frame. Returns merges."""
    import numpy as np
    merges = 0
    while len(anim.palette) > limit:
        rgb = np.array(anim.palette.rgb, dtype=float)
        d = ((rgb[:, None, :] - rgb[None, :, :]) ** 2).sum(-1)
        d[0, :] = d[:, 0] = d[np.arange(len(rgb)), np.arange(len(rgb))] = np.inf
        i, j = np.unravel_index(np.argmin(d), d.shape)
        keep, drop = min(i, j), max(i, j)
        lut = np.arange(len(rgb))
        lut[drop] = keep
        lut[drop + 1:] -= 1
        anim.frames = [lut[f].astype(np.uint8) for f in anim.frames]
        del anim.palette.names[drop], anim.palette.rgb[drop]
        merges += 1
    return merges


def _halve_frames(anim) -> None:
    """Every 2nd frame, same loop duration: half the fps when the holds are even and the fps stays exact in the
    header (fps x 10 is an integer there), else the dropped frame's hold is added to the kept one."""
    n, holds = anim.n, list(anim.holds)
    half = anim.fps / 2
    if len(set(holds)) == 1 and n % 2 == 0 and abs(half * 10 - round(half * 10)) < 1e-9:
        anim.fps, anim.holds = half, holds[0::2]
    else:
        anim.holds = [min(255, holds[i] + (holds[i + 1] if i + 1 < n else 0)) for i in range(0, n, 2)]
    anim.frames = anim.frames[0::2]


def fit_size(anim, limit: int = MAX_FILE, max_frames: int = MAX_FRAMES, min_fps: float = MIN_FIT_FPS):
    """Fit an animation to the board before it is uploaded (64 KiB file, 256 frames: pova.h). First every 2nd frame at
    half the frame rate, which keeps the loop's duration, down to min_fps (3.75 = 8 ticks a frame at 225 rpm); then
    fewer colours (the closest pairs merged: 16, 8, 4), which lengthens the RLE runs; frames again as a last resort.
    Changes `anim` in place. Returns (anim, notes): notes is empty when it already fitted. Call it last, after the
    metadata is final: the metadata is part of the file."""
    def eff_fps():
        return anim.n / anim.duration_s if anim.duration_s > 0 else anim.fps

    def halve():
        _halve_frames(anim)
        s = len(anim.to_bytes())
        steps.append(f"frames/2 -> {anim.n} @ {eff_fps():.3g} fps, {s / 1024:.1f} KB")
        return s
    size = len(anim.to_bytes())
    if size <= limit and anim.n <= max_frames and len(anim.palette) <= MAX_COLOURS:
        return anim, []
    before, steps = (size, anim.n, eff_fps(), len(anim.palette)), []
    if len(anim.palette) > MAX_COLOURS:                   # the board refuses > 32 palette entries outright
        _merge_palette(anim, MAX_COLOURS)
        size = len(anim.to_bytes())
        steps.append(f"colours -> {len(anim.palette)}, {size / 1024:.1f} KB")
    budget = limit - 400                                  # room for the "fit" note added to the metadata below
    while (size > budget or anim.n > max_frames) and anim.n >= 2 and eff_fps() / 2 >= min_fps - 1e-6:
        size = halve()
    for pal_limit in (16, 8, 4):
        if size <= budget:
            break
        if len(anim.palette) > pal_limit:
            _merge_palette(anim, pal_limit)
            size = len(anim.to_bytes())
            steps.append(f"colours -> {len(anim.palette)}, {size / 1024:.1f} KB")
    while (size > budget or anim.n > max_frames) and anim.n >= 2:
        size = halve()
    anim.meta["fit"] = dict(from_bytes=before[0], from_frames=before[1], from_fps=round(before[2], 3),
                            from_colours=before[3], frames=anim.n, fps=round(eff_fps(), 3), colours=len(anim.palette))
    size = len(anim.to_bytes())
    while size > limit and anim.n >= 2:
        size = halve()
    head = (f"fit to {limit // 1024} KB: {before[0] / 1024:.1f} KB, {before[1]} frames @ {before[2]:.3g} fps, "
            f"{before[3]} colours -> {size / 1024:.1f} KB, {anim.n} @ {eff_fps():.3g} fps, {len(anim.palette)} colours")
    return anim, [head] + steps + ([] if size <= limit else [f"STILL TOO BIG ({size} B)"])


def auto_fix(anim, val: dict, mode: str):
    """Zero-latency repairs for validator warnings that need no model: a loop seam becomes a ping-pong loop (frames
    forward then back, which always closes), > 32 colours are merged, and an over-cap peak current is handled by
    storing the validator's recommended global brightness in meta["gb"] (what the firmware plays at)."""
    fixes = []
    w = " ".join(val["warnings"])
    if "loop seam" in w:
        n, size = anim.n, len(anim.to_bytes())
        if n <= PINGPONG_MAX_FRAMES and size * (2 * n - 2) / max(1, n) <= MAX_FILE:
            frames, holds = list(anim.frames), list(anim.holds)
            anim.frames = frames + frames[-2:0:-1]
            anim.holds = holds + holds[-2:0:-1]
            fixes.append(f"seam: ping-pong loop ({len(frames)} -> {anim.n} frames)")
        else:                       # 11-22: a 105-frame scene became 208 frames / 189 KB, which the board refused
            fixes.append(f"seam: kept ({n} frames; a ping-pong loop would not fit the board's 64 KB / 256 frames)")
    if "palette entries" in w:
        fixes.append(f"palette: merged {_merge_palette(anim)} colours")
    gb = 31
    v = povanim.validate(anim, mode=mode)
    if any(x.startswith("peak current") for x in v["warnings"]):
        gb = v["gb_recommended"]
        v = povanim.validate(anim, gb=gb, mode=mode)
        while gb > 4 and any(x.startswith("peak current") for x in v["warnings"]):   # idle current does not scale
            gb -= 1
            v = povanim.validate(anim, gb=gb, mode=mode)
        anim.meta["gb"] = gb
        fixes.append(f"current: plays at gb {gb} (of 31)")
    return anim, v, fixes


# ----------------------------------------------------------------
def codegen_attempt(idx: int, generate, work: Path, conf: dict) -> dict:
    """One candidate: generate -> lint -> render, with one repair round for a lint or render failure -> validate."""
    script, pova = work / f"cand{idx}.py", work / f"cand{idx}.pova"
    out: dict = dict(idx=idx, script=script, pova=pova, errors=[], llm=None, attempts=0)
    extra = ""
    for attempt in range(1 + conf["max_repairs"]):
        out["attempts"] = attempt + 1
        try:
            text, llm = generate(extra)
        except RuntimeError as e:
            out["errors"].append(f"llm: {str(e)[-300:]}")
            return out
        if out["llm"] is None:
            out["llm"] = llm
        else:                                   # keep the first call's numbers, add the repair's time and tokens
            out["llm"] = dict(out["llm"], repair_seconds=llm["seconds"],
                              seconds=round(out["llm"]["seconds"] + llm["seconds"], 1),
                              repair_output_tokens=(llm.get("usage") or {}).get("output_tokens"))
        src = extract_code(text)
        emit("llm", "done", attempt=attempt + 1, lines=len(src.strip().splitlines()), seconds=llm.get("seconds"),
             api_s=llm.get("api_s"), first_token_s=llm.get("first_token_s"), warm=llm.get("warm"),
             out_tokens=(llm.get("usage") or {}).get("output_tokens"), model=llm.get("model"))
        bad = lint_imports(src)
        script.write_text(src, encoding="utf-8")
        if bad:
            err = f"disallowed imports/calls {bad}: use only math, numpy, povanim, characters, scenekit"
        else:
            t_r = time.time()
            emit("render", "start", attempt=attempt + 1)
            try:
                out["render"] = render_script(script, pova, conf)
                anim = povanim.Animation.read(pova)
                check_indices(anim)
                out["render_s"] = round(time.time() - t_r, 2)
                emit("render", "done", seconds=out["render_s"], frames=anim.n, fps=anim.fps, colours=len(anim.palette),
                     duration_s=round(anim.duration_s, 2), mode=anim.meta.get("mode", "front"),
                     pova_b64=_b64(pova) if EVENT_SINK is not None else None)
                emit("check", "start")                  # main() reuses this validation and reports "check done"
                out["val"] = povanim.validate(anim, mode=anim.meta.get("mode", "front"))
                out["ok"] = True
                return out
            except Exception as e:              # traceback, timeout, bad colour index, validator crash: one repair
                err = str(e) if isinstance(e, RuntimeError) else f"{type(e).__name__}: {e}"
                emit("render", "error", error=err[-400:], attempt=attempt + 1)
        out["errors"].append(err[-600:])
        extra = (f"\nYour script failed. Fix it and return the complete script again.\n\nError:\n{err}\n\nScript:\n"
                 f"```python\n{src}\n```")
    return out


def codegen(n: int, generate, work: Path, pova: Path, conf: dict, rep: dict) -> dict | None:
    """n parallel candidates; the first that renders AND passes the validator wins (else the first that renders)."""
    import concurrent.futures as cf
    t0 = time.time()
    results = []
    winner = None
    ex = cf.ThreadPoolExecutor(max_workers=n)
    futs = [ex.submit(codegen_attempt, i, generate, work, conf) for i in range(n)]
    for f in cf.as_completed(futs):
        r = f.result()
        r["t"] = round(time.time() - t0, 1)
        results.append(r)
        if r.get("ok") and r["val"]["ok"]:
            winner = r
            break
    if winner is None:
        rendered = [r for r in results if r.get("ok")]
        winner = min(rendered, key=lambda r: len(r["val"]["warnings"])) if rendered else None
    if n > 1:
        rep["stages"]["candidates"] = [dict(idx=r["idx"], t=r["t"], ok=r.get("ok"), val_ok=(r.get("val") or {}).get("ok"),
                                            attempts=r["attempts"], errors=[e[:120] for e in r["errors"]]) for r in results]
        rep["stages"]["candidates_killed"] = kill_live()
    ex.shutdown(wait=False, cancel_futures=True)
    for r in results:
        for i, e in enumerate(r["errors"]):
            rep["stages"][f"render_error_{i}" if n == 1 else f"c{r['idx']}_error_{i}"] = e
    if winner is None:
        if any("disallowed" in e for r in results for e in r["errors"]):
            rep["refused"] = "generated script used disallowed imports/calls after the repair round"
            rep["exit_code"] = 4
        return None
    shutil.copy(winner["pova"], pova)
    rep["stages"]["render"] = dict(result=winner["render"], wall_s=winner.get("render_s"), attempts=winner["attempts"],
                                   candidate=winner["idx"])
    return dict(script=winner["script"], llm=winner["llm"], val=winner["val"])


def try_template(prompt: str, scope: str, mode: str, conf: dict, rep: dict, model: str | None, min_fit: int) -> str | None:
    """keyword: instant regex match; llm: a small model maps the request onto the template vocabulary (JSON)."""
    t0 = time.time()
    if mode == "keyword":
        spec, fit = fastlane.spec_from_keywords(prompt)
        missing = spec.get("_missing", "")
        info = {}
    else:
        system = (HERE / "prompts" / "template_spec.md").read_text(encoding="utf-8")
        try:
            text, info = call_claude(f"Request: {prompt}", conf, model or TEMPLATE_MODEL, "low", system=system)
        except RuntimeError as e:
            rep["stages"]["template"] = dict(error=str(e)[-300:])
            return None
        spec, fit, missing = fastlane.parse_spec_reply(text)
    rep["stages"]["template"] = dict(mode=mode, fit=fit, spec=spec, missing=missing, wall_s=round(time.time() - t0, 2),
                                     **{k: info.get(k) for k in ("model", "seconds", "cost_usd", "warm") if info})
    if fit < min_fit or not spec:
        return None
    return fastlane.template_script(spec, prompt, scope)


THINKING_NAME = "ai_thinking"


def thinking_anim():
    """The 'thinking' placeholder: three dots that rise in turn, like a chat app's typing indicator, in the viewer's
    window. The column answers at once while the model writes, and nobody takes it for the result (the keyword
    template placeholder looks like a finished scene). 18 frames, ~2 KB."""
    import scenekit
    sc = scenekit.Scene("thinking", mode="front", seconds=1.2, fps=15, name=THINKING_NAME, note="pipeline placeholder")
    dot, dim = sc.col("dot", (255, 214, 160)), sc.col("dot_dim", (110, 92, 70))
    for k, t, cv in sc.frames():
        for i, c in enumerate((42, 48, 54)):
            x = (t - 0.18 * i) % 1.0
            lift = 3.0 * math.sin(math.pi * x / 0.45) if x < 0.45 else 0.0          # one hop per dot per loop
            cv.disc(20 + round(lift), c, 2.2, dot if lift > 0.5 else dim)
    anim = sc.done()
    anim.meta.update(placeholder=True)
    return anim


def show_placeholder(prompt: str, scope: str, work: Path, conf: dict, dry_run: bool, kind: str = "keyword",
                     on_board: bool = False) -> dict:
    """Something on the column within ~1 s while the real scene is made. kind="keyword": the keyword template (or a
    neutral sparkle loop); kind="thinking": the typing-dots loop (`on_board` = pov_serve already stored it, so only
    /api/play is sent). The upload runs in a background thread (gap G5): join out["_thread"] before the final upload,
    so a slow placeholder can never land on top of the result."""
    t0 = time.time()
    if kind == "thinking":
        spec, fit = {}, None
        p = work / f"{THINKING_NAME}.pova"
        if not on_board:
            thinking_anim().write(p, sidecar=False)
    else:
        import scenekit
        spec, fit = fastlane.spec_from_keywords(prompt)
        if not spec:
            spec = dict(subject="none", background="night", effects=["sparkles"], seconds=2)
        spec = {k: v for k, v in spec.items() if not k.startswith("_")}
        anim = scenekit.compose(dict(spec, prompt=prompt, scope=scope, name="placeholder"))
        anim.meta.update(placeholder=True)
        p = work / "placeholder.pova"
        anim.write(p)
    out = dict(kind=kind, fit=fit, spec=spec, file=str(p), render_s=round(time.time() - t0, 2))
    if dry_run:
        out["upload"] = "dry-run"
        return out

    def run():
        out["upload"] = play_only(THINKING_NAME, conf) if (kind == "thinking" and on_board) else upload_and_play(p, conf)
        out["upload_s"] = round(time.time() - t0, 2)
    th = threading.Thread(target=run, daemon=True)
    th.start()
    out["_thread"] = th
    return out


CHECK_SYSTEM = """You review a pixel animation for a 42 x 96 LED column (row 0 is the bottom; the viewer sees the middle
third, columns 32-63). You get the request, six frames spread over the loop (left to right, each the full 96 x 42
grid), the validator's warnings and the scene script. If the animation clearly reads as the request, reply with the
single word OK. Otherwise fix the most important problems (missing or unreadable subject, wrong action, subject outside
the viewer's window, the validator warnings) and reply with the complete corrected script in ONE ```python block."""


def visual_check(prompt: str, scope: str, script: Path, pova: Path, generate, conf: dict, rep: dict, model: str,
                 effort: str | None) -> None:
    """One self-check round: Claude sees the frames; a corrected script replaces the first only if it renders."""
    t0 = time.time()
    png = script.with_suffix(".check.png")
    fastlane.contact_strip(pova, png)
    anim = povanim.Animation.read(pova)
    val = povanim.validate(anim, mode=anim.meta.get("mode", "front"))
    text = (f"Request: {prompt}\nscope: {scope}\nValidator warnings: {val['warnings'] or 'none'}\n\nScript:\n"
            f"```python\n{script.read_text(encoding='utf-8')}\n```")
    st = dict()
    try:
        reply, info = call_claude_image(text, png, conf, model, effort, system=CHECK_SYSTEM)
        st.update(info)
    except RuntimeError as e:
        rep["stages"]["self_check"] = dict(error=str(e)[-300:], wall_s=round(time.time() - t0, 1))
        return
    if "```python" not in reply:
        st.update(verdict="OK", wall_s=round(time.time() - t0, 1))
        rep["stages"]["self_check"] = st
        return
    src = extract_code(reply)
    fixed, fixed_pova = script.with_name("checked.py"), pova.with_name("checked.pova")
    fixed.write_text(src, encoding="utf-8")
    if lint_imports(src):
        st.update(verdict="fix rejected (imports)")
    else:
        try:
            render_script(fixed, fixed_pova, conf)
            shutil.copy(fixed_pova, pova)
            shutil.copy(fixed, script)
            st.update(verdict="fixed")
        except RuntimeError as e:
            st.update(verdict="fix failed to render", error=str(e)[-200:])
    st["wall_s"] = round(time.time() - t0, 1)
    rep["stages"]["self_check"] = st


# ---------------------------------------------------------------- upload
def board_name(pova: Path) -> str:
    """The firmware takes names of 1-28 chars [A-Za-z0-9_.-] (valid_name): drop the timestamp prefix; a longer name
    becomes its first 23 chars + "_" + a 4-char hash, so two prompts that share a beginning ("... jet ski at sunset" /
    "... at sunrise") don't overwrite each other on the board (audit 2026-11-23, finding 5)."""
    name = re.sub(r"[^A-Za-z0-9_.-]", "_", re.sub(r"^\d{8}-\d{6}_", "", Path(pova).stem)).strip("_.-") or "anim"
    if len(name) <= 28:
        return name
    return name[:23].strip("_.-") + "_" + hashlib.sha1(name.encode()).hexdigest()[:4]


def board_limits(data: bytes) -> list[str]:
    """What the board would refuse in this file: size, frame count, palette size (header bytes 8-9 and 12)."""
    bad = []
    if len(data) > MAX_FILE:
        bad.append(f"{len(data)} B > {MAX_FILE} B")
    if len(data) >= 16 and data[:4] == b"POVA":
        if int.from_bytes(data[8:10], "little") > MAX_FRAMES:
            bad.append(f"{int.from_bytes(data[8:10], 'little')} frames > {MAX_FRAMES}")
        if data[12] > MAX_COLOURS:
            bad.append(f"{data[12]} colours > {MAX_COLOURS}")
    return bad


def upload_and_play(pova: Path, conf: dict, play: bool = True, wait: bool = False, name: str | None = None) -> dict:
    """Upload a .pova to the column and play it. A file over the board's 64 KiB is fitted first (fit_size, on a copy).
    wait=True polls GET /api/status until the board reports the animation loaded (it plays from the next 1/8-turn
    tick) or a load error, up to 5 s. Returns name/bytes/upload/play (+ upload_s, playing, load_ms, fit), or error."""
    import requests  # local import: the pipeline must work without network libs for --dry-run
    headers = {"X-POV-Token": conf.get("token", "")}
    base = conf["target"].rstrip("/")
    name = name or board_name(pova)
    data = Path(pova).read_bytes()
    out: dict = dict(name=name, bytes=len(data))
    if board_limits(data):                       # library / cache files skip main()'s fit: fit a copy here
        anim, notes = fit_size(povanim.Animation.read(pova))
        data = anim.to_bytes()
        out.update(fit=notes, bytes=len(data))
        if board_limits(data):
            return dict(out, error="the board would refuse it even after fitting: " + "; ".join(board_limits(data)))
    t0 = time.time()
    try:
        r = requests.post(f"{base}/api/anims", files={"file": (name + ".pova", data, "application/octet-stream")},
                          headers=headers, timeout=10)
    except requests.RequestException as e:   # the column is off, or not on the network
        return dict(out, error=f"no column at {base}: {type(e).__name__}")
    out.update(upload=r.status_code, upload_s=round(time.time() - t0, 2))
    if r.status_code != 200:
        return dict(out, error=f"upload refused: HTTP {r.status_code} {r.text[:160]}")
    if not play:
        return out
    try:
        r2 = requests.post(f"{base}/api/play", json={"name": name, "loop": True}, headers=headers, timeout=5)
    except requests.RequestException as e:
        return dict(out, error=f"play failed: {type(e).__name__}")
    out["play"] = r2.status_code
    if r2.status_code != 200:
        return dict(out, error=f"play refused: HTTP {r2.status_code} {r2.text[:160]}")
    if wait:
        out.update(wait_playing(base, name))
    return out


def play_only(name: str, conf: dict) -> dict:
    """POST /api/play for an animation already stored on the column (the pre-uploaded thinking loop)."""
    import requests
    try:
        r = requests.post(f"{conf['target'].rstrip('/')}/api/play", json={"name": name, "loop": True},
                          headers={"X-POV-Token": conf.get("token", "")}, timeout=5)
        return dict(name=name, play=r.status_code)
    except requests.RequestException as e:
        return dict(name=name, error=f"no column: {type(e).__name__}")


def wait_playing(base: str, name: str, timeout_s: float = 5.0) -> dict:
    """Firmware 0.4 queues /api/play; /api/status "load" goes queued -> busy -> ok (or err). Older builds play at once,
    so "anim" == name counts too."""
    import requests
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        try:
            st = requests.get(f"{base}/api/status", timeout=2).json()
        except (requests.RequestException, ValueError):
            st = {}
        ld = st.get("load") or {}
        if ld.get("name") == name and ld.get("state") == "ok" or (not ld and st.get("anim") == name):
            return dict(playing=True, load_ms=ld.get("ms"), wait_s=round(time.time() - t0, 2), rpm=st.get("rpm"))
        if ld.get("name") == name and ld.get("state") in ("err", "error"):
            return dict(playing=False, error=f"board could not load it: {ld.get('err')}", wait_s=round(time.time() - t0, 2))
        time.sleep(0.08)
    return dict(playing=None, wait_s=round(time.time() - t0, 2), note="not confirmed by /api/status within 5 s")


def column_status(conf: dict, timeout: float = 1.5) -> dict | None:
    import requests
    try:
        return requests.get(f"{conf['target'].rstrip('/')}/api/status", timeout=timeout).json()
    except (requests.RequestException, ValueError):
        return None


def ensure_on_board(anim, name: str, conf: dict) -> dict:
    """Store an animation on the column once (no play) unless the same size is already there: GET /api/anims."""
    import requests
    base, data = conf["target"].rstrip("/"), anim.to_bytes()
    try:
        have = requests.get(f"{base}/api/anims", timeout=3).json()
        if any(a.get("name") == name and a.get("bytes") == len(data) for a in have if isinstance(a, dict)):
            return dict(name=name, stored="already")
        r = requests.post(f"{base}/api/anims", files={"file": (name + ".pova", data, "application/octet-stream")},
                          headers={"X-POV-Token": conf.get("token", "")}, timeout=10)
        return dict(name=name, stored=r.status_code)
    except (requests.RequestException, ValueError) as e:
        return dict(name=name, error=f"no column: {type(e).__name__}")


# ---------------------------------------------------------------- main
def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:40] or "anim"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("prompt")
    ap.add_argument("--scope", choices=("home", "public"))
    ap.add_argument("--model", default=None)
    ap.add_argument("--script", default=None, help="use this scene script instead of asking Claude (gen_dog_ball.py works)")
    ap.add_argument("--character", default=None, help="with --script gen_dog_ball.py: dog|goose")
    ap.add_argument("--mode", default=None, help="with --script gen_dog_ball.py: orbit|front")
    ap.add_argument("--dry-run", action="store_true", help="no upload")
    ap.add_argument("--no-preview", action="store_true")
    ap.add_argument("--allow-home-on-air", action="store_true")
    ap.add_argument("--out-dir", default=None, help="write the .pova/.py/previews here instead of the scope's folder (tests, comparisons)")
    ap.add_argument("--effort", choices=("low", "medium", "high", "xhigh", "max"), default=None,
                    help="claude -p --effort for the generator call (default: the CLI's own)")
    ap.add_argument("--variant", default=None, help=f"generator prompt variant: {', '.join(VARIANTS)} (default v01)")
    ap.add_argument("--sys", choices=("stdin", "system"), default=None,
                    help="stdin = whole prompt as the user turn after Claude Code's own system prompt (v0.1); "
                         "system = generator prompt as --system-prompt-file (cacheable, smaller)")
    ap.add_argument("--report", default=None, help="also write the stage report JSON here")
    ap.add_argument("--no-log", action="store_true", help="do not append to pipeline/log.jsonl (benchmarks)")
    fl = ap.add_argument_group("speed lanes (2026-11-07)")
    fl.add_argument("--fast", action="store_true", help="preset: " + ", ".join(f"{k}={v}" for k, v in FAST.items()))
    fl.add_argument("--fastest", action="store_true", help="preset: --fast with template=llm (template first, code only "
                                                         "when the request does not fit)")
    fl.add_argument("--classic", action="store_true", help="no preset (the pre-11-07 pipeline); --fast is the default "
                                                         "since 2026-11-09")
    fl.add_argument("--autofix", action="store_true", help="zero-latency fixes: seam -> ping-pong, > 32 colours merged, "
                                                         "over-cap current -> meta gb")
    fl.add_argument("--template", choices=("off", "keyword", "llm"), default=None,
                    help="try a ready-made scenekit template first: keyword = instant regex match, llm = a small model "
                         "returns a JSON spec; falls back to code generation when the request does not fit")
    fl.add_argument("--template-model", default=None, help="model for --template llm (default Haiku)")
    fl.add_argument("--template-min-fit", type=int, default=2, help="minimum fit (0-3) to accept a template")
    fl.add_argument("--placeholder", action="store_true", help="show an instant keyword-template loop first")
    fl.add_argument("--no-placeholder", action="store_true", help="no placeholder, whatever the preset says (gap G13)")
    fl.add_argument("--placeholder-kind", choices=("keyword", "thinking"), default="keyword",
                    help="keyword = the keyword template scene; thinking = typing dots (the live-demo choice: the "
                         "audience never mistakes it for the AI's result)")
    fl.add_argument("--thinking-on-board", action="store_true", help=argparse.SUPPRESS)   # pov_serve stored it already
    fl.add_argument("--candidates", type=int, default=None, help="parallel generator calls; the first valid one wins")
    fl.add_argument("--self-check", action="store_true", help="one visual round: Claude sees 6 frames and fixes the script")
    fl.add_argument("--check-effort", default=None, help="effort for the self-check call")
    fl.add_argument("--cache", action="store_true", help="serve repeat requests (same content words) from library.jsonl")
    fl.add_argument("--no-cache", action="store_true", help="always generate, whatever the preset says (each take of "
                                                          "a shoot really runs the model)")
    fl.add_argument("--cache-dir", default=None, help="where library.jsonl lives (default: the output folder)")
    lv = ap.add_argument_group("live demo (2026-11-23)")
    lv.add_argument("--target", default=None, help="column URL (default: pov_config.json's target, or env POV_TARGET)")
    lv.add_argument("--wait-playing", action="store_true", help="after /api/play, poll /api/status until the board "
                                                              "reports the animation loaded (the step view's 'playing')")
    a = ap.parse_args(argv)
    conf = load_conf()
    if a.target:
        conf["target"] = a.target
    pre = FASTEST if a.fastest else {} if a.classic else FAST   # --fast is the default (Brian, 2026-11-09)
    model = a.model or pre.get("model") or conf["model"]
    effort = a.effort or pre.get("effort") or conf.get("effort")
    variant = a.variant or pre.get("variant") or conf.get("variant") or "v01"
    sys_mode = a.sys or pre.get("sys") or conf.get("sys") or "stdin"
    template_mode = a.template or pre.get("template") or "off"
    a.candidates = a.candidates or pre.get("candidates") or 1
    cache_on = (a.cache or bool(pre.get("cache"))) and not a.no_cache
    a.placeholder = (a.placeholder or bool(pre.get("placeholder"))) and not a.no_placeholder
    a.autofix = a.autofix or bool(pre.get("autofix"))
    stream = EVENT_SINK is not None and a.candidates == 1

    def generate(extra: str = "") -> tuple[str, dict]:
        system, user = build_prompts(a.prompt, scope, variant)
        emit("llm", "start", model=model, effort=effort, repair=bool(extra))
        on_text = (lambda s: emit("llm", "delta", text=s)) if stream else None
        on_think = (lambda: emit("llm", "thinking")) if stream else None
        if sys_mode == "system":
            return call_claude(user + extra, conf, model, effort, system=system, on_text=on_text, on_think=on_think)
        return call_claude(f"{system}\n{user}" + extra, conf, model, effort, on_text=on_text, on_think=on_think)
    t_start = time.time()
    rep: dict = dict(prompt=a.prompt, started=time.strftime("%Y-%m-%dT%H:%M:%S"), stages={})
    ph_thread = None

    def done(code: int) -> int:
        rep["total_s"], rep["exit"] = round(time.time() - t_start, 1), code
        if not a.no_log:
            with open(HERE / "log.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(rep) + "\n")
        if a.report:
            Path(a.report).write_text(json.dumps(rep, indent=1), encoding="utf-8")
        emit("done", "done" if code == 0 else "error", code=code, total_s=rep["total_s"], file=rep.get("file"),
             playable_s=rep.get("playable_s"), playing_s=rep.get("playing_s"), source=rep.get("source"),
             error=rep.get("refused") or rep.get("error"))
        print(json.dumps(rep, indent=1))
        return code

    scope, why = resolve_scope(a.prompt, a.scope, conf)
    rep["scope"], rep["scope_reason"] = scope, why
    if scope == "public":
        note = ip_check(a.prompt)
        if note:
            rep["refused"] = note
            emit("scope", "error", scope=scope, reason=why, error=note)
            return done(3)
    emit("scope", "done", scope=scope, reason=why)
    out_root = Path(a.out_dir) if a.out_dir else PUBLIC_DIR if scope == "public" else Path(conf["home_dir"])
    out_root.mkdir(parents=True, exist_ok=True)

    # 1. where does the animation come from?
    lib = fastlane.Library(Path(a.cache_dir) if a.cache_dir else out_root) if cache_on else None
    pova: Path | None = library_hit(a.prompt)
    hit, sim = (lib.lookup(a.prompt, scope) if (lib is not None and not pova and not a.script) else (None, None))
    if sim is not None:
        rep["cache_similarity"] = sim
    if pova:
        rep["source"] = f"library: {pova.name}"
        emit("source", "done", source="library", name=pova.name)
    elif hit:
        pova = Path(hit["file"])
        rep["source"] = f"cache: {pova.name} (\"{hit['prompt']}\")"
        emit("source", "done", source="cache", name=pova.name, prompt=hit["prompt"])
    else:
        work = Path(tempfile.mkdtemp(prefix="pov_"))
        script = work / "scene.py"
        if a.script and Path(a.script).name == "gen_dog_ball.py":
            # the worked example doubles as a parametrised generator
            ch, mode = a.character or ("goose" if "goose" in a.prompt.lower() else "dog"), a.mode or ("front" if "front" in a.prompt.lower() else "orbit")
            script.write_text(f"import sys\nsys.path.insert(0, r'{POVGEN}')\nfrom gen_dog_ball import build as _b\n"
                              f"def build():\n    return _b({ch!r}, {mode!r}, scope={scope!r})\n", encoding="utf-8")
            rep["source"] = f"script: gen_dog_ball.py ({ch}, {mode})"
        elif a.script:
            shutil.copy(a.script, script)
            rep["source"] = f"script: {a.script}"
        pova = work / (slugify(a.prompt) + ".pova")
        if a.placeholder:                       # something on the column within ~1 s while the real scene is made
            ph = show_placeholder(a.prompt, scope, work, conf, a.dry_run, kind=a.placeholder_kind,
                                  on_board=a.thinking_on_board)
            ph_thread = ph.pop("_thread", None)  # uploads in the background (G5); joined before the final upload
            rep["stages"]["placeholder"] = ph
            rep["placeholder_s"] = round(time.time() - t_start, 2)
            emit("placeholder", "done", kind=a.placeholder_kind, seconds=rep["placeholder_s"])
        src = None
        if not a.script and template_mode != "off":
            emit("template", "start", mode=template_mode)
            src = try_template(a.prompt, scope, template_mode, conf, rep, a.template_model, a.template_min_fit)
            emit("template", "done" if src else "skip", **{k: v for k, v in (rep["stages"].get("template") or {}).items()
                                                            if k in ("fit", "missing", "wall_s", "model")})
            if src:
                script.write_text(src, encoding="utf-8")
                rep["source"] = f"template ({template_mode})"
        if a.script or src:
            # 2. render in the sandbox (no repair round: the script is ours)
            t0 = time.time()
            emit("render", "start")
            try:
                rep["stages"]["render"] = dict(result=render_script(script, pova, conf), wall_s=round(time.time() - t0, 2))
                emit("render", "done", seconds=rep["stages"]["render"]["wall_s"],
                     pova_b64=_b64(pova) if EVENT_SINK is not None else None)
            except RuntimeError as e:
                rep["stages"]["render_error_0"] = str(e)[-600:]
                emit("render", "error", error=str(e)[-300:])
                if not src:
                    return done(5)
                src = None                      # a template that fails to render falls through to code generation
        res_val = None
        if not a.script and not src:
            # 2'. code generation: N candidates in parallel, each with its own repair round; first valid one wins
            res = codegen(a.candidates, generate, work, pova, conf, rep)
            if res is None:
                rep["error"] = rep.get("refused") or "the generated script did not render after the repair round"
                return done(rep.get("exit_code", 5))
            script = res["script"]
            rep["source"] = "claude -p"
            rep["stages"]["llm"] = dict(res["llm"], variant=variant, sys=sys_mode,
                                        prompt_sha=hashlib.sha1(a.prompt.encode()).hexdigest()[:8])
            res_val = res["val"]                # codegen validated this file already: don't pay for it twice
            if a.self_check:
                visual_check(a.prompt, scope, script, pova, generate, conf, rep, model, a.check_effort or effort)
                res_val = None
        # 3. check: indices, validate (current, framing, seam, flicker) + zero-latency auto-fixes
        t0 = time.time()
        if res_val is None:                     # codegen already announced (and ran) its validation
            emit("check", "start")
        anim = povanim.Animation.read(pova)
        mode = anim.meta.get("mode", "front")
        try:
            check_indices(anim)
            val = res_val or povanim.validate(anim, mode=mode)
        except Exception as e:                  # a --script/template file with a bad index lands here, not in a traceback
            rep["error"] = f"check failed: {type(e).__name__}: {e}"
            emit("check", "error", error=rep["error"])
            return done(5)
        rep["stages"]["validate"] = val
        fixes = []
        if not val["ok"] and a.autofix:
            anim, val2, fixes = auto_fix(anim, val, mode)
            if fixes:
                rep["stages"]["autofix"] = dict(fixes=fixes, validate=val2)
                val = val2
        if not val["ok"]:
            rep["warning"] = "validator warnings (kept; a production pipeline would run one fix round): " + "; ".join(val["warnings"])
        emit("check", "done", seconds=round(time.time() - t0, 2), peak_ma=val["current_peak_ma"], cap_ma=val["cap_ma"],
             gb=anim.meta.get("gb", 31), frames=anim.n, fps=anim.fps, duration_s=val["duration_s"], colours=val["palette"],
             in_window=val.get("front_window_fraction_min"), warnings=val["warnings"], fixes=fixes)
        # 4. pack: provenance, fit the board's 64 KiB / 256 frames / 32 colours (gap G1), file it by scope
        t0 = time.time()
        anim.meta.update(scope=scope, scope_reason=why, prompt=a.prompt, pipeline="pov_request.py v0.3",
                         generator=rep["source"], model=rep["stages"].get("llm", {}).get("model"))
        before = len(anim.to_bytes())
        anim, fit_notes = fit_size(anim)
        if fit_notes:
            rep["stages"]["fit"] = fit_notes
            val = povanim.validate(anim, mode=mode)          # merged colours can change the peak current
            peak = [w for w in val["warnings"] if w.startswith("peak current")]
            if peak:
                anim.meta["gb"] = val["gb_recommended"]
            rep["stages"]["fit_validate"] = dict(ok=val["ok"], warnings=val["warnings"], peak_ma=val["current_peak_ma"])
        final = out_root / (time.strftime("%Y%m%d-%H%M%S_") + pova.stem + ".pova") if scope == "home" else out_root / pova.name
        info = anim.write(final)
        shutil.copy(script, final.with_suffix(".py"))
        pova = final
        if lib is not None:
            lib.add(a.prompt, scope, final, rep["source"], val)
        emit("pack", "done", seconds=round(time.time() - t0, 2), bytes=info["bytes"], before_bytes=before,
             limit=MAX_FILE, frames=anim.n, fps=anim.fps, colours=len(anim.palette), fit=fit_notes,
             pova_b64=_b64(pova) if EVENT_SINK is not None else None)
    rep["file"] = str(pova)
    rep["playable_s"] = round(time.time() - t_start, 2)     # request -> .pova ready to upload
    code = 0
    # 5. upload + play, before the preview (gap G4); home content is not played while recording
    if a.dry_run:
        rep["upload"] = "dry-run"
        emit("upload", "skip", reason="dry run")
    elif scope == "home" and recording(conf) and not a.allow_home_on_air:
        rep["upload"] = "skipped: home-scope animation while OBS records"
        emit("upload", "skip", reason=rep["upload"])
    else:
        if ph_thread is not None:
            ph_thread.join(timeout=15)          # a slow placeholder upload must never land on top of the result
        name = board_name(pova)
        emit("upload", "start", name=name, bytes=pova.stat().st_size, target=conf["target"])
        up = upload_and_play(pova, conf, play=False, name=name)
        rep["upload"] = up
        if up.get("error"):
            rep["error"], code = up["error"], 6
            emit("upload", "error", error=up["error"], name=name)
        else:
            emit("upload", "done", seconds=up.get("upload_s"), bytes=up.get("bytes"), name=name, fit=up.get("fit"))
            pl = play_only(name, conf)
            up["play"] = pl.get("play")
            if pl.get("play") != 200:
                rep["error"], code = pl.get("error") or f"play refused: HTTP {pl.get('play')}", 6
                emit("playing", "error", error=rep["error"], name=name)
            else:
                if a.wait_playing:
                    up.update(wait_playing(conf["target"].rstrip("/"), name))
                rep["playing_s"] = round(time.time() - t_start, 2)
                if up.get("playing") is False:
                    rep["error"], code = up.get("error"), 7
                    emit("playing", "error", error=rep["error"], name=name)
                else:
                    emit("playing", "done", name=name, confirmed=bool(up.get("playing")), load_ms=up.get("load_ms"),
                         seconds=rep["playing_s"])
    # 6. preview, after the column already shows it
    if not a.no_preview:
        t0 = time.time()
        prev_dir = (pova.parent / "previews" / pova.stem) if scope == "public" else pova.parent / (pova.stem + "_preview")
        prev_dir.mkdir(parents=True, exist_ok=True)
        try:
            rep["stages"]["preview"] = dict(files=preview(pova, prev_dir), wall_s=round(time.time() - t0, 1))
        except (RuntimeError, subprocess.TimeoutExpired) as e:   # the animation is already up: report, don't crash
            rep["stages"]["preview"] = dict(error=str(e)[-300:], wall_s=round(time.time() - t0, 1))
    return done(code)


if __name__ == "__main__":
    sys.exit(main())
