@echo off
TITLE Sentinel-V4 Autonomous Launcher
echo 🚀 Starting Sentinel-V4 24/7 Mission Control...

:: Navigate to Project Directory
cd /d %~dp0\..

:: Start Backend (Python)
echo 🐍 Launching Python Backend Service...
pm2 start app.py --name "sentinel-backend" --interpreter python

:: Start Dashboard (Vite)
echo 🌐 Launching React Frontend Service...
pm2 start "npm run dev" --name "sentinel-dashboard" --cwd "../../.."

:: Save PM2 List for Auto-Restart on VPS Reboot
pm2 save

echo 🎉 Sentinel-V4 is now ONLINE in the background.
echo Check logs with: pm2 logs
pause
