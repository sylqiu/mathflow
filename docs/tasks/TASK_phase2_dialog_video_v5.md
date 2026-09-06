# TASK_phase2_dialog_video_v5.md — hybrid_chain: remove HOST A/B chips from subtitles

## Context

The rendered hybrid_chain video shows a speaker chip ("HOST A" / "HOST B") next to each subtitle. The user wants the chips gone — subtitle text only, centered in the band.

## Current code (demo/hybrid_chain.py, subtitle layer)

```python
subs = []
for speaker, line in dialog:
    chip = Text(
        "HOST A" if speaker == "A" else "HOST B",
        font_size=16, weight=BOLD,
        color=YELLOW if speaker == "A" else BLUE,
    )
    body = Text(
        _wrap(line, 72), font_size=20, color=WHITE,
        line_spacing=0.15,
    )
    sub = VGroup(chip, body).arrange(RIGHT, buff=0.3)
    sub.move_to([0, -3.4, 0])
    subs.append(sub)
```

## Task

Modify ONLY `/Users/zd/Documents/mathflow/demo/hybrid_chain.py`:

1. Remove the `chip` creation entirely (and the now-unused `speaker` variable can stay in the loop unpacking — the dialog tuples still have the speaker letter; just don't create or use a chip).
2. Use the `body` Text alone as the subtitle: center it in the band with `body.move_to([0, -3.4, 0])` and append `body` to `subs` (instead of the VGroup).
3. Keep everything else identical: `_wrap(line, 72)`, `font_size=20`, `color=WHITE`, `line_spacing=0.15`, dialog text, timings, `wait` values, band geometry, all visuals. The `subs` list is later used with FadeIn/FadeOut — appending the bare `body` mobject works the same.
4. Do NOT run manim. Do NOT git commit. English only.

## Verification (human will run)

1. `cd ~/Documents/mathflow && .venv/bin/python -m py_compile demo/hybrid_chain.py`
2. Render: `PATH="$PWD/demo/bin:$PATH" .venv/bin/manim -qm demo/hybrid_chain.py HybridChain`
3. Mux `/tmp/dlg2/full.mp3` with ffmpeg (video+audio, no -shortest).
4. Extract frames at t ≈ 4, 24, 42, 60, 76 s → confirm NO "HOST A/B" chip text anywhere, subtitle text centered in band, still fully inside the band (no overflow above the band top line or below the screen bottom).

Report: exact lines changed, confirmation chips are gone and nothing else moved.
