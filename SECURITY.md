# Security

The column is a hobby device for a bench and a home network. This page says what it exposes, what the defaults are,
and how to report a problem.

## What the firmware exposes

| Thing | Default | What to do |
|---|---|---|
| Web API and page on port 80 (`/api/...`, `/update`) | **No authentication** while `POV_TOKEN` is `""` | Set `POV_TOKEN` in `src/wifi_secrets.h`. Mutating calls and the WebSocket then need it (`X-POV-Token` header or `?token=`) |
| WebSocket `/ws` (live frames, captions) | same token rule | |
| Over-the-air updates, ArduinoOTA (UDP 3232) | password `OTA_PASS`, placeholder `FILL_IN` | Set your own. Anyone who can reach the board and knows the password can replace the firmware |
| Firmware upload in the browser (`GET` / `POST /update`) | protected by `POV_TOKEN` only, so **open while the token is empty** | Set `POV_TOKEN`. This path does not ask for the OTA password |
| The bench sketch (`phase0`): a command port on TCP 23 | **no authentication** | It is a bring-up tool. Don't leave it on a board that stays on a network you share |
| Fallback access point | SSID `POV-Column`, password `povcolumn`, started when the board cannot join your Wi-Fi | The password is public (it is in this repository). Change it in `src/main.cpp` before you build, or keep the board off when it has no network |
| mDNS name | `pov.local` | |

Traffic is plain HTTP on your local network. There is no TLS. Do not forward the board's ports to the internet.

**The prebuilt images attached to a release are built with the placeholders.** They are for a first test: the board
comes up as the `POV-Column` access point at `192.168.4.1` with no token. For anything longer than that, build your
own image with your own `wifi_secrets.h`.

`src/wifi_secrets.h` and `platformio_local.ini` hold your credentials and are ignored by git. A firmware image built
from them contains your Wi-Fi name and password in clear text, so do not share images you built yourself.

## What the PC tools do

- `pipeline/pov_request.py` runs the model-written scene script in a subprocess with a time limit. That catches
  honest mistakes. **It is not a sandbox against hostile code**: a scene script is Python and runs with your rights.
  Run scripts you did not write the way you would run any other downloaded Python.
- The model call is your own Claude Code (`claude -p`), under your login. This project holds no API key and sends
  nothing anywhere else. The only other network traffic is to the column.
- `pipeline/pov_serve.py` and `firmware/tools/mock_board.py` listen on `127.0.0.1` only. The mock board's OTA
  password (`simtest`) is a fixture for the tests, not a secret.
- `firmware/tools/ota_flash.py` can test whether your PC's firewall lets the board connect back, by asking a second
  machine on your LAN over SSH. That test is off unless you set `POV_PROBE_SSH=user@host`.

## Electrical and mechanical safety

That is in the [README](README.md#safety). The current cap is a safety function. Reports of ways to get past it are
welcome as ordinary issues.

## Reporting

For a security problem, please use GitHub's private reporting ("Report a vulnerability" on the Security tab) instead
of a public issue. I will answer as soon as I can. This is a one-person project.
