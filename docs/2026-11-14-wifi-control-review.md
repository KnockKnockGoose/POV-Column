# Wi-Fi control review: why switching, streaming and OTA were slow and crashed (2026-11-14)

*Prepared for Brian, 2026-11-14, by Claude (the desktop PC session "pov-wifi-control-review"). Firmware 0.4 + tools in commit
`c8acc8f` (built, host-tested, **not flashed**: the board still runs 0.2, build `c0034fba81ef88d3`).*

## 1. Summary

Today it took 7+ minutes to switch to an animation that was already on the board. That was not one slow step but a
chain: the play request failed with a misleading 404 (heap), there was no way to reboot remotely, the OTA that was used
as a reboot failed while the picture ran, and its fallback refused to start because of a tool bug. Along the way two
crashes had their own causes. What I found, in order of certainty:

| # | Symptom today | Root cause | Certainty | Fixed by |
|---|---|---|---|---|
| 1 | Upload of `bichon_shades_orbit.pova` → `{"error":"bad file"}`, then a panic | The file is valid (64,312 B, CRC OK). The upload check `malloc`ed the whole file to parse it; on the fragmented heap that failed, and the reject path set `_tempObject = (void*)1`, which the web server later passes to `free()` → assert → panic | **certain** (code + library source) | streaming check, real per-request state (3.1) |
| 2 | `/api/play bichon_shades_front` → 404, also after `/api/stop` | `load_anim()` `malloc`ed the 62,666 B file while the previous one was still allocated; `/api/stop` frees nothing; every failure was reported as "not found" | **certain** | 64 KB arena allocated at boot, specific errors (4.1) |
| 3 | `ota_flash.py` fallback: "no POV_TOKEN in src/wifi_secrets.h" | `wifi_secrets.h` has `#define POV_TOKEN ""` (empty = the board checks no token). The regex matched, but `if not token` treated `""` as missing | **certain** | `None` vs `""` handled (4.4) |
| 4 | 3 × ArduinoOTA "no answer to the authentication" while the picture ran | Each try got its invitation answered, then no answer to the auth datagram. ArduinoOTA sends the auth once and never repeats it, so one lost datagram (either way) ends the try. The password check itself costs ~1 s of CPU, and by the code `loop()` had ~94 % of its core (section 2), so "loop starved" was a guess | **likely** (loss); a blocked `loop()` not excluded: 0.4 now measures it | OTA pauses the display first, automatically; loop lag recorded (4.3, 4.6) |
| 5 | Live streaming: `WebSocketTimeoutException` after ~40 s | `pov_rowwalk.py` sent each 4,032 B frame 3 × per 0.3 s step = 40 KB/s, `pov_diag.py` 15 frames/s = 60 KB/s, over a link that carried 10-20 KB/s (OTA timings 11-13/14). The socket filled until a send timed out | **certain** | `tools/pov_stream.py`, paced by the board's acks (4.5) |
| 6 | 66 % ping loss, 3.8 s RTT with sim 150 + animation; fine after `sim_rpm 0` | By the code the display path uses ~6 % of core 1 and almost nothing on core 0 (section 2), so it cannot starve Wi-Fi. With the picture on at gb 12, 2 minutes after a reboot, I measured 0 % ping loss and 16 ms this morning. Most likely LED current (supply ripple through the bank and pigtail) or the SPI lines near the antenna, possibly plus a bad session state | **open**: needs the A/B test (section 6, step 2) | diagnostics + OTA pause; A/B tool `pov_ctl.py ab` |
| 7 | Board panicked during streaming after reconnects were added (reset_reason 4) | Not provable without a log. Strongest candidate: each reconnect closed the socket with a WebSocket close handshake, the path in which AsyncTCP deletes the connection object while its receive function still uses it (3.2). Other cross-task paths in our code removed too | **likely** | streamer closes without the handshake; no WebSocket calls from `loop()`; crash recorder (4.6) |
| 8 | Status call timed out right after `/api/play` | The old play handler read the file, checked the CRC and decoded every frame for the power cap on the web server's task (~0.3-0.5 s), and every `/api/settings` call (even `sim_rpm` only) decoded every frame again | **likely contributor** (the link was already poor) | loading moved to the player task; cap cached (4.1) |
| 9 | No way to reboot without opening the sled; `sim_rpm` lost at every reboot | Missing features | - | `POST /api/reboot`, `sim_persist` (4.2) |

**Fixed now (firmware 0.4 + tools, committed and pushed, not flashed):** fixed 64 KB animation arena owned by the player
task (any stored file plays at any time, switch measured by the board itself), uploads checked while they stream in
(no big `malloc`, no crash on a reject, temp file + rename), `/api/ota-prep` + automatic pause on every OTA start,
`/api/reboot` with a rollback guard, persistent simulated hall that steps aside for the real sensor, a crash recorder
readable over Wi-Fi (`/api/crash`), CPU/link diagnostics in `/api/status`, and the tools `ota_flash.py` (token fix,
pause + restore), `pov_ctl.py`, `pov_stream.py`, `pov_soak.py`, `mock_board.py` (+ tests).

**Your go is needed for:** flashing 0.4 (one `py tools\ota_flash.py --env pov`, which now pauses the picture by itself),
then three short tests on the real board: `pov_ctl.py ab` (2 min, tells LED power from radio from CPU), the switch +
30-minute soak (`pov_soak.py --minutes 30`), and a timed OTA while an animation plays. Section 6 has the commands.

## 2. Does the display starve `loop()`, async_tcp or Wi-Fi?

Short answer: **not by CPU**, according to the code and today's measurements. Where everything runs (arduino-esp32
3.3.12 / IDF 5.5 sdkconfig, read from the framework):

| Task | Core | Priority | Load with an animation at 150 rpm |
|---|---|---|---|
| Wi-Fi driver | 0 | 23 | - |
| esp_timer (runs the simulated hall `sim_cb`) | 0 | 22 | 2.5 calls/s, a few µs each |
| lwIP tcpip | 0 (`CONFIG_LWIP_TCPIP_TASK_AFFINITY_CPU0`) | 18 | - |
| async_tcp (all HTTP / WebSocket handlers) | 0 (`-DCONFIG_ASYNC_TCP_RUNNING_CORE=0`) | 10 | per request |
| render (captions / text only) | 0 | 5 | idle in animation mode |
| player | 0 | 3 | ~20 frame decodes/s, ~50 µs each |
| column (GPTimer + hall ISR on this core) | 1 | 23 | ≤ 0.25 ms per column × 240 columns/s ≈ **6 % of core 1** (9 % at 225 rpm) |
| loopTask (`ArduinoOTA.handle()`, OTA guard) | 1 (`CONFIG_ARDUINO_RUNNING_CORE=1`) | 1 | the rest of core 1 |

- The column task wakes ~210 µs before each column, builds both chains (60 µs typical; `build_us_max` read today
  333 µs), busy-waits the rest and sleeps until the next column (4.17 ms at 150 rpm). Nothing in it can loop without
  sleeping: every path ends in `ulTaskNotifyTake` or a one-shot alarm.
- `WiFi.setSleep(false)` is already set (no modem sleep). TX power stays at 13 dBm after the join (the open question
  from 11-13, section 7).
- The ArduinoOTA password check (PBKDF2, 10,000 rounds) runs inside `loop()` on core 1 and takes ~1 s of CPU. With 94 %
  of core 1 free that is ~1.1 s, far inside the uploader's 25 s wait, so CPU starvation does not explain "no answer to
  the authentication". All three tries got their invitation answered and then lost the auth exchange. ArduinoOTA sends
  both exchanges once (the uploader repeats only the invitation): one datagram out, one back. With loss p each way an
  exchange gets through with (1 - p)²: 0.49 at p = 30 %, 0.12 at 66 %. Three answered invitations make the 66 % figure
  unlikely for those minutes (the invitation gets two chances), but at 30-50 % losing three auth exchanges in a row
  has a 13-40 % chance. The other possibility is a `loop()` blocked for > 25 s right after answering an invitation;
  nothing in the code does that by CPU, but 0.2 made blocking calls into the web stack from `loop()` (the 2 Hz
  WebSocket push, 3.2). 0.4 removes those calls, records the longest `loop()` stall (`diag.lag1_max_ms`), and pauses the
  picture before the first OTA datagram, which covers both cases.
- Read-only check this morning, board on 0.2 with the jelly animation, simulator 150 rpm, gb 12, 118 s after a reboot: first
  status call 4.9 s, then five calls 50-74 ms; ping 6/6 (10-229 ms) then 20/20, average 16 ms, max 37 ms. So the
  display by itself, at gb 12, did not wreck the link. The 66 % loss came with more: a brighter animation and/or the
  session state after the panics and reconnect storms (dead sockets holding queued data).

What the display does change is **electrical**: LED current pulsing through the power bank, pigtail and 3 A fuse into
the DevKit's regulator, and two 8 MHz SPI clock lines running past the antenna. On 11-13 gb 31 caused a power-on reset
on the bank, and "sim_rpm 0 fixed it" (LEDs off) fits a supply or RF cause better than a CPU one. Firmware 0.4 can now
separate the three causes in two minutes (`pov_ctl.py ab`, section 6, step 2): picture on → LEDs dark but engine and SPI
running (`test_dark`) → engine running without SPI (`test_nospi`) → display paused. It also measures starvation
directly instead of guessing: `diag.lag0_ms` (a priority-1 probe on core 0, how late its 10 ms sleep ends),
`diag.lag1_ms` (how late `loop()` comes back from its 5 ms delay), `diag.col_busy_pct`, task stack headroom,
Wi-Fi disconnects and their reason code.

Software changes that do improve responsiveness regardless: heavy work moved off the async_tcp task (animation load,
cap pass, the old per-settings-call re-decode), no 2 Hz WebSocket push from `loop()` (nothing used it; it was the main
cross-task call into the web stack), and every OTA path pauses the picture first.

## 3. The crash paths

### 3.1 Rejected upload → panic (certain)

`src/main.cpp` (0.2), upload handler: on any failure it did `r->_tempObject = (void*)1;` as a flag. ESPAsyncWebServer
3.12.1 owns that pointer: `AsyncWebServerRequest::~AsyncWebServerRequest()` runs `if (_tempObject != NULL)
free(_tempObject);` (`.pio/libdeps/pov/ESPAsyncWebServer/src/WebRequest.cpp:109-110`). `free((void*)1)` hits IDF's
`heap_caps_free` assert "free() target pointer is outside heap areas" → `abort()` → panic, reset_reason 4, a moment
after the 400 answer (when the connection closed). **Every** rejected upload crashed the board.

And the reject was wrong: after writing the file, the handler `malloc(n)`ed the whole file (64,312 B) to read it back
and parse it. With an animation of 40-63 KB already in RAM, the largest free block was smaller than that, `malloc`
returned NULL and the valid file was called "bad". (`bichon_shades_orbit.pova`: 64,312 B, CRC OK, 84 frames, 22 colours,
under the 65,536 B limit; all 18 `.pova` files in the repo pass the new, stricter checks.)

### 3.2 Live streaming → panic (likely; not provable without a log)

`pov_rowwalk.py`'s reconnect called `ws.close()`, which sends a WebSocket close frame. On the board that close frame is
handled inside the TCP receive callback, and the library closes and **deletes** the connection object right there:

`AsyncClient::_recv` → (our data callback chain) → `AsyncWebSocketClient::_onData` (close frame) → `_queueControl` →
`_runQueue` → `AsyncClient::close()` → `_close()` → disconnect callback → `delete c` (the AsyncClient). When the call
chain unwinds, `AsyncClient::_recv` continues on the deleted object: it reads `_ack_pcb` and does `_rx_ack_len +=
b->len` (`.pio/libdeps/pov/AsyncTCP/src/AsyncTCP.cpp:1095-1096`). That write lands in freed heap. Usually nothing has
reused the block yet; but core 1 and the Wi-Fi driver allocate all the time, and a reused block means silent heap
corruption, which later fails an assert in the allocator (panic, reason 4). A reconnect storm on a lossy link runs this
path many times.

Our own code had two more cross-task hazards, now removed:
- `ws.textAll()` every 500 ms from `loop()` (core 1) while the async_tcp task (core 0) handles the same sockets.
- `ws.closeAll()` in ArduinoOTA's start callback, also from `loop()`. `closeAll()` iterates the client list while each
  `close()` can erase the node it is standing on (the TCP close runs the disconnect callback synchronously).
- Theoretical, not today's: the hall seqlock had two writers (hall ISR on core 1, simulator on core 0). If both ran
  in the same microsecond the sequence counter could stay odd, and every reader would spin forever (a watchdog reset,
  reason 6). Now the writers share a spinlock, and the hall ISR only watches the real sensor while the simulator runs.

`stage_frame` / `publish_palette` were checked as the brief asked: both only copy into the spare buffer under a lock
(or a single flip), so they can tear a picture for one column at worst; they cannot crash. 0.4 adds a lock for the
palette writers and lets a new animation's palette go live in the same instant as its first frame.

### 3.3 What 0.4 does so the next crash explains itself

The crash recorder (`src/pov_crash.h`): arduino-esp32 has a panic hook (`set_arduino_panic_handler`), but it only
works if the linker wraps `esp_panic_handler`, and PlatformIO's pioarduino build does not pass that flag (the Arduino IDE
build does): `firmware.map` listed the wrapper under "Discarded input sections". `platformio.ini` now adds
`-Wl,--wrap=esp_panic_handler` for `env:pov` (verified in the new ELF: `__wrap_esp_panic_handler` is linked). On any
panic, abort, assert or watchdog the hook writes reason, abort/assert message, task, core, PC, 16-deep backtrace,
uptime, free heap, the build id and **what our code was doing** (a breadcrumb set by every API handler) into RTC
memory; the next boot moves it to NVS (survives power-off). `py tools\pov_ctl.py crash` reads it and decodes the
backtrace to file:line with the matching `firmware.elf` (`ota_flash.py` now keeps a copy of every flashed ELF in
`.pio/elf_archive/`).

## 4. What changed (firmware 0.4, tools)

### 4.1 Animations: fixed arena, loads in the player task

- `setup()` allocates a 64 KB arena right after LittleFS mounts, before Wi-Fi, while the heap is still one piece. The
  playing file lives there; nothing on the play path allocates memory any more. `/api/status` shows `heap_max_block`
  (the largest free block) and `arena`.
- `POST /api/play {"name": ...}` now only checks the name and that the file exists (a few ms), queues the load and
  answers `200 {"ok":true,"queued":name}`. The player task reads the file into the arena, checks the CRC, decodes every
  frame once for the power cap (and refuses palette indices ≥ the palette size), and swaps it in at a refresh tick
  together with its palette. While it loads, the column keeps showing the last frame. `/api/status` `load` =
  `{state: queued|loading|ok|error, name, err, ms}`; `ms` is the board's own load time. Errors say why ("not found",
  "damaged file (CRC or structure)", "bad frame data", "no animation memory").
- Brightness changes reuse the worst-case current cached at load (no re-decode); the old handler decoded every frame
  on every `/api/settings` call.
- Expected switch time: 64 KB LittleFS read ~0.1-0.2 s + CRC ~15 ms + cap pass ~1.5-2 ms per frame (86 frames ≈ 0.15 s,
  144 ≈ 0.3 s) → **~0.3-0.5 s**, against the 2 s target. Not yet measured on the board (section 6, step 3).

### 4.2 Uploads, reboot, simulator

- Upload: the file is checked by `pova_check_*` (new in `lib/povcore/pova.h`, host-tested) as the chunks arrive, written
  to `/anims/_upload.tmp` and renamed into place only when complete and valid. Per-request state is a real `calloc`ed
  struct (the server's `free()` is now correct). One upload at a time (409 if busy); a client that disconnects
  mid-file leaves no half file. Answers: 200 with name/bytes/frames, 400 `bad file: <reason>`, 413 too big, 409 busy,
  507 storage full. Stricter than before: ≥ 1 frame, RLE runs that fill each frame exactly, indices < palette size.
- `POST /api/reboot` (token): blanks the LEDs, answers, restarts. Refused with 409 while a fresh OTA image is still
  "pending" (the first ~15 s after an OTA boot, when a reset makes the bootloader roll back); `?force=1` overrides.
- `POST /api/settings {"sim_rpm":150, "sim_persist":true}` keeps the simulator across reboots (`sim_persist:false` or
  `sim_rpm:0` + persist clears it). A saved simulator starts at boot, so the IP text shows with the motor off. It
  steps aside when the real hall reports a steady rotation (two periods within 5 %, last pulse < 1 s ago, so noise on
  the lead can't trigger it) and comes back 2 s after the real pulses stop.
- Also saved: `tx_dbm` (TX power after the join, default 13 = unchanged). Not saved (diagnostics): `test_dark`,
  `test_nospi`.

### 4.3 OTA while the picture runs

- `POST /api/ota-prep?secs=N` pauses the display (LEDs dark, simulator off, player idle, live sockets closed, TX
  19.5 dBm) for N s (default 180, 0 = until reboot); `POST /api/resume` undoes it; it also resumes by itself at the
  deadline if no update arrived. Every OTA start pauses anyway (ArduinoOTA start callback, `/update`), and a failed
  update resumes.
- `tools/ota_flash.py` calls `ota-prep` before the first UDP packet (on 0.2 it does `sim_rpm 0` + `/api/stop`, so the
  first flash of 0.4 works mid-animation too), checks the link, flashes, verifies the build id, then **puts the picture
  back** (simulator rpm + animation; `--no-restore` skips) and prints the total time.

### 4.4 Token fix

`read_secret()` returns `None` (no file or no define) or the value, which may be `""`. The `/update` fallback sends
the token header only when the token is non-empty, and a 401 now says which case it is ("the board wants a token, and
src/wifi_secrets.h has POV_TOKEN """ or "built with a different POV_TOKEN").

### 4.5 Live streaming

`tools/pov_stream.py` (rowwalk, stripes, solid) and the library behind `pov_soak.py`:
- after each frame it sends `{"live":1,"ack":n}`; 0.4 answers `{"live_ack":n}`; at most 2 frames are ever
  unacknowledged, so the sender runs at whatever the link carries (old firmware: fixed pace ≤ 4 frames/s);
- reconnects with backoff 1-2-4-8 s and gives up at the end of the run;
- closes sockets **without** the WebSocket close handshake (plain TCP close, the library's safe path, 3.2).
`pov_rowwalk.py` (uncommitted, from the laptop session) and `pov_diag.py` still send unpaced; use `pov_stream.py
rowwalk` / `stripes` instead.

### 4.6 Diagnostics in `/api/status` (0.4)

`load{}`, `heap_max_block`, `arena`, `paused`, `sim_saved`, `sim_yielded`, `real_pulses`, `reset` (name),
`wifi{tx_dbm, tx_dbm_set, channel, disconnects, last_reason, ws_clients}`, `diag{col_busy_pct, lag0_ms, lag0_max_ms,
lag1_ms, lag1_max_ms, test_dark, test_nospi, live_frames, live_bad, api_reqs, fs_free, stack_free{column, player,
render, probe, loop, async_tcp}}`, `crash{count, reason, msg, task, boot}`. `GET /api/crash` has the full record.
Existing keys are unchanged (the tools and the phone page keep working).

## 5. How it was verified (no board)

| Check | Result |
|---|---|
| `tools\pio.cmd run -e pov` | builds clean (no warnings from our code); RAM 26.1 % static, flash 75.8 % of the 1.5 MB slot; build id `0cbac218f918dca2`; `__wrap_esp_panic_handler` and `set_arduino_panic_handler` linked |
| Host tests `test_pova` (`pio test -e native`) | 9/9: the 5 old ones + 4 new for the streaming check: the dog file accepted in 14 chunkings (1 B ... 64 KB), CRC / truncation / trailing / magic / header rejects with the right reason, every 3rd byte of the dog file corrupted → both the full parser and the streaming check reject, a crafted file with an out-of-range palette index rejected |
| Whole native suite | 45 of 48 cases pass; `test_frame` (1) and `test_povmap` (2) fail on **stale vectors from `2dd3b38`** (as-built rail shift regenerated `povmap.h` but not `test/vectors/vec_povmap.h` or `test_frame_layout`'s hand-coded LED position). Not touched by this work; see 7 |
| All 18 `.pova` files in the repo vs the stricter rules (Python mirror) | 18/18 accepted |
| `tools/mock_board_test.py` (new: the tools against `mock_board.py`, the API + WebSocket + ArduinoOTA on the PC) | **10/10 scenarios pass** (listed below) |
| `tools/ota_sim_test.py` (11-13 self-test, after refactoring `ota_sim.py` into a reusable `serve()`) | **6/6 as expected** (espota and ota_flash.py vs the simulator, 5 s stall with 1 s vs 8 s timeout, wrong password) |
| Read-only `GET /api/status` + ping of the real board | section 2. At 11:46 the board stopped answering (ARP "destination host unreachable": switched off or out of range); this session only ever sent GET requests |

The mock scenarios: OTA on a 0.4 board playing with sim 150 (pause before the invitation, new build verified, sim and
animation restored); the same on today's 0.2 build (stopped the old way, restored); ArduinoOTA unreachable → `/update`
fallback with `POV_TOKEN ""` (today's bug); a board that wants a token → clear exit 1; `pov_ctl play` timed under 2 s
and a missing animation → exit 1; reboot refused while the image is pending, then works, saved sim back after boot;
a panic leaves a record that `pov_ctl crash` reads; streaming paced by acks, survives a cut link, sends **no** close
frame; `pov_soak` passes on a healthy mock and fails when the mock panics mid-soak.

What the mock cannot show: real flash and LittleFS timing, the real heap after hours, the ESP32's Wi-Fi under LED load,
and whether the library's close-path bug (3.2) was today's panic. Those are section 6.

## 6. What needs the board (your go), in this order

All from `software\firmware` on the desktop PC (or the laptop). Nothing here needs USB or opening the sled.

1. **Flash 0.4** (the picture pauses and comes back by itself):
   `py tools\ota_flash.py --env pov` (build first if needed: `tools\pio.cmd run -e pov`). Note the total time it prints
   (target < 90 s with an animation playing). If it fails, it restores the picture and the board is unchanged.
   Then `py tools\pov_ctl.py sim 150 --persist` once.
2. **A/B link test, 2-3 min** (changes the picture briefly, puts it back): pick your usual animation and brightness,
   then `py tools\pov_ctl.py ab --secs 30`. Reading: A bad + B good → LED current is the problem (bank / pigtail /
   regulator ripple: hardware fix, see 7); B bad + C good → the SPI lines radiate; C bad + D good → CPU / software
   (send me the `diag` numbers); all good → today's trouble was the session state, and 0.4 already removes its causes.
   Worth repeating at gb 12 and gb 31.
3. **Switch test + 30-minute live soak**: `py tools\pov_soak.py --minutes 30` (plays the 6 largest stored animations
   and times each, then streams paced stripes for 30 min while watching for reboots and crash records; PASS/FAIL +
   `.pio/soak_logs/*.json`).
4. **OTA while playing, timed**: play something, then `py tools\ota_flash.py --env pov --force` (re-flashes the same
   build; the log line "OK in N s" is the number for the < 90 s target).
5. If anything reboots: `py tools\pov_ctl.py crash` and send me the output (decoded backtrace).

Bench/USB-only items: none required. Only if step 2 points at the supply: scope 5 V and 3V3 at the DevKit with the picture
at gb 31 (ripple and dips during Wi-Fi bursts), or try a bulk capacitor at the DevKit's 5 V input.

## 7. Decisions and open points for you

1. **Flash 0.4?** Needs your go (rule for this job). Rollback protects it: if 0.4 crashes or never gets Wi-Fi, the
   board goes back to 0.2 by itself within 2 minutes.
2. **TX power after the join** (open since 11-13): 13 dBm now. 19.5 dBm gives the uplink 6.5 dB more margin for ~50 mA
   more peak current. Try it in the A/B test: `POST /api/settings {"tx_dbm":19.5}` (saved), then `pov_ctl.py ab`.
3. **The library close-path bug (3.2):** our tools now avoid it, but a browser or another client that closes a socket
   politely still runs it. Options: report upstream / check a newer AsyncTCP, or carry a small local patch. Worth it
   only if a crash record ever points there.
4. **Stale host-test vectors since `2dd3b38`** (3 failures in `test_frame` / `test_povmap`): regenerate with
   `py software/firmware/test/gen_vectors.py` and update `test_frame_layout`'s expected LED, then re-check that the
   C++ map still agrees with the Python model. Separate from this review (the height map itself), so left as is.
5. `pov_rowwalk.py` and `strip_tester.py` are uncommitted files from the laptop session; I left them alone.

## 8. How to explain it

- **"Slow" was a chain, not one bug.** A misleading 404 (heap) → no remote reboot → OTA used as a reboot → OTA fails
  while the picture runs → its fallback blocked by a tool bug. Each link was small; together, 7 minutes. Fixing the
  chain means every step gets a fast, clear failure and a remote way out.
- **Fixed arenas beat malloc on small embedded heaps.** 145 KB free, but the biggest *contiguous* block mattered. A
  64 KB arena allocated once at boot makes "any stored file can play" a guarantee instead of a probability.
- **Validate streams, not files.** A 60-byte state machine checks a 64 KB upload as it arrives; no buffer, and the
  error says which byte rule failed.
- **Know who owns a pointer.** The web server `free()`s `_tempObject`; using it as a flag crashed the board on every
  rejected upload. Same lesson in the library itself: deleting a connection inside its own receive callback.
- **Measure starvation instead of guessing it.** Task/core/priority table + a 10 ms probe per core turned "the loop is
  starved" into a number. Here the numbers said: not CPU, look at power and RF, and a 4-step A/B test settles it.
- **Make the next crash explain itself.** A panic hook that writes to RTC memory + NVS, decoded with addr2line from an
  archived ELF: post-mortems over Wi-Fi on a sealed, spinning device.
- **Flow control for live data:** pace on the receiver's acknowledgements with a window of 2; never send faster than
  the link drains.
- Demo idea: `pov_ctl.py play` timings before/after; the A/B table; a deliberate crash record decoded to file:line.

## Appendix: files

- Firmware: `src/main.cpp` (0.4), `src/pov_crash.h` (new), `lib/povcore/pova.h` (`pova_check_*`), `platformio.ini`
  (version, `--wrap=esp_panic_handler`, async_tcp stack 10 KB), `test/test_pova/test_main.cpp` (+4 tests).
- Tools: `ota_flash.py` (token, pause/restore, ELF archive, `POV_HTTP_PORT` for tests), `ota_sim.py` (reusable
  `serve()`), `pov_ctl.py`, `pov_stream.py`, `pov_soak.py`, `mock_board.py`, `mock_board_test.py` (all new).
- API added in 0.4: `POST /api/ota-prep[?secs=N]`, `POST /api/resume`, `POST /api/reboot[?force=1]`,
  `GET/DELETE /api/crash`, settings `sim_persist`, `tx_dbm`, `test_dark`, `test_nospi`, WebSocket `{"live":1,"ack":n}`.
