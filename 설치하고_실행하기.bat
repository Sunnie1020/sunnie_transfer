@echo off
setlocal

set "REPO_URL=https://github.com/Sunnie1020/sunnie_transfer.git"
set "REPO_DIR=sunnie_transfer"

cd /d %~dp0

where git >nul 2>nul
if errorlevel 1 goto :no_git

where python >nul 2>nul
if errorlevel 1 goto :no_python

if exist "%REPO_DIR%\.git" goto :pull_repo
goto :clone_repo

:pull_repo
echo Getting the latest version...
cd "%REPO_DIR%"
git pull
goto :setup_env

:clone_repo
echo Downloading for the first time...
git clone "%REPO_URL%" "%REPO_DIR%"
if errorlevel 1 goto :clone_failed
cd "%REPO_DIR%"
goto :setup_env

:setup_env
if exist ".venv" goto :install_deps
echo Preparing the environment, this happens only once...
python -m venv .venv

:install_deps
call ".venv\Scripts\activate.bat"
echo Installing required libraries...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt

echo.
echo Starting the converter. Close this window to stop it.
python app.py

pause
exit /b 0

:no_git
echo [ERROR] Git is not installed.
echo Please install it from https://git-scm.com/download/win and run this again.
pause
exit /b 1

:no_python
echo [ERROR] Python is not installed.
echo Please install it from https://www.python.org/downloads/ and run this again.
echo During install, make sure to check "Add python.exe to PATH".
pause
exit /b 1

:clone_failed
echo [ERROR] Download failed. Please check your internet connection.
pause
exit /b 1
