# TASK_phase2_audio_v2.md — switch podcast TTS from edge-tts to local Qwen3-TTS (MLX)

## Context

ZD approved switching TTS from edge-tts (robotic) to locally-run Qwen3-TTS (natural, voice-designable). The environment is already set up and verified:

- Python 3.14 venv: `/Users/zd/Documents/mathflow/.venv-tts`
- mlx-audio 0.5.0 installed there (supports `qwen3_tts` model type)
- Model: `mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-8bit` (cached, ~2 GB)
- Verified CLI (works):
  `.venv-tts/bin/python -m mlx_audio.tts.generate --model mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-8bit --instruct "<voice description>" --text "<text>" --file_prefix /tmp/out --audio_format wav`
  → writes `/tmp/out_000.wav`
- Verified voice descriptions:
  - Host A (female, curious): `A calm, warm female voice, natural conversational podcast host, clear and expressive, medium pitch`
  - Host B (male, expert): `A friendly male voice, natural conversational podcast host, warm and engaging, medium-low pitch`
- Note: the CLI loads the model once per process (~10-20 s). For a whole podcast (30-60 lines), generate ALL lines in ONE python process using the mlx_audio Python API (`from mlx_audio.tts.utils import load_model` / `from mlx_audio.tts.generate import generate_audio`) so the model is loaded once. Do NOT shell out to the CLI per line.

## Deliverable A — `scripts/qwen3_tts.py` (new file)

A batch TTS driver that speaks many lines in one model load:

```
usage: qwen3_tts.py --lines <lines.json> --out-dir <dir> [--model <repo>] [--instruct-a "<desc>"] [--instruct-b "<desc>"] [--sample-rate 24000]
```

- `lines.json`: `[{"speaker": "A"|"B", "text": "..."}, ...]`
- Loads the model ONCE, then generates each line's audio, writing `<out_dir>/line<i>_<speaker>.wav` (i starting at 0). Use `generate_audio(model=model, text=..., instruct=<desc per speaker>, file_prefix=<out_dir>/line<i>_<speaker>, audio_format="wav")` (inspect the installed mlx_audio API in `.venv-tts` for exact signatures; the CLI wrapper already calls `generate_audio` — reuse that call pattern, passing `instruct`).
- Default model = `mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-8bit`.
- Print one log line per line generated (speaker, words, output path). Exit non-zero on failure.
- English only. stdlib + mlx_audio.

## Deliverable B — switch `scripts/generate_podcast.py` to Qwen3-TTS

Modify ONLY `scripts/generate_podcast.py` (keep CLI interface `--course/--lesson/--force` identical):

1. Replace the per-line `tts_line` (edge-tts subprocess) with a call to `qwen3_tts.py` that generates ALL lines of the lesson in one invocation:
   - Write the parsed `lines` to a temp `lines.json`
   - `run([QWEN_PYTHON, str(ROOT/"scripts/qwen3_tts.py"), "--lines", json_path, "--out-dir", workdir, "--instruct-a", HOST_A_INSTRUCT, "--instruct-b", HOST_B_INSTRUCT])`
   - QWEN_PYTHON = `os.environ.get("MF_PODCAST_QWEN_PYTHON", str(ROOT/".venv-tts"/"bin"/"python"))`
2. The wavs land as `line0_A.wav`, `line1_B.wav`, ... — convert each to mp3 (`ffmpeg -i x.wav -c:a libmp3lame -b:a 128k x.mp3`) for the existing concat step, or adapt `concat_audio` to accept wav inputs directly (wav input to ffmpeg concat works fine; output stays 128k mp3). Prefer the simpler path: feed wavs to the concat list directly.
3. Add module constants:
   - `HOST_A_INSTRUCT = "A calm, warm female voice, natural conversational podcast host, clear and expressive, medium pitch"`
   - `HOST_B_INSTRUCT = "A friendly male voice, natural conversational podcast host, warm and engaging, medium-low pitch"`
4. Remove the edge-tts constants/imports (`EDGE_TTS`, `HOST_A_VOICE`, `HOST_B_VOICE`, `SPEECH_RATE`). Keep `FFMPEG`, `FFPROBE`, `SILENCE_SECONDS`, `BITRATE`, DeepSeek script generation, and all parsing logic unchanged.
5. Update the module docstring (usage + requirements: `.venv-tts`, model cached, ffmpeg).

## Constraints

- Do NOT modify any other files. Do NOT run the pipeline end-to-end (it takes many minutes; the human will run it). You MAY smoke-test `qwen3_tts.py` with a 2-line fixture in /tmp to prove the API call works (model is cached; one load ≈ 10-20 s). Do NOT git commit. English only.
- `generate_podcast.py` runs under Python 3.9 (`/Users/zd/Documents/mathflow/.venv`); `qwen3_tts.py` runs under Python 3.14 (`.venv-tts`). They communicate only via CLI args + files.

## Verification (human will run)

1. `cd ~/Documents/mathflow && .venv/bin/python -m py_compile scripts/generate_podcast.py && .venv-tts/bin/python -m py_compile scripts/qwen3_tts.py`
2. Smoke test: create `/tmp/tts_smoke/lines.json` with 2 short lines (one A, one B), run `scripts/qwen3_tts.py`, confirm two wavs exist and are non-empty.
3. Full run: `.venv/bin/python scripts/generate_podcast.py --lesson m2-ci-definition --force` → success, output ≈ 5-8 min mp3, model loaded once (log shows one load, then per-line logs).

Report: exact changes, smoke-test output, any API signature notes discovered in the installed mlx_audio version.
