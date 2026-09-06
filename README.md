# MathFlow

AI-guided math seminar: learn a concept, then prove it — with Lean 4 as the
verifier and a course player designed for phones.

MathFlow has two layers:

1. **Lean 4 practice engine** — the "seminar loop": AI (DeepSeek) explains a
   concept → you answer (multiple-choice, fill-in-the-blank, or by writing a
   Lean proof) → Lean 4 compiles and verifies. Pass → next question; fail →
   the AI explains your exact error.
2. **Course player + admin** — a Python-stdlib-only server that serves
   self-contained math courses (JSON lessons with LaTeX, definitions,
   theorems, videos/audio) and renders them in a mobile-friendly player.

## Components

| Path | What it is |
|---|---|
| `course_server.py` | **Course Server** — course JSON API + single-page course player. Main entry point; serves courses from `data/courses/<course-id>/` (`manifest.json` + `lessons/*.json`). |
| `templates/player.html` | Course player UI (renders lessons, checkpoints, exercises; local judging for MCQ). |
| `templates/admin.html` | Admin/authoring UI for course management. |
| `api_server.py` | JSON HTTP API for the mobile client (question generation + judging on the Mac mini backend). |
| `web.py` | Earlier single-file browser version of the seminar loop. |
| `mathflow.py` | Terminal seminar REPL (`:seminar`, `:check`, `:info`). |
| `llm.py` | DeepSeek Chat Completions client. API key comes from the `DEEPSEEK_API_KEY` environment variable — never hardcoded. |
| `Mathflow/`, `Main.lean`, `*.lean` | Lean 4 library and entry points (proof checking / theorem proving). |
| `lesson.schema.json` + `validate_courses.py` | Lesson JSON schema and a stdlib validator (structure + cross-file checks: chip references, checkpoint options, media files). |
| `course_blueprint/` | Course design notes. |
| `docs/tasks/` | Development planning notes (`TASK_*.md`). |
| `.github/workflows/lean_action_ci.yml` | CI: builds and checks the Lean code on push. |

## Quick start

Course player (pure Python 3.9+, stdlib only, no install):

```sh
python3 course_server.py 8788
# open http://localhost:8788
```

It serves whatever courses exist under `data/courses/<course-id>/`.
**Course content is not distributed in this public repo** — see below.

AI features (terminal seminar / API question generation) need a DeepSeek key:

```sh
export DEEPSEEK_API_KEY=...
```

Lean verification (`lake build`, `lake env lean ...`) requires a Lean 4
toolchain pinned by `lean-toolchain`.

## Course content

Actual lessons (JSON) and media live in a separate **private** repository,
because lesson files embed exercise solutions and are intentionally not
published. This repo ships the app plus `lesson.schema.json` and
`validate_courses.py`, so anyone can author their own courses:

```sh
python3 validate_courses.py   # validate data/courses/* against the schema
```

A browsable demo of the pseudorandomness primer course (static, sanitized
export, m1–m4) is hosted at
<https://sylqiu.github.io/pseudorandomness-course/>.

## Status

Lean CI: ![Lean CI](https://github.com/sylqiu/mathflow/actions/workflows/lean_action_ci.yml/badge.svg)

Active development happens on the Mac mini; the local copy also contains the
private course content (`data/`, `media/`, `demo/`) that is git-ignored here.
