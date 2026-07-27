[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$databasePath = Join-Path $repoRoot "data/control-plane-p1-2.db"
$envPath = Join-Path $repoRoot ".env.p1-2-preview"
$apiRoot = Join-Path $repoRoot "apps/api"

Push-Location $apiRoot
try {
    uv run python -m app.control_plane.preview `
        --database $databasePath `
        --env-file $envPath
}
finally {
    Pop-Location
}
