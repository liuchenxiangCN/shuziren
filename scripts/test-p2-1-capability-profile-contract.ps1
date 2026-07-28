[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$validator = Join-Path $PSScriptRoot "validate-p2-1-capability-profile-contract.ps1"
$sourceContract = Join-Path $repoRoot "docs\product\contracts\p2-1-capability-profile-contract.json"
$tempRoot = [System.IO.Path]::GetTempPath()
$suiteRoot = Join-Path $tempRoot ("shuziren-p2-1-capability-profile-contract-" + [guid]::NewGuid().ToString("N"))
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$strictUtf8 = New-Object System.Text.UTF8Encoding($false, $true)
$results = [System.Collections.Generic.List[object]]::new()

if ($PSVersionTable.PSEdition -ceq "Core") {
    $hostExecutable = Join-Path $PSHOME "pwsh.exe"
}
else {
    $hostExecutable = Join-Path $PSHOME "powershell.exe"
}

function Invoke-Validator {
    param([string]$Path)

    $arguments = @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $validator,
        "-RepoRoot",
        $repoRoot,
        "-ContractPath",
        $Path
    )
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        # Windows PowerShell promotes native stderr to non-terminating
        # ErrorRecord instances. Expected validator failures are fixture output.
        $ErrorActionPreference = "Continue"
        $output = @(& $hostExecutable @arguments 2>&1)
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

function Read-SourceContract {
    return ([System.IO.File]::ReadAllText($sourceContract, $strictUtf8) | ConvertFrom-Json)
}

function Write-FixtureContract {
    param(
        [string]$Name,
        [object]$Contract
    )
    $path = Join-Path $suiteRoot "$Name.json"
    $json = $Contract | ConvertTo-Json -Depth 100
    [System.IO.File]::WriteAllText($path, $json + "`n", $utf8NoBom)
    return $path
}

function Assert-Rejects {
    param(
        [string]$Name,
        [scriptblock]$Mutate,
        [string]$ExpectedFragment
    )
    $contract = Read-SourceContract
    & $Mutate $contract
    $path = Write-FixtureContract -Name $Name -Contract $contract
    $result = Invoke-Validator -Path $path
    if ($result.ExitCode -eq 0) {
        throw "Negative fixture $Name was accepted"
    }
    if (-not $result.Output.Contains($ExpectedFragment)) {
        throw "Negative fixture $Name did not report expected fragment '$ExpectedFragment'. Output: $($result.Output)"
    }
    $results.Add([pscustomobject]@{ Name = $Name; Result = "REJECTED" })
}

function Assert-RawRejects {
    param(
        [string]$Name,
        [scriptblock]$MutateText,
        [string]$ExpectedFragment
    )
    $sourceText = [System.IO.File]::ReadAllText($sourceContract, $strictUtf8)
    $mutatedText = & $MutateText $sourceText
    $path = Join-Path $suiteRoot "$Name.json"
    [System.IO.File]::WriteAllText($path, $mutatedText, $utf8NoBom)
    $result = Invoke-Validator -Path $path
    if ($result.ExitCode -eq 0) {
        throw "Negative raw fixture $Name was accepted"
    }
    if (-not $result.Output.Contains($ExpectedFragment)) {
        throw "Negative raw fixture $Name did not report expected fragment '$ExpectedFragment'. Output: $($result.Output)"
    }
    $results.Add([pscustomobject]@{ Name = $Name; Result = "REJECTED" })
}

New-Item -ItemType Directory -Path $suiteRoot -Force | Out-Null

try {
    $baseline = Invoke-Validator -Path $sourceContract
    if ($baseline.ExitCode -ne 0) {
        throw "Baseline P2.1 capability-profile contract failed: $($baseline.Output)"
    }
    if (-not $baseline.Output.Contains("P2_1_CAPABILITY_PROFILE_CONTRACT_OK")) {
        throw "Baseline P2.1 capability-profile contract omitted its success marker: $($baseline.Output)"
    }
    $results.Add([pscustomobject]@{ Name = "baseline"; Result = "ACCEPTED" })

    Assert-RawRejects "duplicate-json-member" {
        param($text)
        $text.Replace(
            '"contract_version": "p2.1-capability-profile-v1",',
            '"contract_version": "p2.1-capability-profile-v1", "contract_version": "p2.1-capability-profile-v1",'
        )
    } "P2_1_CAPABILITY_PROFILE_CONTRACT_INVALID_JSON"

    Assert-RawRejects "unicode-escaped-duplicate-json-member" {
        param($text)
        $text.Replace(
            '"contract_version": "p2.1-capability-profile-v1",',
            '"contract_version": "p2.1-capability-profile-v1", "\u0063ontract_version": "p2.1-capability-profile-v1",'
        )
    } "P2_1_CAPABILITY_PROFILE_CONTRACT_INVALID_JSON"

    Assert-RawRejects "leading-zero-json-number" {
        param($text)
        $text.Replace('"minimum": 100,', '"minimum": 0100,')
    } "P2_1_CAPABILITY_PROFILE_CONTRACT_INVALID_JSON"

    Assert-RawRejects "non-finite-json-number" {
        param($text)
        $text.Replace('"minimum": 100,', '"minimum": NaN,')
    } "P2_1_CAPABILITY_PROFILE_CONTRACT_INVALID_JSON"

    Assert-RawRejects "trailing-json-content" {
        param($text)
        $text + "`n{}"
    } "P2_1_CAPABILITY_PROFILE_CONTRACT_INVALID_JSON"

    Assert-Rejects "extra-top-level-field" {
        param($contract)
        $contract | Add-Member -NotePropertyName "extra" -NotePropertyValue $true
    } "top-level capability-profile contract schema is closed and ordered"

    Assert-Rejects "contract-version-drift" {
        param($contract)
        $contract.contract_version = "p2.1-capability-profile-v2"
    } "contract_version differs"

    Assert-Rejects "lifecycle-claims-implemented" {
        param($contract)
        $contract.lifecycle = "AS_BUILT"
    } "lifecycle must remain TARGET_NOT_IMPLEMENTED"

    Assert-Rejects "profile-schema-version-drift" {
        param($contract)
        $contract.profile_schema_version = "p2_capability_profile_v2"
    } "profile_schema_version differs"

    Assert-Rejects "provider-registry-version-drift" {
        param($contract)
        $contract.provider_registry_version = "p2_provider_registry_002"
    } "provider_registry_version differs"

    Assert-Rejects "capability-added" {
        param($contract)
        $contract.capabilities = @($contract.capabilities) + "renderer"
    } "capability registry differs from the frozen ordered set"

    Assert-Rejects "capability-duplicate" {
        param($contract)
        $contract.capabilities[1] = $contract.capabilities[0]
    } "capability IDs must be unique"

    Assert-Rejects "capability-order-drift" {
        param($contract)
        $first = $contract.capabilities[0]
        $contract.capabilities[0] = $contract.capabilities[1]
        $contract.capabilities[1] = $first
    } "capability registry differs from the frozen ordered set"

    Assert-Rejects "capability-state-added" {
        param($contract)
        $contract.states = @($contract.states) + "starting"
    } "capability state registry differs"

    Assert-Rejects "capability-state-duplicate" {
        param($contract)
        $contract.states[1] = $contract.states[0]
    } "capability states must be unique"

    Assert-Rejects "capability-state-order-drift" {
        param($contract)
        $first = $contract.states[0]
        $contract.states[0] = $contract.states[1]
        $contract.states[1] = $first
    } "capability state registry differs"

    Assert-Rejects "timeout-schema-open" {
        param($contract)
        $contract.timeout_ms | Add-Member -NotePropertyName "default" -NotePropertyValue 5000
    } "timeout_ms schema is closed and ordered"

    Assert-Rejects "timeout-minimum-string" {
        param($contract)
        $contract.timeout_ms.minimum = "100"
    } "timeout minimum must be the integer 100"

    Assert-Rejects "timeout-maximum-drift" {
        param($contract)
        $contract.timeout_ms.maximum = 120001
    } "timeout maximum must be the integer 120000"

    Assert-Rejects "fallback-schema-open" {
        param($contract)
        $contract.fallback | Add-Member -NotePropertyName "fallback_on_any_error" -NotePropertyValue $true
    } "fallback schema is closed and ordered"

    Assert-Rejects "permission-denied-becomes-fallback" {
        param($contract)
        $contract.fallback.allowed_reasons = @($contract.fallback.allowed_reasons) + "permission_denied"
    } "fallback allowed and terminal reasons must be disjoint"

    Assert-Rejects "cancelled-becomes-fallback" {
        param($contract)
        $contract.fallback.allowed_reasons = @($contract.fallback.allowed_reasons) + "cancelled"
    } "fallback allowed and terminal reasons must be disjoint"

    Assert-Rejects "fallback-allowed-reason-duplicate" {
        param($contract)
        $contract.fallback.allowed_reasons[1] = $contract.fallback.allowed_reasons[0]
    } "fallback allowed reasons must be unique"

    Assert-Rejects "fallback-terminal-reason-duplicate" {
        param($contract)
        $contract.fallback.terminal_reasons[1] = $contract.fallback.terminal_reasons[0]
    } "fallback terminal reasons must be unique"

    Assert-Rejects "fallback-terminal-reason-removed" {
        param($contract)
        $contract.fallback.terminal_reasons = @(
            $contract.fallback.terminal_reasons |
                Where-Object { $_ -cne "cancelled" }
        )
    } "fallback terminal reasons differ"

    Assert-Rejects "fallback-scope-widens" {
        param($contract)
        $contract.fallback.permission_scope = "deployment_bound"
    } "fallback permission scope must remain screen_bound"

    Assert-Rejects "fallback-permission-equivalence-disabled" {
        param($contract)
        $contract.fallback.require_permission_equivalence = $false
    } "fallback must require permission equivalence"

    Assert-Rejects "provider-entry-schema-open" {
        param($contract)
        $contract.providers[0] | Add-Member -NotePropertyName "endpoint" -NotePropertyValue "inline"
    } "provider registry entry schema is closed and ordered"

    Assert-Rejects "provider-added" {
        param($contract)
        $contract.providers = @($contract.providers) + [pscustomobject]@{
            provider_id = "extra_provider"
            capability = "dora"
            state = "unverified"
        }
    } "provider registry differs from the frozen ID/capability/state mapping"

    Assert-Rejects "provider-id-duplicate" {
        param($contract)
        $contract.providers[1].provider_id = $contract.providers[0].provider_id
    } "provider IDs must be unique across all capabilities"

    Assert-Rejects "provider-id-uppercase" {
        param($contract)
        $contract.providers[0].provider_id = "Local_Rules"
    } "provider IDs must be lowercase stable identifiers"

    Assert-Rejects "provider-cross-capability-remap" {
        param($contract)
        $contract.providers[0].capability = "knowledge"
    } "provider cross-capability mapping differs for dora"

    Assert-Rejects "provider-unknown-capability" {
        param($contract)
        $contract.providers[0].capability = "renderer"
    } "references a capability outside the closed registry"

    Assert-Rejects "provider-state-remap" {
        param($contract)
        $contract.providers[2].state = "available"
    } "provider dora_gateway state differs from the frozen registry"

    Assert-Rejects "provider-unknown-state" {
        param($contract)
        $contract.providers[2].state = "starting"
    } "references a state outside the closed registry"

    Assert-Rejects "provider-uses-disabled-state" {
        param($contract)
        $contract.providers[2].state = "disabled"
    } "cannot use the capability-only disabled state"

    Assert-Rejects "provider-order-drift" {
        param($contract)
        $first = $contract.providers[0]
        $contract.providers[0] = $contract.providers[1]
        $contract.providers[1] = $first
    } "provider registry differs from the frozen ID/capability/state mapping"

    Assert-Rejects "preset-added" {
        param($contract)
        $contract.presets = @($contract.presets) + "custom"
    } "preset registry differs"

    Assert-Rejects "preset-duplicate" {
        param($contract)
        $contract.presets[1] = $contract.presets[0]
    } "preset IDs must be unique"

    Assert-Rejects "preset-order-drift" {
        param($contract)
        $first = $contract.presets[0]
        $contract.presets[0] = $contract.presets[1]
        $contract.presets[1] = $first
    } "preset registry differs"

    Assert-Rejects "storage-schema-open" {
        param($contract)
        $contract.storage | Add-Member -NotePropertyName "downgrade" -NotePropertyValue $true
    } "storage schema is closed and ordered"

    Assert-Rejects "storage-migration-drift" {
        param($contract)
        $contract.storage.migration = "005_capability_profiles"
    } "storage migration must remain 004_capability_profiles"

    Assert-Rejects "storage-table-removed" {
        param($contract)
        $contract.storage.tables = @(
            $contract.storage.tables |
                Where-Object { $_ -cne "release_target_capability_snapshots" }
        )
    } "storage table registry differs"

    Assert-Rejects "storage-table-duplicate" {
        param($contract)
        $contract.storage.tables[1] = $contract.storage.tables[0]
    } "storage table names must be unique"

    Assert-Rejects "profile-version-mutable" {
        param($contract)
        $contract.storage.profile_versions_immutable = $false
    } "capability profile versions must remain immutable"

    Assert-Rejects "draft-assignment-mutable" {
        param($contract)
        $contract.storage.draft_assignments_immutable = $false
    } "config draft capability assignments must remain immutable"

    Assert-Rejects "release-snapshot-mutable" {
        param($contract)
        $contract.storage.release_snapshots_immutable = $false
    } "release target capability snapshots must remain immutable"

    Assert-Rejects "legacy-release-claims-profile" {
        param($contract)
        $contract.legacy_release_behavior = "text_only"
    } "legacy release behavior must remain NOT_CONFIGURED_P2_1"

    Assert-Rejects "deferred-result-removed" {
        param($contract)
        $contract.deferred = @(
            $contract.deferred |
                Where-Object { $_ -cne "P2.4_FINEREPORT_PLUGIN" }
        )
    } "deferred result registry differs"

    Assert-Rejects "deferred-result-duplicate" {
        param($contract)
        $contract.deferred[1] = $contract.deferred[0]
    } "deferred result IDs must be unique"

    Write-Output "P2_1_CAPABILITY_PROFILE_CONTRACT_SELF_TEST_OK cases=$($results.Count)"
}
finally {
    $resolvedTempRoot = [System.IO.Path]::GetFullPath($tempRoot)
    $resolvedSuiteRoot = [System.IO.Path]::GetFullPath($suiteRoot)
    if (
        (Test-Path -LiteralPath $resolvedSuiteRoot) -and
        $resolvedSuiteRoot.StartsWith($resolvedTempRoot, [System.StringComparison]::OrdinalIgnoreCase) -and
        ([System.IO.Path]::GetFileName($resolvedSuiteRoot).StartsWith(
            "shuziren-p2-1-capability-profile-contract-",
            [System.StringComparison]::Ordinal
        ))
    ) {
        Remove-Item -LiteralPath $resolvedSuiteRoot -Recurse -Force
    }
}
