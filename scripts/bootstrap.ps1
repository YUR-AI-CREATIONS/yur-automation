# FranklinOps - All-in-One Bootstrap
# Double-click bootstrap.bat to run

$Host.UI.RawUI.WindowTitle = "FranklinOps"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

# Data lives in project folder (avoids AppData/roaming path issues)
$env:FRANKLINOPS_DATA_DIR = Join-Path $Root "data\franklinops"
$env:FRANKLINOPS_DB_PATH = Join-Path $Root "data\franklinops\ops.db"
New-Item -ItemType Directory -Force -Path $env:FRANKLINOPS_DATA_DIR | Out-Null

Write-Host ""
Write-Host "  FRANKLINOPS - All-in-One Bootstrap" -ForegroundColor Cyan
Write-Host ""

# Pre-flight: warn if winget might be busy (another installer running)
$wingetProc = Get-Process -Name "winget" -ErrorAction SilentlyContinue
if ($wingetProc) {
    Write-Host "  WARNING: Another winget/installer may be running." -ForegroundColor Yellow
    Write-Host "  If install hangs, close other installers and run again." -ForegroundColor Gray
    Write-Host ""
}

# Refresh PATH from registry
$machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
$env:Path = $machinePath + ";" + $userPath

# Python
$py = $null
try { $null = & python --version 2>&1; $py = "python" } catch {}
if (-not $py) { try { $null = & py -3 --version 2>&1; $py = "py -3" } catch {} }
if (-not $py) {
    Write-Host "  Python not found. Installing..." -ForegroundColor Yellow
    $pyResult = $null
    try {
        $pyResult = winget install Python.Python.3.11 --accept-package-agreements --accept-source-agreements 2>&1
        if ($LASTEXITCODE -ne 0) { throw "winget exit $LASTEXITCODE" }
    } catch {
        Write-Host "  Winget install failed. Install manually:" -ForegroundColor Red
        Write-Host "  https://www.python.org/downloads/ (check Add Python to PATH)" -ForegroundColor Gray
        Write-Host "  See TROUBLESHOOTING.md for more." -ForegroundColor Gray
        Read-Host "  Press Enter to exit"
        exit 1
    }
    Write-Host "  Waiting 15s for PATH to refresh..." -ForegroundColor Gray
    Start-Sleep 15
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = $machinePath + ";" + $userPath
    $py = "python"
}

# Ollama (optional)
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "  Ollama not found. Installing (for AI)..." -ForegroundColor Yellow
    try {
        $null = winget install Ollama.Ollama --accept-package-agreements --accept-source-agreements 2>&1
        if ($LASTEXITCODE -ne 0) { throw "winget exit $LASTEXITCODE" }
    } catch {
        Write-Host "  Winget install failed. Install manually: https://ollama.ai" -ForegroundColor Yellow
        Write-Host "  (AI will work after you install Ollama and run: ollama pull llama3)" -ForegroundColor Gray
    }
    Write-Host "  Waiting 15s for PATH to refresh..." -ForegroundColor Gray
    Start-Sleep 15
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = $machinePath + ";" + $userPath
}

# Deps
& $py -m pip install -r requirements-minimal.txt -q 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  Pip install had issues. Retrying..." -ForegroundColor Yellow
    & $py -m pip install -r requirements-minimal.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Pip failed. See TROUBLESHOOTING.md" -ForegroundColor Red
        Read-Host "  Press Enter to exit"
        exit 1
    }
}

# Model - pull and wait so llama3 is ready when app opens
if (Get-Command ollama -ErrorAction SilentlyContinue) {
    $listOut = cmd /c "ollama list 2>nul"
    $hasLlama = $listOut | Select-String "llama3"
    if (-not $hasLlama) {
        Write-Host "  Pulling llama3 (~4GB, first run only)..." -ForegroundColor Gray
        $errFile = Join-Path $env:TEMP "ollama-stderr.txt"
        $outFile = Join-Path $env:TEMP "ollama-stdout.txt"
        Start-Process -FilePath "ollama" -ArgumentList "pull","llama3" -Wait -WindowStyle Hidden -RedirectStandardError $errFile -RedirectStandardOutput $outFile
        Remove-Item $errFile,$outFile -Force -ErrorAction SilentlyContinue
        Write-Host "  Done." -ForegroundColor Green
    } else {
        Write-Host "  llama3 ready." -ForegroundColor Green
    }
}

# Free port 8844 if already in use (from previous run)
$lines = netstat -ano 2>$null | Select-String ":8844"
foreach ($m in $lines) {
    if ($m.Line -match "LISTENING\s+(\d+)$") {
        $oldPid = $Matches[1]
        Write-Host "  Stopping previous FranklinOps (PID $oldPid)..." -ForegroundColor Gray
        Stop-Process -Id $oldPid -Force -ErrorAction SilentlyContinue
        Start-Sleep 3
        break
    }
}

# Run
Write-Host "  Starting... Browser opens in 5s." -ForegroundColor Green
Write-Host "  Having trouble? See TROUBLESHOOTING.md" -ForegroundColor Gray
Write-Host ""
Start-Job { Start-Sleep 5; Start-Process "http://127.0.0.1:8844/ui/boot" } | Out-Null
& $py -m uvicorn src.franklinops.server:app --host 127.0.0.1 --port 8844
