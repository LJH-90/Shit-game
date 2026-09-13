@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem exe 로 만들지 않고 소스에서 바로 실행합니다. (Python 3.10 이상 필요)
where pythonw >nul 2>nul
if errorlevel 1 (
  echo [오류] python 을 찾을 수 없습니다. python.org 에서 설치 후 "Add python.exe to PATH" 를 체크하세요.
  pause
  exit /b 1
)
start "" pythonw molgam.py
rem 로직만 검증하려면:  python game.py --selftest
