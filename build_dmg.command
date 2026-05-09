#!/bin/bash
# Build Mimica.dmg — a Mac-native installer for the Mimica wrapper .app.
#
# This produces dmg_build/Mimica.dmg. The .app inside is the lightweight
# wrapper from wrapper/ (a few KB), NOT a PyInstaller bundle. On first
# launch it git-clones the source into ~/Library/Application Support/
# Mimica/source and exec's launch.command, which auto-pulls on every run.
#
# When @muchoosauce changes the wrapper itself (launcher.sh / Info.plist)
# he re-runs this script and ships a new .dmg. When he just changes the
# Python code, users get it automatically on next launch — no rebuild.

set -e
cd "$(dirname "$0")"

C_CYAN='\033[36m'
C_GREEN='\033[32m'
C_YELLOW='\033[33m'
C_RED='\033[31m'
C_DIM='\033[2m'
C_RESET='\033[0m'

printf "\n${C_CYAN}  Building Mimica.dmg…${C_RESET}\n\n"

# Sanity: required tools.
for tool in hdiutil osacompile; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    printf "${C_RED}$tool not found — is this macOS?${C_RESET}\n"
    exit 1
  fi
done

# Sanity: wrapper inputs exist.
for f in wrapper/launcher.sh wrapper/Info.plist; do
  if [ ! -f "$f" ]; then
    printf "${C_RED}Missing: $f${C_RESET}\n"
    exit 1
  fi
done

OUT_DIR="dmg_build"
APP_PATH="$OUT_DIR/Mimica.app"
DMG_STAGE="$OUT_DIR/dmg_stage"
DMG_PATH="$OUT_DIR/Mimica.dmg"

printf "${C_DIM}Cleaning previous build…${C_RESET}\n"
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"

# 1. Assemble the .app bundle by hand. No osacompile / no PyInstaller.
printf "${C_DIM}Assembling Mimica.app…${C_RESET}\n"
mkdir -p "$APP_PATH/Contents/MacOS"
mkdir -p "$APP_PATH/Contents/Resources"

cp wrapper/Info.plist "$APP_PATH/Contents/Info.plist"
cp wrapper/launcher.sh "$APP_PATH/Contents/MacOS/Mimica"
chmod +x "$APP_PATH/Contents/MacOS/Mimica"

# Optional: copy an icon if present at wrapper/AppIcon.icns
if [ -f wrapper/AppIcon.icns ]; then
  cp wrapper/AppIcon.icns "$APP_PATH/Contents/Resources/AppIcon.icns"
  # Patch Info.plist to reference it.
  /usr/libexec/PlistBuddy -c "Add :CFBundleIconFile string AppIcon" \
    "$APP_PATH/Contents/Info.plist" 2>/dev/null || \
  /usr/libexec/PlistBuddy -c "Set :CFBundleIconFile AppIcon" \
    "$APP_PATH/Contents/Info.plist"
fi

# Strip extended attributes that confuse Gatekeeper on unsigned bundles.
xattr -cr "$APP_PATH" 2>/dev/null || true

# 2. Stage a folder for the .dmg with the .app and an Applications symlink,
#    so the standard "drag to /Applications" install pattern works.
printf "${C_DIM}Staging .dmg contents…${C_RESET}\n"
mkdir -p "$DMG_STAGE"
ditto "$APP_PATH" "$DMG_STAGE/Mimica.app"
ln -s /Applications "$DMG_STAGE/Applications"

# 3. Build the .dmg. UDZO = compressed read-only — the standard format for
#    distribution. -volname is what shows up when the user opens it.
printf "${C_DIM}Creating .dmg…${C_RESET}\n"
rm -f "$DMG_PATH"
hdiutil create \
  -volname "Mimica" \
  -srcfolder "$DMG_STAGE" \
  -ov \
  -format UDZO \
  -fs HFS+ \
  -quiet \
  "$DMG_PATH"

SIZE_HUMAN=$(du -sh "$DMG_PATH" | cut -f1)

printf "\n${C_GREEN}  Done.${C_RESET}  ${DMG_PATH}  ·  ${SIZE_HUMAN}\n\n"
printf "${C_DIM}Installer steps for recipients:${C_RESET}\n"
printf "  1. Double-click Mimica.dmg\n"
printf "  2. Drag Mimica.app onto Applications\n"
printf "  3. Right-click Mimica in /Applications → Open → Open  (one-time Gatekeeper bypass)\n"
printf "  4. First launch downloads the source (needs SSH access to the repo)\n"
printf "  5. Settings → paste your MuAPI / Kie / Anthropic key\n\n"
printf "${C_DIM}Subsequent launches auto-pull updates from GitHub silently.${C_RESET}\n\n"
