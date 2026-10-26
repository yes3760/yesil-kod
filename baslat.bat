@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PY=python
where python >nul 2>nul || set PY=py -3
%PY% --version >nul 2>nul
if errorlevel 1 (
  echo Python bulunamadi. https://www.python.org/downloads/ adresinden kurun ve "Add to PATH" kutusunu isaretleyin.
  pause
  exit /b 1
)
set PYTHONUTF8=1
%PY% -m greencode
pause
