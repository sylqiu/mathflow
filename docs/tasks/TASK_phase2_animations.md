# TASK_phase2_animations.md — MathFlow Course Mode Phase 2: P0 Manim animations

## Context

- Phase 1 delivered: `course_server.py` (port 8788, `/media` route ready), 5 lessons for M1/M2 in `data/courses/pseudorandomness-primer/`.
- Phase 2 priorities (decided by ZD): **animations & visual explanations FIRST**, then audio podcasts. The quantifier sorter is CANCELLED — do not build it.
- This task: write **3 P0 manim scene scripts**. Do NOT render (the human will render + verify frames and may send you iteration feedback).
- Environment (already working): Manim Community v0.19.0 in `~/Documents/mathflow/.venv`; TeX via tectonic shim at `demo/bin/pdflatex` (no LaTeX install needed); template `demo/euler_demo.py` (chalkboard style with `TEX_TEMPLATE` + `mt()` helper — reuse that pattern exactly).

## Deliverables (new files only, in ~/Documents/mathflow/)

- `demo/hybrid_chain.py`
- `demo/stat_vs_comp.py`
- `demo/prg_stretch.py`

## Scene specs

Source of truth for teaching points: `~/Documents/pseudorandom-course/APP-DESIGN.md` §3.4. Math accuracy: verify against `course_blueprint/prg08.txt` (do not invent results).

### 1. `hybrid_chain.py` — the most important animation of the course
- Teaching point: the hybrid argument. Distributions H₀,…,H_k form a chain; each hybrid flips one component from Y to X; the total distinguishing advantage is bounded by the sum of per-step advantages, each ≤ ε/k, so the whole chain has advantage ≤ ε. Triangle-inequality intuition.
- Suggested visuals: a grid/row of k+1 hybrid columns, each cell colored by source (X vs Y); a "flip" sweeps left → right changing one column at a time; a per-step advantage bar appears under each transition and a cumulative bar stays ≤ ε.
- Runtime ≤ 90 s.

### 2. `stat_vs_comp.py`
- Teaching point: two distributions whose **statistical distance is large** (a human eye sees clearly different histograms) yet that are **computationally indistinguishable** (every efficient test sees nearly identical projections) → computational indistinguishability ≠ statistical closeness.
- Suggested visuals: two histograms side by side, visibly different shapes; then a "distinguisher" — a coarse linear-functional projection — applied to both; the projected distributions overlap almost completely. Annotate: "Δ(X,Y) large (statistical)" vs "X ≡_c Y (computational)".
- Runtime ≤ 90 s.

### 3. `prg_stretch.py`
- Teaching point: a PRG stretches a k-bit seed to ℓ(k) > k bits; the range has only 2^k points — sparse in {0,1}^ℓ(k) — yet the output looks uniform to efficient observers.
- Suggested visuals: a small seed blob (k bits) → arrow labeled G → a long output string (ℓ(k) bits); draw the huge ambient space {0,1}^ℓ as a big rectangle containing only 2^k dots (visibly sparse); then zoom into a local region where the dots "look uniform" — annotate "value of G" vs "uniform" and the density 2^k / 2^ℓ = 2^{-(ℓ-k)}.
- Runtime ≤ 90 s.

## Style & constraints (same conventions as euler_demo.py)

- English only: code, comments, on-screen text.
- Chalkboard dark style; use the `mt()` MathTex helper with `TEX_TEMPLATE` for all math.
- Each file: one `Scene` class named after the file (`HybridChain`, `StatVsComp`, `PrgStretch`) with a `construct()` method using `self.play` / `self.wait`; total runtime ≤ 90 s at 720p30 (`-qm`).
- Each file starts with a module docstring containing: the teaching point, **2 before/after questions** (one "before" activation question, one "after" check question — the player will use these later), and the run command.
- Use relative paths only inside scene files; do not write files outside `demo/`.
- Do NOT modify any existing files (`euler_demo.py`, `course_server.py`, `api_server.py`, `web.py`, `mathflow.py`, `llm.py`, `prototype_fill.py`, lesson JSONs, etc.).
- Do NOT run manim. Do NOT git commit.

## Verification (the human will run these; you just deliver clean, importable files)

1. `cd ~/Documents/mathflow && .venv/bin/python -m py_compile demo/hybrid_chain.py demo/stat_vs_comp.py demo/prg_stretch.py` — no syntax errors.
2. Human renders with `../.venv/bin/manim -qm <file> <Scene>` from `demo/` and inspects frames; expect a possible iteration round with specific fix requests.
