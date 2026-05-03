#!/bin/bash
set -e
cd "$(dirname "$0")"

C_CYAN='\033[36m'
C_GREEN='\033[32m'
C_YELLOW='\033[33m'
C_RED='\033[31m'
C_DIM='\033[2m'
C_RESET='\033[0m'

printf "\n${C_CYAN}  Building Ad Variator.app…${C_RESET}\n\n"

if ! command -v python3 >/dev/null 2>&1; then
  printf "${C_RED}python3 not found. Install from https://www.python.org/downloads/${C_RESET}\n"
  exit 1
fi

# 1. venv
if [ ! -d ".venv" ]; then
  printf "${C_DIM}Creating virtual environment…${C_RESET}\n"
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

# 2. Build deps
printf "${C_DIM}Installing build dependencies…${C_RESET}\n"
python -m ensurepip --upgrade >/dev/null 2>&1 || true
python -m pip install --quiet --upgrade pip pyinstaller
python -m pip install --quiet -r requirements.txt

# 3. Bundle Chromium for Playwright into ./build_browsers/
BROWSERS_DIR="$(pwd)/build_browsers"
if [ ! -d "$BROWSERS_DIR" ] || [ -z "$(ls -A "$BROWSERS_DIR" 2>/dev/null)" ]; then
  printf "${C_DIM}Downloading Chromium for Playwright (~150 MB)…${C_RESET}\n"
  rm -rf "$BROWSERS_DIR"
  PLAYWRIGHT_BROWSERS_PATH="$BROWSERS_DIR" python -m playwright install chromium
else
  printf "${C_DIM}Chromium already cached in build_browsers/${C_RESET}\n"
fi

# 4. Clean and build
printf "${C_DIM}Building .app via PyInstaller…${C_RESET}\n"
rm -rf build dist
pyinstaller --clean --noconfirm AdVariator.spec

APP_PATH="dist/Ad Variator.app"
if [ ! -d "$APP_PATH" ]; then
  printf "${C_RED}Build failed — '$APP_PATH' missing.${C_RESET}\n"
  exit 1
fi

# 5. Strip extended attributes that confuse Gatekeeper
xattr -cr "$APP_PATH" 2>/dev/null || true

# 6. Zip the .app
ZIP_PATH="dist/AdVariator.app.zip"
rm -f "$ZIP_PATH"
printf "${C_DIM}Zipping…${C_RESET}\n"
( cd dist && ditto -c -k --sequesterRsrc --keepParent "Ad Variator.app" "AdVariator.app.zip" )

SIZE_HUMAN=$(du -sh "$ZIP_PATH" | cut -f1)
printf "\n${C_GREEN}  Done.${C_RESET}  ${ZIP_PATH}  ·  ${SIZE_HUMAN}\n\n"
printf "${C_DIM}Recipient steps:${C_RESET}\n"
printf "  1. Unzip\n"
printf "  2. Drag 'Ad Variator.app' into /Applications\n"
printf "  3. Right-click → Open → Open  (one-time Gatekeeper bypass — unsigned build)\n"
printf "  4. Settings → paste their MuAPI / Kie / Anthropic key\n\n"
