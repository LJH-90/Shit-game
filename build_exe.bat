@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

rem ------------------------------------------------------------
rem  출력 exe 이름. 작업관리자에 이 이름으로 표시됩니다. 원하는 대로 바꾸세요.
set EXE_NAME=SystemSettingsHelper
rem ------------------------------------------------------------

echo ============================================
echo   MolGam - exe 빌드  (%EXE_NAME%.exe)
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo [오류] python 을 찾을 수 없습니다.
  echo        https://www.python.org/downloads/windows/ 에서 설치하고
  echo        설치 화면의 "Add python.exe to PATH" 를 반드시 체크하세요.
  pause
  exit /b 1
)

echo [0/3] 게임 로직 자체 검증...
python game.py --selftest
if errorlevel 1 (
  echo [경고] 자체 검증에 실패했습니다. 그래도 빌드하려면 아무 키나 누르세요.
  pause
)

echo.
echo [1/3] PyInstaller 설치 확인...
python -m PyInstaller --version >nul 2>nul
if errorlevel 1 (
  python -m pip install pyinstaller
  if errorlevel 1 (
    echo [오류] PyInstaller 설치에 실패했습니다. 인터넷 연결을 확인하세요.
    pause
    exit /b 1
  )
)

echo.
echo [2/3] 빌드 중... (1~2분 걸립니다)
rem  --add-data 로 stages.json / config.json 을 exe 안에 동봉합니다.
rem  실행 시에는 exe 옆 폴더의 파일을 먼저 읽고, 없으면 동봉본을 씁니다.
python -m PyInstaller --onefile --noconsole --clean --name %EXE_NAME% ^
  --add-data "stages.json;." --add-data "config.json;." molgam.py
if errorlevel 1 (
  echo [오류] 빌드에 실패했습니다.
  pause
  exit /b 1
)

copy /y stages.json dist\ >nul
copy /y config.json dist\ >nul

echo.
echo [3/3] 완료
echo   실행 파일: %CD%\dist\%EXE_NAME%.exe
echo   설정 파일: %CD%\dist\config.json, stages.json  (exe 옆에 두면 그 파일을 우선 사용)
echo.
echo   백신이 처음 실행을 막을 수 있습니다. PyInstaller 단일 exe 의 알려진 오탐입니다.
echo.
pause
