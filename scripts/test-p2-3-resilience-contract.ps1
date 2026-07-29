[CmdletBinding()]
param([string]$RepoRoot)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = Join-Path $PSScriptRoot ".."
}
$repoRootPath = (Resolve-Path -LiteralPath $RepoRoot).Path
$validator = Join-Path $repoRootPath "scripts\validate-p2-3-resilience-contract.ps1"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$results = [System.Collections.Generic.List[object]]::new()

$contractFiles = @(
    "docs\acceptance\productization\P2.3\ACCEPTANCE_CARD.md",
    "apps\api\app\control_plane\p2_3.py",
    "apps\api\app\control_plane\p2_2.py",
    "apps\api\app\control_plane\router.py",
    "apps\api\app\control_plane\service.py",
    "apps\api\app\control_plane\store.py",
    "apps\web\src\controlPlaneApi.ts"
)

$tempRoot = [System.IO.Path]::GetTempPath()
$suiteRoot = Join-Path $tempRoot ("shuziren-p2-3-resilience-contract-" + [guid]::NewGuid().ToString("N"))

function Invoke-Validator {
    param(
        [string]$TargetRoot,
        [string]$HostExecutable
    )
    $arguments = @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $validator,
        "-RepoRoot",
        $TargetRoot
    )
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        # Windows PowerShell promotes native stderr to non-terminating
        # ErrorRecord instances. Expected validator failures are fixture output.
        $ErrorActionPreference = "Continue"
        $output = @(& $HostExecutable @arguments 2>&1)
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    return [pscustomobject]@{
        ExitCode = $exitCode
        Output = ($output -join "`n")
    }
}

function New-MutatedRepo {
    param(
        [string]$Name,
        [string]$RelativePath,
        [scriptblock]$MutateText
    )
    $fixtureRoot = Join-Path $suiteRoot $Name
    foreach ($relative in $contractFiles) {
        $sourcePath = Join-Path $repoRootPath $relative
        $targetPath = Join-Path $fixtureRoot $relative
        New-Item -ItemType Directory -Path (Split-Path -Parent $targetPath) -Force | Out-Null
        if ($relative -eq $RelativePath) {
            $text = [System.IO.File]::ReadAllText($sourcePath, (New-Object System.Text.UTF8Encoding($false, $true)))
            [System.IO.File]::WriteAllText($targetPath, (& $MutateText $text), $utf8NoBom)
        }
        else {
            Copy-Item -LiteralPath $sourcePath -Destination $targetPath
        }
    }
    return $fixtureRoot
}

function Assert-Rejects {
    param(
        [string]$Name,
        [string]$RelativePath,
        [scriptblock]$MutateText,
        [string]$ExpectedFragment
    )
    $fixtureRoot = New-MutatedRepo -Name $Name -RelativePath $RelativePath -MutateText $MutateText
    foreach ($hostExecutable in @("powershell.exe", "pwsh.exe")) {
        $result = Invoke-Validator -TargetRoot $fixtureRoot -HostExecutable $hostExecutable
        if ($result.ExitCode -eq 0) {
            throw "Negative fixture $Name was accepted by $hostExecutable"
        }
        if (-not $result.Output.Contains($ExpectedFragment)) {
            throw "Negative fixture $Name did not report '$ExpectedFragment' under $hostExecutable. Output: $($result.Output)"
        }
    }
    $results.Add([pscustomobject]@{ Name = $Name; Result = "REJECTED" })
}

New-Item -ItemType Directory -Path $suiteRoot -Force | Out-Null

try {
    foreach ($hostExecutable in @("powershell.exe", "pwsh.exe")) {
        $baseline = Invoke-Validator -TargetRoot $repoRootPath -HostExecutable $hostExecutable
        if ($baseline.ExitCode -ne 0) {
            throw "Baseline P2.3 resilience contract failed under ${hostExecutable}: $($baseline.Output)"
        }
        if (-not $baseline.Output.Contains("P2_3_RESILIENCE_CONTRACT_OK")) {
            throw "Baseline P2.3 resilience contract omitted its success marker under ${hostExecutable}: $($baseline.Output)"
        }
    }
    $results.Add([pscustomobject]@{ Name = "baseline-both-hosts"; Result = "ACCEPTED" })

    Assert-Rejects "route-removed" "apps\api\app\control_plane\router.py" {
        param($text)
        $text.Replace(
            '@router.get(f"{CONTROL_PREFIX}/screen-instances/{{screen_id}}/queue-status")',
            '# removed queue-status route'
        )
    } "screen queue-status route is missing"

    Assert-Rejects "signal-removed" "apps\api\app\control_plane\p2_3.py" {
        param($text)
        $text.Replace('    "backpressure",', '')
    } "drill signal closed set changed"

    Assert-Rejects "constant-duplicated" "apps\api\app\control_plane\p2_3.py" {
        param($text)
        $text + "`nMAX_GLOBAL_INFLIGHT = 6`n"
    } "capacity constants must not be duplicated in p2_3"

    Assert-Rejects "migration-006-added" "apps\api\app\control_plane\store.py" {
        param($text)
        $text.Replace(
            'MIGRATION_005_VERSION = "005_controlled_querying"',
            "MIGRATION_005_VERSION = `"005_controlled_querying`"`nMIGRATION_006_VERSION = `"006_resilience`""
        )
    } "schema migration 006 must not exist"

    Assert-Rejects "device-drill-route" "apps\api\app\control_plane\router.py" {
        param($text)
        $text + "`n@router.post(f`"{DEVICE_PREFIX}/resilience-drills`")`n"
    } "device-prefix resilience-drill routes are forbidden"

    Assert-Rejects "card-section-removed" "docs\acceptance\productization\P2.3\ACCEPTANCE_CARD.md" {
        param($text)
        $text.Replace("## Frozen Non-Scope", "## Removed Section")
    } "acceptance card section '## Frozen Non-Scope' is missing"

    Assert-Rejects "audit-unregistered" "apps\api\app\control_plane\service.py" {
        param($text)
        $text.Replace('"runResilienceDrill": (', '"runResilienceDrillRemoved": (')
    } "runResilienceDrill audit action is not registered"

    Assert-Rejects "frontend-function-missing" "apps\web\src\controlPlaneApi.ts" {
        param($text)
        $text.Replace("export function getScreenQueueStatus", "export function getScreenQueueStatusRemoved")
    } "frontend API function getScreenQueueStatus is missing"

    Write-Output "P2_3_RESILIENCE_CONTRACT_SELF_TEST_OK cases=$($results.Count)"
}
finally {
    $resolvedTempRoot = [System.IO.Path]::GetFullPath($tempRoot)
    $resolvedSuiteRoot = [System.IO.Path]::GetFullPath($suiteRoot)
    if (
        (Test-Path -LiteralPath $resolvedSuiteRoot) -and
        $resolvedSuiteRoot.StartsWith($resolvedTempRoot, [System.StringComparison]::OrdinalIgnoreCase) -and
        ([System.IO.Path]::GetFileName($resolvedSuiteRoot).StartsWith(
            "shuziren-p2-3-resilience-contract-",
            [System.StringComparison]::Ordinal
        ))
    ) {
        Remove-Item -LiteralPath $resolvedSuiteRoot -Recurse -Force
    }
}
