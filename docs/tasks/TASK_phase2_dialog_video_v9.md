# TASK_phase2_dialog_video_v9.md — hybrid_chain: retime waits to energetic-female-voice audio

## Context

hybrid_chain dialog audio regenerated with the NEW energetic female voice (Host A) + unchanged male voice (Host B) → new durations:

| turn | speaker | audio dur (s) |
|---|---|---|
| 0 | A | 16.56 |
| 1 | B | 15.60 |
| 2 | A | 16.00 |
| 3 | B | 19.20 |
| 4 | B | 20.72 |

Full audio /tmp/dlg4/full.mp3 = 89.48 s (0.35 s silence gaps). NEW absolute turn boundaries:

- turn 0: 0.00 → 16.91 (line0 ends 16.56, +0.35 silence → line1 at 16.91)
- turn 1: 16.91 → 32.86 (line1 ends 32.51, +0.35 → 32.86)
- turn 2: 32.86 → 49.21 (line2 ends 48.86, +0.35 → 49.21)
- turn 3: 49.21 → 68.76 (line3 ends 68.41, +0.35 → 68.76)
- turn 4: 68.76 → 89.48 (line4 ends 89.48; dialog end)
- sub4 out: 89.48 → 89.78; final hold → 89.98

## Task

Modify ONLY `/Users/zd/Documents/mathflow/demo/hybrid_chain.py`. Keep every animation run_time and flip() identical; ONLY change the five `self.wait(...)` values (+ inline comments) so each turn ends at the new boundary:

1. Turn 0: animations end at 2.65 → wait to 16.91 → `self.wait(14.26)` (was 15.86). Comment `# 2.65 -> 16.91 (turn 0 end)`
2. Turn 1: anchor 23.86 (turn1 start 16.91 + 0.35+0.6+1.0+2.5+2.5) → wait to 32.86 → `self.wait(9.00)` (was 13.08). Comment `# 23.86 -> 32.86 (turn 1 end)`
3. Turn 2: anchor 35.71 (32.86 + 0.35 + 2.5) → wait to 49.21 → `self.wait(13.50)` (was 16.30). Comment `# 35.71 -> 49.21 (turn 2 end)`
4. Turn 3: anchor 55.36 (49.21 + 0.35 + 2.5 + 2.5 + 0.8) → wait to 68.76 → `self.wait(13.40)` (was 10.84). Comment `# 55.36 -> 68.76 (turn 3 end)`
5. Turn 4: anchor 72.41 (68.76 + 0.35 + 2.0 + 0.5 + 0.8) → wait to 89.48 → `self.wait(17.07)` (was 14.43). Comment `# 72.41 -> 89.48 (dialog end)`

Update section header comments to new boundaries: turn 1 (16.91 - 32.86), turn 2 (32.86 - 49.21), turn 3 (49.21 - 68.76), turn 4 (68.76 - 89.48); fade comments: turn1 `# 16.91 -> 17.26`, turn2 `# 32.86 -> 33.21`, turn3 `# 49.21 -> 49.56`, turn4 `# 68.76 -> 69.11`; sub4 out `# 89.48 -> 89.78`; final hold `# 89.78 -> 89.98`.

Do NOT change: dialog text, font/band code (already updated: wrap 96, line_spacing 0.25, font 22), run_times, flip internals. Do NOT run manim. Do NOT git commit. English only.

## Verification (human will run)

1. `cd ~/Documents/mathflow && .venv/bin/python -m py_compile demo/hybrid_chain.py`
2. Render + mux /tmp/dlg4/full.mp3 → duration ≈ 90.0 s.
3. Frames at t ≈ 4, 24, 42, 58, 78 → subtitle i matches turn i, ≤3 lines, no overflow.

Report: exact wait values changed.
