@echo off
chcp 65001 >nul
setlocal

set "REPO_URL=https://github.com/Sunnie1020/sunnie_transfer.git"
set "REPO_DIR=sunnie_transfer"

cd /d %~dp0

where git >nul 2>nul
if errorlevel 1 (
    echo [오류] Git이 설치되어 있지 않습니다.
    echo https://git-scm.com/download/win 에서 설치한 뒤 다시 실행해주세요.
    pause
    exit /b 1
)

where python >nul 2>nul
if errorlevel 1 (
    echo [오류] Python이 설치되어 있지 않습니다.
    echo https://www.python.org/downloads/ 에서 설치한 뒤 다시 실행해주세요.
    echo 설치 화면에서 "Add python.exe to PATH" 체크박스를 꼭 체크해주세요.
    pause
    exit /b 1
)

if exist "%REPO_DIR%\.git" (
    echo 최신 코드를 받아오는 중...
    cd "%REPO_DIR%"
    git pull
) else (
    echo 프로그램을 처음 받는 중...
    git clone "%REPO_URL%" "%REPO_DIR%"
    if errorlevel 1 (
        echo [오류] 다운로드에 실패했습니다. 인터넷 연결을 확인해주세요.
        pause
        exit /b 1
    )
    cd "%REPO_DIR%"
)

if not exist ".venv" (
    echo 실행 환경을 준비하는 중... 처음 한 번만 시간이 걸립니다.
    python -m venv .venv
)

call ".venv\Scripts\activate.bat"

echo 필요한 라이브러리를 설치하는 중...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt

echo.
echo 변환기를 실행합니다. 이 창을 닫으면 프로그램이 종료됩니다.
python app.py

pause
