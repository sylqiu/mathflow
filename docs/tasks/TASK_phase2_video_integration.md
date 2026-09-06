# TASK_phase2_video_integration.md — MathFlow Course Mode Phase 2: Player video integration

## Context

- Phase 1 delivered the course player (`course_server.py`, port 8788, single-page dark UI, KaTeX, localStorage progress key `mf2:v1:<courseId>:progress`).
- Phase 2 (audio) is DONE: podcast mp3s for all 5 lessons are in `data/courses/pseudorandomness-primer/media/audio/`, and the player already renders an `<audio controls>` bar when a lesson has an `audio` field. **Do not break or remove this.**
- Phase 2 (video) is THIS task: 3 P0 manim animations were rendered and already copied to the course media dir:
  - `data/courses/pseudorandomness-primer/media/videos/hybrid_chain.mp4` (25.5 s)
  - `data/courses/pseudorandomness-primer/media/videos/stat_vs_comp.mp4` (21.2 s)
  - `data/courses/pseudorandomness-primer/media/videos/prg_stretch.mp4` (25.5 s)
- The `/media/<course_id>/<path>` route already serves these (verify with curl before starting).
- The manim sources (`demo/hybrid_chain.py`, `demo/stat_vs_comp.py`, `demo/prg_stretch.py`) each contain a docstring with the intended **before/after questions** — use those EXACT questions (adapt wording only if needed for standalone display).

## Deliverable A — lesson data: attach videos to lessons

### A1. `data/courses/pseudorandomness-primer/lessons/m2-ci-definition.json`
Add a top-level `media.videos` array containing ONE entry for `stat_vs_comp.mp4`:

```jsonc
"media": {"videos": [
  {
    "id": "stat_vs_comp",
    "file": "stat_vs_comp.mp4",
    "title": "Statistical closeness vs computational indistinguishability",
    "duration_sec": 21.2,
    "chapters": [{"label": "...", "t": <sec>}, ...],
    "before": {"qid": "svc-before", "question": "<from docstring>",
               "options": [{"text": "...", "is_correct": false}, ...],   // exactly one correct
               "explanation": "2-4 teaching sentences"},
    "after":  {"qid": "svc-after",  "question": "<from docstring>",
               "options": [...], "explanation": "..."}
  }
]}
```

- `chapters`: derive 2–3 natural jump points from the manim script's section comments (read `demo/stat_vs_comp.py`); each `t` must be within `[0, 21.2)`.
- `before`/`after`: take the two questions from the script docstring. Write 4 plausible options each (exactly one `is_correct: true`), 2–4 sentence explanations. Ground the math in `course_blueprint/prg08.txt` §2.3.1–2.3.2 (do not invent).
- Keep all existing lesson fields intact; only ADD `media`.

### A2. `data/courses/pseudorandomness-primer/lessons/m2-prg-definition.json`
Same pattern, ONE entry for `prg_stretch.mp4` (id `prg_stretch`, duration 25.5, chapters from `demo/prg_stretch.py` sections, before/after from its docstring; ground in prg08 §2.1 + §2.3.1 uniform-ensemble remark).

### A3. New lesson `data/courses/pseudorandomness-primer/lessons/media-hybrid-argument.json`
`hybrid_chain.mp4` is the "most important animation" but belongs to M3 content (not yet written). Give it a home as a standalone video lesson:

- `kind`: `"theory"` (reuse existing schema; no new kind needed).
- `id`: `"media-hybrid-argument"`, `module`: `"media"`, `title`: `"The Hybrid Argument — Core Visualization"`.
- `reading`: `{"text": "Primer §3.1 (hybrid argument; see also §2.3.1)", "url": "https://www.wisdom.weizmann.ac.il/~oded/PSX/prg08.pdf"}` — verify the section number against `course_blueprint/prg08.txt` first and use the correct one.
- `body`: brief markdown (5–8 lines) introducing the hybrid argument as the central proof technique; use `$$...$$` where helpful; reference `@thm:2.14`-style chips only if the referenced defs exist in this lesson's defs/theorems (add a `defs` entry for the hybrid argument if useful, grounded in prg08).
- `media.videos`: ONE entry for `hybrid_chain.mp4` (id `hybrid_chain`, duration 25.5, chapters from `demo/hybrid_chain.py` sections, before/after from its docstring).
- `checkpoints`: `[]`, `exercises`: `[]` (this is a visualization lesson; the before/after questions carry the learning load).
- Must validate against the existing lesson schema (all required top-level fields present; `checkpoints`/`exercises` may be empty arrays).

### A4. `data/courses/pseudorandomness-primer/manifest.json`
Add a module AFTER the checkpoint module:

```jsonc
{"id": "media", "title": "Core Visualizations", "lessons": [{"id": "media-hybrid-argument"}]}
```

(Order in the UI: M1, M2, Checkpoints, Media.)

## Deliverable B — player: video rendering + before/after quiz (edit only `course_server.py`)

Extend the single-page player HTML/JS (it's inline in course_server.py):

1. **Video section**: when a lesson has `media.videos`, render each video as:
   - `<video controls preload="metadata" src="/media/<course_id>/<file>">` styled to fit the dark theme (max-width 100%, rounded corners, border matching the podcast bar aesthetic).
   - Below it a **chapter chip row**: one button per `chapters[]` entry; clicking seeks the video to `t` seconds and highlights the active chip (update on `timeupdate`).
   - A short title line (video `title`).
2. **Before/after quiz** (per video):
   - Show the `before` question ABOVE the video as a collapsible prompt ("Before you watch: ...") — answerable before/while watching, MCQ tap-to-answer with instant green/red feedback exactly like existing checkpoints, explanation shown after answering (right or wrong).
   - Show the `after` question BELOW the video ("After you watched: ..."), same grading UX.
   - Grading is purely client-side against the stored `options[].is_correct` (no new endpoint needed).
   - Optionally auto-reveal the `after` block once the video reaches `duration_sec - 2` or on `ended` — nice-to-have; keep it simple and robust.
3. **Progress persistence**: extend the existing `mf2:v1:<courseId>:progress` object with a `videos` map:
   `{lessons: {...}, videos: {<lessonId>: {<videoId>: {before: bool, after: bool}}}}`
   - `before`/`after` flip to true when answered correctly (wrong answers stay false, like checkpoints).
   - For lesson completion: a lesson with `media.videos` is marked done when ALL its videos have `before` and `after` true (in addition to any checkpoints, which for these lessons are none/empty).
4. Keep everything else (routing, audio bar, defs/theorems chips, checkpoint UX, module tree, progress bars) unchanged.

## Constraints

- Python 3.9.6, stdlib only. English only. No git commits.
- Do NOT modify `api_server.py`, `web.py`, `mathflow.py`, `llm.py`, `prototype_fill.py`, or the existing audio integration in `course_server.py`.
- Lesson JSON edits: only ADD `media` (A1, A2) / create A3 / edit manifest A4. Do not touch other lesson content.
- Math accuracy: verify every claim/section number against `course_blueprint/prg08.txt`.

## Verification (run these; paste outputs into the final report)

1. `python3 -m json.tool` on: `m2-ci-definition.json`, `m2-prg-definition.json`, `media-hybrid-argument.json`, `manifest.json` → all valid.
2. Restart the server (kill old `course_server.py` process first, then start fresh — a stale process holds port 8788):
   `pkill -f course_server.py; sleep 1; (python3 course_server.py 8788 > /tmp/course_server_v.log 2>&1 &)`
3. `curl -s localhost:8788/api/courses/pseudorandomness-primer/lessons/m2-ci-definition | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['media'])"` → videos array with 1 entry, no `solution` keys anywhere in the response.
4. `curl -s -o /dev/null -w "%{http_code}" localhost:8788/media/pseudorandomness-primer/videos/stat_vs_comp.mp4` → 200; same for `hybrid_chain.mp4` and `prg_stretch.mp4`.
5. `curl -s localhost:8788/ | grep -c "video"` → ≥ 5 (video element + JS).
6. `curl -s localhost:8788/api/courses | python3 -c "import json,sys; d=json.load(sys.stdin); print([m['id'] for m in d[0]['modules']])"` → includes `media`.
7. Report: files changed/created, the before/after questions you embedded, chapter timestamps chosen, any deviations, and the exact curl outputs for steps 3–6.
