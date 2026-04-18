param(
    [string]$PythonExe = ".\.venv\Scripts\python.exe",
    [string]$InnoSetupCompiler = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

function Remove-BuildPath {
    param([string]$PathToRemove)

    if (-not (Test-Path $PathToRemove)) {
        return
    }

    try {
        Remove-Item -Recurse -Force $PathToRemove -ErrorAction Stop
    }
    catch {
        throw "Could not remove '$PathToRemove'. Make sure SpeechTyper is closed and no file from the previous build is still in use."
    }
}

function Resolve-InnoSetupCompiler {
    param([string]$RequestedPath)

    if ($RequestedPath -and (Test-Path $RequestedPath)) {
        return [string](Resolve-Path $RequestedPath).Path
    }

    $candidates = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    ) | Where-Object { $_ -and (Test-Path $_) }

    if ($candidates.Count -gt 0) {
        return [string]($candidates | Select-Object -First 1)
    }

    throw "Inno Setup 6 was not found. Install it or pass -InnoSetupCompiler <path-to-ISCC.exe>."
}

Write-Host "Cleaning old build output..."
Remove-BuildPath .\build\SpeechTyper
Remove-BuildPath .\dist\SpeechTyper
Remove-BuildPath .\release

if (-not (Test-Path .\assets\app-icon.ico)) {
    Write-Host "Generating app icon..."
    & .\scripts\generate-icon.ps1
}

Write-Host "Building packaged app..."
& $PythonExe -m PyInstaller .\SpeechTyper.spec --noconfirm --clean

$distRoot = Join-Path $ProjectRoot "dist\SpeechTyper"
if (-not (Test-Path (Join-Path $distRoot "SpeechTyper.exe"))) {
    throw "Packaged app was not created successfully."
}

$iscc = Resolve-InnoSetupCompiler -RequestedPath $InnoSetupCompiler

Write-Host "Building installer..."
& $iscc ".\installer\SpeechTyper.iss"
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup failed with exit code $LASTEXITCODE."
}

Write-Host ""
Write-Host "Done."
Write-Host "Installer:"
Get-ChildItem .\release\SpeechTyper-Setup.exe | Select-Object FullName, Length, LastWriteTime
