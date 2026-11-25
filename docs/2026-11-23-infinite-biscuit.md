# Infinite Biscuit: an endless live gallery for the POV column

**Prepared for Brian** · Claude (Opus 5.5), pov-infinite-biscuit agent on the desktop PC · 2026-11-23
Inputs: your 11-23 brain dump (the "infinite Biscuit" idea), the Part 3 storyboard (section 7, live request gallery), the 11-22 meadow scene (`%LOCALAPPDATA%\POVColumn\home\20261122-133139_*`), `software/pipeline/pov_request.py` (used as a library, not edited), scenekit, the firmware's REST API and storage limits.
Outputs: `software/povgen/biscuit_kit.py`, `software/pipeline/infinite_biscuit.py`, `software/pipeline/infinite_biscuit_sentences.csv`, `software/pipeline/prompts/infinite_biscuit.md`, `software/tests/infinite_biscuit_mock_test.py`, this report. The 48 generated clips are AI media, so they live in the home folder (`%LOCALAPPDATA%\POVColumn\home\infinite_biscuit\clips\`), not in git and not in `software/content/public`. Which ones go public is your call.

---

## Summary

Biscuit walks round the column through the 11-22 meadow. Every two laps (16 s) he comes back round doing something new: riding a skateboard, mowing the lawn, flying a kite, driving a little red car, riding a hot-air balloon. Each action is one sentence ("Biscuit" + verb + object) that Claude turns into a short Python scene script through the same pipeline as your F9 requests. The script is rendered in the sandbox, checked, fitted to the column's 64 KB, and played back to back. Every clip uses one shared Biscuit drawing, so he looks the same throughout. A cached library keeps the playlist smooth on camera, and a background generator keeps making new clips and queues each one as soon as it's ready. Main can also add a sentence you say out loud, and it plays next.

**The numbers ("seconds, not minutes"):** 48 clips were generated with 0 failures. From sentence to a playable file the median is **4.7 s**: 90 % within 6.5 s, fastest 2.7 s, slowest 14.2 s. Claude's share is a median **4.0 s**, writing **20 lines** of code (range 11-44). The files are 46-60 KB, all under the 64 KB limit. The 11-22 meadow request took 8.4 s and came out at 104 KB, which the board refused, so Main had to halve it by hand. A free-text request nobody had planned for, "rides a dinosaur", took 7.9 s: Claude drew the dinosaur itself in 44 lines. The API-equivalent cost is about $0.007 per clip ($0.36 for all 48), billed to the subscription.

**Status:** built, tested in simulation and against the firmware's mock board (8 of 8 checks), committed and pushed. **It has not run on the real column yet:** the column was off all session while its battery charged. The first real run is item 1 in section 7.

## 1. How to run it (Main's one-liners)

| What | Command (from the repo root) |
|---|---|
| **Start** (gallery + live generation, in its own Windows Terminal tab) | `py software/pipeline/infinite_biscuit.py start` |
| **Stop** (the column goes back to what it showed before) | `py software/pipeline/infinite_biscuit.py stop` |
| Skip to the next clip | `py software/pipeline/infinite_biscuit.py next` |
| A new sentence from Brian, played as soon as it is ready | `py software/pipeline/infinite_biscuit.py add "rides a dinosaur" --now` |
| What is playing / timing stats | `py software/pipeline/infinite_biscuit.py status` · `... stats` (`--md` for a table) |
| Only the curated 21 (+ clips made live) | `... start --featured` |
| Rehearse without the column | `... start --sim` |

Notes for filming:

- The terminal tab prints each step live, for example `thinking  Biscuit rides a dinosaur ...` then `ready  #48 ... in 7.9 s (Claude 6.9 s, 44 lines; render + fit 0.8 s; 60 frames, 54.1 KB)` then `now  #48 Biscuit rides a dinosaur`. Enlarge the font and that tab works as the split-screen "AI at work" shot.
- Each clip is 2 laps, which is 16 s at 225 rpm. The runner reads the rpm from `/api/status` and times the switch to the board's real frame ticks, so the laps stay whole even when the rpm drifts. `--laps 3` makes each clip longer.
- Live generation makes up to 25 new clips per run (`--max-new`), so a forgotten gallery can't run up usage. `add` requests are always served.

## 2. How it works

*[Figure omitted from the public release: The featured playlist, each clip as Biscuit passes the viewer (t = 0.4, 0.5, 0.6)]*

*The featured playlist: each clip at three moments as Biscuit passes the viewer (flat 96 x 42 grid, cropped).*

1. **Sentence table** (`infinite_biscuit_sentences.csv`, 46 rows). Each row has an action ("flies a kite"), a staging hint ("the kite flies high behind him on a string from his mouth"), a sky (day, sunset, night, rain, snow) and the kit parts it uses. 36 rows can be built from kit parts. 10 are marked `draw:`: there Claude draws the object itself (rocket, pizza, pogo stick, unicycle, sled, birthday cake...). You can edit the file in Excel.
2. **Shared kit** (`biscuit_kit.py`, built on scenekit). `meadow()` is the 11-22 scene: sun, clouds, hills, 24 swaying blades, 12 bobbing flowers, butterflies. It also has sky variants, a rainbow, and grass that gets mown behind the lawnmower. `biscuit()` is the one Biscuit drawing every clip uses: walk, prance, run, stand, sit, 8 hats, sunglasses. It returns **anchor points** (mouth, eyes, head top, back, tail, chest, feet). There are 5 rides (skateboard, scooter, bike, car, hot-air balloon) and about 20 props.
3. **Claude writes the scene** (`prompts/infinite_biscuit.md`): Sonnet at low effort through the pipeline's `call_claude`, with one pre-spawned "warm" process so the CLI's start-up time is skipped. The prompt sets the rules: draw the meadow first, then Biscuit only through `biscuit()`, one lap per loop, the big moment at t = 0.5, props on his anchors, original things only.
4. **Sandbox render and repair** (`pov_request.codegen`): the same import allow-list, isolated interpreter, timeout and one repair round as the F9 pipeline.
5. **Fit to 64 KB:** the script is a function of t, so it is re-rendered at the largest frame count that fits: 80, 60, 48 or 40 frames per 8 s lap. Those are 10, 7.5, 6 and 5 fps, each a whole number of refresh ticks at 225 rpm. 42 clips landed at 60 frames, 5 at 48 and 1 at 80. pov-pipeline-live's new `fit_size` (keep every other frame) is the last resort; none of the 48 needed it.
6. **Checks:** the validator (current per rotor angle, palette, flicker), the auto-fixes that need no model (palette merge, brightness when the current is over the cap), and a check that Biscuit is visible in every frame (at least 40 white fur pixels). Peak current was 2.56 A at most, against the 2.6 A cap.
7. **Play:** upload the next clip while the current one plays, `POST /api/play` at the switch, and keep at most 3 of our clips on the column (LittleFS is 960 KB and shared).

**The trick that makes the transitions invisible:** every clip starts with Biscuit directly *behind* the column (column 0; you face column 48), and he passes the viewer at t = 0.5. The switch to the next clip, and anything that has to reset (a cupcake eaten, a ball caught, the mown grass growing back, a loop seam), all happen while he is out of sight. He simply "comes back round" doing something new, which is what you described in the brain dump.

**Column etiquette (shared rig):** the runner only uploads, plays and deletes its own clips (names `ibNN_...`). It never touches anyone else's animations, and it never reboots or flashes the board. If someone else plays something, or stops the column, while it runs, it pauses instead of fighting over the column. Running `start` again takes it back. `stop` restores whatever was playing before the gallery started and removes our clips.

## 3. The library

46 table sentences plus 2 made live during the tests ("flies like a superhero, wearing a party hat", "rides a dinosaur"). I checked every clip on a review sheet, and the tricky ones over a whole lap with the camera following Biscuit. The actions read as intended: the cupcake loses bites as he goes, the frisbee is caught in front of the viewer and then carried, the rainbow trail grows behind him, the skateboard ollies at the front.

**Featured order** (`playlist.json`, the first 21): struts in sunglasses (sunset) · rides a skateboard · rides a hot-air balloon · mows the lawn · plays guitar (sunset) · drives a little red car · flies a kite · watches the fireworks (night) · flies like a superhero · walks in the rain · walks the cat · holds a bunch of balloons · walks under a rainbow · rides a bike · rides a rocket (night) · goes to a party · races the goose · plays the trumpet · paints a rainbow trail · is the king of the meadow · rides a dinosaur (made live). Then: chases a butterfly, eats a cupcake, catches snowflakes, plays the drum and the rest. All six of your brain-dump examples are in the first 23. Change the order with `infinite_biscuit.py playlist 14 2 10 ...`.

**Taken out of the playlist** (`drop`): #20 fetches a stick (a brown stick vanishes against the dark sky), #33 sniffs the flowers and #45 blows dandelion seeds (both too subtle at 42 rows). `undrop` puts any of them back.

## 4. Timing log

Every generation, including failures, is a line in `%LOCALAPPDATA%\POVColumn\home\infinite_biscuit\gen_log.jsonl`. It records the Claude seconds, output tokens, render and fit seconds, frames, bytes, peak current and the warm or cold process. `infinite_biscuit.py stats --md` prints the per-clip table.

| Measure (48 clips, 2026-11-23) | Median | Range |
|---|---|---|
| Sentence to playable file | 4.7 s | 2.7-14.2 s (90 % ≤ 6.5 s) |
| Claude writing the script | 4.0 s | 2.0-12.7 s |
| Script length | 20 lines | 11-44 |
| Output tokens | 406 | |
| File size | 54.3 KB | 46.5-60.1 KB |
| Frames per 8 s lap | 60 | 48-80 |

For comparison: the 11-07 benchmark's original pipeline took 70 s per animation (Opus writing ~150 lines). The 11-22 meadow request took 8.4 s and produced a file the board refused. The slowest Infinite Biscuit clip was "paints a rainbow trail" at 14.2 s; Claude thought for longer on that one. **Not yet measured:** uploading to the real column and the start of playback. The mock board models that as about 1.5-2 s for a 55 KB file, so sentence to playing should be about 6-7 s. The first real run will give the actual figure.

## 5. Decisions and why

- **pov_request as a library, no edits to it.** pov-pipeline-live owns that file today. I call its `call_claude`, `codegen`, `render_script`, `auto_fix`, `upload_and_play` and `WarmPool`, and add `biscuit_kit` to its import allow-list at runtime. pov-pipeline-live agreed to add `biscuit_kit` to the list upstream and to keep those functions backward-compatible.
- **Re-render at fewer frames rather than decimate.** Main's 11-22 fix (every other frame at half the rate) always halves the smoothness. Re-rendering the script picks the smoothest frame count that fits, and every count on the ladder plays at exact tick multiples.
- **One lap per loop, starting behind the column.** This hides every seam and every switch, so a 2-lap clip is just the same loop played twice.
- **Content scope:** the clips are safe for the public channel by construction: your own dog, generic objects, an IP check on `add` sentences, and "no logos or real people" in the prompt. The meta says so. They are still filed in home, because publishing is your decision.
- **At most 3 clips on the column** (current, next, one spare). The 0.9 MB file system is shared with other agents' animations, and 48 clips at about 55 KB would not fit anyway.
- **Live cap of 25 new clips per run** keeps usage bounded. At $0.007 per clip that is about $0.18 per run, API-equivalent.

## 6. How to explain it

- **"It isn't drawing pictures, it's writing programs, from a kit."** Claude composes about 20 lines out of tested parts: the meadow, Biscuit, a kite. That is why it is fast (4 s) and why Biscuit looks identical in every clip. When the kit doesn't have something (a dinosaur, a rocket, a pizza), Claude draws it with the same primitives, and you can show that on camera.
- **Anchors are the AI-engineering detail.** `biscuit()` returns where his mouth, back and head are in every frame, so a kite string or a hat stays attached while he moves round the drum. The LLM never has to work out geometry; it writes `kite(sc, cv, a["mouth"], t)`.
- **Hide the seam behind the column.** Loop seams, resets and clip switches happen where nobody can see them. It is a stagecraft fix, not a code fix.
- **Fit to the hardware's memory.** The ESP32 keeps the whole animation in 64 KB of RAM. The runner picks the frame count from 10, 7.5, 6 or 5 fps, the frame rates that divide evenly into the column's refresh ticks.
- **Line for the video:** "Every two laps, the AI invents something new for Biscuit to do, and it takes about five seconds."

## 7. Open items for Brian

1. **First run on the real column** (it was off all session): `py software/pipeline/infinite_biscuit.py start` at the bench. Check that the first switch happens while Biscuit is behind the column, and watch one clip with a prop (the kite or the car) at 225 rpm. If the switch shows, tell Main the offset and I'll add a lead time. Main will see "taking over the column from ..." if another agent's animation was on.
2. **Public or not:** which clips, if any, go into `software/content/public` for the video? They are in `%LOCALAPPDATA%\POVColumn\home\infinite_biscuit\clips\`, each with its `.py`, `.json` and a contact-strip `.png`.
3. **Featured order:** keep mine, or pick your own (`playlist ...`)?
4. **On camera, live or cached?** For the gallery shot, start it with live generation (new clips appear in the terminal tab) or `--no-live` (only the curated library)? I'd go live, with `add "<your sentence>" --now` for the moment you say a new one.

## Files

| File | What |
|---|---|
| `software/povgen/biscuit_kit.py` | Biscuit + meadow + rides + props + anchors (shared by every clip) |
| `software/pipeline/infinite_biscuit.py` | runner: generate, fit, file, play, live queue, start / stop / next / add / status / stats / review / playlist |
| `software/pipeline/infinite_biscuit_sentences.csv` | 46 sentences (edit in Excel; `enabled` 0 hides a row) |
| `software/pipeline/prompts/infinite_biscuit.md` | the generator prompt (kit API + rules + one worked example) |
| `software/tests/infinite_biscuit_mock_test.py` | integration test against the firmware mock (8 / 8) |
| `%LOCALAPPDATA%\POVColumn\home\infinite_biscuit\` | `clips\` (48 clips: .pova / .py / .json / .png), `library.json`, `playlist.json`, `gen_log.jsonl`, `runner_state.json`, `review.png` |
