[CmdletBinding()]
param(
    [string]$SourceDatabase = "data/control-plane.db",
    [string]$TargetDatabase = "data/control-plane-p1-2.db",
    [string]$SourceEnvironment = ".env.p1-1-preview",
    [string]$TargetEnvironment = ".env.p1-2-preview"
)

$ErrorActionPreference = "Stop"
$repoRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$sourceDatabasePath = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $SourceDatabase))
$targetDatabasePath = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $TargetDatabase))
$sourceEnvPath = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $SourceEnvironment))
$targetEnvPath = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $TargetEnvironment))
$apiRoot = Join-Path $repoRoot "apps/api"

foreach ($target in @($sourceDatabasePath, $targetDatabasePath)) {
    if (-not $target.StartsWith((Join-Path $repoRoot "data"), [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Resolved preview database path escaped the repository data directory."
    }
}
foreach ($target in @($sourceEnvPath, $targetEnvPath)) {
    if (-not $target.StartsWith($repoRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Resolved preview environment path escaped the repository."
    }
}
if (-not (Test-Path -LiteralPath $sourceDatabasePath -PathType Leaf)) {
    throw "Accepted P1.1 preview database is missing: $sourceDatabasePath"
}
if (-not (Test-Path -LiteralPath $sourceEnvPath -PathType Leaf)) {
    throw "Accepted P1.1 preview environment file is missing: $sourceEnvPath"
}
if (
    (Test-Path -LiteralPath $targetDatabasePath) -or
    (Test-Path -LiteralPath $targetEnvPath)
) {
    throw "Refusing to overwrite an existing P1.2 preview database or environment file."
}

$allowedKeys = @(
    "CONTROL_PLANE_PREVIEW_MODE",
    "CONTROL_PLANE_ROOT_KEY_B64",
    "CONTROL_PLANE_DB_PATH",
    "CONTROL_PLANE_ALLOWED_ORIGINS"
)
$previewSettings = @{}
$sourceEnvLines = Get-Content -LiteralPath $sourceEnvPath -Encoding utf8
foreach ($line in $sourceEnvLines) {
    $trimmed = $line.Trim()
    if (-not $trimmed -or $trimmed.StartsWith("#")) {
        continue
    }
    $parts = $trimmed.Split("=", 2)
    if ($parts.Count -ne 2 -or $parts[0] -notin $allowedKeys) {
        throw "Unexpected setting in .env.p1-1-preview."
    }
    $previewSettings[$parts[0]] = $parts[1]
}
if ($previewSettings["CONTROL_PLANE_PREVIEW_MODE"] -ne "true") {
    throw "The source database is not bound to explicit development preview mode."
}
if ([string]::IsNullOrWhiteSpace($previewSettings["CONTROL_PLANE_ROOT_KEY_B64"])) {
    throw "The source preview root key is missing."
}

$env:CONTROL_PLANE_ROOT_KEY_B64 = $previewSettings["CONTROL_PLANE_ROOT_KEY_B64"]
Push-Location $apiRoot
try {
    uv run python -m app.control_plane.upgrade_preview `
        --source $sourceDatabasePath `
        --database $targetDatabasePath
}
finally {
    Pop-Location
}

$allowedOriginsLine = if (
    $previewSettings.ContainsKey("CONTROL_PLANE_ALLOWED_ORIGINS")
) {
    "CONTROL_PLANE_ALLOWED_ORIGINS=$($previewSettings["CONTROL_PLANE_ALLOWED_ORIGINS"])"
}
else {
    'CONTROL_PLANE_ALLOWED_ORIGINS=["http://localhost:18000","http://127.0.0.1:18000"]'
}
$targetEnvLines = @(
    "# Generated P1.2 development preview settings. Never commit this file.",
    "CONTROL_PLANE_PREVIEW_MODE=true",
    "CONTROL_PLANE_ROOT_KEY_B64=$($previewSettings["CONTROL_PLANE_ROOT_KEY_B64"])",
    "CONTROL_PLANE_DB_PATH=/app/data/$([System.IO.Path]::GetFileName($targetDatabasePath))",
    $allowedOriginsLine,
    ""
)
[System.IO.File]::WriteAllLines($targetEnvPath, $targetEnvLines)
Write-Host "P1.1 source database was left unchanged."
Write-Host "P1.2 copied database: $targetDatabasePath"
Write-Host "P1.2 preview environment: $targetEnvPath"
