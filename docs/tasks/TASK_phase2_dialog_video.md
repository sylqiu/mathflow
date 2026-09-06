# TASK_phase2_dialog_video.md — hybrid_chain: dialog-driven timeline + Manim subtitles (prototype)

## Context

We are prototyping the "narrated video" style for MathFlow course animations. The user wants NotebookLM-style **two-host dialog** (Host A = curious learner, female voice; Host B = expert explainer, male voice) with **subtitles rendered inside the Manim scene**, and the **animation timeline driven by the dialog timing** (each dialog turn maps to a scene phase; the scene waits long enough for that turn's audio).

The target file: `~/Documents/mathflow/demo/hybrid_chain.py` (existing scene `HybridChain`, currently ~25.5 s, no audio). We will change ONLY this file's `construct()` so that:

1. The total timeline ≈ 34.4 s (the dialog length, see below).
2. A **subtitle layer** is added: one subtitle per dialog turn, bottom-center, with a speaker label chip (Host A / Host B), fading in exactly when that turn's audio starts and fading out when the next turn starts.
3. The existing chalkboard visuals are kept but their pacing is stretched to fill the dialog turns (add `self.wait(...)` to reach the target timestamps; do NOT change what is drawn).

## Dialog script (verbatim; timing is fixed — do not reword)

Audio was already generated with edge-tts at rate +5% and concatenated with 0.35 s silence between turns. Turn start times (absolute, from video t=0) and durations:

| turn | speaker | start (s) | dur (s) | text |
|---|---|---|---|---|
| 0 | A (Host A, curious) | 0.00 | 6.41 | So we want to show that many samples of Y look like many samples of X... but directly, that seems hard? |
| 1 | B (Host B, expert) | 6.76 | 10.03 | Right. So instead, we interpolate: a chain of hybrids, H zero through H k. Each step flips just one component from Y to X. |
| 2 | A | 17.14 | 3.14 | And each single step is easy to analyze? |
| 3 | B | 20.63 | 8.69 | Exactly. Every step has advantage at most epsilon over k. Sum over the k steps, and the total advantage is at most epsilon. |
| 4 | A | 29.67 | 4.75 | Small steps, tight bound. Now I see the whole trick! |

End of dialog: 34.42 s. Scene should end at ≈ 35 s (add a final 0.5 s hold).

## Scene phase mapping (dialog turn → existing visuals)

Map the existing `construct()` steps onto the dialog turns, padding with waits so each turn's subtitle appears at its exact start time:

- **Turn 0 (0.0–6.76 s)** — "the problem": write title "The Hybrid Argument" + caption "Each step flips one component from Y to X". Keep the current `Write(title)` + `FadeIn(caption)` but pad so the turn-0 subtitle (shown during the whole turn) has time. Subtitle 0 fades in at t=0.0 (right after title/caption are up — target: appear by ≈ 0.8 s, stay until 6.76 s).
- **Turn 1 (6.76–17.14 s)** — "the interpolation": legend (X/Y swatches) + first hybrid column H_0 + labels; then perform the first ~2 flips of the sweep (i=1, i=2) at a relaxed pace. Subtitle 1 fades in at 6.76 s, out at 17.14 s.
- **Turn 2 (17.14–20.63 s)** — "each step easy?": perform flip i=3 (FadeIn column, flip one cell Y→X). Subtitle 2 fades in at 17.14 s, out at 20.63 s.
- **Turn 3 (20.63–29.67 s)** — "the bound": perform flips i=4, i=5 with per-step advantage bars ε/k and the cumulative bar segments; then the red cap line at ε with label. Subtitle 3 fades in at 20.63 s, out at 29.67 s.
- **Turn 4 (29.67–34.42 s)** — "the payoff": `Write(payoff)` formula and the takeaway text ("The whole chain has advantage <= epsilon"). Subtitle 4 fades in at 29.67 s; hold to 34.92 s (0.5 s after dialog ends).

Implementation guidance: compute the cumulative elapsed time as you go (sum of `run_time` + `wait`), and insert `self.wait(delta)` at the end of each phase so the next subtitle starts exactly at its target timestamp. Keep the math mobjects and colors identical to the current file.

## Subtitle layer design

- One `VGroup` per turn: a small label chip (`Text("HOST A")` / `Text("HOST B")`, font_size 18, bold) + the turn text (`Text(..., font_size 26, line_spacing 0.15)`). 
  - Host A chip color: `YELLOW`; Host B chip color: `BLUE` (matching the legend colors used for X/Y).
  - Text color: `WHITE`; wrap text at ~70 chars (`Text` auto-wraps by default in manim; set `line_spacing` and `width` to keep it on 2 lines max, e.g. `width=config.frame_width - 1.5`).
- Position: bottom-center, `subtitle.to_edge(DOWN, buff=0.35)`.
- Behavior: `FadeIn(subtitle, run_time=0.35)` at the turn's start time; `FadeOut(subtitle, run_time=0.3)` at the turn's end time. Only one subtitle visible at a time.
- The subtitle must never overlap the cumulative-bar area (bars live at y ≈ -2.35, payoff at y ≈ -1.85); bottom-center with buff 0.35 is safe. If any visual collides, raise the subtitle slightly (buff 0.3) — do not move the math visuals.

## Constraints

- Python 3.9.6, manim v0.19.0 (`.venv`), tectonic shim (`demo/bin/pdflatex`), English only.
- Modify ONLY `demo/hybrid_chain.py`. Do not touch other files.
- Do NOT run manim (the human renders and verifies).
- Do NOT git commit.
- Do not reword the dialog lines; timings are fixed. If you believe a subtitle would overflow, adjust font_size (24–28) or `width` — never the text.

## Verification (human will run; just make the code correct)

1. `cd ~/Documents/mathflow && .venv/bin/python -m py_compile demo/hybrid_chain.py` — no syntax errors.
2. Human renders `PATH="$PWD/demo/bin:$PATH" .venv/bin/manim -qm demo/hybrid_chain.py HybridChain` and checks subtitle timing against the table above, then muxes the pre-built dialog audio (`/tmp/dlg/full.mp3`) with ffmpeg.
3. Expected final duration ≈ 35 s.

Report: what you changed, the exact wait values you inserted (a per-phase table), and confirm subtitle start times match the table.
