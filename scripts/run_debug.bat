@echo off
cd ..
"dist/Sam - Debug Build/Sam.exe"
if ERRORLEVEL 1 pause
cd scripts