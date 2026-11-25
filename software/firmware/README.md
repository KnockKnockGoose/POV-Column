# POV LED Column v2 firmware

**Status 2026-11-24: firmware 0.4 runs the column in the Part 3 video.** The build report linked below describes
the first compile on 2026-11-03, before any hardware existed; the last section of this page is kept from that day.
Build report: [`docs/2026-11-03-firmware-build.md`](../../docs/2026-11-03-firmware-build.md). Design:
`docs/2026-11-02-software-and-ai-content.md` section 1; pins and
bring-up: [`docs/2026-11-02-electrical-design.md`](../../docs/2026-11-02-electrical-design.md) sections 2.5 and 9.

| Environment | What | Flash / RAM (2026-11-03) |
|---|---|---|
| `pov` | the column firmware: `src/main.cpp` + `lib/povcore` | 1,167,757 B flash (74 % of the 1.5 MB OTA slot), 84,656 B RAM static |
| `pov_ota` | the same, pio's own espota upload to <column-ip> (prefer `tools/ota_flash.py`) | same image |
| `pov_crashtest` | the column firmware with an `abort()` after the LED blank: OTA-only rollback self-test | ~0.5 MB |
| `phase0` | bench bring-up sketch: `src/phase0/phase0.cpp` (rotor open; 0.3: Wi-Fi + TCP 23 commands + NVS bench state, runs from J1 alone) | 1,010,725 B flash, 54,512 B RAM |
| `native` | host unit tests in `test/` (MinGW g++ 5.1, Unity) | 44 test cases, 6 suites |

## One command per job (from `software/firmware`, any shell)

```
tools\pio.cmd run -e pov                    build the column firmware
tools\pio.cmd run -e pov -t upload          flash it over USB            (pigtail unplugged! see the USB rule)
py tools\ota_flash.py --env pov             flash it over Wi-Fi + verify  (motor stopped; password in platformio_local.ini)
py tools\ota_flash.py --check               OTA preflight: what runs on the board, local build ids, firewall path
py tools\ota_sim_test.py                    OTA self-test with no board (fake ArduinoOTA receiver, 6 scenarios)
tools\pio.cmd run -e phase0 -t upload       flash the bench sketch       (then: tools\pio.cmd device monitor, type ?)
tools\pio.cmd test -e native                run the host tests
tools\pio.cmd device monitor                serial console, 115200
py software/firmware/test/gen_vectors.py    regenerate povgamma.h + test vectors after a change to povanim/font/column_model (repo root)
py software/povgen/gen_dog_ball.py --povmap software/firmware/lib/povcore/povmap.h      regenerate the LED map
py software/captions/font.py --header software/firmware/lib/povcore/captions_font.h    regenerate the fonts
```

`tools\pio.cmd` is a thin wrapper: it points PlatformIO at the venv, sets `PLATFORMIO_CORE_DIR=C:\pio`, clears the
MSYS variables Git Bash exports (ESP-IDF's tool installer refuses to run under them) and puts the MinGW toolchain on
PATH for the native env. The PlatformIO VS Code extension works too if `PLATFORMIO_CORE_DIR` stays `C:\pio` (it is set
as a user environment variable on the desktop PC).

**USB / bank rule (electrical report 2.7, open question E3).** The DevKit's VIN pin *is* the 5 V bus. Pigtail
unplugged whenever a USB cable is in. If the diode test shows no D1 on the VIN path: never both, ever. The first flash
is the ESP32 alone on USB (bench step 2, before it is soldered in); every later update of the closed rotor is OTA.

**OTA (review 2026-11-13, `docs/2026-11-13-ota-failure-review.md`).** Always `tools/ota_flash.py`: it streams the image,
retries, falls back to `POST /update`, and exits 0 only when the board reports the new build (`elf` in `/api/status`)
as a confirmed image. Both firmwares roll back by themselves if a new OTA image crashes or never gets Wi-Fi
(`src/pov_ota.h`). Exit 1 = board unchanged, 2 = uploaded but not running (rolled back). Trace: `.pio/ota_logs/`.
Since the Wi-Fi control review (2026-11-14, `docs/2026-11-14-wifi-control-review.md`) it pauses the picture first
(`/api/ota-prep`; on 0.2 images `sim_rpm 0` + `/api/stop`), puts it back afterwards and prints the total time.

**Everyday control (0.4+):** `py tools\pov_ctl.py status | play <name> | stop | sim 150 --persist | gb 12 | reboot |
crash | net | ab` (see its docstring). Live frames: `py tools\pov_stream.py rowwalk|stripes` (paced by the board's
acks). Acceptance test: `py tools\pov_soak.py --minutes 30`. All of them are tested without the board by
`py tools\mock_board_test.py` (tools vs `tools/mock_board.py`, a PC stand-in for the API, WebSocket and ArduinoOTA).

## Toolchain (installed on the desktop PC 2026-11-03; the laptop needs the same four steps)

| Piece | Version | Where / how |
|---|---|---|
| CPython for PlatformIO | 3.12.14 (uv-managed interpreter) | `<real 3.12.14 dir>\python.exe -m venv C:\pio\pio-venv` (the desktop PC, 2026-11-13). **Plain venv from the interpreter's real directory, not `uv venv`:** uv venvs point at the `cpython-3.12-...` junction, and SSH sessions refuse to traverse it ("untrusted mount point" / "uv trampoline failed to spawn Python child process"). pioarduino's own helper venv `C:\pio\penv` was rebuilt the same way (pre-create it; the platform only fills it). |
| PlatformIO Core | 6.2.0 (not 6.2.0.post1: fails the platform's version check and removes the platform) | `C:\pio\pio-venv\Scripts\python.exe -m pip install platformio==6.2.0` |
| PlatformIO home | `C:\pio` (`PLATFORMIO_CORE_DIR`) | the Arduino libs archive has 200-character paths that overflow Windows' 260-character limit from `C:\Users\<you>\.platformio`; a short home fixes it without the admin-only long-path policy |
| ESP32 platform | pioarduino 55.03.312-1 = Arduino-ESP32 3.3.12 on ESP-IDF 5.5.5 | pinned by URL in `platformio.ini`; installs xtensa GCC 14.2, esptool 5.x, the core and its libs (~1 GB) on the first `run` |
| Libraries | ESPAsyncWebServer 3.12.1, AsyncTCP 3.5.0, ArduinoJson 7.4.3 | pinned exactly in `platformio.ini`; FastLED and ElegantOTA were dropped (unused / replaced by `Update.h`) |
| Host compiler | MinGW GCC 5.1 (`platformio/toolchain-gccmingw32` 1.50100.0) | `tools\pio.cmd pkg install -g -t platformio/toolchain-gccmingw32@1.50100.0`; C++14 only, so `lib/povcore` stays C++14 |

## Layout

| Path | What |
|---|---|
| `platformio.ini` | the four environments, exact versions, build flags (`-DCONFIG_ASYNC_TCP_RUNNING_CORE=0` keeps the web stack on core 0) |
| `partitions.csv` | 2 x 1.5 MB OTA app slots + 0.9 MB LittleFS |
| `lib/povcore/` | **the logic, host-tested, C++14, no FreeRTOS**: `povmap.h` (generated LED map), `povgamma.h` (generated gamma 2.2 LUT), `povframe.h` (SK9822 frames, palettes, current model, cap, front-only mask), `povsched.h` (hall period estimate + column scheduler), `pova.h` (`.pova` parser + CRC + RLE), `captions.h` + `captions_font.h` (live captions), `povpattern.h` (calibration patterns, text scroller), `pov_compat.h` (shims) |
| `src/main.cpp` | the ESP32 glue: SPI DMA on two hosts, hall ISR, GPTimer alarm on core 1, tasks, LittleFS, Wi-Fi/mDNS/OTA, web API, NVS settings |
| `src/pov_ota.h`, `src/pov_crash.h` | OTA rollback guard + build id; crash recorder (`GET /api/crash`, needs `-Wl,--wrap=esp_panic_handler`) |
| `src/phase0/phase0.cpp` | the bench sketch (serial menu, same commands on TCP 23) |
| `tools/pov_cmd.py` | the laptop client for the TCP 23 command port (`py pov_cmd.py "cb s8000 a"`, `--watch`) |
| `tools/make_dist.cmd`, `tools/FLASH-FROM-LAPTOP.md` | merged phase0 image in `dist/` (gitignored) + the esptool flash command for the laptop |
| `src/wifi_secrets.h` | **gitignored**: copy `wifi_secrets.example.h` and fill in `WIFI_SSID`, `WIFI_PASS`, `OTA_PASS`, `POV_TOKEN` |
| `platformio_local.ini` | **gitignored**: copy `platformio_local.example.ini` for the OTA upload password |
| `test/test_*/` | Unity suites: povmap, frame, sched, pova (+ streaming upload check), font, captions |
| `tools/ota_flash.py`, `tools/ota_sim.py`, `tools/ota_sim_test.py` | OTA uploader + PC simulator of the board's ArduinoOTA + its self-test |
| `tools/pov_ctl.py`, `tools/pov_stream.py`, `tools/pov_soak.py` | control, paced live frames, switch + soak acceptance test |
| `tools/mock_board.py`, `tools/mock_board_test.py` | PC stand-in for the image firmware (0.4 or 0.2) + scenario tests for the tools |
| `test/gen_vectors.py`, `test/vectors/` | Python-generated reference vectors (povanim, font.py, column_model) the C++ must reproduce |
| `tools/pio.cmd`, `tools/native_env.py` | the wrapper and the native-env PATH script |

## Web API (<column-ip> / `pov.local`, token in `X-POV-Token` or `?token=` when `POV_TOKEN` is set)

`GET /` built-in page (or `/www/index.html` from LittleFS) · `GET /api/status` (+ `load`, `wifi`, `diag`, `crash` since
0.4) · `GET /api/anims` · `POST /api/anims` (multipart `file`, `.pova` <= 64 KB, checked while it streams in, temp file
+ rename; 400/409/413/507 say why) · `DELETE /api/anims?name=` · `POST /api/play {name}` (0.4: 200 = queued, the player
task loads it into a fixed 64 KB arena; `load.state` / `load.ms` in status) · `POST /api/stop` ·
`POST /api/pattern {name: rowramp|colramp|sets|grid|f|strips|white}` ·
`POST /api/text {text, color:[r,g,b], speed (col/s, 30), big, vs, secs}` · `POST /api/settings {gb, offset_x8, dir,
autoplay, front_only, front_deg, sim_rpm, sim_persist, tx_dbm}` (saved to NVS) and `{test_dark, test_nospi}`
(diagnostics, not saved) · `POST /api/ota-prep[?secs=N]` / `POST /api/resume` (pause the picture for an update) ·
`POST /api/reboot[?force=1]` (409 while a fresh OTA image is unconfirmed) · `GET|DELETE /api/crash` (last crash
record) · `GET|POST /update` (browser firmware update, `Update.h`) · `WS /ws` (`{"cap":...}` caption messages;
`{"live":...,"pal":[[r,g,b],...]}` + binary 4032-byte frames for live mode, `{"live":1,"ack":n}` -> `{"live_ack":n}`
for pacing; `{"ack":id,"swap_us":t}` after a caption frame reaches the LEDs; the 2 Hz status push was removed in 0.4).
Close live sockets without the WebSocket close handshake (review 3.2).

## What the hardware still had to confirm (written 2026-11-03, before the first power-up)

The frame builder, mapping, scheduler, parser, fonts and caption engine are tested on the host against the Python
reference. Untested until the parts are on the bench: the SPI timing (expect 0.704 ms per 704-byte frame; `t` in
phase 0), the SK9822 end frame / last-LED latch (`k`), the hall debounce and period estimate on a real sensor (`h`),
the GPTimer alarm jitter and `late_cols`/`skipped_cols` at 225 rpm, Wi-Fi and the async web stack on core 0 next to
the column task, OTA, the current model (20 mA per channel, 1 mA idle) against a meter. Section 6 of the build report.
