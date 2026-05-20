@echo off
REM ============================================================================
REM Mimica - One-click installer for Windows 10/11.
REM
REM Mirrors install.command on macOS: detects what's already installed, fills
REM in the rest, clones the repo, sets up the venv, and launches the app. Safe
REM to re-run any time — already-installed steps are skipped.
REM
REM Requires: Windows 10 1709+ (for winget) or Windows 11. Older Windows users
REM should follow the manual path in README.md.
REM ============================================================================
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1
cd /d "%~dp0"

REM ── Colors (ANSI works in Win10 1909+ / Win11 cmd) ─────────────────────────
for /F %%a in ('echo prompt $E ^| cmd') do set "ESC=%%a"
set "C_CYAN=%ESC%[36m"
set "C_GREEN=%ESC%[32m"
set "C_YELLOW=%ESC%[33m"
set "C_RED=%ESC%[31m"
set "C_DIM=%ESC%[2m"
set "C_BOLD=%ESC%[1m"
set "C_RESET=%ESC%[0m"

REM ── Banner ─────────────────────────────────────────────────────────────────
cls
echo.
echo %C_CYAN%%C_BOLD%╔═══════════════════════════════════════════════════╗%C_RESET%
echo %C_CYAN%%C_BOLD%║          Mimica — Installation automatique         ║%C_RESET%
echo %C_CYAN%%C_BOLD%╚═══════════════════════════════════════════════════╝%C_RESET%
echo.
echo %C_DIM%Ce script installe Mimica et toutes ses dépendances en une passe.%C_RESET%
echo %C_DIM%Durée estimée : 5–10 min selon ta connexion + ta machine.%C_RESET%
echo.
echo %C_DIM%Windows va te demander une confirmation UAC pour installer Python et Git.%C_RESET%
echo %C_DIM%Clique "Oui" quand la fenêtre apparaît.%C_RESET%
echo.
pause
echo.

REM ── Step 1: winget availability ────────────────────────────────────────────
echo %C_CYAN%%C_BOLD%[1/5]%C_RESET% %C_BOLD%Vérification de winget%C_RESET%
where winget >nul 2>nul
if errorlevel 1 (
  echo %C_RED%✗ winget introuvable.%C_RESET%
  echo %C_YELLOW%winget est inclus dans Windows 10 1809+ et Windows 11.%C_RESET%
  echo %C_YELLOW%Mets à jour Windows ou installe "App Installer" depuis le Microsoft Store.%C_RESET%
  pause
  exit /b 1
)
echo %C_GREEN%✓%C_RESET% winget disponible.
echo.

REM ── Step 2: Python 3.12 ────────────────────────────────────────────────────
echo %C_CYAN%%C_BOLD%[2/5]%C_RESET% %C_BOLD%Python 3.12%C_RESET%

REM Vérifie si python -V renvoie 3.10+
set "PY_OK="
where python >nul 2>nul
if not errorlevel 1 (
  for /F "tokens=2 delims= " %%v in ('python -V 2^>nul') do (
    for /F "tokens=1,2 delims=." %%a in ("%%v") do (
      if %%a GEQ 3 if %%b GEQ 10 set "PY_OK=1"
    )
  )
)

if defined PY_OK (
  for /F "tokens=*" %%v in ('python -V 2^>nul') do echo %C_GREEN%✓%C_RESET% Déjà installé ^(%%v^).
) else (
  echo %C_YELLOW%Installation via winget… une fenêtre UAC va apparaître.%C_RESET%
  winget install --id Python.Python.3.12 -e --silent --accept-package-agreements --accept-source-agreements
  if errorlevel 1 (
    echo %C_RED%✗ Échec de l'installation Python.%C_RESET%
    pause
    exit /b 1
  )
  REM Refresh PATH dans la session courante (winget l'ajoute mais cmd actuel ne le voit pas)
  for /F "tokens=*" %%p in ('powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable('Path','User') + ';' + [Environment]::GetEnvironmentVariable('Path','Machine')"') do set "PATH=%%p"
  echo %C_GREEN%✓%C_RESET% Installé.
)
echo.

REM ── Step 3: Git ────────────────────────────────────────────────────────────
echo %C_CYAN%%C_BOLD%[3/5]%C_RESET% %C_BOLD%Git%C_RESET%
where git >nul 2>nul
if not errorlevel 1 (
  for /F "tokens=*" %%v in ('git --version 2^>nul') do echo %C_GREEN%✓%C_RESET% Déjà installé ^(%%v^).
) else (
  echo %C_YELLOW%Installation via winget…%C_RESET%
  winget install --id Git.Git -e --silent --accept-package-agreements --accept-source-agreements
  if errorlevel 1 (
    echo %C_RED%✗ Échec de l'installation Git.%C_RESET%
    pause
    exit /b 1
  )
  REM Refresh PATH
  for /F "tokens=*" %%p in ('powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable('Path','User') + ';' + [Environment]::GetEnvironmentVariable('Path','Machine')"') do set "PATH=%%p"
  echo %C_GREEN%✓%C_RESET% Installé.
)
echo.

REM ── Step 4: Mimica source code ─────────────────────────────────────────────
echo %C_CYAN%%C_BOLD%[4/5]%C_RESET% %C_BOLD%Code source Mimica%C_RESET%
set "REPO_URL=https://github.com/muchoosauce/mimica.git"

REM Si on est déjà DANS un clone (app.py + launch.bat présents), on travaille ici.
if exist "app.py" if exist "launch.bat" (
  echo %C_GREEN%✓%C_RESET% Le repo est déjà ici, on l'utilise.
  set "REPO_DIR=%CD%"
  if exist ".git" (
    git pull --ff-only --quiet 2>nul && echo %C_GREEN%✓%C_RESET% Repo à jour. || echo %C_YELLOW%⚠ git pull skipped ^(local changes or offline^).%C_RESET%
  )
  goto :step5
)

REM Sinon on clone dans %LOCALAPPDATA%\Mimica\source
set "TARGET_DIR=%LOCALAPPDATA%\Mimica\source"
if exist "%TARGET_DIR%\.git" (
  echo %C_DIM%Mise à jour du clone existant…%C_RESET%
  pushd "%TARGET_DIR%"
  git pull --ff-only --quiet 2>nul || echo %C_YELLOW%⚠ git pull a échoué.%C_RESET%
  popd
) else (
  echo %C_DIM%Clonage dans %TARGET_DIR%…%C_RESET%
  if not exist "%LOCALAPPDATA%\Mimica" mkdir "%LOCALAPPDATA%\Mimica"
  git clone --quiet "%REPO_URL%" "%TARGET_DIR%"
  if errorlevel 1 (
    echo %C_RED%✗ Échec du clone. Si le repo est privé, configure un token GitHub d'abord.%C_RESET%
    pause
    exit /b 1
  )
)
set "REPO_DIR=%TARGET_DIR%"
echo %C_GREEN%✓%C_RESET% Code prêt.
echo.

:step5
REM ── Step 5: venv + dependencies via launch.bat ─────────────────────────────
echo %C_CYAN%%C_BOLD%[5/5]%C_RESET% %C_BOLD%Environnement virtuel + dépendances%C_RESET%
echo %C_DIM%On délègue à launch.bat qui sait déjà installer le venv,%C_RESET%
echo %C_DIM%PySide6, les providers SDK et Playwright Chromium.%C_RESET%
echo.
cd /d "%REPO_DIR%"

REM launch.bat se termine en lançant python app.py — fenêtre Mimica s'ouvre.
call launch.bat

REM ── Done ───────────────────────────────────────────────────────────────────
echo.
echo %C_GREEN%%C_BOLD%╔═══════════════════════════════════════════════════╗%C_RESET%
echo %C_GREEN%%C_BOLD%║              ✓ Installation terminée                ║%C_RESET%
echo %C_GREEN%%C_BOLD%╚═══════════════════════════════════════════════════╝%C_RESET%
echo.
echo   Pour relancer Mimica :
echo     %C_BOLD%double-clic sur launch.bat%C_RESET%
echo.
echo   Code installé dans :
echo     %C_DIM%%REPO_DIR%%C_RESET%
echo.
pause
endlocal
