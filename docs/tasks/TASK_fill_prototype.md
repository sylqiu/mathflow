# Task: Build a fill-in-the-blank question prototype for MathFlow

Work in `~/Documents/mathflow`. Do **NOT** modify `mathflow.py`, `web.py`, or `llm.py` — create a new standalone script `prototype_fill.py` that imports from them (`mathflow.compile_check`, `llm.chat_with_retry`).

## New architecture (replaces the old MCQ idea)

The old approach made the LLM craft 4 mutually-competitive options + answer, then compile-check them. It was slow (80-220s with retries) and fragile.

The new approach:
- The LLM only generates the question + the ONE correct answer fragment (it's good at this).
- Distractors are synthesized by **deterministic string mutations** of the correct answer (pure Python).
- The Lean compiler is the judge: a mutated fragment that STILL compiles when substituted into the code template is DISCARDED (it would be a second correct answer → ambiguity). Fragments that FAIL to compile become distractors.

Result: "exactly one correct fill" is guaranteed by construction + compilation, not by LLM virtue.

## Script spec (`prototype_fill.py`)

### 1) FILL_SYSTEM prompt (defined inside prototype_fill.py)
Instructs the LLM to output ONLY a JSON object:
```json
{
  "title": "short title",
  "explanation": "2-4 sentence concept explanation",
  "question": "asks the learner to fill the blank ___ in the code below; describe what the fragment should be",
  "hint": "strategy hint",
  "code": "a complete Lean example/theorem whose proof contains exactly one blank marked with three underscores ___, e.g. \"example (a b : Nat) : a + b = b + a := by\n  ___\"",
  "answer": "the exact short fragment that makes the code compile when substituted at ___, e.g. \"exact Nat.add_comm a b\"",
  "lemma_pool": ["2-4 sibling lemma names near the one used in the answer, e.g. Nat.add_assoc, Nat.mul_comm — optional; the judge decides; the LLM does NOT need to control compilation"]
}
```
Prompt constraints:
- exactly one `___` in `code`
- `answer` must be a SHORT fragment (≤ ~60 chars: one tactic call or one expression), not a whole proof
- forbid `sorry`, `axiom`, `admit`
- keep propositions modest (mathlib lemmas or simple induction) so they compile in mathlib's lake env
- output raw JSON, no markdown fences

### 2) Distractor synthesis (pure Python, deterministic, priority order)
Applied to `answer`; skip any result identical to the answer or already kept. Dedupe.

a. **Argument mutations** on lemma applications. Detect a Lean application with a regex over the last whitespace-separated token group: `name` = leading identifier starting with an uppercase letter or dotted namespace (e.g. `Nat.add_comm`), `args` = following identifier tokens. Then:
   - swap each adjacent arg pair (`Nat.add_comm a b` → `Nat.add_comm b a`)
   - reverse the whole arg list
   - drop first arg; drop last arg

b. **Operator swap** inside the fragment, small table `{"+":"*", "*":"+", "-":"+", "=":"≤", "≤":"=", "∧":"∨", "∨":"∧"}`; keep if the result differs.

c. **Rewrite direction flip**: `rw [X]` → `rw [← X]`, and `rw [← X]` → `rw [X]` (only when the fragment contains `rw`).

d. **Lemma name swap**: if the answer contains an identifier and `lemma_pool` is non-empty, replace that identifier with each pool name.

### 3) The judge (only source of truth)
For each candidate fragment, substitute into `code` at the single `___` marker, run `mathflow.compile_check(filled_code, "")`.
- compiles → DISCARD (valid fill → ambiguity)
- fails → distractor; keep a short (≤120 char) first-line snippet of the error for reporting

Also compile the TRUE answer first: if the true answer does NOT compile, this question is an LLM failure → print why and retry generation (up to 3 attempts, mirroring `generate_lesson`).

### 4) Question assembly
1 correct + up to 3 distractors (in priority order). If 0 distractors were found, the question is unusable → print why and retry generation (up to 3 times). If 1-3 distractors, accept with however many we got.

### 5) CLI
```
python3 prototype_fill.py ["goal1" "goal2" "goal3"]
```
Default goals: `["commutativity of natural number addition", "associativity of function composition", "even plus even is even"]`.

Per goal: attempt up to 3 questions, stop at first success. Per question print:
- title, question, code template (with `___`)
- options A/B/C/D with fragments, correct one marked
- compile verdicts: OK / FAIL + first error line
- timing: LLM call seconds, compile seconds

End summary: per-goal success, avg LLM seconds, avg compile seconds, mutation hit rate (distractors kept / candidates judged).

### 6) Mock mode
If env `MATHFLOW_LLM_MOCK=1`, prototype_fill.py must NOT hit the network; return a canned FILL JSON (write one realistic example: commutativity of natural addition, code template with `___`, answer `exact Nat.add_comm a b`, lemma_pool `["Nat.add_assoc", "Nat.mul_comm", "Nat.add_left_comm"]`). Same contract as llm.py's mock. Used for offline verification.

### 7) Verification (run these and report output)
1. Mock mode: `MATHFLOW_LLM_MOCK=1 python3 prototype_fill.py` — expect exactly one option compiles, swapped-arg distractor present.
2. Real mode: export `DEEPSEEK_API_KEY` (ask the operator for it if not set) then `python3 prototype_fill.py` with the 3 default goals. May take minutes; that's fine.

## Constraints
- Python 3.9+ stdlib only, no new dependencies.
- Self-contained, clean, ~250-350 lines. Code comments in English (UI strings can be English too for this prototype).
- Do NOT commit or push; just leave the new file.
