@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-windows.ps1"
if errorlevel 1 (
  echo.
  echo WakeUp2 setup did not complete successfully.
  pause
  exit /b 1
)
echo.
pause
