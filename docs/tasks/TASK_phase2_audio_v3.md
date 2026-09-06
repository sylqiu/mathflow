# TASK_phase2_audio_v3 + dialog_v8 — energetic female voice + subtitle line/row spacing

## Context

User feedback:
1. **Voices**: keep two voices. Questions (Host A) = female voice but **slightly more energetic** than the current calm one. Explanations (Host B) = **the current male voice, unchanged** ("A friendly male voice, natural conversational podcast host, warm and engaging, medium-low pitch").
2. **Subtitles**: still has spacing issues, especially **between rows** — text sometimes wraps to **4 lines**, which looks cramped in the 1.2-unit band. Reduce to at most 3 lines and increase `line_spacing` so rows breathe.

Measured (manim Text, fs=22): `wrap=96` + `line_spacing=0.25` → max width 12.40, max height 0.85, max 3 lines (band 14.222 x 1.2, margins ~0.91/side). Safe.

## Task A — voice descriptions (scripts)

Modify `/Users/zd/Documents/mathflow/scripts/generate_podcast.py`:

- `HOST_A_INSTRUCT` → new energetic female voice description:
  `"A bright, energetic young female voice, lively podcast co-host, expressive and upbeat, medium-high pitch"`
- `HOST_B_INSTRUCT` → unchanged: `"A friendly male voice, natural conversational podcast host, warm and engaging, medium-low pitch"`

Nothing else in that file. (The CLI `qwen3_tts.py` takes `--instruct-a/--instruct-b` so it needs no change; the human will pass the new descriptions directly when regenerating the hybrid_chain lines.)

## Task B — subtitle line/row spacing (demo)

Modify `/Users/zd/Documents/mathflow/demo/hybrid_chain.py`:

In the subtitle body creation, change:
- `_wrap(_clean_math(line), 90)` → `_wrap(_clean_math(line), 96)`
- `line_spacing=0.15` → `line_spacing=0.25`

Do NOT change: dialog text, timings, `wait` values, band geometry, centering, font_size (22), any visuals.

## Constraints

- Only those two files. Do NOT run manim. Do NOT run the TTS pipeline. Do NOT git commit. English only.

## Verification (human will run)

1. `cd ~/Documents/mathflow && .venv/bin/python -m py_compile scripts/generate_podcast.py demo/hybrid_chain.py`
2. Regenerate the 5 hybrid_chain lines with `scripts/qwen3_tts.py` passing the NEW --instruct-a and current --instruct-b; re-measure durations; retime waits; render; mux /tmp/dlg3/full.mp3; extract frames at t ≈ 4, 24, 44, 62, 80 → subtitles show at most 3 lines, rows visibly spaced, no overflow above band top.

Report: exact lines changed in both files.
