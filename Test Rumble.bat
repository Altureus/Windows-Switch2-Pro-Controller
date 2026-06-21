@echo off
title Switch 2 Pro -- rumble test
echo Sending a SAFE 1.5s rumble (a value from ProCon2Tool's own haptic test).
echo Hold the controller so you can feel it. Close ProCon2Tool first if it's open.
echo.
python "%~dp0procon2\test_rumble.py"
echo.
pause
