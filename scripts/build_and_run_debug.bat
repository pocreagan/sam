@echo off
cd ..
pipenv run py -m src.build --debug
if ERRORLEVEL 1 goto paused
"dist/Sam - Debug Build/Sam.exe"
if ERRORLEVEL 0 goto end
:paused
pause
:end
cd scripts