#!/usr/bin/env python3
"""
MathFlow v0.1 — Lean 4 对话闭环 (终端 MVP)
==========================================
最小可行性闭环: AI 讲概念 → 你写 Lean 命题 → 编译验证 → 通过/讲解后重试

研讨会模式 (:seminar): AI (DeepSeek) 讲解概念并提问, 你用 Lean 作答,
Lean 编译验证, 通过则写入会话继续下一题, 失败则 AI 针对错误讲解后重试。

用法:
    python3 mathflow.py [session_name]      # 默认 session 名为 "default"

会话:
    sessions/<session_name>.lean  — 累加式环境, 已验证的内容持续累积,
                                    后续命题自动可以引用前面的定义/定理

命令 (以 : 开头):
    :check              进入多行输入模式, 粘贴 Lean 代码, 以单独一行 --END 结束
                        (粘贴时也可用空行 + Ctrl-D 结束)
    :info <expr>        用 #check 查看表达式类型, 如: :info Nat.add_comm
    :load <file>        加载一个 .lean 文件作为会话起点
    :show               打印当前会话内容
    :reset              清空会话 (仅清内存, 不删文件)
    :seminar [目标]     启动研讨会模式 (需设置 DEEPSEEK_API_KEY)
    :help               显示本帮助
    :quit               退出 (或 Ctrl-D)

示例:
    > :check
    ... example (a b : Nat) : a + b = b + a := Nat.add_comm a b
    ... --END
    ✅ 验证通过 — 已加入会话
"""

import os
import subprocess
import sys
import json
import re
from pathlib import Path

import llm

VERSION = "0.1.0"
BASE_DIR = Path(__file__).resolve().parent
SESSIONS_DIR = BASE_DIR / "sessions"
SESSIONS_DIR.mkdir(exist_ok=True)

# Lean 可执行文件: 优先用 lake env lean (mathlib 环境), 否则回退到裸 lean
def find_lean() -> str:
    for candidate in ["lake", "lean"]:
        p = os.path.expanduser(f"~/.elan/bin/{candidate}")
        if os.path.exists(p):
            return p
    return "lean"

LAKE = find_lean() if Path(find_lean()).name == "lake" else None
LEAN = find_lean()


def lean_cmd() -> list[str]:
    """返回运行 lean 的命令前缀 (自动处理 mathlib 环境)"""
    if LAKE and os.path.exists(BASE_DIR / "lakefile.toml"):
        return [LAKE, "env", "lean"]
    return [LEAN]


def _run_lean(code: str) -> subprocess.CompletedProcess:
    """把代码写入临时文件并运行 lean, 返回进程结果。"""
    tmp = BASE_DIR / ".tmp_check.lean"
    tmp.write_text(code + "\n", encoding="utf-8")
    return subprocess.run(
        lean_cmd() + [str(tmp)],
        capture_output=True, text=True, timeout=60,
        cwd=BASE_DIR,
    )


def _clean(output: str, tmp: Path) -> str:
    """去掉临时文件路径, 让报错更友好。"""
    out = output.replace(str(tmp), "<your code>")
    return out.replace(".tmp_check.lean", "<your code>")


def compile_check(code: str, session_code: str = "") -> tuple[bool, str]:
    """
    编译验证代码。
    session_code 是已累积的会话内容 (只读, 不会写入)。
    返回 (是否通过, 输出信息)。
    """
    tmp = BASE_DIR / ".tmp_check.lean"
    # 会话内容在前, 用户代码在后; 自动带 mathlib 环境
    full = "import Mathlib\n" + session_code + "\n" + code
    proc = _run_lean(full)
    # Lean 4 的错误/警告输出在 stdout (stderr 基本为空)
    out = _clean((proc.stdout or "") + (proc.stderr or ""), tmp).strip()
    if proc.returncode == 0:
        warns = [l for l in out.splitlines() if "warning" in l.lower()]
        return True, ("✅ Verified" + (f"\n⚠️ Warnings:\n{chr(10).join(warns)}" if warns else ""))
    return False, f"❌ Verification failed:\n{out}"


def info_check(expr: str, session_code: str = "") -> str:
    """对表达式运行 #check"""
    tmp = BASE_DIR / ".tmp_check.lean"
    try:
        proc = _run_lean("import Mathlib\n" + session_code + f"\n#check {expr}\n")
        out = _clean((proc.stdout or "") + (proc.stderr or ""), tmp).strip()
        if proc.returncode == 0:
            return f"📖 {expr}\n{out}" if out else f"📖 {expr}\n(无输出)"
        return f"❌ {expr}:\n{out}"
    except subprocess.TimeoutExpired:
        return "❌ 编译超时 (60s)"


class Session:
    def __init__(self, name: str):
        self.name = name
        self.path = SESSIONS_DIR / f"{name}.lean"
        self.code = ""
        if self.path.exists():
            self.code = self.path.read_text(encoding="utf-8")
            print(f"📂 会话 '{name}' 已加载 ({len(self.code.splitlines())} 行)")

    def add(self, code: str) -> None:
        self.code += "\n" + code.strip() + "\n"
        self.path.write_text(self.code, encoding="utf-8")
        print(f"💾 已写入 {self.path}")

    def reset(self) -> None:
        self.code = ""
        print("🗑️ 会话已清空 (内存中)")

    def show(self) -> None:
        print(f"--- 会话 '{self.name}' 内容 ---")
        print(self.code if self.code.strip() else "(空)")

    def last_statement(self) -> str:
        """返回会话最后一条非空语句 (用于给 LLM 提供上下文)。"""
        lines = [l for l in self.code.splitlines() if l.strip()]
        return lines[-1] if lines else ""


def read_multiline() -> str:
    """读取多行输入, 以单独一行 --END 结束"""
    lines = []
    print("📝 粘贴 Lean 代码, 以单独一行 --END 结束 (Ctrl-C 取消):")
    while True:
        try:
            line = input()
        except (EOFError, KeyboardInterrupt):
            print("\n--END--")
            break
        if line.strip() == "--END":
            break
        lines.append(line)
    return "\n".join(lines)


HELP = f"""MathFlow v{ VERSION } — Lean 4 对话闭环 (终端 MVP)

命令:
  :check              多行输入 Lean 代码并验证 (以 --END 结束)
  :info <expr>        #check 表达式类型, 如: :info Nat.add_comm
  :load <file>        加载 .lean 文件作为会话起点
  :show               显示会话内容
  :reset              清空会话
  :seminar [目标]     启动研讨会: AI 讲解 → 提问 → Lean 验证 (需 DEEPSEEK_API_KEY)
  :help               本帮助
  :quit               退出
"""


# ---------------- 研讨会模式 (AI 讲解 → 提问 → Lean 验证) ----------------

LESSON_SYSTEM = """You are the MathFlow math tutor, running a one-on-one seminar: "concept explanation -> question -> formal verification".

Environment: Lean 4 + Mathlib. Every question must be answerable by a Lean proposition + proof that passes compilation.

Requirements:
1. Explanation: in English, 150-300 words, conceptually accurate, aimed at a learner who can program and is new to Lean.
2. Question: in English, state the exact mathematical proposition to prove and ask the learner to pick the correct Lean proof from the options (or write their own).
3. Hint: give the Lean skeleton (proposition form, needed variables/premises) and a proof-strategy direction (which Mathlib lemmas may help, whether induction is needed). Never reveal which option is correct and never write the full proof.
4. Keep propositions simple: provable in one or two proof steps; prefer existing Mathlib lemmas (e.g. Nat.add_comm, Nat.add_assoc); avoid custom definitions.
5. Options: output 3-4 options as a JSON array "options": [{"label": "A", "code": "<Lean code>"}, ...]. Exactly ONE option is a complete, correct, compilable Lean proof of the stated proposition. The others must be TYPICAL MISTAKES that FAIL to compile: wrong lemma name, wrong argument order, missing variables, wrong proposition shape, wrong tactic (e.g. rfl where induction is needed), syntax errors, etc. Never use "sorry" or "admit" in any option (they compile but are not real proofs). Inside "code" strings, escape newlines as \\n and quotes as \\".
6. "answer": the 0-based index of the correct option inside "options". Server-side only: never mention it in the question, hint, or explanation.
7. Output ONLY one JSON object. No Markdown fences, no extra text.

JSON format (fields exactly):
{"title": "...", "explanation": "...", "question": "...", "hint": "...", "options": [{"label": "A", "code": "..."}, ...], "answer": <int>}"""

FIX_SYSTEM = """You are the MathFlow Lean tutor. The learner's Lean code failed to compile. Please:
1. Point out the error in English, quoting the key line from the compiler output when helpful.
2. Give targeted hints (variable declarations, lemma names, tactic choices, syntax, proof strategy) to guide the learner to fix it themselves.
3. Never hand over a complete working proof.
4. Output plain text (no JSON), 150-300 words."""


def _normalize_options(raw):
    """Normalize LLM-provided options into [{label, code}, ...]; return [] if invalid."""
    if isinstance(raw, dict):
        items = [{"label": k, "code": v} for k, v in raw.items()]
    elif isinstance(raw, list):
        items = raw
    else:
        return []
    out = []
    for item in items:
        if isinstance(item, str):
            code, label = item, ""
        elif isinstance(item, dict):
            code, label = item.get("code"), item.get("label")
        else:
            continue
        if not isinstance(code, str) or not code.strip():
            continue
        out.append({
            "label": (str(label or "").strip() or chr(ord("A") + len(out))),
            "code": code.strip(),
        })
    return out


def _normalize_answer(raw, n):
    """answer is the 0-based index of the correct option (server-side only)."""
    if isinstance(raw, bool):
        return None
    try:
        idx = int(raw)
    except (TypeError, ValueError):
        return None
    return idx if 0 <= idx < n else None


def parse_lesson(text: str) -> dict:
    """Parse the lesson JSON from the LLM; degrade to plain-text mode on failure.

    Backward compatible: parses "options" (and server-side "answer") when present,
    otherwise returns the original field set.
    """
    text = (text or "").strip()
    candidates = []
    # 1) Try the whole output directly
    candidates.append(text)
    # 2) Strip Markdown code fences, then parse
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if m:
        candidates.append(m.group(1).strip())
    # 3) Extract the longest brace block
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        candidates.append(m.group(0))
    for cand in candidates:
        try:
            data = json.loads(cand)
            if isinstance(data, dict) and "question" in data:
                lesson = {
                    "title": str(data.get("title") or "").strip(),
                    "explanation": str(data.get("explanation") or "(AI provided no explanation)").strip(),
                    "question": str(data.get("question") or "(AI provided no question)").strip(),
                    "hint": str(data.get("hint") or "").strip(),
                }
                options = _normalize_options(data.get("options"))
                if options:
                    lesson["options"] = options
                    answer = _normalize_answer(data.get("answer"), len(options))
                    if answer is not None:
                        lesson["answer"] = answer
                return lesson
        except ValueError:
            continue
    print("⚠️  AI output was not valid JSON - degraded to plain-text mode.")
    return {
        "title": "",
        "explanation": text or "(AI provided no explanation)",
        "question": "Based on the explanation above, write the corresponding Lean proposition and proof.",
        "hint": "Look up the lemmas you need, then structure the proposition and proof.",
    }


def generate_lesson(goal: str, last_proven: str = ""):
    """Call the LLM to generate a lesson (explanation + question + hint + options); None on failure."""
    extra = ""
    if last_proven:
        extra = (
            f"\n\nThe learner has already proved and verified: {last_proven}\n"
            "Please ask the next question on the same topic (slightly more advanced); do not repeat the previous one."
        )
    msgs = [
        {"role": "system", "content": LESSON_SYSTEM},
        {"role": "user", "content": f"Learning goal: {goal}{extra}"},
    ]
    # Double fault tolerance: chat_with_retry covers empty responses; retry all when parse degrades (non-JSON)
    for _ in range(3):
        try:
            text = llm.chat_with_retry(msgs, temperature=0.7, attempts=2)
        except llm.LLMError as e:
            print(f"⚠️  {e}")
            return None
        lesson = parse_lesson(text)
        if lesson.get("title") and "(AI provided no explanation)" not in (lesson.get("explanation") or ""):
            return lesson
    return lesson


def generate_fix_hint(goal: str, code: str, error: str, context: str = "") -> str:
    """Send the compile error to the LLM for a targeted explanation; fallback text when the LLM is down.

    context is optional extra context (e.g. which multiple-choice option was picked), prepended to the prompt.
    """
    msgs = [
        {"role": "system", "content": FIX_SYSTEM},
        {"role": "user", "content": (
            f"Learning goal: {goal}\n\n{context}"
            f"The learner's Lean code:\n```lean\n{code}\n```\n\n"
            f"Lean compiler error:\n```\n{error[-1500:]}\n```"
        )},
    ]
    try:
        text = llm.chat_with_retry(msgs, temperature=0.3).strip()
        return text or "(AI returned no explanation - compare your code with the compiler error above)"
    except llm.LLMError as e:
        return f"(AI explanation temporarily unavailable: {e})"


def run_seminar(sess, goal=None) -> None:
    """研讨会闭环: 讲解 → 提问 → 用户写 Lean → 验证 → 通过/讲解后重试。"""
    print("🎓 研讨会模式 — AI 讲解 → 你写 Lean 证明 → Lean 验证")
    print("   · 回答时多行输入, 以 --END 结束; 输入 :back 可放弃本轮")
    try:
        if goal is None:
            goal = input("🎯 学习目标 (如: 二元运算 / 自然数加法交换律): ").strip()
        if not goal or goal == ":back":
            print("↩️  未输入目标, 返回 REPL。")
            return
        topic = goal
        while True:
            lesson = generate_lesson(topic, sess.last_statement())
            if lesson is None:
                print("❌ 无法生成教学内容, 返回 REPL。")
                return
            print(f"\n📚 概念讲解 — {lesson['title'] or topic}")
            print("-" * 44)
            print(lesson["explanation"])
            print("\n❓ 验证问题")
            print("-" * 44)
            print(lesson["question"])
            if lesson["hint"]:
                print("\n💡 期望形式提示")
                print("-" * 44)
                print(lesson["hint"])
            # 作答 + 验证循环
            while True:
                print("\n✍️  请写出你的 Lean 答案 (以 --END 结束, :back 放弃本轮):")
                code = read_multiline()
                if any(l.strip() == ":back" for l in code.splitlines()):
                    print("↩️  已放弃本轮作答。")
                    break
                if not code.strip():
                    print("(输入为空, 请重新输入)")
                    continue
                ok, msg = compile_check(code, sess.code)
                print(msg)
                if ok:
                    sess.add(code)
                    print("🎉 回答正确! 已写入会话。")
                    break
                hint = generate_fix_hint(topic, code, msg)
                print("\n🧑‍🏫 AI 讲解 (针对你的错误):")
                print("-" * 44)
                print(hint)
                print("↻ 请根据提示修改后重试。")
            choice = input("\n[继续下一题 n / 换目标 g / 退出 q] > ").strip().lower()
            if choice in ("q", "quit", "exit", "退出"):
                break
            if choice in ("g", "goal", "换目标"):
                new = input("🎯 新学习目标: ").strip()
                if new:
                    topic = new
                else:
                    print("(目标未变, 继续出下一题)")
    except KeyboardInterrupt:
        print("\n↩️  研讨会已中断。")
    print("👋 研讨会结束, 回到 REPL。")


def repl(session_name: str = "default") -> None:
    sess = Session(session_name)
    print(HELP)
    while True:
        try:
            line = input(f"[{sess.name}] lean> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 再见!")
            break
        if not line:
            continue
        if line == ":quit":
            print("👋 再见!")
            break
        elif line == ":help":
            print(HELP)
        elif line == ":check":
            code = read_multiline()
            if not code.strip():
                print("(空输入, 跳过)")
                continue
            ok, msg = compile_check(code, sess.code)
            print(msg)
            if ok and "warning" not in msg:
                sess.add(code)
        elif line.startswith(":info "):
            print(info_check(line[6:].strip(), sess.code))
        elif line == ":seminar" or line.startswith(":seminar "):
            goal = line[len(":seminar "):].strip() if line.startswith(":seminar ") else None
            run_seminar(sess, goal)
        elif line.startswith(":load "):
            p = Path(line[6:].strip())
            if not p.exists():
                p = BASE_DIR / p
            if p.exists():
                sess.code = p.read_text(encoding="utf-8")
                print(f"📂 已加载 {p} ({len(sess.code.splitlines())} 行)")
            else:
                print(f"❌ 找不到文件: {p}")
        elif line == ":show":
            sess.show()
        elif line == ":reset":
            sess.reset()
        else:
            # 当作单行 Lean 代码直接验证
            ok, msg = compile_check(line, sess.code)
            print(msg)
            if ok and "warning" not in msg and not line.startswith("#"):
                sess.add(line)


def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else "default"
    # 安全化会话名
    name = "".join(c for c in name if c.isalnum() or c in "-_")
    if not name:
        name = "default"
    repl(name)


if __name__ == "__main__":
    main()
