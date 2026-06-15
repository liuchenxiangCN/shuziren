param(
    [switch]$RequireServices,
    [switch]$SkipExternal,
    [switch]$RunSmoke,
    [switch]$Json,
    [string]$OutputDir = ""
)

. "$PSScriptRoot\poc-common.ps1"

$root = Get-PocRepoRoot
$config = Get-PocConfig -Root $root
$results = @()

$results += New-PocCheckResult -Category "files" -Name ".env" -Status ($(if (Test-Path -LiteralPath $config.EnvPath) { "ok" } else { "warning" })) -Message ($(if (Test-Path -LiteralPath $config.EnvPath) { ".env found" } else { ".env not found; start-poc.ps1 can copy .env.example" }))
$results += New-PocCheckResult -Category "files" -Name "config" -Status ($(if (Test-Path -LiteralPath (Join-Path $root "config")) { "ok" } else { "error" })) -Message "config directory"
$results += New-PocCheckResult -Category "files" -Name "customer profiles" -Status ($(if (Test-Path -LiteralPath (Join-Path $root "config\customers")) { "ok" } else { "warning" })) -Message "config/customers"
$results += New-PocCheckResult -Category "files" -Name "ask metrics data" -Status ($(if (Test-Path -LiteralPath (Join-Path $root "docs\demo_data\ask_metrics")) { "ok" } else { "error" })) -Message "docs/demo_data/ask_metrics"

if (Test-PocCommand -Name "docker") {
    $results += New-PocCheckResult -Category "docker" -Name "docker cli" -Status "ok" -Message "docker command found"
    $dockerInfo = & docker info 2>$null
    if ($LASTEXITCODE -eq 0) {
        $results += New-PocCheckResult -Category "docker" -Name "docker daemon" -Status "ok" -Message "Docker daemon is reachable"
    } else {
        $results += New-PocCheckResult -Category "docker" -Name "docker daemon" -Status "error" -Message "Docker daemon is not reachable"
    }
    $composeVersion = & docker compose version 2>$null
    $results += New-PocCheckResult -Category "docker" -Name "docker compose" -Status ($(if ($LASTEXITCODE -eq 0) { "ok" } else { "error" })) -Message ($(if ($LASTEXITCODE -eq 0) { ($composeVersion -join " ") } else { "docker compose is unavailable" }))
    $composeConfig = & docker compose --project-directory $root config --services 2>$null
    $hasApi = $composeConfig -contains "api"
    $hasWeb = $composeConfig -contains "web"
    $results += New-PocCheckResult -Category "docker" -Name "compose services" -Status ($(if ($hasApi -and $hasWeb) { "ok" } else { "error" })) -Message "services: $($composeConfig -join ', ')"
} else {
    $results += New-PocCheckResult -Category "docker" -Name "docker cli" -Status "error" -Message "docker command not found"
}

foreach ($portCheck in @(
    @{ Name = "api port"; Port = $config.ApiPort },
    @{ Name = "web port"; Port = $config.WebPort }
)) {
    $listening = Test-PocPortListening -Port $portCheck.Port
    if ($listening) {
        $results += New-PocCheckResult -Category "ports" -Name $portCheck.Name -Status "ok" -Message "port $($portCheck.Port) is listening"
    } elseif ($RequireServices) {
        $results += New-PocCheckResult -Category "ports" -Name $portCheck.Name -Status "error" -Message "port $($portCheck.Port) is not listening"
    } else {
        $results += New-PocCheckResult -Category "ports" -Name $portCheck.Name -Status "warning" -Message "port $($portCheck.Port) is free; this is expected before startup"
    }
}

function Add-KeyCheck {
    param(
        [string]$Name,
        [bool]$Mock,
        [string[]]$Values
    )
    if ($Mock) {
        return New-PocCheckResult -Category "config" -Name $Name -Status "ok" -Message "mock mode enabled"
    }
    foreach ($value in $Values) {
        if (Test-PocPlaceholder -Value $value) {
            return New-PocCheckResult -Category "config" -Name $Name -Status "error" -Message "real mode requires non-placeholder key and URL values"
        }
    }
    if ($Values.Count -eq 0) {
        return New-PocCheckResult -Category "config" -Name $Name -Status "error" -Message "real mode requires a non-placeholder key or URL"
    }
    return New-PocCheckResult -Category "config" -Name $Name -Status "ok" -Message "real mode config is present"
}

$results += Add-KeyCheck -Name "dora" -Mock $config.DoraMock -Values @($config.DoraBaseUrl, $config.DoraApiKey)
$results += Add-KeyCheck -Name "asr" -Mock $config.AsrMock -Values @($config.AsrApiKey)
$results += Add-KeyCheck -Name "tts" -Mock $config.TtsMock -Values @($config.TtsApiKey)
if ($config.FvsMock) {
    $results += New-PocCheckResult -Category "config" -Name "fvs" -Status "ok" -Message "mock mode enabled"
} elseif ([string]::IsNullOrWhiteSpace($config.FvsUrl)) {
    $results += New-PocCheckResult -Category "config" -Name "fvs" -Status "warning" -Message "FVS iframe URL is empty"
} else {
    $results += New-PocCheckResult -Category "config" -Name "fvs" -Status "ok" -Message "FVS URL configured"
}

$apiHealth = Invoke-PocHttpGet -Url "$($config.ApiBaseUrl)/api/health" -TimeoutSec 3
if ($apiHealth.ok) {
    $results += New-PocCheckResult -Category "runtime" -Name "api health" -Status "ok" -Message "GET /api/health HTTP $($apiHealth.status_code)"
} elseif ($RequireServices) {
    $results += New-PocCheckResult -Category "runtime" -Name "api health" -Status "error" -Message (Select-PocText -Value $apiHealth.error -Fallback "GET /api/health failed")
} else {
    $results += New-PocCheckResult -Category "runtime" -Name "api health" -Status "warning" -Message "API is not reachable before startup"
}

$webHealth = Invoke-PocHttpGet -Url $config.WebUrl -TimeoutSec 3
if ($webHealth.ok) {
    $results += New-PocCheckResult -Category "runtime" -Name "web" -Status "ok" -Message "GET $($config.WebUrl) HTTP $($webHealth.status_code)"
} elseif ($RequireServices) {
    $results += New-PocCheckResult -Category "runtime" -Name "web" -Status "error" -Message (Select-PocText -Value $webHealth.error -Fallback "web failed")
} else {
    $results += New-PocCheckResult -Category "runtime" -Name "web" -Status "warning" -Message "Web is not reachable before startup"
}

if ($apiHealth.ok -and -not $SkipExternal) {
    $ops = Invoke-PocHttpGet -Url "$($config.ApiBaseUrl)/api/ops/dependencies" -TimeoutSec 8
    if ($ops.ok) {
        try {
            $opsJson = $ops.content | ConvertFrom-Json
            $results += New-PocCheckResult -Category "ops" -Name "dependencies" -Status $opsJson.status -Message "Ops aggregate status: $($opsJson.status)"
            foreach ($dependency in $opsJson.dependencies) {
                $results += New-PocCheckResult -Category "ops" -Name $dependency.name -Status $dependency.status -Message $dependency.message
            }
        } catch {
            $results += New-PocCheckResult -Category "ops" -Name "dependencies" -Status "warning" -Message "Ops dependency response could not be parsed"
        }
    } else {
        $results += New-PocCheckResult -Category "ops" -Name "dependencies" -Status "warning" -Message (Select-PocText -Value $ops.error -Fallback "Ops dependencies failed")
    }
} elseif ($SkipExternal) {
    $results += New-PocCheckResult -Category "ops" -Name "dependencies" -Status "skipped" -Message "external dependency probes skipped"
}

if (-not $SkipExternal) {
    if ($config.RagflowBaseUrl) {
        $ragflow = Invoke-PocHttpGet -Url "$($config.RagflowBaseUrl.TrimEnd('/'))/api/v1/system/healthz" -TimeoutSec 4
        $results += New-PocCheckResult -Category "external" -Name "ragflow healthz" -Status ($(if ($ragflow.ok) { "ok" } else { "warning" })) -Message ($(if ($ragflow.ok) { "HTTP $($ragflow.status_code)" } else { Select-PocText -Value $ragflow.error -Fallback "RAGFlow health check failed" }))
    } elseif ($config.RagflowMcpUrl) {
        $ragflowMcp = Invoke-PocHttpGet -Url $config.RagflowMcpUrl -Headers @{ Accept = "application/json, text/event-stream" } -OkStatuses @(200, 202, 406) -TimeoutSec 4
        $results += New-PocCheckResult -Category "external" -Name "ragflow mcp" -Status ($(if ($ragflowMcp.ok) { "ok" } else { "warning" })) -Message ($(if ($ragflowMcp.ok) { "HTTP $($ragflowMcp.status_code)" } else { Select-PocText -Value $ragflowMcp.error -Fallback "RAGFlow MCP check failed" }))
    } else {
        $results += New-PocCheckResult -Category "external" -Name "ragflow" -Status "warning" -Message "RAGFlow URL is not configured"
    }
}

if ($RunSmoke) {
    & (Join-Path $PSScriptRoot "smoke-demo.ps1") -ApiBaseUrl $config.ApiBaseUrl | Out-Host
    $results += New-PocCheckResult -Category "smoke" -Name "demo smoke" -Status ($(if ($LASTEXITCODE -eq 0) { "ok" } else { "error" })) -Message "smoke-demo.ps1 exit code $LASTEXITCODE"
}

if ($OutputDir) {
    $fullOutputDir = if ([System.IO.Path]::IsPathRooted($OutputDir)) { $OutputDir } else { Join-Path $root $OutputDir }
    New-Item -ItemType Directory -Force -Path $fullOutputDir | Out-Null
    $stamp = Get-PocTimestamp
    $results | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $fullOutputDir "check-poc-$stamp.json") -Encoding UTF8
    New-PocMarkdownReport -Results $results -Title "POC preflight report" | Set-Content -LiteralPath (Join-Path $fullOutputDir "check-poc-$stamp.md") -Encoding UTF8
}

if ($Json) {
    $results | ConvertTo-Json -Depth 8
} else {
    $results | Format-Table category, name, status, message -AutoSize
    $errors = @($results | Where-Object { $_.status -eq "error" }).Count
    $warnings = @($results | Where-Object { $_.status -eq "warning" }).Count
    Write-Host "Summary: $errors error(s), $warnings warning(s)"
}

if (@($results | Where-Object { $_.status -eq "error" }).Count -gt 0) {
    exit 1
}
exit 0
