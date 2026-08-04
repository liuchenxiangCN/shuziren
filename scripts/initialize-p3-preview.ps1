[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repoRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$databasePath = Join-Path $repoRoot "data/control-plane-p3.db"
$backupRoot = Join-Path $repoRoot "data/control-plane-p3-backups"
$envPath = Join-Path $repoRoot ".env.p3-preview"
$apiRoot = Join-Path $repoRoot "apps/api"

Push-Location $apiRoot
try {
    $pythonPath = Join-Path $apiRoot ".venv/Scripts/python.exe"
    if (Test-Path -LiteralPath $pythonPath -PathType Leaf) {
        & $pythonPath -m app.control_plane.preview_p2_3 `
            --database $databasePath `
            --backup-root $backupRoot `
            --env-file $envPath `
            --seed-p3
    }
    else {
        uv run python -m app.control_plane.preview_p2_3 `
            --database $databasePath `
            --backup-root $backupRoot `
            --env-file $envPath `
            --seed-p3
    }
    if ($LASTEXITCODE -ne 0) {
        throw "P3 preview initialization failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
