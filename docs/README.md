# Documents

Two kinds of document live here.

**Written for you:** [BUILD.md](BUILD.md) (the build order), [BOM.md](BOM.md) (the parts), and the READMEs in
[`cad/`](../cad/README.md) and [`software/`](../software/README.md).

**Written during the build:** the dated reports below. They are the working documents of three weeks of design,
bench work and debugging, written by the AI agents that did the work and addressed to me ("Prepared for Brian"),
with my open questions still in them. I am publishing them because they are the honest record of how an AI designs
hardware: the calculations, the checks, the wrong turns and the corrections.

Read them with three things in mind:

- **A report describes the day it was written.** The design went through fifteen revisions (a to o). The current
  machine is rev o,
  and [`cad/README.md`](../cad/README.md) says exactly which files it is made of.
- **Where a report and the firmware disagree, the firmware is right.** Two known cases: the hall sensor is on GPIO 26
  (not 27), and the strips sit one rail back from the drawings (`SET_SHIFT = 2`).
- **On safety, the README is the current word.** Some early reports treat the fuse as optional. It is not, and the
  machine has one.
- **They are lightly redacted.** Machine names, folder paths and home-network addresses are replaced with
  placeholders such as `<column-ip>`. A few figures are left out, with a note where each was: pictures of the
  animations (which are not part of this release), one seller's drawing and one video still. Links to documents that
  are not in this repository are plain text.

## Start here

| Report | What it is |
|---|---|
| [2026-11-11 Prompt to light](2026-11-11-prompt-to-light-process.md) | The whole chain from a spoken sentence to photons, stage by stage, with timings and the gaps found |
| [2026-11-22 Drive review](2026-11-22-drive-redesign.md) | Why the column would not get past 150 rpm: the factory grease in the big bearing. The best single read on the mechanics |
| [2026-11-23 Check, pack, send: audit](2026-11-23-check-pack-send-audit.md) | Every check between a scene script and the LEDs, the 2.6 A cap and where it comes from, worst-case tests, open findings |
| [2026-11-07 Pipeline speed](2026-11-07-pipeline-speed-investigation.md) | 70 s to 5 s per animation: a kit of tested parts plus a smaller model beat a bigger model writing everything |
| [2026-11-04 Wiring build guide](2026-11-04-wiring-build-guide.md) | The soldering document: strips, jumpers, the carrier board layer by layer |

## Hardware, in order

| Date | Report | Rev | What changed |
|---|---|---|---|
| 11-01 | [Feasibility](2026-11-01-feasibility.md) | v1 | The first numbers: size, speed, refresh, power. Describes an 8-strip design that was never built |
| 11-01 | [CAD build](2026-11-01-cad-build.md) | v1 | The first assembly in Fusion, with clearance checks and balance |
| 11-01 | [Parts and links](2026-11-01-parts-and-links.md) | v1 | The first shopping list |
| 11-02 | [24 strips and tie rods](2026-11-02-v2-24-strips-tie-rods.md) | v2 | The display as built: 24 strips in 3 interleaved sets, 42 x 96, tie rods clamping the caps |
| 11-02 | [Electrical design](2026-11-02-electrical-design.md) | v2 | Schematics, carrier layout and netlist, power and signal numbers, bring-up plan |
| 11-02 | [Wiring CAD](2026-11-02-wiring-cad.md) | v2 | The carrier and all 120 wires modelled as bodies, with clearance and bend-radius checks |
| 11-03 | [FDM optimisation](2026-11-03-fdm-optimisation.md) | f | Every printed part reworked for printing: materials, orientation, no supports |
| 11-04 | [SPI signal investigation](2026-11-04-spi-signal-investigation.md) | | A data-signal fault on the bench, traced to one miswired resistor on the test rig; 8 MHz confirmed |
| 11-09 | [Rim bearing](2026-11-09-rev-k-rim-bearing.md) | k | The tube's top wobbled 3 to 5 mm. The rotor moves onto a 6820 bearing in a collar |
| 11-13 | [Rotor power and wobble](2026-11-13-rotor-power-and-wobble.md) | m | The 225 rpm shake explained; power from the base through a slip ring |
| 11-13 | [Rev m CAD](2026-11-13-rev-m-cad.md), [shopping list](2026-11-13-rev-m-shopping-list.md) | m | Motor off-axis on a belt, slip ring on the axis |
| 11-17 | [Drive redesign](2026-11-17-rev-n-drive-redesign.md) | n | The printed pulley broke twice. The drive becomes a hub on its own bearing with four pins |
| 11-19 | [Bench diagnosis](2026-11-19-rev-n-bench-diagnosis.md) | n | Built, and it ran badly. Where the torque went |
| 11-20 | [Rev o CAD](2026-11-20-rev-o-cad.md) | o | The as-built drive as the baseline, fit coupons, the slip-ring mast and pogo contacts (option D) |
| 11-21 | [Concentricity](2026-11-21-rev-o-concentricity.md) | o | Proud inserts, tilted parts, and a pass over the whole stack's alignment |
| 11-22 | [Drive review](2026-11-22-drive-redesign.md) | o | The grease. Keep rev o |
| | [Measurements](measurements.md) | | The bench log: every dimension and reading I took, numbered |

## Software and firmware

| Date | Report | What it is |
|---|---|---|
| 11-02 | [Live captions](2026-11-02-live-captions.md) | Speech to captions on the column in under a second, in simulation; why moving text tears on camera |
| 11-03 | [Firmware build](2026-11-03-firmware-build.md) | Toolchain, the first compile, the host-tested core |
| 11-06 | [Pipeline vs hand-built](2026-11-06-pipeline-vs-handbuilt.md) | The first pipeline runs against animations an agent built by hand |
| 11-07 | [Pipeline speed](2026-11-07-pipeline-speed-investigation.md) | The benchmark that led to the kit |
| 11-11 | [Prompt to light](2026-11-11-prompt-to-light-process.md) | The end-to-end trace |
| 11-14 | [Wi-Fi control review](2026-11-14-wifi-control-review.md) | Firmware 0.4: a fixed arena, a crash recorder, a mock board for testing the tools |
| 11-23 | [Infinite Biscuit](2026-11-23-infinite-biscuit.md) | An endless gallery: the model writes the next clip while the current one plays |
| 11-23 | [Live demo pipeline](2026-11-23-live-demo-pipeline.md) | A warm process, the live step view, and fitting every file to the board's 64 KB |
| 11-23 | [Check, pack, send: audit](2026-11-23-check-pack-send-audit.md) | The audit of the safety checks |
| 11-24 | [Orbit Rally](2026-11-24-orbit-rally.md) | A paddle game on a round screen, and what a slow Wi-Fi link does to live frames |

Raw benchmark logs for the live-demo report are in [`data/`](data/).

## Not here

The video-production documents (storyboards, shot lists, edit reports), a product study, a concept study for a
different display, and my machine-setup notes stayed in my private repository. So did the animations, and four
reports that need a hand edit before they can be public: two design reviews (`2026-11-02-qa-review.md`,
`2026-11-03-qa-review-2.md`), the first software design report (`2026-11-02-software-and-ai-content.md`) and a
post-mortem of the early over-the-air update failures (`2026-11-13-ota-failure-review.md`). The code and the other
reports still cite them by name.

## Licence

These documents and their figures are [CC BY 4.0](../LICENSE-DOCS). The schematics, layouts, wiring tables and other
design files among them are Open Hardware under the [CERN-OHL-P v2](../LICENSE-HARDWARE). See
[LICENSING.md](../LICENSING.md).
