[CmdletBinding()]
param(
    [string]$RepoRoot,
    [string]$ContractPath
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = Join-Path $PSScriptRoot ".."
}

$repoRootPath = (Resolve-Path -LiteralPath $RepoRoot).Path
if ([string]::IsNullOrWhiteSpace($ContractPath)) {
    $ContractPath = Join-Path $repoRootPath "docs\product\contracts\p2-1-capability-profile-contract.json"
}
$contractFullPath = (Resolve-Path -LiteralPath $ContractPath).Path

$failures = [System.Collections.Generic.List[string]]::new()
$checks = 0

function Assert-Contract {
    param(
        [bool]$Condition,
        [string]$Message
    )
    $script:checks++
    if (-not $Condition) {
        $script:failures.Add($Message)
    }
}

function Test-ExactSequence {
    param(
        [AllowNull()][object[]]$Actual,
        [AllowNull()][object[]]$Expected
    )
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

function Test-SameSet {
    param(
        [AllowNull()][object[]]$Actual,
        [AllowNull()][object[]]$Expected
    )
    $actualValues = @($Actual | ForEach-Object { [string]$_ })
    $expectedValues = @($Expected | ForEach-Object { [string]$_ })
    [Array]::Sort($actualValues, [System.StringComparer]::Ordinal)
    [Array]::Sort($expectedValues, [System.StringComparer]::Ordinal)
    return (Test-ExactSequence -Actual $actualValues -Expected $expectedValues)
}

function Test-UniqueOrdinal {
    param([AllowNull()][object[]]$Values)
    $seen = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    foreach ($value in @($Values)) {
        if (-not $seen.Add([string]$value)) {
            return $false
        }
    }
    return $true
}

function Test-ContainsOrdinal {
    param(
        [AllowNull()][object[]]$Values,
        [AllowNull()][object]$Expected
    )
    foreach ($value in @($Values)) {
        if ([string]$value -ceq [string]$Expected) {
            return $true
        }
    }
    return $false
}

function Test-ExactPropertySequence {
    param(
        [AllowNull()][object]$Value,
        [string[]]$Expected
    )
    if ($null -eq $Value) {
        return $false
    }
    return (Test-ExactSequence -Actual @($Value.PSObject.Properties.Name) -Expected $Expected)
}

function Test-JsonInteger {
    param([AllowNull()][object]$Value)
    return (
        ($Value -is [sbyte]) -or
        ($Value -is [byte]) -or
        ($Value -is [int16]) -or
        ($Value -is [uint16]) -or
        ($Value -is [int32]) -or
        ($Value -is [uint32]) -or
        ($Value -is [int64]) -or
        ($Value -is [uint64])
    )
}

function Skip-StrictJsonWhitespace {
    while ($script:strictJsonIndex -lt $script:strictJsonText.Length) {
        $codePoint = [int]$script:strictJsonText[$script:strictJsonIndex]
        if ($codePoint -notin @(0x20, 0x09, 0x0A, 0x0D)) {
            break
        }
        $script:strictJsonIndex++
    }
}

function Read-StrictJsonString {
    if (
        $script:strictJsonIndex -ge $script:strictJsonText.Length -or
        $script:strictJsonText[$script:strictJsonIndex] -ne '"'
    ) {
        throw "JSON string expected at offset $script:strictJsonIndex"
    }

    $script:strictJsonIndex++
    $value = [System.Text.StringBuilder]::new()
    while ($script:strictJsonIndex -lt $script:strictJsonText.Length) {
        $character = $script:strictJsonText[$script:strictJsonIndex]
        $script:strictJsonIndex++

        if ($character -eq '"') {
            return $value.ToString()
        }
        if ([int]$character -lt 0x20) {
            throw "unescaped control character in JSON string"
        }
        if ($character -ne '\') {
            $null = $value.Append($character)
            continue
        }

        if ($script:strictJsonIndex -ge $script:strictJsonText.Length) {
            throw "unterminated JSON escape"
        }
        $escape = $script:strictJsonText[$script:strictJsonIndex]
        $script:strictJsonIndex++
        switch -CaseSensitive ($escape) {
            '"' { $null = $value.Append('"') }
            '\' { $null = $value.Append('\') }
            '/' { $null = $value.Append('/') }
            'b' { $null = $value.Append([char]0x08) }
            'f' { $null = $value.Append([char]0x0C) }
            'n' { $null = $value.Append([char]0x0A) }
            'r' { $null = $value.Append([char]0x0D) }
            't' { $null = $value.Append([char]0x09) }
            'u' {
                if (($script:strictJsonIndex + 4) -gt $script:strictJsonText.Length) {
                    throw "incomplete JSON Unicode escape"
                }
                $hex = $script:strictJsonText.Substring($script:strictJsonIndex, 4)
                if ($hex -notmatch '^[0-9A-Fa-f]{4}$') {
                    throw "invalid JSON Unicode escape"
                }
                $codeUnit = [int]::Parse(
                    $hex,
                    [System.Globalization.NumberStyles]::HexNumber,
                    [System.Globalization.CultureInfo]::InvariantCulture
                )
                $null = $value.Append([char]$codeUnit)
                $script:strictJsonIndex += 4
            }
            default { throw "invalid JSON escape '\$escape'" }
        }
    }
    throw "unterminated JSON string"
}

function Read-StrictJsonNumber {
    $length = $script:strictJsonText.Length
    $numberStart = $script:strictJsonIndex
    if (
        $script:strictJsonIndex -lt $length -and
        $script:strictJsonText[$script:strictJsonIndex] -eq '-'
    ) {
        $script:strictJsonIndex++
    }
    if ($script:strictJsonIndex -ge $length) {
        throw "incomplete JSON number"
    }

    $codePoint = [int]$script:strictJsonText[$script:strictJsonIndex]
    if ($codePoint -eq 0x30) {
        $script:strictJsonIndex++
        if ($script:strictJsonIndex -lt $length) {
            $nextCodePoint = [int]$script:strictJsonText[$script:strictJsonIndex]
            if ($nextCodePoint -ge 0x30 -and $nextCodePoint -le 0x39) {
                throw "leading zero in JSON number"
            }
        }
    }
    elseif ($codePoint -ge 0x31 -and $codePoint -le 0x39) {
        do {
            $script:strictJsonIndex++
            if ($script:strictJsonIndex -ge $length) {
                break
            }
            $codePoint = [int]$script:strictJsonText[$script:strictJsonIndex]
        } while ($codePoint -ge 0x30 -and $codePoint -le 0x39)
    }
    else {
        throw "invalid or non-finite JSON number"
    }

    if (
        $script:strictJsonIndex -lt $length -and
        $script:strictJsonText[$script:strictJsonIndex] -eq '.'
    ) {
        $script:strictJsonIndex++
        if ($script:strictJsonIndex -ge $length) {
            throw "missing fractional digits in JSON number"
        }
        $codePoint = [int]$script:strictJsonText[$script:strictJsonIndex]
        if ($codePoint -lt 0x30 -or $codePoint -gt 0x39) {
            throw "missing fractional digits in JSON number"
        }
        do {
            $script:strictJsonIndex++
            if ($script:strictJsonIndex -ge $length) {
                break
            }
            $codePoint = [int]$script:strictJsonText[$script:strictJsonIndex]
        } while ($codePoint -ge 0x30 -and $codePoint -le 0x39)
    }

    if (
        $script:strictJsonIndex -lt $length -and
        $script:strictJsonText[$script:strictJsonIndex] -in @('e', 'E')
    ) {
        $script:strictJsonIndex++
        if (
            $script:strictJsonIndex -lt $length -and
            $script:strictJsonText[$script:strictJsonIndex] -in @('+', '-')
        ) {
            $script:strictJsonIndex++
        }
        if ($script:strictJsonIndex -ge $length) {
            throw "missing exponent digits in JSON number"
        }
        $codePoint = [int]$script:strictJsonText[$script:strictJsonIndex]
        if ($codePoint -lt 0x30 -or $codePoint -gt 0x39) {
            throw "missing exponent digits in JSON number"
        }
        do {
            $script:strictJsonIndex++
            if ($script:strictJsonIndex -ge $length) {
                break
            }
            $codePoint = [int]$script:strictJsonText[$script:strictJsonIndex]
        } while ($codePoint -ge 0x30 -and $codePoint -le 0x39)
    }

    $numberText = $script:strictJsonText.Substring($numberStart, $script:strictJsonIndex - $numberStart)
    $numberValue = [double]0
    $numberIsFiniteAndRepresentable = [double]::TryParse(
        $numberText,
        [System.Globalization.NumberStyles]::Float,
        [System.Globalization.CultureInfo]::InvariantCulture,
        [ref]$numberValue
    )
    if (
        -not $numberIsFiniteAndRepresentable -or
        [double]::IsNaN($numberValue) -or
        [double]::IsInfinity($numberValue)
    ) {
        throw "non-finite or out-of-range JSON number"
    }
}

function Read-StrictJsonLiteral {
    param([string]$Literal)
    if (
        ($script:strictJsonIndex + $Literal.Length) -gt $script:strictJsonText.Length -or
        $script:strictJsonText.Substring($script:strictJsonIndex, $Literal.Length) -cne $Literal
    ) {
        throw "invalid JSON literal at offset $script:strictJsonIndex"
    }
    $script:strictJsonIndex += $Literal.Length
}

function Read-StrictJsonObject {
    $script:strictJsonIndex++
    $memberNames = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    Skip-StrictJsonWhitespace
    if (
        $script:strictJsonIndex -lt $script:strictJsonText.Length -and
        $script:strictJsonText[$script:strictJsonIndex] -eq '}'
    ) {
        $script:strictJsonIndex++
        return
    }

    while ($true) {
        Skip-StrictJsonWhitespace
        $memberName = Read-StrictJsonString
        if (-not $memberNames.Add($memberName)) {
            throw "duplicate JSON object member '$memberName'"
        }
        Skip-StrictJsonWhitespace
        if (
            $script:strictJsonIndex -ge $script:strictJsonText.Length -or
            $script:strictJsonText[$script:strictJsonIndex] -ne ':'
        ) {
            throw "':' expected after JSON object member"
        }
        $script:strictJsonIndex++
        Read-StrictJsonValue
        Skip-StrictJsonWhitespace
        if ($script:strictJsonIndex -ge $script:strictJsonText.Length) {
            throw "unterminated JSON object"
        }
        $separator = $script:strictJsonText[$script:strictJsonIndex]
        $script:strictJsonIndex++
        if ($separator -eq '}') {
            return
        }
        if ($separator -ne ',') {
            throw "',' or '}' expected in JSON object"
        }
    }
}

function Read-StrictJsonArray {
    $script:strictJsonIndex++
    Skip-StrictJsonWhitespace
    if (
        $script:strictJsonIndex -lt $script:strictJsonText.Length -and
        $script:strictJsonText[$script:strictJsonIndex] -eq ']'
    ) {
        $script:strictJsonIndex++
        return
    }

    while ($true) {
        Read-StrictJsonValue
        Skip-StrictJsonWhitespace
        if ($script:strictJsonIndex -ge $script:strictJsonText.Length) {
            throw "unterminated JSON array"
        }
        $separator = $script:strictJsonText[$script:strictJsonIndex]
        $script:strictJsonIndex++
        if ($separator -eq ']') {
            return
        }
        if ($separator -ne ',') {
            throw "',' or ']' expected in JSON array"
        }
    }
}

function Read-StrictJsonValue {
    Skip-StrictJsonWhitespace
    if ($script:strictJsonIndex -ge $script:strictJsonText.Length) {
        throw "JSON value expected"
    }
    $character = $script:strictJsonText[$script:strictJsonIndex]
    switch -CaseSensitive ($character) {
        '{' { Read-StrictJsonObject; return }
        '[' { Read-StrictJsonArray; return }
        '"' { $null = Read-StrictJsonString; return }
        't' { Read-StrictJsonLiteral -Literal "true"; return }
        'f' { Read-StrictJsonLiteral -Literal "false"; return }
        'n' { Read-StrictJsonLiteral -Literal "null"; return }
        default {
            $codePoint = [int]$character
            if ($character -eq '-' -or ($codePoint -ge 0x30 -and $codePoint -le 0x39)) {
                Read-StrictJsonNumber
                return
            }
            throw "invalid JSON token at offset $script:strictJsonIndex"
        }
    }
}

function Assert-StrictJsonText {
    param([string]$Text)
    $script:strictJsonText = $Text
    $script:strictJsonIndex = 0
    try {
        Read-StrictJsonValue
        Skip-StrictJsonWhitespace
        if ($script:strictJsonIndex -ne $script:strictJsonText.Length) {
            throw "multiple top-level JSON values or trailing content are forbidden"
        }
    }
    finally {
        $script:strictJsonText = $null
        $script:strictJsonIndex = 0
    }
}

try {
    $strictUtf8 = New-Object System.Text.UTF8Encoding($false, $true)
    $contractText = [System.IO.File]::ReadAllText($contractFullPath, $strictUtf8)
    Assert-StrictJsonText -Text $contractText
    $contract = $contractText | ConvertFrom-Json
}
catch {
    Write-Error "P2_1_CAPABILITY_PROFILE_CONTRACT_INVALID_JSON $($_.Exception.Message)"
    exit 1
}

$expectedContractFileSha256 = "ac5abbaa49a806489ee8e48877142d249e811ad2c6556ac00ef4041b226dfde4"
$actualContractFileSha256 = (Get-FileHash -LiteralPath $contractFullPath -Algorithm SHA256).Hash.ToLowerInvariant()
Assert-Contract (
    $actualContractFileSha256 -ceq $expectedContractFileSha256
) "contract file SHA-256 differs from the frozen P2.1 capability-profile contract"

$expectedTopLevelProperties = @(
    "contract_version",
    "lifecycle",
    "profile_schema_version",
    "provider_registry_version",
    "capabilities",
    "states",
    "timeout_ms",
    "fallback",
    "providers",
    "presets",
    "storage",
    "legacy_release_behavior",
    "deferred"
)
Assert-Contract (
    $contract -is [System.Management.Automation.PSCustomObject]
) "top-level contract must be a JSON object"
Assert-Contract (
    Test-ExactPropertySequence -Value $contract -Expected $expectedTopLevelProperties
) "top-level capability-profile contract schema is closed and ordered"

Assert-Contract (
    ($contract.contract_version -is [string]) -and
    ($contract.contract_version -ceq "p2.1-capability-profile-v1")
) "contract_version differs from p2.1-capability-profile-v1"
Assert-Contract (
    ($contract.lifecycle -is [string]) -and
    ($contract.lifecycle -ceq "TARGET_NOT_IMPLEMENTED")
) "lifecycle must remain TARGET_NOT_IMPLEMENTED"
Assert-Contract (
    ($contract.profile_schema_version -is [string]) -and
    ($contract.profile_schema_version -ceq "p2_capability_profile_v1")
) "profile_schema_version differs from p2_capability_profile_v1"
Assert-Contract (
    ($contract.provider_registry_version -is [string]) -and
    ($contract.provider_registry_version -ceq "p2_provider_registry_001")
) "provider_registry_version differs from p2_provider_registry_001"

$expectedCapabilities = @(
    "dora",
    "knowledge",
    "direct_llm",
    "asr",
    "tts",
    "querying",
    "fvs_control"
)
$capabilities = @($contract.capabilities)
Assert-Contract (
    Test-ExactSequence -Actual $capabilities -Expected $expectedCapabilities
) "capability registry differs from the frozen ordered set"
Assert-Contract (
    Test-UniqueOrdinal -Values $capabilities
) "capability IDs must be unique"
foreach ($capability in $capabilities) {
    Assert-Contract (
        ($capability -is [string]) -and
        ([string]$capability -cmatch '^[a-z][a-z0-9_]*$')
    ) "capability IDs must be lowercase stable identifiers"
}

$expectedStates = @(
    "disabled",
    "mock",
    "unverified",
    "available",
    "degraded"
)
$states = @($contract.states)
Assert-Contract (
    Test-ExactSequence -Actual $states -Expected $expectedStates
) "capability state registry differs from disabled/mock/unverified/available/degraded"
Assert-Contract (
    Test-UniqueOrdinal -Values $states
) "capability states must be unique"

Assert-Contract (
    Test-ExactPropertySequence -Value $contract.timeout_ms -Expected @("minimum", "maximum")
) "timeout_ms schema is closed and ordered"
Assert-Contract (
    (Test-JsonInteger -Value $contract.timeout_ms.minimum) -and
    ([long]$contract.timeout_ms.minimum -eq 100)
) "timeout minimum must be the integer 100"
Assert-Contract (
    (Test-JsonInteger -Value $contract.timeout_ms.maximum) -and
    ([long]$contract.timeout_ms.maximum -eq 120000)
) "timeout maximum must be the integer 120000"
Assert-Contract (
    ([long]$contract.timeout_ms.minimum -lt [long]$contract.timeout_ms.maximum)
) "timeout minimum must be less than maximum"

Assert-Contract (
    Test-ExactPropertySequence -Value $contract.fallback -Expected @(
        "allowed_reasons",
        "terminal_reasons",
        "permission_scope",
        "require_permission_equivalence"
    )
) "fallback schema is closed and ordered"
$expectedAllowedReasons = @("timeout", "unavailable", "unsupported")
$expectedTerminalReasons = @(
    "permission_denied",
    "invalid_request",
    "unauthorized_template",
    "cancelled"
)
$allowedReasons = @($contract.fallback.allowed_reasons)
$terminalReasons = @($contract.fallback.terminal_reasons)
Assert-Contract (
    Test-ExactSequence -Actual $allowedReasons -Expected $expectedAllowedReasons
) "fallback allowed reasons differ from timeout/unavailable/unsupported"
Assert-Contract (
    Test-ExactSequence -Actual $terminalReasons -Expected $expectedTerminalReasons
) "fallback terminal reasons differ from the frozen denial/error/cancellation set"
Assert-Contract (
    Test-UniqueOrdinal -Values $allowedReasons
) "fallback allowed reasons must be unique"
Assert-Contract (
    Test-UniqueOrdinal -Values $terminalReasons
) "fallback terminal reasons must be unique"
$fallbackReasonsAreDisjoint = $true
foreach ($reason in $allowedReasons) {
    if (Test-ContainsOrdinal -Values $terminalReasons -Expected $reason) {
        $fallbackReasonsAreDisjoint = $false
    }
}
Assert-Contract (
    $fallbackReasonsAreDisjoint
) "fallback allowed and terminal reasons must be disjoint"
Assert-Contract (
    ($contract.fallback.permission_scope -is [string]) -and
    ($contract.fallback.permission_scope -ceq "screen_bound")
) "fallback permission scope must remain screen_bound"
Assert-Contract (
    ($contract.fallback.require_permission_equivalence -is [bool]) -and
    ($contract.fallback.require_permission_equivalence -eq $true)
) "fallback must require permission equivalence"

$expectedProviderTuples = @(
    "local_rules|dora|available",
    "mock_dora|dora|mock",
    "dora_gateway|dora|unverified",
    "local_extractive|knowledge|available",
    "mock_knowledge|knowledge|mock",
    "dora_ragflow|knowledge|unverified",
    "ragflow_gateway|knowledge|unverified",
    "fixed_template|direct_llm|available",
    "mock_llm|direct_llm|mock",
    "direct_llm_gateway|direct_llm|unverified",
    "mock_asr|asr|mock",
    "vendor_asr|asr|unverified",
    "mock_tts|tts|mock",
    "browser_text_fallback|tts|degraded",
    "vendor_tts|tts|unverified",
    "mock_query|querying|mock",
    "finereport_ai_plugin|querying|unverified",
    "controlled_query|querying|unverified",
    "mock_fvs|fvs_control|mock",
    "fvs_page_number|fvs_control|unverified",
    "fvs_post_message|fvs_control|unverified"
)
$providers = @($contract.providers)
$providerTuples = @()
$providerIds = @()
$providerStates = @()
$providerCapabilities = @()
foreach ($provider in $providers) {
    Assert-Contract (
        $provider -is [System.Management.Automation.PSCustomObject]
    ) "every provider registry entry must be a JSON object"
    Assert-Contract (
        Test-ExactPropertySequence -Value $provider -Expected @("provider_id", "capability", "state")
    ) "provider registry entry schema is closed and ordered"

    $providerId = [string]$provider.provider_id
    $providerCapability = [string]$provider.capability
    $providerState = [string]$provider.state
    $providerIds += $providerId
    $providerCapabilities += $providerCapability
    $providerStates += $providerState
    $providerTuples += "$providerId|$providerCapability|$providerState"

    Assert-Contract (
        ($provider.provider_id -is [string]) -and
        ($providerId -cmatch '^[a-z][a-z0-9_]*$')
    ) "provider IDs must be lowercase stable identifiers"
    Assert-Contract (
        Test-ContainsOrdinal -Values $expectedCapabilities -Expected $providerCapability
    ) "provider $providerId references a capability outside the closed registry"
    Assert-Contract (
        Test-ContainsOrdinal -Values $expectedStates -Expected $providerState
    ) "provider $providerId references a state outside the closed registry"
    Assert-Contract (
        $providerState -cne "disabled"
    ) "provider $providerId cannot use the capability-only disabled state"
}
Assert-Contract (
    Test-ExactSequence -Actual $providerTuples -Expected $expectedProviderTuples
) "provider registry differs from the frozen ID/capability/state mapping"
Assert-Contract (
    Test-UniqueOrdinal -Values $providerIds
) "provider IDs must be unique across all capabilities"

$expectedProvidersByCapability = [ordered]@{
    dora = @("local_rules", "mock_dora", "dora_gateway")
    knowledge = @("local_extractive", "mock_knowledge", "dora_ragflow", "ragflow_gateway")
    direct_llm = @("fixed_template", "mock_llm", "direct_llm_gateway")
    asr = @("mock_asr", "vendor_asr")
    tts = @("mock_tts", "browser_text_fallback", "vendor_tts")
    querying = @("mock_query", "finereport_ai_plugin", "controlled_query")
    fvs_control = @("mock_fvs", "fvs_page_number", "fvs_post_message")
}
foreach ($capability in $expectedCapabilities) {
    $actualProviderIds = @(
        $providers |
            Where-Object { [string]$_.capability -ceq $capability } |
            ForEach-Object { [string]$_.provider_id }
    )
    Assert-Contract (
        Test-ExactSequence -Actual $actualProviderIds -Expected $expectedProvidersByCapability[$capability]
    ) "provider cross-capability mapping differs for $capability"
}

$expectedProviderStateById = [ordered]@{}
foreach ($expectedTuple in $expectedProviderTuples) {
    $tupleParts = $expectedTuple.Split('|')
    $expectedProviderStateById[$tupleParts[0]] = $tupleParts[2]
}
foreach ($provider in $providers) {
    $providerId = [string]$provider.provider_id
    if ($expectedProviderStateById.Contains($providerId)) {
        Assert-Contract (
            [string]$provider.state -ceq [string]$expectedProviderStateById[$providerId]
        ) "provider $providerId state differs from the frozen registry"
    }
}
Assert-Contract (
    Test-SameSet -Actual @($providerStates | Sort-Object -Unique) -Expected @(
        "available",
        "degraded",
        "mock",
        "unverified"
    )
) "provider registry must exercise available/degraded/mock/unverified without disabled"

$expectedPresets = @("text_only", "mock_voice", "mock_presenter")
$presets = @($contract.presets)
Assert-Contract (
    Test-ExactSequence -Actual $presets -Expected $expectedPresets
) "preset registry differs from text_only/mock_voice/mock_presenter"
Assert-Contract (
    Test-UniqueOrdinal -Values $presets
) "preset IDs must be unique"
foreach ($preset in $presets) {
    Assert-Contract (
        ($preset -is [string]) -and
        ([string]$preset -cmatch '^[a-z][a-z0-9_]*$')
    ) "preset IDs must be lowercase stable identifiers"
}

Assert-Contract (
    Test-ExactPropertySequence -Value $contract.storage -Expected @(
        "migration",
        "tables",
        "profile_versions_immutable",
        "draft_assignments_immutable",
        "release_snapshots_immutable"
    )
) "storage schema is closed and ordered"
Assert-Contract (
    ($contract.storage.migration -is [string]) -and
    ($contract.storage.migration -ceq "004_capability_profiles")
) "storage migration must remain 004_capability_profiles"
$expectedTables = @(
    "capability_profiles",
    "capability_profile_versions",
    "config_draft_capability_assignments",
    "release_target_capability_snapshots"
)
$storageTables = @($contract.storage.tables)
Assert-Contract (
    Test-ExactSequence -Actual $storageTables -Expected $expectedTables
) "storage table registry differs from the frozen ordered set"
Assert-Contract (
    Test-UniqueOrdinal -Values $storageTables
) "storage table names must be unique"
foreach ($table in $storageTables) {
    Assert-Contract (
        ($table -is [string]) -and
        ([string]$table -cmatch '^[a-z][a-z0-9_]*$')
    ) "storage table names must be lowercase stable identifiers"
}
Assert-Contract (
    ($contract.storage.profile_versions_immutable -is [bool]) -and
    ($contract.storage.profile_versions_immutable -eq $true)
) "capability profile versions must remain immutable"
Assert-Contract (
    ($contract.storage.draft_assignments_immutable -is [bool]) -and
    ($contract.storage.draft_assignments_immutable -eq $true)
) "config draft capability assignments must remain immutable"
Assert-Contract (
    ($contract.storage.release_snapshots_immutable -is [bool]) -and
    ($contract.storage.release_snapshots_immutable -eq $true)
) "release target capability snapshots must remain immutable"

Assert-Contract (
    ($contract.legacy_release_behavior -is [string]) -and
    ($contract.legacy_release_behavior -ceq "NOT_CONFIGURED_P2_1")
) "legacy release behavior must remain NOT_CONFIGURED_P2_1"

$expectedDeferred = @(
    "P2.2_QUERY_SOURCES",
    "P2.3_INTEGRATED_RESILIENCE_CERTIFICATION",
    "P2.4_FINEREPORT_PLUGIN",
    "P3_RENDERER_AVATAR_PACKAGE"
)
$deferred = @($contract.deferred)
Assert-Contract (
    Test-ExactSequence -Actual $deferred -Expected $expectedDeferred
) "deferred result registry differs from the frozen P2.2/P2.3/P2.4/P3 boundary"
Assert-Contract (
    Test-UniqueOrdinal -Values $deferred
) "deferred result IDs must be unique"

if ($failures.Count -gt 0) {
    Write-Output "P2_1_CAPABILITY_PROFILE_CONTRACT_FAILED checks=$checks failures=$($failures.Count)"
    foreach ($failure in $failures) {
        Write-Output " - $failure"
    }
    exit 1
}

Write-Output "P2_1_CAPABILITY_PROFILE_CONTRACT_OK checks=$checks capabilities=$($capabilities.Count) providers=$($providers.Count) presets=$($presets.Count) tables=$($storageTables.Count)"
