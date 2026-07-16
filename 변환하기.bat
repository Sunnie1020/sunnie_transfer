@echo off
chcp 65001 >nul
setlocal
cd /d %~dp0

if "%~1"=="" (
    echo 변환할 이미지 파일을 이 배치파일 위로 끌어다 놓아주세요.
    echo.
    pause
    exit /b 1
)

set INPUT=%~1

echo 변환할 파일: %INPUT%
echo.
set /p FORMAT=목표 포맷을 입력하세요 (jpg, png, webp, bmp, gif, tiff):

echo.
python test_convert.py "%INPUT%" %FORMAT%

echo.
pause
