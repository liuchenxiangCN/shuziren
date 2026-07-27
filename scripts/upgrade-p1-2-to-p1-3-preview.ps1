[CmdletBinding()]
param(
    [string]$SourceDatabase = "data/control-plane-p1-2-final.db",
    [string]$TargetDatabase = "data/control-plane-p1-3.db",
    [string]$SourceEnvironment = ".env.p1-2-final",
    [string]$TargetEnvironment = ".env.p1-3-preview",
    [string]$BackupRoot = "data/control-plane-p1-3-backups"
)

$ErrorActionPreference = "Stop"
$repoRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$dataRoot = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "data"))
$sourceDatabasePath = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $SourceDatabase))
$targetDatabasePath = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $TargetDatabase))
$sourceEnvPath = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $SourceEnvironment))
$targetEnvPath = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $TargetEnvironment))
$backupRootPath = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $BackupRoot))
$apiRoot = Join-Path $repoRoot "apps/api"

foreach ($target in @($sourceDatabasePath, $targetDatabasePath, $backupRootPath)) {
    if (-not $target.StartsWith($dataRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Resolved P1.3 data path escaped the repository data directory."
    }
}
foreach ($target in @($sourceEnvPath, $targetEnvPath)) {
    if (-not $target.StartsWith($repoRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Resolved preview environment path escaped the repository."
    }
}
if (-not (Test-Path -LiteralPath $sourceDatabasePath -PathType Leaf)) {
    throw "Accepted P1.2 preview database is missing: $sourceDatabasePath"
}
if (-not (Test-Path -LiteralPath $sourceEnvPath -PathType Leaf)) {
    throw "Accepted P1.2 preview environment file is missing: $sourceEnvPath"
}
if (
    (Test-Path -LiteralPath $targetDatabasePath) -or
    (Test-Path -LiteralPath $targetEnvPath) -or
    (Test-Path -LiteralPath $backupRootPath)
) {
    throw "Refusing to overwrite an existing P1.3 database, environment file or backup root."
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
foreach ($line in Get-Content -LiteralPath $sourceEnvPath -Encoding utf8) {
    $trimmed = $line.Trim()
    if (-not $trimmed -or $trimmed.StartsWith("#")) {
        continue
    }
    $parts = $trimmed.Split("=", 2)
    if ($parts.Count -ne 2 -or $parts[0] -notin $allowedKeys) {
        throw "Unexpected setting in the P1.2 preview environment."
    }
    $previewSettings[$parts[0]] = $parts[1]
}
if ($previewSettings["CONTROL_PLANE_PREVIEW_MODE"] -ne "true") {
    throw "The source database is not bound to explicit development preview mode."
}
if ([string]::IsNullOrWhiteSpace($previewSettings["CONTROL_PLANE_ROOT_KEY_B64"])) {
    throw "The source preview root key is missing."
}

$previousRootKey = [System.Environment]::GetEnvironmentVariable(
    "CONTROL_PLANE_ROOT_KEY_B64",
    [System.EnvironmentVariableTarget]::Process
)
try {
    $env:CONTROL_PLANE_ROOT_KEY_B64 = $previewSettings["CONTROL_PLANE_ROOT_KEY_B64"]
    Push-Location $apiRoot
    try {
        uv run python -m app.control_plane.upgrade_p1_3 `
            --source $sourceDatabasePath `
            --database $targetDatabasePath `
            --backup-root $backupRootPath
        if ($LASTEXITCODE -ne 0) {
            throw "P1.3 copied database migration failed with exit code $LASTEXITCODE."
        }
    }
    finally {
        Pop-Location
    }
}
finally {
    [System.Environment]::SetEnvironmentVariable(
        "CONTROL_PLANE_ROOT_KEY_B64",
        $previousRootKey,
        [System.EnvironmentVariableTarget]::Process
    )
}

$allowedOriginsLine = if ($previewSettings.ContainsKey("CONTROL_PLANE_ALLOWED_ORIGINS")) {
    "CONTROL_PLANE_ALLOWED_ORIGINS=$($previewSettings["CONTROL_PLANE_ALLOWED_ORIGINS"])"
}
else {
    'CONTROL_PLANE_ALLOWED_ORIGINS=["http://localhost:18000","http://127.0.0.1:18000"]'
}
$targetEnvLines = @(
    "# Generated P1.3 development preview settings. Never commit this file.",
    "CONTROL_PLANE_PREVIEW_MODE=true",
    "CONTROL_PLANE_ROOT_KEY_B64=$($previewSettings["CONTROL_PLANE_ROOT_KEY_B64"])",
    "CONTROL_PLANE_DB_PATH=/app/data/$([System.IO.Path]::GetFileName($targetDatabasePath))",
    "CONTROL_PLANE_BACKUP_ROOT=/app/data/$([System.IO.Path]::GetFileName($backupRootPath))",
    "SESSION_LOG_RETENTION_DAYS=3",
    $allowedOriginsLine,
    ""
)
[System.IO.File]::WriteAllLines($targetEnvPath, $targetEnvLines)
Write-Host "P1.2 source database was left unchanged."
Write-Host "P1.3 copied database: $targetDatabasePath"
Write-Host "P1.3 backup root: $backupRootPath"
Write-Host "P1.3 preview environment: $targetEnvPath"
