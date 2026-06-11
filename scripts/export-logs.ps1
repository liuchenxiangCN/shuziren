param(
    [string]$OutputDir = "logs\exports",
    [string]$ApiBaseUrl = "",
    [int]$Limit = 80,
    [switch]$IncludeDockerLogs,
    [switch]$Zip
)

. "$PSScriptRoot\poc-common.ps1"

$root = Get-PocRepoRoot
$config = Get-PocConfig -Root $root
if (-not $ApiBaseUrl) {
    $ApiBaseUrl = $config.ApiBaseUrl
}
$ApiBaseUrl = $ApiBaseUrl.TrimEnd("/")

$baseOutputDir = if ([System.IO.Path]::IsPathRooted($OutputDir)) { $OutputDir } else { Join-Path $root $OutputDir }
$stamp = Get-PocTimestamp
$bundleDir = Join-Path $baseOutputDir "zt-poc-logs-$stamp"
New-Item -ItemType Directory -Force -Path $bundleDir | Out-Null

$exportUrl = "$ApiBaseUrl/api/ops/export?limit=$Limit"
try {
    Invoke-WebRequest -Uri $exportUrl -OutFile (Join-Path $bundleDir "ops-export.md") -TimeoutSec 15 -UseBasicParsing
} catch {
    "Ops markdown export failed: $($_.Exception.Message)" | Set-Content -LiteralPath (Join-Path $bundleDir "ops-export-error.txt") -Encoding UTF8
}

$jsonEndpoints = @(
    @{ Name = "ops-health"; Path = "/api/ops/health" },
    @{ Name = "ops-dependencies"; Path = "/api/ops/dependencies" },
    @{ Name = "ops-sessions"; Path = "/api/ops/sessions?limit=$Limit" },
    @{ Name = "ops-errors"; Path = "/api/ops/errors?limit=$Limit" },
    @{ Name = "ops-metrics"; Path = "/api/ops/metrics" },
    @{ Name = "demo-config"; Path = "/api/demo/config" }
)

foreach ($endpoint in $jsonEndpoints) {
    $target = Join-Path $bundleDir "$($endpoint.Name).json"
    $response = Invoke-PocHttpGet -Url "$ApiBaseUrl$($endpoint.Path)" -TimeoutSec 10
    if ($response.ok) {
        $response.content | Set-Content -LiteralPath $target -Encoding UTF8
    } else {
        @{
            ok = $false
            endpoint = $endpoint.Path
            error = $response.error
            status_code = $response.status_code
        } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $target -Encoding UTF8
    }
}

& docker compose --project-directory $root ps --format json > (Join-Path $bundleDir "docker-compose-ps.json") 2>$null
if ($LASTEXITCODE -ne 0) {
    & docker compose --project-directory $root ps > (Join-Path $bundleDir "docker-compose-ps.txt") 2>$null
}

if ($IncludeDockerLogs) {
    & docker compose --project-directory $root logs --no-color --tail 500 api web > (Join-Path $bundleDir "docker-compose-logs.txt") 2>$null
}

if ($Zip) {
    $zipPath = "$bundleDir.zip"
    if (Test-Path -LiteralPath $zipPath) {
        Remove-Item -LiteralPath $zipPath -Force
    }
    Compress-Archive -LiteralPath $bundleDir -DestinationPath $zipPath
    Write-Host "Log bundle: $zipPath"
} else {
    Write-Host "Log bundle: $bundleDir"
}
