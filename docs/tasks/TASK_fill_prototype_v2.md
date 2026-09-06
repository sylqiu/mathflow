# Task: Iterate on prototype_fill.py based on real-API findings

File: `~/Documents/mathflow/prototype_fill.py` (already exists, works). Do NOT modify `mathflow.py`, `web.py`, `llm.py`.

## Real-API verification findings (from operator's run)

| Goal | Result |
|---|---|
| commutativity of natural number addition | ✅ 3 distractors, perfect (swapped args all fail to compile) |
| associativity of function composition | ❌ 3 attempts, 0 distractors survived the judge |
| even plus even is even | ⚠️ attempt 1 failed (LLM used non-existent `Nat.Even`), attempt 2 OK but only 1 distractor |

Root causes identified:
1. **Zero mutation space**: for function composition associativity (a definitional equality), the LLM answered with `rfl` (or similar bare tactic). `rfl` has no arguments, no operators, no rw, no lemma name → every mutation is a no-op → 0 distractors.
2. **Non-standard mathlib names**: LLM wrote `Nat.Even` (doesn't exist); correct is `Even` (from Mathlib). The retry eventually self-corrected, but wasted an attempt.
3. **Small mutation space for structure answers**: `exact ⟨a + b, by ring⟩` only yielded 1 distractor because the answer form is a structure literal, not a lemma application.

## Changes to make (all inside prototype_fill.py)

### 1. Harden FILL_SYSTEM prompt
Add/strengthen constraints (keep the existing JSON contract unchanged):
- "The answer MUST be a named-lemma application with at least two explicit arguments, e.g. 'exact Nat.add_comm a b'. NEVER use a bare tactic (rfl, simp, trivial, omega, ring, aesop, tauto, linarith, exact rfl) as the answer, even when it would close the goal — rewrite the proof so the blank is a named-lemma application. If the statement is a definitional equality, still fill the blank with the lemma form (e.g. 'exact Function.comp_assoc f g h') rather than rfl."
- "Use ONLY standard mathlib names (e.g. Even, Nat.Even does not exist). Double-check every constant name against mathlib before outputting."
- Keep everything else (exactly one `___`, ≤60 chars, forbid sorry/axiom/admit, modest propositions).

### 2. Add a variable-substitution mutation operator (new priority e, after lemma name swap)
- Extract bound variable identifiers from the code template: regex `\(\s*([A-Za-z_][A-Za-z0-9_']*)\s*:` over `data["code"]` (only the header portion — collect the names before the first `:= by`, i.e. from the example/theorem signature). Example: for `example (a b : Nat) : ...`, variables = `[a, b]`.
- For each variable `v` in the answer fragment (regex `\b[a-z][A-Za-z0-9_']*\b` — lowercase-starting identifiers only, so lemma names like `Nat.add_comm` are never touched), and for each other variable `w` in the template's variable list: produce a single-variable substitution of `v` → `w` in the answer (replace ALL occurrences of that one variable), skip if result == answer. Add after the existing operators, deduped as before.
- Note: variables may be multi-char (e.g. `n`, `m`, `x`, `y`, `α`, `β`). The substitution must only replace whole tokens (word boundaries), not substrings.

### 3. Re-run verification and report
1. Mock mode: `MATHFLOW_LLM_MOCK=1 python3 prototype_fill.py` — must still work (canned answer `exact Nat.add_comm a b`, variables `a b`; the new operator should generate extra candidates; expect still exactly one OK option).
2. Real mode (operator runs this after you finish; you do NOT run real mode): nothing to do here — just leave the script ready.

## Constraints
- stdlib only, keep it clean, English comments. Do not commit or push. Only touch `prototype_fill.py`.
