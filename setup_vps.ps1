# Sentinel-V4 VPS Setup Script
# Run this script with Administrator privileges on the VPS.

Write-Host "--- Initializing Sentinel-V4 Setup on VPS (34.26.143.224) ---" -ForegroundColor Cyan

# 1. Install Dependencies
Write-Host "[1/3] Installing Python dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt

# 2. Configure Firewall
Write-Host "[2/3] Configuring Windows Firewall for Dashboard..." -ForegroundColor Yellow
New-NetFirewallRule -DisplayName "Sentinel_Dashboard" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow -ErrorAction SilentlyContinue
New-NetFirewallRule -DisplayName "Sentinel_Web_Public" -Direction Inbound -LocalPort 80 -Protocol TCP -Action Allow -ErrorAction SilentlyContinue

# 3. Create Persistence Task (Optional but recommended)
Write-Host "[3/3] Setting up background persistence..." -ForegroundColor Yellow
# This creates a task that runs on system startup
$Action = New-ScheduledTaskAction -Execute "python.exe" -Argument "f:\TradeBot\app.py" -WorkingDirectory "f:\TradeBot"
$Trigger = New-ScheduledTaskTrigger -AtStartup
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName "SentinelBot" -Action $Action -Trigger $Trigger -Settings $Settings -User "SYSTEM" -Force

Write-Host "--- Setup Complete! ---" -ForegroundColor Green
Write-Host "You can now start the bot manually with: python app.py"
Write-Host "Access Dashboard at: http://34.26.143.224:8000"
