Write-Output "--- Starting Sentinel-V4 Deployment Run 15 ---"
Get-Date

# 1. Terminate all active python processes to free port 8000 and MT5 connection
Write-Output "Stopping all active python processes..."
Stop-Process -Name python -Force -ErrorAction SilentlyContinue
Stop-Process -Name pythonw -Force -ErrorAction SilentlyContinue
Stop-ScheduledTask -TaskName "SentinelBot" -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName "SentinelBot" -Confirm:$false -ErrorAction SilentlyContinue

# 2. Sync and clean git repository in C:\TradeBot
Write-Output "Syncing C:\TradeBot repository..."
$git = "C:\Program Files\Git\cmd\git.exe"
if (Test-Path $git) {
    Set-Location "C:\TradeBot"
    & $git fetch origin
    & $git reset --hard origin/main
}

# 3. Ensure python requirements are fully installed
Write-Output "Installing python requirements on C:\Python311\python.exe..."
if (Test-Path "C:\Python311\python.exe") {
    & C:\Python311\python.exe -m pip install -r C:\TradeBot\requirements.txt
}

# 4. Register scheduled task under majan21212
Write-Output "Registering SentinelBot scheduled task under user majan21212..."
$Action = New-ScheduledTaskAction -Execute "C:\Python311\python.exe" -Argument "app.py" -WorkingDirectory "C:\TradeBot"
$Trigger = New-ScheduledTaskTrigger -AtStartup
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -Enabled

try {
    # We specify Domain as the local computer name MAJAN21212-BOT to ensure correct mapping
    $username = "MAJAN21212-BOT\majan21212"
    $password = "-1It7R[xf_!Y5f3"
    
    Register-ScheduledTask -TaskName "SentinelBot" -Action $Action -Trigger $Trigger -Settings $Settings -User $username -Password $password -Force
    Write-Output "Scheduled task registered successfully as $username!"
    
    Start-ScheduledTask -TaskName "SentinelBot"
    Write-Output "Scheduled task started."
} catch {
    Write-Output "Failed to register scheduled task as majan21212: $_"
}

# 5. Wait 20 seconds and check running processes and owners
Write-Output "Sleeping 20 seconds to allow initialization..."
Start-Sleep -Seconds 20

Write-Output "=== Active Python Processes ==="
$pyProcs = Get-Process python -ErrorAction SilentlyContinue
if ($pyProcs) {
    foreach ($proc in $pyProcs) {
        $owner = (Get-CimInstance Win32_Process -Filter "ProcessId = $($proc.Id)").GetOwner().User
        Write-Output "PID: $($proc.Id) | Owner: $owner | Path: $($proc.Path)"
    }
} else {
    Write-Output "No running python processes found!"
}

# 6. Check web server port binding (8000)
Write-Output "=== Port Binding Check (Port 8000) ==="
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Format-Table -AutoSize | Out-String | Write-Output

Write-Output "--- Patch 15 Completed ---"
