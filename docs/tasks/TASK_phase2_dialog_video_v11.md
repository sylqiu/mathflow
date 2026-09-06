# TASK_phase2_dialog_video_v11.md — hybrid_chain: retime waits to tuned voices (female toned down, male speed 1.08)

## Context

hybrid_chain dialog audio regenerated with tuned voices → new durations:

| turn | speaker | audio dur (s) |
|---|---|---|
| 0 | A | 17.20 |
| 1 | B | 16.48 |
| 2 | A | 17.68 |
| 3 | B | 19.68 |
| 4 | B | 21.20 |

Full audio /tmp/dlg5/full.mp3 = 93.64 s (0.35 s silence gaps). NEW absolute turn boundaries:

- turn 0: 0.00 → 17.55 (line0 ends 17.20, +0.35 silence → line1 at 17.55)
- turn 1: 17.55 → 34.38 (line1 ends 34.03, +0.35 → 34.38)
- turn 2: 34.38 → 52.41 (line2 ends 52.06, +0.35 → 52.41)
- turn 3: 52.41 → 72.44 (line3 ends 72.09, +0.35 → 72.44)
- turn 4: 72.44 → 93.64 (line4 ends 93.64; dialog end)
- sub4 out: 93.64 → 93.94; final hold → 94.14

## Task

Modify ONLY `/Users/zd/Documents/mathflow/demo/hybrid_chain.py`. Keep every animation run_time and flip() identical; ONLY change the five `self.wait(...)` values (+ inline comments) so each turn ends at the new boundary:

1. Turn 0: animations end at 2.65 → wait to 17.55 → `self.wait(14.55)` (was 14.26). Comment `# 2.65 -> 17.55 (turn 0 end)`
2. Turn 1: anchor 24.50 (17.55 + 0.35+0.6+1.0+2.5+2.5) → wait to 34.38 → `self.wait(9.88)` (was 9.00). Comment `# 24.50 -> 34.38 (turn 1 end)`
3. Turn 2: anchor 37.23 (34.38 + 0.35 + 2.5) → wait to 52.41 → `self.wait(15.18)` (was 13.50). Comment `# 37.23 -> 52.41 (turn 2 end)`
4. Turn 3: anchor 58.56 (52.41 + 0.35 + 2.5 + 2.5 + 0.8) → wait to 72.44 → `self.wait(13.88)` (was 13.40). Comment `# 58.56 -> 72.44 (turn 3 end)`
5. Turn 4: anchor 76.09 (72.44 + 0.35 + 2.0 + 0.5 + 0.8) → wait to 93.64 → `self.wait(17.55)` (was 17.07). Comment `# 76.09 -> 93.64 (dialog end)`

Update section header comments to new boundaries: turn 1 (17.55 - 34.38), turn 2 (34.38 - 52.41), turn 3 (52.41 - 72.44), turn 4 (72.44 - 93.64); fade comments: turn1 `# 17.55 -> 17.90`, turn2 `# 34.38 -> 34.73`, turn3 `# 52.41 -> 52.76`, turn4 `# 72.44 -> 72.79`; sub4 out `# 93.64 -> 93.94`; final hold `# 93.94 -> 94.14`.

Do NOT change: dialog text, font/band code, run_times, flip internals. Do NOT run manim. Do NOT git commit. English only.

## Verification (human will run)

1. `cd ~/Documents/mathflow && .venv/bin/python -m py_compile demo/hybrid_chain.py`
2. Render + mux /tmp/dlg5/full.mp3 → duration ≈ 94.1 s.
3. Frames at t ≈ 4, 26, 43, 62, 82 → subtitle i matches turn i, ≤3 lines, no overflow.

Report: exact wait values changed.
