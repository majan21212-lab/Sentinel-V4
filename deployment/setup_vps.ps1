# Sentinel-V4 VPS Provisioning Script (Windows Server)
# This script installs Python, Node.js, and PM2 to prepare the VPS for 24/7 trading.

Write-Host "🚀 Initializing Sentinel-V4 Environment Setup..." -ForegroundColor Cyan

# 1. Install Chocolatey (Package Manager for Windows)
if (-(Get-Command choco -ErrorAction SilentlyContinue)) {
    Write-Host "✅ Chocolatey already installed."
} else {
    Write-Host "📦 Installing Chocolatey..."
    Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
}

# 2. Install Dependencies
Write-Host "📦 Installing Python, Node.js, and Git..."
choco install python --version=3.10.11 -y
choco install nodejs -y
choco install git -y

# 3. Install Global Process Manager (PM2)
Write-Host "📦 Installing PM2..."
npm install -g pm2

# 4. Refresh Environment Variables
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

Write-Host "🎉 Environment Ready! Please restart your terminal." -ForegroundColor Green
Write-Host "Next Step: git clone https://github.com/majan21212-lab/Sentinel-V4"
