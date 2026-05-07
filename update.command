#!/bin/bash
set -e

cd "$(dirname "$0")"

C_CYAN='\033[36m'
C_GREEN='\033[32m'
C_YELLOW='\033[33m'
C_RED='\033[31m'
C_DIM='\033[2m'
C_RESET='\033[0m'

printf "\n${C_CYAN}  Mimica — checking for updates…${C_RESET}\n\n"

if ! command -v git >/dev/null 2>&1; then
  printf "${C_RED}git not found. Install Xcode Command Line Tools: xcode-select --install${C_RESET}\n"
  read -n 1 -s -r -p "Press any key to close..."
  exit 1
fi

if [ ! -d ".git" ]; then
  printf "${C_RED}This folder isn't a git clone. Re-clone the repository to enable updates.${C_RESET}\n"
  read -n 1 -s -r -p "Press any key to close..."
  exit 1
fi

# Refuse to update if there are uncommitted changes — preserves any local
# tweaks the user might have made.
if [ -n "$(git status --porcelain)" ]; then
  printf "${C_YELLOW}Local changes detected. Stash them first if you want to update.${C_RESET}\n"
  printf "${C_DIM}  git stash      # to save\n  git stash pop  # to restore later${C_RESET}\n"
  read -n 1 -s -r -p "Press any key to close..."
  exit 1
fi

printf "${C_DIM}Pulling latest changes…${C_RESET}\n"
BEFORE=$(git rev-parse HEAD)
git pull --ff-only
AFTER=$(git rev-parse HEAD)

if [ "$BEFORE" = "$AFTER" ]; then
  printf "${C_GREEN}Already up to date.${C_RESET}\n\n"
else
  printf "${C_GREEN}Updated to $(git rev-parse --short HEAD).${C_RESET}\n"
  CHANGED_FILES=$(git diff --name-only "$BEFORE..$AFTER")

  # Refresh deps if requirements.txt changed.
  if echo "$CHANGED_FILES" | grep -q "^requirements.txt$"; then
    if [ -d ".venv" ]; then
      printf "${C_DIM}Refreshing Python dependencies…${C_RESET}\n"
      # shellcheck disable=SC1091
      source .venv/bin/activate
      python -m pip install --quiet --upgrade pip
      python -m pip install --quiet -r requirements.txt
      touch .venv/.deps_installed
    fi
  fi
  printf "\n"
fi

printf "${C_CYAN}Launching Mimica…${C_RESET}\n\n"
exec ./launch.command
