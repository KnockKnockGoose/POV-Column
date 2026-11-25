"""Offline checks for the 2026-11-07 speed lanes (scenekit, templates, cache, placeholder). No model calls:
call_claude is replaced by a guard that fails the test if anything tries to reach Claude.

    py -m pytest software/tests/test_pipeline_fast.py -q
"""
import json
import os
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SOFTWARE = HERE.parent
sys.path.insert(0, str(SOFTWARE / "povgen"))
sys.path.insert(0, str(SOFTWARE / "pipeline"))

import fastlane  # noqa: E402
import povanim  # noqa: E402
import pov_request as pr  # noqa: E402
import scenekit as sk  # noqa: E402

SPECS = {
    "jetski": dict(subject="bichon", action="ride", vehicle="jetski", background="sunset", effects=["sun", "splash"]),
    "shades": dict(subject="bichon_head", action="portrait", background="sunset", effects=["shades_gag"], seconds=6),
    "goose": dict(subject="goose", action="ride", vehicle="skateboard", background="day", scenery="road"),
    "fireworks": dict(subject="none", background="night", scenery="city", effects=["fireworks"], seconds=6),
    "laser": dict(subject="cat", action="chase", target="laser", scenery="floor"),
    "dog_ball": dict(subject="dog", action="chase", target="ball", background="day", scenery="grass"),
    "bichon_surf": dict(subject="bichon", action="ride", vehicle="surfboard", background="day", scenery="sea"),
    "orbit": dict(subject="goose", action="run", scenery="grass", mode="orbit"),
}


@pytest.fixture(autouse=True)
def no_claude(monkeypatch):
    def guard(*a, **k):
        raise AssertionError("test tried to call Claude")
    monkeypatch.setattr(pr, "call_claude", guard)
    monkeypatch.setattr(pr, "call_claude_image", guard)


@pytest.mark.parametrize("name", sorted(SPECS))
def test_compose_specs_are_valid(name):
    anim = sk.compose(dict(SPECS[name], prompt=name))
    v = povanim.validate(anim, mode=anim.meta["mode"])
    assert v["ok"], v["warnings"]
    assert len(anim.palette) <= 32
    assert anim.n % 8 == 0 and 2.0 <= anim.duration_s <= 10.0


def test_compose_never_raises_on_odd_specs():
    for spec in ({}, {"subject": "unicorn"}, {"action": "ride", "vehicle": "rocket"}, {"seconds": 99, "mode": "spin"},
                 {"subject": "cat", "target": "laser", "facing": -1}):
        anim = sk.compose(spec)
        assert anim.n >= 8


def test_frames_loop_adds_every_frame():
    sc = sk.Scene("x", seconds=1, fps=15)
    for k, t, cv in sc.frames():
        cv.px(0, k, sc.col("a", (10, 20, 30)))
    assert sc.done().n == 15


@pytest.mark.parametrize("prompt,subject,extra", [
    ("a fluffy white bichon frise riding a jet ski over waves, looped, for the video", "bichon", {"vehicle": "jetski"}),
    ("a goose skateboarding", "goose", {"vehicle": "skateboard"}),
    ("a cat chasing a laser dot", "cat", {"target": "laser"}),
    ("fireworks over a city skyline", "none", {"scenery": "city"}),
    ("a big fluffy bichon frise head; a paw comes up and slides dark black sunglasses on", "bichon_head", {}),
])
def test_keyword_specs(prompt, subject, extra):
    spec, fit = fastlane.spec_from_keywords(prompt)
    assert fit >= 2 and spec["subject"] == subject
    for k, v in extra.items():
        assert spec[k] == v


def test_keyword_lane_admits_what_it_cannot_draw():
    assert fastlane.spec_from_keywords("a dog driving a car")[1] == 1
    assert fastlane.spec_from_keywords("a dragon breathing fire")[1] == 0
    assert fastlane.spec_from_keywords("a rocket launching into space")[1] == 0


def test_parse_spec_reply_is_robust():
    spec, fit, missing = fastlane.parse_spec_reply('```json\n{"fit": 3, "spec": {"subject": "cat"}, "missing": ""}\n```')
    assert fit == 3 and spec == {"subject": "cat"}
    assert fastlane.parse_spec_reply("no idea")[1] == 0
    assert fastlane.parse_spec_reply('{"fit": "lots", "spec": []}')[:2] == ({}, 0)
    assert fastlane.parse_spec_reply('{"fit": 9, "spec": {}}')[1] == 3


def test_template_script_renders_in_the_sandbox(tmp_path):
    src = fastlane.template_script(dict(SPECS["goose"], vehicle=None), "a goose", "public")
    assert pr.lint_imports(src) == []
    script = tmp_path / "scene.py"
    script.write_text(src, encoding="utf-8")
    out = pr.render_script(script, tmp_path / "x.pova", pr.load_conf())
    assert out.startswith("OK")


def test_lint_allows_future_and_rejects_os():
    assert pr.lint_imports("from __future__ import annotations\nimport math\nfrom scenekit import *\n") == []
    assert "os" in pr.lint_imports("import os\n")


def test_kit_prompt_example_renders(tmp_path):
    md = (SOFTWARE / "pipeline" / "prompts" / "generator_kit.md").read_text(encoding="utf-8")
    ex = re.findall(r"## Example\n```python\n(.*?)```", md, re.S)[0]
    assert pr.lint_imports(ex) == []
    script = tmp_path / "ex.py"
    script.write_text(ex, encoding="utf-8")
    pr.render_script(script, tmp_path / "ex.pova", pr.load_conf())
    anim = povanim.Animation.read(tmp_path / "ex.pova")
    assert povanim.validate(anim, mode="front")["ok"]


def test_library_cache_round_trip(tmp_path):
    lib = fastlane.Library(tmp_path)
    f = tmp_path / "a.pova"
    f.write_bytes(b"x")
    lib.add("a goose skateboarding", "public", f, "test")
    hit, s = lib.lookup("a goose skateboarding, looped", "public")
    assert hit and s >= 0.75
    assert lib.lookup("a goose skateboarding", "home")[0] is None          # scopes never mix
    assert lib.lookup("a cat skateboarding", "public")[0] is None


def test_keyword_lane_end_to_end_without_claude(tmp_path):
    rep_path = tmp_path / "rep.json"
    code = pr.main(["a goose skateboarding", "--scope", "public", "--dry-run", "--no-preview", "--no-log",
                    "--template", "keyword", "--placeholder", "--cache", "--out-dir", str(tmp_path), "--report", str(rep_path)])
    rep = json.loads(rep_path.read_text(encoding="utf-8"))
    assert code == 0 and rep["source"] == "template (keyword)"
    assert rep["placeholder_s"] < 2 and rep["playable_s"] < 10
    # the same request again is served from the library cache
    code = pr.main(["a goose skateboarding", "--scope", "public", "--dry-run", "--no-preview", "--no-log", "--cache",
                    "--template", "keyword", "--out-dir", str(tmp_path), "--report", str(rep_path)])
    rep = json.loads(rep_path.read_text(encoding="utf-8"))
    assert code == 0 and rep["source"].startswith("cache:")


def test_auto_fix_seam_palette_and_current():
    sc = sk.Scene("seam test", seconds=2, fps=15)
    for k, t, cv in sc.frames():                       # a dot that jumps back at the loop end + 40 colours
        cv.disc(20, 10 + 2 * k, 2, sc.col(f"c{k % 40}", (200, 6 * (k % 40), 50)))
        for j in range(40):
            cv.px(0, j * 2, sc.col(f"c{j}", (200, 6 * j, 50)))
    anim = sc.done()
    val = povanim.validate(anim, mode="orbit")
    assert any("loop seam" in w for w in val["warnings"]) and any("palette" in w for w in val["warnings"])
    anim, v2, fixes = pr.auto_fix(anim, val, "orbit")
    assert anim.n == 2 * 30 - 2 and len(anim.palette) <= 32
    assert not any("loop seam" in w or "palette" in w for w in v2["warnings"]), v2["warnings"]
    assert len(fixes) == 2
