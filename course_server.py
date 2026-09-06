#!/usr/bin/env python3
"""
MathFlow Course Server — course API + single-page course player (stdlib only).
===============================================================================
Course Mode: serves courses stored under data/courses/<course-id>/
(manifest.json + lessons/*.json) through a JSON API and renders them in a
hash-routed single-page player (dark theme, KaTeX math, no build step). Also
serves an admin SPA (/admin) plus protected /api/admin/* endpoints for course
creation, lesson editing (full JSON incl. solutions), media upload, validation
and zip package import/publish.

API:
  GET  /api/courses                                      -> course index with modules/lessons
  GET  /api/courses/<id>/lessons/<lid>                   -> lesson JSON (exercise solutions stripped)
  GET  /api/courses/<id>/lessons/<lid>/solutions         -> {"exercises": [{"id", "solution"}]}
  POST /api/courses/<id>/checkpoint  {"qid", "option_index"} -> {"correct", "explanation"}
  GET  /media/<course_id>/<path>                         -> static file from data/courses/<course_id>/media/
  GET  /                                                 -> single-page player HTML
  GET  /admin                                            -> admin SPA HTML
  GET  /api/admin/courses                                -> admin course list with validate counts
  POST /api/admin/courses                                -> create course {id, title, subtitle, source_url}
  DELETE /api/admin/courses/<id>                         -> delete course
  GET/PUT /api/admin/courses/<id>/manifest               -> read/replace manifest
  GET /api/admin/courses/<id>/validate                   -> run validate_courses checks
  GET/PUT/DELETE /api/admin/courses/<id>/lessons/<lid>   -> full lesson JSON (admin sees solutions)
  POST /api/admin/courses/<id>/lessons                   -> create lesson skeleton
  POST/GET/DELETE /api/admin/courses/<id>/media          -> upload / list / delete media files
  POST /api/admin/import                                 -> zip course package -> validate -> publish
  GET/POST /api/admin/reviews                            -> list/create review documents
  GET/PUT/DELETE /api/admin/reviews/<id>                 -> read/update/delete a review document
  POST /api/admin/reviews/<id>/blocks/<bid>/comments     -> add a comment anchored to a block
  PUT /api/admin/reviews/<id>/blocks/<bid>/decision      -> set/clear a block decision

Run:
  python3 course_server.py 8788
Stdlib only (Python 3.9+). English only. No git commits.
"""

import datetime
import hmac
import io
import json
import mimetypes
import os
import re
import shutil
import sys
import tempfile
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent
COURSES_DIR = BASE_DIR / "data" / "courses"
REVIEWS_DIR = BASE_DIR / "data" / "reviews"
TRASH_DIR = BASE_DIR / "data" / ".trash"
DEFAULT_PORT = 8788
MAX_BODY = 1 << 20  # 1 MiB request bodies
MAX_UPLOAD = 200 << 20  # 200 MiB media / package uploads
MAX_FILENAME = 200
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
KIND_RE = re.compile(r"^[A-Za-z0-9._-]+$")
REVIEW_KINDS = ("plan", "lesson-draft", "course-draft")
REVIEW_DECISIONS = ("do", "dont", "revise")
ADMIN_TOKEN = os.environ.get("MATHFLOW_ADMIN_TOKEN") or None

sys.path.insert(0, str(BASE_DIR))
import validate_courses  # noqa: E402  (reused for structural validation)


def _parse_port():
    if len(sys.argv) > 1:
        try:
            return int(sys.argv[1])
        except ValueError:
            print(f"Invalid port: {sys.argv[1]}, using default {DEFAULT_PORT}")
    return DEFAULT_PORT


PORT = _parse_port()


def _load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _course_dirs():
    if not COURSES_DIR.is_dir():
        return []
    return sorted(p.parent for p in COURSES_DIR.glob("*/manifest.json"))


def _trash_path(name: str) -> Path:
    """Return a free path under data/.trash, mkdir'd on each call."""
    TRASH_DIR.mkdir(parents=True, exist_ok=True)
    target = TRASH_DIR / name
    n = 2
    while target.exists():
        target = TRASH_DIR / f"{name}-{n}"
        n += 1
    return target


def _backup_if_exists(path: Path) -> None:
    """Copy <path> to <path>.bak if it exists (single rolling backup)."""
    if path.is_file():
        shutil.copy2(path, str(path) + ".bak")


def _course_manifest(course_id):
    if not SAFE_ID_RE.match(course_id or ""):
        return None
    return _load_json(COURSES_DIR / course_id / "manifest.json")


def _load_lesson(course_id, lesson_id):
    if not SAFE_ID_RE.match(course_id or "") or not SAFE_ID_RE.match(lesson_id or ""):
        return None
    return _load_json(COURSES_DIR / course_id / "lessons" / f"{lesson_id}.json")


def _course_index():
    """[{id, title, subtitle, source_url, modules: [{id, title, lessons: [{id, title, kind}]}]}]"""
    index = []
    for d in _course_dirs():
        manifest = _load_json(d / "manifest.json")
        if not isinstance(manifest, dict) or not manifest.get("id"):
            continue
        course = {
            "id": manifest["id"],
            "title": manifest.get("title", ""),
            "subtitle": manifest.get("subtitle", ""),
            "source_url": manifest.get("source_url", ""),
            "modules": [],
        }
        for mod in manifest.get("modules") or []:
            if not isinstance(mod, dict):
                continue
            lessons = []
            for lesson_ref in mod.get("lessons") or []:
                lid = lesson_ref.get("id") if isinstance(lesson_ref, dict) else lesson_ref
                lesson = _load_lesson(course["id"], lid)
                if lesson is None:
                    continue
                lessons.append({
                    "id": lid,
                    "title": lesson.get("title", lid),
                    "kind": lesson.get("kind", "theory"),
                })
            course["modules"].append({
                "id": mod.get("id", ""),
                "title": mod.get("title", ""),
                "lessons": lessons,
            })
        index.append(course)
    return index


def _all_lessons(course_id):
    manifest = _course_manifest(course_id)
    if not isinstance(manifest, dict):
        return []
    lessons = []
    for mod in manifest.get("modules") or []:
        if not isinstance(mod, dict):
            continue
        for lesson_ref in mod.get("lessons") or []:
            lid = lesson_ref.get("id") if isinstance(lesson_ref, dict) else lesson_ref
            if not lid:
                continue
            lesson = _load_lesson(course_id, lid)
            if lesson is not None:
                lessons.append((lid, lesson))
    return lessons


def _find_checkpoint(course_id, qid):
    for _, lesson in _all_lessons(course_id):
        for cp in lesson.get("checkpoints") or []:
            if cp.get("qid") == qid:
                return cp
    return None


def _lesson_public(lesson):
    """Full lesson JSON with exercises[].solution replaced by a has_solution marker."""
    out = json.loads(json.dumps(lesson))
    exercises = []
    for ex in out.get("exercises") or []:
        ex = dict(ex)
        has_solution = bool(ex.get("solution"))
        ex.pop("solution", None)
        ex["has_solution"] = has_solution
        exercises.append(ex)
    out["exercises"] = exercises
    return out


def _lesson_audio_file(course_id, lesson_id):
    """Return "<lesson_id>.mp3" when the lesson's podcast mp3 exists on disk, else None."""
    if not SAFE_ID_RE.match(course_id or "") or not SAFE_ID_RE.match(lesson_id or ""):
        return None
    mp3 = COURSES_DIR / course_id / "media" / "audio" / f"{lesson_id}.mp3"
    if mp3.is_file():
        return f"{lesson_id}.mp3"
    return None


def _lesson_solutions(lesson):
    exercises = [
        {"id": ex.get("id"), "solution": ex.get("solution", "")}
        for ex in lesson.get("exercises") or []
        if ex.get("solution")
    ]
    return {"exercises": exercises}


def _is_loopback(addr):
    if not addr:
        return False
    host = addr[0] if isinstance(addr, (tuple, list)) else addr
    return host in ("127.0.0.1", "::1", "localhost")


def _sanitize_filename(name):
    """Keep only [A-Za-z0-9._-], collapse to a safe basename."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name or "")
    cleaned = cleaned.strip("._-")
    if not cleaned:
        return None
    return cleaned[:MAX_FILENAME]


def _parse_multipart(body, ctype):
    """Minimal multipart/form-data parser -> (fields: dict, files: {name: (filename, data)})."""
    fields, files = {}, {}
    if not body or "boundary=" not in ctype:
        return fields, files
    boundary = ctype.split("boundary=", 1)[1].split(";", 1)[0].strip().strip('"')
    delim = b"--" + boundary.encode("utf-8")
    parts = body.split(delim)
    for part in parts:
        if part in (b"", b"--", b"\r\n") or part.startswith(b"--"):
            continue
        if b"\r\n\r\n" not in part:
            continue
        raw_head, content = part.split(b"\r\n\r\n", 1)
        if content.endswith(b"\r\n"):
            content = content[:-2]
        head = raw_head.decode("utf-8", "replace")
        disp = None
        for line in head.splitlines():
            if line.lower().startswith("content-disposition:"):
                disp = line
                break
        if not disp:
            continue
        m = re.search(r'name="([^"]*)"', disp)
        fname = re.search(r'filename="([^"]*)"', disp)
        name = m.group(1) if m else ""
        if fname:
            files[name] = (fname.group(1), content)
        else:
            fields[name] = content.decode("utf-8", "replace")
    return fields, files


def _extract_zip_safe(zf, dest):
    """Extract zip entries to dest, rejecting any path escaping dest (zip-slip)."""
    dest = Path(dest).resolve()
    for info in zf.infolist():
        name = info.filename
        target = (dest / name).resolve()
        try:
            target.relative_to(dest)
        except ValueError:
            raise ValueError(f"unsafe zip path: {name}")
        if info.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(info) as src, open(target, "wb") as out:
            shutil.copyfileobj(src, out)


def _admin_course_summary():
    """[{id, title, subtitle, source_url, lesson_count, module_count, validate, updated_at}]"""
    out = []
    for d in _course_dirs():
        manifest = _load_json(d / "manifest.json")
        if not isinstance(manifest, dict) or not manifest.get("id"):
            continue
        modules = [m for m in (manifest.get("modules") or []) if isinstance(m, dict)]
        lesson_count = sum(
            1 for m in modules
            for ref in (m.get("lessons") or [])
            if (ref.get("id") if isinstance(ref, dict) else ref)
        )
        errors, warnings = validate_courses.validate_course(d, course_id=manifest["id"])
        updated_at = ""
        mtime = d / "manifest.json"
        try:
            updated_at = str(int(mtime.stat().st_mtime))
        except OSError:
            pass
        out.append({
            "id": manifest["id"],
            "title": manifest.get("title", ""),
            "subtitle": manifest.get("subtitle", ""),
            "source_url": manifest.get("source_url", ""),
            "lesson_count": lesson_count,
            "module_count": len(modules),
            "validate": {"errors": len(errors), "warnings": len(warnings)},
            "updated_at": updated_at,
        })
    return out


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _review_path(review_id):
    if not SAFE_ID_RE.match(review_id or ""):
        return None
    return REVIEWS_DIR / f"{review_id}.json"


def _review_ids():
    if not REVIEWS_DIR.is_dir():
        return []
    return sorted(p.stem for p in REVIEWS_DIR.glob("*.json"))


def _write_json_atomic(path, obj, backup=False):
    """Write JSON to a temp file in the same dir, then atomically replace."""
    if backup:
        _backup_if_exists(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".review-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _normalize_review(raw):
    """Fill sane defaults so hand-written files (no timestamps etc.) serve fine."""
    if not isinstance(raw, dict):
        return None
    rid = raw.get("id")
    if not isinstance(rid, str) or not SAFE_ID_RE.match(rid):
        return None
    now = _now_iso()
    title = raw.get("title")
    kind = raw.get("kind")
    status = raw.get("status")
    blocks = []
    raw_blocks = raw.get("blocks")
    if isinstance(raw_blocks, list):
        for b in raw_blocks:
            if not isinstance(b, dict):
                continue
            bid = b.get("id")
            comments = b.get("comments")
            comments = [c for c in comments if isinstance(c, dict)] if isinstance(comments, list) else []
            blocks.append({
                "id": bid if isinstance(bid, str) else "",
                "title": b.get("title") if isinstance(b.get("title"), str) else "",
                "text": b.get("text") if isinstance(b.get("text"), str) else "",
                "decision": b.get("decision") if b.get("decision") in REVIEW_DECISIONS else None,
                "comments": comments,
            })
    return {
        "id": rid,
        "title": title if isinstance(title, str) else "",
        "kind": kind if isinstance(kind, str) and kind else "plan",
        "status": status if status in ("open", "done") else "open",
        "created_at": raw.get("created_at") if isinstance(raw.get("created_at"), str) else now,
        "updated_at": raw.get("updated_at") if isinstance(raw.get("updated_at"), str) else now,
        "blocks": blocks,
    }


def _load_review(review_id):
    path = _review_path(review_id)
    if path is None or not path.is_file():
        return None
    return _normalize_review(_load_json(path))


def _review_summary(doc):
    blocks = doc.get("blocks") or []
    decided = sum(1 for b in blocks if b.get("decision") in REVIEW_DECISIONS)
    comment_count = sum(len(b.get("comments") or []) for b in blocks)
    return {
        "id": doc.get("id", ""),
        "title": doc.get("title", ""),
        "kind": doc.get("kind", ""),
        "status": doc.get("status", "open"),
        "updated_at": doc.get("updated_at", ""),
        "block_count": len(blocks),
        "decided_count": decided,
        "comment_count": comment_count,
    }


def _review_list():
    """Newest updated_at first."""
    out = [_review_summary(doc) for rid in _review_ids() if (doc := _load_review(rid)) is not None]
    out.sort(key=lambda r: r["updated_at"], reverse=True)
    return out


def _review_block(doc, block_id):
    for b in doc.get("blocks") or []:
        if b.get("id") == block_id:
            return b
    return None


def _manifest_check(course_id, manifest):
    """Structural checks for manifest.json. Returns (ok, errors)."""
    errors = []
    if not isinstance(manifest, dict):
        return False, ["manifest must be a JSON object"]
    if manifest.get("id") != course_id:
        errors.append(f"manifest id must stay '{course_id}'")
    if "title" in manifest and not isinstance(manifest.get("title"), str):
        errors.append("manifest title must be a string")
    modules = manifest.get("modules")
    if modules is None:
        modules = []
    if not isinstance(modules, list):
        errors.append("manifest modules must be an array")
        modules = []
    seen = set()
    for mod in modules:
        if not isinstance(mod, dict):
            errors.append("module entries must be objects")
            continue
        for ref in mod.get("lessons") or []:
            lid = ref.get("id") if isinstance(ref, dict) else ref
            if not lid or not isinstance(lid, str):
                errors.append("lesson reference must have an id")
                continue
            if lid in seen:
                errors.append(f"duplicate lesson id across course: {lid}")
            seen.add(lid)
    return not errors, errors


def _lesson_skeleton(lesson_id, module, kind, title):
    return {
        "schema_version": 1,
        "id": lesson_id,
        "module": module,
        "kind": kind,
        "title": title,
        "body": "",
        "defs": [],
        "theorems": [],
        "checkpoints": [],
        "exercises": [],
    }


def _validate_lesson_json(lesson, lesson_id, module_ids):
    """Structural validation of a full lesson JSON. Returns (ok, errors)."""
    errors = []
    if not isinstance(lesson, dict):
        return False, ["lesson must be a JSON object"]
    if lesson.get("id") != lesson_id:
        errors.append(f"lesson id must be '{lesson_id}'")
    if not isinstance(lesson.get("module"), str) or not lesson["module"]:
        errors.append("lesson module must be a non-empty string")
    elif module_ids and lesson["module"] not in module_ids:
        errors.append(f"lesson module '{lesson['module']}' is not in the manifest")
    if lesson.get("kind") not in ("theory", "media", "checkpoint", "mcq", "exercise"):
        errors.append(f"bad kind: {lesson.get('kind')!r}")
    for f in ("title", "body"):
        if not isinstance(lesson.get(f), str):
            errors.append(f"lesson {f} must be a string")
    for f in ("defs", "theorems", "checkpoints", "exercises"):
        if not isinstance(lesson.get(f), list):
            errors.append(f"lesson {f} must be an array")
    if lesson.get("schema_version") not in (None, 1):
        errors.append(f"unsupported schema_version: {lesson.get('schema_version')!r}")
    return not errors, errors


def _media_list(course_id):
    audio, videos = [], []
    root = COURSES_DIR / course_id / "media"
    for sub, bucket in (("audio", audio), ("videos", videos)):
        d = root / sub
        if d.is_dir():
            bucket.extend(sorted(p.name for p in d.iterdir() if p.is_file()))
    return {"audio": audio, "videos": videos}


def _publish_import(tmp_course_dir, course_id, manifest, overwrite):
    """Move a validated package into data/courses/<id>. Returns error string or None."""
    target = COURSES_DIR / course_id
    if target.exists():
        if not overwrite:
            return f"course '{course_id}' already exists (use overwrite=true to replace)"
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.move(str(target), str(_trash_path(f"{ts}__course__{course_id}")))
    COURSES_DIR.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(str(tmp_course_dir), str(target))
    except OSError:
        shutil.copytree(tmp_course_dir, target)
    return None


class Handler(BaseHTTPRequestHandler):
    server_version = "MathFlowCourse/1.0"

    def _send_bytes(self, data, ctype, status=200):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, obj, status=200):
        self._send_bytes(json.dumps(obj).encode("utf-8"), "application/json; charset=utf-8", status)

    def _send_html(self, html, status=200):
        self._send_bytes(html.encode("utf-8"), "text/html; charset=utf-8", status)

    def _read_body(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
        except (TypeError, ValueError):
            length = 0
        if length <= 0 or length > MAX_BODY:
            return b""
        return self.rfile.read(length)

    def _read_body_upto(self, limit):
        try:
            length = int(self.headers.get("Content-Length", 0))
        except (TypeError, ValueError):
            length = 0
        if length <= 0:
            return b""
        if length > limit:
            return None
        return self.rfile.read(length)

    def _read_json_body(self, limit=MAX_BODY):
        raw = self._read_body_upto(limit)
        if raw is None:
            self._send_json({"error": "request body too large"}, 413)
            return None
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except ValueError:
            self._send_json({"error": "invalid JSON body"}, 400)
            return None
        if not isinstance(data, dict):
            self._send_json({"error": "invalid JSON body"}, 400)
            return None
        return data

    def _read_multipart(self):
        raw = self._read_body_upto(MAX_UPLOAD)
        if raw is None:
            self._send_json({"error": "upload too large (max 200 MB)"}, 413)
            return None
        ctype = self.headers.get("Content-Type", "")
        fields, files = _parse_multipart(raw, ctype)
        return fields, files

    def _admin_allowed(self):
        """Protect admin APIs: token env var or loopback-only, token always for non-loopback."""
        if not self.path.startswith("/api/admin/"):
            return True
        loopback = _is_loopback(self.client_address)
        if not loopback:
            token = self.headers.get("X-Admin-Token", "")
            if ADMIN_TOKEN and token and hmac.compare_digest(token, ADMIN_TOKEN):
                return True
            return False
        if ADMIN_TOKEN:
            token = self.headers.get("X-Admin-Token", "")
            return bool(token) and hmac.compare_digest(token, ADMIN_TOKEN)
        return True

    def _route_admin_get(self, path):
        m = re.match(r"^/api/admin/courses$", path)
        if m:
            self._send_json(_admin_course_summary())
            return True
        m = re.match(r"^/api/admin/courses/([^/]+)/validate$", path)
        if m:
            cid = m.group(1)
            if not SAFE_ID_RE.match(cid or ""):
                self._send_json({"error": "bad course id"}, 404)
                return True
            errors, warnings = validate_courses.validate_course(COURSES_DIR / cid, course_id=cid)
            self._send_json({"ok": not errors, "errors": errors, "warnings": warnings})
            return True
        m = re.match(r"^/api/admin/courses/([^/]+)/manifest$", path)
        if m:
            cid = m.group(1)
            manifest = _course_manifest(cid)
            if manifest is None:
                self._send_json({"error": "unknown course"}, 404)
            else:
                self._send_json(manifest)
            return True
        m = re.match(r"^/api/admin/courses/([^/]+)/lessons/([^/]+)$", path)
        if m:
            lesson = _load_lesson(m.group(1), m.group(2))
            if lesson is None:
                self._send_json({"error": "unknown course or lesson"}, 404)
            else:
                self._send_json(lesson)
            return True
        m = re.match(r"^/api/admin/courses/([^/]+)/media$", path)
        if m:
            if not _course_manifest(m.group(1)):
                self._send_json({"error": "unknown course"}, 404)
            else:
                self._send_json(_media_list(m.group(1)))
            return True
        m = re.match(r"^/api/admin/reviews$", path)
        if m:
            self._send_json(_review_list())
            return True
        m = re.match(r"^/api/admin/reviews/([^/]+)$", path)
        if m:
            rid = m.group(1)
            doc = _load_review(rid)
            if doc is None:
                self._send_json({"error": "unknown review"}, 404)
            else:
                self._send_json(doc)
            return True
        return False

    def _route_admin_post_json(self, path, data):
        m = re.match(r"^/api/admin/courses$", path)
        if m:
            cid = data.get("id")
            if not isinstance(cid, str) or not SAFE_ID_RE.match(cid):
                self._send_json({"error": "id must match ^[A-Za-z0-9][A-Za-z0-9._-]*$"}, 400)
                return True
            if _course_manifest(cid):
                self._send_json({"error": f"course '{cid}' already exists"}, 409)
                return True
            title = data.get("title") or ""
            subtitle = data.get("subtitle") or ""
            source_url = data.get("source_url") or ""
            manifest = {"id": cid, "title": title, "subtitle": subtitle, "source_url": source_url, "modules": []}
            for sub in ("lessons", "media/audio", "media/videos"):
                (COURSES_DIR / cid / sub).mkdir(parents=True, exist_ok=True)
            (COURSES_DIR / cid / "manifest.json").write_text(
                json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            self._send_json(manifest, 201)
            return True
        m = re.match(r"^/api/admin/courses/([^/]+)/lessons$", path)
        if m:
            cid = m.group(1)
            if not _course_manifest(cid):
                self._send_json({"error": "unknown course"}, 404)
                return True
            lid, module, kind, title = (data.get(k) for k in ("id", "module", "kind", "title"))
            if not isinstance(lid, str) or not SAFE_ID_RE.match(lid):
                self._send_json({"error": "lesson id must match ^[A-Za-z0-9][A-Za-z0-9._-]*$"}, 400)
                return True
            if kind not in ("theory", "media", "checkpoint", "mcq", "exercise"):
                self._send_json({"error": "kind must be one of theory|media|checkpoint|mcq|exercise"}, 400)
                return True
            if not isinstance(title, str):
                title = lid
            if not isinstance(module, str):
                module = ""
            skeleton = _lesson_skeleton(lid, module, kind, title)
            (COURSES_DIR / cid / "lessons").mkdir(parents=True, exist_ok=True)
            _backup_if_exists(COURSES_DIR / cid / "lessons" / f"{lid}.json")
            (COURSES_DIR / cid / "lessons" / f"{lid}.json").write_text(
                json.dumps(skeleton, indent=2) + "\n", encoding="utf-8")
            self._send_json(skeleton, 201)
            return True
        m = re.match(r"^/api/admin/reviews$", path)
        if m:
            rid = data.get("id")
            if not isinstance(rid, str) or not SAFE_ID_RE.match(rid):
                self._send_json({"error": "id must match ^[A-Za-z0-9][A-Za-z0-9._-]*$"}, 400)
                return True
            if _review_path(rid).is_file():
                self._send_json({"error": f"review '{rid}' already exists"}, 409)
                return True
            title = data.get("title")
            kind = data.get("kind")
            if not isinstance(title, str):
                title = ""
            if not isinstance(kind, str) or not kind:
                kind = "plan"
            raw_blocks = data.get("blocks")
            if not isinstance(raw_blocks, list):
                self._send_json({"error": "blocks must be an array of {id, title, text}"}, 400)
                return True
            blocks, seen = [], set()
            for b in raw_blocks:
                if not isinstance(b, dict):
                    self._send_json({"error": "each block must be an object with id, title, text"}, 400)
                    return True
                bid = b.get("id")
                if not isinstance(bid, str) or not SAFE_ID_RE.match(bid):
                    self._send_json({"error": "block id must match ^[A-Za-z0-9][A-Za-z0-9._-]*$"}, 400)
                    return True
                if bid in seen:
                    self._send_json({"error": f"duplicate block id: {bid}"}, 400)
                    return True
                seen.add(bid)
                btitle = b.get("title")
                btext = b.get("text")
                blocks.append({
                    "id": bid,
                    "title": btitle if isinstance(btitle, str) else "",
                    "text": btext if isinstance(btext, str) else "",
                    "decision": None,
                    "comments": [],
                })
            now = _now_iso()
            doc = {
                "id": rid,
                "title": title,
                "kind": kind,
                "status": "open",
                "created_at": now,
                "updated_at": now,
                "blocks": blocks,
            }
            REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
            _write_json_atomic(_review_path(rid), doc)
            self._send_json(doc, 201)
            return True
        m = re.match(r"^/api/admin/reviews/([^/]+)/blocks/([^/]+)/comments$", path)
        if m:
            rid, bid = m.group(1), m.group(2)
            doc = _load_review(rid)
            if doc is None:
                self._send_json({"error": "unknown review"}, 404)
                return True
            block = _review_block(doc, bid)
            if block is None:
                self._send_json({"error": "unknown block"}, 404)
                return True
            text = data.get("text")
            if not isinstance(text, str) or not text.strip():
                self._send_json({"error": "comment text is required"}, 400)
                return True
            comments = block.get("comments")
            if not isinstance(comments, list):
                comments = []
                block["comments"] = comments
            comments.append({"text": text.strip(), "at": _now_iso()})
            doc["updated_at"] = _now_iso()
            _write_json_atomic(_review_path(rid), doc, backup=True)
            self._send_json(block)
            return True


    def _route_admin_post(self, path, fields, files):
        m = re.match(r"^/api/admin/courses/([^/]+)/media$", path)
        if m:
            cid = m.group(1)
            if not _course_manifest(cid):
                self._send_json({"error": "unknown course"}, 404)
                return True
            kind = (fields.get("kind") or "audio").strip() or "audio"
            if kind not in ("audio", "videos"):
                self._send_json({"error": "kind must be audio or videos"}, 400)
                return True
            file_entry = files.get("file")
            if not file_entry:
                self._send_json({"error": "missing 'file' field in multipart upload"}, 400)
                return True
            filename, content = file_entry
            safe = _sanitize_filename(filename)
            if not safe:
                self._send_json({"error": "invalid filename"}, 400)
                return True
            if len(content) > MAX_UPLOAD:
                self._send_json({"error": "upload too large (max 200 MB)"}, 413)
                return True
            d = COURSES_DIR / cid / "media" / kind
            d.mkdir(parents=True, exist_ok=True)
            if (d / safe).is_file():
                ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
                shutil.move(str(d / safe), str(_trash_path(f"{ts}__media__{cid}__{kind}__{safe}")))
            (d / safe).write_bytes(content)
            self._send_json({"file": safe, "kind": kind, "size": len(content)}, 201)
            return True
        m = re.match(r"^/api/admin/import$", path)
        if m:
            self._admin_import(fields, files)
            return True
        m = re.match(r"^/api/admin/courses/([^/]+)/checkpoint$", path)
        if m:
            self._send_json({"error": "checkpoint endpoint is not an admin API"}, 404)
            return True
        return False

    def _route_admin_put(self, path):
        m = re.match(r"^/api/admin/courses/([^/]+)/manifest$", path)
        if m:
            cid = m.group(1)
            if not _course_manifest(cid):
                self._send_json({"error": "unknown course"}, 404)
                return True
            data = self._read_json_body()
            if data is None:
                return True
            ok, errors = _manifest_check(cid, data)
            if not ok:
                self._send_json({"error": "invalid manifest", "errors": errors}, 400)
                return True
            _backup_if_exists(COURSES_DIR / cid / "manifest.json")
            (COURSES_DIR / cid / "manifest.json").write_text(
                json.dumps(data, indent=2) + "\n", encoding="utf-8")
            self._send_json(data)
            return True
        m = re.match(r"^/api/admin/courses/([^/]+)/lessons/([^/]+)$", path)
        if m:
            cid, lid = m.group(1), m.group(2)
            if not _course_manifest(cid):
                self._send_json({"error": "unknown course"}, 404)
                return True
            data = self._read_json_body()
            if data is None:
                return True
            manifest = _course_manifest(cid)
            module_ids = {mod.get("id") for mod in (manifest.get("modules") or []) if isinstance(mod, dict)}
            ok, errors = _validate_lesson_json(data, lid, module_ids)
            if not ok:
                self._send_json({"error": "invalid lesson", "errors": errors}, 400)
                return True
            (COURSES_DIR / cid / "lessons").mkdir(parents=True, exist_ok=True)
            _backup_if_exists(COURSES_DIR / cid / "lessons" / f"{lid}.json")
            (COURSES_DIR / cid / "lessons" / f"{lid}.json").write_text(
                json.dumps(data, indent=2) + "\n", encoding="utf-8")
            self._send_json(data)
            return True
        m = re.match(r"^/api/admin/reviews/([^/]+)$", path)
        if m:
            rid = m.group(1)
            doc = _load_review(rid)
            if doc is None:
                self._send_json({"error": "unknown review"}, 404)
                return True
            data = self._read_json_body()
            if data is None:
                return True
            if "status" in data:
                status = data["status"]
                if status not in ("open", "done"):
                    self._send_json({"error": "status must be 'open' or 'done'"}, 400)
                    return True
                doc["status"] = status
            if "title" in data:
                if not isinstance(data["title"], str):
                    self._send_json({"error": "title must be a string"}, 400)
                    return True
                doc["title"] = data["title"]
            doc["updated_at"] = _now_iso()
            _write_json_atomic(_review_path(rid), doc, backup=True)
            self._send_json(doc)
            return True
        m = re.match(r"^/api/admin/reviews/([^/]+)/blocks/([^/]+)/decision$", path)
        if m:
            rid, bid = m.group(1), m.group(2)
            doc = _load_review(rid)
            if doc is None:
                self._send_json({"error": "unknown review"}, 404)
                return True
            block = _review_block(doc, bid)
            if block is None:
                self._send_json({"error": "unknown block"}, 404)
                return True
            data = self._read_json_body()
            if data is None:
                return True
            if "decision" not in data:
                self._send_json({"error": "decision is required"}, 400)
                return True
            decision = data["decision"]
            if decision is not None and decision not in REVIEW_DECISIONS:
                self._send_json({"error": "decision must be one of do|dont|revise or null"}, 400)
                return True
            block["decision"] = decision
            doc["updated_at"] = _now_iso()
            _write_json_atomic(_review_path(rid), doc, backup=True)
            self._send_json(block)
            return True
        return False

    def _route_admin_delete(self, path):
        m = re.match(r"^/api/admin/courses/([^/]+)$", path)
        if m:
            cid = m.group(1)
            if not SAFE_ID_RE.match(cid or ""):
                self._send_json({"error": "bad course id"}, 404)
                return True
            target = COURSES_DIR / cid
            if not target.is_dir():
                self._send_json({"error": "unknown course"}, 404)
                return True
            ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            shutil.move(str(target), str(_trash_path(f"{ts}__course__{cid}")))
            self._send_json({"ok": True, "deleted": cid})
            return True
        m = re.match(r"^/api/admin/courses/([^/]+)/lessons/([^/]+)$", path)
        if m:
            cid, lid = m.group(1), m.group(2)
            if not SAFE_ID_RE.match(lid or ""):
                self._send_json({"error": "bad lesson id"}, 404)
                return True
            lesson_file = COURSES_DIR / cid / "lessons" / f"{lid}.json"
            if not lesson_file.is_file():
                self._send_json({"error": "unknown course or lesson"}, 404)
                return True
            ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            shutil.move(str(lesson_file), str(_trash_path(f"{ts}__lesson__{cid}__{lid}.json")))
            self._send_json({"ok": True, "deleted": lid})
            return True
        m = re.match(r"^/api/admin/courses/([^/]+)/media/(audio|videos)/([^/]+)$", path)
        if m:
            cid, kind, fname = m.group(1), m.group(2), m.group(3)
            if not _course_manifest(cid):
                self._send_json({"error": "unknown course"}, 404)
                return True
            target = (COURSES_DIR / cid / "media" / kind / fname).resolve()
            root = (COURSES_DIR / cid / "media").resolve()
            try:
                target.relative_to(root)
            except ValueError:
                self._send_json({"error": "bad media path"}, 400)
                return True
            if not target.is_file():
                self._send_json({"error": "media file not found"}, 404)
                return True
            ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            shutil.move(str(target), str(_trash_path(f"{ts}__media__{cid}__{kind}__{fname}")))
            self._send_json({"ok": True, "deleted": fname})
            return True
        m = re.match(r"^/api/admin/reviews/([^/]+)$", path)
        if m:
            rid = m.group(1)
            target = _review_path(rid)
            if target is None or not target.is_file():
                self._send_json({"error": "unknown review"}, 404)
                return True
            ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            shutil.move(str(target), str(_trash_path(f"{ts}__review__{rid}.json")))
            self._send_json({"ok": True, "deleted": rid})
            return True
        return False

    def _admin_import(self, fields, files):
        file_entry = files.get("file")
        if not file_entry:
            self._send_json({"error": "missing 'file' field in multipart upload"}, 400)
            return
        filename, content = file_entry
        if not filename.lower().endswith(".zip"):
            self._send_json({"error": "course package must be a .zip file"}, 400)
            return
        overwrite = (fields.get("overwrite") or "").strip().lower() in ("1", "true", "yes", "on")
        COURSES_DIR.mkdir(parents=True, exist_ok=True)
        tmp = Path(tempfile.mkdtemp(prefix=".import-", dir=str(COURSES_DIR)))
        try:
            try:
                with zipfile.ZipFile(io.BytesIO(content)) as zf:
                    _extract_zip_safe(zf, tmp)
            except (zipfile.BadZipFile, ValueError, OSError) as e:
                self._send_json({"error": f"invalid zip package: {e}"}, 422)
                return
            manifest_path = tmp / "manifest.json"
            if not manifest_path.is_file():
                self._send_json({"error": "package missing manifest.json"}, 422)
                return
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except ValueError as e:
                self._send_json({"error": f"invalid manifest.json: {e}"}, 422)
                return
            if not isinstance(manifest, dict) or not isinstance(manifest.get("id"), str):
                self._send_json({"error": "manifest.json must be an object with an id string"}, 422)
                return
            cid = manifest["id"]
            if not SAFE_ID_RE.match(cid):
                self._send_json({"error": "manifest id must match ^[A-Za-z0-9][A-Za-z0-9._-]*$"}, 422)
                return
            package_root = tmp / cid
            if not package_root.is_dir():
                # package may be laid out flat (manifest.json at zip root)
                package_root = tmp
            errors, warnings = validate_courses.validate_course(package_root, course_id=cid)
            if errors:
                self._send_json({"error": "package failed validation", "errors": errors, "warnings": warnings}, 422)
                return
            pub_err = _publish_import(package_root, cid, manifest, overwrite)
            if pub_err:
                self._send_json({"error": pub_err}, 409)
                return
            media = _media_list(cid)
            lesson_count = sum(1 for p in (COURSES_DIR / cid / "lessons").glob("*.json") if p.is_file())
            self._send_json({
                "id": cid,
                "lessons": lesson_count,
                "media": {"audio": len(media["audio"]), "videos": len(media["videos"])},
                "validate": {"errors": 0, "warnings": len(warnings)},
            }, 201)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            self._send_html(PLAYER_HTML)
            return
        if path == "/admin":
            self._send_html(ADMIN_HTML)
            return
        if path.startswith("/api/admin/"):
            if not self._admin_allowed():
                self._send_json({"error": "forbidden: admin token required"}, 403)
                return
            if self._route_admin_get(path):
                return
            self._send_json({"error": "unknown endpoint"}, 404)
            return
        if path == "/api/courses":
            self._send_json(_course_index())
            return
        m = re.match(r"^/api/courses/([^/]+)/lessons/([^/]+)/solutions$", path)
        if m:
            lesson = _load_lesson(m.group(1), m.group(2))
            if lesson is None:
                self._send_json({"error": "unknown course or lesson"}, 404)
            else:
                self._send_json(_lesson_solutions(lesson))
            return
        m = re.match(r"^/api/courses/([^/]+)/lessons/([^/]+)$", path)
        if m:
            lesson = _load_lesson(m.group(1), m.group(2))
            if lesson is None:
                self._send_json({"error": "unknown course or lesson"}, 404)
            else:
                out = _lesson_public(lesson)
                audio = _lesson_audio_file(m.group(1), m.group(2))
                if audio:
                    out["audio"] = {"file": audio}
                self._send_json(out)
            return
        m = re.match(r"^/media/([^/]+)/(.+)$", path)
        if m:
            self._serve_media(m.group(1), m.group(2))
            return
        self._send_json({"error": "unknown endpoint"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        if path.startswith("/api/admin/"):
            if not self._admin_allowed():
                self._send_json({"error": "forbidden: admin token required"}, 403)
                return
            is_json_post = (
                path == "/api/admin/courses"
                or bool(re.match(r"^/api/admin/courses/[^/]+/lessons$", path))
                or bool(re.match(r"^/api/admin/reviews$", path))
                or bool(re.match(r"^/api/admin/reviews/[^/]+/blocks/[^/]+/comments$", path))
            )
            if is_json_post:
                data = self._read_json_body()
                if data is None:
                    return
                if self._route_admin_post_json(path, data):
                    return
            else:
                fields, files = self._read_multipart()
                if fields is None:
                    return
                if self._route_admin_post(path, fields, files):
                    return
            self._send_json({"error": "unknown endpoint"}, 404)
            return
        m = re.match(r"^/api/courses/([^/]+)/checkpoint$", path)
        if not m:
            self._send_json({"error": "unknown endpoint"}, 404)
            return
        course_id = m.group(1)
        data = self._read_json_body()
        if data is None:
            return
        qid = data.get("qid")
        option_index = data.get("option_index")
        if not isinstance(qid, str) or not isinstance(option_index, int):
            self._send_json({"error": "qid must be a string and option_index an integer"}, 400)
            return
        cp = _find_checkpoint(course_id, qid)
        if cp is None:
            self._send_json({"error": "unknown checkpoint"}, 404)
            return
        options = cp.get("options") or []
        if option_index < 0 or option_index >= len(options):
            self._send_json({"error": "option_index out of range"}, 400)
            return
        self._send_json({
            "correct": bool(options[option_index].get("is_correct")),
            "explanation": cp.get("explanation", ""),
        })

    def do_PUT(self):
        path = urlparse(self.path).path
        if not path.startswith("/api/admin/"):
            self._send_json({"error": "unknown endpoint"}, 404)
            return
        if not self._admin_allowed():
            self._send_json({"error": "forbidden: admin token required"}, 403)
            return
        if self._route_admin_put(path):
            return
        self._send_json({"error": "unknown endpoint"}, 404)

    def do_DELETE(self):
        path = urlparse(self.path).path
        if not path.startswith("/api/admin/"):
            self._send_json({"error": "unknown endpoint"}, 404)
            return
        if not self._admin_allowed():
            self._send_json({"error": "forbidden: admin token required"}, 403)
            return
        if self._route_admin_delete(path):
            return
        self._send_json({"error": "unknown endpoint"}, 404)

    def _serve_media(self, course_id, rel_path):
        if not SAFE_ID_RE.match(course_id or ""):
            self._send_json({"error": "bad course id"}, 404)
            return
        media_root = (COURSES_DIR / course_id / "media").resolve()
        target = (media_root / rel_path).resolve()
        try:
            target.relative_to(media_root)
        except ValueError:
            self._send_json({"error": "bad media path"}, 404)
            return
        if not target.is_file():
            self._send_json({"error": "media not found"}, 404)
            return
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        try:
            data = target.read_bytes()
        except OSError:
            self._send_json({"error": "media not found"}, 404)
            return
        self._send_bytes(data, ctype)

    def log_message(self, fmt, *args):
        print(f"[course_server] {self.address_string()} - {fmt % args}")


def _load_player_html():
    """Read the shared course-player template (templates/player.html).

    Template-as-code: the player UI lives in one file used by both the live
    server and the static build; Python never embeds the HTML.
    """
    path = BASE_DIR / "templates" / "player.html"
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ("<!DOCTYPE html><html><head><meta charset='utf-8'><title>MathFlow</title></head>"
                "<body><h1>Missing template: templates/player.html</h1></body></html>")


PLAYER_HTML = _load_player_html()


def _load_admin_html():
    path = BASE_DIR / "templates" / "admin.html"
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ("<!DOCTYPE html><html><head><meta charset='utf-8'><title>MathFlow Admin</title></head>"
                "<body><h1>Missing template: templates/admin.html</h1></body></html>")


ADMIN_HTML = _load_admin_html()



def main():
    REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Course Mode @ http://0.0.0.0:{PORT}")
    print(f"   Local: http://localhost:{PORT}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
