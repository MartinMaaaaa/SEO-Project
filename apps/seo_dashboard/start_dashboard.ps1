param(
    [int]$Port = 8766
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$PidFile = Join-Path $Root ".dashboard_server.pid"
$OutLog = Join-Path $PSScriptRoot "server.out.log"
$ErrLog = Join-Path $PSScriptRoot "server.err.log"

$existing = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($existing) {
    Write-Output "SEO dashboard is already listening on http://127.0.0.1:$Port"
    return
}

$python = (Get-Command python).Source

$psi = [System.Diagnostics.ProcessStartInfo]::new()
$psi.FileName = $python
$psi.Arguments = "-u apps/seo_dashboard/server.py $Port"
$psi.WorkingDirectory = $Root
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true
$psi.RedirectStandardOutput = $false
$psi.RedirectStandardError = $false
$process = [System.Diagnostics.Process]::new()
$process.StartInfo = $psi
[void]$process.Start()

$process.Id | Set-Content -Path $PidFile -Encoding ASCII
Start-Sleep -Seconds 1

$listening = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listening) {
    Write-Output "SEO dashboard started: http://127.0.0.1:$Port"
    Write-Output "PID: $($process.Id)"
} else {
    Write-Output "Dashboard did not start. Check logs:"
    Write-Output $OutLog
    Write-Output $ErrLog
}
