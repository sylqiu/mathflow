#!/usr/bin/env python3
"""
qwen3_tts.py - batch TTS driver for Qwen3-TTS (MLX) podcasts.
=============================================================
Loads the Qwen3-TTS model ONCE, then generates one wav per line of a
lines.json file, so a whole podcast (30-60 lines) needs only a single model
load instead of one ~10-20 s load per line.

Input lines.json format:
  [{"speaker": "A"|"B", "text": "..."}, ...]

Output: <out_dir>/line<i>_<speaker>.wav  (i starting at 0)

Usage:
  python3 scripts/qwen3_tts.py --lines <lines.json> --out-dir <dir> \
      [--model <repo>] [--instruct-a "<desc>"] [--instruct-b "<desc>"] \
      [--sample-rate 24000] [--speed-a 1.0] [--speed-b 1.08]

English only. Requires the repo .venv-tts (Python 3.14, mlx-audio 0.5.0) and
the cached model mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-8bit.
"""

import argparse
import json
import sys
from pathlib import Path

DEFAULT_MODEL = "mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-8bit"
DEFAULT_INSTRUCT_A = (
    "A calm, warm female voice, natural conversational podcast host, "
    "clear and expressive, medium pitch"
)
DEFAULT_INSTRUCT_B = (
    "A friendly male voice, natural conversational podcast host, "
    "warm and engaging, medium-low pitch"
)
DEFAULT_SAMPLE_RATE = 24000


def log(msg):
    print(f"[qwen3_tts] {msg}", flush=True)


def err(msg):
    print(f"[qwen3_tts] error: {msg}", file=sys.stderr, flush=True)


def load_lines(path):
    try:
        with open(path, encoding="utf-8") as fh:
            items = json.load(fh)
    except (OSError, ValueError) as e:
        raise ValueError(f"cannot read lines JSON {path}: {e}") from e
    if not isinstance(items, list) or not items:
        raise ValueError(f"lines JSON {path} must be a non-empty list")
    lines = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"line {i}: expected an object, got {type(item).__name__}")
        speaker = str(item.get("speaker", "")).strip().upper()
        text = str(item.get("text", "")).strip()
        if speaker not in ("A", "B"):
            raise ValueError(f"line {i}: speaker must be \"A\" or \"B\", got {item.get('speaker')!r}")
        if not text:
            raise ValueError(f"line {i}: text is empty")
        lines.append((speaker, text))
    return lines


def generate_lines(lines, out_dir, model_repo, instruct_a, instruct_b, sample_rate, speed_a=1.0, speed_b=1.08):
    from mlx_audio.tts.generate import generate_audio
    from mlx_audio.tts.utils import load_model

    log(f"loading model {model_repo} (one load for {len(lines)} lines) ...")
    model = load_model(model_repo)
    log("model loaded")
    if hasattr(model, "sample_rate") and int(model.sample_rate) != int(sample_rate):
        log(f"warning: --sample-rate {sample_rate} ignored; model outputs at {model.sample_rate} Hz")
    log(f"sample rate: {getattr(model, 'sample_rate', sample_rate)} Hz")

    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, (speaker, text) in enumerate(lines):
        instruct = instruct_a if speaker == "A" else instruct_b
        prefix = out_dir / f"line{i}_{speaker}"
        words = len(text.split())
        generate_audio(
            model=model,
            text=text,
            instruct=instruct,
            file_prefix=str(prefix),
            audio_format="wav",
            join_audio=True,
            verbose=False,
            speed=speed_a if speaker == "A" else speed_b,
        )
        out_path = out_dir / f"line{i}_{speaker}.wav"
        if not out_path.is_file() or out_path.stat().st_size == 0:
            raise RuntimeError(f"generation produced no audio: {out_path}")
        paths.append(out_path)
        log(f"line {i} ({speaker}, {words} words) -> {out_path}")
    return paths


def main(argv=None):
    parser = argparse.ArgumentParser(description="Batch Qwen3-TTS (MLX) driver: many lines, one model load.")
    parser.add_argument("--lines", required=True, help="path to lines.json: [{\"speaker\": \"A\"|\"B\", \"text\": \"...\"}, ...]")
    parser.add_argument("--out-dir", required=True, help="directory for line<i>_<speaker>.wav outputs")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"model repo/path (default: {DEFAULT_MODEL})")
    parser.add_argument("--instruct-a", default=DEFAULT_INSTRUCT_A, help="voice description for host A")
    parser.add_argument("--instruct-b", default=DEFAULT_INSTRUCT_B, help="voice description for host B")
    parser.add_argument("--sample-rate", type=int, default=DEFAULT_SAMPLE_RATE,
                        help=f"expected output sample rate (default: {DEFAULT_SAMPLE_RATE})")
    parser.add_argument("--speed-a", type=float, default=1.0,
                        help="speed multiplier for host A lines (default: 1.0)")
    parser.add_argument("--speed-b", type=float, default=1.08,
                        help="speed multiplier for host B lines (default: 1.08)")
    args = parser.parse_args(argv)

    try:
        lines = load_lines(args.lines)
        paths = generate_lines(
            lines,
            Path(args.out_dir),
            args.model,
            args.instruct_a,
            args.instruct_b,
            args.sample_rate,
            args.speed_a,
            args.speed_b,
        )
    except Exception as e:
        err(str(e))
        return 1
    log(f"done - {len(paths)} wav(s) written to {args.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
