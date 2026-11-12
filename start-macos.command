#!/bin/bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"
PYTHON="$ROOT_DIR/venv/bin/python"
INDEX="$ROOT_DIR/frontend/dist/index.html"
URL="http://127.0.0.1:8000/"
HEALTH_URL="http://127.0.0.1:8000/api/health"
SERVER_PID=""
LOG_FILE="$ROOT_DIR/data-local/server.log"

cleanup() {
  if [[ -n "$SERVER_PID" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

fail() {
  printf '\nWakeUp2 could not start: %s\n' "$1" >&2
  exit 1
}

is_running_wakeup2() {
  curl --fail --silent --max-time 2 "$HEALTH_URL" | grep -q '"status":"ok"' &&
    curl --fail --silent --max-time 2 "$URL" | grep -q 'WakeUp2'
}

[[ "$(uname -s)" == "Darwin" ]] || fail "This launcher is for macOS."
[[ -x "$PYTHON" && -s "$INDEX" ]] || fail "Run setup-macos.command first."

if is_running_wakeup2; then
  printf 'WakeUp2 is already running at %s\n' "$URL"
  open "$URL"
  exit 0
fi

if curl --silent --max-time 1 http://127.0.0.1:8000/ >/dev/null 2>&1; then
  fail "Port 8000 is occupied by another application. WakeUp2 will not stop it."
fi

mkdir -p "$ROOT_DIR/data-local"
printf 'Starting WakeUp2 at %s ...\n' "$URL"
"$PYTHON" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 >"$LOG_FILE" 2>&1 &
SERVER_PID=$!

READY=0
for _ in $(seq 1 60); do
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    tail -n 40 "$LOG_FILE" >&2 || true
    fail "The backend exited during startup. See data-local/server.log."
  fi
  if is_running_wakeup2; then
    READY=1
    break
  fi
  sleep 1
done
if [[ "$READY" -ne 1 ]]; then
  tail -n 40 "$LOG_FILE" >&2 || true
  fail "The application did not become ready. See data-local/server.log."
fi

printf 'WakeUp2 is ready. Opening %s\n' "$URL"
open "$URL"
printf 'Keep this Terminal window open while monitoring. Press Control-C to stop WakeUp2.\n'
wait "$SERVER_PID"
