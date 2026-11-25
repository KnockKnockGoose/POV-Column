# POV pipeline vs hand-built: two bichon animations

*Prepared for Brian, 2026-11-06, by Claude (Opus 5.5) on the desktop PC. Simulations only (the column isn't built yet).*

Outputs (videos, .pova, generated scripts, sims): `<video>/2026-11-06 POV pipeline vs hand-built/` on the desktop PC (not in git).

This test checks the prompt-to-animation pipeline (`software/pipeline/pov_request.py`, built 11-02). I gave it the two
requests that the laptop's agents hand-built this morning. Each prompt went through the pipeline as designed: one
`claude -p` call (Opus 5.5) writes a scene script, which is then run in a sandbox, validated and previewed, with
`--scope public --dry-run`. The results are compared with the hand-built versions in
`software/content/public/bichon_{jetski,shades}_front.*`.

## Files

| File | What it is |
|---|---|
| `compare_jetski_pipeline_vs_handbuilt.mp4` | 960x1056, 9.6 s. **Top:** "pipeline (one prompt)" (its 1.6 s loop, repeated). **Bottom:** "hand-built (agent)" (`bichon_jetski_front_sim.mp4`). |
| `compare_shades_pipeline_vs_handbuilt.mp4` | 960x1056, 8.6 s. **Top:** the pipeline's 3.0 s loop, repeated. **Bottom:** `bichon_shades_front_sim.mp4`. |
| `jetski/`, `shades/` | Pipeline output for each prompt: the `.pova` file, the generated scene script `.py`, the `.json` sidecar, `pipeline_report.json` (the full stage report, including the validator output) and `previews/` (the pipeline's own preview step). |
| `*/sim/` | `simulate.py --gif --mp4 --stills --width 960 --scale 4 --seconds <loop>`. Same side-by-side format as the laptop's sims: flat frame on the left, camera model of the column on the right. |

## Prompts and run stats

| | Jet ski | Sunglasses |
|---|---|---|
| Prompt | "a fluffy white bichon frise riding a jet ski over waves, looped, for the video" | "a big fluffy bichon frise head; a paw comes up and slides dark black sunglasses on, like the start of CSI, for the video" |
| Command | `py software/pipeline/pov_request.py "<prompt>" --scope public --dry-run --out-dir <dir>` | same |
| Attempts | **1** (rendered first time, no repair round) | **1** |
| LLM time | 99.7 s (9,275 output tokens, 6,327 of them thinking) | 174.2 s (16,551 output tokens, 12,677 thinking) |
| Wall time (whole pipeline) | 102 s | 178 s |
| API-equivalent cost (reported by the CLI; billed to the subscription) | $0.24 | $0.38 |
| Generated script | 133 lines | 199 lines |
| Result | 24 frames @ 15 fps = **1.6 s** loop, front mode, 12 colours | 45 frames @ 15 fps = **3.0 s** loop, front mode, 7 colours |
| Validator | `ok: false`: "front mode but only 78 % of the subject's pixels are inside columns 32-63" (the waves run all the way round the drum, so this warning is expected). Kept, as designed: the pipeline has no fix round for warnings. | `ok: true`, no warnings |

## Validator side by side (same `povanim.validate`)

| | Jet ski: pipeline | Jet ski: hand-built | Shades: pipeline | Shades: hand-built |
|---|---|---|---|---|
| Loop | 1.6 s, 24 fr | 9.6 s, 144 fr | 3.0 s, 45 fr | 8.6 s, 86 fr @ 10 fps |
| Palette | 12 | 13 | 7 | 22 |
| Lit fraction (mean) | 11 % | 22 % | 11 % | **85 %** (full sunset background) |
| Peak current @ gb 31 | 1.67 A | 2.33 A | 2.29 A | **4.87 A**, so it has to run at gb 16 (half brightness) |
| Subject in front window (min) | 78 % | 85 % | 100 % | 69 % |
| Loop seam ratio | 1.09 (smooth) | 2.16 | 0.0 (last frame = first, so one doubled frame at the seam) | 113 (the iris-out is deliberate) |
| Validator ok | no (front-window warning) | no (front window) | **yes** | no (seam, front window, current) |

## What each one looks like

- **Jet ski, pipeline:** a side-on bichon in an orange life vest on a red-and-yellow jet ski, bobbing over scrolling blue
  waves with spray. It reads as "a white dog on a jet ski". The head is a profile blob with a tongue and a grey ear,
  but no visible eye or nose, so it doesn't read as a *bichon* in particular. There is no sky and no sun. It's a
  tight 1.6 s bob loop.
- **Jet ski, hand-built:** a bigger, front-facing face with eyes and a nose, a sun, splash detail and a 9.6 s
  sequence. It is more character-driven and reads better on camera.
- **Shades, pipeline:** a clean, cute front-facing head (eyes, nose, tongue, cream ears). Over 3 s, a paw rises from
  the bottom, slides the glasses up onto the eyes, a glint sweeps the lenses, it holds, then the glasses drop away
  and the loop restarts. The gag lands and the frame is electrically gentle, but it's small (about 20 rows) on an
  empty black drum, with no turn, squint or smirk.
- **Shades, hand-built:** a big bust filling the drum against a sunset, with a slow turn to camera, a squint, the
  shades going on, a glint, a smirk and an iris out. It is far more cinematic, and it took an agent session plus
  a shared `povgen/bichon_head.py` helper (304 lines) to build. The hand-built version is also over the current
  cap at full brightness.

## Fixes made to the pipeline

- **Added `--out-dir`** (2 lines in `pov_request.py`). Public scope always wrote to `software/content/public`, so the
  test could not run without writing next to the laptop's files. Nothing else had broken since 11-02: the `claude -p`
  flags, paths, sandbox runner, validator and preview all worked unchanged with Claude Code 2.1.319.

## Verdict (honest, 5 lines)

1. The pipeline works end to end and produced both animations first time: no repair round, no crash, both under
   3 minutes and about $0.25-0.40 of model time.
2. Both results are recognisably the request (a dog on a jet ski over waves; a paw sliding shades on with a glint),
   and the pipeline output is electrically better behaved than the hand-built versions (11 % lit, under the cap at
   full brightness).
3. On quality, the hand-built versions clearly win: bigger subjects, backgrounds, an 8-10 s story with acting beats,
   and a face that reads as a bichon. The pipeline gives short 1.6-3 s icon-style loops.
4. Most of that gap comes from the generator prompt ("loops should last 1-3 s", "keep lit fraction < 15 %",
   "characters 14-24 rows") and from having no visual feedback loop. It is not a model-capability limit.
5. For Video 2 the fair line is: "one sentence gets you a working, safe, on-model loop in 2 minutes; an agent with
   an hour and a feedback loop gets you something you'd put in a thumbnail."

## What to fix in the pipeline (in priority order)

1. **Story mode in the generator prompt.** When the request describes a sequence of beats, allow 6-10 s loops and
   larger subjects (up to the full 42 rows), with a background, and use the validator's `gb_recommended` instead of
   capping the lit fraction at 15 %.
2. **A visual self-check round.** Render the contact sheet and send it back to Claude (`claude -p` with the image)
   once, asking "does this read as the prompt? fix it". This is the step the hand-built agents had and the pipeline
   lacks. Wire the existing validator warnings into the same round (they are currently only logged).
3. **Raise `timeout_llm_s` from 240 to about 420 s.** The shades run took 174 s of its 240 s budget, so a longer story
   prompt will time out.
4. **Expose `povgen/bichon_head.py`** (and future character modules) to the generator. Add it to `ALLOWED_IMPORTS`
   and the prompt's API list so recurring characters can be reused instead of redrawn.
5. **Small: avoid duplicating frame 0 as the last frame** (the shades loop holds one frame twice at the seam). Add a
   rule to the prompt, or a validator check for `seam_ratio == 0`.

## How to explain it

- The pipeline is a **constrained code generator**. The LLM writes a small deterministic Python program against a
  20-function drawing API, rather than outputting pixels. The program is linted for imports, run in a sandboxed
  subprocess with a timeout, and checked by a physics-aware validator (current draw, front window, loop seam) before
  anything reaches the hardware.
- The comparison shows the usual trade-off: **one-shot generation is reliable and safe but generic**. Agent-in-the-loop
  work (render, look, revise) is where quality comes from. The next step is to put that render-and-look step inside
  the pipeline.
