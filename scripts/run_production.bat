@echo off
cd ..
"dist/Sam.exe"
if ERRORLEVEL 1 pause
cd scripts
