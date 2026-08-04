[CmdletBinding()]
param([string]$RepoRoot)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = Join-Path $PSScriptRoot ".."
}
$repoRootPath = (Resolve-Path -LiteralPath $RepoRoot).Path
$validator = Join-Path $repoRootPath "scripts\validate-p3-renderer-contract.ps1"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$results = [System.Collections.Generic.List[object]]::new()
$contractFiles = @(
    "docs\acceptance\productization\P3\ACCEPTANCE_CARD.md",
    "docs\NEXT_ACTIONS.md",
    "apps\api\app\control_plane\p3.py",
    "apps\api\app\control_plane\router.py",
    "apps\api\app\control_plane\service.py",
    "apps\api\app\control_plane\store.py",
    "apps\api\app\control_plane\recovery.py",
    "apps\api\app\control_plane\p1_3.py",
    "apps\web\src\controlPlaneApi.ts",
    "apps\web\src\ControlPlaneApp.vue"
)
$fixtureParent = Join-Path $repoRootPath "outputs"
$suiteRoot = Join-Path $fixtureParent ("p3-renderer-contract-" + [guid]::NewGuid().ToString("N"))
$hostExecutables = @(
    @("powershell.exe", "pwsh.exe") |
        Where-Object { $null -ne (Get-Command $_ -ErrorAction SilentlyContinue) }
)
if ($hostExecutables.Count -eq 0) {
    throw "No supported PowerShell host is available"
}

function Invoke-Validator {
    param([string]$TargetRoot, [string]$HostExecutable)
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
        $ErrorActionPreference = "Continue"
        $output = @(& $HostExecutable @arguments 2>&1)
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    return [pscustomobject]@{
        ExitCode = $exitCode
        Output = ($output -join [Environment]::NewLine)
    }
}

function New-MutatedRepo {
    param([string]$Name, [string]$RelativePath, [scriptblock]$MutateText)
    $fixtureRoot = Join-Path $suiteRoot $Name
    foreach ($relative in $contractFiles) {
        $sourcePath = Join-Path $repoRootPath $relative
        $targetPath = Join-Path $fixtureRoot $relative
        New-Item -ItemType Directory -Path (Split-Path -Parent $targetPath) -Force | Out-Null
        if ($relative -eq $RelativePath) {
            $text = [System.IO.File]::ReadAllText(
                $sourcePath,
                (New-Object System.Text.UTF8Encoding($false, $true))
            )
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
    $fixtureRoot = New-MutatedRepo $Name $RelativePath $MutateText
    foreach ($hostExecutable in $hostExecutables) {
        $result = Invoke-Validator $fixtureRoot $hostExecutable
        if ($result.ExitCode -eq 0) {
            throw "Negative fixture $Name was accepted by $hostExecutable"
        }
        if (-not $result.Output.Contains($ExpectedFragment)) {
            throw "Negative fixture $Name omitted '$ExpectedFragment' under $($hostExecutable): $($result.Output)"
        }
    }
    $results.Add([pscustomobject]@{ Name = $Name; Result = "REJECTED" })
}

New-Item -ItemType Directory -Path $suiteRoot -Force | Out-Null
try {
    foreach ($hostExecutable in $hostExecutables) {
        $baseline = Invoke-Validator $repoRootPath $hostExecutable
        if ($baseline.ExitCode -ne 0) {
            throw "Baseline P3 renderer contract failed under $($hostExecutable): $($baseline.Output)"
        }
        if (-not $baseline.Output.Contains("P3_RENDERER_CONTRACT_OK")) {
            throw "Baseline P3 validator omitted its success marker under $hostExecutable"
        }
    }
    $results.Add([pscustomobject]@{ Name = "baseline-both-hosts"; Result = "ACCEPTED" })

    Assert-Rejects "card-test-boundary-removed" "docs\acceptance\productization\P3\ACCEPTANCE_CARD.md" {
        param($text)
        $text.Replace("TEST_ONLY", "REMOVED_TEST_BOUNDARY")
    } "P3 acceptance card lost the test-only boundary"

    Assert-Rejects "renderer-production-enabled" "apps\api\app\control_plane\p3.py" {
        param($text)
        $text.Replace('"production_eligible": False', '"production_eligible": True')
    } "renderer registry must remain production-ineligible"

    Assert-Rejects "javascript-suffix-allowed" "apps\api\app\control_plane\p3.py" {
        param($text)
        $text.Replace('            ".js",', '')
    } "blocked executable resource suffix set changed"

    Assert-Rejects "migration-head-regressed" "apps\api\app\control_plane\store.py" {
        param($text)
        $text.Replace(
            "MIGRATION_VERSION = MIGRATION_006_VERSION",
            "MIGRATION_VERSION = MIGRATION_005_VERSION"
        )
    } "migration head is not 006"

    Assert-Rejects "backup-validator-removed" "apps\api\app\control_plane\recovery.py" {
        param($text)
        $text.Replace("BackupManager._validate_p3_avatar_data(connection)", "pass")
    } "backup verification omits P3 data"

    Assert-Rejects "device-avatar-mutation-added" "apps\api\app\control_plane\router.py" {
        param($text)
        $text + [Environment]::NewLine + '@router.post(f"{DEVICE_PREFIX}/avatar-publications")'
    } "device API exposes avatar mutation or prefetch routes"

    Assert-Rejects "frontend-dynamic-html-added" "apps\web\src\ControlPlaneApp.vue" {
        param($text)
        $text + [Environment]::NewLine + '<div v-html="avatarPreview"></div>'
    } "frontend contains a dynamic rendering or execution surface"

    Assert-Rejects "p24-deferment-removed" "docs\NEXT_ACTIONS.md" {
        param($text)
        $text.Replace(
            "P2.4 Deferred And Blocked By External Gate",
            "P2.4 Ready For Execution"
        )
    } "P2.4 deferment was lost"

    Write-Output "P3_RENDERER_CONTRACT_SELF_TEST_OK cases=$($results.Count)"
}
finally {
    $resolvedParent = [System.IO.Path]::GetFullPath($fixtureParent)
    $resolvedSuite = [System.IO.Path]::GetFullPath($suiteRoot)
    if (
        (Test-Path -LiteralPath $resolvedSuite) -and
        $resolvedSuite.StartsWith($resolvedParent, [System.StringComparison]::OrdinalIgnoreCase) -and
        ([System.IO.Path]::GetFileName($resolvedSuite).StartsWith(
            "p3-renderer-contract-",
            [System.StringComparison]::Ordinal
        ))
    ) {
        Remove-Item -LiteralPath $resolvedSuite -Recurse -Force
    }
}
