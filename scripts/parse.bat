@echo off
cd ..
pipenv run py -m src.build
cd scripts
if ERRORLEVEL 1 pause