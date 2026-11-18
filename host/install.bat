@echo off
cd /d "%~dp0"
echo Installing Python libraries...
python -m pip install -r requirements.txt
echo.
echo Done. Now run test.bat
pause
