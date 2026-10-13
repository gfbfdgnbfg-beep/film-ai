@echo off
cd /d "%~dp0"
echo AI FILM FACTORY V0.5 - DESKTOP AGENT
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 desktop_agent\agent.py
) else (
  python desktop_agent\agent.py
)
echo.
echo Agent has stopped. Check the message above.
pause
