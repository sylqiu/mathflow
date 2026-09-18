# TASK: Review anchoring (P2) — reviews that point at real lesson content

Goal: make review blocks **anchored to real lesson content** so the agent that
consumes them knows *where* each note lives and *whether the content moved since
the note was written*. Add a one-click "Review this lesson" flow that snapshots
the lesson, jump links both ways, and a drift indicator.

This is **P2 only** from `docs/DESIGN_p1p2_editor_review.md`. Do NOT implement P1
(card-based structured lesson editor). Do NOT implement P3 (apply/resolve) or P4
(draft/publish/diff).

Project rules (unchanged):
- Python 3.9+, **stdlib only**.
- English UI strings and code comments only.
- Do **NOT** touch `templates/player.html`, reader (non-admin) APIs, or
  `lesson.schema.json`.
- No git commit.
- Reuse existing helpers; do not duplicate logic. Do not break existing
  unanchored reviews (they must keep working exactly as today).

Files to edit:
- `course_server.py`
- `templates/admin.html`

---

## 0. Definitions

**Anchor** — identifies a piece of a lesson:
```jsonc
{ "section": "defs" | "theorems" | "checkpoints" | "exercises" | "body",
  "item": "<def/theorem/exercise id | checkpoint qid | body section index 'h1','h2',…>",
  "hash": "<sha256 hex of the canonical snippet at capture time>" }   // optional
```

**Target** — which lesson a review is about:
```jsonc
{ "course": "<course-id>", "lesson": "<lesson-id>" }
```

**Canonical snippet** — the exact text a block stands for, computed by ONE
shared function so capture and drift-check always agree (see §1).

---

## 1. Server — snippet + anchor helpers (`course_server.py`)

Add near the review helpers (after `_now_iso`, before `_review_path`):

### 1.1 `_split_body_sections(body)`
Return an ordered list of `(title, text)` for markdown body sections.
- A section starts at a line matching `^## ` or `^### `.
- `title` = heading text without the leading `#`/`###` and trimmed.
- `text` = the lines after the heading up to (not including) the next heading.
- Content before the first heading is ignored.
- Deterministic: same input → same list order. Body section index for anchors
  is `"h1"`, `"h2"`, … (1-based, in document order).

### 1.2 `_lesson_snippet(lesson, anchor) -> str | None`
Return the canonical snippet for an anchor, or `None` if it does not resolve.
`item` matching uses the same `SAFE_ID_RE` id comparison the rest of the server uses.
- `section == "defs"`: find `defs[]` where `id == item` → return `statement`.
- `section == "theorems"`: find `theorems[]` where `id == item` → return
  `statement`, and if `proof` is non-empty append `"\n\n" + proof`.
- `section == "exercises"`: find `exercises[]` where `id == item` → return
  `prompt` (append `"\n\n" + hint` if `hint` is non-empty).
- `section == "checkpoints"`: find `checkpoints[]` where `qid == item` →
  return `question` plus a markdown list of the options, **without marking which
  option is correct** (reviewer must judge the question on its own). Number the
  options `1.`, `2.`, … in stored order.
- `section == "body"`: `int(item.lstrip("h"))` is a 1-based index into
  `_split_body_sections(lesson["body"])` → return that section's `text`.
- Any other section, missing item, or bad index → `None`.

### 1.3 `_snippet_hash(text) -> str`
`hashlib.sha256(text.encode("utf-8")).hexdigest()`. Import `hashlib` if absent.

### 1.4 `_review_anchor_status(block, lesson) -> str`
Return one of `"unanchored"`, `"fresh"`, `"stale"`, `"missing"`:
- No `anchor` (or no resolvable shape) → `"unanchored"`.
- `lesson` is `None` (target lesson unreadable/absent) → `"missing"`.
- `_lesson_snippet(...)` returns `None` → `"missing"`.
- Stored `anchor.hash` present and equals `_snippet_hash(current)` → `"fresh"`.
- Stored `anchor.hash` present and differs → `"stale"`.
- `anchor.hash` absent → `"fresh"` if the snippet resolves, else `"missing"`
  (no hash ⇒ cannot judge drift, so do not claim stale).

---

## 2. Server — data model passthrough

### 2.1 `_normalize_review` (existing function)
Add tolerant passthrough (keep every existing field and behavior byte-compatible):
- Top level: optional `target`. Accept only a dict with string `course` and
  `lesson`; otherwise omit the key entirely (do not emit `null` when absent, so
  old files and new unanchored reviews stay identical).
- Per block: optional `anchor`. Accept only a dict with string `section` and
  `item`, `section` in the allowed set; copy `hash` when it is a string.
  Otherwise omit `anchor` entirely for that block.
- Unknown extra fields are still ignored, as today.

### 2.2 `_review_summary` (existing function)
Add `"target"` to the summary when present (same optional-omit rule), so the
lesson page can group reviews. Do not change the existing keys.

### 2.3 `_review_block` / decision / comments routes
Unchanged in logic; they must round-trip `anchor` and `target` untouched.

---

## 3. Server — API changes

All under the existing `/api/admin/*` protection (token / loopback). Reuse
`_send_json`, `_read_json`, `_load_lesson`, `_write_json_atomic`, `SAFE_ID_RE`.

### 3.1 `POST /api/admin/reviews` (existing route)
- Accept optional `target`. If present: validate `course` and `lesson` both match
  `SAFE_ID_RE`, then confirm the lesson exists via `_load_lesson(course, lesson)`.
  Failure → `400` with `{"error": "unknown target lesson"}`. (Keep the existing
  `409` duplicate-id and `400` invalid-JSON behavior exactly.)
- Accept optional `anchor` per block, validated as in §2.1. Invalid shape → `400`.
- Persist via the existing atomic write. No `.bak` on first create (unchanged).

### 3.2 `GET /api/admin/reviews/<id>` (existing route)
When the document has a `target`, load the target lesson once and attach a
**computed-at-read** status to each block in the response:
```jsonc
{ "id": "b1", "title": "…", "text": "…", "decision": null, "comments": [],
  "anchor": { "section": "defs", "item": "random", "hash": "…" },
  "anchor_status": "fresh" }   // one of unanchored|fresh|stale|missing
```
- Unanchored blocks get `"anchor_status": "unanchored"`.
- Reviews with no `target`: every block is `"unanchored"`.
- This is read-only — never write the computed status back to disk.
- Do not change `PUT`, `DELETE`, comments, or decision route behavior.

### 3.3 New: `POST /api/admin/courses/<cid>/lessons/<lid>/review-draft`
Returns a **non-persisted** draft review built from the lesson, so the admin form
can show it for editing before Create. No body required.

Response `200`:
```jsonc
{
  "title": "Review: <lesson title>",
  "kind": "lesson-draft",
  "target": { "course": "<cid>", "lesson": "<lid>" },
  "blocks": [ { "id": "b1", "title": "…", "text": "…",
                "anchor": { "section": "defs", "item": "random", "hash": "…" } } ]
}
```
Generation rules (**snapshot only — never modify the lesson**):
- Order: body sections first (document order), then `defs`, `theorems`,
  `checkpoints`, `exercises`.
- body → one block per `_split_body_sections` entry:
  `title` = section title, `text` = section text, anchor
  `{section:"body", item:"h1"|"h2"|…}`, hash of that text.
- defs → one block per entry: `title` = `"def: " + name`, `text` = `statement`,
  anchor `{section:"defs", item:<id>}`, hash of `statement`.
- theorems → `title` = `"thm: " + name`, `text` = `statement` (+ `"\n\n" + proof`
  when non-empty), anchor `{section:"theorems", item:<id>}`.
- checkpoints → `title` = `"cp: " + first 60 chars of question`,
  `text` = question + numbered options (**do not mark the correct option**),
  anchor `{section:"checkpoints", item:<qid>}`.
- exercises → `title` = `"ex: " + first 60 chars of prompt`,
  `text` = `prompt` (+ `"\n\n" + hint` when non-empty),
  anchor `{section:"exercises", item:<id>}`.
- Empty sections are skipped. Block ids are `b1`, `b2`, … in emission order.
- Unknown lesson → `404` `{"error": "unknown lesson"}`.
- Never write to `data/reviews/` from this route. Reviews still only appear on disk
  via the existing Create POST.

### 3.4 New: `GET /api/admin/courses/<cid>/lessons/<lid>/reviews`
Return the summaries of reviews whose `target` matches, newest `updated_at`
first, using `_review_summary` (so shape matches the list endpoint).
- No matches → `200` with `[]`.
- Unknown lesson → `404`.

---

## 4. Frontend — `templates/admin.html`

Reuse `api()`, `postJson()`, `putJson()`, `mdToHtml()`, `renderMath()`, existing
CSS classes (`.card`, `.btn`, `.badge`, `.row`, `.dim`, `.back`), and the existing
hash router. **Append/upgrade only** — keep all current views and routes working.

### 4.1 Lesson page (`renderLesson`)
- Add a `[Review this lesson]` button to the lesson header →
  `location.hash = '#/reviews/new?from=' + encodeURIComponent(courseId) + '/' + encodeURIComponent(lid)`.
- Add a **Reviews row** under the title: call the §3.4 endpoint. If non-empty,
  render `N open review(s)` followed by one chip per review
  (`title (kind) · decided a/b`) linking to `#/review/<id>`. Render nothing when
  the list is empty. Failure to fetch must not break lesson rendering.

### 4.2 New review form (`#/reviews/new`, existing view)
- Parse an optional `from=<course>/<lesson>` query param out of the hash.
- When present, `POST` to the §3.3 review-draft endpoint on mount and prefill
  title / kind / target, then render the returned blocks **rendered** (via
  `mdToHtml` + `renderMath`, one card per block, editable text) instead of raw
  JSON. Keep the existing manual-blocks textarea path for the no-`from` case.
- Preserve the existing Create behavior; the POST body now also carries
  `target` and per-block `anchor` when the draft flow was used.
- Add a live KaTeX preview (debounce ~300 ms) under the blocks editor for both
  the draft and manual paths — same render chain as the lesson body preview.

### 4.3 Review detail (`renderReview`)
- Header sub-line when `target` exists: `Lesson: <course>/<lid>` plus an
  `[Open lesson ↗]` link to `#/course/<cid>/lesson/<lid>`.
- Per block with an `anchor`: show a section badge
  (`defs` / `thm` / `cp` / `ex` / `body`), an `[jump]` link to
  `#/course/<cid>/lesson/<lid>@<section>:<item>`, and a drift marker from
  `anchor_status`: `fresh` → no marker, `stale` → `⚠ lesson changed since this
  review was captured`, `missing` → `⚠ anchor no longer resolves`.
- Existing decision buttons, comments thread, status toggle, and delete are
  unchanged.

### 4.4 Deep link `#/course/<cid>/lesson/<lid>@<section>:<item>`
- Extend the lesson route to accept the optional `@<section>:<item>` suffix.
- After the lesson renders, scroll the matching section into view and highlight
  it for ~2 s. In card mode, expand the matching entry where applicable;
  otherwise scrolling is enough. Unknown suffix → just render the lesson
  normally, no error.

---

## 5. Constraints

- Only `course_server.py` and `templates/admin.html` change.
- Deletes keep going to `data/.trash`; saves keep `.bak` behavior; writes stay
  atomic (`_write_json_atomic`).
- Old review files (no `target`, no `anchor`) load, list, serve, decide and
  comment exactly as before.
- `validate_courses.py` and the static-site builder scan `data/courses/` only —
  must stay unaffected.

---

## 6. Verification (run these yourself before reporting)

1. `python3 -m py_compile course_server.py`
2. Extract the `<script>` from `templates/admin.html` to a temp file and run
   `node --check` (node is available).
3. Restart cleanly: `pkill -f course_server.py; sleep 1; python3 course_server.py 8788 &`
4. `curl -s -o /dev/null -w '%{http_code}' localhost:8788/admin` → 200;
   `curl -s localhost:8788/api/courses` unchanged 200.
5. Backward compatibility: create a review with **no** target/anchor →
   `GET /api/admin/reviews/<id>` still returns the same document shape plus
   `anchor_status: "unanchored"`; decision + comment + delete still work.
6. Draft endpoint: `POST /api/admin/courses/pseudorandomness-primer/lessons/m1-three-theories/review-draft`
   → 200; block count equals body sections + defs + theorems + checkpoints +
   exercises for that lesson; every block has `anchor` with a `hash`; no file was
   written under `data/reviews/`.
7. Create with target+anchor from the draft → 201; `GET` shows
   `anchor_status: "fresh"` for every block.
8. Drift: edit the target lesson's `body` (then restore it) → `GET` the review
   shows `stale` for the affected body block and `fresh` for untouched ones.
   Restore the lesson and confirm it returns to `fresh`.
9. Lesson→reviews: `GET /api/admin/courses/<cid>/lessons/<lid>/reviews` → the new
   review; a lesson with none → `[]`.
10. Errors: draft/create for an unknown lesson or unknown course → 404/400 as
    specified; invalid `anchor.section` → 400; duplicate review id → 409.
11. `python3 validate_courses.py` → still ALL OK.
12. Clean up test reviews from `data/reviews/` (move to `data/.trash`, do not
    leave test artifacts in place) and leave the server running.

Report: files changed, the exact commands you ran, and their observed results.
