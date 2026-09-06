# TASK_backend_api.md — MathFlow HTTP API for mobile client (Mac mini backend)

## Context

MathFlow generates Lean 4 exercises: the LLM (DeepSeek) produces a fill-in question with
ONE correct fragment; deterministic string mutations + the Lean compiler as judge produce
distractors (exactly one option compiles). Existing pieces in this repo (import, do NOT
modify unless strictly necessary):

- `mathflow.py` — `compile_check(code, session_code="") -> (bool, str)`; compiles via
  `lake env lean` (~17s cold start per invocation)
- `llm.py` — `chat_with_retry`; mock mode via env `MATHFLOW_LLM_MOCK=1`
- `prototype_fill.py` — `build_question(goal) -> dict` (full question incl. options);
  `first_error_line(msg)`; safe in mock mode
- `web.py` — reference for stdlib `http.server` `ThreadingHTTPServer` patterns

Environment: Python 3.9.6, **stdlib only** (flask/fastapi are NOT installed; do not pip
install anything). Lean binaries at `~/.elan/bin`.

## Deliverable

New file `api_server.py` in `~/Documents/mathflow` plus generated cache files under
`data/courses/`. **No git commits.** English code/comments/strings (UI is English).

## API (JSON over stdlib ThreadingHTTPServer)

Bind `0.0.0.0`, default port `8787` (first CLI arg overrides). Must work with
`MATHFLOW_LLM_MOCK=1`.

1. `GET /api/health` → `{"ok": true}`
2. `GET /api/lessons` → `[{"id": str, "title": str, "created_at": str, "question_count": int}]`
   from the cache dir; `[]` if empty.
3. `GET /api/lessons/<id>` → `{"id": str, "title": str, "questions": [{"qid": str, "code": str,
   "options": [{"text": str, "is_correct": bool}], "explanation": str, "hint": str}]}`;
   404 if unknown id. `code` contains exactly one `___` blank.
4. `POST /api/check` body `{"qid": str, "answer": str}` → `{"correct": bool, "error": str|null}`.
   Substitute the answer into the stored template at `___`, then `compile_check`.
   **Fast path:** if `answer` equals the stored correct fragment → `{"correct": true, "error": null}`
   with NO compile. Free-form fills are correct iff they compile; on failure return the
   truncated first error line (reuse `prototype_fill.first_error_line`).
5. `POST /api/lessons/generate` body `{"goal": str}` → generate ONE question via
   `prototype_fill.build_question`, append to `data/courses/<id>.json` (id = slugified goal
   + short timestamp), return the lesson object as in GET /api/lessons/<id>. Serialize with a
   `threading.Lock` (single-flight; compiles are slow).
6. `--seed` flag: on startup, if `data/courses/` is empty, generate one mock course
   (`MATHFLOW_LLM_MOCK=1`) so the API always has content. Usage:
   `MATHFLOW_LLM_MOCK=1 python3 api_server.py --seed 8787`

## Caching

- Courses: one JSON file per lesson under `data/courses/` (list of question dicts).
- Compile results: in-memory LRU (max ~64 entries) keyed by sha1 of the substituted code,
  so identical answers never recompile. Thread-safe (lock around compile + cache access).

## Verification (MUST run; paste outputs into the final report)

1. Start: `MATHFLOW_LLM_MOCK=1 python3 api_server.py --seed 8787` (background)
2. `curl -s localhost:8787/api/health` → ok
3. `curl -s localhost:8787/api/lessons` → seeded lesson present
4. `curl -s localhost:8787/api/lessons/<id>` → each question has exactly one `is_correct: true` option
5. `curl -s -X POST localhost:8787/api/check -d '{"qid": "<id>", "answer": "<correct fragment>"}'`
   → `correct: true` (fast path, instant)
6. `curl -s -X POST localhost:8787/api/check -d '{"qid": "<id>", "answer": "<one mutated wrong fragment>"}'`
   → `correct: false` + error text (this triggers ONE real compile, ~17-70s, be patient)
7. `curl -s -X POST localhost:8787/api/lessons/generate -d '{"goal": "a + b = b + a"}'`
   in mock mode → new lesson appears in `GET /api/lessons`

Report: file created, endpoint behaviors, timing of the slow check, any deviations.
Stop the server or leave it running — either is fine, but document how to start it.

## Constraints

- Do NOT run real LLM generation (no DEEPSEEK_API_KEY needed — mock mode only).
- Do NOT modify `mathflow.py` / `prototype_fill.py` / `llm.py` / `web.py` — import instead.
- Do NOT commit to git.
- Keep port 8787.
