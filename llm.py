#!/usr/bin/env python3
"""
llm.py — DeepSeek Chat Completions 客户端 (MathFlow)
====================================================
- API key 从环境变量 DEEPSEEK_API_KEY 读取, 绝不硬编码
- 默认 baseUrl: https://api.deepseek.com/v1, 模型: deepseek-v4-flash
- 可用环境变量覆盖: MATHFLOW_LLM_BASE_URL / MATHFLOW_LLM_MODEL / MATHFLOW_LLM_TIMEOUT
- 离线自测: MATHFLOW_LLM_MOCK=1 时返回预设内容, 不访问网络
"""

import json
import os
import urllib.error
import urllib.request

DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_TIMEOUT = 60


class LLMError(Exception):
    """LLM 调用失败 (网络/鉴权/格式)。message 可直接展示给用户。"""


def _api_key() -> str:
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key:
        raise LLMError(
            "未检测到 DEEPSEEK_API_KEY 环境变量。\n"
            "请先执行: export DEEPSEEK_API_KEY=sk-xxx\n"
            "(可在 https://platform.deepseek.com 获取 API key)"
        )
    return key


def _mock_content(messages):
    """Offline canned content. Only used when MATHFLOW_LLM_MOCK=1, for network-free end-to-end tests."""
    user = messages[-1]["content"] if messages else ""
    if "The learner's Lean code" in user:
        return (
            "Your Lean code did not compile. Common causes:\n"
            "① The proposition skeleton does not match the question (names, parentheses, argument order).\n"
            "② The tactic does not fit the goal (e.g. rfl only solves definitional equalities).\n"
            "③ The lemma name is misspelled or does not exist.\n"
            "Suggested fix: confirm the lemma with #check, align the proposition with the question, "
            "then pick the matching tactic. For natural addition, Mathlib provides Nat.add_comm."
        )
    if "next question" in user:
        return json.dumps({
            "title": "Associativity of natural addition",
            "explanation": "Associativity means the parentheses do not change the result. "
                           "For any natural numbers a b c, (a + b) + c = a + (b + c). "
                           "Together with commutativity it forms the basic algebraic properties of addition.",
            "question": "Which Lean proof correctly proves: for any a b c : Nat, (a + b) + c = a + (b + c)?",
            "hint": "Proposition skeleton: example (a b c : Nat) : (a + b) + c = a + (b + c) := ... "
                    "Use the Mathlib lemma Nat.add_assoc, or induction on c. No sorry.",
            "options": [
                {"label": "A", "code": "example (a b c : Nat) : (a + b) + c = a + (b + c) := by\n  exact Nat.add_assoc a b c"},
                {"label": "B", "code": "example (a b c : Nat) : (a + b) + c = a + (b + c) := by\n  exact Nat.add_assoc a c b"},
                {"label": "C", "code": "example (a b c : Nat) : (a + b) + c = a + (b + c) := by\n  rfl"},
                {"label": "D", "code": "example (a b c : Nat) : (a + b) + c = a + (b + c) := by\n  exact Nat.add_assoc b a c"},
            ],
            "answer": 0,
        }, ensure_ascii=False)
    return json.dumps({
        "title": "Commutativity of natural addition",
        "explanation": "Commutativity means the result does not depend on the order of operands. "
                       "For natural addition: for any a b : Nat, a + b = b + a. "
                       "This is not true by definitional equality (rfl will not solve it); "
                       "it needs induction or a lemma already proved in Mathlib.",
        "question": "Which Lean proof correctly proves: for any a b : Nat, a + b = b + a?",
        "hint": "Proposition skeleton: example (a b : Nat) : a + b = b + a := ... "
                "Strategy: use the Mathlib lemma Nat.add_comm, or induction. No sorry.",
        "options": [
            {"label": "A", "code": "example (a b : Nat) : a + b = b + a := by\n  exact Nat.add_comm a b"},
            {"label": "B", "code": "example (a b : Nat) : a + b = b + a := by\n  exact Nat.add_comm b a"},
            {"label": "C", "code": "example (a b : Nat) : a + b = b + a := by\n  rfl"},
            {"label": "D", "code": "example (a b : Nat) : a + b = b + a := by\n  exact Nat.add_assoc a b a"},
        ],
        "answer": 0,
    }, ensure_ascii=False)


def chat(messages, temperature=0.7):
    """
    调用 /chat/completions, 返回助手消息文本。
    失败抛 LLMError, message 为可直接展示的友好信息。
    """
    if os.environ.get("MATHFLOW_LLM_MOCK") == "1":
        return _mock_content(messages)

    key = _api_key()
    base = (os.environ.get("MATHFLOW_LLM_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
    model = os.environ.get("MATHFLOW_LLM_MODEL") or DEFAULT_MODEL
    try:
        timeout = int(os.environ.get("MATHFLOW_LLM_TIMEOUT") or DEFAULT_TIMEOUT)
    except ValueError:
        timeout = DEFAULT_TIMEOUT
    url = f"{base}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        # deepseek-v4-flash 是推理模型: reasoning_content 会占 token 配额,
        # 4096 会被思考吃光导致 content 为空; 调大到 8192 并限制推理强度
        # (reasoning_effort=low), 保证正式输出有足够空间 (finish_reason=stop)
        "max_tokens": 8192,
        "reasoning_effort": "low",
        "stream": False,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise LLMError(f"DeepSeek API 返回 HTTP {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise LLMError(f"无法连接 DeepSeek API ({url}): {e.reason}") from e
    except TimeoutError:
        raise LLMError(f"DeepSeek API 请求超时 ({timeout}s), 请稍后重试") from None
    except Exception as e:  # JSON 解析等其他异常, 保证不崩溃
        raise LLMError(f"DeepSeek API 调用失败: {e}") from e
    try:
        return body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise LLMError(f"DeepSeek API 返回格式异常: {str(body)[:300]}") from None


def chat_with_retry(messages, temperature=0.7, attempts=4, backoff=1.0):
    """chat() 的容错封装: DeepSeek 偶发返回空 content / 瞬时失败时自动重试。

    指数退避: 第 i 次重试前等待 backoff * 2^i 秒 (默认 1s, 2s, 4s)。
    返回非空文本; 重试耗尽后抛 LLMError。
    """
    import time
    last_err = None
    for i in range(attempts):
        try:
            text = chat(messages, temperature=temperature)
        except LLMError as e:
            last_err = e
            if i < attempts - 1:
                time.sleep(backoff * (2 ** i))
                continue
            raise
        if text and text.strip():
            return text
        last_err = LLMError(f"DeepSeek model returned empty content (attempt {i + 1}/{attempts})")
        if i < attempts - 1:
            time.sleep(backoff * (2 ** i))
    raise last_err
