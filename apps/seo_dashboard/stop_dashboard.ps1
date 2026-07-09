$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$PidFile = Join-Path $Root ".dashboard_server.pid"

if (-not (Test-Path $PidFile)) {
    Write-Output "No dashboard pid file found."
    return
}

$processId = [int](Get-Content $PidFile)
$process = Get-Process -Id $processId -ErrorAction SilentlyContinue
if ($process) {
    Stop-Process -Id $processId
    Write-Output "Stopped SEO dashboard process $processId."
} else {
    Write-Output "Dashboard process $processId is not running."
}

Remove-Item $PidFile -Force

