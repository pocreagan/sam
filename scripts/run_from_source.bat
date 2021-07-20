cd ..
pipenv run py -m src.app
cd scripts
if ERRORLEVEL 1 pause
