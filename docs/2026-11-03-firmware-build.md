# POV LED Column v2: Firmware Build Report (toolchain, first compile, fixes, host tests, phase-0 bench sketch, how to flash)

**Prepared for Brian** · Claude (Fable 5.1), firmware build agent on the desktop PC · 2026-11-03
Inputs: Brian's request of 2026-11-02 (compile and desk-test the firmware that had never been compiled; install the toolchain; fix what matters; native tests for the mapping, scheduler, fonts and captions; a phase-0 bring-up sketch; OTA; a report), `software/firmware/` as it stood (the skeleton of 2026-11-02 with the caption hooks), `docs/2026-11-02-software-and-ai-content.md` (architecture, frame format, phase-0 checks), `docs/2026-11-02-live-captions.md` (the caption message format and `column_model.py`), `docs/2026-11-02-electrical-design.md` rev e (pins 23/18, 13/14, 27, `CAP_MA` 2,600, the bring-up plan, the USB rule), `docs/2026-11-02-qa-review.md` (findings B1 a-e, M7, m5, m7), the Python reference code in `software/povgen`, `software/povsim`, `software/captions` (read only, nothing changed), and the installed Arduino-ESP32 3.3.12 / ESP-IDF 5.5.5 headers.
Outputs: this report (`.md` + `.html`); the firmware project `software/firmware/` (four PlatformIO environments, `lib/povcore`, `src/main.cpp`, `src/phase0/phase0.cpp`, `test/`, `tools/`); the toolchain on the desktop PC; revision notes in the software, live-captions and electrical reports; `software/README.md`; the knowledge base (`cad-hardware-and-tooling.md`) and the projects index. Nothing in Fusion, `cad/` or `software/captions/` was touched.

---

## Executive summary

**The firmware compiles, links and passes its desk tests; nothing has run on hardware.** PlatformIO is now installed on the desktop PC (Core 6.2.0 in a dedicated Python 3.12 environment, home `C:\pio`, the pioarduino platform for Arduino core 3.3.12 on ESP-IDF 5.5.5, a MinGW compiler from the PlatformIO registry for host tests), and `software/firmware` builds three targets with **no warnings in project code**:

| Environment | Image | Flash | RAM (static) | Note |
|---|---|---|---|---|
| `pov` (the column firmware) | `.pio/build/pov/firmware.bin`, 1,190,880 B | **1,167,757 B = 74.2 %** of the 1.5 MB OTA slot | **84,656 B = 25.8 %** of 320 KB | ~380 KB headroom per slot; the stock 1.25 MB `default.csv` would also fit, barely |
| `phase0` (bench sketch) | `.pio/build/phase0/firmware.bin`, 1,022,976 B | 1,010,725 B = 64.3 % | 54,512 B = 16.6 % | USB only, serial menu |
| `native` (host tests) | `program.exe` per suite | | | **44 test cases in 6 suites, all pass** (15 s) |

The QA review's five first-light blockers (B1 a-e) are fixed: the gamma table is generated, SPI transactions use `SPI_DEVICE_NO_RETURN_RESULT` with one descriptor per DMA buffer, the hall estimator anchors on the first pulse and only trusts two periods that agree within 5 %, a hardware GPTimer alarm on core 1 replaces the unavailable `ESP_TIMER_ISR` dispatch, and the platform is pioarduino. The caption mode, the `.pova` parser (now with its CRC check), the LED map and the SK9822 frame builder were moved into a header-only library (`lib/povcore`, C++14, no FreeRTOS) so the same code runs on the ESP32 and in the host tests. The host tests compare the C++ against the Python reference code that the earlier reports validated: the LED map against `povanim.column_indices` *and* against the simulator's paint model (so `povsim` and the firmware agree pixel for pixel), the current model against `current_profile`, the parser against the dog animation file, the fonts against `font.py`, and the caption engine against `column_model.py` over five scripted sessions (476 ticks, every frame checked by CRC). The tests caught three real port bugs before any hardware existed (section 5).

The firmware also gained what phase 2 of the bring-up needs (QA M7): calibration patterns (`/api/pattern`: row ramp, column ramp, set colours, grid, an upright F, strip lines, dense white), a text scroller (`/api/text`), `/api/stop`, settings in NVS, the token check on the WebSocket, a browser firmware page (`/update`, `Update.h`), a small built-in web page so a phone can play, upload, trim and brighten before the real UI exists, and front-only mode implemented per strip. A separate **phase-0 bench sketch** drives the bring-up steps 2-9 of the electrical report from a serial menu: one chain at a time, a low current field, strip-number / row-ramp / last-LED patterns, the SPI frame-time measurement, a 2.78 ms column clock that cycles the last LED (the SK9822 end-frame check), a hall readout with pulse width, the dense current-cap test and the Wi-Fi + OTA round trip. **One command per job: `tools\pio.cmd run -e pov -t upload`, `-e phase0 -t upload`, `-e pov_ota -t upload`, `test -e native`.**

What remains unknown is exactly what needs the parts: the real SPI timing, the last-LED latch, the hall sensor's behaviour, the timer jitter at 225 rpm, Wi-Fi next to the column task, OTA, and the current model against a meter (section 6). The USB / bank rule stands and is printed in the bench sketch's banner: pigtail unplugged whenever a USB cable is in; never both if the DevKit has no D1 (open question E3).

---

## 1. Toolchain: what was installed on the desktop PC and how to rerun it

Nothing on the desktop PC could compile for an ESP32 or for the host on 2026-11-03 morning: Python 3.14 only, `arduino-cli` with the AVR core, no PlatformIO, no gcc, no MSVC, and the Windows long-path policy off (`LongPathsEnabled = 0`, admin-only to change). The install took four steps and three workarounds, all without administrator rights:

| Step | What | Why this way |
|---|---|---|
| 1 | `uv venv C:\Users\<you>\.platformio-venv --python 3.12` then `uv pip install --python ...\Scripts\python.exe platformio==6.2.0` | uv already had CPython 3.12.14 on this machine; PlatformIO 6.2.0 (Sept 2026) is the latest and is not verified on Python 3.14. The venv sits outside the synced folder. |
| 2 | `setx PLATFORMIO_CORE_DIR C:\pio` (user variable) and move `~/.platformio` there | The first `pkg install` failed unpacking the Arduino libs archive: its longest member path is 200 characters (a Matter SDK header), which overflows Windows' 260-character limit from `C:\Users\<you>\.platformio\.cache\tmp\pkg-installing-xxxxxxxx\...` (262). From `C:\pio` the worst case is 242. Measured with a 20-line tarfile script before choosing the path. |
| 3 | `platform = https://github.com/pioarduino/platform-espressif32/releases/download/55.03.312-1/platform-espressif32.zip` | QA B1e: the official `espressif32` platform stops at Arduino core 2.0.x. pioarduino 55.03.312-1 is the latest stable (2026-09-22): Arduino 3.3.12 on ESP-IDF 5.5.5, xtensa GCC 14.2.0, esptool 5.x. Pinned by URL so the build is reproducible. |
| 4 | `pio pkg install -g -t platformio/toolchain-gccmingw32@1.50100.0` | PlatformIO's `native` platform ships no Windows compiler; the only compiler obtainable without an installer or admin rights was this registry package (MinGW GCC 5.1, 96 MB, 2016). It is old but fine for C++14 logic. `tools/native_env.py` puts it on PATH for the native env. |
| wrapper | `software/firmware/tools/pio.cmd` | Sets the venv, the core dir, `PYTHONUTF8=1` (pio's registry listing crashed with a `UnicodeEncodeError` on the Windows console), clears `MSYSTEM`/`MSYS` (ESP-IDF's `idf_tools.py` refuses to run under Git Bash's MSYS environment: "MSys/Mingw is not supported", which also left the xtensa compiler off PATH on the first build), and prepends the MinGW bin. |

Package versions pinned in `platformio.ini`: ESP32Async/ESPAsyncWebServer 3.12.1, ESP32Async/AsyncTCP 3.5.0, bblanchon/ArduinoJson 7.4.3 (the registry's latest 7.x), native platform 1.2.1. **FastLED and ElegantOTA were removed** from `lib_deps` (QA m7: FastLED was never used and drives only one SPI host; ElegantOTA 4.0 changed its API in September and the web update needs 30 lines of `Update.h`, which is what `/update` is now).

Disk: `C:\pio` is about 1.9 GB (toolchain, core, libs, MinGW, esptool venv); `C:\Users\<you>\.platformio-venv` 60 MB. The first full build of `pov` took 106 s; incremental builds take 12-25 s; the test suite 15 s.

**To rerun on the desktop PC:** everything goes through the wrapper from `software/firmware` (any shell; from Bash write `cmd //c "tools\pio.cmd run -e pov"`). **On the laptop** the same four steps are needed (the README lists them); nothing of this exists there yet. Optional, admin only: enabling Win32 long paths would let `~/.platformio` work again, but `C:\pio` is enough.

---

## 2. What changed in the firmware

### 2.1 Structure

| Before (2026-11-02) | Now |
|---|---|
| `src/main.cpp`, `src/pova.h`, `src/captions.h`, generated `povmap.h` and `captions_font.h` in `src/` | `lib/povcore/` holds every piece of logic as header-only, C++14, FreeRTOS-free code: `povmap.h` and `captions_font.h` (generated, unchanged), `povgamma.h` (generated), `povframe.h`, `povsched.h`, `pova.h`, `captions.h`, `povpattern.h`, `pov_compat.h`. `src/main.cpp` is the ESP32 glue; `src/phase0/phase0.cpp` the bench sketch. |
| one env, FastLED + ElegantOTA in `lib_deps`, `platform = espressif32` | four envs (`pov`, `pov_ota`, `phase0`, `native`), exact versions, pioarduino, `extra_configs = platformio_local*.ini` for the OTA password, `-Wall -Wextra` on everything |
| no tests | `test/` with six Unity suites and `test/gen_vectors.py`, which writes `povgamma.h` and the reference vectors from the Python code |

### 2.2 Fixes, by QA finding and by what the compile and the tests found

| # | Where | Problem | Fix |
|---|---|---|---|
| B1a | `povgamma.h` | `GAMMA22[256]` was empty: every colour mapped to 0 | generated from `povanim.gamma_lut()` by `test/gen_vectors.py` (checked: 0 → 0, 128 → 56, 255 → 255, monotonic) |
| B1b | `main.cpp` `setup_spi`, `queue_frame` | `spi_device_queue_trans` with `queue_size 2` and no `get_trans_result`: output stops after two columns; one `static spi_transaction_t` reused while in flight | `cfg.flags = SPI_DEVICE_NO_RETURN_RESULT` (exists in IDF 5.5.5, checked in the header) and one `spi_transaction_t` per DMA buffer (`spi_tr[2][2]`, `blank_tr[2]`); a descriptor is reused only two columns later, 5.5 ms after a 0.7 ms transfer. A side effect: `spi_device_transmit` cannot be used on such a device, so the blank frame also goes through the queue. |
| B1c | `povsched.h` `hall_pulse` | the first pulse took "time since boot" as the period and the filter chased it for seconds; `uint32` wrap after 71 min | the first pulse only anchors; a period is kept only if it is under `rev_us_max` (100 rpm); the estimate is trusted (`valid`) after two consecutive periods within 5 % (the report's own rule), with the alpha-1/4 filter after that; a period jump of more than 5 % restarts the estimate (`resyncs` counter); bounce inside a quarter revolution is rejected (`rejected` counter). Integer-only, tested with synthetic pulses. |
| B1d | `main.cpp` `column_task` | `ESP_TIMER_ISR` dispatch is not compiled into the Arduino libraries (`CONFIG_ESP_TIMER_SUPPORTS_ISR_DISPATCH_METHOD` unset, confirmed in the installed `sdkconfig`) | a GPTimer (`driver/gptimer.h`, 1 MHz) with a one-shot alarm re-armed from the column task (`gptimer_get_raw_count` + `gptimer_set_alarm_action`). The timer is created *inside* the task pinned to core 1, so its interrupt is allocated on core 1: nothing on core 0 (Wi-Fi, the esp_timer task) can delay a column wake-up. `CONFIG_GPTIMER_ISR_HANDLER_IN_IRAM=y` in the Arduino build. |
| B1e | `platformio.ini` | Arduino core 2.x | pioarduino 55.03.312-1 (core 3.3.12) |
| m7 | `platformio.ini` | FastLED unused, ElegantOTA without its async flag, `max(1UL, ...)` type mix | both libraries dropped; `/update` on `Update.h`; the player counts refresh ticks instead of sleeping computed milliseconds |
| m5 | `main.cpp` `setup` | `WiFi.setSleep(false)` costs ~50 mA | kept (caption latency), commented; decision F3 below |
| M7 | `main.cpp` | no calibration patterns, no `/api/text`, no static page, no NVS, no OTA page, no token on the WebSocket | all added (section 2.3) |
| new | `povsched.h` | the column task read a 64-bit hall timestamp that the ISR can update halfway through (torn read on a 32-bit core: a wrong column time every few seconds) | a seqlock around the ISR's update; the task takes a consistent snapshot |
| new | `povsched.h` `plan_next` | the old "nearest column edge" rule could skip an edge that was still reachable, or re-send one | the plan is the earliest edge whose fire time (edge - 704 us) is still at least the build time ahead; never re-send; a new pulse re-anchors (index k of the old revolution is k - 96); `late` and `skipped` are counted separately, and the busy-wait is capped (an early wake just re-arms the alarm) |
| new | `main.cpp` palette | the palette was rebuilt in place while core 1 read it | two palette sets, written on core 0 and flipped with an index |
| new | `main.cpp` `load_anim` | the first frame was decoded straight into the buffer being shown; the player's `vTaskDelay` drifted against the ticks | the new frame is staged into the spare buffer; the player advances on `tick_count` (one tick before the frame is due) |
| new | `pova.h` | no CRC, no bounds checks on `meta_len` / palette, `memmem` is a GNU extension (not on the host) | zlib-compatible CRC-32 (checked against `zlib.crc32("123456789")`), bounds checks, a private `memmem_` |
| new | `captions.h` | FreeRTOS queue (untestable on the host); the `dim` colour was not truncated like `Config.palette()`; `float` time | lock-free single-producer / single-consumer ring; `uint8_t` truncation; `double` for the ticker maths so it matches Python bit for bit |
| test | `captions.h` `TapeWord` | 24-character word buffer cut the limiter test's 34-letter word (x = 137 instead of 203) | 48 characters, like the message buffer |
| test | `captions.h` `draw_text_marquee` | the scroller's tape coordinate had the wrong sign: text would have moved away from the viewer | fixed; the test checks that x + 1 shifts every column one step to the viewer's left |
| test | `test_captions` harness | a constant tick length made x differ from Python by one ulp after 44 ticks, which moved a word by one column through `floor()` | the harness derives dt from consecutive tick times like `column_model.tick()`; documented as a parity rule in the knowledge base |
| compile | `povsched.h`, `main.cpp`, `phase0.cpp` | GCC 14 (`gnu++2b`): `++` on `volatile` is deprecated; `%u` with `uint32_t` on xtensa (`long unsigned int`) | `x = x + 1` on ISR-shared counters; casts in `printf` |

### 2.3 New in the column firmware

- **Modes** `off | anim | captions | live | pattern | text` (`/api/status` reports which). `MODE_OFF` and an OTA in progress blank the LEDs.
- **`POST /api/pattern {name}`**: `rowramp` (31 grey steps bottom to top; a wrong interleave or an un-inverted odd strip shows as a jagged ramp), `colramp` (grey around the drum, every 8th column white), `sets` (rows of set A/B/C in red/green/blue), `grid` (every 8th column and 7th row; column 0 and row 0 orange), `f` (an upright 3-pixel F in the window: mirrored or rotated means `dir` / `offset_x8`), `strips` (one coloured line per strip position), `white` (every pixel: the current-cap test). Each pattern carries its own palette and goes through the same cap as an animation.
- **`POST /api/text {text, color, speed, big, vs, secs}`**: a marquee around the whole drum on the caption fonts (7x9 bold by default, vertically doubled), 30 columns/s by default (1 column per tick, the camera-legible speed from the captions report). At boot the column scrolls its IP address and `POV.LOCAL` for 10 s, then autoplays the last animation.
- **Settings in NVS** (`Preferences`, namespace `pov`): `gb`, `dir`, `offset_x8`, `autoplay`, `front_only`, `front_deg`, `last`. `POST /api/settings` saves and re-fits the cap of the running animation.
- **Front-only mode, implemented.** The rev e note sketched blanking whole columns by strip 0's angle; that would blank all 24 strips for half of every revolution and paint nothing special. What the note *wants* (paint only the 180 deg facing the viewer, halve the current and the glow from behind) is per strip: strip s sits at 3.75 k + 15 s degrees from the hall reference at scheduler column k, and it is lit only within 90 deg of `front_deg`. `front_mask(k, front_deg)` is a 24-bit mask computed per column (integer quarter-degrees), tested: 13 strips face the front at any instant.
- **Token on the WebSocket** (captions report, section 6): the same `X-POV-Token` header, or `?token=` in the URL for browsers and the upgrade request, through `ws.setFilter`. With `POV_TOKEN` empty (bench) everything is open.
- **`/update`**: a one-form page that flashes `.pio/build/pov/firmware.bin` through `Update.h`; the column blanks during the write and reboots after it. ArduinoOTA (`pov_ota` env, port 3232, password from `wifi_secrets.h` / `platformio_local.ini`) stays for `pio run -t upload`; `onStart` blanks the LEDs.
- **Built-in page** at `/` (served when `/www/index.html` is absent): status, the animation list with play / delete, upload, brightness slider, offset trims in 1/8 and whole columns, direction flip, pattern and text boxes, the update link. About 30 lines of HTML; the real UI of the software report's section 3.1 still belongs in `/www`.
- **Status** now also reports `valid`, `rejected`, `resyncs`, `skipped_cols`, `build_us_max`, `spi_fail`, `ticks`, `gb_used`, `cap_gb`, `cap_peak_ma`, `heap_min`, `psram`, `rssi`, `uptime_s`; the 2 Hz WebSocket push carries `mode`, `late`, `skipped`.
- **Live frames**: the palette message may carry `pal`; every incoming 4,032-byte frame is capped per frame (its worst rotor position against `CAP_MA`), indices above the palette size are forced to 0.

### 2.4 Design checks requested in the brief

| Check | Result |
|---|---|
| Pins vs the 30-pin DOIT board | `PIN_D0 23 / PIN_C0 18` (VSPI = `SPI3_HOST`, IO_MUX pins), `PIN_D1 13 / PIN_C1 14` (HSPI = `SPI2_HOST`, IO_MUX pins), `PIN_HALL 27` (full GPIO, external 10 k pull-up on the carrier, `INPUT_PULLUP` as well): all on the 30-pin header, none a strapping pin (electrical 2.5). The code names the hosts by number because IDF 5 deprecates `VSPI_HOST`/`HSPI_HOST`. |
| Two hardware SPI buses at 8 MHz | `spi_bus_initialize` on both hosts with `SPI_DMA_CH_AUTO`, mode 0, no CS, 8,000,000 Hz (= 80 MHz APB / 10, exact), `max_transfer_sz = 704`; buffers `DMA_ATTR`; both chains clock out in parallel while the task waits. Frame time 704 B x 8 / 8 MHz = **0.704 ms** (`SPI_US`), the number the scheduler subtracts from each column edge. |
| Hall ISR on GPIO 27 | `IRAM_ATTR`, falling edge, attached from the column task so the GPIO ISR service lives on core 1; the ISR does one `esp_timer_get_time()` and integer arithmetic; debounce = reject pulses closer than a quarter of the fastest plausible revolution (21.6 ms at 694 rpm; the real pulse is ~10 ms wide at 225 rpm and 267 ms apart); the ISR notifies the column task so the schedule re-anchors within microseconds. |
| Column timing at 225 rpm | 266,667 us per revolution / 96 = 2,778 us per column; the task is woken 60 + 100 us before the fire time, builds both frames (budget 60 us; `build_us_max` reports the real figure), busy-waits to the fire time and queues the DMA; the LEDs latch 704 us later, on the edge. Margin per column: 2,778 - 704 - 160 = 1.9 ms. Refresh ticks every 12 columns (`POV_TICK_COLS`), frames swap there. The scheduler test runs three clean revolutions, a 1 %-per-revolution speed ramp (no duplicate columns, at most one skipped per revolution, estimate stays valid), a late plan, an early pulse and a late pulse. |
| `CAP_MA` | 2,600 in `povframe.h` = `povanim.CAP_MA` (a test asserts they are equal, so the validator and the firmware cannot drift); the per-animation fit folds the cap into the 5-bit field (all-white would run at field 3). The caption limiter counts the ESP32 too, like `column_model`, so its default is 2,720 in its own units. |
| Wi-Fi / WebSocket / `POST /api/text` | STA with a 10 s timeout then the `POV-Column` access point; mDNS `pov`; `WiFi.setSleep(false)`; the async TCP task on core 0 (`-DCONFIG_ASYNC_TCP_RUNNING_CORE=0`), the web server, WebSocket with `setNoDelay`, acks after the swap; `/api/text` as described. All compiled against ESPAsyncWebServer 3.12.1; nothing exercised on a radio yet. |
| Caption mode | reviewed line by line against `column_model.py` and then tested against it (section 5); the hybrid jump now happens on the message wake too (so a word is fully in the window at the very next tick); the crawl drop rule, `need()`, `forget_old` and the limiter match. |
| OTA with the rotor closed | ArduinoOTA (`pov_ota`) and `/update`; both blank the LEDs; the column task stops while `ota_active`. **USB / bank rule (E3, D1):** VIN is the bus; pigtail out whenever USB is in; never both without D1; first flash on USB before soldering the DevKit in. In the README, the sketch banner and here. |

---

## 3. Phase-0 bench sketch (`src/phase0/phase0.cpp`, env `phase0`)

Serial at 115200, `?` for help. It maps onto the electrical report's bring-up table:

| Bench step | Command | What it does / what to expect |
|---|---|---|
| 2 (ESP32 alone on USB, before soldering) | boot banner, `i`, `w` | prints the chip, `ESP.getPsramSize()` (expect 0), free heap (expect > 200 kB), the pins; `w` joins Wi-Fi from `wifi_secrets.h`, starts ArduinoOTA and prints the IP for the OTA round trip (`--upload-port <ip>`) |
| 3 (carrier, no strips, scope on J3/J4) | `c0` / `c1` / `cb`, `4` | 8 MHz bursts of 704 B every time a pattern is sent; `t` sends 200 frames to time |
| 4 (one 14-LED strip) | `n14`, `g4`, `1` `2` `3` `4` (R G B W), `g31`, `g8`, `g1` | colour order (if red shows green, the BGR order in `povframe.h` is wrong: one line); white at field 31 ≈ 0.8-0.85 A per the model (the sketch prints the predicted mA for every pattern); dim to field 8 and wave the strip: no dashes |
| 5 (a 12-strip chain) | `n168`, `5` (strip numbers), `6` (row ramp), `7` (last LED), `t`, `k` | `5`: strip s lights its LED s; `6`: grey by image row (the interleave and the odd-strip inversion visible on the bench); `t`: blocking and DMA-queued frame times, min/avg/max (expect ~704 us + a few tens); `k`: a frame every 2,778 us for 10 s from a GPTimer alarm with the last LED cycling R/G/B: a white-ish last LED means the end frame latches it every column, a single colour means it does not; prints missed alarms and the worst alarm-to-send latency |
| 6 (both chains, dense) | `cb`, `m2600`, `9` | dense white at the cap: the sketch fits the field like the firmware (all 168 LEDs white at field 3 ≈ 1.3 A per chain predicted) and prints the prediction to compare with the supply's meter |
| 7 (the bank) | `0`, then `9` | blank current (expect 0.46 A with both chains dark), then the dense pattern |
| 8-9 (hall) | `h` | pulses, rejected, resyncs, the firmware's own period estimate and rpm, `valid`, pulse width (falling to rising, ~10 ms at 225 rpm when swept at 1 m/s), edge count, pin level; 2 Hz |

`8` walks one white LED along the chain (10 per second) to count LEDs; `mNNNN` sets the cap; the field never exceeds the `g` value. The sketch keeps the SPI result queue (blocking sends) because nothing is timing-critical on the bench.

---

## 4. How to flash

From `software/firmware` (every command through the wrapper; `-t upload` finds the DevKit's COM port itself, or add `--upload-port COMx`):

| Job | Command | Preconditions |
|---|---|---|
| bench sketch over USB | `tools\pio.cmd run -e phase0 -t upload` then `tools\pio.cmd device monitor` | **pigtail unplugged**; ESP32 alone or in the carrier with the bank out; CP210x/CH340 driver (Windows usually has it) |
| column firmware over USB | `tools\pio.cmd run -e pov -t upload` | same; `src/wifi_secrets.h` filled in (copy `wifi_secrets.example.h`), else it boots into the `POV-Column` access point (password `povcolumn`) |
| column firmware over Wi-Fi (rotor closed) | `tools\pio.cmd run -e pov_ota -t upload` | `platformio_local.ini` with `--auth=<OTA_PASS>` (copy the example); `pov.local` resolving (or `upload_port = <ip>`); the rotor may be stopped or spinning (the LEDs blank during the write) |
| from a phone | open `http://pov.local/update?token=<POV_TOKEN>` and pick `.pio/build/pov/firmware.bin` | the build on the desktop PC |
| host tests | `tools\pio.cmd test -e native` | nothing |
| LittleFS content (animations, `/www`) | `tools\pio.cmd run -e pov -t uploadfs` after putting files in `software/firmware/data/` (not created yet), or `POST /api/anims` from `pov_request.py` | |

First power-on order (the electrical report's step 2 and 7): flash `phase0` on the bare DevKit on USB, do the diode test, solder it in, run steps 3-6 on the bench supply, then the bank, then `pov`.

---

## 5. Desk tests (`tools\pio.cmd test -e native`, 44 cases, 6 suites)

The Python code of the earlier reports is the reference: `software/povgen/povanim.py` (geometry, mapping, `.pova`, current model), `software/povsim/simulate.py` (the paint model), `software/captions/font.py` and `column_model.py` (fonts, the caption engine; 36 pytest cases of their own). `test/gen_vectors.py` runs that code and writes C headers of expected results into `test/vectors/`; the Unity suites replay the same inputs through `lib/povcore` and compare.

| Suite | Cases | What it proves |
|---|---|---|
| `test_povmap` | 7 | the generated tables equal a brute-force re-derivation (strip = chain·12 + pos/14, odd strips inverted, row = 3k + set, offset 4s); every row has 8 LEDs 12 columns apart; `build_column` reproduces `povanim.column_indices` for four columns of a known frame; **the simulator's paint model agrees**: for every (row, column, strip-of-the-set) the firmware puts `frame[r][c]` on exactly the LED that `povsim.paint_times` says paints it, at scheduler column j = (c - 4s) mod 96; `front_mask` blanks 11 of 24 strips per column |
| `test_frame` | 7 | `CAP_MA` equals `povanim.CAP_MA`; the 704-byte frame layout (zero start, `0xE0|gb,B,G,R`, 24 x `0xFF`, 4 x `0x00`); the blank frame; gamma, order and index 0 forced off; the current model: all-white 20,616 mA exactly as Python, within 1 % on a sparse frame and 1.5 % on the dog's first frame (LUT rounding), all-white at field 15; `fit_gb` (all white → field 3, never 0, exact at the boundary) |
| `test_sched` | 10 | defaults; first pulse anchors only, two agreeing periods validate, the filter step; bounce rejected without touching the state; blank after 0.5 s, after a hand turn, at 90 rpm; a 25 % speed jump resyncs; **three revolutions at 225 rpm**: columns 1..95, 0, 1... in order, each fired exactly 704 us before its edge, 8 ticks per revolution, nothing late or skipped; a 1 %-per-revolution ramp over 12 revolutions: no duplicate, ≤ 1 skipped per revolution, estimate stays valid; late plans fire now, early wakes wait; re-anchoring continues the count after an on-time pulse (next column 1) and after an early pulse (column 0 skipped and counted); `image_col` direction and 1/8-column offsets |
| `test_pova` | 5 | CRC-32 equals zlib; the dog file parses (24 frames, 15 fps, 13 colours, loop, name, scope, holds, palette); frame 0 and the last frame decode to Python's pixels; every frame's indices are below `npal`; a flipped byte fails the CRC but still parses structurally, truncation / bad magic / wrong rows / too short all fail; a raw (non-RLE) file built in C round-trips |
| `test_font` | 7 | text widths of 22 strings in both fonts equal `font.text_width`; the auto-font choice equals `layout_word` (7x9 if ≤ 32 columns, else 5x7, else scroll); glyph coverage, lowercase mapping, undrawn characters; "HI" and "HELLO" in word mode equal the Python frames and are centred; the marquee moves left and wraps; the scroller state; the patterns (monotonic row ramp, set colours, the F's orientation, palettes) |
| `test_captions` | 8 | **five sessions replayed tick by tick** against `column_model.ColumnCaptions`: word mode (short word, 5x7 word, the jump mini-scroll of TRANSCRIPTION, a dim partial, clear; 60 ticks), the hybrid ticker (eight words arriving over 33 ticks with a partial, then 1.5 s of silence and the drift; 130 ticks), the crawl ticker (a 230-column burst that forces drops, then a steady stream; 160 ticks), the current limiter (a white WWWW... ticker all round the drum: field drops to keep 2 A, releases one step per three ticks; 90 ticks), cfg changes (red, dim 0.5, vertical scale 1, smooth scroll, a mode switch; 36 ticks). At every tick: the same frame (CRC-32 of 4,032 pixels; full-frame comparison at 125 of the 476 ticks), tape position x to 1e-6, speed, current field, drops, mode, peak current within 0.5 mA. Plus the message-wake path (a word jumps fully into the window at once, acks carry the id, a second wake changes nothing), garbage and a 40-message burst (the ring drops the overflow, the engine keeps running), cfg clamps, and the dim colour truncation. |

**What the tests caught** (all fixed in section 2.2): the marquee direction sign, the 24-character tape word buffer, and the one-ulp tick-length mismatch. The scheduler tests also corrected two of my own expectations: 50 us after a pulse the earliest reachable column is 1, not 0 (column 0's fire time is 704 us *before* its own edge), so a cold start misses one column once, and a pulse that arrives early makes column 0 unreachable too (counted as skipped). Both are correct behaviour; the firmware paints column 0 of every later revolution from the previous anchor's prediction.

**Not covered by desk tests** (needs the chip): the SPI driver and DMA, the GPTimer, the hall ISR entry, task interplay, Wi-Fi, LittleFS, NVS, OTA. The host compiler is also 32-bit GCC 5.1; the ESP32 build uses GCC 14 with `int` and `long` both 32-bit, so integer semantics match.

---

## 6. What the hardware still has to confirm (risk list)

| Item | Why it is still open | How phase 0 settles it |
|---|---|---|
| SPI frame time 0.704 ms and continuous DMA | the FastLED concern of the software report does not apply to `spi_master`, but the driver's per-transaction overhead is unmeasured | `t` in the bench sketch; expect ~720-760 us queue-to-done |
| SK9822 end frame / last-LED latch | the extra zero frame is the conservative reading of two sources | `k` with 168 LEDs: the last LED must cycle |
| Hall pulse shape, bounce, the 5 % gate during spin-up | modelled, not measured; a noisy sensor could keep `valid` false (the display stays dark) or resync too often | `h` on a drill-spun mock: `rejected` and `resyncs` should stay near 0 at steady speed; raise `agree_pct` if the motor's speed ripple exceeds 5 % per revolution |
| GPTimer alarm jitter, `late_cols`, `skipped_cols`, `build_us_max` at 225 rpm | the 60 us build budget and 100 us slack are estimates | `/api/status` after a minute; if `build_us_max` > 60, raise `BUILD_US` |
| Wi-Fi + async web stack next to the column task | the core split is designed, not observed | the 30 s streaming test of phase 4 with `late_cols` = 0 |
| `WiFi.setSleep(false)` current | ~50 mA extra, 8 % of the port budget | measure the blank current (expect 0.46 A + up to 0.05) |
| The current model (20 mA per channel, 1 mA idle) | the cap is only as good as the model | bench steps 4 and 6 with a meter; adjust `I_CH_MA` / `I_DARK_MA` in `povframe.h` and `povanim.py` together |
| Caption / live latency, acks | simulated on the Pi, not on an ESP32 | `probe_link.py ws://pov.local/ws` |
| OTA with the rotor spinning | flash writes stall non-IRAM code; expect a glitch, not a crash | try it once with the rotor stopped, then spinning |
| Boot window | the strips power up in a random state until `setup()` blanks them (electrical 11) | bench step 7: watch for a flash at plug-in |
| NVS, LittleFS, the upload path | compiled against the core's libraries, never executed | `pov_request.py --dry-run` → a real upload of the dog |

---

## 7. Decisions and open questions for Brian

| # | Item | Default now | Options |
|---|---|---|---|
| F1 | Column timer | GPTimer one-shot alarm, ISR on core 1 | `esp_timer` with task dispatch (simpler, runs on core 0 behind the Wi-Fi task) |
| F2 | Web update | `/update` on `Update.h` (no library) + ArduinoOTA | ElegantOTA 4 if a nicer page matters |
| F3 | Wi-Fi modem sleep | off (captions need it) | on when not in caption mode: ~50 mA back, 8 % of the port budget |
| F4 | Front-only semantics | per strip from the hall angle (`front_deg`), default off | per column (the rev e sketch), which blanks everything for half a revolution; or derive `front_deg` from `offset_x8` automatically |
| F5 | Spin-up gate | two periods within 5 % | loosen to 8-10 % if the gearmotor's speed ripple keeps `valid` false |
| F6 | Host compiler | registry MinGW GCC 5.1 (C++14) | MSYS2 / w64devkit GCC 14 if Brian installs one (then `-std=gnu++17` in the native env) |
| F7 | Long paths | `C:\pio` workaround | enable Win32 long paths as admin (one PowerShell line, reboot) and move back to `~/.platformio` |
| F8 | the laptop | nothing installed | the same four steps (README), ~2 GB, 15 min |

---

## 8. How to explain it

- **Test the logic where you can see it.** The firmware is split into a header-only library with no hardware or RTOS calls and a thin glue file. The library runs on a 2016 MinGW compiler on the desktop under a unit-test framework, against vectors generated by the Python code that designed the display. Three real bugs surfaced in an hour, before a single part was soldered.
- **Two implementations, one truth.** The LED map, the fonts and the gamma table are *generated* from Python into C headers; the caption engine is *ported* and then replayed tick by tick against the Python original with a CRC of every frame. Generated things cannot drift; ported things are caught when they do.
- **Floating point is reproducible if you copy the arithmetic.** Matching Python's `x += v * dt` to the bit meant deriving `dt` the same way (difference of tick times, not a constant) and using `double` on a chip with no double hardware; the cost is a few microseconds per tick, the benefit is a simulator you can trust to the pixel.
- **A scheduler is a contract about time.** "Which column is next" became a pure function of the pulse time, the period, now, and what was already sent; it is tested with synthetic pulses at 225 rpm, during a speed ramp, and around early and late pulses. The ISR only anchors and filters; it never does arithmetic that can wrap.
- **Toolchain archaeology is engineering too.** No admin rights, Python 3.14, Git Bash: three separate blockers (a 262-character path, an MSYS check inside ESP-IDF, no host compiler) each had a non-admin workaround, and the wrapper script makes them invisible to the next person.
- **Don't ship what you cannot reap.** The original DMA code queued transactions into a two-slot queue and never collected the results: it would have stopped after two columns. The IDF flag that says "don't return results" plus one descriptor per buffer is the whole fix.

---

## Appendix A. Files

| Path | Purpose | Status |
|---|---|---|
| `software/firmware/platformio.ini`, `partitions.csv`, `platformio_local.example.ini` | envs, versions, flags; 2 x 1.5 MB OTA + 0.9 MB LittleFS; OTA password template | built |
| `software/firmware/tools/pio.cmd`, `tools/native_env.py` | the wrapper; MinGW on PATH for the native env | used for every build here |
| `software/firmware/lib/povcore/*.h` | the logic (see 2.1) | host-tested |
| `software/firmware/src/main.cpp` | the column firmware | compiles, untested on hardware |
| `software/firmware/src/phase0/phase0.cpp` | the bench sketch | compiles, untested on hardware |
| `software/firmware/src/wifi_secrets.example.h` | secrets template (the real file is gitignored) | |
| `software/firmware/test/gen_vectors.py`, `test/vectors/vec_*.h`, `test/test_*/test_main.cpp` | vector generator, vectors (292 KB captions, 35 KB dog file, the rest small), six suites | 44 pass |
| `software/firmware/README.md` | commands, toolchain, layout, API, untested list | |
| `docs/2026-11-02-software-and-ai-content.md`, `-live-captions.md`, `-electrical-design.md` | revision notes of 2026-11-03 at the top | |
| `C:\pio`, `C:\Users\<you>\.platformio-venv` | the toolchain (not in git) | |

## Appendix B. Build log excerpts

```
pov:    RAM:   [===       ]  25.8% (used 84656 bytes from 327680 bytes)
        Flash: [=======   ]  74.2% (used 1167757 bytes from 1572864 bytes)      [SUCCESS] Took 105.70 seconds (first build)
phase0: RAM:   [==        ]  16.6% (used 54512 bytes from 327680 bytes)
        Flash: [======    ]  64.3% (used 1010725 bytes from 1572864 bytes)      [SUCCESS] Took 29.71 seconds
native: 44 test cases: 44 succeeded in 00:00:15.698
PACKAGES: framework-arduinoespressif32 3.3.12, framework-arduinoespressif32-libs 5.5.5+sha.b774170ff46,
          toolchain-xtensa-esp-elf 14.2.0+20260121, tool-esptoolpy 5.4.0 (esptool 5.6.0 in C:\pio\penv)
```
