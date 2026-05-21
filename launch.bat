@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo   Ad Variator - starting...
echo.

REM ─ Silent auto-update from GitHub before launching ────────────────
REM Mirrors launch.command on macOS. Skipped silently if not a git
REM clone, git missing, local changes present, or pull fails (offline).
if exist ".git" (
  where git >nul 2>nul
  if not errorlevel 1 (
    set HAS_LOCAL=
    for /f "delims=" %%i in ('git status --porcelain 2^>nul') do set HAS_LOCAL=1
    if not defined HAS_LOCAL (
      echo Checking for updates...
      for /f "delims=" %%i in ('git rev-parse HEAD 2^>nul') do set BEFORE=%%i
      set GIT_TERMINAL_PROMPT=0
      git pull --ff-only --quiet 2>nul
      for /f "delims=" %%i in ('git rev-parse HEAD 2^>nul') do set AFTER=%%i
      if not "!BEFORE!" == "!AFTER!" (
        for /f "delims=" %%i in ('git rev-parse --short HEAD 2^>nul') do echo Updated to %%i.
      )
    ) else (
      echo Local changes detected - skipping auto-update.
    )
  )
)

where python >nul 2>nul
if errorlevel 1 (
  where py >nul 2>nul
  if errorlevel 1 (
    echo Python 3 not found.
    echo Install from https://www.python.org/downloads/ and check "Add Python to PATH".
    pause
    exit /b 1
  )
  set "PY=py -3"
) else (
  set "PY=python"
)

if not exist ".venv" (
  echo Creating virtual environment...
  %PY% -m venv .venv
  if errorlevel 1 (
    echo Failed to create virtual environment.
    pause
    exit /b 1
  )
)

call ".venv\Scripts\activate.bat"

if not exist ".venv\.deps_installed" (
  echo Installing dependencies ^(first run can take ~1 min^)...
  python -m pip install --quiet --upgrade pip
  python -m pip install --quiet -r requirements.txt
  if errorlevel 1 (
    echo Dependency install failed.
    pause
    exit /b 1
  )
  echo ok > ".venv\.deps_installed"
)

if not exist ".venv\.playwright_installed" (
  echo Installing Playwright Chromium ^(one-time, ~150 MB^)...
  python -m playwright install chromium
  if errorlevel 1 (
    echo Playwright Chromium install failed. Brand DNA scraping will be unavailable.
    echo You can retry later with:  .venv\Scripts\python -m playwright install chromium
    pause
  ) else (
    echo ok > ".venv\.playwright_installed"
  )
)

python app.py
if errorlevel 1 pause
