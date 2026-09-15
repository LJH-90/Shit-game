@echo off
cd /d "%~dp0"
rem Run from source without building an exe. Needs Python 3.10+.
rem Keep this file ASCII-only: "chcp 65001" + Korean text makes cmd misparse the batch.
where pythonw >nul 2>nul
if errorlevel 1 (
  echo [ERROR] python not found. Install from python.org and check "Add python.exe to PATH".
  pause
  exit /b 1
)
start "" pythonw molgam.py
rem Logic-only check:  python game.py --selftest
