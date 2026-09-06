# TASK_phase2_dialog_video_v3.md — hybrid_chain: professional dialog + new timeline (keep subtitle band)

## Context

The user reviewed the narrated video and wants a **more professional dialog style**:
- Remove filler reactions ("Right!", "Exactly!", "Now I see the whole trick!") — they are gone.
- Focus on: **motivation for the problem, definitions, analysis, insight**, and questions that provoke thought.
- Keep the subtitle band layout from v2 (fixed black band y ∈ [-4.0, -2.8], HOST A yellow / HOST B blue chips, WHITE text inside the band, all math visuals above -2.8). Do NOT change the layout code — only the dialog text, the subtitle timing, and the `wait` values.

New dialog audio has been generated (`/tmp/dlg2/line0..4.mp3`, concatenated with 0.35 s silence into `/tmp/dlg2/full.mp3`). Turn start times (absolute) and durations:

| turn | speaker | start (s) | dur (s) | text |
|---|---|---|---|---|
| 0 | A | 0.00 | 16.39 | We know no efficient test can distinguish a single sample of X from a single sample of Y. Why should the same hold for k samples? The joint distribution has more structure — a distinguisher could exploit correlations across positions, and the direct argument fails. |
| 1 | B | 16.74 | 15.77 | The hybrid method interpolates. Define H_i: the first i samples come from X, the remaining k minus i from Y. Then H_0 is all Y, H_k is all X, and adjacent hybrids differ in exactly one component. |
| 2 | A | 32.86 | 19.15 | Why are adjacent hybrids indistinguishable? If some test separated H_{i-1} from H_i, we could build a single-sample distinguisher: challenge on the i-th position, fill the rest by sampling, run the test. So single-sample indistinguishability forces every step to be small. |
| 3 | B | 52.36 | 15.29 | The triangle inequality assembles the bound: total advantage is at most the sum over adjacent pairs. Each step at most epsilon over k, k steps at most epsilon. The distinguisher may change per step — the sum only needs each bound individually. |
| 4 | B | 68.00 | 16.34 | The insight is composability: polynomially many negligible steps stay negligible, losing only a polynomial factor per step. But ask — if the chain had exponentially many steps, would this still work? That edge is where the hybrid technique ends and new ideas begin. |

Dialog ends at 84.34 s; add a final 0.5 s hold → scene ends ≈ 84.84 s.

## Scene phase mapping (dialog turn → existing visuals, same order as v2)

- **Turn 0 (0.00–16.74)** — "the problem": `Write(title)` + `FadeIn(caption)` early, then pad with `self.wait` so sub 0 (shown during the whole turn) has time; sub 0 fades in at t≈0.8, fades out at 16.74.
- **Turn 1 (16.74–32.86)** — "the interpolation": legend + column H_0 + labels + flips i=1,2 (relaxed pace). Sub 1 fades in at 16.74, out at 32.86.
- **Turn 2 (32.86–52.36)** — "why adjacent hybrids are indistinguishable": flips i=3,4. Sub 2 in at 32.86, out at 52.36.
- **Turn 3 (52.36–68.00)** — "the bound": flip i=5 (with ε/k bar + cumulative segment) + red cap line + ε label. Sub 3 in at 52.36, out at 68.00.
- **Turn 4 (68.00–84.34)** — "the insight": `Write(payoff)` + takeaway. Sub 4 in at 68.00; fade out 84.34 → 84.64; final hold to ≈84.84.

Implementation guidance: keep the existing visual code (positions from v2 — do not touch the band or the moved visuals), replace the `dialog` list with the new 5 lines above (verbatim, with manual `\n` word-boundary wraps ≤ ~66 chars for the body text), and recompute the `wait` values so each subtitle fades in at the exact start times above. Keep chip colors/font sizes from v2 (chip 16 pt, body 24 pt, band center y=-3.4).

## Constraints

- Modify ONLY `demo/hybrid_chain.py`. Do NOT touch other files. Do NOT reword the dialog lines (timings are fixed to the generated audio). Do NOT run manim. Do NOT git commit. English only.
- The subtitle band and all v2 visual positions must remain unchanged.
- Total runtime ≈ 84.8 s (may slightly exceed the 90 s guideline; that is accepted for this prototype — note it in the report).

## Verification (human will run)

1. `cd ~/Documents/mathflow && .venv/bin/python -m py_compile demo/hybrid_chain.py`
2. Human renders with `PATH="$PWD/demo/bin:$PATH" .venv/bin/manim -qm demo/hybrid_chain.py HybridChain`, then muxes `/tmp/dlg2/full.mp3` (ffmpeg, video+audio, no -shortest), then extracts frames at t ≈ 4, 24, 42, 60, 76 s to confirm subtitles appear in the band at the right turns and nothing overlaps.
3. Expected final duration ≈ 84.8 s.

Report: the new per-phase `wait` values, confirmation that subtitle start times match the table, and confirmation the band/visual layout is untouched.
