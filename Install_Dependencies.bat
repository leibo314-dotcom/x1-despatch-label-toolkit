@echo off
cd /d "%~dp0"
py -3 -m pip install --upgrade pip
py -3 -m pip install -r requirements.txt
pause
