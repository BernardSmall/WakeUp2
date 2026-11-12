#!/bin/bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"
PYTHON=""
NODE=""

fail() {
  printf '\nSetup failed: %s\n' "$1" >&2
  exit 1
}

find_python() {
  local candidate
  for candidate in python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1 &&
      "$candidate" "$ROOT_DIR/scripts/prerequisites.py" python >/dev/null 2>&1; then
      PYTHON="$(command -v "$candidate")"
      return 0
    fi
  done
  return 1
}

find_node() {
  if ! command -v node >/dev/null 2>&1; then
    return 1
  fi
  local version
  version="$(node --version)"
  if [[ "$version" =~ ^v24\.[0-9]+\. ]] ||
    ( [[ "$version" =~ ^v22\.([0-9]+)\. ]] && (( BASH_REMATCH[1] >= 12 )) ); then
    NODE="$(command -v node)"
    return 0
  fi
  return 1
}

printf 'WakeUp2 setup for macOS\n'
printf 'Checking macOS and processor architecture...\n'
[[ "$(uname -s)" == "Darwin" ]] || fail "This setup script is for macOS."
ARCH="$(uname -m)"
[[ "$ARCH" == "arm64" || "$ARCH" == "x86_64" ]] || fail "Unsupported processor: $ARCH."
if [[ "$ARCH" == "x86_64" ]]; then
  MACOS_VERSION="$(sw_vers -productVersion)"
  MACOS_MAJOR="${MACOS_VERSION%%.*}"
  if (( MACOS_MAJOR < 12 )); then
    fail "Intel Macs require macOS 12 or later for the pinned OpenCV wheel. Detected macOS $MACOS_VERSION."
  fi
fi
printf 'Detected macOS %s (%s).\n' "$(sw_vers -productVersion)" "$ARCH"

printf 'Checking Python installation...\n'
find_python || true
printf 'Checking Node.js and npm...\n'
find_node || true
if [[ -z "$PYTHON" || -z "$NODE" ]]; then
  printf '\nMissing compatible prerequisites:\n'
  [[ -n "$PYTHON" ]] || printf '  - Python 3.10, 3.11, or 3.12\n'
  [[ -n "$NODE" ]] || printf '  - Node.js 22.12+ or 24.x with npm\n'
  [[ -n "$PYTHON" ]] || printf '  Python downloads: https://www.python.org/downloads/macos/\n'
  [[ -n "$NODE" ]] || printf '  Node.js downloads: https://nodejs.org/en/download\n'
  if ! command -v brew >/dev/null 2>&1; then
    printf '\nInstall prerequisites from the official sites, then rerun this script.\n'
    printf 'WakeUp2 will not install Homebrew or change system security settings for you.\n'
    exit 1
  fi
  printf '\nHomebrew can install the missing user-requested prerequisites (python@3.11 and node@22).\n'
  read -r -p "Install the missing prerequisites with Homebrew? [y/N] " answer
  [[ "$answer" == "y" || "$answer" == "Y" ]] || fail "Install the prerequisites using the official links above, then rerun setup."
  packages=()
  [[ -n "$PYTHON" ]] || packages+=(python@3.11)
  [[ -n "$NODE" ]] || packages+=(node@22)
  brew install "${packages[@]}" || fail "Homebrew could not install the requested packages. Check the output above."
  BREW_PREFIX="$(brew --prefix)"
  PATH="$BREW_PREFIX/bin:$BREW_PREFIX/opt/python@3.11/bin:$BREW_PREFIX/opt/node@22/bin:$PATH"
  export PATH
  find_python || fail "Python was installed but is not available in PATH. Open a new Terminal window and rerun setup."
  find_node || fail "Node.js was installed but is not available in PATH. Open a new Terminal window and rerun setup."
fi

"$PYTHON" "$ROOT_DIR/scripts/prerequisites.py" host || fail "Unsupported computer."
"$PYTHON" "$ROOT_DIR/scripts/prerequisites.py" python || fail "Install a supported Python version."
python_minor="$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
"$PYTHON" "$ROOT_DIR/scripts/prerequisites.py" node --version "$("$NODE" --version)" ||
  fail "Install Node.js 22.12+ or 24.x from https://nodejs.org/en/download."
command -v npm >/dev/null 2>&1 || fail "npm is missing; reinstall Node.js from https://nodejs.org/en/download."
printf '\nUsing Python %s and Node.js %s.\n' "$python_minor" "$("$NODE" --version)"

if [[ -e "$ROOT_DIR/venv" ]]; then
  [[ -x "$ROOT_DIR/venv/bin/python" ]] || fail "An existing venv is incomplete. Rename it manually after backing it up, then rerun setup."
  "$ROOT_DIR/venv/bin/python" "$ROOT_DIR/scripts/prerequisites.py" python ||
    fail "The existing venv uses an unsupported Python. Back it up and rename it manually; setup will not delete it."
else
  printf '\nCreating WakeUp2 environment...\n'
  "$PYTHON" -m venv "$ROOT_DIR/venv" || fail "Could not create the local Python environment."
fi

printf '\nInstalling application dependencies...\n'
"$ROOT_DIR/venv/bin/python" -m pip install --upgrade pip || fail "Could not update pip inside the project environment."
"$ROOT_DIR/venv/bin/python" -m pip install -r "$ROOT_DIR/requirements.txt" || fail "Python dependencies could not be installed. Review the error above."
if ! pip_check_output="$("$ROOT_DIR/venv/bin/python" -m pip check 2>&1)"; then
  if [[ "$pip_check_output" == "mediapipe 0.10.21 is not supported on this platform" ]]; then
    printf 'Checking MediaPipe runtime compatibility (the wheel metadata is flagged by pip check)...\n'
    "$ROOT_DIR/venv/bin/python" -c 'import cv2, mediapipe; from mediapipe.python import solutions; assert hasattr(solutions, "face_mesh"); print("MediaPipe and OpenCV runtime imports are ready.")' ||
      fail "MediaPipe is not usable on this Mac."
  else
    printf '%s\n' "$pip_check_output" >&2
    fail "Python dependency versions conflict."
  fi
fi

printf '\nInstalling frontend dependencies...\n'
(cd "$ROOT_DIR/frontend" && npm ci) || fail "Frontend dependencies could not be installed."
printf '\nBuilding the frontend...\n'
(cd "$ROOT_DIR/frontend" && npm run build) || fail "The frontend build failed. Review the output above."

printf '\nValidating WakeUp2...\n'
"$ROOT_DIR/venv/bin/python" -c 'import cv2, mediapipe, fastapi, AVFoundation; print("Python imports are ready.")' ||
  fail "A required backend import failed."
[[ -s "$ROOT_DIR/frontend/dist/index.html" ]] || fail "The frontend build output is missing."
mkdir -p "$ROOT_DIR/data-local"

printf '\nSetup completed successfully.\n'
printf 'Run start-macos.command to launch WakeUp2 in your browser.\n'
printf 'Camera permission is requested by macOS the first time monitoring starts.\n'
