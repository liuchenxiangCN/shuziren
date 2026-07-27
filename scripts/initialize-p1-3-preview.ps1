[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repoRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$databasePath = Join-Path $repoRoot "data/control-plane-p1-3.db"
$backupRoot = Join-Path $repoRoot "data/control-plane-p1-3-backups"
$envPath = Join-Path $repoRoot ".env.p1-3-preview"
$apiRoot = Join-Path $repoRoot "apps/api"

Push-Location $apiRoot
try {
    uv run python -m app.control_plane.preview_p1_3 `
        --database $databasePath `
        --backup-root $backupRoot `
        --env-file $envPath
    if ($LASTEXITCODE -ne 0) {
        throw "P1.3 preview initialization failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
