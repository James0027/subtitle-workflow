$ErrorActionPreference = "Stop"
$root = (Resolve-Path "$PSScriptRoot\..").Path
$python = "$root\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) { $python = "C:\Python312\python.exe" }

# Current-user DPAPI only. Never print the encrypted blob or decrypted value.
$credentialPath = $env:GEMINI_API_KEY_DPAPI_PATH
if (-not $credentialPath) {
    $workspace = (Resolve-Path "$root\..\..").Path
    $credentialPath = Join-Path $workspace 'work\首批落地准备\.local-secrets\gemini-api-key.dpapi'
}

$startInfo = New-Object System.Diagnostics.ProcessStartInfo
$startInfo.FileName = $python
$startInfo.Arguments = '-m uvicorn code.backend.main:app --host 127.0.0.1 --port 8765'
$startInfo.WorkingDirectory = $root
$startInfo.UseShellExecute = $false
$startInfo.CreateNoWindow = $true
$secureValue = $null
$keyPointer = [IntPtr]::Zero
try {
    if (Test-Path -LiteralPath $credentialPath) {
        $secureValue = Get-Content -LiteralPath $credentialPath -Raw | ConvertTo-SecureString
        $keyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureValue)
        $startInfo.EnvironmentVariables['GEMINI_API_KEY'] = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPointer)
    }
    # Explicit local-app audio/billing consent granted by the user on 2026-10-21.
    $startInfo.EnvironmentVariables['GEMINI_EXTERNAL_OUTBOUND_AUTHORIZED'] = '1'
    $startInfo.EnvironmentVariables['GEMINI_BUDGET_AUTHORIZED'] = '1'
    $process = [System.Diagnostics.Process]::Start($startInfo)
} catch {
    Write-Error 'Secure service launch failed. Check current-user DPAPI access and Python configuration.'
    exit 1
} finally {
    if ($keyPointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer) }
    $startInfo.EnvironmentVariables.Remove('GEMINI_API_KEY')
    if ($secureValue) { $secureValue.Dispose() }
}
# Keep the detached launcher alive; child inherits only the redirected log handles.
$process.WaitForExit()
exit $process.ExitCode
