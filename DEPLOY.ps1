# Sentinel V4 - Cloud Deployment Script
# Run this on your Windows VPS as Administrator

echo "🚀 Starting Sentinel V4 Cloud Provisioning..."

# 1. Install Choco (Package Manager) if not present
if (!(Get-Command choco -ErrorAction SilentlyContinue)) {
    echo "📦 Installing Chocolatey..."
    Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
}

# 2. Install Dependencies
echo "📦 Installing Python 3.11 and Git..."
choco install python --version=3.11.5 -y
choco install git -y
choco install nssm -y

# 3. Setup Virtual Environment
echo "🐍 Setting up Python Environment..."
python -m venv venv
.\venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt

# 4. Configure Firewall for Dashboard
echo "🛡️ Opening Port 8000 for Mobile Access..."
New-NetFirewallRule -DisplayName "Sentinel_FastAPI" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow

# 5. Create Always-on Service (NSSM)
echo "⚙️ Creating Sentinel Background Service..."
# Note: You should be in the f:\TradeBot directory for this to work perfectly.
nssm install SentinelService "$(Get-Location)\venv\Scripts\python.exe" "$(Get-Location)\app.py"
nssm set SentinelService AppDirectory "$(Get-Location)"
nssm start SentinelService

echo "✅ Sentinel V4 is now Running in the Background."
echo "🔗 Dashboard: http://localhost:8000"
