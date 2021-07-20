@echo off
cd ..
pipenv run py -m src.app
if ERRORLEVEL 1 pause
cd scripts
