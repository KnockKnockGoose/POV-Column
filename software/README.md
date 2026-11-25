# Software

Everything between a sentence and the LEDs. It all runs on a PC with Python (3.11 or newer; numpy and Pillow for the
core, see [`requirements.txt`](../requirements.txt)), except the firmware, which is a PlatformIO project for the
ESP32. The examples use `py`, the Windows launcher; use `python3` elsewhere.

| Folder | What | State |
|---|---|---|
| [`povgen/povanim.py`](povgen/povanim.py) | **The one source of truth for the display**: geometry, the LED to (row, column) map (exported to the firmware as `povmap.h`), a small drawing DSL (Canvas, Sprite, Palette), the `.pova` file format, and the validator (loop seam, current at the worst rotor angle, front-window framing, flicker) | tested |
| `povgen/scenekit.py`, `biscuit_kit.py`, `columnkit.py`, `characters.py`, `bichon_head.py` | **The kits**: tested building blocks a scene script is written against. Skies, sea, ground, weather, characters with anchor points (mouth, back, feet), props, vehicles, a drawing of the column itself | tested through the pipeline |
| `povgen/gen_dog_ball.py` | The worked example the generator prompt shows the model, and the command that regenerates `povmap.h` | tested |
| [`examples/test_pattern.py`](examples/test_pattern.py) | A neutral test pattern: the smallest complete scene script | tested |
| [`povsim/simulate.py`](povsim/simulate.py) | The simulator: unwrapped view, perspective cylinder, a camera-shutter model (1/30 s shows the picture, 1/2000 s shows the strips), GIF and MP4 | tested |
| [`pipeline/pov_request.py`](pipeline/pov_request.py) | **Prompt to light**: scope guard, the language-model call (or a script, or a cached result), sandbox render, validate, fit to 64 KB, upload, play | runs the column |
| `pipeline/pov_serve.py`, `stepview.html` | A warm-process server and a live page that shows each stage as it happens (server-sent events) | used for the video |
| `pipeline/infinite_biscuit.py` | An endless gallery: every two laps the character does something new, written by the model while the current clip plays | used for the video |
| `pipeline/fastlane.py`, `prompts/` | The template fast path and the system prompts | |
| [`games/orbit_rally.py`](games/orbit_rally.py) | Orbit Rally: a one-player paddle game streamed to the column's live mode over a WebSocket | tested against the mock board; played on the column |
| [`captions/`](captions/README.md) | Live captions: streaming speech recognition to words on the column | works in the simulator |
| [`firmware/`](firmware/README.md) | The ESP32 firmware and its PC tools (OTA uploader with verification, control, live frames, a soak test, a mock board) | 0.4 runs the column |
| `elec/` | The scripts that draw the schematics, the carrier layout and the wiring guide's figures in `docs/img/` | |
| `tests/` | `py -m pytest software/tests -q` | 99 tests |

The animations from the videos are not in this repository. The pipeline writes what it makes into
`software/content/` and your local app-data folder, both ignored by git.

## 1. Draw something and look at it (no hardware)

```
py software/examples/test_pattern.py
py software/povsim/simulate.py software/out/test_pattern/test_pattern.pova --stills --gif --mp4
```

A scene script is a Python file with a `build()` function that returns an `Animation`: a palette and a list of
42 x 96 frames of palette indices. `test_pattern.py` is about 115 lines and uses only the base DSL. The kits sit on top of
it, so a script written against them is usually 15 to 20 lines.

The validator's report is the interesting part. For every frame it works out the current at each of the 96 rotor
angles (a full-circle band of colour lights 8 LEDs per row at *every* angle, which is why the pattern's bands are
only two rows tall) and compares the worst one with the 2.6 A cap. An average would be wrong by a factor of three
for stripes: see [the audit](../docs/2026-11-23-check-pack-send-audit.md), section 3.3.

## 2. Send it to a column, or to a stand-in

`firmware/tools/mock_board.py` is a PC stand-in for the board's web API, WebSocket and OTA receiver. Everything below
works against it.

```
py software/firmware/tools/mock_board.py --http-port 18091 --no-arduino-ota
py software/pipeline/pov_request.py "test pattern" --script software/examples/test_pattern.py --target http://127.0.0.1:18091 --out-dir software/out/demo --no-log --no-preview --wait-playing
```

For a real column, `--target http://pov.local` (or its address), or copy `pipeline/pov_config.example.json` to
`pov_config.json` and set it once. The firmware tools take `--host` or the `POV_HOST` environment variable.

## 3. Let a model write the scene

This step runs [Claude Code](https://claude.com/claude-code) head-less (`claude -p`) under your own login. There is
no API key in this project.

```
py software/pipeline/pov_request.py "a goose on a skateboard at sunset" --target http://127.0.0.1:18091 --wait-playing
py software/pipeline/pov_serve.py --preset fast --target http://127.0.0.1:18091 --open
```

- The default is the fast path from the video (the same as `--fast`): an instant placeholder, then a smaller model
  at low effort writes a short script against the kit. `--classic` is the original path: a larger model writes
  everything from the base DSL and takes about a minute.
- The script runs in a subprocess with a time limit and may only produce frames. That catches honest mistakes. It is
  not a security boundary against a hostile model, and the code says so.
- Every request is checked and fitted before it is sent: at most 256 frames, 32 colours, 64 KB, a name of 28
  characters, peak current under the cap.
- Requests for recognisable third-party characters are refused in "public" scope with a suggestion for an original
  one. The scope rules are at the top of `pov_request.py`.
- `pov_serve.py` keeps a model process warm between requests and serves the step view on port 8790. With
  `--f9 all --inbox <folder>` it watches the inbox of [BrianDump](https://github.com/KnockKnockGoose/BrianDump), my
  push-to-talk tool, which is how the voice part works in the video. Anything else can send it text:
  `POST /pov` with `{"prompt": "..."}`.

Measured: a median of 4.7 s from sentence to playable file over 48 gallery clips, and about 4 s from prompt to
playing for a request the kit covers, on a warm process. A request the kit does not cover takes 9 to 20 s. Details
and logs: [live-demo report](../docs/2026-11-23-live-demo-pipeline.md),
[Infinite Biscuit report](../docs/2026-11-23-infinite-biscuit.md).

## 4. Play the game

```
py software/games/orbit_rally.py --sim          # a window on the PC, arrow keys or W/S
py software/games/orbit_rally.py --keys         # the same, streamed to the column
py software/games/orbit_rally.py --selftest     # a bot plays head-less: frames and current under the cap
```

One paddle on the front of the column, and a ball that goes right round the back. `--pot` reads a knob from the
control box on my desk over a local UDP port; it is the only part that needs my own hardware. Raw live frames are 4,032 bytes each, so the frame rate is whatever the Wi-Fi link gives: 5 to
12 frames a second at the 20 to 50 kB/s I measured to the rotor. Report: [Orbit Rally](../docs/2026-11-24-orbit-rally.md).

## 5. The firmware

[`firmware/README.md`](firmware/README.md) has one command per job. In short:

```
cd software/firmware
copy src\wifi_secrets.example.h src\wifi_secrets.h        (then fill it in; it is ignored by git)
tools\pio.cmd run -e pov                                  build
tools\pio.cmd run -e pov -t upload                        first flash, over USB
py tools\ota_flash.py --env pov                           every later flash, over Wi-Fi, verified
tools\pio.cmd test -e native                              the unit tests of the core, on the PC
```

`tools\pio.cmd` is a Windows wrapper around PlatformIO that expects it in `C:\pio`. On another system, plain
`pio run -e pov` does the same job. The core logic (`lib/povcore`: LED map, frame builder, scheduler, file parser,
fonts, captions) is plain C++14 with no FreeRTOS in it, so it compiles and is tested on the PC against vectors that
the Python reference generates (`test/gen_vectors.py`).

By default the board takes an address from your router and answers as `pov.local`. A fixed address is four optional
lines in `wifi_secrets.h` (the example file shows them).

A prebuilt image is attached to each release. It has placeholder Wi-Fi settings, so it starts its own access point.
Read [SECURITY.md](../SECURITY.md) before you use it for more than a first test.

## The `.pova` file

Header (16 bytes: magic `POVA`, version, flags, 42, 96, frame count, fps x 10, palette size, meta length), a JSON
meta block, the palette (3 bytes per colour), then each frame as a hold count and run-length pairs along the rows,
and a CRC-32 at the end. `povanim.py` (`Animation.to_bytes` / `from_bytes`) and `firmware/lib/povcore/pova.h` are
the two implementations, and the firmware tests check that they agree. The board checks a file while it streams in,
and again when it loads it.

## Where things are honest about their limits

- The current cap is enforced for animations. The live-frame, text and caption paths have small known gaps
  (findings F1 to F3 in [the audit](../docs/2026-11-23-check-pack-send-audit.md)).
- Firmware 0.4 does not compress live frames. A run-length version exists on a branch in my private repository and
  has not been flashed, so it is not here.
- The captions path has run in the simulator and against the mock board, not with me talking to the real column.
- The tools were written and tested on Windows. The Python is portable; the `.cmd` wrappers are not.
