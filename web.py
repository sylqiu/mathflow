#!/usr/bin/env python3
"""
MathFlow Web — the seminar loop in your browser
================================================
Single-file web app (Python 3.9+ stdlib http.server). Reuses mathflow.py and llm.py
without changing their existing logic.

Answer modes:
  - Multiple choice: the AI generates 3-4 Lean-code options (one correct proof, the
    rest typical mistakes); tap an option to submit it through the normal verification flow.
  - Free input: write the Lean code yourself (fallback, always available).

API:
  POST /api/seminar/start  {"goal": "..."}  → generate a lesson {title, explanation, question, hint, options?}
  POST /api/answer         {"code": "...", "option": "A"} → compile-check; on success write to the session and
                                auto-generate the next lesson; on failure return an AI explanation
  POST /api/check          {"code": "..."}  → check only, no session write (REPL style)
  POST /api/next           {"goal": "..."}  → skip the current question (optionally with a new goal)
  POST /api/reset                            → reset the session (including the persisted file)
  GET  /api/session                          → current session state
  GET  /                                    → single-page UI (dark, responsive, KaTeX math)

Run:
  MATHFLOW_LLM_MOCK=1 python3 web.py 8000            # offline self-test
  DEEPSEEK_API_KEY=sk-xxx python3 web.py [port]      # real LLM
"""

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

import mathflow
import llm

BASE_DIR = Path(__file__).resolve().parent


def _parse_port() -> int:
    if len(sys.argv) > 1:
        try:
            return int(sys.argv[1])
        except ValueError:
            print(f"⚠️  Invalid port: {sys.argv[1]}, using default 8000")
    return 8000


PORT = _parse_port()

# Single global session (plenty for this web build); the lock keeps it consistent across requests.
STATE_LOCK = threading.Lock()
SESS = mathflow.Session("web")
TOPIC = ""          # current learning goal
LESSON = None       # current lesson (may carry server-side "answer" index — never sent to the client)
QNO = 0             # current question number (UI display only)


def check_code(code: str, session_code: str) -> tuple[bool, str]:
    """Wrap mathflow.compile_check, turning timeouts/missing Lean into friendly messages."""
    try:
        return mathflow.compile_check(code, session_code)
    except subprocess.TimeoutExpired:
        return False, "❌ Verification failed: Lean compilation timed out (60s). Simplify the code and try again."
    except FileNotFoundError as e:
        return False, f"❌ Verification failed: Lean executable not found ({e.filename}). Install Lean 4 via elan first."
    except Exception as e:
        return False, f"❌ Verification failed: compiler error ({e})."


def llm_unavailable_message() -> str:
    return ("❌ AI service unavailable — could not generate lesson content. "
            "Set DEEPSEEK_API_KEY and retry, or use MATHFLOW_LLM_MOCK=1 for offline mode.")


def _clear_session_file() -> None:
    """Also clear the persisted session file on reset, so old content isn't reloaded on next start."""
    p = SESS.path
    if p.exists():
        try:
            p.unlink()
        except OSError:
            pass


def _with_index(lesson):
    """Attach the question number for the UI. The server-only 'answer' field must never leave the server."""
    if lesson is None:
        return None
    out = {k: v for k, v in lesson.items() if k != "answer"}
    out["index"] = QNO
    return out


def _generate_lesson_with_retry(goal: str, last_proven: str = "") -> Optional[dict]:
    """Generate a lesson; retry once when the LLM returns empty/truncated output."""
    for attempt in range(2):
        lesson = mathflow.generate_lesson(goal, last_proven)
        if lesson is None:
            return None
        text = ((lesson.get("explanation") or "") + (lesson.get("question") or "")).strip()
        # Treat empty content, raw JSON echoes, or the plain-text fallback as failures and retry.
        if text and lesson.get("title") and "no explanation" not in text and not text.lstrip().startswith("{"):
            return lesson
    return lesson


HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MathFlow Seminar · Web</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"></script>
<style>
  :root { --bg:#0f1115; --panel:#171a21; --line:#2a2f3a; --fg:#e6e9ef; --dim:#8b93a3;
          --green:#3fb96f; --red:#e05555; --blue:#5b9dff; --mono:ui-monospace,Menlo,Consolas,monospace; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--fg); font:15px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }
  .wrap { max-width:880px; margin:0 auto; padding:22px 16px 90px; }
  header { display:flex; align-items:baseline; gap:10px; flex-wrap:wrap; }
  h1 { font-size:20px; margin:0; }
  .badge { font-size:11px; color:var(--dim); border:1px solid var(--line); border-radius:20px; padding:1px 10px; }
  .sub { color:var(--dim); font-size:13px; margin:6px 0 18px; }
  .card { background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:16px; margin-bottom:14px; }
  .lbl { font-size:12px; color:var(--dim); margin-bottom:8px; text-transform:uppercase; letter-spacing:.5px; }
  .title { font-size:17px; font-weight:600; margin-bottom:12px; color:var(--blue); }
  .section { margin-bottom:12px; }
  .section b { display:block; color:var(--dim); font-size:13px; margin-bottom:4px; }
  .hint { color:var(--dim); font-size:14px; border-left:3px solid var(--blue); padding-left:10px; }
  textarea { width:100%; min-height:140px; background:#0c0e12; color:var(--fg);
             border:1px solid var(--line); border-radius:8px; padding:10px;
             font-family:var(--mono); font-size:13.5px; resize:vertical; }
  textarea:focus { outline:none; border-color:var(--blue); }
  .row { display:flex; gap:8px; margin-top:10px; flex-wrap:wrap; }
  button { background:#232836; color:var(--fg); border:1px solid var(--line); border-radius:8px;
           padding:8px 16px; font-size:14px; cursor:pointer; }
  button:hover { border-color:var(--blue); }
  button.primary { background:var(--blue); border-color:var(--blue); color:#fff; }
  button:disabled { opacity:.45; cursor:not-allowed; }
  input[type=text] { flex:1; min-width:220px; background:#0c0e12; color:var(--fg);
           border:1px solid var(--line); border-radius:8px; padding:9px 12px; font-size:14px; }
  input[type=text]:focus { outline:none; border-color:var(--blue); }
  .tabs { display:flex; gap:8px; margin-bottom:12px; flex-wrap:wrap; }
  .tab { border-radius:20px; padding:6px 14px; font-size:13px; }
  .tab.active { background:var(--blue); border-color:var(--blue); color:#fff; }
  .opts { display:flex; flex-direction:column; gap:10px; }
  .optbtn { display:block; width:100%; text-align:left; background:#0c0e12; border:1px solid var(--line);
            border-radius:10px; padding:10px 12px; font-size:13.5px; cursor:pointer; line-height:1.5; }
  .optbtn:hover { border-color:var(--blue); }
  .optbtn:disabled { opacity:.45; cursor:not-allowed; }
  .optlabel { display:inline-block; min-width:24px; height:24px; line-height:24px; text-align:center;
              background:var(--panel); border:1px solid var(--line); border-radius:50%;
              font-weight:600; font-size:12px; margin-right:10px; vertical-align:top; }
  .optcode { display:block; margin-top:6px; white-space:pre-wrap; word-break:break-word;
             font-family:var(--mono); font-size:12.5px; color:var(--fg); }
  .result { white-space:pre-wrap; font-family:var(--mono); font-size:13px; border-radius:8px;
            padding:12px; margin-top:12px; display:none; }
  .result.ok { display:block; background:#12301f; border:1px solid var(--green); color:#b7e8c9; }
  .result.fail { display:block; background:#331518; border:1px solid var(--red); color:#f2c4c4; }
  .result.info { display:block; background:#12233a; border:1px solid var(--blue); color:#c4d9f2; }
  .spin { color:var(--dim); font-size:13px; margin-top:8px; display:none; }
  .katex { font-size:1.05em; }
  .statusline { color:var(--dim); font-size:12.5px; margin-top:10px; min-height:18px; }
  pre.session { white-space:pre-wrap; font-family:var(--mono); font-size:12.5px; background:#0c0e12;
                border:1px solid var(--line); border-radius:8px; padding:10px; max-height:260px; overflow:auto; }
  .empty { color:var(--dim); }
  .meta { font-size:12.5px; color:var(--dim); font-weight:normal; text-transform:none; letter-spacing:0; }
  @media (max-width:600px) {
    .wrap { padding:14px 10px 80px; }
    .row button { flex:1; }
    .tabs { gap:6px; }
  }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>🎓 MathFlow Seminar</h1>
    <span class="badge">Web Beta</span>
  </header>
  <div class="sub">AI explains a concept → pick the correct Lean proof or write your own → verified by Lean · A correct answer unlocks the next question</div>

  <div class="card">
    <div class="lbl">Learning goal</div>
    <div class="row">
      <input type="text" id="goal" placeholder="e.g. commutativity of natural addition / binary operations / function composition" autocomplete="off">
      <button class="primary" id="btnStart" onclick="startSeminar()">Start</button>
      <button id="btnNext" onclick="nextLesson()">Skip / Next</button>
    </div>
    <div class="statusline" id="status"></div>
  </div>

  <div class="card" id="lessonCard" style="display:none">
    <div class="title" id="lessonTitle"></div>
    <div class="section"><b>📖 Concept</b><div id="lessonExpl"></div></div>
    <div class="section"><b>❓ Question</b><div id="lessonQ"></div></div>
    <div class="section"><b>💡 Hint</b><div class="hint" id="lessonHint"></div></div>
  </div>

  <div class="card" id="answerCard" style="display:none">
    <div class="tabs">
      <button type="button" id="tabOptions" class="tab active" onclick="switchTab('options')">Choose an answer</button>
      <button type="button" id="tabWrite" class="tab" onclick="switchTab('write')">Write code yourself</button>
    </div>

    <div id="panelOptions">
      <div class="lbl">Pick the correct Lean proof</div>
      <div class="opts" id="optionsBox"></div>
    </div>

    <div id="panelWrite" style="display:none">
      <div class="lbl">Your Lean code <span class="meta">(Ctrl/Cmd + Enter to submit)</span></div>
      <textarea id="code" placeholder="example (a b : Nat) : a + b = b + a := by&#10;  exact Nat.add_comm a b" spellcheck="false"></textarea>
      <div class="row">
        <button class="primary" id="btnAnswer" onclick="submitAnswer()">Verify &amp; submit</button>
        <button id="btnCheck" onclick="checkOnly()">Check only</button>
      </div>
    </div>

    <div class="row">
      <button id="btnReset" onclick="resetAll()">Reset session</button>
    </div>
    <div class="result" id="result"></div>
    <div class="spin" id="spin">⏳ Compiling / AI generating — please wait…</div>
  </div>

  <div class="card" id="sessionCard" style="display:none">
    <div class="row" style="justify-content:space-between;margin-top:0">
      <div class="lbl" style="margin:0">📄 Proven so far <span class="meta" id="sessionMeta"></span></div>
      <button id="btnRefresh" onclick="refreshSession()">Refresh</button>
    </div>
    <pre class="session" id="sessionCode"><span class="empty">Nothing proven yet</span></pre>
  </div>
</div>

<script>
function renderMath(el) {
  if (window.renderMathInElement) {
    renderMathInElement(el, {delimiters:[{left:'$$',right:'$$',display:true},{left:'$',right:'$',display:false}],throwOnError:false});
  }
}
function $(id) { return document.getElementById(id); }
function setStatus(t) { $('status').textContent = t; }
function show(el) { el.style.display = 'block'; }
function hide(el) { el.style.display = 'none'; }

async function api(path, body) {
  const r = await fetch(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body||{})});
  return r.json();
}

function renderOptions(l) {
  const box = $('optionsBox');
  box.innerHTML = '';
  const opts = (l.options || []).filter(function (o) { return o && o.code && String(o.code).trim(); });
  if (opts.length < 2) {
    $('tabOptions').style.display = 'none';
    switchTab('write');
    return;
  }
  $('tabOptions').style.display = '';
  opts.forEach(function (o, i) {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'optbtn';
    const lab = document.createElement('span');
    lab.className = 'optlabel';
    lab.textContent = o.label || String.fromCharCode(65 + i);
    const pre = document.createElement('code');
    pre.className = 'optcode';
    pre.textContent = o.code;
    b.appendChild(lab);
    b.appendChild(pre);
    b.addEventListener('click', function () { submitOption(o); });
    box.appendChild(b);
  });
  switchTab('options');
}

function switchTab(which) {
  $('tabOptions').classList.toggle('active', which === 'options');
  $('tabWrite').classList.toggle('active', which === 'write');
  $('panelOptions').style.display = which === 'options' ? 'block' : 'none';
  $('panelWrite').style.display = which === 'write' ? 'block' : 'none';
}

function showLesson(l) {
  $('lessonTitle').textContent = (l.title || 'Lesson') + (l.index ? ' · Q' + l.index : '');
  $('lessonExpl').textContent = l.explanation || '';
  $('lessonQ').textContent = l.question || '';
  $('lessonHint').textContent = l.hint ? ('💡 ' + l.hint) : 'No hint provided — try sketching the proposition first';
  renderOptions(l);
  show($('lessonCard'));
  renderMath($('lessonCard'));
}

function showResult(text, cls) {
  const el = $('result');
  el.className = 'result ' + cls;
  el.textContent = text;
  show(el);
}

function busy(on) {
  $('spin').style.display = on ? 'block' : 'none';
  ['btnAnswer','btnStart','btnNext','btnCheck','btnRefresh','btnReset'].forEach(function (id) {
    $(id).disabled = on;
  });
  document.querySelectorAll('.optbtn,.tab').forEach(function (el) { el.disabled = on; });
}

async function startSeminar() {
  const goal = $('goal').value.trim();
  if (!goal) { setStatus('⚠️ Enter a learning goal first'); return; }
  busy(true); hide($('result'));
  try {
    const d = await api('/api/seminar/start', {goal});
    if (d.error) { showResult(d.error, 'fail'); return; }
    showLesson(d.lesson);
    show($('answerCard'));
    show($('sessionCard'));
    setStatus('Topic: ' + d.topic + ' — pick a proof or write your own');
    refreshSession();
  } finally { busy(false); }
}

async function submitAnswer() {
  const code = $('code').value;
  if (!code.trim()) { showResult('Please enter some Lean code first', 'fail'); return; }
  busy(true); hide($('result'));
  try {
    const d = await api('/api/answer', {code: code});
    if (d.error) { showResult(d.error, 'fail'); return; }
    if (d.ok) {
      showResult(d.message, 'ok');
      if (d.lesson) { setTimeout(function () { showLesson(d.lesson); }, 150); setStatus('✅ Correct! Next question coming up'); }
      else { setStatus(d.notice || '✅ Correct! Added to session'); }
      refreshSession();
    } else {
      showResult(d.message + '\n\n🧑‍🏫 AI explanation:\n' + (d.hint || 'AI explanation unavailable — review the compile error above'), 'fail');
      setStatus('Not correct yet — read the explanation and try again');
    }
  } finally { busy(false); }
}

async function submitOption(o) {
  busy(true); hide($('result'));
  try {
    const d = await api('/api/answer', {code: o.code, option: o.label || ''});
    if (d.error) { showResult(d.error, 'fail'); return; }
    if (d.ok) {
      showResult(d.message, 'ok');
      if (d.lesson) { setTimeout(function () { showLesson(d.lesson); }, 150); setStatus('✅ Correct! Next question coming up'); }
      else { setStatus(d.notice || '✅ Correct! Added to session'); }
      refreshSession();
    } else {
      showResult(d.message + '\n\n🧑‍🏫 AI explanation:\n' + (d.hint || 'AI explanation unavailable — review the compile error above'), 'fail');
      setStatus('Not correct yet — read the explanation and try again');
    }
  } finally { busy(false); }
}

async function nextLesson() {
  const goal = $('goal').value.trim();
  busy(true); hide($('result'));
  try {
    const d = await api('/api/next', goal ? {goal: goal} : {});
    if (d.error) { showResult(d.error, 'fail'); return; }
    showLesson(d.lesson);
    setStatus('Next question ready');
  } finally { busy(false); }
}

async function checkOnly() {
  const code = $('code').value;
  if (!code.trim()) return;
  busy(true); hide($('result'));
  try {
    const d = await api('/api/check', {code: code});
    showResult(d.message, d.ok ? 'ok' : 'fail');
  } finally { busy(false); }
}

async function refreshSession() {
  try {
    const r = await fetch('/api/session');
    const d = await r.json();
    $('sessionMeta').textContent = d.lines ? (d.lines + ' line' + (d.lines === 1 ? '' : 's')) : '';
    $('sessionCode').textContent = d.code.trim() || 'Nothing proven yet';
  } catch (e) {}
}

async function resetAll() {
  busy(true);
  try {
    const d = await api('/api/reset', {});
    if (d.error) { showResult(d.error, 'fail'); return; }
    $('code').value = '';
    hide($('result'));
    hide($('lessonCard'));
    hide($('answerCard'));
    setStatus('Session reset — enter a new goal to start over');
    refreshSession();
  } finally { busy(false); }
}

$('code').addEventListener('keydown', function (e) {
  if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') submitAnswer();
});
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # compact logs
        sys.stderr.write("[web] %s\n" % (fmt % args))

    def _send(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self, limit=1 << 20):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if n <= 0 or n > limit:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            body = HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/session":
            with STATE_LOCK:
                self._send({
                    "topic": TOPIC,
                    "lesson": LESSON.get("title", "") if LESSON else "",
                    "qno": QNO,
                    "code": SESS.code,
                    "lines": len([l for l in SESS.code.splitlines() if l.strip()]),
                })
            return
        self._send({"error": "unknown endpoint"}, 404)

    def do_POST(self):
        global TOPIC, LESSON, QNO
        path = self.path.split("?")[0]
        data = self._read_json()
        try:
            if path == "/api/seminar/start":
                goal = (data.get("goal") or "").strip()
                if not goal:
                    self._send({"error": "Missing learning goal (field: goal)."})
                    return
                with STATE_LOCK:
                    TOPIC = goal
                    QNO = 1
                    LESSON = _generate_lesson_with_retry(goal, SESS.last_statement())
                if LESSON is None:
                    self._send({"error": llm_unavailable_message()})
                    return
                self._send({"lesson": _with_index(LESSON), "topic": TOPIC})

            elif path == "/api/answer":
                code = (data.get("code") or "").strip()
                option = (data.get("option") or "").strip()
                if not code:
                    self._send({"ok": False, "message": "❌ Please enter some Lean code."})
                    return
                with STATE_LOCK:
                    ok, msg = check_code(code, SESS.code)
                    if ok:
                        SESS.add(code)
                        QNO += 1
                        next_lesson = _generate_lesson_with_retry(TOPIC or "mathematical proof", SESS.last_statement())
                        LESSON = next_lesson
                        resp = {"ok": True, "message": "✅ Verified — added to session" + (f" (option {option})" if option else "")}
                        if next_lesson is None:
                            resp["notice"] = ("✅ Added to session, but the AI could not generate the next question "
                                              "right now (check DEEPSEEK_API_KEY / network). Use “Skip / Next” to retry later.")
                        else:
                            resp["lesson"] = _with_index(next_lesson)
                    else:
                        context = ""
                        if option:
                            context = (f"Multiple-choice answer: the learner picked option {option}. "
                                       "Explain why this code does not prove the stated question.\n\n")
                        hint = mathflow.generate_fix_hint(TOPIC or "mathematical proof", code, msg, context=context)
                        resp = {"ok": False, "message": msg, "hint": hint}
                self._send(resp)

            elif path == "/api/next":
                goal = (data.get("goal") or "").strip()
                with STATE_LOCK:
                    if goal:
                        TOPIC = goal
                    topic = TOPIC or "mathematical proof"
                    QNO += 1
                    LESSON = _generate_lesson_with_retry(topic, SESS.last_statement())
                if LESSON is None:
                    self._send({"error": llm_unavailable_message()})
                    return
                self._send({"lesson": _with_index(LESSON), "topic": TOPIC})

            elif path == "/api/check":
                code = (data.get("code") or "").strip()
                if not code:
                    self._send({"ok": False, "message": "❌ Please enter some Lean code."})
                    return
                ok, msg = check_code(code, SESS.code)
                self._send({"ok": ok, "message": msg})

            elif path == "/api/reset":
                with STATE_LOCK:
                    SESS.reset()
                    _clear_session_file()
                    TOPIC = ""
                    LESSON = None
                    QNO = 0
                self._send({"ok": True, "message": "Session reset."})

            else:
                self._send({"error": "unknown endpoint"}, 404)
        except Exception as e:  # always answer JSON instead of dropping the connection
            self._send({"error": f"Server error: {e}"}, 500)


def main():
    print(f"🎓 MathFlow Web @ http://0.0.0.0:{PORT}")
    print(f"   Local: http://localhost:{PORT}    LAN: http://<this-IP>:{PORT}")
    if os.environ.get("MATHFLOW_LLM_MOCK") == "1":
        print("   LLM: offline MOCK mode (MATHFLOW_LLM_MOCK=1)")
    elif not os.environ.get("DEEPSEEK_API_KEY"):
        print("   ⚠️ DEEPSEEK_API_KEY not set — AI generation will fail (use MATHFLOW_LLM_MOCK=1 to test offline)")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
