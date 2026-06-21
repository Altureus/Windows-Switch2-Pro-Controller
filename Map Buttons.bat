@echo off
title Switch 2 Pro -- guided button ^& stick mapper
echo ============================================================
echo   Switch 2 Pro Controller -- button ^& stick mapper
echo ============================================================
echo It will name each control; press exactly that one.
echo   - press  s  or  Enter  to SKIP a control you don't have
echo   - press  q  to quit
echo First it calibrates: leave the controller ALONE for ~2s.
echo ============================================================
echo.
python "%~dp0procon2\map_buttons.py"
echo.
echo Mapping done (saved to procon2\mapping_data.py). Press any key to close.
pause >nul
