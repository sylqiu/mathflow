# TASK_course_mode.md — MathFlow Course Mode: Pseudorandomness course player (Phase 1)

## Context

MathFlow currently has a Lean-exercise backend (`api_server.py`, port 8787, courses cache in `data/courses/*.json`) and a single-file web prototype (`web.py`). We are adding a **Course Mode**: a theory-course player for a new "Pseudorandomness" course (based on Oded Goldreich's primer). Phase 1 = course content for Modules M1+M2 + `course_server.py` (API + single-page player).

Existing assets in this repo (reference, do NOT modify):
- `web.py` — reference for stdlib `http.server` `ThreadingHTTPServer` + single-page dark UI + KaTeX (CDN: `https://cdn.jsdelivr.net/npm/katex@0.16.9/...`)
- `api_server.py` — courses cache at `data/courses/*.json` via **non-recursive** `COURSES_DIR.glob("*.json")`; subdirectories are safe (do not create top-level `.json` files)
- `mathflow.py` / `llm.py` / `prototype_fill.py` — NOT needed in Phase 1 (no Lean checks; checkpoints are graded locally)

Resources for content accuracy (read these, do NOT invent math):
- `course_blueprint/COURSE.md` — course blueprint (Modules M1/M2 sections; checkpoints answers in §4)
- `course_blueprint/prg08.txt` — full text of Goldreich, "Pseudorandom Generators: A Primer" (2008). **Every definition, theorem, and section number must be verified against this file.**

Environment: Python 3.9.6, **stdlib only** (do not pip install anything). English code/comments/strings (UI is English). **No git commits.**

## Deliverable A — course content

Create `data/courses/pseudorandomness-primer/`:

```
data/courses/pseudorandomness-primer/manifest.json
data/courses/pseudorandomness-primer/lessons/m1-three-theories.json
data/courses/pseudorandomness-primer/lessons/m1-general-paradigm.json
data/courses/pseudorandomness-primer/lessons/m1-m2-checkpoints.json
data/courses/pseudorandomness-primer/lessons/m2-prg-definition.json
data/courses/pseudorandomness-primer/lessons/m2-ci-definition.json
```

### manifest.json

```jsonc
{
  "id": "pseudorandomness-primer",
  "title": "Pseudorandomness: From Computational Indistinguishability to Derandomization",
  "subtitle": "Based on Oded Goldreich, \"Pseudorandom Generators: A Primer\" (2008)",
  "source_url": "https://www.wisdom.weizmann.ac.il/~oded/c-indist.html",
  "modules": [
    {"id": "m1", "title": "Three Theories of Randomness & the General Paradigm", "lessons": [
      {"id": "m1-three-theories"}, {"id": "m1-general-paradigm"}]},
    {"id": "m2", "title": "Computational Indistinguishability", "lessons": [
      {"id": "m2-prg-definition"}, {"id": "m2-ci-definition"}]},
    {"id": "checkpoint", "title": "Checkpoints: M1 & M2", "lessons": [
      {"id": "m1-m2-checkpoints"}]}
  ]
}
```

### Lesson schema (all fields required; `kind` ∈ `theory` | `mcq`)

```jsonc
{
  "id": "m2-ci-definition",
  "module": "m2",
  "kind": "theory",
  "title": "Computational Indistinguishability — the Definition",
  "reading": {"text": "Primer §2.3.1 (pp. 15–16)", "url": "https://www.wisdom.weizmann.ac.il/~oded/PSX/prg08.pdf"},
  "body": "Markdown with $$...$$ math (KaTeX). Reference defs/theorems as @def:ci or @thm:2.14 (front-end renders these as clickable chips).",
  "defs": [
    {"id": "ci", "name": "Computational Indistinguishability",
     "statement": "$$\\{X_n\\}_n \\equiv_c \\{Y_n\\}_n$$ iff for every PPT distinguisher D and every polynomial p, for all sufficiently large n: $$|\\Pr[D(X_n){=}1] - \\Pr[D(Y_n){=}1]| < 1/p(n)$$",
     "intuition": "No efficient procedure can tell the two ensembles apart, even by a hair."}
  ],
  "theorems": [
    {"id": "2.14", "name": "PRGs exist iff one-way functions exist", "statement": "..."}
  ],
  "checkpoints": [
    {"qid": "m2-cp-1", "question": "...", "options": [{"text": "...", "is_correct": true}], "explanation": "..."}
  ],
  "exercises": [
    {"id": "m2-ex-1", "prompt": "...", "hint": "...", "solution": "..."}
  ]
}
```

### Content rules (accuracy is the top priority)

1. **M1 lessons** (source: prg08.txt Preface + §1.1–1.4):
   - `m1-three-theories` (theory): Shannon/information-theoretic view; Kolmogorov/complexity view (and its uncomputability); the complexity-theoretic "third theory" (randomness as an effect on an observer); the Alice & Bob coin-flip thought experiment (§1.1). Defs: none required; include 1–2 "concept" entries in `defs` if helpful (e.g., id `prg-general`). 1 checkpoint, 1 exercise.
   - `m1-general-paradigm` (theory): the three fundamental aspects of any pseudorandom generator — (1) stretch measure, (2) class of distinguishers, (3) resources of the generator (§1.4.1); the instantiations that the rest of the course follows (§1.4.3). 1 checkpoint, 1 exercise.
2. **M2 lessons** (source: prg08.txt §2.1–2.3.2; use ln00a.txt only as a secondary check if needed):
   - `m2-prg-definition` (theory): Definition 2.1 (general-purpose PRG) with the full quantifier structure; stretch function ℓ(n) > n; the archetypical application (Construction 2.2 / Prop 2.3 intuition). 1–2 checkpoints, 1–2 exercises.
   - `m2-ci-definition` (theory): computational indistinguishability (§2.3.1), relation to statistical closeness (§2.3.2), why the quantifier order "∀D ∃ε (per distinguisher)" matters and what ∃ε ∀D would mean (statistical closeness). 2 checkpoints, 2 exercises.
3. **`m1-m2-checkpoints`** (mcq): 5 checkpoints covering the classic confusions across M1+M2 (see COURSE.md §4 for answer keys): quantifier order; statistical vs computational closeness; "no visible pattern" is not pseudorandomness; why deterministic generation is possible in the complexity-theoretic sense but not Shannon/Kolmogorov sense; the three fundamental aspects.
4. Every checkpoint has **exactly one** `is_correct: true` option (2–4 options each) and a real explanation (2–4 sentences, teaching-focused).
5. Exercises: prompt + hint + solution (solution = full answer skeleton, 5–15 lines, matching COURSE.md §4 answer keys).
6. Body markdown: use `##`/`###` headings, `**bold**`, inline `` `code` ``, `$$...$$` block math, and `@def:x`/`@thm:y` chips. Keep each lesson 40–90 lines of body. English only.

## Deliverable B — course_server.py (new file, stdlib only)

Single-file HTTP server: course API + single-page player. Port **8788** (first CLI arg overrides). `ThreadingHTTPServer`. English code/comments/strings.

### API

1. `GET /api/courses` → `[{"id", "title", "subtitle", "source_url", "modules": [{"id", "title", "lessons": [{"id", "title", "kind"}]}]}]` (read all course dirs under `data/courses/` that contain a `manifest.json`; only this one exists).
2. `GET /api/courses/<id>/lessons/<lid>` → full lesson JSON **without** `exercises[].solution` (keep a `"has_solution": true` marker instead); 404 if unknown course/lesson.
3. `GET /api/courses/<id>/lessons/<lid>/solutions` → `{"exercises": [{"id", "solution"}]}` (collapsible reveal in the UI).
4. `POST /api/courses/<id>/checkpoint` body `{"qid": "...", "option_index": 0}` → `{"correct": bool, "explanation": "..."}` — server-side grading by looking up the stored checkpoint; instant, no Lean, no LLM. 404 if qid unknown.
5. `GET /` → single-page player HTML (dark theme, KaTeX via the same jsdelivr CDN as web.py).
6. `GET /media/<course_id>/<path>` → static file from `data/courses/<course_id>/media/` (directory may be empty for now; return 404 if missing). Keep the route so Phase 2 videos just work.

### Player requirements (served by course_server.py, no build step)

- **Routing**: hash-based — `#/course/<id>` (course home), `#/course/<id>/lesson/<lid>` (lesson view).
- **Course home**: hero (title, subtitle, source link), module list with per-module progress bars (from localStorage), lesson rows with completion checkmarks.
- **Lesson view**: renders `body` markdown (headings, bold, inline code, `$$` math via KaTeX auto-render, `@def:x` / `@thm:y` chips). Clicking a chip opens a popover card with name + statement (KaTeX-rendered) + intuition.
- **Checkpoints**: MCQ tap-to-answer; instant feedback (green/red); wrong → show explanation; right → show explanation too. Correct answers mark the checkpoint complete; all checkpoints complete marks the lesson complete (localStorage, key `mf2:v1:<courseId>:progress`, shape: `{lessons: {<lid>: {done: bool, checkpoints: {<qid>: bool}}}}`).
- **Exercises**: prompt + "Show hint" toggle + "Reveal solution" button (fetches the solutions endpoint once, then caches in memory).
- **Layout**: left sidebar module tree (collapsible; drawer overlay on narrow screens), main content area; responsive; dark theme matching web.py's aesthetic (copy the CSS vibe from web.py).
- KaTeX: `<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">` + `katex.min.js` + `contrib/auto-render.min.js` (defer), exactly like web.py lines 117–119.

Do NOT modify `api_server.py`, `web.py`, `mathflow.py`, `llm.py`, `prototype_fill.py`.

## Verification (MUST run; paste outputs into the final report)

1. `python3 -m json.tool` on all 5 lesson files + manifest → valid JSON
2. Start: `python3 course_server.py 8788` (background)
3. `curl -s localhost:8788/api/courses` → 1 course, 2 modules + checkpoint module, 5 lessons with kinds
4. `curl -s localhost:8788/api/courses/pseudorandomness-primer/lessons/m2-ci-definition` → lesson JSON: `kind=theory`, `defs` non-empty, no `solution` key inside exercises; then `curl .../solutions` → solutions present
5. `curl -s -X POST localhost:8788/api/courses/pseudorandomness-primer/checkpoint -d '{"qid":"<real qid>","option_index":<correct index>}'` → `{"correct": true, ...}`; repeat with a wrong index → `correct: false` + explanation
6. `curl -s localhost:8788/ | grep -c katex` → ≥ 3 (CSS + JS + auto-render)
7. `curl -s localhost:8788/api/courses/pseudorandomness-primer/lessons/nope` → 404
8. Report: files created, endpoint behaviors, any deviations, and the exact curl outputs for steps 3–6.

## Constraints

- Python 3.9.6 stdlib only. No pip installs. No git commits. English only.
- **Accuracy**: verify every theorem/definition/section number against `course_blueprint/prg08.txt` before writing content. Do not invent results.
- Keep port 8788. Stop the server when done (or document how to start it).
