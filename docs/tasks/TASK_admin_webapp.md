# TASK: MathFlow Course Management Webapp (Admin + Pipeline Entry)

Goal: extend the existing single-file course server into a two-sided webapp:
a **reader/player side** (already working, keep unchanged) and an **admin side**
(manage courses, edit lessons, upload media, import/publish course packages).
Plus a CLI import tool usable from the terminal.

Constraints (keep the project style):
- Python 3.9+, **stdlib only** (no Flask/Django). Use `http.server` like `course_server.py`.
- No build step for the frontend: plain HTML/CSS/JS in a template file, served as-is.
- Dark theme, same visual language as `templates/player.html` (--bg #0f1115 etc.).
- English UI only (MathFlow rule).
- Do NOT commit to git. Do NOT touch `templates/player.html` rendering logic.
- Data layout stays: `data/courses/<course-id>/manifest.json`, `lessons/*.json`, `media/{audio,videos}/`.

## Design: one server, two faces

Keep `course_server.py` as the single entry point. Add:

1. `GET /admin` → serves `templates/admin.html` (the management SPA).
2. `GET /api/admin/courses` → list courses with extra admin metadata:
   `[{id, title, subtitle, source_url, lesson_count, module_count, validate: {errors: n, warnings: n}, updated_at}]`
3. Admin write APIs (see below). All admin APIs are **protected**:
   - If env var `MATHFLOW_ADMIN_TOKEN` is set → require header `X-Admin-Token` to match (compare with `hmac.compare_digest`).
   - If not set → allow only requests from loopback (127.0.0.1 / ::1). Return 403 otherwise.
   - Also always require the token header when the request comes from a non-loopback address.

## Admin API surface

Base prefix `/api/admin`. JSON bodies for writes unless noted.

### Courses
- `POST /api/admin/courses` — body `{id, title, subtitle, source_url}`.
  Creates `data/courses/<id>/manifest.json` with empty `modules: []` and creates the
  `lessons/` + `media/audio/` + `media/videos/` dirs. `id` must match `^[A-Za-z0-9][A-Za-z0-9._-]*$`
  (reuse `SAFE_ID_RE`), must not already exist. Returns 201 + the manifest.
- `DELETE /api/admin/courses/<id>` — removes the course dir (shutil.rmtree). Returns 200.
- `GET /api/admin/courses/<id>/manifest` — full manifest JSON.
- `PUT /api/admin/courses/<id>/manifest` — replace manifest (validate: id field unchanged,
  modules[].lessons[].id entries must be unique across course). Returns 200 + saved manifest.
- `GET /api/admin/courses/<id>/validate` — runs the same checks as `validate_courses.py`
  (import it as a module: `sys.path.insert(0, repo root); import validate_courses`), returns
  `{ok: bool, errors: [...], warnings: [...]}`.

### Lessons (admin sees solutions — full JSON, unlike the reader API)
- `GET /api/admin/courses/<id>/lessons/<lid>` — full lesson JSON (including `exercises[].solution`).
- `PUT /api/admin/courses/<id>/lessons/<lid>` — save full lesson JSON (create if missing).
  Validates against `lesson.schema.json` shape (structural checks; reuse `validate_courses`
  helpers where practical). Returns 200 + saved lesson.
- `DELETE /api/admin/courses/<id>/lessons/<lid>` — delete the lesson file.
- `POST /api/admin/courses/<id>/lessons` — body `{id, module, kind, title}` → creates a
  lesson skeleton: `{schema_version:1, id, module, kind, title, body:"", defs:[], theorems:[], checkpoints:[], exercises:[]}`.
  `kind` ∈ theory|media|checkpoint|mcq|exercise.

### Media
- `POST /api/admin/courses/<id>/media` — multipart/form-data upload (file field `file`,
  optional field `kind` ∈ `audio`|`videos`, default `audio`). Store as
  `data/courses/<id>/media/<kind>/<sanitized-filename>`. Sanitize filename
  (keep `[A-Za-z0-9._-]`). Reject > 200 MB. Returns `{file, kind, size}`.
- `GET /api/admin/courses/<id>/media` — list `{audio: [names], videos: [names]}`.
- `DELETE /api/admin/courses/<id>/media/<kind>/<filename>` — delete one file.

### Import / publish pipeline (the "course factory" entry)
- `POST /api/admin/import` — multipart upload of a **course package zip**. The zip must contain:
  - `manifest.json` (with `id`, `title`, `modules[]`)
  - `lessons/<id>.json` for every lesson referenced by the manifest
  - optional `media/audio/*.mp3`, `media/videos/*.mp4`
  Pipeline steps, all server-side:
  1. Extract to a temp dir (zip-slip safe: resolve paths, reject `..` escapes).
  2. Validate: manifest references resolvable lessons; run `validate_courses` checks
     against the temp dir by pointing COURSES_DIR there (or replicate its checks).
  3. If errors (not warnings) → return 422 with the full error list, nothing published.
  4. If OK → atomically publish: move/copy into `data/courses/<id>/` (fail if id exists,
     unless `overwrite=true` field given). Return 201 + `{id, lessons: n, media: {audio: n, videos: n}, validate: {errors:0, warnings: n}}`.
- `POST /api/admin/new-from-template` — optional nice-to-have: same as POST /courses but
  also scaffolds one starter lesson. (Can skip if time is short.)

## Frontend: templates/admin.html

Single-page admin UI, same dark theme as the player. Views (hash-routed like the player):

- `#/` — course list: cards with title/subtitle, lesson count, validation badge
  (green OK / red N errors), buttons: Open (links to `/` player), Edit, Validate, Delete (confirm).
  Top bar: "New Course" button, "Import Package" button, link "Open Player".
- `#/new` — form: id, title, subtitle, source_url → POST /api/admin/courses → redirect to edit.
- `#/import` — file input (zip) + optional overwrite checkbox → POST /api/admin/import →
  show pipeline result (validation errors list or success summary).
- `#/course/<id>` — course editor: editable manifest fields (title, subtitle, source_url),
  modules list (add/remove module, add lesson to module, remove lesson, reorder optional),
  tabs: **Lessons** | **Media** | **Validate**.
  - Lessons tab: click lesson → `#/course/<id>/lesson/<lid>`.
  - Media tab: upload audio/video via file input + kind select; list existing files with delete.
  - Validate tab: run GET validate, show errors/warnings.
- `#/course/<id>/lesson/<lid>` — lesson editor:
  - Fields: id (readonly), module, kind (select), title.
  - `body`: big textarea with live preview (render the mini-markdown: headings, lists,
    **bold**, `code`, $$latex$$ (KaTeX from CDN, same as player), :::def/thm/proof/con/ex/rem
    fences, @def:id / @thm:id chips as clickable chips).
  - defs/theorems/checkpoints/exercises: JSON textareas (one per array) with a "Format"
    button that pretty-prints JSON, plus an "Add blank entry" helper button per section.
    (Structured forms are nice-to-have; JSON textareas are the MVP.)
  - Save button → PUT. Status line "Saved ✓" / error message. Back link to course.

JS style: vanilla, no frameworks, hash routing like player.html. Fetch wrapper that adds
`X-Admin-Token` from `localStorage` when present; a small "Admin token" prompt in the top
bar if the server returns 403 (store in localStorage, editable).

## CLI import tool: scripts/import_course.py

```
python3 scripts/import_course.py <course-package.zip|dir> [--overwrite] [--host http://localhost:8788] [--token TOKEN]
```
Uploads the zip (or zips the dir) to POST /api/admin/import and prints the JSON result
readably (success summary or validation errors). Reuses urllib. English output.

## Acceptance checks

1. `python3 course_server.py 8788` starts; `/` still serves the player; `/admin` serves admin UI.
2. Create course via API → dir + manifest created; appears in `/api/courses`.
3. PUT a lesson with full JSON incl. solution → `GET /api/admin/...` returns it, reader API strips solution.
4. Upload an mp3 via media API → appears in media list; player can fetch `/media/<id>/audio/<file>`.
5. Zip import: build a test package (manifest + 1 lesson + 1 audio) → import → course appears;
   import a broken package → 422 with error list, nothing published.
6. Localhost-only protection: request from non-loopback (simulate by calling handler with
   a fake client address or use `curl --interface` if available) → 403 without token.
7. `scripts/import_course.py` works against the live server.

## Files

- Modify: `course_server.py` (admin routes, protection, import pipeline; keep reader routes intact).
- New: `templates/admin.html`, `scripts/import_course.py`.
- Possibly refactor: expose `validate_courses.py` checks as an importable function
  (e.g. `validate_course(course_dir) -> (errors, warnings)`) WITHOUT changing its CLI behavior.
