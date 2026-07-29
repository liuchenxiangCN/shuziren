[CmdletBinding()]
param(
    [string]$RepoRoot
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = Join-Path $PSScriptRoot ".."
}
$repoRootPath = (Resolve-Path -LiteralPath $RepoRoot).Path
$failures = [System.Collections.Generic.List[string]]::new()
$checks = 0

function Assert-Contract {
    param([bool]$Condition, [string]$Message)
    $script:checks++
    if (-not $Condition) {
        $script:failures.Add($Message)
    }
}

function Test-ExactSequence {
    param([AllowNull()][object[]]$Actual, [AllowNull()][object[]]$Expected)
    $actualValues = @($Actual | ForEach-Object { [string]$_ })
    $expectedValues = @($Expected | ForEach-Object { [string]$_ })
    if ($actualValues.Count -ne $expectedValues.Count) {
        return $false
    }
    for ($index = 0; $index -lt $actualValues.Count; $index++) {
        if ($actualValues[$index] -cne $expectedValues[$index]) {
            return $false
        }
    }
    return $true
}

function Read-RepoFile {
    param([string]$RelativePath)
    $path = Join-Path $repoRootPath $RelativePath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        return $null
    }
    return [System.IO.File]::ReadAllText($path, (New-Object System.Text.UTF8Encoding($false, $true)))
}

$card = Read-RepoFile "docs/acceptance/productization/P2.3/ACCEPTANCE_CARD.md"
$p23 = Read-RepoFile "apps/api/app/control_plane/p2_3.py"
$p22 = Read-RepoFile "apps/api/app/control_plane/p2_2.py"
$router = Read-RepoFile "apps/api/app/control_plane/router.py"
$service = Read-RepoFile "apps/api/app/control_plane/service.py"
$store = Read-RepoFile "apps/api/app/control_plane/store.py"
$frontend = Read-RepoFile "apps/web/src/controlPlaneApi.ts"

# Frozen acceptance card.
Assert-Contract ($null -ne $card) "P2.3 acceptance card is missing"
foreach ($section in @(
    "## Status",
    "## User-Visible Outcome",
    "## Entry Point And Test Data",
    "## Result Scenarios",
    "## Required Gates",
    "## Frozen Non-Scope",
    "## Immediate Failure Conditions",
    "## Rollback Target"
)) {
    Assert-Contract ($null -ne $card -and $card.Contains($section)) "acceptance card section '$section' is missing"
}
Assert-Contract ($null -ne $card -and $card.Contains("ACTIVE_RESULT_CARD_FROZEN")) "acceptance card is not frozen"
Assert-Contract ($null -ne $card -and $card.Contains("005_controlled_querying")) "acceptance card lost migration 005"
Assert-Contract (
    $null -ne $card -and $card.Contains("a75d3327fdc1ab4b83b0bba501d387af150353c4")
) "acceptance card lost the accepted P2.2 rollback commit"

# Closed P2.3 drill contract in p2_3.py.
Assert-Contract ($null -ne $p23) "p2_3.py is missing"
$signalsMatch = [regex]::Match(
    [string]$p23,
    '(?s)DRILL_SIGNALS\s*=\s*\((.*?)\)',
    [System.Text.RegularExpressions.RegexOptions]::CultureInvariant
)
$actualSignals = @()
if ($signalsMatch.Success) {
    $actualSignals = @(
        [regex]::Matches($signalsMatch.Groups[1].Value, '"([^"]+)"') |
            ForEach-Object { $_.Groups[1].Value }
    )
}
Assert-Contract (Test-ExactSequence $actualSignals @(
    "timeout", "unavailable", "unsupported", "permission_denied",
    "invalid_request", "unauthorized_template", "cancelled", "backpressure"
)) "drill signal closed set changed"
foreach ($outcome in @(
    "FALLBACK_RESOLVED", "TERMINAL_NO_FALLBACK", "CAPABILITY_DISABLED", "NO_FALLBACK_CONFIGURED"
)) {
    Assert-Contract ($null -ne $p23 -and $p23.Contains("`"$outcome`"")) "drill outcome $outcome is missing"
}
Assert-Contract ($null -ne $p23 -and $p23.Contains("MAX_RETAINED_DRILLS = 128")) "retained drill bound changed"
Assert-Contract ($null -ne $p23 -and $p23.Contains("RESILIENCE_DRILL_RUN")) "drill audit event is missing"

# Shared registries and capacity constants are imported, never duplicated.
$p21Import = [regex]::Match(
    [string]$p23,
    '(?s)from app\.control_plane\.p2_1 import \((.*?)\)',
    [System.Text.RegularExpressions.RegexOptions]::CultureInvariant
)
Assert-Contract ($p21Import.Success -and $p21Import.Groups[1].Value.Contains("CAPABILITY_KEYS")) `
    "capability keys are not imported from p2_1"
Assert-Contract ($p21Import.Success -and $p21Import.Groups[1].Value.Contains("FALLBACK_TERMINAL_REASONS")) `
    "fallback terminal reasons are not imported from p2_1"
Assert-Contract ($null -ne $p23 -and -not [regex]::IsMatch($p23, '(?m)^CAPABILITY_KEYS\s*=')) `
    "capability keys must not be duplicated in p2_3"
$p22Import = [regex]::Match(
    [string]$p23,
    '(?s)from app\.control_plane\.p2_2 import \((.*?)\)',
    [System.Text.RegularExpressions.RegexOptions]::CultureInvariant
)
$importedAll = $p22Import.Success
foreach ($constant in @("MAX_GLOBAL_INFLIGHT", "MAX_PER_SCREEN_INFLIGHT", "EXECUTOR_WORKERS", "MAX_RETAINED_JOBS")) {
    $importedAll = $importedAll -and $p22Import.Groups[1].Value.Contains($constant)
}
Assert-Contract $importedAll "capacity constants are not imported from p2_2"
Assert-Contract (
    $null -ne $p23 -and -not [regex]::IsMatch(
        $p23,
        '(?m)^(MAX_GLOBAL_INFLIGHT|MAX_PER_SCREEN_INFLIGHT|EXECUTOR_WORKERS|MAX_RETAINED_JOBS)\s*='
    )
) "capacity constants must not be duplicated in p2_3"
Assert-Contract ($null -ne $p22 -and $p22.Contains("MAX_GLOBAL_INFLIGHT = 6")) "global inflight bound changed"
Assert-Contract ($null -ne $p22 -and $p22.Contains("MAX_PER_SCREEN_INFLIGHT = 2")) "per-screen inflight bound changed"
Assert-Contract ($null -ne $p22 -and $p22.Contains("EXECUTOR_WORKERS = 3")) "executor worker count changed"
Assert-Contract ($null -ne $p22 -and $p22.Contains("MAX_RETAINED_JOBS = 256")) "retained job bound changed"

# Browser-session routes; no device-prefix drill or queue routes.
Assert-Contract (
    $null -ne $router -and $router.Contains('@router.get(f"{CONTROL_PREFIX}/screen-instances/{{screen_id}}/query-executions")')
) "screen query-executions list route is missing"
Assert-Contract (
    $null -ne $router -and $router.Contains('@router.get(f"{CONTROL_PREFIX}/screen-instances/{{screen_id}}/queue-status")')
) "screen queue-status route is missing"
$drillPost = [regex]::Match(
    [string]$router,
    '(?s)@router\.post\(\s*f"\{CONTROL_PREFIX\}/screen-instances/\{\{screen_id\}\}/resilience-drills",\s*status_code=201,?\s*\)',
    [System.Text.RegularExpressions.RegexOptions]::CultureInvariant
)
Assert-Contract $drillPost.Success "screen resilience-drill creation route with status 201 is missing"
Assert-Contract (
    $null -ne $router -and
    $router.Contains('f"{CONTROL_PREFIX}/screen-instances/{{screen_id}}/resilience-drills/{{drill_id}}"')
) "screen resilience-drill fetch route is missing"
Assert-Contract (
    $null -ne $router -and -not [regex]::IsMatch($router, 'DEVICE_PREFIX\}[^"]*resilience-drills')
) "device-prefix resilience-drill routes are forbidden"
Assert-Contract (
    $null -ne $router -and -not [regex]::IsMatch($router, 'DEVICE_PREFIX\}[^"]*queue-status')
) "device-prefix queue-status routes are forbidden"

# Audit action registration and service wiring.
Assert-Contract ($null -ne $service -and $service.Contains('"runResilienceDrill": (')) `
    "runResilienceDrill audit action is not registered"
Assert-Contract (
    $null -ne $service -and
    $service.Contains('"/api/v1/control-plane/screen-instances/{screen_id}/resilience-drills"')
) "runResilienceDrill idempotency route metadata is missing"
Assert-Contract (
    $null -ne $service -and $service.Contains("from app.control_plane.p2_3 import P23ControlPlane")
) "P23ControlPlane is not imported by the service"
Assert-Contract ($null -ne $service -and $service.Contains("self.p2_3 = P23ControlPlane(self)")) `
    "P23ControlPlane is not wired into the service"

# No schema migration beyond 005.
Assert-Contract ($null -ne $store -and -not $store.Contains("MIGRATION_006")) `
    "schema migration 006 must not exist"
Assert-Contract ($null -ne $store -and -not [regex]::IsMatch($store, '"006_')) `
    "no 006 migration version may be declared"
Assert-Contract ($null -ne $store -and $store.Contains("MIGRATION_VERSION = MIGRATION_005_VERSION")) `
    "store migration head must remain 005"

# Frontend API surface.
foreach ($functionName in @(
    "listScreenQueryExecutions", "getScreenQueueStatus", "startResilienceDrill", "getResilienceDrill"
)) {
    Assert-Contract ($null -ne $frontend -and $frontend.Contains("export function $functionName(")) `
        "frontend API function $functionName is missing"
}

if ($failures.Count -gt 0) {
    Write-Output "P2_3_RESILIENCE_CONTRACT_FAILED checks=$checks failures=$($failures.Count)"
    foreach ($failure in $failures) {
        Write-Output " - $failure"
    }
    exit 1
}
Write-Output "P2_3_RESILIENCE_CONTRACT_OK checks=$checks"
