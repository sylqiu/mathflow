# TASK: Admin delete safety + auto .bak (lightweight, no history UI)

Goal: make the MathFlow admin API non-destructive in practice and add missing
frontend confirmations. NO revision/history UI, NO restore API. Keep project
style: Python 3.9 stdlib only, English UI only, no git commits, do NOT touch
`templates/player.html`, do NOT change the reader (non-admin) API behavior.

Files to edit:
- `course_server.py`
- `templates/admin.html`

## Server changes (course_server.py)

### 1. Trash directory helper
- Add `TRASH_DIR = BASE_DIR / "data" / ".trash"` next to `COURSES_DIR`.
- Add helper `_trash_path(name: str) -> Path`:
  - `TRASH_DIR.mkdir(parents=True, exist_ok=True)` on each call.
  - If `TRASH_DIR / name` already exists, append `-2`, `-3`, ... until free
    (protect against same-second deletes).
- Timestamp string helper: reuse `datetime`; format
  `datetime.datetime.now().strftime("%Y%m%d-%H%M%S")` (imports already include
  `datetime`). Use it inside delete handlers to build names like
  `<ts>__lesson__<cid>__<lid>.json`.

### 2. Replace hard deletes with moves to trash
All four DELETE endpoints currently `rmtree`/`unlink`. Change them to move the
file/dir into `TRASH_DIR` with `shutil.move` (same volume → cheap). Keep the
exact same JSON responses the frontend already consumes
(`{"ok": true, "deleted": ...}`).

- `DELETE /api/admin/courses/<id>` (in `_route_admin_delete`): instead of
  `shutil.rmtree(target)`, move the whole course dir:
  `shutil.move(str(target), str(_trash_path(f"{ts}__course__{cid}")))`.
- `DELETE /api/admin/courses/<id>/lessons/<lid>`: instead of `unlink()`, move
  the lesson json to `_trash_path(f"{ts}__lesson__{cid}__{lid}.json")`.
- `DELETE /api/admin/courses/<id>/media/<kind>/<filename>`: instead of
  `unlink()`, move the file to `_trash_path(f"{ts}__media__{cid}__{kind}__{fname}")`.
- `DELETE /api/admin/reviews/<id>`: instead of `unlink()`, move the review json
  to `_trash_path(f"{ts}__review__{rid}.json")`.
- Also `_publish_import(...)` with `overwrite=True` currently does
  `shutil.rmtree(target)` to replace an existing course. Change it to move the
  old course dir to trash first:
  `shutil.move(str(target), str(_trash_path(f"{ts}__course__{course_id}")))`
  (compute `ts` inside the function; then proceed with the move of the new
  package as today).

### 3. Auto `.bak` before overwriting existing JSON files
Add helper:
```python
def _backup_if_exists(path: Path) -> None:
    """Copy <path> to <path>.bak if it exists (single rolling backup)."""
    if path.is_file():
        shutil.copy2(path, str(path) + ".bak")
```
Call it right before each of these write sites so the previous version is
always recoverable as `*.json.bak`:

- `PUT /api/admin/courses/<id>/manifest` → `_backup_if_exists(manifest_path)`.
- `PUT /api/admin/courses/<id>/lessons/<lid>` →
  `_backup_if_exists(lessons_path)`.
- `POST /api/admin/courses/<id>/lessons` (skeleton create): the current code
  silently overwrites an existing lesson file if the id already exists — back
  it up first (`_backup_if_exists`) so nothing is silently clobbered.
- Review updates go through `_write_json_atomic(_review_path(rid), doc)` in
  three handlers: `PUT /api/admin/reviews/<id>` (doc update),
  `POST /api/admin/reviews/<id>/blocks/<bid>/comments`,
  `PUT /api/admin/reviews/<id>/blocks/<bid>/decision`.
  Add a keyword arg `backup: bool = False` to `_write_json_atomic` that calls
  `_backup_if_exists(path)` before writing when `backup=True`. Pass
  `backup=True` at those three review-update call sites. Do NOT pass it at the
  review-create call site (file doesn't exist yet anyway — harmless either way,
  but keep it explicit).
- `.bak` files must never be picked up by listings: lesson listing globs
  `lessons/*.json` (a `.json.bak` suffix does not match `*.json` ✓), media
  listing lists raw dir entries for media dirs only (we never `.bak` media —
  see below), course listing globs `*/manifest.json` ✓, review listing globs
  `*.json` in REVIEWS_DIR — a `<rid>.json.bak` does not match `*.json` ✓.
  Verify no other code path scans these dirs for `*.json` in a way that would
  see `.bak` files.

### 4. Media overwrite → trash the old file
`POST /api/admin/courses/<id>/media` currently overwrites a same-named file
silently (`(d / safe).write_bytes(content)`). Before writing, if
`(d / safe).is_file()`, move the existing file to
`_trash_path(f"{ts}__media__{cid}__{kind}__{safe}")` first. Do NOT create
`.bak` files inside media dirs (they would appear in the media listing UI).

## Frontend changes (templates/admin.html)

Keep the same dark-theme SPA style, English text only. Native `confirm` /
`prompt` dialogs are fine (already used in this file).

1. **Course delete → type-to-confirm** (two places call `del-course`: the
   course-list card and the course editor). Replace the plain `confirm(...)`
   with a `prompt` asking the user to type the course id:
   - Message like:
     `'Delete course "<id>"? It will be moved to the server trash. Type the course id to confirm:'`
   - If the returned string does not exactly equal the id → do nothing (and if
     the user typed a non-empty wrong value, `alert` a mismatch message).
2. **`rm-module`**: add a `confirm(...)` before splicing the module out of the
   in-memory manifest, e.g.
   `'Remove module "<title>" from the manifest? Its lessons will no longer be listed. (Click Save manifest to apply.)'`
   Use the module's title when available, else its id.
3. **`rm-lesson`** (Remove from manifest): add `confirm(...)`, e.g.
   `'Remove lesson "<lid>" from the manifest? The lesson file itself is kept. (Click Save manifest to apply.)'`
4. **Media overwrite prompt** in `upload-media`: before POSTing, check the
   chosen filename against the currently listed media for the selected kind.
   Simplest robust way: `renderMediaTab` already fetches the media list — store
   it on `state.mediaList = list` when rendered (audio + videos arrays), and in
   `upload-media` check `(list.audio.includes(name) || list.videos.includes(name))`.
   If it exists → `confirm('File "<name>" already exists in <kind>. Overwrite it? The old file is moved to the server trash.')`;
   abort upload if cancelled.
5. Update remaining delete-confirm strings so they no longer claim permanent
   erasure; mention the server trash instead:
   - `del-course` (both places) → see #1.
   - `del-lesson` / `del-lesson-file` →
     `'Delete lesson "<lid>"? The file is moved to the server trash.'`
   - `del-media` → `'Delete media file "<file>"? It is moved to the server trash.'`
   - `del-review` / `del-review-item` →
     `'Delete review "<title-or-id>"? It is moved to the server trash.'`

## Verification (do this yourself before finishing)
- `python3 -m py_compile course_server.py` passes.
- Re-read your diff: no reader-facing endpoints changed, no `player.html`
  touched, no git operations, trash moves preserve the previous JSON response
  shapes.
- Sanity-scan that `.trash` and `*.bak` can never be listed as courses,
  lessons, media, or reviews (check every `glob`/`iterdir` that reads those
  data dirs).
- Do NOT restart any running server and do NOT touch `data/` contents.

Report back with: summary of edits per file, py_compile result, and anything
you deliberately chose differently.
