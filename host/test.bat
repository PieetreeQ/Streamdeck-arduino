@echo off
cd /d "%~dp0"
echo Test mode: press keys, nothing will be executed. Ctrl+C to quit.
python streamdeck.py --test
pause
