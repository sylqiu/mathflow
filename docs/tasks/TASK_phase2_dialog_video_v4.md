# TASK_phase2_dialog_video_v4.md — hybrid_chain: fix subtitle overflow (text exceeds subtitle band / screen)

## Context

The rendered video has a fixed subtitle band (y ∈ [-4.0, -2.8], height 1.2) at the bottom. The user reports that **long subtitles overflow the band** — text is taller than the band (top pokes above the band line, bottom goes off-screen).

Root cause: subtitle body uses `font_size=24` with `_wrap(line)` at the default width of 66 chars. Measured with manim `Text`: the longest dialog turn wraps to a height of ~1.38–1.45, exceeding the 1.2 band height.

Measured fix (verified with manim Text metrics): `font_size=20` + wrap width 72 chars → max height 0.97, max width 7.98 (band is 14.222 wide). Text centered at y=-3.4 spans ≈ [-3.885, -2.915], fully inside the band.

## Task

Modify ONLY `/Users/zd/Documents/mathflow/demo/hybrid_chain.py`:

1. In the subtitle body creation (`body = Text(_wrap(line), font_size=24, ...)`), change `font_size=24` → `font_size=20`. Keep `color=WHITE`, `line_spacing=0.15`.
2. Call `_wrap(line, 72)` (or change the `_wrap` default `width=66` → `width=72`; prefer passing 72 explicitly at the call site so the helper stays reusable).
3. Do NOT change: dialog text, timings, `wait` values, chip (HOST A/B) style, band geometry, any visual positions, or the other `font_size=24` usages (legend X/Y labels, epsilon label — those are on-screen labels, leave them).
4. Do NOT run manim. Do NOT git commit. English only.

## Verification (human will run)

1. `cd ~/Documents/mathflow && .venv/bin/python -m py_compile demo/hybrid_chain.py`
2. Render: `PATH="$PWD/demo/bin:$PATH" .venv/bin/manim -qm demo/hybrid_chain.py HybridChain`
3. Mux `/tmp/dlg2/full.mp3` with ffmpeg (video+audio, no -shortest).
4. Extract frames at t ≈ 4, 24, 42, 60, 76 s → confirm every subtitle line fits inside the band (nothing above the band top line, nothing below screen bottom).

Report: confirm the exact lines changed, and that nothing else was touched.
