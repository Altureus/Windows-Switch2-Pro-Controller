@echo off
title Switch 2 Pro -- full-chain rumble test
echo Simulates a Dolphin rumble and forwards it to the controller.
echo HOLD THE CONTROLLER. Close ProCon2Tool first if it's open.
echo.
python "%~dp0procon2\test_rumble_e2e.py"
echo.
pause
