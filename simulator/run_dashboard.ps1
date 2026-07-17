param([int]$Port = 8501)

$ErrorActionPreference = "Stop"
$workdir = $PSScriptRoot
$python = if ($env:CAIMAN_PYTHON) { $env:CAIMAN_PYTHON } else { (Get-Command python).Source }
$stdout = Join-Path $workdir "streamlit.stdout.log"
$stderr = Join-Path $workdir "streamlit.stderr.log"

$healthy = $false
try {
    $healthy = (Invoke-WebRequest -UseBasicParsing "http://localhost:$Port/_stcore/health" -TimeoutSec 2).Content -eq "ok"
} catch {
    $healthy = $false
}
if ($healthy) {
    Write-Output "Caiman dashboard is already running at http://localhost:$Port"
    exit 0
}

$process = Start-Process -FilePath $python `
    -ArgumentList "-m", "streamlit", "run", "app.py", "--server.headless", "true", "--server.port", "$Port", "--browser.gatherUsageStats", "false", "--server.fileWatcherType", "none" `
    -WorkingDirectory $workdir `
    -WindowStyle Hidden `
    -RedirectStandardOutput $stdout `
    -RedirectStandardError $stderr `
    -PassThru

for ($attempt = 0; $attempt -lt 20; $attempt++) {
    Start-Sleep -Milliseconds 250
    try {
        if ((Invoke-WebRequest -UseBasicParsing "http://localhost:$Port/_stcore/health" -TimeoutSec 2).Content -eq "ok") {
            Write-Output "Caiman dashboard started: PID=$($process.Id) URL=http://localhost:$Port"
            exit 0
        }
    } catch {}
}

throw "Dashboard did not become healthy. Check $stderr"
