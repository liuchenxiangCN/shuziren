param(
    [switch]$WithRagflow,
    [switch]$RemoveOrphans
)

. "$PSScriptRoot\poc-common.ps1"

$root = Get-PocRepoRoot
$composeArgs = @("compose", "--project-directory", $root, "down")
if ($RemoveOrphans) {
    $composeArgs += "--remove-orphans"
}

& docker @composeArgs
if ($LASTEXITCODE -ne 0) {
    throw "docker compose down failed"
}

if ($WithRagflow) {
    $ragflowComposeDir = "D:\Project\ragflow\docker"
    if (Test-Path -LiteralPath (Join-Path $ragflowComposeDir "docker-compose.yml")) {
        Push-Location $ragflowComposeDir
        try {
            & docker compose -f docker-compose.yml --profile cpu --profile elasticsearch down
            if ($LASTEXITCODE -ne 0) {
                throw "RAGFlow docker compose stop failed"
            }
        } finally {
            Pop-Location
        }
    } else {
        Write-Warning "RAGFlow compose directory not found: $ragflowComposeDir"
    }
}

Write-Host "POC stopped."
