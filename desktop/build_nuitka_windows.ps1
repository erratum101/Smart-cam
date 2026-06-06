# Build Smart Cam App.exe with Nuitka (PySide6).
# Usage:
#   .\build_nuitka_windows.ps1
#   .\build_nuitka_windows.ps1 -Debug
#   .\build_nuitka_windows.ps1 -Standalone
#   .\build_nuitka_windows.ps1 -Clean
param(
    [switch]$Debug,
    [switch]$Standalone,
    [switch]$Clean,
    [string]$AppName = "Smart Cam App"
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$projectRoot = $PSScriptRoot
$repoRoot = Split-Path -Parent $projectRoot
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$python = if (Test-Path $venvPython) {
    $venvPython
} else {
    (Get-Command python -ErrorAction Stop).Source
}

Write-Host ("Python: " + $python)

$appIcon = Join-Path $PSScriptRoot "app_icon.png"
$fallbackIcon = Join-Path $PSScriptRoot "icon.png"
if (-not (Test-Path $appIcon)) {
    if (Test-Path $fallbackIcon) {
        Copy-Item -Force $fallbackIcon $appIcon
    } else {
        Write-Error "Missing app_icon.png or icon.png in desktop/ (same folder as this script)."
    }
}

# Keep executable display name, but avoid spaces/special chars in build folders.
$safeBuildName = ($AppName -replace '[^A-Za-z0-9_.-]+', '_').Trim('_')
if ([string]::IsNullOrWhiteSpace($safeBuildName)) {
    $safeBuildName = "Smart_Cam_App"
}
$buildRoot = Join-Path $projectRoot ("build-" + $safeBuildName)
$nuitkaDir = Join-Path $buildRoot "build-nuitka"
$standaloneDir = Join-Path $buildRoot "build-standalone"
New-Item -ItemType Directory -Force -Path $buildRoot | Out-Null
New-Item -ItemType Directory -Force -Path $nuitkaDir | Out-Null
New-Item -ItemType Directory -Force -Path $standaloneDir | Out-Null

if ($Clean) {
    Write-Host "Cleaning previous Nuitka artifacts..."
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue (Join-Path $nuitkaDir "*.build")
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue (Join-Path $nuitkaDir "*.dist")
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue (Join-Path $nuitkaDir "*.onefile-build")
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue (Join-Path $standaloneDir "*.build")
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue (Join-Path $standaloneDir "*.dist")
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue (Join-Path $standaloneDir "*.onefile-build")
}

& $python -m pip install --upgrade pip setuptools wheel
& $python -m pip install -r requirements.txt
& $python -m pip install "nuitka>=2.3"
& $python make_icon.py

$consoleMode = if ($Debug) { "--windows-console-mode=force" } else { "--windows-console-mode=disable" }
$outputExeName = "$AppName.exe"

$common = @(
    "--assume-yes-for-downloads",
    "--remove-output",
    "--windows-uac-admin",
    $consoleMode,
    "--windows-icon-from-ico=app_icon.ico",
    "--enable-plugin=pyside6",
    "--include-qt-plugins=sensible",
    "--include-package=smart_cam",
    "--include-data-files=app_icon.png=app_icon.png",
    "--nofollow-import-to=pytest",
    "--nofollow-import-to=tests",
    "main.py"
)

if ($Standalone) {
    & $python -m nuitka `
        --standalone `
        --output-dir=$standaloneDir `
        --output-filename=$outputExeName `
        @common
    Write-Host "Done (standalone). Ищите exe в подпапке *.dist:"
    Write-Host $standaloneDir
    Get-ChildItem -Path $standaloneDir -Recurse -Filter $outputExeName -ErrorAction SilentlyContinue | ForEach-Object { Write-Host " -> $($_.FullName)" }
} else {
    & $python -m nuitka `
        --onefile `
        --output-dir=$nuitkaDir `
        --output-filename=$outputExeName `
        @common
    Write-Host ('Done (onefile): ' + (Join-Path $nuitkaDir $outputExeName))
}
