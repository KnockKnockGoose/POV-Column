"""Caption fonts for the POV column: an uppercase 5x7 face and a bold 7x9 face (2-pixel stems), proportional widths.

Single source of truth for the firmware: `py software/captions/font.py --header software/firmware/src/captions_font.h`
writes the glyph tables the ESP32's caption mode draws with (same pattern as povmap.h).

Captions are shown in UPPERCASE: capitals need no descenders, so a whole 7x9 line is 9 rows, and they read better at
5 mm pixels on camera. Charset: A-Z, 0-9, space and light punctuation . , ? ! ' - : % & $ / + # " ( ) =
Characters the 7x9 face does not draw fall back to the 5x7 glyph, vertically centred.
"""
from __future__ import annotations

import argparse

import numpy as np

G5 = {}   # char -> list of row strings, top row first ('#' lit)
G7 = {}


def _defs(table: dict, text: str, h: int):
    """Parse blocks: a line with the char in backquotes, then h rows."""
    lines = [ln for ln in text.strip("\n").split("\n")]
    i = 0
    while i < len(lines):
        ln = lines[i].strip()
        if not ln:
            i += 1
            continue
        assert ln.startswith("`") and ln.endswith("`"), ln
        ch = ln[1:-1]
        rows = [r.strip() for r in lines[i + 1:i + 1 + h]]
        assert len(rows) == h and len({len(r) for r in rows}) == 1, (ch, rows)
        table[ch] = rows
        i += 1 + h


_defs(G5, """
`A`
.###.
#...#
#...#
#####
#...#
#...#
#...#
`B`
####.
#...#
#...#
####.
#...#
#...#
####.
`C`
.###.
#...#
#....
#....
#....
#...#
.###.
`D`
###..
#..#.
#...#
#...#
#...#
#..#.
###..
`E`
#####
#....
#....
####.
#....
#....
#####
`F`
#####
#....
#....
####.
#....
#....
#....
`G`
.###.
#...#
#....
#.###
#...#
#...#
.####
`H`
#...#
#...#
#...#
#####
#...#
#...#
#...#
`I`
###
.#.
.#.
.#.
.#.
.#.
###
`J`
..###
...#.
...#.
...#.
...#.
#..#.
.##..
`K`
#...#
#..#.
#.#..
##...
#.#..
#..#.
#...#
`L`
#....
#....
#....
#....
#....
#....
#####
`M`
#...#
##.##
#.#.#
#.#.#
#...#
#...#
#...#
`N`
#...#
#...#
##..#
#.#.#
#..##
#...#
#...#
`O`
.###.
#...#
#...#
#...#
#...#
#...#
.###.
`P`
####.
#...#
#...#
####.
#....
#....
#....
`Q`
.###.
#...#
#...#
#...#
#.#.#
#..#.
.##.#
`R`
####.
#...#
#...#
####.
#.#..
#..#.
#...#
`S`
.####
#....
#....
.###.
....#
....#
####.
`T`
#####
..#..
..#..
..#..
..#..
..#..
..#..
`U`
#...#
#...#
#...#
#...#
#...#
#...#
.###.
`V`
#...#
#...#
#...#
#...#
#...#
.#.#.
..#..
`W`
#...#
#...#
#...#
#.#.#
#.#.#
#.#.#
.#.#.
`X`
#...#
#...#
.#.#.
..#..
.#.#.
#...#
#...#
`Y`
#...#
#...#
.#.#.
..#..
..#..
..#..
..#..
`Z`
#####
....#
...#.
..#..
.#...
#....
#####
`0`
.###.
#...#
#..##
#.#.#
##..#
#...#
.###.
`1`
.#.
##.
.#.
.#.
.#.
.#.
###
`2`
.###.
#...#
....#
...#.
..#..
.#...
#####
`3`
#####
...#.
..#..
...#.
....#
#...#
.###.
`4`
...#.
..##.
.#.#.
#..#.
#####
...#.
...#.
`5`
#####
#....
####.
....#
....#
#...#
.###.
`6`
..##.
.#...
#....
####.
#...#
#...#
.###.
`7`
#####
....#
...#.
..#..
.#...
.#...
.#...
`8`
.###.
#...#
#...#
.###.
#...#
#...#
.###.
`9`
.###.
#...#
#...#
.####
....#
...#.
.##..
`.`
.
.
.
.
.
.
#
`,`
..
..
..
..
..
.#
#.
`?`
.###.
#...#
....#
...#.
..#..
.....
..#..
`!`
#
#
#
#
#
.
#
`'`
#
#
.
.
.
.
.
`-`
....
....
....
####
....
....
....
`:`
.
.
#
.
.
#
.
`%`
##..#
##..#
...#.
..#..
.#...
#..##
#..##
`&`
.##..
#..#.
#.#..
.#...
#.#.#
#..#.
.##.#
`$`
..#..
.####
#.#..
.###.
..#.#
####.
..#..
`/`
....#
....#
...#.
..#..
.#...
#....
#....
`+`
.....
..#..
..#..
#####
..#..
..#..
.....
`#`
.#.#.
.#.#.
#####
.#.#.
#####
.#.#.
.#.#.
`"`
#.#
#.#
...
...
...
...
...
`(`
..#
.#.
#..
#..
#..
.#.
..#
`)`
#..
.#.
..#
..#
..#
.#.
#..
`=`
.....
.....
#####
.....
#####
.....
.....
""", 7)

_defs(G7, """
`A`
..###..
.##.##.
##...##
##...##
#######
##...##
##...##
##...##
##...##
`B`
######.
##...##
##...##
##...##
######.
##...##
##...##
##...##
######.
`C`
.#####.
##...##
##.....
##.....
##.....
##.....
##.....
##...##
.#####.
`D`
#####..
##..##.
##...##
##...##
##...##
##...##
##...##
##..##.
#####..
`E`
#######
##.....
##.....
##.....
######.
##.....
##.....
##.....
#######
`F`
#######
##.....
##.....
##.....
######.
##.....
##.....
##.....
##.....
`G`
.#####.
##...##
##.....
##.....
##..###
##...##
##...##
##...##
.#####.
`H`
##...##
##...##
##...##
##...##
#######
##...##
##...##
##...##
##...##
`I`
####
.##.
.##.
.##.
.##.
.##.
.##.
.##.
####
`J`
..#####
....##.
....##.
....##.
....##.
....##.
##..##.
##..##.
.####..
`K`
##...##
##..##.
##.##..
####...
###....
####...
##.##..
##..##.
##...##
`L`
##.....
##.....
##.....
##.....
##.....
##.....
##.....
##.....
#######
`M`
##...##
###.###
#######
##.#.##
##.#.##
##...##
##...##
##...##
##...##
`N`
##...##
###..##
###..##
####.##
##.####
##..###
##..###
##...##
##...##
`O`
.#####.
##...##
##...##
##...##
##...##
##...##
##...##
##...##
.#####.
`P`
######.
##...##
##...##
##...##
######.
##.....
##.....
##.....
##.....
`Q`
.#####.
##...##
##...##
##...##
##...##
##...##
##.####
##..##.
.###.##
`R`
######.
##...##
##...##
##...##
######.
##.##..
##..##.
##...##
##...##
`S`
.#####.
##...##
##.....
##.....
.#####.
.....##
.....##
##...##
.#####.
`T`
######
..##..
..##..
..##..
..##..
..##..
..##..
..##..
..##..
`U`
##...##
##...##
##...##
##...##
##...##
##...##
##...##
##...##
.#####.
`V`
##...##
##...##
##...##
##...##
##...##
##...##
.##.##.
..###..
...#...
`W`
##...##
##...##
##...##
##...##
##.#.##
##.#.##
#######
###.###
##...##
`X`
##...##
##...##
.##.##.
.##.##.
..###..
.##.##.
.##.##.
##...##
##...##
`Y`
##...##
##...##
.##.##.
.##.##.
..###..
..###..
..###..
..###..
..###..
`Z`
#######
.....##
....##.
...##..
..##...
.##....
##.....
##.....
#######
`0`
.#####.
##...##
##..###
##.#.##
##.#.##
###..##
##...##
##...##
.#####.
`1`
..##..
.###..
####..
..##..
..##..
..##..
..##..
..##..
######
`2`
.#####.
##...##
.....##
.....##
....##.
..###..
.##....
##.....
#######
`3`
.#####.
##...##
.....##
.....##
..####.
.....##
.....##
##...##
.#####.
`4`
....##.
...###.
..####.
.##.##.
##..##.
#######
....##.
....##.
....##.
`5`
#######
##.....
##.....
######.
.....##
.....##
.....##
##...##
.#####.
`6`
.#####.
##...##
##.....
##.....
######.
##...##
##...##
##...##
.#####.
`7`
#######
.....##
....##.
...##..
..##...
..##...
..##...
..##...
..##...
`8`
.#####.
##...##
##...##
##...##
.#####.
##...##
##...##
##...##
.#####.
`9`
.#####.
##...##
##...##
##...##
.######
.....##
.....##
##...##
.#####.
`.`
..
..
..
..
..
..
..
##
##
`,`
..
..
..
..
..
..
##
##
#.
`?`
.#####.
##...##
.....##
....##.
...##..
...##..
.......
...##..
...##..
`!`
##
##
##
##
##
##
..
##
##
`'`
##
##
#.
..
..
..
..
..
..
`-`
.....
.....
.....
.....
#####
.....
.....
.....
.....
`:`
..
..
##
##
..
..
##
##
..
""", 9)

FONTS = {"5x7": (G5, 7), "7x9": (G7, 9)}
SPACE_W = {"5x7": 3, "7x9": 4}      # width of a space
GAP = 1                              # columns between glyphs


def glyph(ch: str, font: str) -> np.ndarray:
    """(h, w) bool array, top row first. Unknown characters -> None."""
    table, h = FONTS[font]
    if ch == " ":
        return np.zeros((h, SPACE_W[font]), bool)
    rows = table.get(ch)
    if rows is None and font == "7x9" and ch in G5:      # fall back to the 5x7 glyph, vertically centred
        g = glyph(ch, "5x7")
        out = np.zeros((9, g.shape[1]), bool)
        out[1:8] = g
        return out
    if rows is None:
        return None
    return np.array([[c == "#" for c in r] for r in rows], bool)


CHARSET = sorted(set(G5) | {" "})


def text_width(text: str, font: str) -> int:
    gs = [glyph(c, font) for c in text]
    gs = [g for g in gs if g is not None]
    return sum(g.shape[1] for g in gs) + GAP * max(0, len(gs) - 1)


def rasterize(text: str, font: str) -> np.ndarray:
    """(h, W) bool bitmap of a line, top row first."""
    gs = [g for g in (glyph(c, font) for c in text) if g is not None]
    h = FONTS[font][1]
    if not gs:
        return np.zeros((h, 0), bool)
    parts = []
    for i, g in enumerate(gs):
        if i:
            parts.append(np.zeros((h, GAP), bool))
        parts.append(g)
    return np.concatenate(parts, axis=1)


# ---------------------------------------------------------------- firmware header
def write_header(path: str) -> None:
    """captions_font.h: per font, per ASCII 32..95 a width and up to 7 column words (bit 0 = TOP row)."""
    lines = ["// Generated by software/captions/font.py - do not edit by hand.",
             "// Caption fonts: uppercase 5x7 and bold 7x9, proportional. Column-major, bit 0 = top row.",
             "#pragma once", "#include <stdint.h>",
             "#define CAPF_FIRST 32", "#define CAPF_LAST 95", "#define CAPF_MAXW 7", f"#define CAPF_GAP {GAP}",
             "struct CapGlyph { uint8_t w; uint16_t col[CAPF_MAXW]; };"]
    for name, (_, h) in FONTS.items():
        ident = "CAPF_" + name.replace("x", "X")
        lines.append(f"#define {ident}_H {h}")
        lines.append(f"static const CapGlyph {ident}[CAPF_LAST - CAPF_FIRST + 1] = {{")
        for code in range(32, 96):
            g = glyph(chr(code), name)
            if g is None:
                lines.append(f"  {{0, {{0}}}},  // '{chr(code)}' (not drawn)" if chr(code) != "\\" else "  {0, {0}},  // backslash (not drawn)")
                continue
            cols = [sum(int(g[r, c]) << r for r in range(h)) for c in range(g.shape[1])]
            esc = chr(code) if chr(code) not in "\\" else "backslash"
            lines.append(f"  {{{g.shape[1]}, {{{', '.join(f'0x{v:03X}' for v in cols)}}}}},  // '{esc}'")
        lines.append("};")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


def _demo():
    for font in ("5x7", "7x9"):
        bm = rasterize("HELLO, 2026?", font)
        print("\n".join("".join("#" if v else "." for v in row) for row in bm), "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--header")
    a = ap.parse_args()
    if a.header:
        write_header(a.header)
        print("written", a.header)
    else:
        _demo()
