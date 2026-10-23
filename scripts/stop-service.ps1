$ErrorActionPreference = "Continue"
$root = (Resolve-Path "$PSScriptRoot\..").Path
$infoFile = "$root\data\server-info.json"
$pidFile = "$root\data\server.pid"
$port = 8765

# Function to safely kill an application process if and only if identity matches
function Stop-OurProcess([int]$pidToKill) {
    if (-not $pidToKill -or $pidToKill -le 0) { return $false }
    try {
        $proc = Get-Process -Id $pidToKill -ErrorAction Stop
        $wmi = Get-CimInstance Win32_Process -Filter "ProcessId = $pidToKill" -ErrorAction SilentlyContinue
        $cmd = if ($wmi) { $wmi.CommandLine } else { "" }
        $execPath = if ($wmi) { $wmi.ExecutablePath } else { $proc.Path }

        $isOurServer = ($cmd -match "code\.backend\.main:app") -or ($cmd -match "uvicorn" -and ($cmd -match [regex]::Escape($root) -or $execPath -match [regex]::Escape($root)))

        if ($isOurServer) {
            Write-Host "正在终止字幕服务进程 (PID: $pidToKill, 命令行: $cmd)..."
            Stop-Process -Id $pidToKill -Force -ErrorAction SilentlyContinue
            Start-Sleep -Milliseconds 600
            return $true
        } else {
            Write-Warning "PID $pidToKill 不是字幕服务进程 (命令行: $cmd)，拒绝终止以防误杀其他进程！"
            return $false
        }
    } catch {
        return $false
    }
}

$killedAny = $false

# 1. Check PID from files
if (Test-Path $infoFile) {
    try {
        $info = Get-Content $infoFile -Raw | ConvertFrom-Json
        if (Stop-OurProcess -pidToKill $info.pid) { $killedAny = $true }
    } catch {}
}

if (Test-Path $pidFile) {
    try {
        $fPid = [int]((Get-Content $pidFile).Trim())
        if (Stop-OurProcess -pidToKill $fPid) { $killedAny = $true }
    } catch {}
}

# 2. Check who is listening on port 8765
$conn = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | Where-Object { $_.State -eq 'Listen' }
if ($conn) {
    $portPid = $conn.OwningProcess
    if (Stop-OurProcess -pidToKill $portPid) { $killedAny = $true }
}

# 3. Clean up info files
Remove-Item $infoFile, $pidFile -Force -ErrorAction SilentlyContinue

# 4. Final verification
$connAfter = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | Where-Object { $_.State -eq 'Listen' }
if ($connAfter) {
    Write-Warning "端口 $port 仍被占用 (PID: $($connAfter.OwningProcess))，请人工核查。"
} else {
    Write-Host "服务进程已安全停止，端口 $port 空闲。"
}
