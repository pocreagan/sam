@ECHO OFF
cd ..
git add .
git commit -m "batch commit"
git push
if ERRORLEVEL 1 pause