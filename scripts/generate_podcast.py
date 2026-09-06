#!/usr/bin/env python3
"""
generate_podcast.py - NotebookLM-style two-host podcast audio for MathFlow lessons.
=================================================================================
For each lesson of a course, asks DeepSeek for a conversational two-host script
(Host A: curious learner; Host B: expert explainer), synthesizes every line with
local Qwen3-TTS (MLX, one model load per lesson), and assembles the podcast mp3
with ffmpeg (0.45 s silence between lines, 128 kbps output, same recipe as
demo/audio/m1-three-theories-sample.mp3).

Usage:
  python3 scripts/generate_podcast.py [--course pseudorandomness-primer] [--lesson <lid>] [--force]

Output: data/courses/<course>/media/audio/<lesson_id>.mp3

English only. Requires the repo .venv-tts (Python 3.14, mlx-audio) with the
cached Qwen3-TTS model mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-8bit,
/opt/homebrew/bin/ffmpeg, and a DeepSeek API key (llm.py reads DEEPSEEK_API_KEY
from the environment).
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import llm  # DeepSeek wrapper; reads DEEPSEEK_API_KEY from the environment.

DEFAULT_COURSE = "pseudorandomness-primer"
QWEN_PYTHON = os.environ.get("MF_PODCAST_QWEN_PYTHON", str(ROOT / ".venv-tts" / "bin" / "python"))
FFMPEG = os.environ.get("MF_PODCAST_FFMPEG", "/opt/homebrew/bin/ffmpeg")
FFPROBE = os.environ.get("MF_PODCAST_FFPROBE", "/opt/homebrew/bin/ffprobe")

HOST_A_INSTRUCT = "A warm, friendly female voice, natural conversational podcast host, clear and expressive, medium pitch"
HOST_B_INSTRUCT = "A friendly male voice, natural conversational podcast host, warm and engaging, medium-low pitch"
SILENCE_SECONDS = 0.45
BITRATE = "128k"
BODY_CHARS = 5000  # sensible truncation for the prompt
CHECKPOINT_EXPL_CHARS = 400

LINE_RE = re.compile(r"^\s*(?:[-*]\s*)?(?:Host\s+)?([AB])\s*[:.\-]\s*(.+?)\s*$", re.S)


def log(msg):
    print(f"[podcast] {msg}", flush=True)


def err(msg):
    print(f"[podcast] error: {msg}", file=sys.stderr, flush=True)


def run(cmd):
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        tail = (proc.stderr or b"").decode("utf-8", "replace").strip().splitlines()
        raise RuntimeError("command failed: %s\n%s" % (" ".join(cmd), "\n".join(tail[-8:])))
    return proc


def load_lesson(course, lid):
    path = ROOT / "data" / "courses" / course / "lessons" / f"{lid}.json"
    if not path.is_file():
        raise FileNotFoundError(f"lesson JSON not found: {path}")
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except ValueError as e:
        raise ValueError(f"invalid JSON in {path}: {e}") from e


def course_lesson_ids(course):
    manifest_path = ROOT / "data" / "courses" / course / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"course manifest not found: {manifest_path}")
    try:
        with open(manifest_path, encoding="utf-8") as fh:
            manifest = json.load(fh)
    except ValueError as e:
        raise ValueError(f"invalid JSON in {manifest_path}: {e}") from e
    ids = []
    for mod in manifest.get("modules") or []:
        for ref in mod.get("lessons") or []:
            if isinstance(ref, dict):
                ref = ref.get("id")
            if ref:
                ids.append(ref)
    return ids


def _truncate(text, limit):
    text = text or ""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    return cut.rstrip() + " …"


def _checkpoint_text(cp):
    correct = [o.get("text", "") for o in (cp.get("options") or []) if o.get("is_correct")]
    lines = [f"- Q: {_truncate(cp.get('question', ''), 500)}"]
    if correct:
        lines.append(f"  Correct answer: {correct[0]}")
    expl = _truncate(cp.get("explanation", ""), CHECKPOINT_EXPL_CHARS)
    if expl:
        lines.append(f"  Explanation: {expl}")
    return "\n".join(lines)


def build_messages(lesson):
    """System + user messages grounding the podcast conversation in the lesson JSON."""
    kind = lesson.get("kind", "theory")
    title = lesson.get("title", lesson.get("id", ""))
    reading = lesson.get("reading") or {}
    reading_text = reading.get("text", "") if isinstance(reading, dict) else ""
    body = _truncate(lesson.get("body", ""), BODY_CHARS)

    defs_text = "\n".join(
        f"- {d.get('name', d.get('id', ''))}: {d.get('statement', '')}"
        + (f" (intuition: {d.get('intuition', '')})" if d.get("intuition") else "")
        for d in (lesson.get("defs") or [])
    )
    thms_text = "\n".join(
        f"- {t.get('name', t.get('id', ''))}: {t.get('statement', '')}"
        + (f" (intuition: {t.get('intuition', '')})" if t.get("intuition") else "")
        for t in (lesson.get("theorems") or [])
    )
    cps_text = "\n".join(_checkpoint_text(cp) for cp in (lesson.get("checkpoints") or []))

    system = (
        "You are a scriptwriter for an educational podcast series on computational complexity, "
        "in the style of a NotebookLM audio overview. You write a natural two-host conversation:\n"
        "- Host A is a curious learner who asks questions, expresses confusion, and asks for examples.\n"
        "- Host B is an expert who explains clearly, uses analogies, and answers Host A's questions.\n"
        "The result must sound like a relaxed back-and-forth between two people, not a lecture, "
        "not a monologue, and not a transcript of the lesson text.\n\n"
        "Rules:\n"
        "1. Ground every claim strictly in the lesson material and Primer sections supplied below. "
        "Never invent results, definitions, examples, or section numbers.\n"
        "2. Read mathematics aloud naturally (e.g., \"epsilon over p of n\", \"ell of k\", "
        "\"the uniform distribution over strings of length ell of k\").\n"
        "3. Keep each spoken line short, 1-3 sentences, so a single voice can read it.\n"
        "4. Target 750-1200 words total (about 5-8 minutes of speech).\n"
        "5. End the conversation with a 2-3 sentence recap.\n"
        "6. Output ONLY the dialogue, one line per turn, tagged \"A:\" or \"B:\". "
        "No headings, no stage directions, no preamble, no closing note."
    )
    if kind == "mcq":
        task = (
            "This is a recap-style checkpoint lesson (multiple-choice review). Write the podcast "
            "as a recap conversation that walks through the confusions below, explains each one, "
            "and states its resolution."
        )
    else:
        task = "Write the podcast conversation for this lesson."

    user = (
        f"COURSE CONTEXT\n"
        f"Lesson id: {lesson.get('id', '')}\n"
        f"Lesson kind: {kind}\n"
        f"Lesson title: {title}\n"
        f"Reading: {reading_text}\n\n"
        f"--- LESSON BODY ---\n{body}\n"
    )
    if defs_text:
        user += f"\n--- DEFINITIONS ---\n{defs_text}\n"
    if thms_text:
        user += f"\n--- THEOREMS ---\n{thms_text}\n"
    if cps_text:
        user += f"\n--- CHECKPOINTS ---\n{cps_text}\n"
    user += f"\nTASK\n{task}\n"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def parse_script(text):
    """Return [(speaker, line), ...] from LLM output (A:/B: lines or a JSON list)."""
    if not text or not text.strip():
        raise ValueError("model returned an empty script")
    stripped = text.strip()

    if stripped.startswith("["):
        try:
            items = json.loads(stripped)
        except ValueError:
            items = None
        if isinstance(items, list):
            out = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                speaker = str(item.get("speaker", "")).strip().upper()
                speaker = re.sub(r"^HOST\s*", "", speaker)
                body = str(item.get("text", "")).strip()
                if speaker not in ("A", "B") or not body:
                    continue
                out.append((speaker, body))
            if out:
                return out

    fence = re.search(r"```(?:[A-Za-z]+)?\n(.*?)```", stripped, re.S)
    if fence:
        stripped = fence.group(1).strip()

    out = []
    for raw in stripped.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = LINE_RE.match(line)
        if m:
            out.append((m.group(1), m.group(2).strip()))
        elif out:
            speaker, text = out[-1]
            out[-1] = (speaker, text + " " + line)

    speakers = {s for s, _ in out}
    if len(out) < 2 or "A" not in speakers or "B" not in speakers:
        raise ValueError("script must contain at least one A line and one B line")
    return out


def make_silence(out_path, seconds=SILENCE_SECONDS):
    run([
        FFMPEG, "-v", "error", "-y",
        "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
        "-t", f"{seconds:.2f}", "-q:a", "9", "-acodec", "libmp3lame",
        str(out_path),
    ])


def concat_audio(line_paths, out_path):
    """Concat per-line wavs with a 0.45 s silence gap between lines; 128 kbps mp3 output."""
    tmpdir = Path(tempfile.mkdtemp(prefix="podcast_concat_"))
    try:
        silence = tmpdir / "silence.mp3"
        make_silence(silence)
        entries = []
        for i, p in enumerate(line_paths):
            entries.append(str(p))
            if i < len(line_paths) - 1:
                entries.append(str(silence))
        list_path = tmpdir / "list.txt"
        with open(list_path, "w", encoding="utf-8") as fh:
            for e in entries:
                escaped = e.replace("'", "'\\''")
                fh.write(f"file '{escaped}'\n")
        run([
            FFMPEG, "-v", "error", "-y",
            "-f", "concat", "-safe", "0", "-i", str(list_path),
            "-c:a", "libmp3lame", "-b:a", BITRATE,
            str(out_path),
        ])
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def probe_duration(path):
    proc = run([FFPROBE, "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)])
    out = proc.stdout.decode("utf-8", "replace").strip()
    try:
        return float(out)
    except ValueError:
        return 0.0


def generate_lesson(course, lid, force=False):
    lesson = load_lesson(course, lid)
    out = ROOT / "data" / "courses" / course / "media" / "audio" / f"{lid}.mp3"
    if out.exists() and not force:
        log(f"{lid}: audio exists, skipping ({out.name}; use --force to regenerate)")
        return False
    out.parent.mkdir(parents=True, exist_ok=True)

    log(f"{lid}: requesting script from DeepSeek ...")
    script_text = llm.chat_with_retry(build_messages(lesson), temperature=0.8)
    lines = parse_script(script_text)
    words = sum(len(t.split()) for _, t in lines)
    log(f"{lid}: script received ({len(lines)} lines, {words} words)")
    if words < 500 or words > 1500:
        log(f"{lid}: warning - {words} words is outside the 750-1200 target range")

    workdir = Path(tempfile.gettempdir()) / f"podcast_{lid}"
    shutil.rmtree(workdir, ignore_errors=True)
    workdir.mkdir(parents=True, exist_ok=True)
    line_paths = []
    try:
        lines_json = workdir / "lines.json"
        with open(lines_json, "w", encoding="utf-8") as fh:
            json.dump([{"speaker": s, "text": t} for s, t in lines], fh, ensure_ascii=False)
        log(f"{lid}: running Qwen3-TTS ({len(lines)} lines, one model load) ...")
        run([
            QWEN_PYTHON, str(ROOT / "scripts" / "qwen3_tts.py"),
            "--lines", str(lines_json),
            "--out-dir", str(workdir),
            "--instruct-a", HOST_A_INSTRUCT,
            "--instruct-b", HOST_B_INSTRUCT,
            "--speed-a", "1.0",
            "--speed-b", "1.08",
        ])
        for i, (speaker, _) in enumerate(lines):
            line_paths.append(workdir / f"line{i}_{speaker}.wav")
        log(f"{lid}: assembling with ffmpeg ...")
        concat_audio(line_paths, out)
        duration = probe_duration(out)
        log(f"{lid}: done - {words} words, {int(duration // 60)}m{int(duration % 60):02d}s "
            f"({duration:.1f}s) -> {out}")
        return True
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate NotebookLM-style two-host lesson podcasts (DeepSeek + Qwen3-TTS + ffmpeg)."
    )
    parser.add_argument("--course", default=DEFAULT_COURSE, help=f"course id (default: {DEFAULT_COURSE})")
    parser.add_argument("--lesson", default=None, help="lesson id; if omitted, all lessons in the manifest")
    parser.add_argument("--force", action="store_true", help="regenerate audio even if the mp3 already exists")
    args = parser.parse_args(argv)

    if args.lesson:
        ids = [args.lesson]
    else:
        ids = course_lesson_ids(args.course)

    failures = 0
    for lid in ids:
        try:
            generate_lesson(args.course, lid, force=args.force)
        except Exception as e:  # keep going so one bad lesson does not block the rest
            failures += 1
            err(f"{lid}: {e}")
    if failures:
        err(f"{failures} lesson(s) failed")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
