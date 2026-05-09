#!/bin/bash
set -e

cd "$(dirname "$0")"

C_CYAN='\033[36m'
C_GREEN='\033[32m'
C_YELLOW='\033[33m'
C_RED='\033[31m'
C_DIM='\033[2m'
C_RESET='\033[0m'

printf "\n${C_CYAN}  Mimica — starting…${C_RESET}\n\n"

# Silent auto-update from GitHub before launching.
# Skipped silently if: not a git clone, no git, local changes, or network is down.
# Short timeouts (5s SSH connect, 5s low-speed HTTPS) so a flaky connection
# can't block app startup. The `|| true` swallows pull failures so offline
# users still get the app — they just stay on their current commit.
if [ -d ".git" ] && command -v git >/dev/null 2>&1; then
  if [ -z "$(git status --porcelain 2>/dev/null)" ]; then
    printf "${C_DIM}Checking for updates…${C_RESET}\n"
    BEFORE=$(git rev-parse HEAD 2>/dev/null || echo "")
    GIT_TERMINAL_PROMPT=0 \
    GIT_SSH_COMMAND="ssh -o ConnectTimeout=5 -o BatchMode=yes" \
    GIT_HTTP_LOW_SPEED_LIMIT=1000 GIT_HTTP_LOW_SPEED_TIME=5 \
      git pull --ff-only --quiet 2>/dev/null || true
    AFTER=$(git rev-parse HEAD 2>/dev/null || echo "")
    if [ -n "$BEFORE" ] && [ -n "$AFTER" ] && [ "$BEFORE" != "$AFTER" ]; then
      printf "${C_GREEN}Updated to $(git rev-parse --short HEAD).${C_RESET}\n"
    fi
  else
    printf "${C_YELLOW}Local changes detected — skipping auto-update.${C_RESET}\n"
  fi
fi

# Pick the Python binary. The wrapper .app sets PYTHON_BIN to a verified
# 3.10+ interpreter; running from a Terminal we fall back to system python3
# but still version-check it so a stale venv from 3.9 can't silently corrupt
# pip later.
PY="${PYTHON_BIN:-python3}"

if ! command -v "$PY" >/dev/null 2>&1; then
  printf "${C_RED}$PY not found. Install Python 3.10+ from https://www.python.org/downloads/${C_RESET}\n"
  read -n 1 -s -r -p "Press any key to close..."
  exit 1
fi

if ! "$PY" -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" 2>/dev/null; then
  printf "${C_RED}Python 3.10+ required. You have: $("$PY" --version 2>&1)${C_RESET}\n"
  printf "${C_YELLOW}Install a newer Python:\n  • https://www.python.org/downloads/  (check \"Add Python to PATH\")\n  • or:  brew install python@3.12${C_RESET}\n"
  read -n 1 -s -r -p "Press any key to close..."
  exit 1
fi

# Repair a half-built venv (no pip) — happens after a failed/interrupted
# install or a Python-version swap.
if [ -d ".venv" ] && [ ! -x ".venv/bin/pip" ]; then
  printf "${C_YELLOW}Broken venv detected — rebuilding…${C_RESET}\n"
  rm -rf .venv
fi

if [ ! -d ".venv" ]; then
  printf "${C_DIM}Creating virtual environment…${C_RESET}\n"
  "$PY" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

if [ ! -f ".venv/.deps_installed" ] || [ requirements.txt -nt .venv/.deps_installed ]; then
  printf "${C_DIM}Installing dependencies (first run can take ~1 min)…${C_RESET}\n"
  python -m ensurepip --upgrade >/dev/null 2>&1 || true
  python -m pip install --quiet --upgrade pip
  python -m pip install --quiet -r requirements.txt
  touch .venv/.deps_installed
fi

if [ ! -f ".venv/.playwright_installed" ] || [ requirements.txt -nt ".venv/.playwright_installed" ]; then
  printf "${C_DIM}Installing Playwright Chromium (one-time, ~150 MB)…${C_RESET}\n"
  python -m playwright install chromium
  touch .venv/.playwright_installed
fi

exec python app.py
