@echo off
cd /d "%~dp0"
echo =====================================================================
echo  Starting LensQR Flask Server on 0.0.0.0:5000
echo =====================================================================
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" app.py %*
) else (
    python app.py %*
)
pause
