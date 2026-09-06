# TASK_android_app.md — MathFlow Android App (MVP)

## Context

MathFlow teaches Lean 4 theorem proving via generated exercises. A backend HTTP API runs on
the Mac mini (see `~/Documents/mathflow/TASK_backend_api.md` for the contract; the canonical
API shape is repeated below). This task builds the **Android client** (new project):

- Project dir: `~/Documents/mathflow-android` (create it)
- Kotlin + Jetpack Compose + Material3, UI in **English**
- Records (attempts, wrong answers) stored **locally** (Room) — survives offline/restart
- Reference scaffolding: `~/Documents/signal-noise-android` — copy its proven toolchain:
  Gradle 8.4 wrapper, AGP 8.2.0, Kotlin 1.9.20, Compose BOM 2023.10.01, compileSdk 34,
  minSdk 26, targetSdk 34, JVM 17. Copy `gradlew`, `gradle/wrapper/`, and the `local.properties`
  pattern (`sdk.dir=/Users/zd/android-sdk`).
- No git commits. No Firebase/Ktor. English strings.

## Backend API contract (canonical)

Base URL is user-configurable (Settings screen, stored in SharedPreferences; default shown
as `http://<mac-mini-lan-ip>:8787`). Cleartext HTTP must be allowed for MVP
(`android:usesCleartextTraffic="true"` in the manifest).

- `GET {base}/api/lessons` → `[{"id": str, "title": str, "created_at": str, "question_count": int}]`
- `GET {base}/api/lessons/{id}` → `{"id": str, "title": str, "questions": [{"qid": str, "code": str,
  "options": [{"text": str, "is_correct": bool}], "explanation": str, "hint": str}]}`
  — `code` contains exactly one `___` blank
- `POST {base}/api/check` body `{"qid": str, "answer": str}` → `{"correct": bool, "error": str|null}`
  — used for free-text fill answers (can take ~20-70s; show a spinner + note)

## Screens & flow

1. **Home** — lesson list from `GET /api/lessons` (pull-to-refresh; fall back to cached copy
   when offline). Settings action (⚙) → Server URL screen. Tap lesson → Lesson screen.
2. **Lesson** — fetch `GET /api/lessons/{id}`, show questions one at a time
   ("Question 2/5" progress). Question card:
   - `code` in monospace, `___` blank visually highlighted
   - hint collapsible
   - options as tappable buttons → tap selects & grades immediately (local, via `is_correct`),
     highlight correct green / wrong red, then show `explanation`
   - "Type your own" expandable field → submit → `POST /api/check` with spinner + "Compiling
     on server… can take up to a minute" note; show result + explanation after
   - "Next" button advances; last question → lesson summary (score X/Y) → back to Home
3. **Review** — list of wrong attempts from Room (`isCorrect=false`): question code, your
   answer, correct answer (from stored cache), explanation, timestamp. Accessible from Home.

## Local persistence (Room, version 1)

- `LessonSummary(lessonId PK, title, questionCount, fetchedAt)` — cached lesson list
- `LessonCache(lessonId PK, json)` — full lesson JSON for offline answering
- `Attempt(id auto PK, lessonId, qid, mode("mcq"|"fill"), answer, isCorrect, timestamp)`
- Grading: MCQ graded locally from `is_correct`; fill-in graded by `/api/check` response.
  Every answer inserts an `Attempt` row immediately.

## Architecture

- `retrofit`-free: OkHttp 4.12.0 + kotlinx-serialization-json 1.6.2 (+ the Kotlin serialization
  plugin 1.9.20). Data classes mirror the contract (`LessonSummaryDto`, `LessonDto`,
  `QuestionDto`, `OptionDto`, `CheckRequest`, `CheckResponse`).
- ViewModels: `LessonsViewModel`, `LessonViewModel`, `ReviewViewModel` (ViewModel + StateFlow;
  `lifecycle-viewmodel-compose`). No Hilt — manual DI via an `AppContainer` (keeps it simple).
- Room with KSP (`com.google.devtools.ksp` 1.9.20-1.0.14).
- Navigation: `androidx.navigation:navigation-compose:2.7.6`.

## Verification (MUST run; paste results in the report)

1. `./gradlew assembleDebug` succeeds → APK at `app/build/outputs/apk/debug/app-debug.apk`
2. `./gradlew testDebugUnitTest` — write and pass unit tests for:
   - JSON parsing of the API contract (round-trip of a sample lesson payload)
   - MCQ grading logic (correct/wrong from `is_correct`)
   - Server URL validation (Settings input handling)
3. Best-effort integration check (skip gracefully if the server isn't running): a JUnit test
   that hits `http://localhost:8787/api/lessons` via the real client and asserts parsing.
   If `curl -s localhost:8787/api/health` fails, note it and skip.

Report: files created, APK path + size, unit test results, any deviations. Do NOT commit to git.

## Constraints

- Do NOT modify anything in `~/Documents/mathflow` or `~/Documents/signal-noise-android`.
- Do NOT run real LLM generation; do NOT call DeepSeek.
- English UI text and code comments.
