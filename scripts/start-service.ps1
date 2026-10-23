$ErrorActionPreference = "Stop"
$root = (Resolve-Path "$PSScriptRoot\..").Path
$python = "$root\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "C:\Python312\python.exe"
}
if (-not (Test-Path $python)) {
    Write-Error "Python 解释器未找到：请确保 .venv 或 C:\Python312\python.exe 存在。"
    exit 1
}

$port = 8765
$infoFile = "$root\data\server-info.json"
$pidFile = "$root\data\server.pid"
$logOut = "$root\uvicorn.log"
$logErr = "$root\uvicorn.err.log"

New-Item -ItemType Directory -Path "$root\data" -Force | Out-Null

# 1. Check if port is already listening and verify identity
$conn = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | Where-Object { $_.State -eq 'Listen' }
if ($conn) {
    $existingPid = $conn.OwningProcess
    try {
        $wmi = Get-CimInstance Win32_Process -Filter "ProcessId = $existingPid" -ErrorAction Stop
        $cmd = $wmi.CommandLine
        if ($cmd -match "code\.backend\.main:app") {
            Write-Host "服务已经在运行中："
            Write-Host "  URL: http://127.0.0.1:$port"
            Write-Host "  PID: $existingPid"
            exit 0
        } else {
            Write-Warning "端口 $port 已被其他进程占用 (PID: $existingPid, 命令行: $cmd)。启动中止以防冲突。"
            exit 1
        }
    } catch {
        Write-Warning "端口 $port 已被占用 (PID: $existingPid)。"
        exit 1
    }
}

# 2. Launch persistent hidden background process via Win32_Process (detached from session tree)
$secureLauncher = "$PSScriptRoot\launch-service-secure.ps1"
$cmdToRun = "cmd.exe /c powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$secureLauncher`" >> `"$logOut`" 2>> `"$logErr`""
$procRes = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
    CommandLine = $cmdToRun
    CurrentDirectory = $root
}

if ($procRes.ReturnValue -ne 0) {
    Write-Error "Win32_Process 创建失败，错误代码: $($procRes.ReturnValue)"
    exit 1
}

$launcherPid = $procRes.ProcessId

# 3. Wait up to 10 seconds for service health endpoint and capture the actual listener PID
$ready = $false
$actualPid = $launcherPid

for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Milliseconds 500
    $c = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | Where-Object { $_.State -eq 'Listen' }
    if ($c) {
        $actualPid = $c.OwningProcess
        # Test health via python script bypassing any proxy
        try {
            $hCheck = & $python -c "import urllib.request, json; opener = urllib.request.build_opener(urllib.request.ProxyHandler({})); res = opener.open('http://127.0.0.1:$port/api/v1/health', timeout=1.5); print(json.loads(res.read().decode())['status'])" 2>$null
            if ($hCheck -eq "healthy") {
                $ready = $true
                break
            }
        } catch {}
    }
}

# 4. Record server metadata with actual PID
$serverInfo = @{
    pid = $actualPid
    launcher_pid = $launcherPid
    port = $port
    host = "127.0.0.1"
    python = $python
    working_dir = $root
    app_target = "code.backend.main:app"
    log_file = $logOut
    started_at = (Get-Date).ToString("o")
} | ConvertTo-Json

$serverInfo | Out-File -FilePath $infoFile -Encoding utf8
$actualPid | Out-File -FilePath $pidFile -Encoding ascii

if ($ready) {
    Write-Host "字幕工作流服务已成功启动并就绪："
    Write-Host "  URL: http://127.0.0.1:$port"
    Write-Host "  PID: $actualPid"
    Write-Host "  日志文件: $logOut"
    exit 0
} else {
    Write-Warning "服务已派发启动，但在 10 秒内未检测到健康检查正常返回。"
    if (Test-Path $logErr) {
        Write-Host "--- 错误日志 ---"
        Get-Content $logErr -Tail 20
    }
    exit 1
}
