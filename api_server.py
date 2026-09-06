#!/usr/bin/env python3
"""
MathFlow API server — JSON HTTP API for the mobile client (Mac mini backend).
================================================================================
Thin stdlib ThreadingHTTPServer wrapper around the existing MathFlow pieces:
- prototype_fill.build_question  (LLM fill + deterministic distractor judge)
- mathflow.compile_check         (the Lean compiler as judge)

Endpoints:
  GET  /api/health               -> {"ok": true}
  GET  /api/lessons              -> [{id, title, created_at, question_count}]
  GET  /api/lessons/<id>         -> {id, title, questions: [...]}
  POST /api/check                -> {"correct": bool, "error": str|null}
  POST /api/lessons/generate     -> lesson object (same shape as GET detail)

Run:
  MATHFLOW_LLM_MOCK=1 python3 api_server.py --seed 8787
  python3 api_server.py 8787            # no seeding
Stdlib only (Python 3.9+).
"""

import hashlib
import json
import os
import random
import re
import subprocess
import sys
import threading
import time
import uuid
from collections import OrderedDict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import mathflow
import prototype_fill

BASE_DIR = Path(__file__).resolve().parent
COURSES_DIR = BASE_DIR / "data" / "courses"

DEFAULT_PORT = 8787
MAX_CACHE_ENTRIES = 64
JSON_LIMIT = 1 << 20  # 1 MiB request bodies

# Lesson ids are slugified goals + a timestamp; keep them strictly filesystem-safe.
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

FILE_LOCK = threading.Lock()       # guards all data/courses/*.json reads/writes
GENERATE_LOCK = threading.Lock()   # single-flight question generation


# ------------------------------------------------------------ compile cache ---
class CompileCache:
    """Thread-safe in-memory LRU for compile results, keyed by sha1 of the code.

    One lock guards both the cache and the compile call itself: compiles are
    serialized (mathflow writes a shared temp file, and compiles are slow), so
    identical answers never recompile and no two threads run lean at once.
    """

    def __init__(self, maxsize=MAX_CACHE_ENTRIES):
        self.maxsize = maxsize
        self._cache = OrderedDict()
        self._lock = threading.Lock()

    def compile(self, code):
        """Return (ok, message, elapsed_seconds, from_cache)."""
        key = hashlib.sha1(code.encode("utf-8")).hexdigest()
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                ok, msg = self._cache[key]
                return ok, msg, 0.0, True
            t0 = time.monotonic()
            try:
                ok, msg = mathflow.compile_check(code, "")
            except subprocess.TimeoutExpired:
                return False, "Lean compilation timed out (60s).", time.monotonic() - t0, False
            except FileNotFoundError as e:
                return False, f"Lean executable not found ({e.filename}).", time.monotonic() - t0, False
            except Exception as e:
                return False, f"Lean compiler error ({e}).", time.monotonic() - t0, False
            elapsed = time.monotonic() - t0
            self._cache[key] = (ok, msg)
            self._cache.move_to_end(key)
            while len(self._cache) > self.maxsize:
                self._cache.popitem(last=False)
            return ok, msg, elapsed, False


COMPILE_CACHE = CompileCache()


# ------------------------------------------------------------ course files ---
def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _slugify(goal):
    s = re.sub(r"[^A-Za-z0-9]+", "-", (goal or "").strip().lower()).strip("-")
    return s or "lesson"


def _question_files():
    if not COURSES_DIR.exists():
        return []
    return sorted(COURSES_DIR.glob("*.json"))


def _load_questions(lesson_id):
    """Read one lesson file -> (list of question dicts, file mtime) or (None, None)."""
    if not SAFE_ID_RE.match(lesson_id):
        return None, None
    p = COURSES_DIR / f"{lesson_id}.json"
    with FILE_LOCK:
        try:
            with open(p, encoding="utf-8") as f:
                questions = json.load(f)
            mtime = p.stat().st_mtime
        except (OSError, ValueError):
            return None, None
    if not isinstance(questions, list) or not questions:
        return None, None
    return questions, mtime


def _api_question(q):
    """Strip server-only fields (answer/title/created_at/goal) from a stored question."""
    return {
        "qid": q.get("qid"),
        "code": q.get("code", ""),
        "options": q.get("options", []),
        "explanation": q.get("explanation", ""),
        "hint": q.get("hint", ""),
    }


def _lesson_summary(lesson_id):
    questions, mtime = _load_questions(lesson_id)
    if questions is None:
        return None
    first = questions[0]
    return {
        "id": lesson_id,
        "title": first.get("title") or lesson_id,
        "created_at": first.get("created_at") or datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat(timespec="seconds"),
        "question_count": len(questions),
    }


def _lesson_detail(lesson_id):
    questions, _ = _load_questions(lesson_id)
    if questions is None:
        return None
    first = questions[0]
    return {
        "id": lesson_id,
        "title": first.get("title") or lesson_id,
        "questions": [_api_question(q) for q in questions],
    }


def _find_question(qid):
    """Locate a stored question dict by qid across all lesson files."""
    for p in _question_files():
        with FILE_LOCK:
            try:
                with open(p, encoding="utf-8") as f:
                    questions = json.load(f)
            except (OSError, ValueError):
                continue
        if not isinstance(questions, list):
            continue
        for q in questions:
            if isinstance(q, dict) and q.get("qid") == qid:
                return q, p.stem
    return None, None


def _append_question(goal, data, distractors):
    """Persist one generated question (correct + judged distractors) to data/courses/<id>.json."""
    lesson_id = f"{_slugify(goal)}-{time.strftime('%H%M%S')}"
    p = COURSES_DIR / f"{lesson_id}.json"
    options = [{"text": data["answer"], "is_correct": True}]
    options += [{"text": frag, "is_correct": False} for frag, _ in distractors]
    random.shuffle(options)
    q = {
        "qid": uuid.uuid4().hex[:12],
        "title": data["title"],
        "created_at": _now_iso(),
        "goal": goal,
        "code": data["code"],
        "options": options,
        "explanation": data["explanation"],
        "hint": data["hint"],
        "answer": data["answer"],  # server-only: never sent to clients
    }
    with FILE_LOCK:
        questions = []
        if p.exists():
            try:
                with open(p, encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, list):
                    questions = loaded
            except (OSError, ValueError):
                questions = []
        questions.append(q)
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(questions, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(p)
    return lesson_id


def _generate_question(goal):
    """build_question + persist; returns (lesson_id, question) or (None, error)."""
    goal = (goal or "").strip()
    if not goal:
        return None, "Missing field: goal"
    with GENERATE_LOCK:  # single-flight; compiles are slow
        t0 = time.monotonic()
        q = prototype_fill.build_question(goal)
        if q is None:
            return None, "Could not generate a question (LLM/fill failed after 3 attempts)."
        data, dist = q["data"], q["distractors"]
        lesson_id = _append_question(goal, data, dist)
        s = q["stats"]
        print(f"[api] generated question -> lesson {lesson_id} "
              f"(llm {s['llm']:.1f}s, compile {s['compile']:.1f}s, judged {s['judged']}, kept {s['kept']})",
              flush=True)
        return lesson_id, None


# ------------------------------------------------------------------- HTTP ---
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # compact logs
        sys.stderr.write("[api] %s\n" % (fmt % args))

    def _send(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self, limit=JSON_LIMIT):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if n <= 0 or n > limit:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/health":
            self._send({"ok": True})
            return
        if path == "/api/lessons":
            lessons = []
            for p in _question_files():
                summary = _lesson_summary(p.stem)
                if summary is not None:
                    lessons.append(summary)
            lessons.sort(key=lambda s: s["created_at"], reverse=True)
            self._send(lessons)
            return
        m = re.fullmatch(r"/api/lessons/([^/]+)", path)
        if m:
            lesson = _lesson_detail(m.group(1))
            if lesson is None:
                self._send({"error": "unknown lesson"}, 404)
            else:
                self._send(lesson)
            return
        self._send({"error": "unknown endpoint"}, 404)

    def do_POST(self):
        path = self.path.split("?")[0]
        data = self._read_json()
        try:
            if path == "/api/check":
                qid = data.get("qid") or ""
                answer = data.get("answer")
                if not qid or not isinstance(answer, str):
                    self._send({"error": "Missing fields: qid (str), answer (str)."}, 400)
                    return
                q, _ = _find_question(qid)
                if q is None:
                    self._send({"error": "unknown question"}, 404)
                    return
                if answer.strip() == (q.get("answer") or "").strip():
                    # Fast path: exact correct fragment -> no compile at all.
                    self._send({"correct": True, "error": None})
                    return
                code = q.get("code", "")
                if code.count("___") != 1:
                    self._send({"error": "stored question is malformed (blank count != 1)"}, 500)
                    return
                substituted = code.replace("___", answer, 1)
                ok, msg, elapsed, from_cache = COMPILE_CACHE.compile(substituted)
                if not from_cache:
                    print(f"[api] check compile {'OK' if ok else 'FAIL'} in {elapsed:.1f}s "
                          f"(cache size {len(COMPILE_CACHE._cache)})", flush=True)
                if ok:
                    self._send({"correct": True, "error": None})
                else:
                    self._send({"correct": False, "error": prototype_fill.first_error_line(msg)})
                return

            if path == "/api/lessons/generate":
                goal = data.get("goal") or ""
                if not goal.strip():
                    self._send({"error": "Missing field: goal."}, 400)
                    return
                lesson_id, err = _generate_question(goal)
                if lesson_id is None:
                    self._send({"error": err}, 502)
                    return
                lesson = _lesson_detail(lesson_id)
                self._send(lesson)
                return

            self._send({"error": "unknown endpoint"}, 404)
        except Exception as e:  # always answer JSON instead of dropping the connection
            self._send({"error": f"Server error: {e}"}, 500)


# ------------------------------------------------------------------- main ---
def _parse_args(argv):
    seed = "--seed" in argv
    port = DEFAULT_PORT
    for a in argv:
        if a == "--seed":
            continue
        try:
            port = int(a)
            break
        except ValueError:
            continue
    return seed, port


def _seed_course():
    """If data/courses/ is empty, generate one mock course so the API has content."""
    if _question_files():
        return False
    print("[api] data/courses is empty — seeding one mock course (compiles are slow, be patient)...", flush=True)
    lesson_id, err = _generate_question("commutativity of natural number addition")
    if lesson_id is None:
        print(f"[api] SEED FAILED: {err}", flush=True)
        return False
    print(f"[api] seeded lesson {lesson_id}", flush=True)
    return True


def main():
    seed, port = _parse_args(sys.argv[1:])
    COURSES_DIR.mkdir(parents=True, exist_ok=True)
    if seed:
        _seed_course()
    print(f"[api] MathFlow API @ http://0.0.0.0:{port}")
    if os.environ.get("MATHFLOW_LLM_MOCK") == "1":
        print("[api] LLM: offline MOCK mode (MATHFLOW_LLM_MOCK=1)")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
