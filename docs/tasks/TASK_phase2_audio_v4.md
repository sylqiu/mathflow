# TASK_phase2_audio_v4.md — tune voices: tone down female energy, speed up male

## Context

User feedback on the latest hybrid_chain audio:
1. **Female voice (Host A) is now too energetic** — tone it back to a middle ground: warm/friendly but still natural and conversational (not the flat calm one, not the hyper upbeat one).
2. **Male voice (Host B) is good but should speak a bit faster** — add per-speaker speed control. `generate_audio` (mlx_audio, verified) accepts a `speed` kwarg (default 1.0).

## Task A — `scripts/qwen3_tts.py`: per-speaker speed

Add two optional CLI flags:
- `--speed-a` (default 1.0) — speed multiplier for host A lines
- `--speed-b` (default 1.08) — speed multiplier for host B lines

Wire them into `generate_lines(...)`: pass `speed=speed_a if speaker == "A" else speed_b` to the `generate_audio(...)` call. Update the argparse help + module docstring. Keep everything else identical (defaults chosen so existing behavior only changes when flags are passed... but note: per user request we WANT B faster, so default `--speed-b 1.08` is fine; A stays 1.0).

## Task B — `scripts/generate_podcast.py`: tone down female voice

Change `HOST_A_INSTRUCT` to a middle-ground description:
`"A warm, friendly female voice, natural conversational podcast host, clear and expressive, medium pitch"`

Keep `HOST_B_INSTRUCT` unchanged. Also pass `--speed-a 1.0 --speed-b 1.08` in the qwen3_tts.py invocation inside `generate_lesson(...)` (add the flags explicitly so the pipeline matches the user's request).

## Constraints

- Modify ONLY `scripts/qwen3_tts.py` and `scripts/generate_podcast.py`. Do NOT run manim or the TTS pipeline. Do NOT git commit. English only.

## Verification (human will run)

1. `cd ~/Documents/mathflow && .venv/bin/python -m py_compile scripts/qwen3_tts.py scripts/generate_podcast.py`
2. Regenerate the 5 hybrid_chain lines with the new instruct-a + speed-b 1.08; re-measure durations; retime waits; render; mux; extract frames → same visual checks as before.

Report: exact changes in both files.
