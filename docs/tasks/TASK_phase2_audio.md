# TASK_phase2_audio.md — MathFlow Course Mode Phase 2: NotebookLM-style lesson audio

## Context

- ZD approved the audio direction: **NotebookLM-style two-host podcast audio** for each lesson. Sample approved: `demo/audio/m1-three-theories-sample.mp3` (71 s, two voices, conversational).
- Working recipe (already validated on this machine):
  - TTS: `edge-tts` (installed in `~/Documents/mathflow/.venv`). Host A = `en-US-JennyNeural` (curious questioner, female), Host B = `en-US-GuyNeural` (expert explainer, male). Use `--rate=+6%`.
  - Assembly: generate each line as its own mp3, then `ffmpeg` concat with a **0.45 s silence gap** between lines (see sample build in `/tmp/mf_audio` if still present).
  - Output location: `data/courses/pseudorandomness-primer/media/audio/<lesson_id>.mp3` — the server's `/media/<course_id>/<path>` route already serves this directory, no server route change needed.
- Script generation: use DeepSeek (key at `~/.openclaw/agents/main/agent/models.json` → `providers.deepseek.apiKey`; model `deepseek/deepseek-v4-flash`, **max_tokens ≥ 4096** — reasoning model caveat). Reuse `llm.py` if it fits (it already wraps DeepSeek calls); otherwise read the key from that file directly. Communicate with DeepSeek in English.
- Content accuracy is the top priority: every claim must be grounded in the lesson JSON + `course_blueprint/prg08.txt`. Do not invent results, definitions, or section numbers.

## Deliverable A — `scripts/generate_podcast.py` (new file, in ~/Documents/mathflow/)

A CLI pipeline that produces the audio for one or all lessons:

```
usage: generate_podcast.py [--course pseudorandomness-primer] [--lesson <lid>] [--force]
```

- Reads each lesson JSON from `data/courses/<course>/lessons/<lid>.json` (kind `theory` and `mcq` both get podcasts; the checkpoint lesson gets a recap-style podcast).
- For each lesson, asks DeepSeek for a **conversational two-host script** (English), NotebookLM vibe:
  - Host A: curious learner who asks questions, expresses confusion, asks for examples.
  - Host B: expert who explains clearly, uses analogies, answers A's questions.
  - Natural back-and-forth, not a lecture. Include a 2–3 sentence recap at the end.
  - Target length **5–8 minutes** spoken (~750–1200 words). Include math read aloud naturally (e.g., "epsilon over p of n", "ell of n").
  - The prompt must include the lesson's title, body text (truncated sensibly), defs, theorems, and checkpoints so the conversation is grounded in the actual content.
- Parse the script into lines tagged `A:` / `B:` (or JSON `{"speaker": "A"|"B", "text": "..."}`).
- TTS each line with edge-tts (A = Jenny, B = Guy, rate +6%), write per-line mp3s to a temp dir (`/tmp/podcast_<lid>/`).
- Concat with ffmpeg: each line followed by 0.45 s silence → `data/courses/pseudorandomness-primer/media/audio/<lid>.mp3` (128 kbps, like the sample).
- Idempotent: skip lessons whose mp3 already exists unless `--force`. Log progress per lesson (words, duration). Exit non-zero on failure.
- English only: code, comments, strings.

## Deliverable B — player integration in `course_server.py` (edit only this file)

- In the lesson view HTML, if an audio file exists for the lesson, show an **`<audio controls>` player** near the top of the lesson body (under the title). Source = `/media/<course_id>/audio/<lid>.mp3`.
- The lesson JSON passed to the player should include a hint that audio exists (e.g., add `"audio": {"file": "<lid>.mp3"}` when the file is present on disk, or derive from the `/media` path). Keep it simple and consistent with existing JSON philosophy.
- Do NOT change the API route structure, the `/media` route, or any other `.py` file.

## Deliverable C — generate the audio

- Run the pipeline for **all 5 lessons** of `pseudorandomness-primer` (m1-three-theories, m1-general-paradigm, m2-prg-definition, m2-ci-definition, m1-m2-checkpoints).
- Each mp3 should land in `data/courses/pseudorandomness-primer/media/audio/` with size > 1 MB and duration ≈ 5–8 min.

## Constraints

- Python 3.9.6; stdlib for the server file. The generation script may use `edge-tts` (already in `.venv`) and the `ffmpeg` binary (`/opt/homebrew/bin/ffmpeg`).
- Do NOT modify `api_server.py`, `web.py`, `mathflow.py`, `prototype_fill.py`, or any lesson JSON content files (audio mp3s are fine to add; JSON edits only if required and minimal).
- Do NOT git commit.

## Verification (run these; paste outputs into the final report)

1. `~/Documents/mathflow/.venv/bin/python scripts/generate_podcast.py --lesson m2-ci-definition --force` → succeeds, logs words + duration.
2. `ffprobe -v quiet -show_entries format=duration -of csv=p=0 data/courses/pseudorandomness-primer/media/audio/m2-ci-definition.mp3` → ≈ 300–480 s.
3. `ls -la data/courses/pseudorandomness-primer/media/audio/` → all 5 mp3s present, each > 1 MB.
4. Start `python3 course_server.py 8788` (background), then:
   - `curl -s -o /dev/null -w "%{http_code}" localhost:8788/media/pseudorandomness-primer/audio/m2-ci-definition.mp3` → 200
   - `curl -s localhost:8788/ | grep -c "<audio"` → ≥ 1
5. Spot-check one podcast's accuracy: listen/transcribe 2–3 claims in the m2-ci-definition mp3 and confirm they match `course_blueprint/prg08.txt` §2.3.1. Note any deviation in the report.
