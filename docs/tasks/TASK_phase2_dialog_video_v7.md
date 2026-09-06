# TASK_phase2_dialog_video_v7.md — hybrid_chain: clean subtitle glyphs + reduce side margins

## Context

User feedback on the current hybrid_chain video subtitles:
1. **Uneven letter spacing** — the subtitle text contains raw LaTeX tokens (`H_{i-1}`, `H_i`, `H_0`, `H_k`) that render as literal braces/underscores via font fallback, causing visibly uneven gaps.
2. **Too much whitespace on both sides** — subtitle text width ≈ 7.98 units vs band width 14.222; ~3.1 units of empty space per side.

Verified fixes (measured with manim Text on this machine):
- Replacing LaTeX tokens with Unicode subscripts renders cleanly: `H_{i-1}` → `Hᵢ₋₁` (H + U+1D62 + U+208B + U+2081), `H_i` → `Hᵢ` (U+1D62), `H_0` → `H₀` (U+2080), `H_k` → `Hₖ` (U+2096). All render with the default font, no fallback.
- `font_size=22` + wrap width 90 → max text width 11.65, max height 0.94 (band height 1.2 → fits), side margins ≈ 1.29 each.

## Task

Modify ONLY `/Users/zd/Documents/mathflow/demo/hybrid_chain.py`:

1. Add a small helper near `_wrap` (e.g. `_clean_math`) that replaces, in order:
   - `H_{i-1}` → `Hᵢ₋₁`
   - `H_i` → `Hᵢ`
   - `H_0` → `H₀`
   - `H_k` → `Hₖ`
   (Use the exact Unicode chars: H + \u1d62 + \u208b + \u2081 for i−1; H + \u1d62 for i; H + \u2080 for 0; H + \u2096 for k. Plain str.replace in that order is fine.)
2. In the subtitle body creation, apply the cleaner to the display text:
   `body = Text(_wrap(_clean_math(line), 90), font_size=22, color=WHITE, line_spacing=0.15)`
   (was `_wrap(line, 72), font_size=20`).
3. Do NOT change: dialog text content, timings, `wait` values, band geometry, subtitle centering, any visuals.
4. Do NOT run manim. Do NOT git commit. English only.

Note: the audio was already generated from the original text; do not touch audio files or the dialog list wording (only the display transform above).

## Verification (human will run)

1. `cd ~/Documents/mathflow && .venv/bin/python -m py_compile demo/hybrid_chain.py`
2. Render + mux /tmp/dlg3/full.mp3, extract frames at t ≈ 4, 24, 44, 62, 80 s:
   - no literal `{`, `}`, `_` visible in subtitles (they should show Hᵢ/H₀/Hₖ/Hᵢ₋₁)
   - text still fully inside band (no white pixels above band top line)
   - text visibly wider than before (side margins smaller)

Report: exact changes, confirm nothing else touched.
