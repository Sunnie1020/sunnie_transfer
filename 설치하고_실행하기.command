#!/bin/bash
set -e

REPO_URL="https://github.com/Sunnie1020/sunnie_transfer.git"
REPO_DIR="sunnie_transfer"

cd "$(cd "$(dirname "$0")" && pwd)"

if ! command -v git >/dev/null 2>&1; then
    echo "[오류] Git이 설치되어 있지 않습니다."
    echo "터미널에서 xcode-select --install 명령을 실행해 설치한 뒤 다시 실행해주세요."
    read -p "엔터를 누르면 창이 닫힙니다..." _
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "[오류] Python3가 설치되어 있지 않습니다."
    echo "https://www.python.org/downloads/ 에서 설치한 뒤 다시 실행해주세요."
    read -p "엔터를 누르면 창이 닫힙니다..." _
    exit 1
fi

if [ -d "$REPO_DIR/.git" ]; then
    echo "최신 코드를 받아오는 중..."
    cd "$REPO_DIR"
    git pull
else
    echo "프로그램을 처음 받는 중..."
    git clone "$REPO_URL" "$REPO_DIR"
    cd "$REPO_DIR"
fi

if [ ! -d ".venv" ]; then
    echo "실행 환경을 준비하는 중... 처음 한 번만 시간이 걸립니다."
    python3 -m venv .venv
fi

source .venv/bin/activate

echo "필요한 라이브러리를 설치하는 중..."
python3 -m pip install --quiet --upgrade pip
python3 -m pip install --quiet -r requirements.txt

echo ""
echo "변환기를 실행합니다. 이 창을 닫으면 프로그램이 종료됩니다."
python3 app.py

read -p "엔터를 누르면 창이 닫힙니다..." _
