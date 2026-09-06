#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate MathFlow course data against lesson.schema.json.

Stdlib only (no jsonschema dependency): structural checks mirroring the schema
plus cross-file checks (chip references, checkpoint option integrity, media files).

Usage:
  python3 validate_courses.py                 # validate all courses
  python3 validate_courses.py <course_id>     # validate one course
Exit code 0 = all OK, 1 = errors found.

Importable:
  errors, warnings = validate_course(course_dir, course_id=None)
"""
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
COURSES_DIR = BASE / "data" / "courses"
SCHEMA_VERSION = 1
CHIP_RE = re.compile(r"@(def|thm):([A-Za-z0-9._-]+)")
FENCE_RE = re.compile(r"^:::(def|thm|proof|con|ex|rem)$")


def _err(errors, course, lid, msg):
    errors.append(f"{course}/{lid}: {msg}")


def _warn(warnings, course, lid, msg):
    warnings.append(f"{course}/{lid}: {msg}")


def check_ids(entries, errors, warnings, course, lid, pool_name):
    seen = set()
    for e in entries:
        eid = e.get("id", "")
        if not eid:
            _err(errors, course, lid, f"{pool_name} entry missing id")
            continue
        if eid in seen:
            _err(errors, course, lid, f"duplicate {pool_name} id: {eid}")
        seen.add(eid)
        for f in ("name", "statement"):
            if not e.get(f):
                _err(errors, course, lid, f"{pool_name} '{eid}' missing '{f}'")
    return seen


def check_quiz(q, errors, warnings, course, lid, where):
    if not q.get("qid") or not q.get("question"):
        _err(errors, course, lid, f"{where}: missing qid/question")
    opts = q.get("options") or []
    if len(opts) < 2:
        _err(errors, course, lid, f"{where}: need >= 2 options")
    if not any(o.get("is_correct") for o in opts):
        _err(errors, course, lid, f"{where}: no correct option")
    if not q.get("explanation"):
        _warn(warnings, course, lid, f"{where}: missing explanation")


def check_lesson(course_id, lid, lesson, errors, warnings):
    if lesson.get("schema_version") != SCHEMA_VERSION:
        _err(errors, course_id, lid, f"schema_version != {SCHEMA_VERSION} (got {lesson.get('schema_version')!r})")
    for f in ("id", "module", "kind", "title", "body"):
        if not lesson.get(f):
            _err(errors, course_id, lid, f"missing required field: {f}")
    if lesson.get("kind") not in ("theory", "media", "checkpoint", "mcq", "exercise"):
        _err(errors, course_id, lid, f"bad kind: {lesson.get('kind')!r}")
    if lesson.get("id") != lid:
        _err(errors, course_id, lid, f"file/lesson id mismatch: {lesson.get('id')!r} != {lid!r}")

    body = lesson.get("body", "")
    def_ids = check_ids(lesson.get("defs") or [], errors, warnings, course_id, lid, "defs")
    thm_ids = check_ids(lesson.get("theorems") or [], errors, warnings, course_id, lid, "theorems")

    # chip references must resolve
    for ref, cid in CHIP_RE.findall(body):
        pool = def_ids if ref == "def" else thm_ids
        if cid not in pool:
            _err(errors, course_id, lid, f"unresolved chip @{ref}:{cid}")

    # fences must be balanced
    depth = 0
    for line in body.splitlines():
        t = line.strip()
        if FENCE_RE.match(t):
            depth += 1
        elif t == ":::":
            depth -= 1
            if depth < 0:
                _err(errors, course_id, lid, "unbalanced ::: fence (extra close)")
                depth = 0
    if depth != 0:
        _err(errors, course_id, lid, f"unbalanced ::: fence (open={depth})")

    # checkpoints
    cp_qids = set()
    for cp in lesson.get("checkpoints") or []:
        qid = cp.get("qid", "")
        if qid in cp_qids:
            _err(errors, course_id, lid, f"duplicate checkpoint qid: {qid}")
        cp_qids.add(qid)
        check_quiz(cp, errors, warnings, course_id, lid, f"checkpoint {qid}")

    # exercises
    ex_ids = set()
    for ex in lesson.get("exercises") or []:
        eid = ex.get("id", "")
        if eid in ex_ids:
            _err(errors, course_id, lid, f"duplicate exercise id: {eid}")
        ex_ids.add(eid)
        for f in ("prompt", "hint", "solution"):
            if not ex.get(f):
                _warn(warnings, course_id, lid, f"exercise {eid}: missing {f}")

    # media videos
    for v in (lesson.get("media") or {}).get("videos") or []:
        for f in ("id", "file", "title", "duration_sec"):
            if not v.get(f):
                _err(errors, course_id, lid, f"video missing '{f}': {v.get('id','?')}")
        if v.get("before"):
            check_quiz(v["before"], errors, warnings, course_id, lid, f"video {v.get('id')} before-quiz")
        if v.get("after"):
            check_quiz(v["after"], errors, warnings, course_id, lid, f"video {v.get('id')} after-quiz")


def validate_course(course_dir, course_id=None):
    """Validate one course directory.

    course_dir: path to a course directory containing manifest.json and lessons/.
    course_id:  used in error messages; when None it is derived from the
                manifest's id field (falling back to the directory name), so a
                package can be validated in a temp dir before publishing.

    Returns (errors, warnings) as lists of human-readable strings.
    """
    errors = []
    warnings = []
    course_dir = Path(course_dir)
    if course_id is None:
        course_id = course_dir.name
        manifest = course_dir / "manifest.json"
        if manifest.is_file():
            try:
                m0 = json.loads(manifest.read_text(encoding="utf-8"))
            except ValueError:
                m0 = None
            if isinstance(m0, dict) and m0.get("id"):
                course_id = m0["id"]

    manifest = course_dir / "manifest.json"
    if not manifest.is_file():
        _err(errors, course_id, "(manifest)", "manifest.json not found")
        return errors, warnings
    try:
        m = json.loads(manifest.read_text(encoding="utf-8"))
    except ValueError as e:
        _err(errors, course_id, "(manifest)", f"invalid JSON: {e}")
        return errors, warnings
    if not isinstance(m, dict):
        _err(errors, course_id, "(manifest)", "manifest must be a JSON object")
        return errors, warnings
    if m.get("id") != course_id:
        _err(errors, course_id, "(manifest)", f"manifest id mismatch: {m.get('id')!r}")
    for mod in m.get("modules") or []:
        if not isinstance(mod, dict):
            _err(errors, course_id, "(manifest)", f"module entry must be an object: {mod!r}")
            continue
        for ref in mod.get("lessons") or []:
            lid = ref.get("id") if isinstance(ref, dict) else ref
            if not lid:
                continue
            lesson_path = course_dir / "lessons" / f"{lid}.json"
            if not lesson_path.is_file():
                _err(errors, course_id, lid, "lesson file not found")
                continue
            try:
                lesson = json.loads(lesson_path.read_text(encoding="utf-8"))
            except ValueError as e:
                _err(errors, course_id, lid, f"invalid JSON: {e}")
                continue
            if not isinstance(lesson, dict):
                _err(errors, course_id, lid, "lesson must be a JSON object")
                continue
            check_lesson(course_id, lid, lesson, errors, warnings)
    return errors, warnings


def main():
    course_ids = sys.argv[1:] or [d.parent.name for d in sorted(COURSES_DIR.glob("*/manifest.json"), key=lambda p: p.parent.name)]
    errors = []
    warnings = []
    for course_id in course_ids:
        e, w = validate_course(COURSES_DIR / course_id, course_id=course_id)
        errors.extend(e)
        warnings.extend(w)

    print(f"--- validate_courses ---")
    for w in warnings:
        print(f"  WARN {w}")
    for e in errors:
        print(f"  ERR  {e}")
    if errors:
        print(f"FAILED: {len(errors)} error(s), {len(warnings)} warning(s)")
        sys.exit(1)
    print(f"ALL OK ({len(warnings)} warning(s))")


if __name__ == "__main__":
    main()
