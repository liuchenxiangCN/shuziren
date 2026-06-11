param(
    [switch]$Build,
    [switch]$DemoStable,
    [switch]$SkipCheck,
    [switch]$WithRagflow,
    [switch]$NoWait,
    [int]$TimeoutSeconds = 120
)

. "$PSScriptRoot\poc-common.ps1"

$root = Get-PocRepoRoot
$envPath = Join-Path $root ".env"
$envExample = Join-Path $root ".env.example"

if (-not (Test-Path -LiteralPath $envPath)) {
    if (-not (Test-Path -LiteralPath $envExample)) {
        throw ".env.example not found"
    }
    Copy-Item -LiteralPath $envExample -Destination $envPath
    Write-Host "Created .env from .env.example"
}

if ($DemoStable) {
    $env:DEMO_STABLE_MODE = "true"
    $env:VITE_DEMO_STABLE_MODE = "true"
    Write-Host "Demo stable mode enabled for this startup."
}

if (-not $SkipCheck) {
    & (Join-Path $PSScriptRoot "check-poc.ps1") -SkipExternal
    if ($LASTEXITCODE -ne 0) {
        throw "Preflight failed. Fix the errors above or rerun with -SkipCheck."
    }
}

if ($WithRagflow) {
    $ragflowComposeDir = "D:\Project\ragflow\docker"
    if (Test-Path -LiteralPath (Join-Path $ragflowComposeDir "docker-compose.yml")) {
        Push-Location $ragflowComposeDir
        try {
            & docker compose -f docker-compose.yml --profile cpu --profile elasticsearch up -d
            if ($LASTEXITCODE -ne 0) {
                throw "RAGFlow docker compose startup failed"
            }
        } finally {
            Pop-Location
        }
    } else {
        Write-Warning "RAGFlow compose directory not found: $ragflowComposeDir"
    }
}

$composeArgs = @("compose", "--project-directory", $root, "up", "-d")
if ($Build) {
    $composeArgs += "--build"
}
$composeArgs += @("api", "web")

& docker @composeArgs
if ($LASTEXITCODE -ne 0) {
    throw "docker compose up failed"
}

$config = Get-PocConfig -Root $root
if (-not $NoWait) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $apiReady = $false
    $webReady = $false
    while ((Get-Date) -lt $deadline) {
        if (-not $apiReady) {
            $api = Invoke-PocHttpGet -Url "$($config.ApiBaseUrl)/api/health" -TimeoutSec 3
            $apiReady = $api.ok
        }
        if (-not $webReady) {
            $web = Invoke-PocHttpGet -Url $config.WebUrl -TimeoutSec 3
            $webReady = $web.ok
        }
        if ($apiReady -and $webReady) {
            break
        }
        Start-Sleep -Seconds 2
    }
    if (-not ($apiReady -and $webReady)) {
        throw "POC did not become ready within $TimeoutSeconds seconds"
    }
}

Write-Host "POC started."
Write-Host "Web: $($config.WebUrl)"
Write-Host "API: $($config.ApiBaseUrl)/api/health"
Write-Host "Ops: $($config.WebUrl) -> switch to Ops view"
Write-Host "Run scripts\check-poc.ps1 -RequireServices for a full runtime check."
