# TASK_review_annotations.md — MathFlow Admin: Review / Annotation System

## Context

MathFlow course player + admin webapp exist (`course_server.py` port 8788, `templates/admin.html`
hash-routed dark SPA, `/admin`, protected `/api/admin/*` with `X-Admin-Token` / loopback rules).

The agent (BB) proposes course plans — module directory structures, M5 plans, lesson drafts — as
**review documents**. The owner (ZD) wants to annotate them **in the admin app**: add a comment at
any specific block (paragraph / lesson / module proposal) and mark each item as **do / don't / revise**.
Purpose: feedback is anchored to a precise location so the agent knows exactly what and where.

Deliverable: a Review system —
- new data dir `data/reviews/<slug>.json`
- new admin API under `/api/admin/reviews*`
- new admin UI views (`#/reviews` list, `#/reviews/new`, `#/review/<id>` detail)

Do **NOT** touch `templates/player.html` or reader APIs. Python **stdlib only**. English UI.
Same dark visual language as `admin.html`. **No git commit.**

## Data model

`data/reviews/<slug>.json` (one review document per file):

```jsonc
{
  "id": "m5-plan-v1",            // == slug, matches ^[A-Za-z0-9][A-Za-z0-9._-]*$
  "title": "M5 PRF/GGM — directory structure draft (v1)",
  "kind": "plan",                // "plan" | "lesson-draft" | "course-draft" (free string, suggest enum)
  "status": "open",              // "open" | "done"
  "created_at": "<ISO-8601>",
  "updated_at": "<ISO-8601>",
  "blocks": [
    {
      "id": "b1",                // unique within document
      "title": "Module 5 module split",   // short heading
      "text": "markdown…",                // the proposal content (may contain $$LaTeX$$)
      "decision": null,          // null | "do" | "dont" | "revise"
      "comments": [ { "text": "…", "at": "<ISO-8601>" } ]
    }
  ]
}
```

Notes:
- Agents may also create these files directly on disk (not only via API) — server must tolerate
  documents it did not create (no required extra fields beyond id/blocks; fill sane defaults when
  loading and saving is not needed for direct drops — read-only serving of hand-written files must
  work even if e.g. `created_at` is missing).
- `data/reviews/` is a sibling of `data/courses/` — create the dir on server start if missing.
- `validate_courses.py` and the static-site builder scan `data/courses/` only → unaffected.

## API (all under existing admin protection)

Base `/api/admin/reviews` (protection identical to other `/api/admin/*` routes).

| Method + path | Body | Returns |
|---|---|---|
| GET `/api/admin/reviews` | — | list: `[{id,title,kind,status,updated_at,block_count,decided_count,comment_count}]` |
| POST `/api/admin/reviews` | `{id,title,kind,blocks:[{id,title,text}]}` | 201 full doc |
| GET `/api/admin/reviews/<id>` | — | full doc |
| DELETE `/api/admin/reviews/<id>` | — | 200 |
| PUT `/api/admin/reviews/<id>` | `{status?:"open"\|"done", title?}` | 200 updated doc |
| POST `/api/admin/reviews/<id>/blocks/<bid>/comments` | `{text}` | 200 updated block |
| PUT `/api/admin/reviews/<id>/blocks/<bid>/decision` | `{decision:"do"\|"dont"\|"revise"\|null}` | 200 updated block |

Error semantics:
- unknown review → 404; unknown block → 404
- invalid JSON / missing text / invalid decision value → 400
- duplicate review id on create → 409
- list order: newest `updated_at` first.
- A comment on an unknown review/block → 404. Empty comment text → 400.
- `PUT decision` with `null` clears the decision (allowed).
- Setting `status:"done"` on a doc with unresolved (null-decision) blocks is allowed (owner's call).

Write files atomically (write temp file in same dir + `os.replace`) to avoid corruption.

## Frontend (templates/admin.html)

Reuse existing pieces: `api()` wrapper (auto `X-Admin-Token`), `$`, `renderMath`/KaTeX,
`mdToHtml` (already handles markdown + `$$` + chips), CSS vars, `.card/.btn/.badge` etc.
Keep existing views and router structure intact; **append** new routes/views.

1. **Topbar**: add link `Reviews` → `#/reviews` (near "New Course").
2. **`#/reviews`** — list view:
   - cards: title, kind badge, status badge, updated_at, progress "decided x/y blocks".
   - buttons: Open (`#/review/<id>`), Delete (confirm dialog).
   - top action: "New Review" → `#/reviews/new`.
3. **`#/reviews/new`** — create form: `id`, `title`, `kind` (text or select with the 3 suggested
   values), and a `blocks` JSON textarea (array of `{id,title,text}`) + "Format" button that
   pretty-prints (mirror existing JSON textarea pattern). On success → `#/review/<id>`.
4. **`#/review/<id>`** — detail view:
   - header: title, kind badge, status badge, updated_at; buttons: "Mark done"/"Reopen"
     (toggle `status`), Delete (confirm), "← Back".
   - "done" banner when `status == "done"`.
   - blocks rendered one after another, each a `.card`:
     - `title` (bold heading).
     - `text` rendered via `mdToHtml` (KaTeX auto-render afterwards).
     - **Decision control**: three toggle buttons — `✅ Do` / `❌ Don't` / `✏️ Revise` —
       current value highlighted (e.g. `.btn.active` style), clicking the active one clears
       (decision → null). Writes via the decision PUT.
     - **Comments thread**: existing comments listed (text + time), a text input + "Add"
       button appends via the comments POST; after POST re-render that block.
   - Decide/reopen/comment actions re-render only the affected block (or the whole view — simpler
     is fine) and update the list counts on return.

Router: add cases for the three new hashes; unknown review id → friendly error card.

## Constraints

- Python 3.9+, stdlib only. Modify `course_server.py` and `templates/admin.html` only.
- Reuse existing constants/helpers (`SAFE_ID_RE`, `_is_loopback`, `_send_json`, `_read_json`,
  `_admin_allowed`, admin token handling) — do not duplicate logic.
- Keep reader routes and existing admin routes byte-identical in behavior.
- English UI strings/comments only. No git commit.

## Verification (the human/agent will run — do it yourself where possible before reporting)

1. `python3 -m py_compile course_server.py`.
2. JS syntax: extract the `<script>` content of `templates/admin.html` to a temp file and run
   `node --check` if `node` exists.
3. Restart server cleanly: `pkill -f course_server.py; sleep 1; python3 course_server.py &`.
4. `curl localhost:8788/admin` → 200; `curl localhost:8788/api/courses` → unchanged 200.
5. API happy path with curl:
   - POST create a review (2 blocks) → 201; file exists under `data/reviews/`.
   - GET list → 1 entry with `block_count: 2`.
   - POST comment on block b1 → 200; GET full → comment present.
   - PUT decision `"do"` on b1, `"dont"` on b2 → 200; GET shows decisions; list shows `decided_count: 2`.
   - PUT status `"done"` → 200.
6. API errors: duplicate id → 409; bad decision value → 400; unknown review → 404;
   unknown block → 404; empty comment → 400.
7. Direct-file tolerance: drop a minimal hand-written `data/reviews/direct-test.json`
   (id + blocks only, no timestamps) → GET `/api/admin/reviews/direct-test` serves it; DELETE it after.

## Files

- Modify: `course_server.py` (REVIEWS_DIR + admin review routes)
- Modify: `templates/admin.html` (topbar link, list/new/detail views, router cases)
