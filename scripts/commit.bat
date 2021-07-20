@ECHO OFF
cd ..
git add .
git commit -m "batch commit"
git push
cd scripts
if ERRORLEVEL 1 pause
