# Upload Smart-Cam-App.exe and Smart-Cam-App.apk to GitHub Releases.
# Requires: $env:GITHUB_TOKEN with repo scope (classic PAT or fine-grained).
#
# Usage:
#   $env:GITHUB_TOKEN = "ghp_..."
#   .\scripts\publish-github-release.ps1 -Tag v1.0.0
param(
    [string]$Tag = "v1.0.0",
    [string]$Repo = "erratum101/Smart-cam"
)

$ErrorActionPreference = "Stop"

if (-not $env:GITHUB_TOKEN) {
    Write-Error "Set GITHUB_TOKEN (repo scope). Create at https://github.com/settings/tokens"
}

$landingRoot = Split-Path $PSScriptRoot -Parent
& (Join-Path $PSScriptRoot "copy-downloads.ps1")

$downloadsDir = Join-Path $landingRoot "public\downloads"
$assets = @(
    @{
        Path = Join-Path $downloadsDir "smart-cam-windows.exe"
        Name = "Smart-Cam-App.exe"
        ContentType = "application/octet-stream"
    },
    @{
        Path = Join-Path $downloadsDir "smart-cam-android.apk"
        Name = "Smart-Cam-App.apk"
        ContentType = "application/vnd.android.package-archive"
    }
)

foreach ($asset in $assets) {
    if (-not (Test-Path $asset.Path)) {
        Write-Error "Missing file: $($asset.Path)"
    }
}

$headers = @{
    Authorization = "Bearer $env:GITHUB_TOKEN"
    Accept = "application/vnd.github+json"
    "X-GitHub-Api-Version" = "2022-11-28"
}

Write-Host "Creating release $Tag on $Repo ..."
$releaseBody = @{
    tag_name = $Tag
    name = "Smart Cam $Tag"
    body = "Windows (.exe) and Android (.apk) builds."
    draft = $false
    prerelease = $false
} | ConvertTo-Json

try {
    $release = Invoke-RestMethod `
        -Uri "https://api.github.com/repos/$Repo/releases" `
        -Method Post `
        -Headers $headers `
        -Body $releaseBody `
        -ContentType "application/json; charset=utf-8"
} catch {
    if ($_.Exception.Response.StatusCode.value__ -eq 422) {
        Write-Host "Release $Tag already exists, fetching ..."
        $release = Invoke-RestMethod `
            -Uri "https://api.github.com/repos/$Repo/releases/tags/$Tag" `
            -Headers $headers
    } else {
        throw
    }
}

if (-not $release.id) {
    Write-Error "GitHub did not return a release id. Check token permissions (Contents: Read and write)."
}

$owner, $repoName = $Repo -split "/", 2
if (-not $owner -or -not $repoName) {
    Write-Error "Invalid repo format: $Repo (expected owner/name)"
}

foreach ($existing in @($release.assets)) {
    if ($existing.name -in @("Smart-Cam-App.exe", "Smart-Cam-App.apk")) {
        Write-Host "Removing old asset: $($existing.name)"
        Invoke-RestMethod `
            -Uri "https://api.github.com/repos/$Repo/releases/assets/$($existing.id)" `
            -Method Delete `
            -Headers $headers | Out-Null
    }
}

foreach ($asset in $assets) {
    $sizeMb = [math]::Round((Get-Item $asset.Path).Length / 1MB, 1)
    Write-Host "Uploading $($asset.Name) ($sizeMb MB) ..."
    $uploadUri = "https://uploads.github.com/repos/$owner/$repoName/releases/$($release.id)/assets?name=$([uri]::EscapeDataString($asset.Name))"

    Invoke-RestMethod `
        -Uri $uploadUri `
        -Method Post `
        -Headers @{
            Authorization = "Bearer $env:GITHUB_TOKEN"
            Accept = "application/vnd.github+json"
            "X-GitHub-Api-Version" = "2022-11-28"
        } `
        -ContentType $asset.ContentType `
        -InFile $asset.Path `
        -TimeoutSec 3600 | Out-Null
}

Write-Host ""
Write-Host "Done. Download URLs:"
Write-Host "  https://github.com/$Repo/releases/download/$Tag/Smart-Cam-App.exe"
Write-Host "  https://github.com/$Repo/releases/download/$Tag/Smart-Cam-App.apk"
Write-Host ""
Write-Host "Redeploy Vercel (or push) so landing uses these links in production."
