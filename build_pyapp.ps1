# Script to build standalone TorrentCreator using PyApp (Rust)
$ErrorActionPreference = "Stop"

Write-Host "=== Building TorrentCreator with Rust PyApp ===" -ForegroundColor Cyan

$RootDir = $PSScriptRoot
$PyAppDir = Join-Path $RootDir "build\pyapp\pyapp-v0.29.0"
$DistDir = Join-Path $RootDir "dist"
$VenvPython = Join-Path $RootDir ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    $VenvPython = "python"
}

# 1. Clean cache and temp files
Write-Host "1. Cleaning previous build artifacts..." -ForegroundColor Yellow
& $VenvPython -c "
import shutil, os, glob
for p in glob.glob('**/__pycache__', recursive=True): shutil.rmtree(p, ignore_errors=True)
if os.path.exists('build/bdist.win-amd64'): shutil.rmtree('build/bdist.win-amd64')
if os.path.exists('build/lib'): shutil.rmtree('build/lib')
for f in glob.glob('dist/*.whl'): 
    try: os.remove(f)
    except: pass
"

# 2. Build wheel
Write-Host "2. Building wheel package..." -ForegroundColor Yellow
& $VenvPython -m build --wheel
$WheelPath = (Get-ChildItem -Path $DistDir -Filter "*.whl" | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName

if (-not $WheelPath) {
    Write-Error "Wheel file not found in $DistDir"
}
Write-Host "Built wheel: $WheelPath" -ForegroundColor Green

# 3. Compile Rust PyApp launcher
Write-Host "3. Compiling Rust PyApp launcher..." -ForegroundColor Yellow
$env:PYAPP_PROJECT_PATH = $WheelPath
$env:PYAPP_PYTHON_VERSION = "3.12"
$env:PYAPP_EXEC_MODULE = "main"
$env:PYAPP_UV_ENABLED = "1"
$env:PYAPP_IS_GUI = "1"
$env:PYAPP_DISTRIBUTION_EMBED = "1"

Push-Location $PyAppDir
try {
    cargo build --release
} finally {
    Pop-Location
}

# 4. Copy to dist
$CompiledExe = Join-Path $PyAppDir "target\release\pyapp.exe"
$OutputExe = Join-Path $DistDir "TorrentCreator.exe"
Copy-Item $CompiledExe -Destination $OutputExe -Force

$SizeMB = [math]::Round((Get-Item $OutputExe).Length / 1MB, 2)
Write-Host "SUCCESS! Standalone executable created: $OutputExe ($SizeMB MB)" -ForegroundColor Green
