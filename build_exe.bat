@echo off
REM ===========================================================================
REM Build Switch2ProBridge.exe -- a single, no-Python-needed executable of the
REM auto-detect launcher (launch.py). Output: dist\Switch2ProBridge.exe
REM Requires Python 3 + this repo. Installs the build tooling if missing.
REM ===========================================================================
echo Installing build tooling (pyinstaller, bleak)...
python -m pip install --quiet --upgrade pyinstaller bleak
echo.
echo Building Switch2ProBridge.exe ...
python -m PyInstaller --onefile --noconfirm --clean ^
  --name Switch2ProBridge ^
  --paths procon2 ^
  --add-data "procon2/vendor/ViGEmClient.dll;vendor" ^
  --collect-all bleak ^
  --collect-all winrt ^
  --hidden-import bridge --hidden-import ble_bridge --hidden-import ble_connect ^
  --hidden-import mapping --hidden-import mapping_data ^
  --hidden-import hid --hidden-import winusb --hidden-import haptics ^
  --hidden-import vigem --hidden-import xinput ^
  procon2\launch.py
echo.
echo Done.  ->  dist\Switch2ProBridge.exe
pause
