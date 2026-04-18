param(
    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPath = Join-Path $ProjectRoot ".venv"

if (-not (Test-Path $VenvPath)) {
    & $PythonExe -m venv $VenvPath
}

$Python = Join-Path $VenvPath "Scripts\python.exe"

& $Python -m pip install --upgrade pip
& $Python -m pip install -r (Join-Path $ProjectRoot "requirements.txt")

$DataPath = Join-Path $ProjectRoot "data"
if (-not (Test-Path $DataPath)) {
    New-Item -ItemType Directory -Path $DataPath | Out-Null
}

$ModelsPath = Join-Path $ProjectRoot "models"
if (-not (Test-Path $ModelsPath)) {
    New-Item -ItemType Directory -Path $ModelsPath | Out-Null
}

Write-Host ""
Write-Host "Setup complete."
Write-Host "Next:"
Write-Host "  1. Extract one or more Vosk models into $ModelsPath"
Write-Host "  2. Run $Python .\src\main.py"
