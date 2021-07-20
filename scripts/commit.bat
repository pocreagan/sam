@ECHO OFF
cd ..
git add .
git commit -m "batch commit"
if ERRORLEVEL 1 pause