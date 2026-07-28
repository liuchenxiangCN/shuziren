[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repoRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$previewEnvPath = Join-Path $repoRoot ".env.p2-2-preview"
$databasePath = Join-Path $repoRoot "data/control-plane-p2-2.db"
$backupRoot = Join-Path $repoRoot "data/control-plane-p2-2-backups"
$apiRoot = Join-Path $repoRoot "apps/api"

if (-not (Test-Path -LiteralPath $previewEnvPath -PathType Leaf)) {
    throw "P2.2 preview is not initialized. Run scripts\initialize-p2-2-preview.ps1 first."
}
if (-not (Test-Path -LiteralPath $databasePath -PathType Leaf)) {
    throw "P2.2 preview database is missing: $databasePath"
}

$allowedKeys = @(
    "CONTROL_PLANE_PREVIEW_MODE",
    "CONTROL_PLANE_ROOT_KEY_B64",
    "CONTROL_PLANE_DB_PATH",
    "CONTROL_PLANE_BACKUP_ROOT",
    "CONTROL_PLANE_ALLOWED_ORIGINS",
    "SESSION_LOG_RETENTION_DAYS"
)
$previewSettings = @{}
foreach ($line in Get-Content -LiteralPath $previewEnvPath -Encoding utf8) {
    $trimmed = $line.Trim()
    if (-not $trimmed -or $trimmed.StartsWith("#")) {
        continue
    }
    $parts = $trimmed.Split("=", 2)
    if ($parts.Count -ne 2 -or $parts[0] -notin $allowedKeys) {
        throw "Unexpected setting in .env.p2-2-preview."
    }
    $previewSettings[$parts[0]] = $parts[1]
}
if ($previewSettings["CONTROL_PLANE_PREVIEW_MODE"] -ne "true") {
    throw "P2.2 local API requires explicit development preview mode."
}
if ([string]::IsNullOrWhiteSpace($previewSettings["CONTROL_PLANE_ROOT_KEY_B64"])) {
    throw "P2.2 preview root key is missing."
}

$env:CONTROL_PLANE_PREVIEW_MODE = "true"
$env:CONTROL_PLANE_ROOT_KEY_B64 = $previewSettings["CONTROL_PLANE_ROOT_KEY_B64"]
$env:CONTROL_PLANE_DB_PATH = [System.IO.Path]::GetFullPath($databasePath)
$env:CONTROL_PLANE_BACKUP_ROOT = [System.IO.Path]::GetFullPath($backupRoot)
$env:SESSION_LOG_RETENTION_DAYS = "3"
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
    Write-Host "Starting P2.2 local API at http://127.0.0.1:18080"
    Write-Host "Root key, database credentials and passwords will not be printed."
    & uv run uvicorn app.main:app --host 127.0.0.1 --port 18080 --no-access-log
    if ($LASTEXITCODE -ne 0) {
        throw "P2.2 local API exited with code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
