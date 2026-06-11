Set-StrictMode -Version Latest

function Get-PocRepoRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Read-PocEnv {
    param([string]$Path)

    $values = @{}
    if (-not (Test-Path -LiteralPath $Path)) {
        return $values
    }

    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) {
            continue
        }
        $parts = $trimmed.Split("=", 2)
        $key = $parts[0].Trim()
        $value = $parts[1].Trim().Trim("'").Trim('"')
        if ($key) {
            $values[$key] = $value
        }
    }
    return $values
}

function Get-PocEnvValue {
    param(
        [hashtable]$Values,
    [string]$Key,
    [string]$Default = ""
)

    $processValue = [Environment]::GetEnvironmentVariable($Key, "Process")
    if ($processValue) {
        return $processValue
    }
    if ($Values.ContainsKey($Key) -and $Values[$Key]) {
        return [string]$Values[$Key]
    }
    return $Default
}

function ConvertTo-PocBool {
    param(
        [string]$Value,
        [bool]$Default = $false
    )

    if (-not $Value) {
        return $Default
    }
    switch ($Value.Trim().ToLowerInvariant()) {
        "1" { return $true }
        "true" { return $true }
        "yes" { return $true }
        "on" { return $true }
        "0" { return $false }
        "false" { return $false }
        "no" { return $false }
        "off" { return $false }
        default { return $Default }
    }
}

function Get-PocConfig {
    param([string]$Root)

    $envPath = Join-Path $Root ".env"
    $envValues = Read-PocEnv -Path $envPath
    $apiPort = Get-PocEnvValue -Values $envValues -Key "API_PORT" -Default "18080"
    $webPort = Get-PocEnvValue -Values $envValues -Key "WEB_PORT" -Default "18000"
    $apiBaseUrl = Get-PocEnvValue -Values $envValues -Key "VITE_API_BASE_URL" -Default "http://localhost:$apiPort"

    return [pscustomobject]@{
        Root = $Root
        EnvPath = $envPath
        Env = $envValues
        ApiPort = [int]$apiPort
        WebPort = [int]$webPort
        ApiBaseUrl = $apiBaseUrl.TrimEnd("/")
        WebUrl = "http://localhost:$webPort"
        CustomerId = Get-PocEnvValue -Values $envValues -Key "CUSTOMER_ID" -Default "zt-securities"
        DemoStableMode = ConvertTo-PocBool -Value (Get-PocEnvValue -Values $envValues -Key "DEMO_STABLE_MODE" -Default "false")
        DoraMock = ConvertTo-PocBool -Value (Get-PocEnvValue -Values $envValues -Key "ENABLE_MOCK_DORA" -Default "true")
        AsrMock = ConvertTo-PocBool -Value (Get-PocEnvValue -Values $envValues -Key "ENABLE_MOCK_ASR" -Default "true")
        TtsMock = ConvertTo-PocBool -Value (Get-PocEnvValue -Values $envValues -Key "ENABLE_MOCK_TTS" -Default "true")
        FvsMock = ConvertTo-PocBool -Value (Get-PocEnvValue -Values $envValues -Key "ENABLE_MOCK_FVS" -Default "true")
        DoraBaseUrl = Get-PocEnvValue -Values $envValues -Key "DORA_BASE_URL"
        DoraApiKey = Get-PocEnvValue -Values $envValues -Key "DORA_API_KEY"
        RagflowBaseUrl = Get-PocEnvValue -Values $envValues -Key "RAGFLOW_BASE_URL"
        RagflowMcpUrl = Get-PocEnvValue -Values $envValues -Key "RAGFLOW_MCP_URL"
        FvsUrl = Get-PocEnvValue -Values $envValues -Key "VITE_FVS_URL"
        AsrApiKey = Get-PocEnvValue -Values $envValues -Key "ASR_API_KEY"
        TtsApiKey = Get-PocEnvValue -Values $envValues -Key "TTS_API_KEY"
    }
}

function New-PocCheckResult {
    param(
        [string]$Name,
        [ValidateSet("ok", "warning", "error", "skipped")]
        [string]$Status,
        [string]$Message,
        [string]$Category = "general"
    )

    return [pscustomobject]@{
        category = $Category
        name = $Name
        status = $Status
        message = $Message
    }
}

function Test-PocCommand {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Test-PocPortListening {
    param([int]$Port)

    try {
        $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        return [bool]$connections
    } catch {
        return $false
    }
}

function Invoke-PocHttpGet {
    param(
        [string]$Url,
        [int[]]$OkStatuses = @(200),
        [int]$TimeoutSec = 4,
        [hashtable]$Headers = @{}
    )

    try {
        $response = Invoke-WebRequest -Uri $Url -Method Get -Headers $Headers -TimeoutSec $TimeoutSec -UseBasicParsing
        $ok = $OkStatuses -contains [int]$response.StatusCode
        return [pscustomobject]@{
            ok = $ok
            status_code = [int]$response.StatusCode
            content = ConvertFrom-PocWebResponseContent -Response $response
            error = $null
        }
    } catch {
        $statusCode = $null
        if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
            $statusCode = [int]$_.Exception.Response.StatusCode
        }
        return [pscustomobject]@{
            ok = $false
            status_code = $statusCode
            content = ""
            error = $_.Exception.Message
        }
    }
}

function ConvertFrom-PocWebResponseContent {
    param([object]$Response)

    if (($Response.PSObject.Properties.Name -contains "RawContentStream") -and $Response.RawContentStream) {
        $stream = $Response.RawContentStream
        if ($stream.CanSeek) {
            $stream.Position = 0
        }
        $memory = New-Object System.IO.MemoryStream
        try {
            $stream.CopyTo($memory)
            return [System.Text.Encoding]::UTF8.GetString($memory.ToArray())
        } finally {
            $memory.Dispose()
        }
    }
    return [string]$Response.Content
}

function Invoke-PocJsonRequest {
    param(
        [string]$Uri,
        [ValidateSet("Get", "Post")]
        [string]$Method = "Get",
        [string]$Body = "",
        [int]$TimeoutSec = 15
    )

    $parameters = @{
        Uri = $Uri
        Method = $Method
        TimeoutSec = $TimeoutSec
        UseBasicParsing = $true
    }
    if ($Method -eq "Post") {
        $parameters["ContentType"] = "application/json; charset=utf-8"
        $parameters["Body"] = $Body
    }

    $response = Invoke-WebRequest @parameters
    $content = ConvertFrom-PocWebResponseContent -Response $response
    return $content | ConvertFrom-Json
}

function Test-PocPlaceholder {
    param([string]$Value)

    if (-not $Value) {
        return $true
    }
    $normalized = $Value.Trim().ToLowerInvariant()
    return $normalized -eq "replace_me" -or $normalized.StartsWith("your-") -or $normalized.Contains("your-")
}

function Select-PocText {
    param(
        [string]$Value,
        [string]$Fallback
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $Fallback
    }
    return $Value
}

function New-PocMarkdownReport {
    param(
        [object[]]$Results,
        [string]$Title
    )

    $lines = @(
        "# $Title",
        "",
        "- Generated: $(Get-Date -Format s)",
        "",
        "| Category | Check | Status | Message |",
        "| --- | --- | --- | --- |"
    )
    foreach ($result in $Results) {
        $message = ([string]$result.message).Replace("|", "\|").Replace("`r", " ").Replace("`n", " ")
        $lines += "| $($result.category) | $($result.name) | $($result.status) | $message |"
    }
    return ($lines -join "`n")
}

function Get-PocTimestamp {
    return Get-Date -Format "yyyyMMdd-HHmmss"
}
