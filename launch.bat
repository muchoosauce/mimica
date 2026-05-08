@echo off
setlocal
cd /d "%~dp0"

echo.
echo   Ad Variator - starting...
echo.

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
