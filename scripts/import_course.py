#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Import a MathFlow course package into the running course server.

Uploads a course package zip (or zips a directory on the fly) to
POST /api/admin/import and prints the pipeline result.

Usage:
  python3 scripts/import_course.py <course-package.zip|dir> [--overwrite]
      [--host http://localhost:8788] [--token TOKEN]

Stdlib only. English output. Exit code 0 on success, 1 on failure.
"""
import argparse
import io
import json
import os
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path


def parse_args(argv):
    ap = argparse.ArgumentParser(
        prog="import_course.py",
        description="Import a MathFlow course package (zip or directory) into the course server.",
    )
    ap.add_argument("package", help="Path to a course package .zip file or a directory containing manifest.json")
    ap.add_argument("--overwrite", action="store_true", help="Replace an existing course with the same id")
    ap.add_argument("--host", default="http://localhost:8788", help="Server base URL (default: http://localhost:8788)")
    ap.add_argument("--token", default=None, help="Value for the X-Admin-Token header (needed for non-loopback or token-protected servers)")
    return ap.parse_args(argv)


def zip_package(source):
    """Return (filename, bytes) for the package. Zips a directory (contents at zip root)."""
    src = Path(source)
    if src.is_file():
        if src.suffix.lower() != ".zip":
            raise SystemExit(f"error: '{source}' is not a .zip file")
        return src.name, src.read_bytes()
    if not src.is_dir():
        raise SystemExit(f"error: '{source}' is neither a zip file nor a directory")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(src.rglob("*")):
            if p.is_file():
                zf.write(p, p.relative_to(src).as_posix())
    return src.name + ".zip", buf.getvalue()


def build_multipart(filename, content, overwrite):
    boundary = "----mathflowImport" + os.urandom(8).hex()
    safe_name = filename.replace("\\", "\\\\").replace('"', '\\"')
    parts = []
    parts.append(
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{safe_name}"\r\n'
        "Content-Type: application/zip\r\n\r\n".encode("utf-8")
    )
    parts.append(content)
    parts.append(b"\r\n")
    if overwrite:
        parts.append(
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="overwrite"\r\n\r\n'
            "true\r\n".encode("utf-8")
        )
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(parts)
    return boundary, body


def upload(host, boundary, body, token):
    url = host.rstrip("/") + "/api/admin/import"
    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(body)),
    }
    if token:
        headers["X-Admin-Token"] = token
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def print_result(status, text):
    try:
        data = json.loads(text)
    except ValueError:
        print(f"error: non-JSON response (HTTP {status}): {text[:500]}")
        return 1
    if status == 201:
        print(f"OK: course '{data.get('id')}' imported")
        print(f"  lessons: {data.get('lessons', 0)}")
        media = data.get("media") or {}
        print(f"  media:   audio={media.get('audio', 0)} videos={media.get('videos', 0)}")
        validate = data.get("validate") or {}
        if validate.get("warnings"):
            print(f"  warnings: {validate['warnings']} (see server logs / validate endpoint)")
        return 0
    print(f"FAILED (HTTP {status}): {data.get('error', text)}")
    for e in data.get("errors") or []:
        print(f"  ERR  {e}")
    for w in data.get("warnings") or []:
        print(f"  WARN {w}")
    return 1


def main(argv=None):
    args = parse_args(argv)
    filename, content = zip_package(args.package)
    boundary, body = build_multipart(filename, content, args.overwrite)
    print(f"Uploading {filename} ({len(content)} bytes) to {args.host}/api/admin/import ...")
    status, text = upload(args.host, boundary, body, args.token)
    return print_result(status, text)


if __name__ == "__main__":
    sys.exit(main())
