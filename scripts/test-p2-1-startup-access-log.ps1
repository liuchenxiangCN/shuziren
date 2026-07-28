[CmdletBinding()]
param(
    [switch]$RuntimeProbe
)

$ErrorActionPreference = "Stop"
$repoRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$expectedEntrypoints = @(
    "scripts/start-p2-1-local-api.ps1",
    "scripts/start-p2-1-browser-gate.ps1",
    "apps/api/Dockerfile"
)
$p2StartupScripts = @(
    Get-ChildItem -LiteralPath (Join-Path $repoRoot "scripts") -File |
        Where-Object {
            $_.Name -like "start-p2-1-*.ps1" -and
            (Get-Content -Raw -LiteralPath $_.FullName).Contains("app.main:app")
        } |
        ForEach-Object {
            "scripts/$($_.Name)"
        }
)
$discoveredEntrypoints = @(
    $p2StartupScripts
    "apps/api/Dockerfile"
) | Sort-Object -Unique

$expectedSorted = @($expectedEntrypoints | Sort-Object)
if (
    $discoveredEntrypoints.Count -ne $expectedSorted.Count -or
    (Compare-Object -ReferenceObject $expectedSorted -DifferenceObject $discoveredEntrypoints)
) {
    throw "P2.1 startup entrypoint inventory drifted; review every new or removed entrypoint."
}

foreach ($relativePath in $expectedSorted) {
    $path = Join-Path $repoRoot $relativePath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "P2.1 startup entrypoint is missing: $relativePath"
    }

    $content = Get-Content -Raw -LiteralPath $path
    if ($relativePath.EndsWith("Dockerfile")) {
        $cmdMatches = @([regex]::Matches($content, '(?m)^CMD\s+(\[.*\])\s*$'))
        if ($cmdMatches.Count -ne 1) {
            throw "P2.1 Docker startup entrypoint must contain exactly one JSON CMD."
        }
        try {
            $parsedCommand = $cmdMatches[0].Groups[1].Value | ConvertFrom-Json
            $invocationTokens = @(
                foreach ($argument in $parsedCommand) {
                    [string]$argument
                }
            )
        }
        catch {
            throw "P2.1 Docker startup entrypoint CMD must remain valid JSON."
        }
    }
    else {
        $tokens = $null
        $parseErrors = $null
        [void][System.Management.Automation.Language.Parser]::ParseFile(
            $path,
            [ref]$tokens,
            [ref]$parseErrors
        )
        if ($parseErrors.Count -ne 0) {
            throw "P2.1 PowerShell startup entrypoint must parse cleanly: $relativePath"
        }
        $invocationTokens = @(
            $tokens |
                Where-Object { $_.Kind -ne "Comment" } |
                ForEach-Object { $_.Text.Trim([char[]]@([char]34, [char]39)) }
        )
    }

    $uvicornTokens = @($invocationTokens | Where-Object { $_ -ceq "uvicorn" })
    $appTargets = @($invocationTokens | Where-Object { $_ -ceq "app.main:app" })
    if ($uvicornTokens.Count -ne 1 -or $appTargets.Count -ne 1) {
        throw "P2.1 startup entrypoint must contain exactly one Uvicorn app invocation: $relativePath"
    }
    $disabledFlags = @($invocationTokens | Where-Object { $_ -ceq "--no-access-log" })
    if ($disabledFlags.Count -ne 1) {
        throw "P2.1 startup entrypoint must disable Uvicorn access logging exactly once: $relativePath"
    }
    if ($invocationTokens -ccontains "--access-log") {
        throw "P2.1 startup entrypoint must never enable Uvicorn access logging: $relativePath"
    }

    $uvicornIndex = -1
    $appTargetIndex = -1
    $disabledFlagIndex = -1
    for ($index = 0; $index -lt $invocationTokens.Count; $index++) {
        if ($invocationTokens[$index] -ceq "uvicorn") {
            $uvicornIndex = $index
        }
        elseif ($invocationTokens[$index] -ceq "app.main:app") {
            $appTargetIndex = $index
        }
        elseif ($invocationTokens[$index] -ceq "--no-access-log") {
            $disabledFlagIndex = $index
        }
    }
    if (
        $uvicornIndex -ge $appTargetIndex -or
        $appTargetIndex -ge $disabledFlagIndex
    ) {
        throw "P2.1 access-log guard must be part of the Uvicorn app invocation: $relativePath"
    }
}

if ($RuntimeProbe) {
    $apiRoot = Join-Path $repoRoot "apps/api"
    $uvicornPath = Join-Path $apiRoot ".venv/Scripts/uvicorn.exe"
    if (-not (Test-Path -LiteralPath $uvicornPath -PathType Leaf)) {
        throw "Runtime probe requires the API virtual environment."
    }

    $tempBase = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
    $tempName = "p21-access-log-" + [Guid]::NewGuid().ToString("N")
    $tempRoot = [System.IO.Path]::GetFullPath((Join-Path $tempBase $tempName))
    if (-not $tempRoot.StartsWith($tempBase, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Runtime probe temporary path escaped the system temporary directory."
    }
    New-Item -ItemType Directory -Path $tempRoot | Out-Null

    $apiProcess = $null
    try {
        $listener = [System.Net.Sockets.TcpListener]::new(
            [System.Net.IPAddress]::Loopback,
            0
        )
        $listener.Start()
        $port = ([System.Net.IPEndPoint]$listener.LocalEndpoint).Port
        $listener.Stop()

        $rootBytes = New-Object byte[] 32
        $random = [System.Security.Cryptography.RandomNumberGenerator]::Create()
        try {
            $random.GetBytes($rootBytes)
        }
        finally {
            $random.Dispose()
        }

        $env:CONTROL_PLANE_PREVIEW_MODE = "true"
        $env:CONTROL_PLANE_ROOT_KEY_B64 = [Convert]::ToBase64String($rootBytes)
        $env:CONTROL_PLANE_DB_PATH = Join-Path $tempRoot "control-plane.db"
        $env:CONTROL_PLANE_BACKUP_ROOT = Join-Path $tempRoot "backups"
        $env:SQLITE_PATH = Join-Path $tempRoot "sessions.db"
        $env:SESSION_LOG_RETENTION_DAYS = "3"
        $env:CONTROL_PLANE_ALLOWED_ORIGINS = '["http://127.0.0.1"]'

        $stdoutPath = Join-Path $tempRoot "stdout.log"
        $stderrPath = Join-Path $tempRoot "stderr.log"
        $apiProcess = Start-Process `
            -FilePath $uvicornPath `
            -ArgumentList @(
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                [string]$port,
                "--no-access-log"
            ) `
            -WorkingDirectory $apiRoot `
            -RedirectStandardOutput $stdoutPath `
            -RedirectStandardError $stderrPath `
            -WindowStyle Hidden `
            -PassThru

        $ready = $false
        for ($attempt = 0; $attempt -lt 80; $attempt++) {
            if ($apiProcess.HasExited) {
                throw "Runtime probe API exited before readiness."
            }
            try {
                $response = Invoke-WebRequest `
                    -UseBasicParsing `
                    -Uri "http://127.0.0.1:$port/api/health" `
                    -TimeoutSec 2
                if ($response.StatusCode -eq 200) {
                    $ready = $true
                    break
                }
            }
            catch {
                # Readiness polling is bounded; captured logs are never emitted.
            }
            Start-Sleep -Milliseconds 125
        }
        if (-not $ready) {
            throw "Runtime probe API did not become ready."
        }

        $marker = "synthetic-query-" + [Guid]::NewGuid().ToString("N")
        $probeResponse = Invoke-WebRequest `
            -UseBasicParsing `
            -Uri "http://127.0.0.1:$port/api/health?probe=$marker" `
            -TimeoutSec 5
        if ($probeResponse.StatusCode -ne 200) {
            throw "Runtime request-target probe failed."
        }

        Stop-Process -Id $apiProcess.Id -Force
        $apiProcess.WaitForExit()
        $combinedLogs = $null
        for ($attempt = 0; $attempt -lt 40; $attempt++) {
            try {
                $combinedLogs = (
                    [System.IO.File]::ReadAllText($stdoutPath) +
                    [System.IO.File]::ReadAllText($stderrPath)
                )
                break
            }
            catch [System.IO.IOException] {
                # Windows PowerShell can release redirected handles after process exit.
                Start-Sleep -Milliseconds 50
            }
        }
        if ($null -eq $combinedLogs) {
            throw "Runtime probe could not inspect captured logs."
        }
        if ($combinedLogs.Contains($marker) -or $combinedLogs.Contains("/api/health")) {
            throw "Runtime logs contained an unredacted request target."
        }
    }
    finally {
        if ($null -ne $apiProcess -and -not $apiProcess.HasExited) {
            Stop-Process -Id $apiProcess.Id -Force -ErrorAction SilentlyContinue
            $apiProcess.WaitForExit()
        }
        if (Test-Path -LiteralPath $tempRoot -PathType Container) {
            $resolvedCleanup = [System.IO.Path]::GetFullPath($tempRoot)
            $cleanupLeaf = Split-Path -Leaf $resolvedCleanup
            if (
                $resolvedCleanup.StartsWith(
                    $tempBase,
                    [System.StringComparison]::OrdinalIgnoreCase
                ) -and
                $cleanupLeaf.StartsWith("p21-access-log-")
            ) {
                Remove-Item -LiteralPath $resolvedCleanup -Recurse -Force
            }
        }
    }
}

$runtimeState = if ($RuntimeProbe) { "pass" } else { "not-run" }
Write-Output (
    "P2_1_STARTUP_ACCESS_LOG_TEST_OK " +
    "entrypoints=$($expectedSorted.Count) runtime_probe=$runtimeState"
)
