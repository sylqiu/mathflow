# MathFlow

AI 驱动的 Lean 4 数学研讨会：AI 讲解概念 → 你用 Lean 写证明 → 编译器实时验证。
An AI-powered Lean 4 math seminar: AI explains a concept → you write the proof in Lean → the compiler verifies it.

## Features

- **Seminar loop (研讨会闭环)**: AI (DeepSeek) explains a concept, poses a verification problem, you answer in Lean, Lean 4 compiles and verifies. Pass → next question; fail → AI explains your specific error.
- **Terminal REPL** (`mathflow.py`): `:seminar` mode, `:check` multi-line verification, `:info` type-checking, session accumulation in `sessions/<name>.lean`.
- **Web version** (`web.py`): single-file Python stdlib HTTP server, KaTeX rendering, dark mobile-friendly UI, multiple-choice / fill-in-the-blank answering for phone use.
- **Progressive session**: verified statements accumulate, so later problems can reference earlier definitions/theorems.

## Requirements

- Lean 4 (via elan) + Mathlib — `~/.elan/bin` on PATH
- Python 3.9+
- DeepSeek API key (or `MATHFLOW_LLM_MOCK=1` for offline testing)

## Quick start

```bash
# Terminal seminar
export DEEPSEEK_API_KEY=sk-...
python3 mathflow.py

# Web version
python3 web.py 8000          # then open http://localhost:8000
```

## Project layout

- `mathflow.py` — terminal REPL + seminar loop + Lean compile check
- `llm.py` — DeepSeek chat client (env-var key only, mock mode supported)
- `web.py` — browser UI wrapping the same loop
- `sessions/` — accumulated Lean session files (gitignored)
