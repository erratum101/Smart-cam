# Build "Smart Cam App.exe" (PyInstaller). Icon: desktop/app_icon.png or desktop/icon.png.
# Output: desktop/Smart Cam App/dist/
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$appIcon = Join-Path $PSScriptRoot "app_icon.png"
$fallbackIcon = Join-Path $PSScriptRoot "icon.png"
if (-not (Test-Path $appIcon)) {
    if (Test-Path $fallbackIcon) {
        Copy-Item -Force $fallbackIcon $appIcon
    } else {
        Write-Error "Missing app_icon.png or icon.png in desktop/ (same folder as this script)."
    }
}

$appRoot = Join-Path $PSScriptRoot "Smart Cam App"
$distDir = Join-Path $appRoot "dist"
$workDir = Join-Path $appRoot "build"
New-Item -ItemType Directory -Force -Path $distDir, $workDir | Out-Null

python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller
python make_icon.py

pyinstaller --noconfirm --clean --onefile --windowed `
    --name "Smart Cam App" `
    --icon app_icon.ico `
    --paths . `
    --distpath $distDir `
    --workpath $workDir `
    --collect-all PySide6 `
    --hidden-import qrcode.image.pil `
    --hidden-import qrcode.image.pure `
    --add-data "app_icon.png;." `
    main.py

Write-Host ('Done: ' + (Join-Path $distDir 'Smart Cam App.exe'))
