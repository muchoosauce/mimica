#!/bin/bash
# install.command — first-time automated setup for Mimica on a fresh Mac.
#
# Walks through everything a clean macOS install needs to run Mimica:
#   1. Xcode Command Line Tools (needed by Homebrew + git)
#   2. Homebrew (package manager)
#   3. Python 3.12 (via Homebrew — the version Mimica is tested against)
#   4. The Mimica source repo (clone or update)
#   5. The Python virtual environment + dependencies (delegated to launch.command)
#
# Idempotent: safe to re-run any time. Already-installed steps are skipped
# with a green checkmark. After the first run the partner just double-clicks
# Mimica.app or launch.command — they never need to run this again.
#
# UX choices:
#  • All messages in French (Mimica's main user language).
#  • Colored milestones so the partner can see what's happening even if they
#    don't read every line.
#  • Two unavoidable system prompts on a fresh Mac:
#      - macOS dialog for Xcode CLI Tools (one click "Install")
#      - sudo password for Homebrew (typed once)
#    The script polls and waits politely for both, then continues.

set -u  # NOT -e — we handle errors explicitly with friendly messages.
cd "$(dirname "$0")"

# ── Colors ──────────────────────────────────────────────────────────
C_CYAN='\033[36m'
C_GREEN='\033[32m'
C_YELLOW='\033[33m'
C_RED='\033[31m'
C_DIM='\033[2m'
C_BOLD='\033[1m'
C_RESET='\033[0m'

# ── Helpers ─────────────────────────────────────────────────────────
say()     { printf "%b\n" "$*"; }
ok()      { printf "${C_GREEN}✓${C_RESET} %b\n" "$*"; }
warn()    { printf "${C_YELLOW}⚠${C_RESET} %b\n" "$*"; }
err()     { printf "${C_RED}✗${C_RESET} %b\n" "$*"; }
step()    { printf "\n${C_CYAN}${C_BOLD}[$1/$TOTAL_STEPS]${C_RESET} ${C_BOLD}$2${C_RESET}\n"; }
abort()   { printf "\n${C_RED}${C_BOLD}Installation interrompue.${C_RESET}\n%b\n\n" "$1"
            read -n 1 -s -r -p "Press any key to close..."
            exit 1; }

TOTAL_STEPS=5

# ── Banner ──────────────────────────────────────────────────────────
clear
say "${C_CYAN}${C_BOLD}╔═══════════════════════════════════════════════════╗${C_RESET}"
say "${C_CYAN}${C_BOLD}║          Mimica — Installation automatique         ║${C_RESET}"
say "${C_CYAN}${C_BOLD}╚═══════════════════════════════════════════════════╝${C_RESET}"
say ""
say "${C_DIM}Ce script installe Mimica et toutes ses dépendances en une passe.${C_RESET}"
say "${C_DIM}Durée estimée : 5–10 min selon ta connexion + ta machine.${C_RESET}"
say ""
say "${C_DIM}Tu devras peut-être :${C_RESET}"
say "${C_DIM}  • cliquer sur ${C_BOLD}Install${C_RESET}${C_DIM} dans la boîte de dialogue macOS Xcode${C_RESET}"
say "${C_DIM}  • saisir une fois le mot de passe de ta session Mac (pour Homebrew)${C_RESET}"
say ""
read -n 1 -s -r -p "Appuie sur n'importe quelle touche pour commencer…"
say ""

# ── Step 1 — Xcode Command Line Tools ───────────────────────────────
step 1 "Xcode Command Line Tools"
if xcode-select -p >/dev/null 2>&1; then
  ok "Déjà installés."
else
  warn "Une boîte de dialogue macOS va s'ouvrir. Clique sur ${C_BOLD}Install${C_RESET}, puis attends."
  xcode-select --install >/dev/null 2>&1 || true
  printf "${C_DIM}Attente de l'installation"
  WAITED=0
  while ! xcode-select -p >/dev/null 2>&1; do
    printf "."
    sleep 5
    WAITED=$((WAITED + 5))
    if [ $WAITED -gt 1800 ]; then
      printf "\n"
      abort "Xcode CLI Tools non installés au bout de 30 min. Relance ce script."
    fi
  done
  printf "${C_RESET}\n"
  ok "Installés."
fi

# ── Step 2 — Homebrew ───────────────────────────────────────────────
step 2 "Homebrew"
ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ]; then
  BREW_PREFIX="/opt/homebrew"
else
  BREW_PREFIX="/usr/local"
fi
BREW_BIN="$BREW_PREFIX/bin/brew"

if [ -x "$BREW_BIN" ]; then
  ok "Déjà installé ($("$BREW_BIN" --version | head -1))."
  eval "$("$BREW_BIN" shellenv)"
else
  warn "Installation… le mot de passe Mac va t'être demandé une fois."
  # NONINTERACTIVE=1 makes the official installer skip its "press RETURN to
  # continue" gate, while sudo will still prompt for the password once.
  if ! NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"; then
    abort "Échec de l'installation Homebrew. Vérifie la sortie ci-dessus."
  fi
  if [ ! -x "$BREW_BIN" ]; then
    abort "Homebrew n'est pas où il devrait être ($BREW_BIN)."
  fi
  eval "$("$BREW_BIN" shellenv)"
  ok "Installé."
fi

# ── Step 3 — Python 3.12 ────────────────────────────────────────────
step 3 "Python 3.12"
# Even on machines where /usr/bin/python3 exists (Apple's 3.9), we install
# a clean 3.12 via Homebrew to match what launch.command's PY scan picks
# up first. This avoids the broken-ensurepip class of bugs we saw on fresh
# 3.13 installs.
PY_BIN="$BREW_PREFIX/bin/python3.12"
if [ -x "$PY_BIN" ]; then
  ok "Déjà installé ($("$PY_BIN" --version 2>&1))."
else
  warn "Installation via Homebrew… 1–3 minutes."
  if ! brew install python@3.12; then
    abort "Échec brew install python@3.12. Réessaie ou vérifie ta connexion."
  fi
  if [ ! -x "$PY_BIN" ]; then
    # Some Homebrew layouts symlink differently — try the alt path.
    PY_BIN="$BREW_PREFIX/opt/python@3.12/libexec/bin/python3"
    if [ ! -x "$PY_BIN" ]; then
      abort "Python 3.12 installé mais introuvable au chemin attendu."
    fi
  fi
  ok "Installé ($("$PY_BIN" --version 2>&1))."
fi

# ── Step 4 — Mimica source code ─────────────────────────────────────
step 4 "Code source Mimica"
REPO_URL="https://github.com/muchoosauce/mimica.git"

if [ -f "app.py" ] && [ -f "launch.command" ]; then
  ok "Le repo est déjà ici, on l'utilise."
  REPO_DIR="$(pwd)"
  # Try a fast-forward pull if it's a git checkout — silent on failure
  # (offline / detached HEAD / local changes all OK).
  if [ -d ".git" ]; then
    git pull --ff-only --quiet 2>/dev/null && ok "Repo à jour." || warn "Skip git pull (changements locaux ou offline)."
  fi
else
  TARGET_DIR="$HOME/Library/Application Support/Mimica/source"
  if [ -d "$TARGET_DIR/.git" ]; then
    say "${C_DIM}Mise à jour du clone existant…${C_RESET}"
    (cd "$TARGET_DIR" && git pull --ff-only --quiet) || warn "git pull a échoué (offline ?)."
  else
    say "${C_DIM}Clonage dans $TARGET_DIR…${C_RESET}"
    mkdir -p "$(dirname "$TARGET_DIR")"
    if ! git clone --quiet "$REPO_URL" "$TARGET_DIR"; then
      abort "Échec du clone. Si le repo est privé, configure un token GitHub d'abord."
    fi
  fi
  REPO_DIR="$TARGET_DIR"
  ok "Code prêt."
fi

# ── Step 5 — Virtual env + Python deps (via launch.command) ─────────
step 5 "Environnement virtuel + dépendances"
say "${C_DIM}On délègue à launch.command qui sait déjà installer le venv,${C_RESET}"
say "${C_DIM}PySide6, les providers SDK et Playwright Chromium.${C_RESET}"
say ""
cd "$REPO_DIR"
# Pass our verified Python explicitly so launch.command skips its own scan
# and uses the 3.12 we just installed.
export PYTHON_BIN="$PY_BIN"
# launch.command finishes by exec'ing `python app.py` — so the Mimica
# window pops up at the end of this. That IS our success signal.
bash launch.command

# ── Done ────────────────────────────────────────────────────────────
# If we reach this point, the user has just closed Mimica after a successful
# launch. Show the final summary.
say ""
say "${C_GREEN}${C_BOLD}╔═══════════════════════════════════════════════════╗${C_RESET}"
say "${C_GREEN}${C_BOLD}║              ✓ Installation terminée                ║${C_RESET}"
say "${C_GREEN}${C_BOLD}╚═══════════════════════════════════════════════════╝${C_RESET}"
say ""
say "  Pour relancer Mimica :"
say "    ${C_BOLD}double-clic sur launch.command${C_RESET}"
say "    ${C_DIM}(ou sur Mimica.app si tu l'as installé via le .dmg)${C_RESET}"
say ""
say "  Code installé dans :"
say "    ${C_DIM}$REPO_DIR${C_RESET}"
say ""
read -n 1 -s -r -p "Appuie sur n'importe quelle touche pour fermer…"
say ""
