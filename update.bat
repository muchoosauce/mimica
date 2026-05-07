@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo   Mimica - checking for updates...
echo.

where git >nul 2>nul
if errorlevel 1 (
  echo git not found. Install from https://git-scm.com/download/win
  pause
  exit /b 1
)

if not exist ".git" (
  echo This folder is not a git clone. Re-clone the repository to enable updates.
  pause
  exit /b 1
)

REM Refuse to update if there are uncommitted changes — preserves any local
REM tweaks the user might have made.
for /f %%a in ('git status --porcelain ^| find /c /v ""') do set "DIRTY=%%a"
if not "%DIRTY%"=="0" (
  echo Local changes detected. Stash them first if you want to update:
  echo   git stash      ^(to save^)
  echo   git stash pop  ^(to restore later^)
  pause
  exit /b 1
)

echo Pulling latest changes...
for /f %%h in ('git rev-parse HEAD') do set "BEFORE=%%h"
git pull --ff-only
if errorlevel 1 (
  echo Pull failed.
  pause
  exit /b 1
)
for /f %%h in ('git rev-parse HEAD') do set "AFTER=%%h"

if "%BEFORE%"=="%AFTER%" (
  echo Already up to date.
  echo.
) else (
  for /f %%h in ('git rev-parse --short HEAD') do set "SHORT=%%h"
  echo Updated to !SHORT!.

  REM Refresh Python deps if requirements.txt changed in the pull.
  git diff --name-only %BEFORE%..%AFTER% | findstr /x "requirements.txt" >nul
  if not errorlevel 1 (
    if exist ".venv" (
      echo Refreshing Python dependencies...
      call ".venv\Scripts\activate.bat"
      python -m pip install --quiet --upgrade pip
      python -m pip install --quiet -r requirements.txt
      echo ok > ".venv\.deps_installed"
    )
  )
  echo.
)

echo Launching Mimica...
echo.
call launch.bat
