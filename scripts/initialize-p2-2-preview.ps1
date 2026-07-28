[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repoRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$databasePath = Join-Path $repoRoot "data/control-plane-p2-2.db"
$backupRoot = Join-Path $repoRoot "data/control-plane-p2-2-backups"
$envPath = Join-Path $repoRoot ".env.p2-2-preview"
$apiRoot = Join-Path $repoRoot "apps/api"

Push-Location $apiRoot
try {
    uv run python -m app.control_plane.preview_p2_2 `
        --database $databasePath `
        --backup-root $backupRoot `
        --env-file $envPath
    if ($LASTEXITCODE -ne 0) {
        throw "P2.2 preview initialization failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
