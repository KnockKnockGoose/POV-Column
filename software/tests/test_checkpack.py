"""Regression tests from the check-pack-send audit (docs/2026-11-23-check-pack-send-audit.md). Offline: no Claude, no board.

    py -m pytest software/tests/test_checkpack.py -q

The firmware half compiles tools/cap_audit_host.cpp (the board's own pova.h / povframe.h check code) with the PlatformIO
MinGW g++ and is skipped where that compiler is missing. xfail = an open audit finding; it turns into a pass once fixed.
"""
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "povgen"))
sys.path.insert(0, str(HERE.parent / "pipeline"))

import checkpack_audit as ca  # noqa: E402
import checkpack_cases as cc  # noqa: E402
import povanim as pa  # noqa: E402
import pov_request as pr  # noqa: E402

FUSE_MA = 3000          # F1 as fitted (a 3 A fast-blow; the design's 4 A is on order)
BRIGHT = ("white_full", "red_full", "white_stripes4", "white_front_third")


@pytest.fixture(scope="module")
def fw(tmp_path_factory):
    """Every case through the firmware's check code: {case: harness result}."""
    out = tmp_path_factory.mktemp("cp")
    exe = ca.build_harness(out)
    if exe is None:
        pytest.skip("MinGW g++ not installed (PlatformIO toolchain-gccmingw32)")
    items, names = [], []
    for k, f in cc.CASES.items():
        p = out / f"cp_{k}.pova"
        f().write(p, sidecar=False)
        items.append(str(p))
        names.append(k)
    return dict(zip(names, ca.run_harness(exe, items)))


@pytest.mark.parametrize("case", BRIGHT)
def test_validator_flags_and_autofix_lands_under_the_cap(case):
    a = cc.build_case(case)
    v = pa.validate(a)
    assert any(w.startswith("peak current") for w in v["warnings"])
    a2, v2, fixes = pr.auto_fix(a, v, "front")
    assert 1 <= a2.meta["gb"] < 31
    assert v2["current_peak_ma"] <= pa.CAP_MA


def test_the_cap_uses_the_worst_angle_not_the_average():
    """White on every 4th column lights 25 % of the picture but all 336 LEDs at once at every 4th rotor angle."""
    stripes = pa.validate(cc.build_case("white_stripes4"))
    full = pa.validate(cc.build_case("white_full"))
    assert stripes["current_peak_ma"] == full["current_peak_ma"]
    assert stripes["gb_recommended"] == full["gb_recommended"]


@pytest.mark.parametrize("case", BRIGHT)
def test_firmware_cap_holds_and_real_current_stays_under_the_fuse(fw, case):
    r = fw[case]
    assert r["upload_http"] == 200 and r["load_err"] == ""
    fit = r["fit"]["31"]
    assert fit["leds_ma"] <= r["cap_ma"]                       # the firmware's own definition: LEDs + idle <= 2,600 mA
    a = cc.build_case(case)
    worst_real = ca.cal_profile(a, fit["gb_used"], ca.CAL["datasheet"]).max()   # 18 mA/colour, 1 mA idle, 170 mA ESP32
    assert worst_real < FUSE_MA


def test_white_is_clamped_to_3_of_31(fw):
    assert fw["white_full"]["fit"]["31"]["gb_used"] == 3
    assert fw["white_stripes4"]["fit"]["31"]["gb_used"] == 3


@pytest.mark.parametrize("case,http,err", [
    ("at_64k", 200, ""),
    ("over_64k_by_1", 400, "too big"),         # 400 not 413: see cap_audit_host.cpp (pova_check_feed / UP_BIG)
    ("noise_big", 413, "too big"),
    ("frames_257", 400, "bad header"),
    ("pal_33", 400, "bad header"),
    ("bad_index", 400, "palette index out of range"),
])
def test_firmware_upload_check(fw, case, http, err):
    r = fw[case]
    assert r["upload_http"] == http
    assert err in r["upload_err"]


def test_upload_names_are_valid_on_the_board(fw, tmp_path):
    exe = ca.build_harness(tmp_path)
    dark = tmp_path / "d.pova"
    cc.build_case("dark").write(dark, sidecar=False)
    rows = ca.names_check(exe, dark)
    assert all(r["firmware_valid_name"] for r in rows)
    assert all(1 <= r["length"] <= 28 for r in rows)


def test_different_prompts_get_different_board_names(tmp_path):
    """Audit P5, fixed in 802f9b7: names over 28 characters become the first 23 + "_" + a 4-character hash."""
    rows = ca.names_check(None, tmp_path / "unused.pova")
    assert not any(r["collides_with_other_prompt"] for r in rows)


def test_undefined_colour_number_is_a_clean_error():
    """Audit P2, fixed in 802f9b7: pov_request.check_indices turns it into a RuntimeError the repair round acts on."""
    a = cc.build_case("bad_index")
    with pytest.raises(RuntimeError, match="colour index 5"):
        pr.check_indices(a)


def test_pipeline_fits_every_file_to_the_board(fw):
    """Audit P3, fixed in 802f9b7: whatever the pipeline would upload passes the firmware's own upload check."""
    import tempfile
    for case in ("noise_big", "frames_257", "pal_33", "over_64k_by_1"):
        a, notes = pr.fit_size(cc.build_case(case))
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / f"{case}.pova"
            a.write(p, sidecar=False)
            exe = ca.build_harness(Path(td))
            r = ca.run_harness(exe, [str(p)])[0]
        assert r["upload_http"] == 200 and r["load_err"] == "", (case, notes, r)


def test_undefined_colour_number_through_the_pipeline(tmp_path):
    """pov_request.py --script on a scene with an undefined colour number: a clean exit and a report, not a traceback."""
    r = ca.dry_run("bad_index", tmp_path)
    assert "stderr_tail" not in r or not any("IndexError" in line for line in r["stderr_tail"]), r
