cd ..
pipenv run py -m src.build --release
cd scripts
if ERRORLEVEL 1 pause
