@echo off
cd /d "%~dp0"
echo =====================================================================
echo  Starting LensQR with Cloudflare Tunnel
echo =====================================================================
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" run_with_tunnel.py %*
) else (
    python run_with_tunnel.py %*
)
pause
