[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$BrowserPassword
)

$ErrorActionPreference = "Stop"
$repoRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$evidenceRoot = Join-Path $repoRoot "logs/productization/P2.3-$stamp"
foreach ($name in @(
    "screenshots", "browser", "test-results", "contract",
    "migration", "rollback", "security", "review", "verification", "capacity"
)) {
    New-Item -ItemType Directory -Path (Join-Path $evidenceRoot $name) -Force | Out-Null
}

$databasePath = Join-Path $evidenceRoot "browser/control-plane.db"
$backupRoot = Join-Path $evidenceRoot "browser/backups"
$sessionLogPath = Join-Path $evidenceRoot "browser/sessions.db"
$rootBytes = New-Object byte[] 32
[System.Security.Cryptography.RandomNumberGenerator]::Fill($rootBytes)

# The generator consumes the root key and password only through the process
# environment; its generated env file is discarded so no key enters evidence.
$fixtureEnvPath = Join-Path ([System.IO.Path]::GetTempPath()) (
    "shuziren-p23-gate-" + [guid]::NewGuid().ToString("N") + ".env"
)
$env:CONTROL_PLANE_ROOT_KEY_B64 = [Convert]::ToBase64String($rootBytes)
$env:P2_3_PREVIEW_PASSWORD = $BrowserPassword
Push-Location (Join-Path $repoRoot "apps/api")
try {
    uv run python -m app.control_plane.preview_p2_3 `
        --database $databasePath `
        --backup-root $backupRoot `
        --env-file $fixtureEnvPath
    if ($LASTEXITCODE -ne 0) {
        throw "P2.3 browser fixture initialization failed."
    }
}
finally {
    Pop-Location
    Remove-Item Env:P2_3_PREVIEW_PASSWORD
    if (Test-Path -LiteralPath $fixtureEnvPath) {
        Remove-Item -LiteralPath $fixtureEnvPath -Force
    }
}

$env:CONTROL_PLANE_PREVIEW_MODE = "true"
$env:CONTROL_PLANE_DB_PATH = $databasePath
$env:CONTROL_PLANE_BACKUP_ROOT = $backupRoot
$env:SQLITE_PATH = $sessionLogPath
$env:SESSION_LOG_RETENTION_DAYS = "3"
$env:CONTROL_PLANE_ALLOWED_ORIGINS = '["http://localhost:18300"]'
$uvPath = (Get-Command uv).Source
$apiProcess = Start-Process `
    -FilePath $uvPath `
    -ArgumentList @(
        "run", "uvicorn", "app.main:app", "--host", "127.0.0.1",
        "--port", "18380", "--no-access-log"
    ) `
    -WorkingDirectory (Join-Path $repoRoot "apps/api") `
    -RedirectStandardOutput (Join-Path $evidenceRoot "browser/api.stdout.log") `
    -RedirectStandardError (Join-Path $evidenceRoot "browser/api.stderr.log") `
    -WindowStyle Hidden `
    -PassThru

$env:VITE_API_BASE_URL = "http://localhost:18380"
$pnpmPath = (Get-Command pnpm).Source
$webProcess = Start-Process `
    -FilePath $pnpmPath `
    -ArgumentList @("exec", "vite", "--host", "127.0.0.1", "--port", "18300") `
    -WorkingDirectory (Join-Path $repoRoot "apps/web") `
    -RedirectStandardOutput (Join-Path $evidenceRoot "browser/web.stdout.log") `
    -RedirectStandardError (Join-Path $evidenceRoot "browser/web.stderr.log") `
    -WindowStyle Hidden `
    -PassThru

$ready = $false
for ($attempt = 0; $attempt -lt 40; $attempt++) {
    try {
        $api = Invoke-WebRequest -UseBasicParsing http://127.0.0.1:18380/api/health -TimeoutSec 2
        $web = Invoke-WebRequest -UseBasicParsing http://127.0.0.1:18300/manage -TimeoutSec 2
        if ($api.StatusCode -eq 200 -and $web.StatusCode -eq 200) {
            $ready = $true
            break
        }
    }
    catch {
        # Polling is bounded; captured stderr files retain startup failures.
    }
    Start-Sleep -Milliseconds 250
}
if (-not $ready) {
    throw "P2.3 browser gate services did not become ready."
}

Write-Output "EVIDENCE_ROOT=$evidenceRoot"
Write-Output "API_PID=$($apiProcess.Id)"
Write-Output "WEB_PID=$($webProcess.Id)"
Write-Output "BROWSER_GATE_READY=http://localhost:18300/manage"
