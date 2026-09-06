#!/bin/bash
# run_codex_once.sh — launch a codex task with a per-task-key single-instance lock.
#
# Why: a buggy/duplicated exec can otherwise launch N concurrent codex instances
# all writing the same files (this actually happened 2026-09-01 with mathflow:
# 4 instances clobbered course_server.py). This wrapper guarantees at most one
# live codex process per task key; duplicate launches exit 0 immediately.
#
# Usage:
#   run_codex_once.sh <task-key> <codex args...>
#   run_codex_once.sh mathflow-admin codex exec -s workspace-write "implement ..."
#
# Lock: mkdir-based atomic lock under /tmp/mathflow-codex-locks/<key>.lock
# with a pid file; stale locks (dead pid) are reclaimed.
set -u

# Overridable for testing: CODEX_BIN=sleep run_codex_once.sh key 8
CODEX_BIN="${CODEX_BIN:-codex}"

TASK_KEY="${1:-}"
if [ -z "$TASK_KEY" ]; then
  echo "usage: run_codex_once.sh <task-key> <codex args...>" >&2
  exit 2
fi
shift

LOCK_DIR="/tmp/mathflow-codex-locks"
LOCK="$LOCK_DIR/$TASK_KEY.lock"
mkdir -p "$LOCK_DIR" || { echo "[codex-lock] cannot mkdir $LOCK_DIR" >&2; exit 1; }

acquire() {
  if mkdir "$LOCK" 2>/dev/null; then
    echo "$$" > "$LOCK/pid" 2>/dev/null
    return 0
  fi
  # Lock exists: is the holder alive?
  if [ -f "$LOCK/pid" ]; then
    HOLDER_PID="$(cat "$LOCK/pid" 2>/dev/null)"
    if [ -n "$HOLDER_PID" ] && kill -0 "$HOLDER_PID" 2>/dev/null; then
      return 1  # live holder -> duplicate
    fi
  fi
  # Stale lock -> reclaim
  rm -rf "$LOCK"
  if mkdir "$LOCK" 2>/dev/null; then
    echo "$$" > "$LOCK/pid" 2>/dev/null
    return 0
  fi
  return 1
}

if ! acquire; then
  HOLDER_PID="$(cat "$LOCK/pid" 2>/dev/null)"
  echo "[codex-lock] task '$TASK_KEY' already running (pid ${HOLDER_PID:-unknown}); duplicate launch skipped." >&2
  exit 0
fi
trap 'rm -rf "$LOCK"' EXIT INT TERM

echo "[codex-lock] task '$TASK_KEY' acquired lock (pid $$), starting: $CODEX_BIN $*" >&2
exec "$CODEX_BIN" "$@"
