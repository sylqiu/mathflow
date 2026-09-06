# TASK_phase2_dialog_video_v6.md — hybrid_chain: retime subtitles to new Qwen3-TTS audio

## Context

The hybrid_chain dialog audio was regenerated with local Qwen3-TTS (natural voices; Host A female, Host B male). New per-turn audio durations (from /tmp/dlg3/line*_*.wav):

| turn | speaker | new audio dur (s) |
|---|---|---|
| 0 | A | 18.16 |
| 1 | B | 19.68 |
| 2 | A | 18.80 |
| 3 | B | 16.64 |
| 4 | B | 18.08 |

The full audio (/tmp/dlg3/full.mp3) concatenates lines with 0.35 s silence gaps (exactly like the old /tmp/dlg2/full.mp3 recipe). Therefore the NEW absolute turn boundaries are:

- turn 0: 0.00 → 18.51 (line0 ends 18.16, +0.35 s silence → line1 starts 18.51)
- turn 1: 18.51 → 38.54 (line1 ends 38.19, +0.35 → 38.54)
- turn 2: 38.54 → 57.69 (line2 ends 57.34, +0.35 → 57.69)
- turn 3: 57.69 → 74.68 (line3 ends 74.33, +0.35 → 74.68)
- turn 4: 74.68 → 92.76 (line4 ends 92.76; dialog end)
- fade sub4 out: 92.76 → 93.06; final hold → 93.26

Subtitle i is visible from its fade-in (turn start) until the next turn start; sub4 fades out at 92.76.

## Task

Modify ONLY `/Users/zd/Documents/mathflow/demo/hybrid_chain.py`. Keep every animation `run_time` and every `flip()` the same; ONLY change the five `self.wait(...)` values (and their inline `# ... -> ...` comments) so each turn ends at the new boundary. The visual animation phases stay anchored at the turn starts, exactly as before.

Compute the waits from the anchor points (animation sequence before each wait is unchanged):

1. Turn 0: animations end at 2.65 → wait until 18.51 → `self.wait(15.86)` (was 14.09).
   Comment: `# 2.65 -> 18.51 (turn 0 end)`
2. Turn 1: after FadeOut/FadeIn(0.35)+legend(0.6)+columns0(1.0)+flip(1)+flip(2) the anchor is 25.46 → wait until 38.54 → `self.wait(13.08)` (was 9.17).
   Comment: `# 25.46 -> 38.54 (turn 1 end)`
3. Turn 2: after FadeOut/FadeIn(0.35)+flip(3) anchor is 41.39 → wait until 57.69 → `self.wait(16.30)` (was 16.65).
   Comment: `# 41.39 -> 57.69 (turn 2 end)`
4. Turn 3: after FadeOut/FadeIn(0.35)+flip(4)+flip(5)+cap(0.8) anchor is 63.84 → wait until 74.68 → `self.wait(10.84)` (was 9.49).
   Comment: `# 63.84 -> 74.68 (turn 3 end)`
5. Turn 4: after FadeOut/FadeIn(0.35)+Write(payoff)(2.0)+wait(0.5)+FadeIn(takeaway)(0.8) anchor is 78.33 → wait until 92.76 → `self.wait(14.43)` (was 12.69).
   Comment: `# 78.33 -> 92.76 (dialog end)`

Also update the section comments (`# turn 1 (16.74 - 32.86 s): ...` style headers) to the new boundaries (18.51-38.54, 38.54-57.69, 57.69-74.68, 74.68-92.76) and the trailing inline comments on the FadeIn/FadeOut lines to the new absolute times (they shift by the turn start deltas):
- turn 1 fade: `# 18.51 -> 18.86`
- turn 2 fade: `# 38.54 -> 38.89`
- turn 3 fade: `# 57.69 -> 58.04`
- turn 4 fade: `# 74.68 -> 75.03`
- sub4 out: `# 92.76 -> 93.06`
- final hold: `# 93.06 -> 93.26`

Do NOT change: dialog text, subtitle font/band code, any run_time, any flip internals, band geometry. Do NOT run manim. Do NOT git commit. English only.

## Verification (human will run)

1. `cd ~/Documents/mathflow && .venv/bin/python -m py_compile demo/hybrid_chain.py`
2. Render + mux /tmp/dlg3/full.mp3 (no -shortest), expected duration ≈ 93.3 s.
3. Extract frames at t ≈ 4, 24, 44, 62, 80 s → subtitle i matches turn i, text inside band, no overflow.

Report: exact wait values changed, confirmation that nothing else was touched.
