# TASK_phase2_dialog_video_v2.md — hybrid_chain: dedicated subtitle zone (fix overlay)

## Problem

The current `demo/hybrid_chain.py` renders subtitles at bottom-center with `to_edge(DOWN, buff=0.35)`. The user reports the subtitles **overlap the math content** (the cumulative advantage bar, the ε cap, and the payoff formula sit low in the frame and collide with the subtitle text). The scene is 1280×720 (`-qm`): x ∈ [-7.111, 7.111], y ∈ [-4, 4].

## Goal

Add a **dedicated subtitle zone**: a fixed, full-width, semi-transparent dark band along the bottom of the frame. Subtitles render ONLY inside this band. All existing math visuals must be moved UP so that **no visual ever enters the band**. The dialog timing table stays EXACTLY the same (do not change any timings).

## Design

1. **Subtitle band** (draw first, behind everything):
   - `Rectangle(width=14.222, height=1.2)` (full frame width), positioned so it spans y ∈ [-4.0, -2.8] (center at y = -3.4).
   - Fill: `BLACK`, opacity 0.55; stroke: `GREY_B`, width 1. Optional: a thin `Line` at the band's top edge (y = -2.8) as a separator.
   - The band is part of the scene background — add it in `construct()` before the subtitle groups (or as a static mobject); it should be visible throughout the whole scene.

2. **Subtitle content inside the band** (per turn, one `VGroup`):
   - Label chip: `Text("HOST A")` (YELLOW, bold, font_size 16) or `Text("HOST B")` (BLUE, bold, font_size 16), positioned at the band's top-left (x ≈ -6.9, y ≈ -3.15) for every turn — or, if cleaner, inline before the text. Choose the layout that fits the band; the key constraint is everything stays inside y ∈ [-4.0, -2.8].
   - Dialog text: `Text(..., font_size 24, WHITE)`, wrapped to ≤ 2 lines (~70 chars per line, manual `\n` at word boundaries — manim 0.19 `Text` does not auto-wrap). Centered in the band: center y ≈ -3.4, x = 0. If label chip is inline, keep text width ≤ 13.4 so the chip + text fit.
   - Fade in/out timings unchanged: sub i fades in at its turn start, fades out at the next turn start (cross-fade 0.35 s), sub 4 fades out at 34.92 → 35.22.

3. **Move existing visuals up** so nothing is below y = -2.8:
   - Title (top edge): unchanged.
   - Caption under title: unchanged.
   - Legend (UR corner): unchanged.
   - Hybrid columns: currently `move_to(UP * 0.9)`; keep, but verify the bottom-most label (H_0…H_k under each column) stays above -2.8. If not, nudge columns up (e.g. `UP * 1.2`).
   - Per-step advantage bars: currently at y = -1.35 → move UP to y ≈ -0.9 (keep relative position to the columns' gap).
   - Cumulative bar: currently `cum_y = -2.35` → move UP to `cum_y ≈ -1.55`. Adjust `cum_x0`, segment width, cap line and `cap_label` accordingly (they follow `cum_y`).
   - Payoff formula + takeaway: currently `next_to(cum_bar, DOWN, buff=0.5)` → place below the (moved-up) cumulative bar but keep payoff's lowest point ≥ -2.6 (well above the band top at -2.8). Use `buff` ≈ 0.35–0.45 and verify.
   - ε cap label: ensure it stays above -2.8 too.

4. **Timing table (unchanged — do NOT touch)**

   | turn | start (s) | dur (s) |
   |---|---|---|
   | 0 | 0.00 | 6.41 |
   | 1 | 6.76 | 10.03 |
   | 2 | 17.14 | 3.14 |
   | 3 | 20.63 | 8.69 |
   | 4 | 29.67 | 4.75 |

   End ≈ 34.92 s, final hold to 35.22 s. Keep every `wait` value exactly as it is now (the timeline already matches; only positions change).

## Constraints

- Modify ONLY `demo/hybrid_chain.py`. Python 3.9.6, manim 0.19.0, tectonic shim. English only. Do not reword dialog. Do not run manim. Do not git commit.
- The subtitle band must be drawn so it renders behind the subtitles but in front of nothing else — add it early in `construct()` before the subtitle VGroups, and do not `FadeIn/Out` the band (static).

## Verification (human will run)

1. `py_compile` passes.
2. Human renders (`PATH="$PWD/demo/bin:$PATH" .venv/bin/manim -qm demo/hybrid_chain.py HybridChain`), then extracts frames at t ≈ 2, 8, 18, 22, 31 s and visually checks: (a) every subtitle sits fully inside the band y ∈ [-4.0, -2.8]; (b) no math visual is inside the band; (c) dialog text not clipped.
3. Human muxes `/tmp/dlg/full.mp3` again and confirms duration ≈ 35.2 s.

Report: the exact new y-coordinates you chose for every moved visual (bars, cum bar, cap, payoff, takeaway), and confirm no visual's bbox dips below y = -2.8.
