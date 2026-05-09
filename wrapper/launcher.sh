#!/bin/bash
# Mimica wrapper launcher.
#
# Lives at Mimica.app/Contents/MacOS/Mimica. On first launch it clones the
# source repo into ~/Library/Application Support/Mimica/source/. Subsequent
# launches just chdir into that source dir and exec ./launch.command, which
# handles the silent git pull, the venv, and exec'ing python app.py.
#
# Why a wrapper at all? Because users want a Mac-native double-click .app —
# not a Terminal window. This .app is the .dmg-installable face of Mimica;
# the actual Python source lives at SOURCE_DIR and gets git-pulled on every
# run, so updates are instant when @muchoosauce pushes.

set +e  # Errors handled explicitly via native dialogs, no auto-exit.

REPO_URL="git@github.com:muchoosauce/mimica.git"
SOURCE_DIR="$HOME/Library/Application Support/Mimica/source"
LOG_DIR="$HOME/Library/Application Support/Mimica/logs"

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/launch-$(date +%Y%m%d).log"
exec >> "$LOG_FILE" 2>&1
echo ""
echo "===== $(date) ====="

# GUI-launched apps inherit a minimal PATH that misses Homebrew and
# python.org installs, so we restore the common bin dirs explicitly.
export PATH="/opt/homebrew/bin:/usr/local/bin:/Library/Frameworks/Python.framework/Versions/Current/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

show_error() {
  /usr/bin/osascript -e "display dialog \"$1\" buttons {\"OK\"} default button \"OK\" with icon caution with title \"Mimica\"" >/dev/null 2>&1 &
}

show_notification() {
  /usr/bin/osascript -e "display notification \"$1\" with title \"Mimica\"" >/dev/null 2>&1 &
}

# Single-instance lock. Stops impatient users who double-click 5 times during
# the slow first-launch install from spawning concurrent venv builds that
# corrupt each other. Lock file holds the PID of the running app — exec
# preserves PID across bash → launch.command → python, so the lock stays
# accurate until Python actually exits.
LOCK_FILE="$HOME/Library/Application Support/Mimica/.lock"
mkdir -p "$(dirname "$LOCK_FILE")"
if [ -f "$LOCK_FILE" ]; then
  OLD_PID=$(cat "$LOCK_FILE" 2>/dev/null)
  if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
    # Another instance is running. Bring it to front and bail silently.
    /usr/bin/osascript -e 'tell application "Mimica" to activate' >/dev/null 2>&1 &
    exit 0
  fi
  rm -f "$LOCK_FILE"  # stale
fi
echo $$ > "$LOCK_FILE"

# Pre-flight: git
if ! command -v git >/dev/null 2>&1; then
  rm -f "$LOCK_FILE"
  show_error "git n'est pas installé.\n\nOuvre le Terminal et tape :\n  xcode-select --install"
  exit 1
fi

# Pre-flight: locate a Python ≥ 3.10. The system python3 (3.9 on Big Sur+)
# is too old for PySide6 6.6+. Prefer named binaries (python3.13, .12, .11,
# .10) — Homebrew installs those by name without a generic `python3` symlink.
PYTHON_BIN=""
for candidate in python3.13 python3.12 python3.11 python3.10; do
  if FOUND="$(command -v "$candidate" 2>/dev/null)"; then
    PYTHON_BIN="$FOUND"
    break
  fi
done
# Last resort: `python3` itself, only if it's ≥ 3.10.
if [ -z "$PYTHON_BIN" ] && command -v python3 >/dev/null 2>&1; then
  if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" 2>/dev/null; then
    PYTHON_BIN="$(command -v python3)"
  fi
fi
if [ -z "$PYTHON_BIN" ]; then
  rm -f "$LOCK_FILE"
  show_error "Python 3.10 ou plus récent requis.\n\nInstall (au choix) :\n• https://www.python.org/downloads/  (coche \"Add Python to PATH\")\n• ou via Homebrew :  brew install python@3.12"
  exit 1
fi
export PYTHON_BIN
echo "Using Python: $PYTHON_BIN ($("$PYTHON_BIN" --version 2>&1))"

# First launch: clone the repo into the user-data dir.
if [ ! -d "$SOURCE_DIR/.git" ]; then
  show_notification "Premier lancement — install en cours (1-2 min). Patience !"
  mkdir -p "$(dirname "$SOURCE_DIR")"
  GIT_TERMINAL_PROMPT=0 \
  GIT_SSH_COMMAND="ssh -o ConnectTimeout=10 -o BatchMode=yes" \
    git clone --quiet "$REPO_URL" "$SOURCE_DIR"
  if [ ! -d "$SOURCE_DIR/.git" ]; then
    rm -f "$LOCK_FILE"
    show_error "Impossible de cloner Mimica depuis GitHub.\n\nVérifie :\n• ta connexion internet\n• ta clé SSH ajoutée à ton compte GitHub\n• ton accès collaborateur au repo\n\nLog : $LOG_FILE"
    exit 1
  fi
fi

cd "$SOURCE_DIR" || { rm -f "$LOCK_FILE"; show_error "Dossier source introuvable : $SOURCE_DIR"; exit 1; }

# Auto-pull from GitHub — runs HERE in the wrapper (not just inside
# launch.command) so it works as a bootstrap: even an old launch.command
# in the clone gets refreshed to the latest before we exec it. No-op if
# the repo is offline or has local changes.
if [ -z "$(git status --porcelain 2>/dev/null)" ]; then
  GIT_TERMINAL_PROMPT=0 \
  GIT_SSH_COMMAND="ssh -o ConnectTimeout=5 -o BatchMode=yes" \
  GIT_HTTP_LOW_SPEED_LIMIT=1000 GIT_HTTP_LOW_SPEED_TIME=5 \
    git pull --ff-only --quiet 2>/dev/null || true
fi

# Python shim: drop a `python3` -> $PYTHON_BIN symlink in a dir we prepend
# to PATH. Reason: an outdated launch.command on GitHub (one that hasn't
# yet learned about $PYTHON_BIN) calls bare `python3`, which on macOS
# resolves to /usr/bin/python3 = 3.9, too old. The shim forces every
# `python3` in our subprocess tree to be the verified 3.10+ binary.
SHIM_DIR="$HOME/Library/Application Support/Mimica/shim"
mkdir -p "$SHIM_DIR"
ln -sf "$PYTHON_BIN" "$SHIM_DIR/python3"
ln -sf "$PYTHON_BIN" "$SHIM_DIR/python"
export PATH="$SHIM_DIR:$PATH"

# If the venv exists but is broken (no pip — typically from a Python-version
# mismatch or a previous concurrent-launch race), wipe it now so launch.command
# rebuilds it cleanly with the right interpreter.
if [ -d ".venv" ] && [ ! -x ".venv/bin/pip" ]; then
  show_notification "Venv corrompue détectée — reconstruction en cours…"
  rm -rf .venv
fi

# Also wipe the venv if it was built on a Python version that no longer
# matches what we're about to use — happens when the user upgrades Python.
if [ -x ".venv/bin/python" ]; then
  VENV_VER=$(.venv/bin/python -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')" 2>/dev/null)
  WANT_VER=$("$PYTHON_BIN" -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')" 2>/dev/null)
  if [ -n "$VENV_VER" ] && [ "$VENV_VER" != "$WANT_VER" ]; then
    show_notification "Venv obsolète (Python $VENV_VER → $WANT_VER) — rebuild…"
    rm -rf .venv
  fi
fi

# If first-time-install (no venv yet), warn that the install is slow.
if [ ! -d ".venv" ]; then
  show_notification "Installation des dépendances (~2 min). Ne ferme pas l'app !"
fi

# Finder/Gatekeeper sometimes strips +x; restore it so launch.command can run.
chmod +x launch.command 2>/dev/null

# Hand off. launch.command does the silent git pull, sets up the venv,
# installs deps if requirements.txt changed, and exec's python app.py.
# We `exec` so the Python process becomes our process — the .app's running
# indicator in the Dock follows the actual Qt app, not this bash wrapper.
exec ./launch.command
