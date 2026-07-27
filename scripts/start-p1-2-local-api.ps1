[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$previewEnvPath = Join-Path $repoRoot ".env.p1-2-preview"
$databasePath = Join-Path $repoRoot "data/control-plane-p1-2.db"
$apiRoot = Join-Path $repoRoot "apps/api"

if (-not (Test-Path -LiteralPath $previewEnvPath -PathType Leaf)) {
    throw "P1.2 preview is not initialized. Run scripts\initialize-p1-2-preview.ps1 first."
}
if (-not (Test-Path -LiteralPath $databasePath -PathType Leaf)) {
    throw "P1.2 preview database is missing: $databasePath"
}

$allowedKeys = @(
    "CONTROL_PLANE_PREVIEW_MODE",
    "CONTROL_PLANE_ROOT_KEY_B64",
    "CONTROL_PLANE_DB_PATH",
    "CONTROL_PLANE_ALLOWED_ORIGINS"
)
$previewSettings = @{}
foreach ($line in Get-Content -LiteralPath $previewEnvPath -Encoding utf8) {
    $trimmed = $line.Trim()
    if (-not $trimmed -or $trimmed.StartsWith("#")) {
        continue
    }
    $parts = $trimmed.Split("=", 2)
    if ($parts.Count -ne 2 -or $parts[0] -notin $allowedKeys) {
        throw "Unexpected setting in .env.p1-2-preview."
    }
    $previewSettings[$parts[0]] = $parts[1]
}
if ($previewSettings["CONTROL_PLANE_PREVIEW_MODE"] -ne "true") {
    throw "P1.2 local API requires explicit development preview mode."
}
if ([string]::IsNullOrWhiteSpace($previewSettings["CONTROL_PLANE_ROOT_KEY_B64"])) {
    throw "P1.2 preview root key is missing."
}

$env:CONTROL_PLANE_PREVIEW_MODE = "true"
$env:CONTROL_PLANE_ROOT_KEY_B64 = $previewSettings["CONTROL_PLANE_ROOT_KEY_B64"]
$env:CONTROL_PLANE_DB_PATH = [System.IO.Path]::GetFullPath($databasePath)
$env:CONTROL_PLANE_ALLOWED_ORIGINS = if (
    $previewSettings.ContainsKey("CONTROL_PLANE_ALLOWED_ORIGINS")
) {
    $previewSettings["CONTROL_PLANE_ALLOWED_ORIGINS"]
}
else {
    '["http://localhost:18000","http://127.0.0.1:18000"]'
}

Push-Location $apiRoot
try {
    Write-Host "Starting P1.2 local API at http://127.0.0.1:18080"
    Write-Host "Root key and passwords will not be printed."
    & uv run uvicorn app.main:app --host 127.0.0.1 --port 18080
    if ($LASTEXITCODE -ne 0) {
        throw "P1.2 local API exited with code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
