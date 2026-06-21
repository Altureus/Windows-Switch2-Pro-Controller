@echo off
title Switch 2 Pro -^> Xbox 360 bridge (for Dolphin)
echo ============================================================
echo   Switch 2 Pro Controller -^> virtual Xbox 360 pad
echo ============================================================
echo Starting bridge... keep this window open while you play.
echo When it says which XInput slot it is, click REFRESH in
echo Dolphin's controller config so Dolphin re-acquires it.
echo Press Ctrl+C (or just close this window) to stop.
echo ============================================================
echo.
python "%~dp0procon2\bridge.py"
echo.
echo Bridge stopped. Press any key to close.
pause >nul
