# Live captions on the POV column

Brian talks to the camera; the column spinning behind him shows what he says as he says it. Two modes:
**`word`**, one word at a time in the camera window, and **`tick`**, a marquee crawling round the drum.
Report: [`docs/2026-11-02-live-captions.md`](../../docs/2026-11-02-live-captions.md).

```powershell
py software/captions/live.py --mode word                          # mic -> preview window (no hardware needed)
py software/captions/live.py --mode tick
py software/captions/live.py --mode both                          # both modes side by side
py software/captions/live.py --mode word --to ws://pov.local/ws   # + the real column (caption messages)
py software/captions/live.py --mode word --to frames:ws://pov.local/ws   # fallback: PC-rendered frames
py software/captions/render_clip.py take2 --stills docs/img       # test clip -> MP4 with audio + latency overlay
py software/captions/bench/bench_asr.py --all                     # re-run the engine benchmark
py -m pytest software/tests -q
```
Options for `live.py`: `--engine` (see below), `--device "<part of the mic name>"`, `--partial` (show the unstable
word dimmer), `--file clip.wav` (replay a 16 kHz WAV in real time), `--no-preview`, `--seconds N`, `--token`.
Keys in the preview: `q`/Esc quits. Each run logs every word with its latency terms to
`%LOCALAPPDATA%\POVColumn\captions\logs\live-*.jsonl`.

## Pieces

| File | What |
|---|---|
| `asr.py` | Streaming recognisers behind one interface: sherpa-onnx transducers (append-only; a word is stable when the next word starts or the decoder runs 0.25 s (FastConformer) to 0.35 s further with nothing new) and faster-whisper + LocalAgreement-2 |
| `engine.py` | PC driver: UPPERCASE, light punctuation, digits stay digits; word mode paces bursts (>= 0.15 s each), drops the oldest if > 1 s behind, clears after 2 s of silence; ticker appends at once |
| `column_model.py` | **Reference model of the ESP32 caption mode** (the firmware's `captions.h` is a port): auto font (7x9 if it fits 32 columns, else 5x7, else a mini-scroll of one character every 3 ticks), ticker `hybrid` (default: holds still, each word jumps fully in at the next tick, drifts away after 1.5 s of silence) or `crawl` (deadline speed controller: each word in within 1.0 s, drop the oldest waiting words if even 110 col/s cannot make 1.5 s), current limiter (2.0 A) |
| `font.py` | Hand-drawn uppercase 5x7 and bold 7x9 fonts; `--header` writes `firmware/src/captions_font.h` |
| `transport.py` | `CaptionWS` (JSON caption messages over the column's WebSocket, TCP_NODELAY, ack round trips), `FrameStreamWS` (fallback: 4,032-byte frames at 30 Hz over live mode), `LocalColumn`; 250 ms keep-alive (Wi-Fi power save) |
| `mock_column.py`, `probe_link.py` | A Python stand-in for the ESP32 on the same WebSocket protocol (acks after the tick) and a one-minute link probe (ping RTT, word -> ack) |
| `session.py` | One caption session on an explicit clock (shared by the live window and the MP4 renderer) with a latency record per word |
| `sim.py` | Fast camera-model renderer (povsim's projection as a sparse matrix, ~40 ms a view) and time-varying exposure (frames swap on 1/30 s ticks) |
| `live.py`, `render_clip.py` | The live app and the offline MP4 renderer |
| `audio.py` | Mic capture (device logic from Brain-Dump-Button `ptt/ptt.py`) and real-time WAV replay |
| `bench/` | `make_clips.py` (clips + large-v3 word-timed references), `bench_asr.py` (latency / WER / CPU), `results.json`, `latency.json` (metrics only) |

## Models (local, not in git)

Everything lives in `%LOCALAPPDATA%\POVColumn\captions\models` (sherpa-onnx models, ~0.7 GB in all) and the
Hugging Face cache (faster-whisper). To fetch the sherpa models:

```bash
M="$LOCALAPPDATA/POVColumn/captions/models"; mkdir -p "$M"; cd "$M"
B=https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models
for n in sherpa-onnx-nemo-streaming-fast-conformer-transducer-en-80ms-int8 \
         sherpa-onnx-streaming-zipformer-en-kroko-2025-08-06 \
         sherpa-onnx-nemotron-3.5-asr-streaming-0.6b-160ms-int8-2026-06-11; do
  curl -sL "$B/$n.tar.bz2" | tar xj; done
```
`py -m pip install sherpa-onnx faster-whisper sounddevice websockets opencv-python scipy psutil`.

Test audio and transcripts stay in `%LOCALAPPDATA%\POVColumn\captions\clips` (personal data, never committed).
