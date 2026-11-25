"""Fast lanes for pov_request.py (2026-11-07 speed investigation): a scene library cache, a keyword template matcher
(no LLM, milliseconds), the LLM template picker (the model returns a small JSON spec instead of code) and the
scenekit `compose(spec)` script that renders a spec.

Lane order in pov_request.py with --fast: library cache -> template (keyword or LLM spec, if it fits) -> code
generation with the scenekit prompt. With --placeholder the keyword template is shown at once while the real scene
is generated.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

STOP = set("a an the of on in at with and to for over under by from its it is my me please make show play some "
           "looped loop video public youtube channel camera pov column animation scene like start".split())


def words(prompt: str) -> set[str]:
    out = set()
    for w in re.findall(r"[a-z]+", prompt.lower()):
        if w in STOP or len(w) < 2:
            continue
        for suf in ("ing", "es", "s"):
            if w.endswith(suf) and len(w) - len(suf) >= 3:
                w = w[: -len(suf)]
                break
        out.add(w)
    return out


# ---------------------------------------------------------------- library cache
class Library:
    """Append-only index of generated scenes (library.jsonl next to them). A repeat request is served from disk with
    no LLM call: same scope and the same content words after stop words and plural/-ing endings, so "Biscuit riding a
    jet ski" == "biscuit rides the jet ski". Since 2026-11-23 a Jaccard score alone is not enough (gap G12): "a dog on
    a jet ski at night" scored 0.75 against "a dog on a jet ski" and replayed the day scene."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.index = self.root / "library.jsonl"

    def entries(self) -> list[dict]:
        if not self.index.exists():
            return []
        out = []
        for line in self.index.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if Path(e.get("file", "")).exists():
                out.append(e)
        return out

    def lookup(self, prompt: str, scope: str, threshold: float = 0.75) -> tuple[dict | None, float]:
        """Returns (entry, 1.0) for the newest entry with the same content words, else (None, best Jaccard score).
        `threshold` is kept for callers; an exact word-set match always clears it."""
        w = words(prompt)
        best_s, same = 0.0, None
        for e in self.entries():
            if e.get("scope") != scope:
                continue
            ew = set(e.get("words", []))
            best_s = max(best_s, len(w & ew) / max(1, len(w | ew)))
            if w and ew == w:
                same = e                                   # entries are oldest first: the newest repeat wins
        return (same, 1.0) if same is not None and threshold <= 1.0 else (None, round(best_s, 2))

    def add(self, prompt: str, scope: str, file: Path, source: str, quality: dict | None = None) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        e = dict(prompt=prompt, words=sorted(words(prompt)), scope=scope, file=str(file), source=source,
                 created=time.strftime("%Y-%m-%dT%H:%M:%S"), validator_ok=(quality or {}).get("ok"))
        with open(self.index, "a", encoding="utf-8") as f:
            f.write(json.dumps(e) + "\n")


# ---------------------------------------------------------------- keyword template (no LLM)
SUBJECTS = [("bichon", r"bichon|biscuit|fluffy white dog|white fluffy dog|poodle|maltese"), ("goose", r"goose|geese|duck|swan"),
            ("cat", r"\bcats?\b|kitten|kitty|tabby"), ("dog", r"\bdogs?\b|pupp|beagle|hound|doggo")]
VEHICLES_RE = [("jetski", r"jet ?ski|waverunner|jetski"), ("skateboard", r"skate"), ("surfboard", r"surf")]
TARGETS = [("laser", r"laser"), ("ball", r"\bball"), ("butterfly", r"butterfl")]
BACKGROUNDS = [("sunset", r"sunset|sundown|golden hour"), ("night", r"night|firework|stars|moon"),
               ("dusk", r"dusk|twilight"), ("day", r"\bday|sunny|sky|beach|park|outside")]
SCENERY = [("sea", r"sea|ocean|wave|water|lake|beach"), ("city", r"city|skyline|town|building"),
           ("road", r"road|street|skate"), ("snow", r"snow|winter"), ("sand", r"sand|desert"),
           ("floor", r"floor|room|house|kitchen|laser"), ("hills", r"hill|mountain|field"), ("grass", r"grass|park|garden")]
EFFECTS = [("fireworks", r"firework"), ("sparkles", r"sparkl|glitter|magic"), ("confetti", r"confetti|party|celebrat"),
           ("hearts", r"heart|love"), ("splash", r"splash|jump"), ("speed_lines", r"fast|speed|zoom|race"),
           ("clouds", r"cloud"), ("shades_gag", r"sunglass|shades"), ("sun", r"\bsun\b|sunny"), ("moon", r"moon")]
# Words the templates cannot show: if one of these is the point of the request, the keyword lane must not claim it.
UNCOVERED = r"\b(car|truck|rocket|plane|dragon|robot|unicorn|horse|bird|fish|shark|whale|tree|flower|text|word|letter|" \
            r"number|clock|heart beat|spaceship|planet|rainbow|train|bike|bicycle|ghost|pumpkin|santa|snowman|person|man|" \
            r"woman|kid|child|guitar|piano|pizza|cake)\b"


def _first(table, low):
    for name, rx in table:
        if re.search(rx, low):
            return name
    return None


def spec_from_keywords(prompt: str) -> tuple[dict, int]:
    """Instant spec from keywords. fit: 3 = subject + every recognised object covered, 2 = covered with defaults,
    1 = something important is outside the vocabulary, 0 = no subject or effect recognised."""
    low = prompt.lower()
    subj = _first(SUBJECTS, low)
    veh = _first(VEHICLES_RE, low)
    target = _first(TARGETS, low)
    bg = _first(BACKGROUNDS, low)
    scen = _first(SCENERY, low)
    fx = [n for n, rx in EFFECTS if re.search(rx, low)]
    spec: dict = {}
    if "shades_gag" in fx or (subj == "bichon" and re.search(r"\bhead|face|portrait|close", low)):
        spec = dict(subject="bichon_head", action="portrait", background=bg or "sunset", effects=fx, seconds=6)
    elif subj:
        action = "ride" if veh else "chase" if (target or re.search(r"chas", low)) else "run" if re.search(r"run|race", low) else "run"
        spec = dict(subject=subj, action=action, vehicle=veh, target=target or ("ball" if action == "chase" else None),
                    background=bg or ("sunset" if veh == "jetski" else "day" if scen not in (None, "floor") or veh else "none"),
                    scenery=scen, effects=fx)
    elif fx:
        spec = dict(subject="none", action="none", background=bg or "night", scenery=scen or ("city" if "fireworks" in fx else None),
                    effects=fx, seconds=6 if "fireworks" in fx else 4)
    spec = {k: v for k, v in spec.items() if v not in (None, [], "")}
    if not spec:
        return {}, 0
    uncovered = re.search(UNCOVERED, low)
    fit = 1 if uncovered else 3 if (subj or fx) and (veh or target or bg or scen or fx) else 2
    if uncovered:
        spec["_missing"] = uncovered.group(0)
    return spec, fit


# ---------------------------------------------------------------- LLM template (JSON spec instead of code)
def parse_spec_reply(text: str) -> tuple[dict, int, str]:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {}, 0, "no JSON"
    try:
        j = json.loads(m.group(0))
    except ValueError:
        return {}, 0, "bad JSON"
    spec = j.get("spec") if isinstance(j.get("spec"), dict) else {}
    try:
        fit = int(j.get("fit", 0))
    except (TypeError, ValueError):
        fit = 0
    return spec, max(0, min(3, fit)), str(j.get("missing", ""))[:120]


def template_script(spec: dict, prompt: str, scope: str) -> str:
    """The scene script for a spec: three lines against scenekit.compose (rendered by the same sandbox runner)."""
    spec = {k: v for k, v in spec.items() if not k.startswith("_")}
    spec.update(prompt=prompt, scope=scope)
    return ("from scenekit import compose\n\n"
            f"SPEC = {spec!r}\n\n\n"
            "def build():\n    return compose(SPEC)\n")


# ---------------------------------------------------------------- contact strip (self-check round, benchmark judging)
def contact_strip(pova: Path, out: Path, k: int = 6, scale: int = 3) -> Path:
    """k frames spread over the loop, each the full flat 96 x 42 grid (row 0 at the bottom) upscaled with a faint LED
    grid, side by side in one PNG."""
    import numpy as np
    from PIL import Image
    import povanim
    anim = povanim.Animation.read(pova)
    idx = sorted({round(i * (anim.n - 1) / max(1, k - 1)) for i in range(k)}) if anim.n > 1 else [0]
    ims = []
    for i in idx:
        rgb = anim.rgb(i)[::-1]
        big = np.kron(rgb, np.ones((scale, scale, 1), dtype=np.uint8))
        big[scale - 1::scale, :, :] //= 3
        big[:, scale - 1::scale, :] //= 3
        ims.append(Image.fromarray(big.astype("uint8")))
    w, h = ims[0].size
    sheet = Image.new("RGB", (len(ims) * (w + 4), h), (40, 40, 48))
    for j, im in enumerate(ims):
        sheet.paste(im, (j * (w + 4), 0))
    sheet.save(out)
    return Path(out)
