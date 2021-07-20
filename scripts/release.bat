cd ..
pipenv run py -m src.build --release
if ERRORLEVEL 1 pause
