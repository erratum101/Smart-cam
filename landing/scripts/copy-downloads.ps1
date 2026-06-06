# Copy built .exe and .apk into landing/public/downloads for direct download buttons.
$ErrorActionPreference = "Stop"

$landingRoot = Split-Path $PSScriptRoot -Parent
$repoRoot = Split-Path $landingRoot -Parent
$destDir = Join-Path $landingRoot "public\downloads"

New-Item -ItemType Directory -Force -Path $destDir | Out-Null

$windowsSources = @(
    (Join-Path $repoRoot "desktop\Smart Cam App\dist\Smart Cam App.exe"),
    (Join-Path $repoRoot "desktop\Smart Cam App\build-nuitka\Smart Cam App.exe")
)
$androidSource = Join-Path $repoRoot "mobile\build\app\outputs\flutter-apk\app-release.apk"

$windowsDest = Join-Path $destDir "smart-cam-windows.exe"
$androidDest = Join-Path $destDir "smart-cam-android.apk"

$windowsSource = $windowsSources | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $windowsSource) {
    Write-Error "Windows .exe not found. Run desktop\build_windows.ps1 first."
}
Copy-Item -Force $windowsSource $windowsDest
Write-Host "Windows: $windowsSource -> $windowsDest"

if (-not (Test-Path $androidSource)) {
    Write-Error "Android APK not found. Run 'flutter build apk --release' in mobile/ first."
}
Copy-Item -Force $androidSource $androidDest
Write-Host "Android: $androidSource -> $androidDest"

Write-Host "Done. Restart landing dev server if it is running."
