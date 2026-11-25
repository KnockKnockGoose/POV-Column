# Licensing

Copyright (c) 2026 Brian Mahoney. Three licences, by kind of file:

| What | Where | Licence | Full text |
|---|---|---|---|
| **Software**: firmware, the animation pipeline, the kits, the simulator, the game, tests, calculation scripts, the scripts in `cad/` | `software/`, `calc/`, `cad/*.py` | [MIT](https://spdx.org/licenses/MIT.html) | [LICENSE](LICENSE) |
| **Hardware design**: CAD models (STL, 3MF, STEP), print projects and sliced plates, schematics, the carrier-board layout and netlist, wiring tables | `cad/` (except its `.py` scripts), `docs/img/elec_*`, `docs/img/guide_*`, `docs/img/wiring_*`, `docs/bom.csv`, the release's STEP and print-file archives | [CERN-OHL-P v2](https://spdx.org/licenses/CERN-OHL-P-2.0.html) (permissive) | [LICENSE-HARDWARE](LICENSE-HARDWARE) |
| **Documentation and images**: the READMEs, the reports in `docs/`, renders, diagrams, photos and footage frames | `README.md`, `docs/` (except the hardware files above), `media/`, every other `README.md` | [CC BY 4.0](https://spdx.org/licenses/CC-BY-4.0.html) | [LICENSE-DOCS](LICENSE-DOCS) |

In short: build it, change it, sell what you build, and say where it came from. All three licences are permissive, and
none of them is copyleft.

## Hardware notice (CERN-OHL-P v2)

> Copyright Brian Mahoney 2026.
>
> This source describes Open Hardware and is licensed under the CERN-OHL-P v2.
>
> You may redistribute and modify this source and make products using it under the terms of the CERN-OHL-P v2
> (https://ohwr.org/cern_ohl_p_v2.txt).
>
> This source is distributed WITHOUT ANY EXPRESS OR IMPLIED WARRANTY, INCLUDING OF MERCHANTABILITY, SATISFACTORY
> QUALITY AND FITNESS FOR A PARTICULAR PURPOSE. Please see the CERN-OHL-P v2 for applicable conditions.
>
> Source location: https://github.com/KnockKnockGoose/POV-Column

If you pass on modified design files, the licence asks you to keep these notices and to add one saying that you
changed them, with the date and a short description (section 3.3).

## Third-party software

Nothing third-party is vendored in this repository. The build tools fetch what they need, at the versions pinned in
`software/firmware/platformio.ini` and `requirements.txt`.

| Component | Version | Licence | How it is used |
|---|---|---|---|
| [Arduino core for ESP32](https://github.com/espressif/arduino-esp32) | 3.3.12 | LGPL-2.1-or-later | linked into the firmware |
| [ESP-IDF](https://github.com/espressif/esp-idf) and its components (FreeRTOS, lwIP, mbedTLS, LittleFS and others) | 5.5.5 | Apache-2.0, with MIT / BSD parts | linked into the firmware |
| [ESPAsyncWebServer](https://github.com/ESP32Async/ESPAsyncWebServer) | 3.12.1 | LGPL-3.0 | linked into the firmware |
| [AsyncTCP](https://github.com/ESP32Async/AsyncTCP) | 3.5.0 | LGPL-3.0 | linked into the firmware |
| [ArduinoJson](https://github.com/bblanchon/ArduinoJson) | 7.4.3 | MIT | linked into the firmware and the host tests |
| [Unity](https://github.com/ThrowTheSwitch/Unity) | 2.6.1 | MIT | host unit tests only |
| [pioarduino platform-espressif32](https://github.com/pioarduino/platform-espressif32) | 55.03.312-1 | Apache-2.0 | build platform (not distributed) |
| NumPy, Pillow, requests, websocket-client, websockets, matplotlib and the optional packages in `requirements.txt` | as installed | their own (BSD / MIT-CMU / Apache-2.0 / LGPL for some) | imported by the Python tools, not distributed |

**About the prebuilt firmware images attached to a release.** A `.bin` contains the LGPL libraries above in linked
form. The complete source of the application is in this repository under the MIT licence, with the exact library
versions pinned and the build command in `software/firmware/README.md`, so you can rebuild the image against a
modified copy of any of those libraries. That is what the LGPL asks for.

## Third-party hardware and trademarks

- **No vendor CAD is included.** Every body in the STEP assembly and every STL was modelled for this project. Bought
  parts (the motor, bearings, slip ring, ESP32 board, LED strips) appear as simple stand-in bodies with the right
  envelope. Take their datasheets and drawings from the sellers.
- Product names in the bill of materials (Bambu Lab, Espressif, INIU and so on) belong to their owners and are there
  to identify the part I used. None of them sponsors or endorses this project.
- Fonts: the two caption fonts (5x7 and 7x9) were drawn for this project as text grids in
  `software/captions/font.py`. No font file is shipped.

## What is not in this repository

The animations shown in the videos (the `.pova` files and the scripts that drew them) are not part of this release.
The code that makes animations is: the kits, the pipeline and the simulator.
