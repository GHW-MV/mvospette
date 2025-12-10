Param(
    [switch]$SkipInstall
)

$repoRoot = Split-Path -Parent $PSScriptRoot
$builderPath = Resolve-Path (Join-Path $repoRoot "..\Email Template Builder")
$buildDir = Join-Path $builderPath "build"

if (-not $SkipInstall) {
    Write-Host "Installing dependencies in '$builderPath'..."
    npm --prefix "$builderPath" install
}

Write-Host "Building email builder..."
npm --prefix "$builderPath" run build

if (-not (Test-Path $buildDir)) {
    throw "Build folder not found at $buildDir"
}

# Sync build into repo root email-builder/
$destBuilder = Join-Path $repoRoot "email-builder"
if (Test-Path $destBuilder) { Remove-Item "$destBuilder" -Recurse -Force }
New-Item -ItemType Directory -Path $destBuilder | Out-Null
Copy-Item (Join-Path $buildDir "*") -Destination $destBuilder -Recurse

# Sync into static_site for hosting
$staticBuilder = Join-Path $repoRoot "static_site\email-builder"
$staticAssets = Join-Path $repoRoot "static_site\assets"

if (Test-Path $staticBuilder) { Remove-Item "$staticBuilder" -Recurse -Force }
if (Test-Path $staticAssets) { Remove-Item "$staticAssets" -Recurse -Force }
New-Item -ItemType Directory -Path $staticBuilder | Out-Null
New-Item -ItemType Directory -Path $staticAssets | Out-Null

Copy-Item (Join-Path $buildDir "index.html") -Destination $staticBuilder
Copy-Item (Join-Path $buildDir "assets\*") -Destination $staticAssets -Recurse

Write-Host "Sync complete:"
Write-Host " - email-builder/ updated"
Write-Host " - static_site/email-builder/index.html refreshed"
Write-Host " - static_site/assets/* refreshed"
