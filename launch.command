#!/bin/bash
set -e

cd "$(dirname "$0")"

C_CYAN='\033[36m'
C_GREEN='\033[32m'
C_YELLOW='\033[33m'
C_RED='\033[31m'
C_DIM='\033[2m'
C_RESET='\033[0m'

printf "\n${C_CYAN}  Ad Variator — starting…${C_RESET}\n\n"

if ! command -v python3 >/dev/null 2>&1; then
  printf "${C_RED}python3 not found. Install from https://www.python.org/downloads/${C_RESET}\n"
  read -n 1 -s -r -p "Press any key to close..."
  exit 1
fi

if [ ! -d ".venv" ]; then
  printf "${C_DIM}Creating virtual environment…${C_RESET}\n"
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

if [ ! -f ".venv/.deps_installed" ] || [ requirements.txt -nt .venv/.deps_installed ]; then
  printf "${C_DIM}Installing dependencies (first run can take ~1 min)…${C_RESET}\n"
  pip install --quiet --upgrade pip
  pip install --quiet -r requirements.txt
  touch .venv/.deps_installed
fi

if [ ! -f ".venv/.playwright_installed" ] || [ requirements.txt -nt ".venv/.playwright_installed" ]; then
  printf "${C_DIM}Installing Playwright Chromium (one-time, ~150 MB)…${C_RESET}\n"
  python -m playwright install chromium
  touch .venv/.playwright_installed
fi

exec python app.py
