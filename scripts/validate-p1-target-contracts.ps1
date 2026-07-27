[CmdletBinding()]
param(
    [string]$RepoRoot,
    [string]$ContractPath,
    [switch]$SkipMarkdown
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = Join-Path $PSScriptRoot ".."
}

$repoRootPath = (Resolve-Path -LiteralPath $RepoRoot).Path
if ([string]::IsNullOrWhiteSpace($ContractPath)) {
    $ContractPath = Join-Path $repoRootPath "docs\product\contracts\p1-target-contract.json"
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

function Test-SameSet {
    param(
        [object[]]$Actual,
        [object[]]$Expected
    )
    $actualValues = @($Actual | ForEach-Object { [string]$_ } | Sort-Object -Unique)
    $expectedValues = @($Expected | ForEach-Object { [string]$_ } | Sort-Object -Unique)
    return (($actualValues -join "`n") -ceq ($expectedValues -join "`n"))
}

function Test-ExactSequence {
    param(
        [object[]]$Actual,
        [object[]]$Expected
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

function ConvertTo-CanonicalJson {
    param([AllowNull()][object]$Value)

    if ($null -eq $Value) {
        return "null"
    }
    if ($Value -is [System.Management.Automation.PSCustomObject]) {
        $parts = [System.Collections.Generic.List[string]]::new()
        $propertyNames = [string[]]@($Value.PSObject.Properties.Name)
        [Array]::Sort($propertyNames, [System.StringComparer]::Ordinal)
        foreach ($propertyName in $propertyNames) {
            $property = $Value.PSObject.Properties[$propertyName]
            $nameJson = ConvertTo-Json -Compress -InputObject ([string]$propertyName)
            $valueJson = ConvertTo-CanonicalJson -Value $property.Value
            $parts.Add($nameJson + ":" + $valueJson)
        }
        return "{" + ($parts -join ",") + "}"
    }
    if ($Value -is [System.Collections.IDictionary]) {
        $parts = [System.Collections.Generic.List[string]]::new()
        $keys = [string[]]@($Value.Keys | ForEach-Object { [string]$_ })
        [Array]::Sort($keys, [System.StringComparer]::Ordinal)
        foreach ($key in $keys) {
            $nameJson = ConvertTo-Json -Compress -InputObject $key
            $valueJson = ConvertTo-CanonicalJson -Value $Value[$key]
            $parts.Add($nameJson + ":" + $valueJson)
        }
        return "{" + ($parts -join ",") + "}"
    }
    if (($Value -is [System.Collections.IEnumerable]) -and -not ($Value -is [string])) {
        $items = [System.Collections.Generic.List[string]]::new()
        foreach ($item in @($Value)) {
            $items.Add((ConvertTo-CanonicalJson -Value $item))
        }
        return "[" + ($items -join ",") + "]"
    }
    if ($Value -is [bool]) {
        if ($Value) {
            return "true"
        }
        return "false"
    }
    if (($Value -is [string]) -or ($Value -is [char])) {
        return (ConvertTo-Json -Compress -InputObject ([string]$Value))
    }
    if ($Value -is [System.IFormattable]) {
        return $Value.ToString($null, [System.Globalization.CultureInfo]::InvariantCulture)
    }
    return (ConvertTo-Json -Compress -Depth 100 -InputObject $Value)
}

function Get-Sha256 {
    param([string]$Text)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($Text)
        return (($sha.ComputeHash($bytes) | ForEach-Object { $_.ToString("x2") }) -join "")
    }
    finally {
        $sha.Dispose()
    }
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
    Write-Error "P1_CONTRACT_INVALID_JSON $($_.Exception.Message)"
    exit 1
}

$expectedContractFileSha256 = "b23214e074ed7582ad3e90109b9b2a181fdb408d9e738b093aed16e04ed66323"
$sha256 = [System.Security.Cryptography.SHA256]::Create()
$contractStream = $null
try {
    $contractStream = [System.IO.File]::OpenRead($contractFullPath)
    $actualContractFileSha256 = ([System.BitConverter]::ToString($sha256.ComputeHash($contractStream))).Replace("-", "").ToLowerInvariant()
}
finally {
    if ($null -ne $contractStream) {
        $contractStream.Dispose()
    }
    $sha256.Dispose()
}
Assert-Contract ($actualContractFileSha256 -ceq $expectedContractFileSha256) "machine contract raw UTF-8 file SHA-256 differs from the frozen P1.0 target contract"

Assert-Contract ($contract.schema_version -eq 1) "schema_version must be 1"
Assert-Contract ($contract.contract_version -ceq "p1.0-target-v1") "contract_version must be p1.0-target-v1"
Assert-Contract ($contract.logical_schema_version -ceq "p1_control_plane_001") "logical schema version is not frozen"
Assert-Contract ($contract.lifecycle -ceq "TARGET_NOT_IMPLEMENTED") "machine contract lifecycle must be TARGET_NOT_IMPLEMENTED"
Assert-Contract ($contract.implemented -eq $false) "machine contract must not claim implementation"
Assert-Contract (Test-ExactSequence @($contract.PSObject.Properties.Name) @(
    "schema_version",
    "contract_version",
    "logical_schema_version",
    "lifecycle",
    "implemented",
    "identity_planes",
    "entities",
    "internal_security_records",
    "permissions",
    "roles",
    "state_machines",
    "invariants",
    "deployment_mode_policy",
    "configuration_authorization",
    "resolution_policy",
    "data_integrity",
    "high_risk_policy",
    "iam_policy",
    "device_policy",
    "external_credential_rotation_policy",
    "key_management_policy",
    "storage",
    "retention",
    "api",
    "three_screen_fixture"
)) "machine contract top-level schema differs from the frozen version"

$expectedIdentityPlanes = @{
    "control_plane_user" = @("local_password_server_session", "authenticated_user_membership")
    "screen_device" = @("device_enrollment_device_credential", "credential_record")
    "finereport_data_identity" = @("secret_referenced_display_or_service_identity", "screen_owned_identity_binding")
}
$identityPlanes = @($contract.identity_planes)
$identityPlaneIds = @($identityPlanes | ForEach-Object { [string]$_.id })
Assert-Contract (Test-SameSet $identityPlaneIds @($expectedIdentityPlanes.Keys)) "identity planes must contain exactly the three frozen identities"
Assert-Contract (($identityPlaneIds | Sort-Object -Unique).Count -eq $identityPlaneIds.Count) "identity plane IDs must be unique"
foreach ($plane in $identityPlanes) {
    $planeId = [string]$plane.id
    Assert-Contract (Test-SameSet @($plane.PSObject.Properties.Name) @("id", "credential_type", "scope_source", "request_asserted_scope")) "identity plane $planeId properties differ from the frozen schema"
    Assert-Contract ($expectedIdentityPlanes.ContainsKey($planeId)) "identity plane $planeId is not allowed"
    if ($expectedIdentityPlanes.ContainsKey($planeId)) {
        Assert-Contract ($plane.credential_type -ceq $expectedIdentityPlanes[$planeId][0]) "identity plane $planeId credential type drifted"
        Assert-Contract ($plane.scope_source -ceq $expectedIdentityPlanes[$planeId][1]) "identity plane $planeId scope source drifted"
    }
    Assert-Contract ($plane.request_asserted_scope -eq $false) "identity plane $planeId must not trust request-asserted scope"
}

$requiredEntities = @(
    "Tenant",
    "Deployment",
    "Site",
    "ScreenGroup",
    "ScreenInstance",
    "DeviceEnrollment",
    "DeviceCredentialFamily",
    "DeviceCredential",
    "DigitalHumanInstance",
    "FineReportIdentityBinding",
    "FineReportIdentityBindingVersion",
    "RuntimeBinding",
    "UserAccount",
    "AuthSession",
    "BootstrapGrant",
    "PasswordResetToken",
    "SecretRecord",
    "SecretVersion",
    "ConfigDraft",
    "ConfigDraftRevision",
    "ConfigLayerRevision",
    "ResolutionFingerprint",
    "ConfigRelease",
    "ReleaseTarget",
    "Publication",
    "PublicationTarget",
    "HighRiskAction",
    "HighRiskApproval",
    "BackupRecord",
    "RestorePlan",
    "RecoverySecurityLedger",
    "SecurityAuditEvent"
)
$entities = @($contract.entities | ForEach-Object { [string]$_ })
Assert-Contract (Test-ExactSequence $entities $requiredEntities) "entity registry differs from the frozen P1 set"
Assert-Contract (($entities | Sort-Object -Unique).Count -eq $entities.Count) "entity names must be unique"

$requiredInternalSecurityRecords = @(
    "PasswordCredential",
    "UserRole",
    "OneTimeSecretResponseReplay",
    "IdempotencyRecord",
    "DirectOperationAuthorization",
    "AsyncOperation",
    "ImmutableTypedCommand",
    "FrozenPlan",
    "OutboxRecord",
    "RestoreCutoverRecord",
    "SecurityAuditSuffixSummary",
    "KeyMetadataRecord",
    "HumanOperatorIdentityAttestation",
    "HumanOperatorUserBinding",
    "DisasterRecoveryAuthorizationEnvelope",
    "DisasterEnvelopeNonceRecord",
    "ExternalOperationalFenceRecord",
    "ProductionReadinessRecoveryAuthorization",
    "ProductionReadinessNonceRecord",
    "EmergencyAuthorityReductionAuthorization",
    "EmergencyAuthorityReductionNonceRecord",
    "ExternalAuthorityRevocationTombstone",
    "CryptographicRootRecoveryAuthorization",
    "CryptographicRootRecoveryNonceRecord",
    "RecoveryPasswordSetupGrant",
    "StagedAdministratorAuthenticationProof",
    "ExternalRecoveryAudit",
    "ExternalProductionReadinessRecoveryAudit",
    "ExternalCryptographicRootRecoveryAudit",
    "RestoreContinuityEnvelope",
    "RecoverySecurityLedgerRecord"
)
$internalSecurityRecords = @($contract.internal_security_records | ForEach-Object { [string]$_ })
Assert-Contract (Test-ExactSequence $internalSecurityRecords $requiredInternalSecurityRecords) "internal security record registry differs from the frozen P1 set"
Assert-Contract (($internalSecurityRecords | Sort-Object -Unique).Count -eq $internalSecurityRecords.Count) "internal security record names must be unique"

$requiredPermissions = @(
    "user.manage",
    "role.assign",
    "deployment.manage",
    "screen.read",
    "screen.manage",
    "device.enroll",
    "device.revoke",
    "config.read",
    "config.edit_business",
    "config.edit_technical",
    "config.validate",
    "config.preview",
    "config.approve",
    "release.publish",
    "release.rollback",
    "secret.metadata.read",
    "secret.write",
    "finereport.binding.manage",
    "operation.read",
    "backup.create",
    "backup.restore",
    "risk.approve",
    "audit.read"
)
$permissions = @($contract.permissions | ForEach-Object { [string]$_ })
Assert-Contract (Test-ExactSequence $permissions $requiredPermissions) "permission registry differs from the frozen P1 set"
Assert-Contract (($permissions | Sort-Object -Unique).Count -eq $permissions.Count) "permission IDs must be unique"
Assert-Contract (-not ($permissions -contains "secret.reveal")) "secret.reveal must not exist"

$expectedRoles = @{
    "platform_admin" = $requiredPermissions
    "implementation_engineer" = @(
        "screen.read",
        "screen.manage",
        "device.enroll",
        "config.read",
        "config.edit_business",
        "config.edit_technical",
        "config.validate",
        "config.preview",
        "release.publish",
        "release.rollback",
        "secret.metadata.read",
        "operation.read"
    )
    "business_operator" = @(
        "screen.read",
        "config.read",
        "config.edit_business",
        "config.validate",
        "config.preview",
        "operation.read"
    )
    "operations_engineer" = @(
        "screen.read",
        "config.read",
        "operation.read",
        "backup.create",
        "audit.read"
    )
    "auditor" = @(
        "screen.read",
        "config.read",
        "operation.read",
        "audit.read"
    )
}
$roleNames = @($contract.roles.PSObject.Properties.Name)
Assert-Contract (Test-SameSet $roleNames @($expectedRoles.Keys)) "role registry differs from the frozen five roles"
foreach ($roleName in @($expectedRoles.Keys)) {
    $actualRolePermissions = @($contract.roles.$roleName | ForEach-Object { [string]$_ })
    Assert-Contract (Test-ExactSequence $actualRolePermissions $expectedRoles[$roleName]) "role $roleName permissions differ from the frozen exact matrix"
    Assert-Contract (($actualRolePermissions | Sort-Object -Unique).Count -eq $actualRolePermissions.Count) "role $roleName contains duplicate permissions"
}

$expectedStateMachines = @{
    "bootstrap_grant" = @{
        States = @("ISSUED", "CONSUMED", "EXPIRED", "REVOKED")
        Initial = "ISSUED"
        Terminal = @("CONSUMED", "EXPIRED", "REVOKED")
        Transitions = @(
            "ISSUED|CONSUMED|complete_bootstrap",
            "ISSUED|EXPIRED|expire",
            "ISSUED|REVOKED|revoke"
        )
    }
    "deployment_mode" = @{
        States = @("SETUP", "PRODUCTION_ACTIVE")
        Initial = "SETUP"
        Terminal = @("PRODUCTION_ACTIVE")
        Transitions = @(
            "SETUP|PRODUCTION_ACTIVE|activate_after_admin_and_disaster_recovery_readiness"
        )
    }
    "deployment_operational_posture" = @{
        States = @("READY", "RECOVERY_REQUIRED")
        Initial = "READY"
        Terminal = @()
        ExtraProperties = @("applies_when_deployment_mode")
        Transitions = @(
            "READY|RECOVERY_REQUIRED|effective_external_fence_after_admin_person_key_nonce_backup_or_disaster_readiness_loss",
            "RECOVERY_REQUIRED|READY|local_offline_recovery_and_complete_readiness_reproof"
        )
    }
    "password_reset_token" = @{
        States = @("ISSUED", "CONSUMED", "EXPIRED", "REVOKED")
        Initial = "ISSUED"
        Terminal = @("CONSUMED", "EXPIRED", "REVOKED")
        Transitions = @(
            "ISSUED|CONSUMED|consume",
            "ISSUED|EXPIRED|expire",
            "ISSUED|REVOKED|revoke"
        )
    }
    "recovery_password_setup_grant" = @{
        States = @("ISSUED", "PROVISIONALLY_CONSUMED", "COMMITTED_CONSUMED", "EXPIRED", "ABORTED_REVOKED")
        Initial = "ISSUED"
        Terminal = @("COMMITTED_CONSUMED", "EXPIRED", "ABORTED_REVOKED")
        Transitions = @(
            "ISSUED|PROVISIONALLY_CONSUMED|consume_into_staged_store_and_authenticate_selected_admin",
            "ISSUED|EXPIRED|expire",
            "ISSUED|ABORTED_REVOKED|abort_or_revoke",
            "PROVISIONALLY_CONSUMED|COMMITTED_CONSUMED|commit_with_matching_authority_anchor",
            "PROVISIONALLY_CONSUMED|EXPIRED|expire_before_authority_commit_destroy_provisional_verifiers_and_abort_entire_authority_transition_grant_set",
            "PROVISIONALLY_CONSUMED|ABORTED_REVOKED|destroy_provisional_verifiers_and_abort_entire_authority_transition_grant_set_before_authority_commit"
        )
    }
    "disaster_envelope_nonce_record" = @{
        States = @("RESERVED", "COMMITTED_CONSUMED", "ABORTED_CONSUMED")
        Initial = "RESERVED"
        Terminal = @("COMMITTED_CONSUMED", "ABORTED_CONSUMED")
        Transitions = @(
            "RESERVED|COMMITTED_CONSUMED|commit_with_matching_restore_cutover_anchor",
            "RESERVED|ABORTED_CONSUMED|abort_before_pointer_after_atomic_grant_set_cleanup"
        )
    }
    "local_authorization_nonce_record" = @{
        States = @("RESERVED", "COMMITTED_CONSUMED", "ABORTED_CONSUMED")
        Initial = "RESERVED"
        Terminal = @("COMMITTED_CONSUMED", "ABORTED_CONSUMED")
        ExtraProperties = @(
            "applies_to",
            "same_deployment_and_nonce_hmac_exact_retry_requires_same_authorization_and_exact_plan_or_effect_hash",
            "payload_mismatch_or_cross_authorization_reuse_result",
            "aborted_consumed_never_reopens",
            "committed_consumed_returns_only_exact_anchored_result",
            "reserved_startup_reconciles_forward_from_authenticated_prepared_or_tombstone_evidence"
        )
        Transitions = @(
            "RESERVED|COMMITTED_CONSUMED|commit_with_matching_local_maintenance_effect_and_anchor",
            "RESERVED|ABORTED_CONSUMED|abort_and_cleanup_without_authority_increase"
        )
    }
    "cryptographic_root_recovery_nonce_record" = @{
        States = @("RESERVED", "COMMITTED_CONSUMED", "ABORTED_CONSUMED")
        Initial = "RESERVED"
        Terminal = @("COMMITTED_CONSUMED", "ABORTED_CONSUMED")
        ExtraProperties = @(
            "exact_retry_requires_same_authorization_replacement_key_plan_and_anchor_generation",
            "terminal_record_never_reopens"
        )
        Transitions = @(
            "RESERVED|COMMITTED_CONSUMED|commit_exact_replacement_key_registry_and_recovery_required_checkpoint",
            "RESERVED|ABORTED_CONSUMED|revoke_staged_replacement_key_and_abort_without_ready_authority"
        )
    }
    "auth_session" = @{
        States = @("ACTIVE", "IDLE_EXPIRED", "ABSOLUTE_EXPIRED", "REVOKED")
        Initial = "ACTIVE"
        Terminal = @("IDLE_EXPIRED", "ABSOLUTE_EXPIRED", "REVOKED")
        Transitions = @(
            "ACTIVE|IDLE_EXPIRED|expire_idle",
            "ACTIVE|ABSOLUTE_EXPIRED|expire_absolute",
            "ACTIVE|REVOKED|revoke"
        )
    }
    "device_enrollment" = @{
        States = @("ISSUED", "CLAIMED", "EXPIRED", "REVOKED")
        Initial = "ISSUED"
        Terminal = @("CLAIMED", "EXPIRED", "REVOKED")
        Transitions = @(
            "ISSUED|CLAIMED|claim",
            "ISSUED|EXPIRED|expire",
            "ISSUED|REVOKED|revoke"
        )
    }
    "device_credential_family" = @{
        States = @("ACTIVE", "REVOKED", "REENROLL_REQUIRED")
        Initial = "ACTIVE"
        Terminal = @("REVOKED", "REENROLL_REQUIRED")
        Transitions = @(
            "ACTIVE|REVOKED|hard_revoke_family",
            "ACTIVE|REENROLL_REQUIRED|recovery_version_mismatch",
            "ACTIVE|REENROLL_REQUIRED|verifier_key_revoked_or_permanently_lost",
            "ACTIVE|REENROLL_REQUIRED|active_credential_expired"
        )
    }
    "device_credential" = @{
        States = @("PENDING_ACTIVATION", "ACTIVE", "EXPIRED", "REVOKED")
        EntryStates = @{
            "enrollment_claim" = "ACTIVE"
            "rotation_successor" = "PENDING_ACTIVATION"
        }
        Terminal = @("EXPIRED", "REVOKED")
        Transitions = @(
            "PENDING_ACTIVATION|ACTIVE|activate_successor_and_revoke_predecessor",
            "PENDING_ACTIVATION|EXPIRED|expire",
            "PENDING_ACTIVATION|REVOKED|hard_revoke",
            "ACTIVE|REVOKED|hard_revoke_or_successor_activation",
            "ACTIVE|EXPIRED|expire"
        )
    }
    "config_draft" = @{
        States = @("DRAFT", "VALIDATED", "PREVIEWED", "APPROVAL_PENDING", "APPROVED", "REJECTED", "RELEASED", "ABANDONED")
        Initial = "DRAFT"
        Terminal = @("RELEASED", "ABANDONED")
        Transitions = @(
            "DRAFT|VALIDATED|validate",
            "VALIDATED|PREVIEWED|preview",
            "PREVIEWED|APPROVAL_PENDING|submit_for_approval",
            "APPROVAL_PENDING|APPROVED|approve",
            "APPROVAL_PENDING|REJECTED|reject",
            "APPROVED|RELEASED|create_release",
            "VALIDATED|DRAFT|create_revision",
            "PREVIEWED|DRAFT|create_revision",
            "REJECTED|DRAFT|create_revision",
            "APPROVAL_PENDING|DRAFT|withdraw_and_create_revision",
            "APPROVED|DRAFT|create_revision_after_stale_fingerprint_or_control_plane_epoch",
            "DRAFT|ABANDONED|abandon",
            "VALIDATED|ABANDONED|abandon",
            "PREVIEWED|ABANDONED|abandon",
            "REJECTED|ABANDONED|abandon"
        )
    }
    "publication_target" = @{
        States = @("QUEUED", "WAITING_FOR_DEVICE", "APPLYING", "ACTIVE", "FAILED", "CANCELLED", "SUPERSEDED")
        Initial = "QUEUED"
        Terminal = @("FAILED", "CANCELLED", "SUPERSEDED")
        Transitions = @(
            "QUEUED|WAITING_FOR_DEVICE|mark_offline",
            "QUEUED|APPLYING|begin_apply",
            "WAITING_FOR_DEVICE|APPLYING|device_reconnect",
            "QUEUED|CANCELLED|cancel",
            "WAITING_FOR_DEVICE|CANCELLED|cancel",
            "APPLYING|ACTIVE|acknowledge_matching_release",
            "APPLYING|FAILED|fail_apply",
            "ACTIVE|SUPERSEDED|activate_newer_target"
        )
    }
    "restore_plan" = @{
        States = @("VALIDATING", "READY", "EXECUTING", "RECONCILING_SECURITY", "CUTOVER_PREPARED", "POINTER_SWITCHED_PENDING_ANCHOR", "ANCHOR_COMMITTED_PENDING_FINALIZATION", "COMPLETED", "COMPLETED_DEGRADED", "FAILED", "ABORTED")
        Initial = "VALIDATING"
        Terminal = @("COMPLETED", "COMPLETED_DEGRADED", "FAILED", "ABORTED")
        Transitions = @(
            "VALIDATING|READY|validation_pass",
            "VALIDATING|FAILED|validation_fail",
            "READY|EXECUTING|execute",
            "READY|ABORTED|abort",
            "EXECUTING|RECONCILING_SECURITY|verified_staged_data_ready_for_security_reconciliation",
            "EXECUTING|FAILED|safe_failure",
            "RECONCILING_SECURITY|CUTOVER_PREPARED|continuity_insert_verified_and_cutover_prepared",
            "CUTOVER_PREPARED|POINTER_SWITCHED_PENDING_ANCHOR|commit_staged_store_and_atomic_replace_active_pointer",
            "CUTOVER_PREPARED|FAILED|abort_before_pointer",
            "POINTER_SWITCHED_PENDING_ANCHOR|ANCHOR_COMMITTED_PENDING_FINALIZATION|append_cutover_committed_and_advance_anchor",
            "POINTER_SWITCHED_PENDING_ANCHOR|FAILED|startup_verify_and_atomically_revert_pointer",
            "ANCHOR_COMMITTED_PENDING_FINALIZATION|COMPLETED|idempotently_finalize_normal_execution_result_from_committed_anchor",
            "ANCHOR_COMMITTED_PENDING_FINALIZATION|COMPLETED_DEGRADED|idempotently_finalize_degraded_execution_result_from_committed_anchor",
            "RECONCILING_SECURITY|FAILED|security_reconciliation_fail_closed"
        )
    }
    "high_risk_action" = @{
        States = @("PENDING", "APPROVED", "REJECTED", "EXPIRED", "CONSUMED", "FAILED")
        Initial = "PENDING"
        Terminal = @("REJECTED", "EXPIRED", "CONSUMED", "FAILED")
        Transitions = @(
            "PENDING|APPROVED|approve_by_different_user",
            "PENDING|REJECTED|reject_by_different_user",
            "PENDING|EXPIRED|expire",
            "PENDING|FAILED|restore_epoch_changed",
            "PENDING|FAILED|request_hmac_key_revoked_or_permanently_lost",
            "APPROVED|CONSUMED|atomically_execute_exact_request_hash",
            "APPROVED|EXPIRED|expire",
            "APPROVED|FAILED|precondition_or_authorization_changed",
            "APPROVED|FAILED|restore_epoch_changed",
            "APPROVED|FAILED|request_hmac_key_revoked_or_permanently_lost"
        )
    }
}
$machineNames = @($contract.state_machines.PSObject.Properties.Name)
Assert-Contract (Test-SameSet $machineNames @($expectedStateMachines.Keys)) "state-machine registry differs from the frozen set"
foreach ($machineName in @($expectedStateMachines.Keys)) {
    $machine = $contract.state_machines.$machineName
    $expectedMachine = $expectedStateMachines[$machineName]
    $expectedProperties = @("states", "terminal", "transitions")
    if ($expectedMachine.ContainsKey("EntryStates")) {
        $expectedProperties += "entry_states"
    }
    else {
        $expectedProperties += "initial"
    }
    if ($expectedMachine.ContainsKey("ExtraProperties")) {
        $expectedProperties += @($expectedMachine.ExtraProperties)
    }
    Assert-Contract (Test-SameSet @($machine.PSObject.Properties.Name) $expectedProperties) "state machine $machineName properties differ from the frozen schema"
    Assert-Contract (Test-ExactSequence @($machine.states) $expectedMachine.States) "state machine $machineName states differ from the frozen sequence"
    Assert-Contract (Test-ExactSequence @($machine.terminal) $expectedMachine.Terminal) "state machine $machineName terminal states differ from the frozen sequence"
    if ($expectedMachine.ContainsKey("EntryStates")) {
        $entryNames = @($machine.entry_states.PSObject.Properties.Name)
        Assert-Contract (Test-SameSet $entryNames @($expectedMachine.EntryStates.Keys)) "state machine $machineName entry states differ from the frozen set"
        foreach ($entryName in @($expectedMachine.EntryStates.Keys)) {
            Assert-Contract ($machine.entry_states.$entryName -ceq $expectedMachine.EntryStates[$entryName]) "state machine $machineName entry $entryName is incorrect"
        }
    }
    else {
        Assert-Contract ($machine.initial -ceq $expectedMachine.Initial) "state machine $machineName initial state is incorrect"
    }
    $transitionKeys = @($machine.transitions | ForEach-Object { "$($_.from)|$($_.to)|$($_.operation)" })
    Assert-Contract (Test-ExactSequence $transitionKeys $expectedMachine.Transitions) "state machine $machineName legal transition set differs from the frozen contract"
    foreach ($terminalState in @($machine.terminal)) {
        Assert-Contract (@($machine.transitions | Where-Object { $_.from -eq $terminalState }).Count -eq 0) "state machine $machineName has outgoing transition from terminal state $terminalState"
    }
}
Assert-Contract ($contract.state_machines.deployment_operational_posture.applies_when_deployment_mode -ceq "PRODUCTION_ACTIVE") "operational posture state machine must apply only after production activation"
Assert-Contract (Test-ExactSequence @($contract.state_machines.local_authorization_nonce_record.applies_to) @("ProductionReadinessNonceRecord", "EmergencyAuthorityReductionNonceRecord")) "local authorization nonce state machine record set drifted"
foreach ($trueField in @(
    "same_deployment_and_nonce_hmac_exact_retry_requires_same_authorization_and_exact_plan_or_effect_hash",
    "aborted_consumed_never_reopens",
    "committed_consumed_returns_only_exact_anchored_result",
    "reserved_startup_reconciles_forward_from_authenticated_prepared_or_tombstone_evidence"
)) {
    Assert-Contract ($contract.state_machines.local_authorization_nonce_record.$trueField -eq $true) "local authorization nonce replay rule $trueField must remain true"
}
Assert-Contract ($contract.state_machines.local_authorization_nonce_record.payload_mismatch_or_cross_authorization_reuse_result -ceq "INVALID_STATE_TRANSITION") "local authorization nonce payload mismatch must fail closed"
Assert-Contract ($contract.state_machines.cryptographic_root_recovery_nonce_record.exact_retry_requires_same_authorization_replacement_key_plan_and_anchor_generation -eq $true) "cryptographic root recovery exact retry binding drifted"
Assert-Contract ($contract.state_machines.cryptographic_root_recovery_nonce_record.terminal_record_never_reopens -eq $true) "cryptographic root recovery terminal nonce must never reopen"

$expectedInvariants = @{
    "max_active_digital_humans_per_screen" = 1
    "max_active_device_credential_families_per_screen" = 1
    "max_active_device_credentials_per_family" = 1
    "max_pending_device_successors_per_family" = 1
    "separate_identity_credentials" = $true
    "device_scope_from_credential" = $true
    "permission_checked_every_request" = $true
    "ui_is_not_authorization_source" = $true
    "config_release_immutable" = $true
    "release_target_immutable" = $true
    "rollback_creates_new_release" = $true
    "group_target_set_frozen" = $true
    "approval_binds_resolution_fingerprint" = $true
    "release_targets_created_with_release" = $true
    "publication_never_creates_release_targets" = $true
    "publication_target_matches_release_and_screen" = $true
    "desired_and_applied_release_separate" = $true
    "secret_reveal_permission_exists" = $false
    "restore_overwrites_active_store" = $false
    "restore_fails_closed_without_fresh_security_anchor" = $true
    "password_reset_never_enables_user" = $true
    "password_reset_revokes_sessions_and_advances_authentication_epoch" = $true
    "bootstrap_completion_invalidates_other_grants" = $true
    "network_product_mutation_may_remove_last_enabled_deployment_platform_admin" = $false
    "product_mutations_may_not_reduce_credential_usable_enabled_deployment_platform_admins_below" = 2
    "product_mutations_may_not_reduce_distinct_attested_platform_admin_person_ids_below" = 2
    "unexpected_admin_person_key_or_disaster_readiness_loss_fences_production" = $true
    "production_activation_requires_disaster_recovery_readiness" = $true
    "user_and_device_security_mutations_require_ledger_commit" = $true
    "release_creation_kind_xor" = $true
    "high_risk_approval_does_not_execute" = $true
    "high_risk_consume_and_effect_atomic" = $true
    "restored_authorization_snapshot_authoritative" = $true
    "restore_never_increases_secret_version_usability" = $true
    "restore_never_increases_finereport_binding_usability" = $true
    "permission_denial_fallback_allowed" = $false
}
Assert-Contract (Test-SameSet @($contract.invariants.PSObject.Properties.Name) @($expectedInvariants.Keys)) "invariant registry differs from the frozen set"
foreach ($entry in $expectedInvariants.GetEnumerator()) {
    Assert-Contract ($contract.invariants.($entry.Key) -eq $entry.Value) "invariant $($entry.Key) has an unsafe value"
}

$deploymentModePolicy = $contract.deployment_mode_policy
Assert-Contract ($deploymentModePolicy.setup_external_serving_allowed -eq $false) "SETUP must never expose external serving"
Assert-Contract ($deploymentModePolicy.production_activation_is_irreversible -eq $true) "production activation must remain irreversible"
Assert-Contract ($deploymentModePolicy.production_activation_operation -ceq "activateDeploymentProduction") "production activation operation drifted"
Assert-Contract ($deploymentModePolicy.deployment_status_operation -ceq "getDeploymentStatus") "deployment status operation drifted"
Assert-Contract ($deploymentModePolicy.setup_config_work_is_limited_to_draft_validation_and_preview -eq $true) "SETUP configuration work must remain non-production"
Assert-Contract ($deploymentModePolicy.setup_cannot_submit_approve_or_create_production_release -eq $true) "SETUP must not create production approval or release authority"
Assert-Contract ($deploymentModePolicy.activation_invalidates_all_setup_validation_preview_or_approval_evidence_for_production_use -eq $true) "SETUP evidence must not become production authority"
Assert-Contract ($deploymentModePolicy.device_surface_policy_by_mode_and_posture.SETUP -ceq "DENY_ALL_DEVICE_SURFACE_REQUESTS") "SETUP device surface must remain denied"
Assert-Contract ($deploymentModePolicy.device_surface_policy_by_mode_and_posture.PRODUCTION_ACTIVE_RECOVERY_REQUIRED -ceq "ALLOW_ONLY_GET_RUNTIME_BINDING_AND_CURRENT_RELEASE_CLAMPED_TO_LAST_ACKNOWLEDGED_APPLIED_TARGET_DENY_CLAIM_ROTATE_ACK_AND_HEARTBEAT_WRITES") "RECOVERY_REQUIRED device access must remain clamped read-only"

$allNetworkOperationIds = @($contract.api.operations | ForEach-Object { [string]$_.operation_id })
Assert-Contract (-not @($deploymentModePolicy.setup_allowed_operations | Where-Object { $_ -notin $allNetworkOperationIds }).Count) "SETUP operation allowlist references an unknown API operation"
Assert-Contract (-not @($deploymentModePolicy.production_recovery_required_policy.allowed_network_operations | Where-Object { $_ -notin $allNetworkOperationIds }).Count) "RECOVERY_REQUIRED operation allowlist references an unknown API operation"
$expectedSetupAllowedOperations = @(
    "completeBootstrap",
    "getDeploymentStatus",
    "activateDeploymentProduction",
    "createAuthSession",
    "getCurrentAuthSession",
    "refreshCsrfToken",
    "reauthenticateAuthSession",
    "listOwnAuthSessions",
    "revokeOwnAuthSession",
    "deleteCurrentAuthSession",
    "changeOwnPassword",
    "listUsers",
    "getUser",
    "getUserRoleAssignments",
    "listRoleDefinitions",
    "createUser",
    "updateUser",
    "disableUser",
    "enableUser",
    "unlockUser",
    "issuePasswordReset",
    "consumePasswordReset",
    "listUserAuthSessions",
    "revokeUserAuthSession",
    "replaceUserRoles",
    "listSites",
    "getSite",
    "listScreenGroups",
    "getScreenGroup",
    "createScreenGroup",
    "updateScreenGroup",
    "listScreenInstances",
    "getScreenInstance",
    "createScreenInstance",
    "updateScreenInstance",
    "getDigitalHumanInstance",
    "createDigitalHumanInstance",
    "getRuntimeBinding",
    "getFineReportIdentityBinding",
    "getHighRiskAction",
    "listPendingHighRiskActions",
    "approveHighRiskAction",
    "rejectHighRiskAction",
    "createConfigDraft",
    "getConfigDraft",
    "replaceConfigDraftSpec",
    "reviseConfigDraft",
    "abandonConfigDraft",
    "validateConfigDraft",
    "previewConfigDraft",
    "getConfigRelease",
    "diffConfigReleases",
    "getStorageProfile",
    "createBackup",
    "getBackup",
    "verifyBackup",
    "getOperation",
    "listAuditEvents"
)
Assert-Contract (Test-ExactSequence @($deploymentModePolicy.setup_allowed_operations) $expectedSetupAllowedOperations) "SETUP operation allowlist drifted"
Assert-Contract (Test-ExactSequence @($deploymentModePolicy.setup_prohibited_effects) @(
    "device_credential_issue_claim_rotate_or_runtime_authentication",
    "publication_or_rollback",
    "runtime_release_delivery_or_acknowledgement",
    "secret_or_finereport_credential_activation",
    "restore_cutover",
    "external_device_or_runtime_traffic"
)) "SETUP prohibited-effect registry drifted"
$expectedRecoveryRequiredAllowedOperations = @(
    "getDeploymentStatus",
    "createAuthSession",
    "getCurrentAuthSession",
    "refreshCsrfToken",
    "reauthenticateAuthSession",
    "listOwnAuthSessions",
    "revokeOwnAuthSession",
    "deleteCurrentAuthSession",
    "changeOwnPassword",
    "listUsers",
    "getUser",
    "getUserRoleAssignments",
    "listRoleDefinitions",
    "listUserAuthSessions",
    "listSites",
    "getSite",
    "listScreenGroups",
    "getScreenGroup",
    "listScreenInstances",
    "getScreenInstance",
    "getDigitalHumanInstance",
    "getRuntimeBinding",
    "getFineReportIdentityBinding",
    "getDeviceEnrollment",
    "getDeviceCredentialMetadata",
    "getSecretMetadata",
    "getHighRiskAction",
    "listPendingHighRiskActions",
    "getConfigDraft",
    "getConfigRelease",
    "diffConfigReleases",
    "getPublication",
    "getStorageProfile",
    "getBackup",
    "verifyBackup",
    "getOperation",
    "listAuditEvents",
    "getDeviceRuntimeBinding",
    "getDeviceCurrentRelease"
)
Assert-Contract (Test-ExactSequence @($deploymentModePolicy.production_recovery_required_policy.allowed_network_operations) $expectedRecoveryRequiredAllowedOperations) "RECOVERY_REQUIRED operation allowlist drifted"
Assert-Contract ($deploymentModePolicy.production_recovery_required_policy.all_other_network_operations_denied_by_default -eq $true) "RECOVERY_REQUIRED network operations must deny by default"
Assert-Contract ($deploymentModePolicy.production_recovery_required_policy.temporary_dependency_gate_may_further_deny_an_allowed_operation_with_retryable_503 -eq $true) "temporary readiness dependency loss must fail closed"
Assert-Contract ($deploymentModePolicy.production_recovery_required_policy.return_to_ready_posture_requires_local_offline_authorization_and_atomic_complete_readiness_recheck -eq $true) "RECOVERY_REQUIRED must clear only through local offline authorization and complete readiness"
Assert-Contract ($deploymentModePolicy.production_recovery_required_policy.never_returns_to_setup -eq $true) "production recovery must never reopen SETUP"

$setupActivationPolicy = $deploymentModePolicy.setup_activation_policy
foreach ($trueField in @(
    "requires_two_enabled_credential_usable_deployment_platform_admin_users",
    "requires_two_distinct_current_attested_person_ids_and_user_bindings",
    "initiator_and_approver_require_deployment_manage_risk_approve_and_recent_reauthentication",
    "initiator_and_approver_user_person_role_credential_binding_and_eligibility_generations_frozen_and_rechecked",
    "requires_current_ledger_head_initial_ready_fence_generation_and_complete_atomic_readiness_snapshot",
    "mode_transition_readiness_evidence_high_risk_consumption_domain_row_audit_and_ledger_anchor_atomic_or_reconciled",
    "failure_keeps_mode_setup_and_external_serving_forbidden"
)) {
    Assert-Contract ($setupActivationPolicy.$trueField -eq $true) "production activation rule $trueField must remain true"
}

$operationalFencePolicy = $deploymentModePolicy.operational_fence_policy
Assert-Contract ($operationalFencePolicy.authoritative_location -ceq "EXTERNAL_MONOTONIC_OPERATIONAL_FENCE_ANCHOR") "operational fence authoritative location drifted"
foreach ($trueField in @(
    "effective_posture_is_recovery_required_when_highest_verified_fence_or_confirmed_persistent_readiness_breach_says_so",
    "temporary_required_registry_anchor_key_or_dependency_unavailability_sets_ephemeral_fail_closed_gate_only",
    "temporary_unavailability_keeps_persisted_posture_and_domain_state_unchanged_and_returns_retryable_503",
    "dependency_recovery_automatically_clears_ephemeral_gate_without_offline_ceremony",
    "confirmed_loss_revocation_invalid_evidence_or_persistent_readiness_breach_appends_recovery_required_fence",
    "fail_closed_gate_applies_before_a_persistent_fence_or_ledger_evidence_can_be_written",
    "database_and_ledger_posture_evidence_reconciled_when_ledger_returns"
)) {
    Assert-Contract ($operationalFencePolicy.$trueField -eq $true) "operational fence availability rule $trueField must remain true"
}
Assert-Contract ($operationalFencePolicy.fence_hmac_algorithm -ceq "HMAC-SHA-256") "operational fence must use HMAC-SHA-256"
Assert-Contract ($operationalFencePolicy.fence_hmac_purpose_domain -ceq "OPERATIONAL_FENCE_HMAC") "operational fence purpose domain drifted"
Assert-Contract ($operationalFencePolicy.fence_hmac_domain_separator -ceq "shuziren:p1:deployment-operational-fence:v1") "operational fence domain separator drifted"
Assert-Contract ($operationalFencePolicy.fence_hmac_canonicalization -ceq "RFC8785_JCS_AFTER_STRICT_TYPED_PARSE") "operational fence canonicalization drifted"
Assert-Contract ($operationalFencePolicy.fence_hmac_input -ceq "COMPLETE_FENCE_RECORD_EXCLUDING_FENCE_HMAC") "operational fence HMAC input drifted"
Assert-Contract ($operationalFencePolicy.records_append_only_and_generation_compare_and_swap -eq $true) "operational fence records must be append-only CAS"
Assert-Contract ($operationalFencePolicy.external_anchor_verifies_transition_evidence_not_only_fence_hmac -eq $true) "a fence HMAC alone must not authorize READY"
Assert-Contract ($operationalFencePolicy.clear_writes_new_authenticated_ready_successor_and_never_mutates_or_deletes_prior_fence -eq $true) "operational fence recovery must append a successor"
Assert-Contract ($operationalFencePolicy.fence_record_branch_rules.RECOVERY_REQUIRED -ceq "FAIL_CLOSED_REASON_AND_OBSERVED_FACTS_REQUIRED_CLEAR_AUTHORIZATION_NONCE_AND_FINALIZED_RESULT_FIELDS_NULL") "RECOVERY_REQUIRED fence branch drifted"
Assert-Contract ($operationalFencePolicy.fence_record_branch_rules.READY_INITIAL_ACTIVATION -ceq "CONSUMED_ACTIVATION_HIGH_RISK_ACTION_LEDGER_COMMIT_AND_COMPLETE_READINESS_SNAPSHOT_REQUIRED") "initial READY fence branch drifted"
Assert-Contract ($operationalFencePolicy.fence_record_branch_rules.READY_RECOVERY_SUCCESSOR -ceq "OFFLINE_RECOVERY_AUTHORIZATION_TERMINAL_NONCE_LEDGER_COMMIT_COMPLETE_READINESS_EXTERNAL_RECOVERY_AUDIT_AND_FINALIZED_RESULT_REQUIRED") "recovery READY fence branch drifted"
Assert-Contract ($operationalFencePolicy.hmac_only_ready_successor_without_verified_offline_or_activation_evidence_result -ceq "CRYPTOGRAPHIC_INTEGRITY_FAILURE") "an HMAC-only READY fence must fail integrity verification"
Assert-Contract ($operationalFencePolicy.startup_uses_highest_verified_monotonic_generation -eq $true) "startup must use the highest verified fence generation"
Assert-Contract ($operationalFencePolicy.clear_fence_requires_local_offline_authorization_complete_readiness_and_ledger_anchor -eq $true) "clearing a production fence requires offline authority, complete readiness and the ledger anchor"
Assert-Contract (Test-ExactSequence @($operationalFencePolicy.fence_record_schema) @(
    "fence_record_id",
    "deployment_id",
    "operational_posture",
    "fence_generation",
    "supersedes_fence_generation",
    "reason_code",
    "observed_readiness_facts_hash",
    "transition_authorization_kind",
    "transition_authorization_id",
    "transition_authorization_hash",
    "custodian_signature_evidence_hash",
    "ledger_committed_sequence",
    "ledger_committed_head_hash",
    "authorization_nonce_registry_kind",
    "authorization_nonce_terminal_generation",
    "authorization_nonce_terminal_record_hash",
    "readiness_snapshot_hash",
    "external_recovery_audit_hash",
    "recovery_finalized_result_hash",
    "fence_hmac_key_id",
    "fence_hmac",
    "created_at"
)) "operational fence record schema drifted"

$expectedLocalMaintenanceOperations = @(
    "recoverProductionReadiness",
    "emergencyReduceAuthority",
    "recoverCryptographicReadinessRoot"
)
$localMaintenanceOperations = @($deploymentModePolicy.local_maintenance_operations)
Assert-Contract (Test-ExactSequence @($localMaintenanceOperations.operation_id) $expectedLocalMaintenanceOperations) "local maintenance operation registry drifted"
Assert-Contract (-not @($localMaintenanceOperations | Where-Object { $_.operation_id -in $allNetworkOperationIds }).Count) "local maintenance operations must not be exposed as network APIs"
Assert-Contract (-not @($localMaintenanceOperations | Where-Object { $_.ledger_mutation -notin $contract.storage.recovery_security_ledger.ledger_backed_mutations }).Count) "local maintenance operation references an unknown ledger mutation"
$expectedLocalMaintenanceMap = @{
    "recoverProductionReadiness" = @(
        "ProductionReadinessRecoveryAuthorization",
        "deployment_production_readiness_recovery",
        "ExternalProductionReadinessRecoveryAuditThenSecurityAuditEvent",
        "COMPLETE_READINESS_LEDGER_AND_FENCE_ANCHORS_COMMITTED_EFFECTIVE_POSTURE_READY"
    )
    "emergencyReduceAuthority" = @(
        "EmergencyAuthorityReductionAuthorization",
        "emergency_authority_reduction_reconciliation",
        "ExternalAuthorityRevocationTombstoneThenSecurityAuditEvent",
        "SUBJECT_DENIED_BY_EXTERNAL_TOMBSTONE_EFFECTIVE_POSTURE_REMAINS_RECOVERY_REQUIRED"
    )
    "recoverCryptographicReadinessRoot" = @(
        "CryptographicRootRecoveryAuthorization",
        "cryptographic_readiness_root_recovery_reconciliation",
        "ExternalCryptographicRootRecoveryAuditThenSecurityAuditEvent",
        "REPLACEMENT_ROOT_KEY_OR_VERIFICATION_CHECKPOINT_INSTALLED_EFFECTIVE_POSTURE_REMAINS_RECOVERY_REQUIRED"
    )
}
foreach ($operation in $localMaintenanceOperations) {
    $expected = $expectedLocalMaintenanceMap[$operation.operation_id]
    Assert-Contract (
        ($operation.surface -ceq "LOCAL_MAINTENANCE_ONLY_NO_NETWORK_API") -and
        ($operation.authorization -ceq $expected[0]) -and
        ($operation.ledger_mutation -ceq $expected[1]) -and
        ($operation.audit_record -ceq $expected[2]) -and
        ($operation.success_postcondition -ceq $expected[3])
    ) "local maintenance operation $($operation.operation_id) authority or evidence mapping drifted"
}

$localAuditPolicy = $deploymentModePolicy.local_maintenance_security_audit_policy
Assert-Contract (Test-ExactSequence @($localAuditPolicy.PSObject.Properties.Name) @(
    "network_execution_authorization_ids_are_null",
    "sanitized_local_actor_and_custodian_evidence_only",
    "security_audit_event_appended_only_after_matching_terminal_nonce_external_evidence_and_ledger_anchor",
    "common_record_schema",
    "by_operation"
)) "local maintenance security-audit policy schema drifted"
foreach ($trueField in @(
    "network_execution_authorization_ids_are_null",
    "sanitized_local_actor_and_custodian_evidence_only",
    "security_audit_event_appended_only_after_matching_terminal_nonce_external_evidence_and_ledger_anchor"
)) {
    Assert-Contract ($localAuditPolicy.$trueField -eq $true) "local maintenance audit $trueField must remain true"
}
Assert-Contract (Test-ExactSequence @($localAuditPolicy.common_record_schema) @(
    "event_id",
    "operation_id",
    "actor_kind",
    "authorization_kind",
    "authorization_id",
    "authorization_hash",
    "terminal_nonce_record_id",
    "terminal_nonce_hash",
    "external_evidence_kind",
    "external_evidence_id",
    "external_evidence_hash",
    "custodian_evidence_hash",
    "ledger_committed_sequence",
    "ledger_committed_head",
    "result",
    "reason",
    "request_id",
    "previous_hash",
    "event_hash"
)) "local maintenance security-audit record schema drifted"
Assert-Contract (Test-ExactSequence @($localAuditPolicy.by_operation.PSObject.Properties.Name) $expectedLocalMaintenanceOperations) "local maintenance audit operation set drifted"
$expectedLocalAuditMap = @{
    "recoverProductionReadiness" = @(
        "PRODUCTION_READINESS_CUSTODIAN",
        "ProductionReadinessRecoveryAuthorization",
        "ProductionReadinessNonceRecord",
        "EXTERNAL_PRODUCTION_READINESS_RECOVERY_AUDIT",
        "ExternalProductionReadinessRecoveryAudit"
    )
    "emergencyReduceAuthority" = @(
        "EMERGENCY_AUTHORITY_REDUCTION_CUSTODIAN",
        "EmergencyAuthorityReductionAuthorization",
        "EmergencyAuthorityReductionNonceRecord",
        "EXTERNAL_AUTHORITY_REVOCATION_TOMBSTONE",
        "ExternalAuthorityRevocationTombstone"
    )
    "recoverCryptographicReadinessRoot" = @(
        "CRYPTOGRAPHIC_ROOT_RECOVERY_CUSTODIAN",
        "CryptographicRootRecoveryAuthorization",
        "CryptographicRootRecoveryNonceRecord",
        "EXTERNAL_CRYPTOGRAPHIC_ROOT_RECOVERY_AUDIT",
        "ExternalCryptographicRootRecoveryAudit"
    )
}
foreach ($operationId in $expectedLocalMaintenanceOperations) {
    $actual = $localAuditPolicy.by_operation.$operationId
    $expected = $expectedLocalAuditMap[$operationId]
    Assert-Contract (Test-ExactSequence @($actual.PSObject.Properties.Name) @(
        "authorization_kind",
        "authorization_record",
        "terminal_nonce_record",
        "external_evidence_kind",
        "external_evidence_record"
    )) "local maintenance audit mapping schema drifted for $operationId"
    Assert-Contract (
        ($actual.authorization_kind -ceq $expected[0]) -and
        ($actual.authorization_record -ceq $expected[1]) -and
        ($actual.terminal_nonce_record -ceq $expected[2]) -and
        ($actual.external_evidence_kind -ceq $expected[3]) -and
        ($actual.external_evidence_record -ceq $expected[4])
    ) "local maintenance audit mapping drifted for $operationId"
}

$productionReadinessRecovery = $deploymentModePolicy.production_readiness_recovery
Assert-Contract ($productionReadinessRecovery.network_api_exposed -eq $false) "production readiness recovery must remain local only"
Assert-Contract (Test-ExactSequence @($productionReadinessRecovery.authorization_modes) @("READINESS_ONLY", "ADMIN_REPLACEMENT")) "production readiness recovery authorization modes drifted"
Assert-Contract ($productionReadinessRecovery.nonce_hmac_purpose_domain -ceq "PRODUCTION_READINESS_NONCE_HMAC") "production readiness nonce purpose drifted"
Assert-Contract ($productionReadinessRecovery.nonce_reserved_before_any_recovery_effect_or_optional_grant_issue_and_terminally_consumed_on_commit_or_abort -eq $true) "production readiness nonce must be terminal before replay"
Assert-Contract ($productionReadinessRecovery.admin_replacement_mode_may_create_bind_enable_or_grant_exactly_one_replacement_admin_only_until_floor_two -eq $true) "production readiness admin replacement authority is too broad"
Assert-Contract ($productionReadinessRecovery.cannot_change_any_other_user_role_permission_or_credential -eq $true) "production readiness recovery must not widen unrelated authority"
Assert-Contract ($productionReadinessRecovery.external_audit_policy.record_type -ceq "ExternalProductionReadinessRecoveryAudit") "production readiness external audit record drifted"
Assert-Contract ($productionReadinessRecovery.external_audit_policy.ready_fence_successor_must_bind_record_hash_and_finalized_result_hash -eq $true) "READY successor must bind production readiness audit and result"
Assert-Contract ($productionReadinessRecovery.external_audit_policy.ordered_hash_chain_and_external_worm_append_required -eq $true) "production readiness external audit must be a WORM hash chain"
Assert-Contract (Test-ExactSequence @($productionReadinessRecovery.external_audit_policy.record_schema) @(
    "sequence",
    "previous_record_hash",
    "authorization_hash",
    "authorization_mode",
    "remediation_class",
    "exact_remediation_plan_hash",
    "current_operational_fence_generation",
    "pre_recovery_readiness_facts_hash",
    "offline_recovery_signature_key_ids_sorted_distinct",
    "human_attestation_signature_key_ids_sorted_distinct",
    "nonce_terminal_record_hash",
    "ledger_committed_sequence",
    "ledger_committed_head_hash",
    "post_recovery_readiness_snapshot_hash",
    "finalized_result_hash",
    "result",
    "created_at"
)) "production readiness external audit schema drifted"

$emergencyAuthorityReduction = $deploymentModePolicy.emergency_authority_reduction
Assert-Contract ($emergencyAuthorityReduction.authorization_requires_two_distinct_offline_recovery_custodian_signatures -eq $true) "emergency authority reduction requires two independent custodians"
Assert-Contract ($emergencyAuthorityReduction.authority_increase_enable_role_grant_or_new_credential_forbidden -eq $true) "emergency authority reduction must never increase authority"
Assert-Contract ($emergencyAuthorityReduction.safety_revocation_not_blocked_by_admin_floor_and_keeps_recovery_fence -eq $true) "emergency safety revocation must remain possible while production stays fenced"
Assert-Contract ($emergencyAuthorityReduction.nonce_hmac_purpose_domain -ceq "EMERGENCY_AUTHORITY_REDUCTION_NONCE_HMAC") "emergency authority reduction nonce purpose drifted"
Assert-Contract ($emergencyAuthorityReduction.external_tombstones_append_only_and_compare_and_swap_by_subject_generation -eq $true) "emergency authority tombstones must be append-only CAS"

$cryptographicRootRecovery = $deploymentModePolicy.cryptographic_root_recovery
Assert-Contract ($cryptographicRootRecovery.network_api_exposed -eq $false) "cryptographic root recovery must remain local only"
Assert-Contract (Test-ExactSequence @($cryptographicRootRecovery.recoverable_roots) @("PRODUCTION_READINESS_NONCE_HMAC", "EMERGENCY_AUTHORITY_REDUCTION_NONCE_HMAC", "DISASTER_ENVELOPE_NONCE_HMAC", "OPERATIONAL_FENCE_HMAC")) "cryptographic root recovery scope drifted"
Assert-Contract ($cryptographicRootRecovery.cannot_write_ready_fence_modify_users_roles_credentials_or_business_state -eq $true) "cryptographic root recovery must not grant READY or business authority"
Assert-Contract ($cryptographicRootRecovery.after_root_recovery_normal_production_readiness_recovery_with_fresh_authorization_and_nonce_is_required -eq $true) "cryptographic root recovery must require a separate readiness recovery"
Assert-Contract ($cryptographicRootRecovery.external_audit_policy.record_type -ceq "ExternalCryptographicRootRecoveryAudit") "cryptographic root recovery external audit record drifted"
Assert-Contract ($cryptographicRootRecovery.external_audit_policy.ordered_hash_chain_and_anchor_native_worm_append_required -eq $true) "cryptographic root recovery audit must be an anchor-native WORM hash chain"
Assert-Contract (Test-ExactSequence @($cryptographicRootRecovery.external_audit_policy.record_schema) @(
    "sequence",
    "previous_record_hash",
    "authorization_hash",
    "confirmed_lost_purpose_domain",
    "highest_previous_worm_checkpoint_hash",
    "exact_replacement_key_plan_hash",
    "replacement_key_id",
    "custodian_registry_generation",
    "custodian_signature_key_ids_sorted_distinct",
    "root_nonce_terminal_record_hash",
    "new_key_registry_generation",
    "recovery_required_checkpoint_hash",
    "result",
    "created_at"
)) "cryptographic root recovery external audit schema drifted"
$localRecoveryExternalAuditRecordTypes = @(
    $productionReadinessRecovery.external_audit_policy.record_type
    $cryptographicRootRecovery.external_audit_policy.record_type
)
Assert-Contract (-not @(
    $localRecoveryExternalAuditRecordTypes |
        Where-Object { $_ -notin $internalSecurityRecords }
).Count) "local recovery external audit record is absent from the internal registry"

$configurationAuthorization = $contract.configuration_authorization
Assert-Contract (Test-SameSet @($configurationAuthorization.PSObject.Properties.Name) @(
    "policy_id",
    "deny_unclassified_fields",
    "path_syntax",
    "path_match",
    "authorization_mode",
    "atomic_rejection",
    "partial_write_allowed",
    "field_permissions",
    "field_match_modes",
    "fine_report_binding_permissions_all"
)) "configuration authorization schema differs from the frozen contract"
Assert-Contract ($configurationAuthorization.policy_id -ceq "config_draft_spec_fields") "draft field policy ID is incorrect"
Assert-Contract ($configurationAuthorization.deny_unclassified_fields -eq $true) "draft field authorization must deny unclassified fields"
Assert-Contract ($configurationAuthorization.path_syntax -ceq "normalized_RFC6901") "draft field paths must use normalized RFC6901"
Assert-Contract ($configurationAuthorization.path_match -ceq "most_specific_exact_or_declared_subtree") "draft field path matching is not frozen"
Assert-Contract ($configurationAuthorization.authorization_mode -ceq "all_changed_paths_all_permissions") "draft field authorization must require all changed-path permissions"
Assert-Contract ($configurationAuthorization.atomic_rejection -eq $true) "unauthorized draft changes must reject atomically"
Assert-Contract ($configurationAuthorization.partial_write_allowed -eq $false) "partial draft writes must remain forbidden"
$expectedFieldPermissions = @{
    "/welcome_text" = @("config.edit_business")
    "/persona" = @("config.edit_business")
    "/business_policy" = @("config.edit_business")
    "/fvs_binding_ref" = @("config.edit_technical")
    "/fine_report_identity_ref" = @("config.edit_technical", "finereport.binding.manage")
    "/digital_human_instance_id" = @("config.edit_technical")
    "/capability_profile_ref" = @("config.edit_technical")
    "/technical_policy" = @("config.edit_technical")
}
$actualFieldNames = @($configurationAuthorization.field_permissions.PSObject.Properties.Name)
Assert-Contract (Test-SameSet $actualFieldNames @($expectedFieldPermissions.Keys)) "draft field permission map differs from the frozen set"
$actualFieldMatchNames = @($configurationAuthorization.field_match_modes.PSObject.Properties.Name)
Assert-Contract (Test-SameSet $actualFieldMatchNames @($expectedFieldPermissions.Keys)) "draft field match-mode map differs from the frozen set"
foreach ($fieldName in @($expectedFieldPermissions.Keys)) {
    $actualFieldPermissions = @($configurationAuthorization.field_permissions.PSObject.Properties[$fieldName].Value)
    Assert-Contract (Test-ExactSequence $actualFieldPermissions $expectedFieldPermissions[$fieldName]) "draft field $fieldName permissions are incorrect"
    Assert-Contract ($configurationAuthorization.field_match_modes.PSObject.Properties[$fieldName].Value -ceq "exact") "draft field $fieldName must use exact path matching"
}
Assert-Contract (Test-ExactSequence @($configurationAuthorization.fine_report_binding_permissions_all) @("screen.manage", "secret.write", "finereport.binding.manage")) "FineReport binding must require all three frozen permissions"

$resolutionPolicy = $contract.resolution_policy
Assert-Contract (Test-SameSet @($resolutionPolicy.PSObject.Properties.Name) @(
    "fingerprint_algorithm",
    "bound_at",
    "inheritance_layer_entity",
    "inheritance_order",
    "approval_binds",
    "approval_kinds",
    "approval_kind_xor_required",
    "approval_mode_by_environment",
    "production_approval_requires_distinct_active_attested_editor_and_approver_person_ids",
    "development_test_policy_actor_schema",
    "development_test_policy_actor_never_fabricates_human_user_or_person_id",
    "approval_branch_field_rules",
    "production_allows_approval_kind",
    "approval_rechecks_complete_editor_and_approver_identity_role_credential_person_and_eligibility_generations",
    "release_creation_recheck_by_approval_kind",
    "editor_or_approver_person_role_credential_or_eligibility_change_invalidates_approval",
    "release_creation",
    "release_creation_kinds",
    "normal_release_requires",
    "rollback_release_requires",
    "rollback_source_target_map_key",
    "rollback_source_screen_must_equal_destination_screen",
    "rollback_source_map_destination_set_equals_release_target_set",
    "rollback_source_map_destination_unique",
    "rollback_substitution_allowed",
    "rollback_copied_fields_must_match_source",
    "release_creation_branch_xor",
    "revise_copy_only",
    "revise_allowed_from",
    "pending_revise_atomically_withdraws_approval",
    "revise_invalidates_evidence",
    "abandon_allowed_from",
    "abandon_preserves_history",
    "source_change_result",
    "publication_creates_release_targets"
)) "resolution policy schema differs from the frozen contract"
Assert-Contract ($resolutionPolicy.fingerprint_algorithm -ceq "SHA-256") "resolution fingerprint algorithm is incorrect"
Assert-Contract ($resolutionPolicy.bound_at -ceq "validation") "resolution fingerprint must be bound at validation"
Assert-Contract ($resolutionPolicy.inheritance_layer_entity -ceq "ConfigLayerRevision") "resolution inputs must use ConfigLayerRevision"
Assert-Contract (Test-ExactSequence @($resolutionPolicy.inheritance_order) @("product_default", "tenant", "deployment", "site", "screen_group", "screen_instance")) "configuration inheritance order drifted"
Assert-Contract (Test-ExactSequence @($resolutionPolicy.approval_binds) @(
    "approval_kind",
    "draft_revision_id",
    "draft_content_hash",
    "resolution_fingerprint_hash",
    "target_set_hash",
    "group_resource_revision",
    "inheritance_layer_revisions",
    "per_screen_effective_content_hashes",
    "fine_report_binding_versions",
    "secret_versions",
    "control_plane_epoch",
    "last_editor_user_id",
    "last_editor_person_id",
    "last_editor_person_registry_generation",
    "last_editor_person_binding_generation",
    "last_editor_user_account_state_generation",
    "last_editor_authentication_epoch",
    "last_editor_authorization_epoch",
    "last_editor_role_scope_assignment_generation",
    "last_editor_credential_generation",
    "last_editor_person_eligibility_generation",
    "approver_user_id",
    "approver_person_id",
    "approver_person_registry_generation",
    "approver_person_binding_generation",
    "approver_user_account_state_generation",
    "approver_authentication_epoch",
    "approver_authorization_epoch",
    "approver_role_scope_assignment_generation",
    "approver_credential_generation",
    "approver_person_eligibility_generation",
    "policy_actor_id",
    "policy_version",
    "policy_environment",
    "policy_immutable_input_hash",
    "policy_decision",
    "policy_reason",
    "policy_audit_event_id"
)) "approval does not bind the exact frozen resolution facts"
Assert-Contract (Test-ExactSequence @($resolutionPolicy.approval_kinds) @("HUMAN", "TYPED_POLICY_ACTOR")) "configuration approval kind registry drifted"
Assert-Contract ($resolutionPolicy.approval_kind_xor_required -eq $true) "configuration approval branches must be mutually exclusive"
Assert-Contract ($resolutionPolicy.production_allows_approval_kind -ceq "HUMAN") "production configuration approval must remain human"
Assert-Contract ($resolutionPolicy.production_approval_requires_distinct_active_attested_editor_and_approver_person_ids -eq $true) "production configuration approval requires independent attested people"
Assert-Contract ($resolutionPolicy.development_test_policy_actor_never_fabricates_human_user_or_person_id -eq $true) "typed policy approval must not fabricate a human identity"
Assert-Contract (Test-ExactSequence @($resolutionPolicy.development_test_policy_actor_schema) @(
    "policy_actor_id",
    "policy_version",
    "policy_environment",
    "policy_immutable_input_hash",
    "policy_decision",
    "policy_reason",
    "policy_audit_event_id"
)) "typed policy actor schema drifted"
Assert-Contract ($resolutionPolicy.approval_branch_field_rules.HUMAN -ceq "EDITOR_AND_APPROVER_USER_PERSON_GENERATION_FIELDS_REQUIRED_POLICY_ACTOR_FIELDS_NULL") "human approval branch nullability drifted"
Assert-Contract ($resolutionPolicy.approval_branch_field_rules.TYPED_POLICY_ACTOR -ceq "POLICY_ACTOR_FIELDS_REQUIRED_APPROVER_USER_PERSON_FIELDS_NULL_EDITOR_FIELDS_AND_IMMUTABLE_INPUT_RETAINED") "typed policy approval branch nullability drifted"
Assert-Contract ($resolutionPolicy.release_creation -ceq "kind_discriminated_atomic_release_and_targets") "release creation must use the frozen kind-discriminated atomic path"
Assert-Contract (Test-ExactSequence @($resolutionPolicy.release_creation_kinds) @("NORMAL", "ROLLBACK")) "release creation kinds drifted"
Assert-Contract (Test-ExactSequence @($resolutionPolicy.normal_release_requires) @(
    "approved_draft_revision",
    "revalidated_resolution_fingerprint",
    "approval_record",
    "atomic_release_targets"
)) "normal release provenance requirements drifted"
Assert-Contract (Test-ExactSequence @($resolutionPolicy.rollback_release_requires) @(
    "immutable_source_release_target_map",
    "target_set_hash",
    "exact_asset_binding_and_secret_versions",
    "approved_high_risk_action",
    "atomic_release_targets"
)) "rollback release provenance requirements drifted"
Assert-Contract (Test-ExactSequence @($resolutionPolicy.rollback_source_target_map_key) @(
    "tenant_id",
    "deployment_id",
    "source_release_id",
    "source_screen_id",
    "source_release_target_id",
    "destination_screen_id"
)) "rollback source-target map key is incomplete"
Assert-Contract ($resolutionPolicy.rollback_source_screen_must_equal_destination_screen -eq $true) "rollback source screen must equal destination screen"
Assert-Contract ($resolutionPolicy.rollback_source_map_destination_set_equals_release_target_set -eq $true) "rollback source-map destinations must equal the new release target set"
Assert-Contract ($resolutionPolicy.rollback_source_map_destination_unique -eq $true) "rollback source-map destinations must be unique"
Assert-Contract ($resolutionPolicy.rollback_substitution_allowed -eq $false) "rollback must not substitute content or versions"
Assert-Contract (Test-ExactSequence @($resolutionPolicy.rollback_copied_fields_must_match_source) @(
    "canonical_effective_content",
    "content_hash",
    "asset_versions",
    "fine_report_binding_version",
    "secret_versions"
)) "rollback copied-field equality set drifted"
Assert-Contract ($resolutionPolicy.release_creation_branch_xor -eq $true) "normal and rollback release provenance must be mutually exclusive"
Assert-Contract ($resolutionPolicy.revise_copy_only -eq $true) "reviseConfigDraft must create a copy-only revision before field edits"
Assert-Contract (Test-ExactSequence @($resolutionPolicy.revise_allowed_from) @(
    "VALIDATED",
    "PREVIEWED",
    "APPROVAL_PENDING",
    "REJECTED",
    "APPROVED_WHEN_RESOLUTION_FINGERPRINT_OR_CONTROL_PLANE_EPOCH_STALE"
)) "draft revision source-state set drifted"
Assert-Contract ($resolutionPolicy.pending_revise_atomically_withdraws_approval -eq $true) "pending draft revision must atomically withdraw pending approval"
Assert-Contract (Test-ExactSequence @($resolutionPolicy.revise_invalidates_evidence) @("validation", "preview", "approval")) "draft revision must invalidate prior evidence"
Assert-Contract (Test-ExactSequence @($resolutionPolicy.abandon_allowed_from) @("DRAFT", "VALIDATED", "PREVIEWED", "REJECTED")) "draft abandon source-state set drifted"
Assert-Contract ($resolutionPolicy.abandon_preserves_history -eq $true) "abandon must preserve draft history"
Assert-Contract ($resolutionPolicy.source_change_result -ceq "RESOLUTION_FINGERPRINT_STALE") "stale resolution must have its own stable error"
Assert-Contract ($resolutionPolicy.publication_creates_release_targets -eq $false) "Publication must never create ReleaseTargets"

$dataIntegrity = $contract.data_integrity
Assert-Contract (Test-SameSet @($dataIntegrity.PSObject.Properties.Name) @(
    "immutable_api_resources",
    "publication_target_composite_foreign_key",
    "publication_target_references_release_target_key",
    "publication_target_references_publication_key"
)) "data-integrity policy schema differs from the frozen contract"
Assert-Contract (Test-ExactSequence @($dataIntegrity.immutable_api_resources) @(
    "ConfigRelease",
    "ReleaseTarget",
    "ConfigLayerRevision",
    "FineReportIdentityBindingVersion",
    "SecretVersion",
    "ResolutionFingerprint",
    "SecurityAuditEvent"
)) "immutable API resource registry drifted"
$publicationTargetKey = @("tenant_id", "deployment_id", "release_id", "screen_id", "release_target_id")
Assert-Contract (Test-ExactSequence @($dataIntegrity.publication_target_composite_foreign_key) $publicationTargetKey) "PublicationTarget composite foreign key is incomplete"
Assert-Contract (Test-ExactSequence @($dataIntegrity.publication_target_references_release_target_key) $publicationTargetKey) "ReleaseTarget composite key does not match PublicationTarget"
Assert-Contract (Test-ExactSequence @($dataIntegrity.publication_target_references_publication_key) @("tenant_id", "deployment_id", "publication_id", "release_id")) "PublicationTarget does not prove Publication release ownership"

$highRiskPolicy = $contract.high_risk_policy
Assert-Contract (Test-SameSet @($highRiskPolicy.PSObject.Properties.Name) @(
    "standard_production_policy_id",
    "approval_ttl_minutes",
    "request_hash_algorithm",
    "request_hash_purpose_domain",
    "request_canonicalization",
    "request_hash_domain_separator",
    "duplicate_json_members_or_non_finite_numbers_result",
    "request_hash_key_outside_live_store_logs_and_backups",
    "request_hash_key_id_stored_with_action",
    "execution_uses_action_bound_request_hash_key_id",
    "request_hash_key_retention_policy",
    "request_hash_key_temporarily_unavailable_result",
    "request_hash_key_revoked_or_permanently_lost_result",
    "recent_reauthentication_minutes",
    "reason_required",
    "initiator_must_differ_from_approver",
    "single_use",
    "production_requires_human_approval",
    "generic_action_creation_forbidden",
    "protected_endpoint_creates_typed_action",
    "request_accepts_only_allowlisted_typed_operation_schemas",
    "request_requires_target_operation_authorization",
    "approver_requires_risk_approve_and_target_operation_authorization",
    "execution_rechecks_initiator_and_approver_target_authorization",
    "approval_only_records_evidence",
    "execution_requires_protected_endpoint_resubmission",
    "execution_header",
    "execution_caller_must_be_initiator",
    "execution_requires_recent_reauthentication",
    "execution_reauthentication_minutes",
    "execution_stale_reauthentication_result",
    "approver_reauthentication_checked_at_approval",
    "approval_queues_execution",
    "direct_permission_async_policy",
    "authorization_commit_semantics_by_kind",
    "synchronous_commit_unit",
    "asynchronous_commit_unit",
    "asynchronous_frozen_intent_required",
    "async_worker_reparses_mutable_request_state",
    "async_common_commit_records",
    "async_operation_schema",
    "idempotency_record_schema",
    "network_execution_security_audit_authorization_schema",
    "async_authorization_commit_records_by_kind",
    "disaster_authorization_final_consumption_at_cutover_anchor",
    "disaster_pre_pointer_abort_keeps_external_nonce_terminally_consumed",
    "execution_authorization_reference_schema",
    "execution_authorization_reference_by_kind",
    "execution_actor_nullability_by_kind",
    "execution_authorization_reference_exactly_one_id",
    "execution_evidence_records_bind_same_authorization_reference",
    "high_risk_action_identity_schema",
    "high_risk_approval_identity_schema",
    "execution_requires_different_active_attested_person_ids",
    "execution_rechecks_both_identity_role_credential_and_eligibility_generations",
    "immutable_typed_command_schema",
    "immutable_typed_command_append_only",
    "outbox_record_schema",
    "execution_idempotency_scope",
    "execution_idempotency_phase_distinct_from_request",
    "crash_before_atomic_commit_result",
    "non_ledger_crash_after_atomic_commit_result",
    "ledger_backed_execution_success_requires_committed_anchor",
    "ledger_prepared_retry_result",
    "ledger_reconciliation_unavailable_result",
    "stored_request_body_policy",
    "request_hash_binds",
    "request_hash_binds_initiator_user_person_registry_role_credential_and_eligibility_generations",
    "affected_privileged_identity_role_or_credential_change_fails_pending_or_approved_action",
    "operational_fence_or_readiness_snapshot_change_fails_pending_or_approved_action",
    "development_test_auto_approval_allowed",
    "protected_operations"
)) "high-risk policy schema differs from the frozen contract"
Assert-Contract ($highRiskPolicy.standard_production_policy_id -ceq "production_four_eyes_v1") "production high-risk policy ID is incorrect"
Assert-Contract ($highRiskPolicy.approval_ttl_minutes -eq 15) "high-risk approval TTL must be 15 minutes"
Assert-Contract ($highRiskPolicy.request_hash_algorithm -ceq "HMAC-SHA-256") "high-risk request hash must use keyed HMAC-SHA-256"
Assert-Contract ($highRiskPolicy.request_hash_purpose_domain -ceq "HIGH_RISK_REQUEST_HMAC") "high-risk request HMAC purpose domain drifted"
Assert-Contract ($highRiskPolicy.request_canonicalization -ceq "RFC8785_JCS_AFTER_STRICT_TYPED_PARSE") "high-risk request canonicalization drifted"
Assert-Contract ($highRiskPolicy.request_hash_domain_separator -ceq "shuziren:p1:high-risk-action:v1") "high-risk request HMAC domain separator drifted"
Assert-Contract ($highRiskPolicy.duplicate_json_members_or_non_finite_numbers_result -ceq "INVALID_REQUEST") "ambiguous high-risk JSON must be rejected"
Assert-Contract ($highRiskPolicy.request_hash_key_outside_live_store_logs_and_backups -eq $true) "high-risk request hash key must remain outside live storage, logs and backups"
Assert-Contract ($highRiskPolicy.request_hash_key_id_stored_with_action -eq $true) "HighRiskAction must store its non-secret request HMAC key ID"
Assert-Contract ($highRiskPolicy.execution_uses_action_bound_request_hash_key_id -eq $true) "high-risk execution must verify with the action-bound HMAC key ID"
Assert-Contract ($highRiskPolicy.request_hash_key_retention_policy -ceq "UNTIL_LAST_REFERENCING_ACTION_TERMINAL_AND_EVIDENCE_RETENTION_EXPIRES") "high-risk request HMAC key retention is not frozen"
Assert-Contract (
    ($highRiskPolicy.request_hash_key_temporarily_unavailable_result.error_code -ceq "KEY_SERVICE_UNAVAILABLE") -and
    ($highRiskPolicy.request_hash_key_temporarily_unavailable_result.state_effect -ceq "ACTION_UNCHANGED") -and
    ($highRiskPolicy.request_hash_key_temporarily_unavailable_result.retryable -eq $true) -and
    ($highRiskPolicy.request_hash_key_revoked_or_permanently_lost_result.error_code -ceq "REQUEST_DIGEST_KEY_EPOCH_CHANGED") -and
    ($highRiskPolicy.request_hash_key_revoked_or_permanently_lost_result.state_effect -ceq "ACTION_FAILED") -and
    ($highRiskPolicy.request_hash_key_revoked_or_permanently_lost_result.retryable -eq $false)
) "missing action-bound request HMAC key must fail closed with the stable error"
Assert-Contract ($highRiskPolicy.recent_reauthentication_minutes -eq 10) "high-risk reauthentication window must be 10 minutes"
foreach ($trueField in @(
    "reason_required",
    "initiator_must_differ_from_approver",
    "single_use",
    "production_requires_human_approval",
    "generic_action_creation_forbidden",
    "protected_endpoint_creates_typed_action",
    "request_accepts_only_allowlisted_typed_operation_schemas",
    "request_requires_target_operation_authorization",
    "approver_requires_risk_approve_and_target_operation_authorization",
    "execution_rechecks_initiator_and_approver_target_authorization",
    "approval_only_records_evidence",
    "execution_requires_protected_endpoint_resubmission",
    "execution_caller_must_be_initiator",
    "execution_requires_recent_reauthentication",
    "approver_reauthentication_checked_at_approval",
    "asynchronous_frozen_intent_required",
    "execution_authorization_reference_exactly_one_id",
    "execution_evidence_records_bind_same_authorization_reference",
    "disaster_authorization_final_consumption_at_cutover_anchor",
    "disaster_pre_pointer_abort_keeps_external_nonce_terminally_consumed",
    "execution_requires_different_active_attested_person_ids",
    "execution_rechecks_both_identity_role_credential_and_eligibility_generations",
    "immutable_typed_command_append_only",
    "execution_idempotency_phase_distinct_from_request",
    "ledger_backed_execution_success_requires_committed_anchor",
    "request_hash_binds_initiator_user_person_registry_role_credential_and_eligibility_generations",
    "affected_privileged_identity_role_or_credential_change_fails_pending_or_approved_action",
    "operational_fence_or_readiness_snapshot_change_fails_pending_or_approved_action"
)) {
    Assert-Contract ($highRiskPolicy.$trueField -eq $true) "high-risk policy $trueField must remain true"
}
Assert-Contract ($highRiskPolicy.execution_header -ceq "High-Risk-Action-ID") "high-risk execution header is not frozen"
Assert-Contract ($highRiskPolicy.execution_reauthentication_minutes -eq 10) "high-risk execution reauthentication window must be 10 minutes"
Assert-Contract (
    ($highRiskPolicy.execution_stale_reauthentication_result.error_code -ceq "RECENT_REAUTHENTICATION_REQUIRED") -and
    ($highRiskPolicy.execution_stale_reauthentication_result.state_effect -ceq "ACTION_REMAINS_APPROVED_UNTIL_TTL") -and
    ($highRiskPolicy.execution_stale_reauthentication_result.retryable -eq $false)
) "stale execution reauthentication must preserve the approved action only until its TTL"
Assert-Contract ($highRiskPolicy.approval_queues_execution -eq $false) "high-risk approval must not enqueue execution"
$directPermissionPolicy = $highRiskPolicy.direct_permission_async_policy
Assert-Contract (Test-ExactSequence @($directPermissionPolicy.PSObject.Properties.Name) @(
    "authorization_kind",
    "allowed_operation_ids",
    "record_schema",
    "precondition_fields_by_operation",
    "request_hash_algorithm",
    "request_hash_purpose_domain",
    "request_hash_domain_separator",
    "authorization_and_scope_rechecked_immediately_before_atomic_enqueue",
    "initiator_user_person_session_role_scope_credential_and_eligibility_generations_frozen_and_rechecked",
    "created_atomically_with_typed_command_frozen_intent_operation_outbox_idempotency_and_audit",
    "direct_authorization_id_single_use_for_exact_command",
    "approver_fields_must_be_null",
    "cannot_authorize_high_risk_restore_or_local_maintenance_operation",
    "worker_uses_only_frozen_intent_and_never_reauthorizes_from_mutable_state",
    "crash_before_atomic_enqueue_has_no_operation_or_effect",
    "crash_after_atomic_enqueue_reuses_stored_operation_and_never_repeats_enqueue"
)) "direct-permission async policy schema drifted"
Assert-Contract ($directPermissionPolicy.authorization_kind -ceq "DIRECT_PERMISSION") "direct async authorization kind drifted"
Assert-Contract (Test-ExactSequence @($directPermissionPolicy.allowed_operation_ids) @("createBackup", "verifyBackup")) "direct async authorization operation set drifted"
Assert-Contract (Test-ExactSequence @($directPermissionPolicy.record_schema) @(
    "direct_operation_authorization_id",
    "operation_id",
    "tenant_id",
    "deployment_id",
    "initiator_user_id",
    "initiator_person_id",
    "initiator_person_registry_generation",
    "initiator_person_binding_generation",
    "initiator_user_account_state_generation",
    "initiator_authentication_epoch",
    "initiator_authorization_epoch",
    "initiator_role_scope_assignment_generation",
    "initiator_credential_generation",
    "initiator_eligibility_generation",
    "auth_session_id",
    "required_permission",
    "resource_scope",
    "storage_epoch",
    "backup_id",
    "backup_hash",
    "http_method",
    "canonical_path",
    "request_hmac",
    "request_hmac_key_id",
    "idempotency_key_digest",
    "exact_command_hash",
    "created_at"
)) "direct operation authorization record schema drifted"
Assert-Contract (Test-ExactSequence @($directPermissionPolicy.precondition_fields_by_operation.PSObject.Properties.Name) @("createBackup", "verifyBackup")) "direct async precondition branch set drifted"
Assert-Contract (Test-ExactSequence @($directPermissionPolicy.precondition_fields_by_operation.createBackup.required) @("storage_epoch")) "createBackup direct authorization preconditions drifted"
Assert-Contract (Test-ExactSequence @($directPermissionPolicy.precondition_fields_by_operation.createBackup.must_be_null) @("backup_id", "backup_hash")) "createBackup direct authorization nullability drifted"
Assert-Contract (Test-ExactSequence @($directPermissionPolicy.precondition_fields_by_operation.verifyBackup.required) @("backup_id", "backup_hash")) "verifyBackup direct authorization preconditions drifted"
Assert-Contract (Test-ExactSequence @($directPermissionPolicy.precondition_fields_by_operation.verifyBackup.must_be_null) @("storage_epoch")) "verifyBackup direct authorization nullability drifted"
Assert-Contract ($directPermissionPolicy.request_hash_algorithm -ceq "HMAC-SHA-256") "direct async request digest must use HMAC-SHA-256"
Assert-Contract ($directPermissionPolicy.request_hash_purpose_domain -ceq "SENSITIVE_REQUEST_DIGEST_HMAC") "direct async request digest purpose drifted"
Assert-Contract ($directPermissionPolicy.request_hash_domain_separator -ceq "shuziren:p1:direct-operation-authorization:v1") "direct async request digest domain separator drifted"
foreach ($trueField in @(
    "authorization_and_scope_rechecked_immediately_before_atomic_enqueue",
    "initiator_user_person_session_role_scope_credential_and_eligibility_generations_frozen_and_rechecked",
    "created_atomically_with_typed_command_frozen_intent_operation_outbox_idempotency_and_audit",
    "direct_authorization_id_single_use_for_exact_command",
    "approver_fields_must_be_null",
    "cannot_authorize_high_risk_restore_or_local_maintenance_operation",
    "worker_uses_only_frozen_intent_and_never_reauthorizes_from_mutable_state",
    "crash_before_atomic_enqueue_has_no_operation_or_effect",
    "crash_after_atomic_enqueue_reuses_stored_operation_and_never_repeats_enqueue"
)) {
    Assert-Contract ($directPermissionPolicy.$trueField -eq $true) "direct async authorization $trueField must remain true"
}
Assert-Contract (
    ($highRiskPolicy.authorization_commit_semantics_by_kind.STANDARD_HIGH_RISK -ceq "CONSUME_ACTION_WITH_SYNC_EFFECT_OR_ASYNC_ENQUEUE_IN_ONE_DATABASE_TRANSACTION") -and
    ($highRiskPolicy.authorization_commit_semantics_by_kind.DISASTER_CUSTODIAN -ceq "RESERVE_EXTERNAL_NONCE_AND_PROVISIONAL_GRANTS_BEFORE_STAGED_ENQUEUE_FINAL_CONSUMPTION_COMMITS_ONLY_WITH_CUTOVER_ANCHOR") -and
    ($highRiskPolicy.authorization_commit_semantics_by_kind.DIRECT_PERMISSION -ceq "AUTHORIZE_EXACT_TYPED_REQUEST_AND_CREATE_IMMUTABLE_AUTHORIZATION_WITH_ASYNC_ENQUEUE_IN_ONE_DATABASE_TRANSACTION")
) "high-risk policy consume_and_effect_atomic must remain true"
Assert-Contract ($highRiskPolicy.development_test_auto_approval_allowed -eq $false) "high-risk policy development_test_auto_approval_requires_explicit_audit_policy must remain true"
Assert-Contract ($highRiskPolicy.synchronous_commit_unit -ceq "action_consumption_domain_effect_audit_and_idempotent_result") "synchronous high-risk execution commit unit is not frozen"
Assert-Contract ($highRiskPolicy.asynchronous_commit_unit -ceq "authorization_evidence_creation_or_consumption_typed_command_frozen_plan_domain_intent_operation_and_outbox_enqueue") "asynchronous execution commit unit is not frozen"
Assert-Contract ($highRiskPolicy.async_worker_reparses_mutable_request_state -eq $false) "asynchronous workers must not reparse mutable request state"
Assert-Contract (Test-ExactSequence @($highRiskPolicy.async_common_commit_records) @(
    "ImmutableTypedCommand",
    "FrozenPlanOrDomainIntent",
    "AsyncOperation",
    "OutboxRecord",
    "SecurityAuditEvent",
    "IdempotencyRecord"
)) "asynchronous high-risk execution record set drifted"
Assert-Contract (
    (Test-ExactSequence @($highRiskPolicy.async_authorization_commit_records_by_kind.STANDARD_HIGH_RISK) @("HighRiskActionConsumption")) -and
    (Test-ExactSequence @($highRiskPolicy.async_authorization_commit_records_by_kind.DISASTER_CUSTODIAN) @("ExternalDisasterEnvelopeNonceReservation", "RecoveryPasswordSetupGrantProvisionalReservation")) -and
    (Test-ExactSequence @($highRiskPolicy.async_authorization_commit_records_by_kind.DIRECT_PERMISSION) @("DirectOperationAuthorizationCreation"))
) "asynchronous authorization record set drifted"
Assert-Contract (Test-ExactSequence @($highRiskPolicy.async_operation_schema) @(
    "operation_id",
    "kind",
    "authorization_kind",
    "direct_operation_authorization_id",
    "high_risk_action_id",
    "disaster_recovery_authorization_envelope_id",
    "immutable_typed_command_id",
    "initiator_user_id",
    "initiator_person_id",
    "approver_user_id",
    "approver_person_id",
    "state",
    "progress",
    "safe_failure_code",
    "created_at",
    "updated_at"
)) "async operation authorization schema drifted"
Assert-Contract (Test-ExactSequence @($highRiskPolicy.idempotency_record_schema) @(
    "principal_id",
    "phase",
    "scope",
    "method",
    "canonical_route",
    "idempotency_key_digest",
    "sensitive_request_digest",
    "sensitive_digest_key_id",
    "authorization_kind",
    "direct_operation_authorization_id",
    "high_risk_action_id",
    "disaster_recovery_authorization_envelope_id",
    "exact_command_hash",
    "result_reference",
    "expires_at"
)) "idempotency authorization schema drifted"
Assert-Contract (Test-ExactSequence @($highRiskPolicy.network_execution_security_audit_authorization_schema) @(
    "event_id",
    "actor_kind",
    "actor_user_id",
    "actor_person_id",
    "authorization_kind",
    "direct_operation_authorization_id",
    "high_risk_action_id",
    "disaster_recovery_authorization_envelope_id",
    "action",
    "resource",
    "result",
    "reason",
    "request_id",
    "previous_hash",
    "event_hash"
)) "network execution security-audit authorization schema drifted"
Assert-Contract (Test-ExactSequence @($highRiskPolicy.execution_authorization_reference_schema) @(
    "authorization_kind",
    "direct_operation_authorization_id",
    "high_risk_action_id",
    "disaster_recovery_authorization_envelope_id"
)) "execution authorization reference schema drifted"
Assert-Contract (Test-ExactSequence @($highRiskPolicy.execution_authorization_reference_by_kind.PSObject.Properties.Name) @(
    "DIRECT_PERMISSION",
    "STANDARD_HIGH_RISK",
    "DISASTER_CUSTODIAN"
)) "execution authorization branch set drifted"
Assert-Contract (
    ($highRiskPolicy.execution_authorization_reference_by_kind.DIRECT_PERMISSION -ceq "direct_operation_authorization_id_required_high_risk_action_id_and_disaster_recovery_authorization_envelope_id_null") -and
    ($highRiskPolicy.execution_authorization_reference_by_kind.STANDARD_HIGH_RISK -ceq "high_risk_action_id_required_direct_operation_authorization_id_and_disaster_recovery_authorization_envelope_id_null") -and
    ($highRiskPolicy.execution_authorization_reference_by_kind.DISASTER_CUSTODIAN -ceq "disaster_recovery_authorization_envelope_id_required_direct_operation_authorization_id_and_high_risk_action_id_null")
) "execution authorization ID nullability drifted"
Assert-Contract (Test-ExactSequence @($highRiskPolicy.execution_actor_nullability_by_kind.PSObject.Properties.Name) @(
    "DIRECT_PERMISSION",
    "STANDARD_HIGH_RISK",
    "DISASTER_CUSTODIAN"
)) "execution actor branch set drifted"
Assert-Contract (
    ($highRiskPolicy.execution_actor_nullability_by_kind.DIRECT_PERMISSION -ceq "initiator_user_person_and_all_identity_generation_fields_required_approver_user_person_and_all_identity_generation_fields_null") -and
    ($highRiskPolicy.execution_actor_nullability_by_kind.STANDARD_HIGH_RISK -ceq "initiator_and_approver_user_person_and_all_identity_generation_fields_required") -and
    ($highRiskPolicy.execution_actor_nullability_by_kind.DISASTER_CUSTODIAN -ceq "initiator_and_approver_user_person_and_all_identity_generation_fields_null_local_custodian_actor_evidence_only")
) "execution actor nullability drifted"
Assert-Contract (Test-ExactSequence @($highRiskPolicy.immutable_typed_command_schema) @(
    "command_id",
    "authorization_kind",
    "direct_operation_authorization_id",
    "high_risk_action_id",
    "disaster_recovery_authorization_envelope_id",
    "initiator_user_id",
    "initiator_person_id",
    "initiator_person_registry_generation",
    "initiator_person_binding_generation",
    "initiator_user_account_state_generation",
    "initiator_authentication_epoch",
    "initiator_authorization_epoch",
    "initiator_role_scope_assignment_generation",
    "initiator_credential_generation",
    "initiator_eligibility_generation",
    "approver_user_id",
    "approver_person_id",
    "approver_person_registry_generation",
    "approver_person_binding_generation",
    "approver_user_account_state_generation",
    "approver_authentication_epoch",
    "approver_authorization_epoch",
    "approver_role_scope_assignment_generation",
    "approver_credential_generation",
    "approver_eligibility_generation",
    "operational_fence_generation",
    "readiness_snapshot_hash",
    "operation_id",
    "request_hmac",
    "request_hmac_key_id",
    "canonical_non_secret_parameters",
    "secret_parameter_references_only",
    "target_revisions_and_generations",
    "frozen_plan_or_domain_intent_id",
    "created_at"
)) "immutable typed command schema drifted"
Assert-Contract (Test-ExactSequence @($highRiskPolicy.outbox_record_schema) @(
    "outbox_id",
    "operation_id",
    "command_id",
    "authorization_kind",
    "direct_operation_authorization_id",
    "high_risk_action_id",
    "disaster_recovery_authorization_envelope_id",
    "event_type",
    "payload_hash",
    "state",
    "attempt_count",
    "not_before",
    "created_at"
)) "outbox record schema drifted"
Assert-Contract ($highRiskPolicy.execution_idempotency_scope -ceq "phase_and_authorization_kind_and_evidence_id_and_exact_command") "high-risk execution idempotency scope is not frozen"
Assert-Contract ($highRiskPolicy.crash_before_atomic_commit_result -ceq "NO_DOMAIN_EFFECT_ACTION_REMAINS_APPROVED") "high-risk pre-commit crash result is unsafe"
Assert-Contract ($highRiskPolicy.non_ledger_crash_after_atomic_commit_result -ceq "IDEMPOTENT_PRIOR_RESULT_ACTION_CONSUMED") "non-ledger high-risk post-commit crash result is unsafe"
Assert-Contract ($highRiskPolicy.ledger_prepared_retry_result -ceq "RECONCILE_DOMAIN_COMMIT_AND_ANCHOR_BEFORE_RETURNING_SUCCESS") "ledger-backed retry must reconcile the anchor before success"
Assert-Contract ($highRiskPolicy.ledger_reconciliation_unavailable_result -ceq "SECURITY_LEDGER_RECONCILIATION_REQUIRED") "unavailable ledger reconciliation must fail closed"
Assert-Contract ($highRiskPolicy.stored_request_body_policy -ceq "KEYED_HMAC_ONLY_NO_SECRET_BODY") "high-risk evidence must not persist a Secret-bearing request body or bare digest"
$expectedRequestHashBindings = @(
    "http_method",
    "canonical_path",
    "tenant_id",
    "deployment_id",
    "requester_user_id",
    "initiator_person_id",
    "initiator_person_registry_generation",
    "initiator_person_binding_generation",
    "initiator_user_account_state_generation",
    "initiator_authentication_epoch",
    "initiator_authorization_epoch",
    "initiator_role_scope_assignment_generation",
    "initiator_credential_generation",
    "initiator_eligibility_generation",
    "resource_ids",
    "canonical_body",
    "if_match",
    "expected_generations",
    "reason",
    "policy_version",
    "control_plane_epoch",
    "operational_fence_generation",
    "readiness_snapshot_hash",
    "recovery_security_ledger_head"
)
Assert-Contract (Test-ExactSequence @($highRiskPolicy.request_hash_binds) $expectedRequestHashBindings) "high-risk request hash bindings are incomplete"
$expectedProtectedOperations = @(
    "activateDeploymentProduction",
    "createUser",
    "updateUser",
    "disableUser",
    "enableUser",
    "unlockUser",
    "issuePasswordReset",
    "revokeUserAuthSession",
    "replaceUserRoles",
    "publishToScreen",
    "publishToScreenGroup",
    "rollbackScreen",
    "rollbackScreenGroup",
    "issueDeviceEnrollment",
    "revokeDeviceEnrollment",
    "revokeDeviceCredential",
    "createSecret",
    "rotateSecret",
    "putFineReportIdentityBinding",
    "executeRestorePlan"
)
Assert-Contract (Test-ExactSequence @($highRiskPolicy.protected_operations) $expectedProtectedOperations) "production four-eyes operation set drifted"
$allAsyncOperationIds = @(
    $contract.api.operations |
        Where-Object { $_.async -eq $true } |
        ForEach-Object { [string]$_.operation_id }
)
$directAsyncOperationIds = @($directPermissionPolicy.allowed_operation_ids | ForEach-Object { [string]$_ })
$protectedAsyncOperationIds = @(
    $contract.api.operations |
        Where-Object { $_.async -eq $true -and $_.operation_id -in $expectedProtectedOperations } |
        ForEach-Object { [string]$_.operation_id }
)
Assert-Contract (-not @($directAsyncOperationIds | Where-Object { $_ -in $expectedProtectedOperations }).Count) "direct async operations must not overlap production four-eyes operations"
Assert-Contract (Test-SameSet $allAsyncOperationIds @($directAsyncOperationIds + $protectedAsyncOperationIds)) "async operation registry is not completely covered by direct-permission or protected authorization"
Assert-Contract (Test-SameSet @($allAsyncOperationIds | Where-Object { $_ -notin $directAsyncOperationIds }) $protectedAsyncOperationIds) "non-direct async operations must be exactly the protected async set"
foreach ($operationId in $directAsyncOperationIds) {
    $directOperation = $contract.api.operations | Where-Object { $_.operation_id -ceq $operationId }
    Assert-Contract ($null -ne $directOperation -and $directOperation.async -eq $true) "direct async operation $operationId must exist and remain asynchronous"
    Assert-Contract ("high_risk_policy" -notin @($directOperation.PSObject.Properties.Name)) "direct async operation $operationId must not carry a production four-eyes marker"
}

Assert-Contract (Test-SameSet @($contract.iam_policy.PSObject.Properties.Name) @(
    "password_min_code_points",
    "password_max_code_points",
    "password_composition_required",
    "periodic_password_change_required",
    "bootstrap_secret",
    "password_hash",
    "lockout",
    "session",
    "browser_session_security",
    "reset_token",
    "recovery_password_setup_grant_policy",
    "human_operator_independence",
    "disaster_recovery_authorization",
    "authorization_scope"
)) "IAM policy schema differs from the frozen contract"
Assert-Contract ($contract.iam_policy.password_min_code_points -eq 15) "password minimum must be 15 code points"
Assert-Contract ($contract.iam_policy.password_max_code_points -eq 128) "password maximum must be 128 code points"
Assert-Contract ($contract.iam_policy.password_composition_required -eq $false) "password composition rules must remain disabled"
Assert-Contract ($contract.iam_policy.periodic_password_change_required -eq $false) "periodic password changes must remain disabled"
Assert-Contract (Test-SameSet @($contract.iam_policy.bootstrap_secret.PSObject.Properties.Name) @(
    "entropy_bits_min",
    "ttl_minutes",
    "single_use",
    "stored_as_digest",
    "verifier_algorithm",
    "verifier_key_id_stored",
    "grant_issued_only_by_local_setup_ceremony",
    "grant_binding_schema",
    "first_person_attestation_and_user_binding_require_two_distinct_current_custodian_signatures",
    "first_user_id_is_server_reserved_before_attestation_and_not_client_selected",
    "target_possession_proof_is_bound_before_first_password_commit",
    "complete_bootstrap_rechecks_current_person_binding_eligibility_key_and_registry_generations",
    "complete_bootstrap_atomically_creates_exact_bound_first_platform_admin_and_invalidates_other_grants",
    "complete_bootstrap_cannot_substitute_person_user_role_or_target_channel"
)) "bootstrap-secret policy schema drifted"
Assert-Contract ($contract.iam_policy.bootstrap_secret.entropy_bits_min -eq 256) "bootstrap secret entropy must be exactly 256 bits"
Assert-Contract ($contract.iam_policy.bootstrap_secret.ttl_minutes -eq 30) "bootstrap secret TTL must be 30 minutes"
Assert-Contract ($contract.iam_policy.bootstrap_secret.single_use -eq $true) "bootstrap secret must be single use"
Assert-Contract ($contract.iam_policy.bootstrap_secret.stored_as_digest -eq $true) "bootstrap secret must be digest stored"
Assert-Contract ($contract.iam_policy.bootstrap_secret.verifier_algorithm -ceq "HMAC-SHA-256") "bootstrap secret verifier must use HMAC-SHA-256"
Assert-Contract ($contract.iam_policy.bootstrap_secret.verifier_key_id_stored -eq $true) "bootstrap secret must bind a verifier key ID"
foreach ($trueField in @(
    "grant_issued_only_by_local_setup_ceremony",
    "first_person_attestation_and_user_binding_require_two_distinct_current_custodian_signatures",
    "first_user_id_is_server_reserved_before_attestation_and_not_client_selected",
    "target_possession_proof_is_bound_before_first_password_commit",
    "complete_bootstrap_rechecks_current_person_binding_eligibility_key_and_registry_generations",
    "complete_bootstrap_atomically_creates_exact_bound_first_platform_admin_and_invalidates_other_grants",
    "complete_bootstrap_cannot_substitute_person_user_role_or_target_channel"
)) {
    Assert-Contract ($contract.iam_policy.bootstrap_secret.$trueField -eq $true) "bootstrap identity binding $trueField must remain true"
}
Assert-Contract (Test-ExactSequence @($contract.iam_policy.bootstrap_secret.grant_binding_schema) @(
    "grant_id",
    "deployment_id",
    "server_reserved_first_user_id",
    "first_person_id",
    "first_person_attestation_hash",
    "first_user_binding_hash",
    "target_channel_event_id",
    "target_possession_challenge_hash",
    "expected_first_credential_generation",
    "person_registry_generation",
    "custodian_registry_generation",
    "verifier_hmac",
    "verifier_key_id",
    "issued_at",
    "expires_at",
    "state"
)) "bootstrap grant identity-binding schema drifted"
$completeBootstrapContract = @($contract.api.operations | Where-Object { $_.operation_id -eq "completeBootstrap" })
Assert-Contract (
    ($completeBootstrapContract.Count -eq 1) -and
    (Test-ExactSequence @($completeBootstrapContract[0].request_forbidden_fields) @("user_id", "person_id", "roles", "enabled", "person_attestation", "user_binding", "target_channel")) -and
    ($completeBootstrapContract[0].uses_only_grant_bound_server_reserved_user_person_attestation_binding_and_target_channel -eq $true) -and
    ($completeBootstrapContract[0].rechecks_current_external_person_custodian_and_key_registries_before_commit -eq $true) -and
    ($completeBootstrapContract[0].security_ledger_mutation -ceq "bootstrap_completion")
) "completeBootstrap must use only the grant-bound first human identity and ledger authority"
Assert-Contract (Test-SameSet @($contract.iam_policy.password_hash.PSObject.Properties.Name) @("algorithm", "memory_kib_min", "iterations_min", "parallelism_min")) "password-hash policy schema drifted"
Assert-Contract ($contract.iam_policy.password_hash.algorithm -ceq "Argon2id") "password hash must be Argon2id"
Assert-Contract ($contract.iam_policy.password_hash.memory_kib_min -eq 19456) "Argon2id memory floor must be exactly 19456 KiB"
Assert-Contract ($contract.iam_policy.password_hash.iterations_min -eq 2) "Argon2id iteration floor must be exactly 2"
Assert-Contract ($contract.iam_policy.password_hash.parallelism_min -eq 1) "Argon2id parallelism floor must be exactly 1"
Assert-Contract (Test-SameSet @($contract.iam_policy.lockout.PSObject.Properties.Name) @("attempts", "window_minutes", "durations_minutes")) "lockout policy schema drifted"
Assert-Contract ($contract.iam_policy.lockout.attempts -eq 5) "lockout threshold must be 5"
Assert-Contract ($contract.iam_policy.lockout.window_minutes -eq 15) "lockout window must be 15 minutes"
Assert-Contract (Test-ExactSequence @($contract.iam_policy.lockout.durations_minutes) @(15, 30, 60)) "lockout durations must remain ordered 15, 30 and 60 minutes"
Assert-Contract (Test-SameSet @($contract.iam_policy.session.PSObject.Properties.Name) @("idle_minutes", "absolute_hours", "high_risk_reauthentication_minutes", "entropy_bits_min", "verifier_algorithm", "verifier_key_id_stored")) "session policy schema drifted"
Assert-Contract ($contract.iam_policy.session.idle_minutes -eq 30) "session idle timeout must be 30 minutes"
Assert-Contract ($contract.iam_policy.session.absolute_hours -eq 8) "session absolute timeout must be 8 hours"
Assert-Contract ($contract.iam_policy.session.high_risk_reauthentication_minutes -eq 10) "session reauthentication window must be 10 minutes"
Assert-Contract ($contract.iam_policy.session.entropy_bits_min -eq 256) "session entropy must be exactly 256 bits"
$browserSessionSecurity = $contract.iam_policy.browser_session_security
Assert-Contract (Test-SameSet @($browserSessionSecurity.PSObject.Properties.Name) @(
    "cookie_secure",
    "cookie_http_only",
    "cookie_same_site",
    "session_cookie_name",
    "session_cookie_host_only",
    "session_cookie_domain_attribute_present",
    "session_cookie_path",
    "duplicate_or_ambiguous_session_cookie_result",
    "session_id_in_url_or_local_storage",
    "csrf_token_entropy_bits_min",
    "csrf_token_bound_to_auth_session",
    "csrf_token_rotated_after_authentication_reauthentication_and_privilege_change",
    "session_identifier_rotated_after_authentication_reauthentication_and_privilege_change",
    "old_session_verifier_revoked_atomically_before_new_cookie_becomes_usable",
    "privilege_change_advances_authorization_epoch_and_invalidates_prior_epoch_sessions",
    "new_session_cookie_delivery",
    "csrf_delivery",
    "csrf_header_name",
    "authenticated_session_bootstrap_operation",
    "authenticated_session_bootstrap_rotates_and_delivers_csrf_token",
    "authenticated_session_bootstrap_response_cache_control",
    "authenticated_session_bootstrap_requires_exact_origin",
    "authenticated_session_bootstrap_is_the_only_cookie_mutation_exempt_from_existing_csrf_header",
    "get_current_auth_session_is_read_only_and_never_rotates_csrf",
    "csrf_response_header_readable_only_to_exact_allowed_origin",
    "cors_allow_credentials_only_for_exact_allowed_origin",
    "wildcard_cors_origin_allowed",
    "server_stores_csrf_keyed_verifier_only",
    "csrf_verifier_algorithm",
    "csrf_verifier_key_id_stored",
    "all_browser_state_changing_requests_including_unauthenticated_login_require_exact_origin",
    "cookie_authenticated_mutations_except_authenticated_session_bootstrap_require_session_bound_csrf_header",
    "allowed_origins_source",
    "safe_methods_exempt",
    "origin_missing_or_mismatch_result",
    "csrf_missing_or_mismatch_result",
    "csrf_token_in_url_local_storage_or_logs"
)) "browser session security schema drifted"
foreach ($trueField in @(
    "cookie_secure",
    "cookie_http_only",
    "session_cookie_host_only",
    "csrf_token_bound_to_auth_session",
    "csrf_token_rotated_after_authentication_reauthentication_and_privilege_change",
    "session_identifier_rotated_after_authentication_reauthentication_and_privilege_change",
    "old_session_verifier_revoked_atomically_before_new_cookie_becomes_usable",
    "privilege_change_advances_authorization_epoch_and_invalidates_prior_epoch_sessions",
    "authenticated_session_bootstrap_rotates_and_delivers_csrf_token",
    "authenticated_session_bootstrap_requires_exact_origin",
    "authenticated_session_bootstrap_is_the_only_cookie_mutation_exempt_from_existing_csrf_header",
    "get_current_auth_session_is_read_only_and_never_rotates_csrf",
    "csrf_response_header_readable_only_to_exact_allowed_origin",
    "cors_allow_credentials_only_for_exact_allowed_origin",
    "server_stores_csrf_keyed_verifier_only",
    "all_browser_state_changing_requests_including_unauthenticated_login_require_exact_origin",
    "cookie_authenticated_mutations_except_authenticated_session_bootstrap_require_session_bound_csrf_header"
)) {
    Assert-Contract ($browserSessionSecurity.$trueField -eq $true) "browser session security $trueField must remain true"
}
Assert-Contract ($browserSessionSecurity.cookie_same_site -ceq "Strict") "browser session cookies must use SameSite Strict"
Assert-Contract ($browserSessionSecurity.session_cookie_name -ceq "__Host-shuziren_session") "browser session cookie must use the __Host- prefix"
Assert-Contract ($browserSessionSecurity.session_cookie_host_only -eq $true) "browser session cookie must remain host-only"
Assert-Contract ($browserSessionSecurity.session_cookie_domain_attribute_present -eq $false) "browser session cookie must not have a Domain attribute"
Assert-Contract ($browserSessionSecurity.session_cookie_path -ceq "/") "browser session cookie Path must remain root"
Assert-Contract ($browserSessionSecurity.session_id_in_url_or_local_storage -eq $false) "browser session IDs must not enter URLs or local storage"
Assert-Contract ($browserSessionSecurity.csrf_token_entropy_bits_min -eq 256) "CSRF tokens must have at least 256 bits of entropy"
Assert-Contract ($browserSessionSecurity.allowed_origins_source -ceq "SERVER_CONFIGURED_EXACT_ALLOWLIST") "browser Origin checks must use a server-configured exact allowlist"
Assert-Contract (Test-ExactSequence @($browserSessionSecurity.safe_methods_exempt) @("GET", "HEAD", "OPTIONS")) "browser CSRF safe-method registry drifted"
Assert-Contract ($browserSessionSecurity.origin_missing_or_mismatch_result -ceq "FORBIDDEN") "missing or mismatched browser Origin must fail closed"
Assert-Contract ($browserSessionSecurity.csrf_missing_or_mismatch_result -ceq "FORBIDDEN") "missing or mismatched CSRF token must fail closed"
Assert-Contract ($browserSessionSecurity.csrf_token_in_url_local_storage_or_logs -eq $false) "CSRF tokens must not enter URLs, local storage or logs"
$authenticatedSessionBootstrapOperation = @($contract.api.operations | Where-Object { $_.operation_id -eq $browserSessionSecurity.authenticated_session_bootstrap_operation })
Assert-Contract (
    ($authenticatedSessionBootstrapOperation.Count -eq 1) -and
    ($authenticatedSessionBootstrapOperation[0].operation_id -ceq "refreshCsrfToken") -and
    ($authenticatedSessionBootstrapOperation[0].browser_security_policy -ceq "exact_origin_required_existing_csrf_header_narrowly_exempt") -and
    ($browserSessionSecurity.authenticated_session_bootstrap_is_the_only_cookie_mutation_exempt_from_existing_csrf_header -eq $true)
) "authenticated CSRF bootstrap must be the one narrow cookie-mutation CSRF exception"
Assert-Contract (Test-SameSet @($contract.iam_policy.reset_token.PSObject.Properties.Name) @(
    "ttl_minutes",
    "entropy_bits_min",
    "single_use",
    "stored_as_digest",
    "verifier_algorithm",
    "verifier_key_id_stored",
    "issuance_kinds",
    "issuance_binding_schema",
    "issuance_branch_rules",
    "target_enabled_role_privilege_person_binding_or_security_generation_change_revokes_outstanding_tokens",
    "consume_rechecks_current_target_matches_issuance_binding_and_policy",
    "normal_user_token_cannot_be_consumed_after_target_becomes_privileged",
    "provisioning_setup_consumption_sets_only_credential_and_possession_evidence_and_never_enables_or_grants_role",
    "provisioning_setup_requires_custodian_signed_user_binding_before_later_enable_or_role_grant",
    "consume_mismatch_result"
)) "reset-token policy schema drifted"
Assert-Contract ($contract.iam_policy.reset_token.ttl_minutes -eq 15) "reset token TTL must be 15 minutes"
Assert-Contract ($contract.iam_policy.reset_token.entropy_bits_min -eq 256) "reset token entropy must be exactly 256 bits"
Assert-Contract ($contract.iam_policy.reset_token.single_use -eq $true) "reset token must be single use"
Assert-Contract ($contract.iam_policy.reset_token.stored_as_digest -eq $true) "reset token must be digest stored"
Assert-Contract (Test-ExactSequence @($contract.iam_policy.reset_token.issuance_kinds) @("NORMAL_PASSWORD_RESET", "PROVISIONING_CREDENTIAL_SETUP")) "password credential setup token kinds drifted"
Assert-Contract (Test-ExactSequence @($contract.iam_policy.reset_token.issuance_binding_schema) @(
    "issuance_kind",
    "target_user_id",
    "target_account_state_generation",
    "target_authentication_epoch",
    "target_authorization_epoch",
    "target_role_scope_assignment_generation",
    "target_privilege_snapshot_hash",
    "target_person_id",
    "target_person_binding_generation",
    "target_person_eligibility_generation",
    "target_channel_event_id",
    "target_possession_challenge_hash",
    "issuance_policy_id"
)) "password credential setup token binding schema drifted"
Assert-Contract ($contract.iam_policy.reset_token.issuance_branch_rules.NORMAL_PASSWORD_RESET -ceq "TARGET_MUST_HAVE_CURRENT_ACTIVE_PERSON_BINDING_AND_ALL_PERSON_FIELDS_REQUIRED_TARGET_CHANNEL_AND_CHALLENGE_FIELDS_BIND_EXACT_TARGET") "normal password reset identity branch drifted"
Assert-Contract ($contract.iam_policy.reset_token.issuance_branch_rules.PROVISIONING_CREDENTIAL_SETUP -ceq "TARGET_MUST_BE_DISABLED_EMPTY_ROLE_PROVISIONING_USER_PERSON_FIELDS_NULL_TARGET_CHANNEL_AND_CHALLENGE_FIELDS_REQUIRED") "provisioning credential setup identity branch drifted"
Assert-Contract ($contract.iam_policy.reset_token.provisioning_setup_consumption_sets_only_credential_and_possession_evidence_and_never_enables_or_grants_role -eq $true) "provisioning credential setup must not grant authority"
Assert-Contract ($contract.iam_policy.reset_token.provisioning_setup_requires_custodian_signed_user_binding_before_later_enable_or_role_grant -eq $true) "provisioning credential setup must precede independent user binding"
$issuePasswordResetContract = @($contract.api.operations | Where-Object { $_.operation_id -eq "issuePasswordReset" })
$consumePasswordResetContract = @($contract.api.operations | Where-Object { $_.operation_id -eq "consumePasswordReset" })
Assert-Contract (
    ($issuePasswordResetContract.Count -eq 1) -and
    ($issuePasswordResetContract[0].issuance_kind_by_target_state.ACTIVE_BOUND_NON_PRIVILEGED -ceq "NORMAL_PASSWORD_RESET") -and
    ($issuePasswordResetContract[0].issuance_kind_by_target_state.PROVISIONING_DISABLED_EMPTY_ROLE_SET -ceq "PROVISIONING_CREDENTIAL_SETUP") -and
    ($issuePasswordResetContract[0].initiator_never_receives_or_observes_reset_token -eq $true)
) "issuePasswordReset target-state branch drifted"
Assert-Contract (
    ($consumePasswordResetContract.Count -eq 1) -and
    ($consumePasswordResetContract[0].privileged_target_person_proof_required -eq $true) -and
    ($consumePasswordResetContract[0].provisioning_credential_setup_never_enables_or_grants_role_and_records_target_possession_evidence -eq $true)
) "consumePasswordReset provisioning authority boundary drifted"

$recoveryPasswordSetupGrantPolicy = $contract.iam_policy.recovery_password_setup_grant_policy
Assert-Contract (Test-ExactSequence @($recoveryPasswordSetupGrantPolicy.authorization_kinds) @("STANDARD_HIGH_RISK", "DISASTER_CUSTODIAN", "PRODUCTION_READINESS_CUSTODIAN")) "recovery password setup grant authorization-kind registry drifted"
Assert-Contract ($recoveryPasswordSetupGrantPolicy.authorization_reference_exactly_one_id -eq $true) "recovery password setup grant must bind exactly one authority"
Assert-Contract ($recoveryPasswordSetupGrantPolicy.grant_set_is_authority_transition_scoped_and_terminalized_atomically -eq $true) "recovery password setup grant set must terminalize atomically"
Assert-Contract ($recoveryPasswordSetupGrantPolicy.any_required_grant_expiry_revocation_or_authentication_failure_aborts_entire_set -eq $true) "recovery password setup grant failure must abort the entire set"
Assert-Contract ($recoveryPasswordSetupGrantPolicy.production_readiness_admin_replacement_grant_count -eq 1) "production readiness admin replacement must issue exactly one grant"
Assert-Contract ($recoveryPasswordSetupGrantPolicy.staged_authentication_proof_contains_password_token_or_reauthentication_material -eq $false) "staged authentication proof must remain sanitized"

$humanOperatorIndependence = $contract.iam_policy.human_operator_independence
Assert-Contract ($humanOperatorIndependence.person_identity_source -ceq "EXTERNAL_CUSTODIAN_ATTESTED_HUMAN_OPERATOR_REGISTRY") "human operator identity source drifted"
Assert-Contract ($humanOperatorIndependence.person_identity_attestation_minimum_distinct_custodians -eq 2) "human identity attestation requires two distinct custodians"
Assert-Contract ($humanOperatorIndependence.person_identity_attestation_signature_algorithm -ceq "Ed25519") "human identity attestation algorithm drifted"
Assert-Contract ($humanOperatorIndependence.person_identity_attestation_signature_purpose_domain -ceq "HUMAN_OPERATOR_ATTESTATION_SIGNATURE") "human identity attestation purpose drifted"
Assert-Contract ($humanOperatorIndependence.person_identity_attestation_canonicalization -ceq "RFC8785_JCS_AFTER_STRICT_TYPED_PARSE") "human identity attestation canonicalization drifted"
Assert-Contract ($humanOperatorIndependence.user_binding_signature_purpose_domain -ceq "HUMAN_OPERATOR_ATTESTATION_SIGNATURE") "human user binding purpose drifted"
Assert-Contract ($humanOperatorIndependence.user_binding_domain_separator -cne $humanOperatorIndependence.person_identity_attestation_domain_separator) "person attestation and user binding must use distinct domains"
Assert-Contract ($humanOperatorIndependence.user_binding_requires_two_distinct_custodian_signatures_and_current_user_possession_proof -eq $true) "human user binding requires independent custodians and possession proof"
Assert-Contract ($humanOperatorIndependence.user_possession_proof_contains_password_verifier_token_or_reusable_authentication_material -eq $false) "human user possession proof must not contain reusable authentication material"
Assert-Contract ($humanOperatorIndependence.all_authenticatable_control_plane_human_users_require_active_attested_person_id_and_user_binding -eq $true) "every authenticatable human user must bind an active attested person"
Assert-Contract ($humanOperatorIndependence.one_active_user_per_person_per_deployment -eq $true) "one person must not control multiple active approval identities"
Assert-Contract ($humanOperatorIndependence.high_risk_initiator_and_approver_person_ids_must_differ -eq $true) "high-risk approvers must be different people"
Assert-Contract ($humanOperatorIndependence.high_risk_initiator_and_approver_user_ids_must_differ -eq $true) "high-risk approvers must be different users"
Assert-Contract ($humanOperatorIndependence.privileged_password_reset_token_returned_to_initiator -eq $false) "a privileged password reset token must never return to the initiator"
Assert-Contract ($humanOperatorIndependence.initiator_may_not_claim_or_observe_another_privileged_person_credential -eq $true) "an initiator must not observe another privileged person's credential"
Assert-Contract ($humanOperatorIndependence.user_provisioning_policy.create_user_accepts_password_enabled_roles_or_person_binding_fields -eq $false) "createUser must not accept credential, authority or person-binding fields"
Assert-Contract ($humanOperatorIndependence.user_provisioning_policy.provisioning_user_has_empty_role_set_and_cannot_authenticate_or_approve -eq $true) "new users must remain non-authoritative while provisioning"
Assert-Contract ($humanOperatorIndependence.user_provisioning_policy.custodian_signed_user_binding_precedes_enable_or_role_grant -eq $true) "custodian user binding must precede enable or role grant"

$createUserContract = @($contract.api.operations | Where-Object { $_.operation_id -eq "createUser" })
Assert-Contract (
    ($createUserContract.Count -eq 1) -and
    ($createUserContract[0].created_user_state -ceq "PROVISIONING_DISABLED_EMPTY_ROLE_SET") -and
    (Test-SameSet @($createUserContract[0].request_forbidden_fields) @("password", "password_verifier", "enabled", "roles", "role_assignments", "person_id", "person_binding_id", "person_attestation"))
) "createUser provisioning request boundary drifted"
$updateUserContract = @($contract.api.operations | Where-Object { $_.operation_id -eq "updateUser" })
Assert-Contract (
    ($updateUserContract.Count -eq 1) -and
    (Test-ExactSequence @($updateUserContract[0].request_allowed_fields) @("normalized_username", "display_name")) -and
    (@("password", "enabled", "roles", "role_assignments", "person_id", "person_binding_id", "person_attestation") | Where-Object { $_ -notin $updateUserContract[0].request_forbidden_fields }).Count -eq 0
) "updateUser must not bypass dedicated credential, authority or person-binding operations"

$disasterRecoveryAuthorization = $contract.iam_policy.disaster_recovery_authorization
Assert-Contract (Test-SameSet @($disasterRecoveryAuthorization.PSObject.Properties.Name) @(
    "enabled",
    "entry_conditions",
    "surface",
    "network_api_exposed",
    "authorization_mode_xor",
    "custodian_envelope_is_restricted_execute_restore_authorization",
    "standard_high_risk_action_not_required_in_disaster_mode",
    "minimum_registered_custodians",
    "minimum_distinct_custodian_signatures",
    "custodian_signature_algorithm",
    "custodian_signature_purpose_domain",
    "custodian_signature_verification_requires_record_bound_key_id_and_exact_purpose",
    "custodian_signature_canonicalization",
    "custodian_signature_domain_separator",
    "custodian_signature_input",
    "custodian_quorum_counts_distinct_custodian_ids_not_key_ids",
    "active_signature_key_id_maps_to_exactly_one_custodian_id",
    "one_signature_per_custodian_id",
    "custodian_registry_version_bound",
    "custodian_revocation_state_from_external_anchor",
    "authorization_ttl_minutes",
    "authorization_time_source",
    "clock_rollback_never_extends_authorization",
    "single_use_nonce",
    "custodian_public_keys_in_external_anchor",
    "custodian_private_keys_offline",
    "backup_recovery_key_is_distinct",
    "authorization_envelope_binds",
    "authorization_envelope_admin_readiness_branch_rules",
    "entry_condition_preflight_evidence_is_canonical_sanitized_and_signed",
    "entry_condition_rechecked_immediately_before_prepared_commit",
    "active_store_available_and_standard_authorization_possible_result",
    "active_store_unavailable_condition_requires_full_loss_source_mode",
    "no_usable_admin_condition_requires_online_source_mode_and_authoritative_query",
    "envelope_nonce_registry",
    "envelope_nonce_record_schema",
    "envelope_nonce_hmac_algorithm",
    "envelope_nonce_hmac_canonicalization",
    "envelope_nonce_hmac_domain_separator",
    "envelope_nonce_hmac_input",
    "envelope_nonce_unique_compare_and_swap_key",
    "envelope_nonce_uniqueness_and_transition_use_external_compare_and_swap",
    "envelope_nonce_hmac_purpose_domain",
    "envelope_nonce_reserved_before_grant_issue",
    "envelope_nonce_reservation_states",
    "pre_pointer_abort_marks_nonce_aborted_consumed_and_never_reusable",
    "envelope_nonce_exact_retry_allowed_only_for_same_cutover_id_and_authenticated_payload",
    "allowed_commands",
    "selected_admins_requirement_by_branch",
    "selected_admins_must_have_distinct_active_attested_person_ids",
    "local_disaster_admin_readiness_replacement",
    "production_disaster_admin_branch_selection",
    "disaster_recovery_password_setup_grant_count_by_deployment_mode",
    "recovery_password_setup_grant_entropy_bits_min",
    "recovery_password_setup_grant_stored_as_keyed_digest_with_key_id",
    "recovery_password_setup_grant_verifier_algorithm",
    "recovery_password_setup_grant_plaintext_local_one_time_no_store",
    "recovery_password_setup_grant_binds",
    "recovery_password_setup_grant_single_use",
    "recovery_password_setup_grant_ttl_minutes",
    "recovery_password_setup_grant_provisional_consume_sets_staged_verifier_and_auth_proof",
    "recovery_password_setup_grant_consume_revokes_sibling_grants_for_user",
    "recovery_password_setup_grant_plaintext_in_continuity_ledger_audit_backup_or_logs",
    "all_required_grants_provisionally_consumed_before_cutover",
    "staged_authentication_proof_required_for_each_selected_admin",
    "provisional_staged_verifier_not_authoritative_before_cutover",
    "password_generation_authority_commits_only_with_cutover_anchor",
    "pre_pointer_abort_result",
    "authority_change_rules_by_admin_readiness_branch",
    "cannot_reactivate_old_credential",
    "ledger_prepared_committed_anchor_required",
    "external_recovery_audit_inserted_via_continuity",
    "production_activation_readiness_checks",
    "cutover_admin_access_requirement_by_deployment_mode",
    "invalid_or_unavailable_result"
)) "disaster recovery authorization schema drifted"
Assert-Contract ($disasterRecoveryAuthorization.enabled -eq $true) "offline disaster recovery authorization must remain enabled"
Assert-Contract (Test-ExactSequence @($disasterRecoveryAuthorization.entry_conditions) @("ACTIVE_STORE_UNAVAILABLE", "NO_CREDENTIAL_USABLE_ENABLED_DEPLOYMENT_PLATFORM_ADMIN")) "disaster recovery authorization entry conditions drifted"
Assert-Contract ($disasterRecoveryAuthorization.surface -ceq "LOCAL_MAINTENANCE_ONLY") "disaster recovery authorization must be local maintenance only"
Assert-Contract ($disasterRecoveryAuthorization.network_api_exposed -eq $false) "disaster recovery authorization must not expose a network API"
Assert-Contract ($disasterRecoveryAuthorization.authorization_mode_xor -ceq "STANDARD_HIGH_RISK_ACTION_XOR_DISASTER_RECOVERY_CUSTODIAN_ENVELOPE") "restore authorization modes must be mutually exclusive"
Assert-Contract ($disasterRecoveryAuthorization.minimum_registered_custodians -eq 3) "disaster recovery authorization must register at least three custodians"
Assert-Contract ($disasterRecoveryAuthorization.minimum_distinct_custodian_signatures -eq 2) "disaster recovery authorization must require two distinct custodians"
Assert-Contract ($disasterRecoveryAuthorization.custodian_signature_algorithm -ceq "Ed25519") "disaster recovery custodian signatures must use Ed25519"
Assert-Contract ($disasterRecoveryAuthorization.authorization_ttl_minutes -eq 30) "disaster recovery authorization TTL must be 30 minutes"
foreach ($trueField in @(
    "single_use_nonce",
    "custodian_public_keys_in_external_anchor",
    "custodian_private_keys_offline",
    "custodian_registry_version_bound",
    "custodian_revocation_state_from_external_anchor",
    "backup_recovery_key_is_distinct",
    "custodian_envelope_is_restricted_execute_restore_authorization",
    "standard_high_risk_action_not_required_in_disaster_mode",
    "custodian_signature_verification_requires_record_bound_key_id_and_exact_purpose",
    "custodian_quorum_counts_distinct_custodian_ids_not_key_ids",
    "active_signature_key_id_maps_to_exactly_one_custodian_id",
    "one_signature_per_custodian_id",
    "clock_rollback_never_extends_authorization",
    "entry_condition_preflight_evidence_is_canonical_sanitized_and_signed",
    "entry_condition_rechecked_immediately_before_prepared_commit",
    "active_store_unavailable_condition_requires_full_loss_source_mode",
    "no_usable_admin_condition_requires_online_source_mode_and_authoritative_query",
    "envelope_nonce_uniqueness_and_transition_use_external_compare_and_swap",
    "envelope_nonce_reserved_before_grant_issue",
    "pre_pointer_abort_marks_nonce_aborted_consumed_and_never_reusable",
    "envelope_nonce_exact_retry_allowed_only_for_same_cutover_id_and_authenticated_payload",
    "selected_admins_must_have_distinct_active_attested_person_ids",
    "recovery_password_setup_grant_stored_as_keyed_digest_with_key_id",
    "recovery_password_setup_grant_plaintext_local_one_time_no_store",
    "recovery_password_setup_grant_single_use",
    "recovery_password_setup_grant_provisional_consume_sets_staged_verifier_and_auth_proof",
    "recovery_password_setup_grant_consume_revokes_sibling_grants_for_user",
    "all_required_grants_provisionally_consumed_before_cutover",
    "staged_authentication_proof_required_for_each_selected_admin",
    "provisional_staged_verifier_not_authoritative_before_cutover",
    "password_generation_authority_commits_only_with_cutover_anchor",
    "cannot_reactivate_old_credential",
    "ledger_prepared_committed_anchor_required",
    "external_recovery_audit_inserted_via_continuity"
)) {
    Assert-Contract ($disasterRecoveryAuthorization.$trueField -eq $true) "disaster recovery authorization $trueField must remain true"
}
Assert-Contract ($disasterRecoveryAuthorization.recovery_password_setup_grant_ttl_minutes -eq 30) "recovery password setup grant TTL must be 30 minutes"
Assert-Contract (
    ($disasterRecoveryAuthorization.disaster_recovery_password_setup_grant_count_by_deployment_mode.SETUP -eq 1) -and
    ($disasterRecoveryAuthorization.disaster_recovery_password_setup_grant_count_by_deployment_mode.PRODUCTION_ACTIVE_ANY_POSTURE -eq 2)
) "disaster recovery must issue the exact deployment-mode recovery password setup grant count"
Assert-Contract ($disasterRecoveryAuthorization.recovery_password_setup_grant_entropy_bits_min -eq 256) "recovery password setup grants must have at least 256 bits of entropy"
Assert-Contract ($disasterRecoveryAuthorization.recovery_password_setup_grant_plaintext_in_continuity_ledger_audit_backup_or_logs -eq $false) "recovery password setup grant plaintext must never enter continuity, ledger, audit, backup or logs"
$localDisasterAdminReplacement = $disasterRecoveryAuthorization.local_disaster_admin_readiness_replacement
Assert-Contract (Test-ExactSequence @($localDisasterAdminReplacement.PSObject.Properties.Name) @(
    "branch_id",
    "allowed_when_local_disaster_and_exactly_one_current_active_attested_existing_admin_remains_for_online_or_full_loss_source",
    "zero_current_active_attested_admins_result",
    "two_current_active_attested_admins_use_branch",
    "replacement_requires_current_two_of_three_human_attestation_signatures_under_human_operator_purpose",
    "human_signature_algorithm",
    "human_signature_purpose_domain",
    "human_signature_domain_separator",
    "human_signed_payload",
    "disaster_restore_still_requires_separate_two_of_three_offline_recovery_signatures",
    "may_create_bind_enable_and_assign_exactly_one_replacement_platform_admin_only",
    "replacement_person_id_must_differ_from_surviving_admin_person_id",
    "replacement_user_id_must_be_new_and_not_alias_existing_or_revoked_user",
    "replacement_attestation_binding_and_eligibility_generations_rechecked_immediately_before_cutover_commit",
    "cannot_reactivate_revoked_person_binding_or_widen_any_other_authority",
    "two_grants_target_surviving_and_replacement_admins_and_both_must_authenticate_staged_store",
    "replacement_user_person_binding_role_password_and_eligibility_generations_provisional_until_same_cutover_ledger_and_disaster_nonce_anchors",
    "abort_destroys_replacement_verifier_and_leaves_no_authoritative_replacement_account"
)) "local-disaster replacement field set differs"
Assert-Contract ($localDisasterAdminReplacement.branch_id -ceq "LOCAL_DISASTER_REPLACE_ONE") "local-disaster replacement branch identifier drifted"
Assert-Contract ($localDisasterAdminReplacement.human_signature_algorithm -ceq "Ed25519") "local-disaster replacement human signatures must use Ed25519"
Assert-Contract ($localDisasterAdminReplacement.human_signature_purpose_domain -ceq "HUMAN_OPERATOR_ATTESTATION_SIGNATURE") "local-disaster replacement human signature purpose drifted"
Assert-Contract ($localDisasterAdminReplacement.human_signature_domain_separator -ceq "shuziren:p1:local-disaster-admin-replacement:v1") "local-disaster replacement signature domain separator drifted"
Assert-Contract ($localDisasterAdminReplacement.human_signed_payload -ceq "COMPLETE_AUTHORIZATION_ENVELOPE_EXCLUDING_OFFLINE_AND_HUMAN_SIGNATURE_TUPLES") "local-disaster replacement signed payload drifted"
Assert-Contract ($localDisasterAdminReplacement.zero_current_active_attested_admins_result -ceq "EXPLICIT_REINITIALIZATION_REQUIRED") "zero-admin disaster recovery must require explicit reinitialization"
Assert-Contract ($localDisasterAdminReplacement.two_current_active_attested_admins_use_branch -ceq "NONE") "two-admin disaster recovery must not use the replacement branch"
foreach ($trueField in @(
    "allowed_when_local_disaster_and_exactly_one_current_active_attested_existing_admin_remains_for_online_or_full_loss_source",
    "replacement_requires_current_two_of_three_human_attestation_signatures_under_human_operator_purpose",
    "disaster_restore_still_requires_separate_two_of_three_offline_recovery_signatures",
    "may_create_bind_enable_and_assign_exactly_one_replacement_platform_admin_only",
    "replacement_person_id_must_differ_from_surviving_admin_person_id",
    "replacement_user_id_must_be_new_and_not_alias_existing_or_revoked_user",
    "replacement_attestation_binding_and_eligibility_generations_rechecked_immediately_before_cutover_commit",
    "cannot_reactivate_revoked_person_binding_or_widen_any_other_authority",
    "two_grants_target_surviving_and_replacement_admins_and_both_must_authenticate_staged_store",
    "replacement_user_person_binding_role_password_and_eligibility_generations_provisional_until_same_cutover_ledger_and_disaster_nonce_anchors",
    "abort_destroys_replacement_verifier_and_leaves_no_authoritative_replacement_account"
)) {
    Assert-Contract ($localDisasterAdminReplacement.$trueField -eq $true) "local-disaster replacement $trueField must remain true"
}
Assert-Contract (Test-ExactSequence @($disasterRecoveryAuthorization.recovery_password_setup_grant_binds) @(
    "authorization_kind",
    "high_risk_action_id",
    "disaster_recovery_authorization_envelope_id",
    "authorization_reference_exactly_one_id",
    "authorization_evidence_hash",
    "deployment_id",
    "staged_store_id",
    "selected_user_id",
    "selected_person_id",
    "selected_person_binding_generation",
    "selected_person_eligibility_generation",
    "expected_old_credential_generation",
    "expected_new_credential_generation",
    "expected_authentication_epoch",
    "cutover_prepared_sequence",
    "nonce",
    "expires_at"
)) "recovery password setup grant bindings drifted"
Assert-Contract (Test-ExactSequence @($disasterRecoveryAuthorization.authorization_envelope_binds) @(
    "deployment_id",
    "deployment_mode",
    "deployment_operational_posture",
    "backup_manifest_hash",
    "recovery_security_ledger_head",
    "staged_store_id",
    "disaster_entry_condition",
    "entry_condition_preflight_evidence_hash",
    "exact_restore_mode",
    "exact_missing_credential_subject_set",
    "admin_readiness_branch",
    "selected_platform_admin_user_ids_sorted_distinct",
    "selected_admin_user_person_tuples_sorted_distinct",
    "selected_admin_person_binding_generations",
    "selected_admin_person_eligibility_generations",
    "person_registry_generation",
    "replacement_person_attestation_hash",
    "replacement_user_binding_hash",
    "human_attestation_custodian_registry_generation",
    "human_attestation_signature_key_ids_sorted_distinct",
    "human_attestation_signature_tuples_sorted_distinct",
    "custodian_registry_version",
    "custodian_ids_sorted_distinct",
    "custodian_signature_key_ids_sorted_distinct",
    "custodian_signature_tuples_sorted_by_custodian_id",
    "nonce",
    "issued_at",
    "expires_at"
)) "disaster recovery authorization envelope bindings drifted"
Assert-Contract (Test-ExactSequence @($disasterRecoveryAuthorization.allowed_commands) @("validate_exact_backup", "authorize_exact_restore", "issue_required_recovery_password_setup_grants_by_deployment_mode")) "disaster recovery authorization command set drifted"
Assert-Contract (Test-ExactSequence @($disasterRecoveryAuthorization.production_activation_readiness_checks) @(
    "backup_recovery_key_available",
    "production_backup_root_writable_on_required_separate_mount",
    "current_checkpoint_at_exact_ledger_head_key_person_registry_and_selected_admin_generations_cryptographically_verified",
    "recovery_security_ledger_and_anchor_healthy",
    "external_disaster_nonce_registry_read_write_compare_and_swap_and_replay_preflight_passed",
    "external_operational_fence_anchor_hmac_read_write_compare_and_swap_and_initial_ready_generation_preflight_passed",
    "active_operational_fence_hmac_key_and_exact_purpose_verification_preflight_passed",
    "external_production_readiness_nonce_registry_and_active_hmac_key_read_write_cas_preflight_passed",
    "external_emergency_authority_reduction_nonce_registry_and_active_hmac_key_read_write_cas_preflight_passed",
    "external_trusted_monotonic_time_read_and_clock_rollback_preflight_passed",
    "anchor_native_root_recovery_nonce_compare_and_swap_checkpoint_and_offline_signature_preflight_passed",
    "minimum_three_active_offline_recovery_custodian_public_keys_registered",
    "offline_recovery_custodian_signature_preflight_passed",
    "minimum_three_active_human_operator_attestation_custodian_public_keys_registered",
    "human_operator_attestation_signature_preflight_passed",
    "current_external_person_registry_healthy",
    "two_distinct_active_attested_admin_person_ids_and_eligibility_generations",
    "restore_continuity_envelope_key_available",
    "two_credential_usable_deployment_platform_admins"
)) "production disaster-recovery readiness checks drifted"
Assert-Contract (
    ($disasterRecoveryAuthorization.cutover_admin_access_requirement_by_deployment_mode.SETUP -ceq "ONE_SELECTED_EXISTING_ATTESTED_ADMIN_CREDENTIAL_USABLE_AND_AUTHENTICATED_AGAINST_STAGED_STORE") -and
    ($disasterRecoveryAuthorization.cutover_admin_access_requirement_by_deployment_mode.PRODUCTION_ACTIVE_ANY_POSTURE -ceq "TWO_SELECTED_DISTINCT_ATTESTED_PERSON_ADMINS_CREDENTIAL_USABLE_AND_AUTHENTICATED_AGAINST_STAGED_STORE")
) "disaster recovery cutover admin access rule drifted"
Assert-Contract ($disasterRecoveryAuthorization.invalid_or_unavailable_result -ceq "FAIL_CLOSED_KEEP_ACTIVE_OR_STAGED_UNSERVED") "invalid disaster recovery authorization must fail closed"

$authorizationScope = $contract.iam_policy.authorization_scope
Assert-Contract (Test-SameSet @($authorizationScope.PSObject.Properties.Name) @(
    "role_catalog_version",
    "scope_types",
    "scope_id_required",
    "scope_must_share_authenticated_tenant_and_deployment",
    "inheritance",
    "sibling_or_ancestor_access",
    "unknown_role_scope_or_catalog_result",
    "production_high_risk_min_distinct_authorized_users",
    "production_high_risk_min_distinct_active_attested_person_ids",
    "production_activation_requires_two_credential_usable_deployment_platform_admins",
    "production_activation_requires_two_distinct_active_attested_admin_person_ids",
    "production_admin_floor_enforced_after_activation_on_disable_and_role_replace",
    "production_activation_failure_result",
    "allowed_scopes_by_role"
)) "authorization scope schema drifted"
Assert-Contract ($authorizationScope.role_catalog_version -ceq "p1_roles_v1") "role catalog version drifted"
Assert-Contract (Test-ExactSequence @($authorizationScope.scope_types) @("DEPLOYMENT", "SITE", "SCREEN")) "authorization scope types drifted"
Assert-Contract ($authorizationScope.scope_id_required -eq $true) "authorization assignment scope IDs must be required"
Assert-Contract ($authorizationScope.scope_must_share_authenticated_tenant_and_deployment -eq $true) "authorization assignment scopes must remain inside the authenticated boundary"
Assert-Contract ($authorizationScope.inheritance -ceq "NAMED_SCOPE_AND_DESCENDANTS_ONLY") "authorization scope inheritance drifted"
Assert-Contract ($authorizationScope.sibling_or_ancestor_access -eq $false) "authorization scopes must not grant sibling or ancestor access"
Assert-Contract ($authorizationScope.unknown_role_scope_or_catalog_result -ceq "DENY") "unknown role/scope/catalog entries must deny"
Assert-Contract ($authorizationScope.production_high_risk_min_distinct_authorized_users -eq 2) "production four-eyes requires at least two distinct authorized users"
Assert-Contract ($authorizationScope.production_high_risk_min_distinct_active_attested_person_ids -eq 2) "production four-eyes requires two distinct active attested persons"
Assert-Contract (
    ($authorizationScope.production_activation_requires_two_credential_usable_deployment_platform_admins -eq $true) -and
    ($authorizationScope.production_activation_requires_two_distinct_active_attested_admin_person_ids -eq $true) -and
    ($authorizationScope.production_admin_floor_enforced_after_activation_on_disable_and_role_replace -eq $true)
) "production must prevent disable or role replacement from reducing usable deployment admins below two"
$expectedScopesByRole = @{
    "platform_admin" = @("DEPLOYMENT")
    "implementation_engineer" = @("DEPLOYMENT", "SITE", "SCREEN")
    "business_operator" = @("SITE", "SCREEN")
    "operations_engineer" = @("DEPLOYMENT", "SITE")
    "auditor" = @("DEPLOYMENT", "SITE", "SCREEN")
}
Assert-Contract (Test-SameSet @($authorizationScope.allowed_scopes_by_role.PSObject.Properties.Name) @($expectedScopesByRole.Keys)) "authorization role/scope registry drifted"
foreach ($roleName in @($expectedScopesByRole.Keys)) {
    Assert-Contract (Test-ExactSequence @($authorizationScope.allowed_scopes_by_role.PSObject.Properties[$roleName].Value) $expectedScopesByRole[$roleName]) "authorization scopes for role $roleName drifted"
}

Assert-Contract (Test-SameSet @($contract.device_policy.PSObject.Properties.Name) @(
    "enrollment_ttl_minutes",
    "credential_entropy_bits_min",
    "enrollment_and_credential_verifier_algorithm",
    "enrollment_and_credential_verifier_key_id_stored",
    "rotation_activation_minutes",
    "hard_revoke_increments_epoch",
    "hard_revoke_etag_resource",
    "hard_revoke_requires_ledger_head",
    "hard_revoke_atomic_family",
    "hard_revoke_epoch_increment_exactly_once",
    "hard_revoke_commit_time_epoch_recheck",
    "hard_revoke_stale_result",
    "enrollment_claim_when_active_family_exists",
    "rotation_requires_active_requester_version",
    "rotation_concurrency",
    "rotation_request_family_generation_increment_exactly_once",
    "successor_activation_family_generation_increment_exactly_once",
    "concurrent_successor_result",
    "pending_successor_expiry_revokes_only_successor_and_keeps_predecessor_active",
    "active_credential_expiry_atomically_sets_family_reenroll_required_advances_family_generation_and_commits_ledger",
    "reenrollment_allowed_only_when_family_reenroll_required_or_absent",
    "reenrollment_requires_family_generation_and_ledger_head"
)) "device policy schema differs from the frozen contract"
Assert-Contract ($contract.device_policy.enrollment_ttl_minutes -eq 15) "device enrollment TTL must be 15 minutes"
Assert-Contract ($contract.device_policy.credential_entropy_bits_min -eq 256) "device credential entropy must be exactly 256 bits"
Assert-Contract ($contract.device_policy.rotation_activation_minutes -eq 10) "device successor activation window must be 10 minutes"
Assert-Contract ($contract.device_policy.hard_revoke_increments_epoch -eq $true) "hard device revocation must increment the credential epoch"
Assert-Contract ($contract.device_policy.hard_revoke_etag_resource -ceq "DeviceCredentialFamily") "hard device revocation must use the family ETag"
Assert-Contract ($contract.device_policy.hard_revoke_requires_ledger_head -eq $true) "hard device revocation must bind the ledger head"
Assert-Contract ($contract.device_policy.hard_revoke_atomic_family -eq $true) "hard device revocation must revoke the family atomically"
Assert-Contract ($contract.device_policy.hard_revoke_epoch_increment_exactly_once -eq $true) "hard device revocation must increment its epoch exactly once"
Assert-Contract ($contract.device_policy.hard_revoke_commit_time_epoch_recheck -eq $true) "device requests must recheck the credential epoch at commit time"
Assert-Contract ($contract.device_policy.hard_revoke_stale_result -ceq "RESOURCE_VERSION_CONFLICT") "hard device revocation stale result drifted"
Assert-Contract ($contract.device_policy.enrollment_claim_when_active_family_exists -ceq "ACTIVE_DEVICE_FAMILY_EXISTS") "enrollment claim must reject a second active device family"
Assert-Contract ($contract.device_policy.rotation_requires_active_requester_version -eq $true) "device rotation must require the active requester credential version"
Assert-Contract ($contract.device_policy.rotation_concurrency -ceq "credential_epoch_and_family_generation") "device rotation concurrency drifted"
Assert-Contract ($contract.device_policy.rotation_request_family_generation_increment_exactly_once -eq $true) "device rotation request must advance family generation exactly once"
Assert-Contract ($contract.device_policy.successor_activation_family_generation_increment_exactly_once -eq $true) "device successor activation must advance family generation exactly once"
Assert-Contract ($contract.device_policy.concurrent_successor_result -ceq "SUCCESSOR_ALREADY_PENDING") "concurrent device successor result drifted"
Assert-Contract ($contract.device_policy.pending_successor_expiry_revokes_only_successor_and_keeps_predecessor_active -eq $true) "pending device successor expiry must preserve the active predecessor"
Assert-Contract ($contract.device_policy.active_credential_expiry_atomically_sets_family_reenroll_required_advances_family_generation_and_commits_ledger -eq $true) "active device credential expiry must atomically require re-enrollment"
Assert-Contract ($contract.device_policy.reenrollment_allowed_only_when_family_reenroll_required_or_absent -eq $true) "device re-enrollment must not create a second active family"
Assert-Contract ($contract.device_policy.reenrollment_requires_family_generation_and_ledger_head -eq $true) "device re-enrollment must bind the current family generation and ledger head"

$externalCredentialRotationPolicy = $contract.external_credential_rotation_policy
Assert-Contract (Test-SameSet @($externalCredentialRotationPolicy.PSObject.Properties.Name) @(
    "secret_version_encryption_schema",
    "secret_version_nonce_unique_per_envelope_encryption_key",
    "secret_version_associated_data_binds",
    "secret_plaintext_or_deterministic_unkeyed_plaintext_commitment_persisted_or_exposed",
    "finereport_identity_binding_references_secret_version_and_never_duplicates_ciphertext",
    "version_states",
    "version_transitions",
    "modes",
    "default_mode",
    "retiring_max_hours",
    "active_version_only_for_new_bindings",
    "retiring_use_scope",
    "high_risk_action_binds_retiring_target_set_hash_and_runtime_binding_generations",
    "execution_recomputes_and_requires_exact_retiring_target_set",
    "changed_retiring_target_set_result",
    "revoked_use_allowed",
    "restore_never_increases_version_usability",
    "emergency_revocation_blocks_affected_runtime"
)) "external credential rotation policy schema drifted"
Assert-Contract (Test-ExactSequence @($externalCredentialRotationPolicy.version_states) @("ACTIVE", "RETIRING", "REVOKED")) "external credential version states drifted"
Assert-Contract (Test-ExactSequence @($externalCredentialRotationPolicy.version_transitions) @("ACTIVE|RETIRING|staged_successor", "ACTIVE|REVOKED|emergency_revoke", "RETIRING|REVOKED|deadline_or_emergency_revoke")) "external credential version transitions drifted"
Assert-Contract (Test-ExactSequence @($externalCredentialRotationPolicy.modes) @("STAGED", "EMERGENCY_REVOKE")) "external credential rotation modes drifted"
Assert-Contract ($externalCredentialRotationPolicy.default_mode -ceq "STAGED") "external credential rotation default must be STAGED"
Assert-Contract ($externalCredentialRotationPolicy.retiring_max_hours -eq 24) "external credential retiring window must be capped at 24 hours"
Assert-Contract ($externalCredentialRotationPolicy.active_version_only_for_new_bindings -eq $true) "new bindings must use only the ACTIVE external credential version"
Assert-Contract ($externalCredentialRotationPolicy.retiring_use_scope -ceq "EXACT_PRE_ROTATION_APPLIED_TARGETS_UNTIL_DEADLINE") "retiring external credential use scope drifted"
Assert-Contract ($externalCredentialRotationPolicy.high_risk_action_binds_retiring_target_set_hash_and_runtime_binding_generations -eq $true) "credential rotation approval must bind the retiring target set and RuntimeBinding generations"
Assert-Contract ($externalCredentialRotationPolicy.execution_recomputes_and_requires_exact_retiring_target_set -eq $true) "credential rotation execution must reject a changed retiring target set"
Assert-Contract ($externalCredentialRotationPolicy.changed_retiring_target_set_result -ceq "HIGH_RISK_ACTION_MISMATCH") "changed retiring target set error drifted"
Assert-Contract ($externalCredentialRotationPolicy.revoked_use_allowed -eq $false) "revoked external credential versions must never be usable"
Assert-Contract ($externalCredentialRotationPolicy.restore_never_increases_version_usability -eq $true) "restore must never increase external credential version usability"
Assert-Contract ($externalCredentialRotationPolicy.emergency_revocation_blocks_affected_runtime -eq $true) "emergency external credential revocation must fail affected runtime closed"

$keyManagement = $contract.key_management_policy
Assert-Contract (Test-SameSet @($keyManagement.PSObject.Properties.Name) @(
    "format_version",
    "purpose_domains",
    "production_required_active_key_purpose_domains",
    "production_activation_and_ready_recovery_require_exact_active_key_purpose_set_algorithm_entropy_and_crypto_preflight",
    "key_states",
    "cross_purpose_key_reuse_allowed",
    "hmac_algorithm",
    "symmetric_and_hmac_key_entropy_bits_min",
    "aead_policy",
    "keyed_verifier_policy",
    "symmetric_service_maximum_active_keys_per_purpose",
    "offline_recovery_maximum_active_keys_per_custodian",
    "human_operator_attestation_maximum_active_keys_per_custodian",
    "offline_recovery_and_human_operator_attestation_keys_must_be_distinct",
    "minimum_active_offline_recovery_custodians",
    "minimum_active_human_operator_attestation_custodians",
    "custodian_key_revocation_is_never_blocked_by_minimum_readiness_floor",
    "confirmed_custodian_or_required_key_loss_below_readiness_appends_production_recovery_required_fence",
    "authoritative_registry_location",
    "monotonic_key_registry_generation_required",
    "rotation_and_revocation_ledger_backed_and_anchored",
    "restore_uses_current_external_registry_never_backup_copy",
    "restore_never_widens_key_state",
    "registry_temporarily_unavailable_result",
    "key_record_schema",
    "key_record_branches",
    "protected_record_key_id_fields",
    "secret_or_private_key_material_persisted_in_live_store_logs_backups_or_evidence",
    "public_verification_keys_only_in_authoritative_external_registry",
    "all_protected_records_bind_key_id",
    "new_writes_use_active_key_only",
    "verification_uses_record_bound_key_id",
    "rotation_moves_predecessor_to_verify_only",
    "verify_only_retained_until_last_reference_and_evidence_retention_expire",
    "immutable_protected_records_never_rewritten_for_key_rotation",
    "rotation_by_purpose",
    "confirmed_verifier_key_loss_or_revocation_invalidates_affected_sessions_tokens_or_device_credentials",
    "temporary_key_service_unavailable_result",
    "durable_chain_key_loss_blocks_restore_and_security_mutation",
    "backup_recovery_and_offline_authorization_keys_distinct",
    "compromise_response",
    "one_time_response_confirmed_key_loss_cleanup_by_operation",
    "one_time_response_temporary_key_outage_keeps_ciphertext_and_domain_state_for_exact_retry",
    "external_security_registry_retention_policy"
)) "key management policy schema drifted"
Assert-Contract ($keyManagement.format_version -eq 1) "key management policy format version must be 1"
Assert-Contract (Test-ExactSequence @($keyManagement.purpose_domains) @(
    "HIGH_RISK_REQUEST_HMAC",
    "SENSITIVE_REQUEST_DIGEST_HMAC",
    "RESTORE_CONTINUITY_ENVELOPE_HMAC",
    "RECOVERY_LEDGER_CHAIN_HMAC",
    "RECOVERY_LEDGER_RECORD_AEAD",
    "AUTH_SESSION_VERIFIER_PEPPER",
    "CSRF_TOKEN_VERIFIER_PEPPER",
    "ONE_TIME_TOKEN_VERIFIER_PEPPER",
    "ONE_TIME_RESPONSE_ENCRYPTION",
    "DEVICE_CREDENTIAL_VERIFIER_PEPPER",
    "SECRET_ENVELOPE_ENCRYPTION",
    "BACKUP_RECOVERY_ENCRYPTION",
    "OFFLINE_RECOVERY_AUTHENTICATION",
    "HUMAN_OPERATOR_ATTESTATION_SIGNATURE",
    "DISASTER_ENVELOPE_NONCE_HMAC",
    "OPERATIONAL_FENCE_HMAC",
    "PRODUCTION_READINESS_NONCE_HMAC",
    "EMERGENCY_AUTHORITY_REDUCTION_NONCE_HMAC"
)) "key purpose-domain registry drifted"
Assert-Contract (Test-ExactSequence @($keyManagement.production_required_active_key_purpose_domains) @($keyManagement.purpose_domains)) "production readiness must require the complete key-purpose registry"
Assert-Contract (Test-ExactSequence @($keyManagement.key_states) @("ACTIVE", "VERIFY_ONLY", "RETIRED", "REVOKED")) "key lifecycle states drifted"
Assert-Contract ($keyManagement.cross_purpose_key_reuse_allowed -eq $false) "keys must never be reused across purpose domains"
Assert-Contract ($keyManagement.hmac_algorithm -ceq "HMAC-SHA-256") "service HMAC algorithm drifted"
Assert-Contract ($keyManagement.symmetric_and_hmac_key_entropy_bits_min -eq 256) "symmetric and HMAC keys require at least 256 bits"
Assert-Contract ($keyManagement.production_activation_and_ready_recovery_require_exact_active_key_purpose_set_algorithm_entropy_and_crypto_preflight -eq $true) "production readiness must preflight the exact key-purpose set"
Assert-Contract ($keyManagement.symmetric_service_maximum_active_keys_per_purpose -eq 1) "each symmetric service key purpose must have exactly one active write key"
Assert-Contract ($keyManagement.offline_recovery_maximum_active_keys_per_custodian -eq 1) "each recovery custodian must have at most one active signing key"
Assert-Contract ($keyManagement.human_operator_attestation_maximum_active_keys_per_custodian -eq 1) "each human-attestation custodian must have at most one active signing key"
Assert-Contract ($keyManagement.offline_recovery_and_human_operator_attestation_keys_must_be_distinct -eq $true) "offline recovery and human-attestation keys must be distinct"
Assert-Contract ($keyManagement.minimum_active_offline_recovery_custodians -eq 3) "offline recovery must retain at least three active custodians"
Assert-Contract ($keyManagement.minimum_active_human_operator_attestation_custodians -eq 3) "human identity attestation must retain at least three active custodians"
Assert-Contract ($keyManagement.custodian_key_revocation_is_never_blocked_by_minimum_readiness_floor -eq $true) "compromised custodian keys must remain revocable"
Assert-Contract ($keyManagement.confirmed_custodian_or_required_key_loss_below_readiness_appends_production_recovery_required_fence -eq $true) "required key loss must fence production"
Assert-Contract ($keyManagement.authoritative_registry_location -ceq "EXTERNAL_KEYSTORE_AND_MONOTONIC_ANCHOR") "key-state registry must remain externally anchored"
Assert-Contract (
    ($keyManagement.registry_temporarily_unavailable_result.error_code -ceq "KEY_SERVICE_UNAVAILABLE") -and
    ($keyManagement.registry_temporarily_unavailable_result.state_effect -ceq "CREDENTIAL_AND_DOMAIN_STATE_UNCHANGED") -and
    ($keyManagement.registry_temporarily_unavailable_result.retryable -eq $true)
) "key-registry outage must fail closed without changing credential state"
Assert-Contract (Test-ExactSequence @($keyManagement.key_record_schema) @("key_id", "purpose_domain", "algorithm", "version", "state", "registry_generation", "custodian_id", "public_verification_key", "created_at", "activated_at", "verify_only_until", "retired_at", "revoked_at")) "key record schema drifted"
$aeadPolicy = $keyManagement.aead_policy
Assert-Contract ($aeadPolicy.algorithm -ceq "AES-256-GCM") "AEAD algorithm drifted"
Assert-Contract (($aeadPolicy.key_entropy_bits -eq 256) -and ($aeadPolicy.nonce_bits -eq 96) -and ($aeadPolicy.tag_bits -eq 128)) "AEAD key, nonce or tag size drifted"
Assert-Contract ($aeadPolicy.nonce_unique_per_key_required -eq $true) "AEAD nonce uniqueness is mandatory"
Assert-Contract ($aeadPolicy.nonce_generation_and_reservation_atomic_per_key -eq $true) "AEAD nonce reservation must be atomic per key"
Assert-Contract ($aeadPolicy.associated_data_canonicalization -ceq "RFC8785_JCS_AFTER_STRICT_TYPED_PARSE") "AEAD associated-data canonicalization drifted"
Assert-Contract ($aeadPolicy.decrypt_reconstructs_and_authenticates_complete_canonical_associated_data_not_stored_hash_alone -eq $true) "AEAD decrypt must authenticate reconstructed complete associated data"
Assert-Contract (Test-SameSet @($aeadPolicy.associated_data_domain_separator_by_purpose.PSObject.Properties.Name) @("RECOVERY_LEDGER_RECORD_AEAD", "ONE_TIME_RESPONSE_ENCRYPTION", "SECRET_ENVELOPE_ENCRYPTION", "BACKUP_RECOVERY_ENCRYPTION")) "AEAD purpose-domain separators drifted"
Assert-Contract (Test-ExactSequence @($aeadPolicy.record_schema) @("ciphertext", "nonce", "authentication_tag", "key_id", "associated_data_hash")) "AEAD record schema drifted"

$keyedVerifierPolicy = $keyManagement.keyed_verifier_policy
Assert-Contract ($keyedVerifierPolicy.algorithm -ceq "HMAC-SHA-256") "keyed verifier algorithm drifted"
Assert-Contract ($keyedVerifierPolicy.canonical_input_encoding -ceq "DOMAIN_SEPARATED_LENGTH_PREFIXED_TYPED_BINARY_ENCODING") "keyed verifier input encoding drifted"
Assert-Contract ($keyedVerifierPolicy.record_bound_key_id_required -eq $true) "keyed verifiers must bind the exact key ID"
Assert-Contract (Test-SameSet @($keyedVerifierPolicy.purpose_by_record.PSObject.Properties.Name) @("BootstrapGrant", "AuthSession.session", "AuthSession.csrf", "PasswordResetToken", "RecoveryPasswordSetupGrant", "DeviceEnrollment", "DeviceCredential")) "keyed verifier record registry drifted"
Assert-Contract ($keyedVerifierPolicy.purpose_by_record."AuthSession.csrf" -ceq "CSRF_TOKEN_VERIFIER_PEPPER") "CSRF verifier purpose drifted"
Assert-Contract ($keyedVerifierPolicy.purpose_by_record.DeviceCredential -ceq "DEVICE_CREDENTIAL_VERIFIER_PEPPER") "device verifier purpose drifted"
Assert-Contract ([string]$keyedVerifierPolicy.input_by_record.PasswordResetToken -like "*issuance_kind*target_channel_event_id*") "password reset verifier must bind issuance kind and target channel"
Assert-Contract ($keyedVerifierPolicy.cross_record_type_tenant_deployment_or_subject_verifier_substitution_result -ceq "AUTHENTICATION_REQUIRED") "cross-record verifier substitution must fail closed"
$protectedKeyFields = $keyManagement.protected_record_key_id_fields
Assert-Contract (Test-SameSet @($protectedKeyFields.PSObject.Properties.Name) @(
    "BootstrapGrant",
    "AuthSession",
    "PasswordResetToken",
    "DeviceEnrollment",
    "DeviceCredential",
    "IdempotencyRecord",
    "DirectOperationAuthorization",
    "HighRiskAction",
    "SecretVersion",
    "OneTimeSecretResponseReplay",
    "RecoveryPasswordSetupGrant",
    "RecoverySecurityLedgerRecord",
    "RestoreContinuityEnvelope",
    "HumanOperatorIdentityAttestation",
    "HumanOperatorUserBinding",
    "DisasterRecoveryAuthorizationEnvelope",
    "DisasterEnvelopeNonceRecord",
    "ExternalOperationalFenceRecord",
    "ProductionReadinessRecoveryAuthorization",
    "ProductionReadinessNonceRecord",
    "EmergencyAuthorityReductionAuthorization",
    "EmergencyAuthorityReductionNonceRecord",
    "ExternalAuthorityRevocationTombstone",
    "CryptographicRootRecoveryAuthorization",
    "ExternalRecoveryAudit",
    "ExternalProductionReadinessRecoveryAudit",
    "ExternalCryptographicRootRecoveryAudit",
    "BackupManifest"
)) "protected-record key ID registry drifted"
Assert-Contract ($protectedKeyFields.BootstrapGrant -ceq "verifier_key_id") "BootstrapGrant verifier key ID is not frozen"
Assert-Contract (Test-ExactSequence @($protectedKeyFields.AuthSession) @("session_verifier_key_id", "csrf_verifier_key_id")) "AuthSession verifier key IDs are not frozen"
Assert-Contract ($protectedKeyFields.PasswordResetToken -ceq "verifier_key_id") "PasswordResetToken verifier key ID is not frozen"
Assert-Contract ($protectedKeyFields.DeviceEnrollment -ceq "verifier_key_id") "DeviceEnrollment verifier key ID is not frozen"
Assert-Contract ($protectedKeyFields.DeviceCredential -ceq "verifier_key_id") "DeviceCredential verifier key ID is not frozen"
Assert-Contract ($protectedKeyFields.IdempotencyRecord -ceq "sensitive_digest_key_id") "IdempotencyRecord sensitive digest key ID is not frozen"
Assert-Contract ($protectedKeyFields.DirectOperationAuthorization -ceq "request_hmac_key_id") "DirectOperationAuthorization request HMAC key ID is not frozen"
Assert-Contract ($protectedKeyFields.HighRiskAction -ceq "request_hmac_key_id") "HighRiskAction request HMAC key ID is not frozen"
Assert-Contract ($protectedKeyFields.SecretVersion -ceq "envelope_encryption_key_id") "SecretVersion envelope key ID is not frozen"
Assert-Contract ($protectedKeyFields.OneTimeSecretResponseReplay -ceq "response_encryption_key_id") "one-time response replay key ID is not frozen"
Assert-Contract ($protectedKeyFields.RecoveryPasswordSetupGrant -ceq "verifier_key_id") "recovery password setup grant key ID is not frozen"
Assert-Contract (Test-ExactSequence @($protectedKeyFields.RecoverySecurityLedgerRecord) @("chain_hmac_key_id", "record_aead_key_id")) "recovery-ledger record key IDs drifted"
Assert-Contract ($protectedKeyFields.RestoreContinuityEnvelope -ceq "envelope_hmac_key_id") "restore-continuity envelope key ID is not frozen"
Assert-Contract (Test-ExactSequence @($protectedKeyFields.HumanOperatorIdentityAttestation) @("custodian_registry_generation", "custodian_signature_key_ids_sorted_distinct")) "human identity attestation key bindings drifted"
Assert-Contract (Test-ExactSequence @($protectedKeyFields.HumanOperatorUserBinding) @("custodian_registry_generation", "custodian_signature_key_ids_sorted_distinct")) "human user binding key bindings drifted"
Assert-Contract (Test-ExactSequence @($protectedKeyFields.DisasterRecoveryAuthorizationEnvelope) @("custodian_registry_version", "custodian_signature_key_ids_sorted_distinct")) "disaster-recovery signature key bindings drifted"
Assert-Contract ($protectedKeyFields.DisasterEnvelopeNonceRecord -ceq "nonce_hmac_key_id") "disaster nonce key binding drifted"
Assert-Contract ($protectedKeyFields.ExternalOperationalFenceRecord -ceq "fence_hmac_key_id") "operational fence key binding drifted"
Assert-Contract (Test-ExactSequence @($protectedKeyFields.ProductionReadinessRecoveryAuthorization) @("offline_recovery_signature_key_ids_sorted_distinct", "human_attestation_signature_key_ids_sorted_distinct")) "production readiness authorization key bindings drifted"
Assert-Contract ($protectedKeyFields.ProductionReadinessNonceRecord -ceq "nonce_hmac_key_id") "production readiness nonce key binding drifted"
Assert-Contract ($protectedKeyFields.EmergencyAuthorityReductionAuthorization -ceq "signature_key_ids_sorted_distinct") "emergency authority reduction key binding drifted"
Assert-Contract ($protectedKeyFields.EmergencyAuthorityReductionNonceRecord -ceq "nonce_hmac_key_id") "emergency authority reduction nonce key binding drifted"
Assert-Contract ($protectedKeyFields.ExternalAuthorityRevocationTombstone -ceq "fence_hmac_key_id") "external authority tombstone key binding drifted"
Assert-Contract ($protectedKeyFields.CryptographicRootRecoveryAuthorization -ceq "signature_key_ids_sorted_distinct") "cryptographic root recovery key binding drifted"
Assert-Contract (Test-ExactSequence @($protectedKeyFields.ExternalRecoveryAudit) @("custodian_registry_generation", "custodian_signature_key_ids_sorted_distinct")) "external recovery audit key bindings drifted"
Assert-Contract (Test-ExactSequence @($protectedKeyFields.ExternalProductionReadinessRecoveryAudit) @("offline_recovery_signature_key_ids_sorted_distinct", "human_attestation_signature_key_ids_sorted_distinct")) "external production-readiness recovery audit key bindings drifted"
Assert-Contract (Test-ExactSequence @($protectedKeyFields.ExternalCryptographicRootRecoveryAudit) @("custodian_registry_generation", "custodian_signature_key_ids_sorted_distinct")) "external cryptographic-root recovery audit key bindings drifted"
Assert-Contract (Test-ExactSequence @($protectedKeyFields.BackupManifest) @("recovery_encryption_key_id", "ledger_chain_hmac_key_id", "ledger_record_aead_key_id")) "backup manifest key IDs drifted"
Assert-Contract ($keyManagement.secret_or_private_key_material_persisted_in_live_store_logs_backups_or_evidence -eq $false) "key material must remain outside live storage, logs, backups and evidence"
Assert-Contract ($keyManagement.public_verification_keys_only_in_authoritative_external_registry -eq $true) "public verification keys must come only from the authoritative registry"
foreach ($trueField in @(
    "monotonic_key_registry_generation_required",
    "rotation_and_revocation_ledger_backed_and_anchored",
    "restore_uses_current_external_registry_never_backup_copy",
    "restore_never_widens_key_state",
    "all_protected_records_bind_key_id",
    "new_writes_use_active_key_only",
    "verification_uses_record_bound_key_id",
    "rotation_moves_predecessor_to_verify_only",
    "verify_only_retained_until_last_reference_and_evidence_retention_expire",
    "immutable_protected_records_never_rewritten_for_key_rotation",
    "confirmed_verifier_key_loss_or_revocation_invalidates_affected_sessions_tokens_or_device_credentials",
    "durable_chain_key_loss_blocks_restore_and_security_mutation",
    "backup_recovery_and_offline_authorization_keys_distinct"
)) {
    Assert-Contract ($keyManagement.$trueField -eq $true) "key management policy $trueField must remain true"
}
Assert-Contract (
    ($keyManagement.temporary_key_service_unavailable_result.error_code -ceq "KEY_SERVICE_UNAVAILABLE") -and
    ($keyManagement.temporary_key_service_unavailable_result.state_effect -ceq "CREDENTIAL_AND_DOMAIN_STATE_UNCHANGED") -and
    ($keyManagement.temporary_key_service_unavailable_result.retryable -eq $true)
) "temporary key outage must not mutate credential state"
$rotationByPurpose = $keyManagement.rotation_by_purpose
Assert-Contract (Test-SameSet @($rotationByPurpose.PSObject.Properties.Name) @(
    "request_hmacs",
    "continuity_envelope_hmac",
    "recovery_ledger_chain_hmac",
    "recovery_ledger_record_aead",
    "session_csrf_token_device_verifiers",
    "one_time_response_encryption",
    "secret_envelope_encryption",
    "backup_recovery_encryption",
    "offline_recovery_authentication",
    "human_operator_attestation_signature",
    "disaster_envelope_nonce_hmac",
    "operational_fence_hmac",
    "production_readiness_nonce_hmac",
    "emergency_authority_reduction_nonce_hmac"
)) "purpose-specific key rotation registry drifted"
Assert-Contract ($rotationByPurpose.request_hmacs -ceq "NEW_WRITES_ACTIVE_OLD_VERIFY_ONLY_UNTIL_LAST_REFERENCE_AND_EVIDENCE_RETENTION") "request HMAC rotation semantics drifted"
Assert-Contract ($rotationByPurpose.continuity_envelope_hmac -ceq "NEW_ENVELOPES_ACTIVE_OLD_VERIFY_ONLY_UNTIL_CUTOVER_AND_EVIDENCE_RETENTION") "continuity envelope HMAC rotation semantics drifted"
Assert-Contract ($rotationByPurpose.recovery_ledger_chain_hmac -ceq "APPEND_KEY_ROTATION_RECORD_RETAIN_OLD_VERIFY_KEY_NO_CHAIN_REWRITE") "ledger chain HMAC rotation must not rewrite history"
Assert-Contract ($rotationByPurpose.recovery_ledger_record_aead -ceq "APPEND_WRAPPED_DEK_METADATA_OR_RETAIN_DECRYPT_KEY_NO_RECORD_REWRITE") "ledger record AEAD rotation must not rewrite history"
Assert-Contract ($rotationByPurpose.session_csrf_token_device_verifiers -ceq "VERIFY_BOUND_KEY_UNTIL_ARTIFACT_EXPIRY_OR_CONTROLLED_REVOCATION") "verifier-key rotation semantics drifted"
Assert-Contract ($rotationByPurpose.one_time_response_encryption -ceq "RETAIN_BOUND_KEY_AT_MOST_FIVE_MINUTES_THEN_DESTROY_CIPHERTEXT") "one-time response key rotation semantics drifted"
Assert-Contract ($rotationByPurpose.secret_envelope_encryption -ceq "CREATE_SUCCESSOR_VERSION_OR_AUTHENTICATED_DEK_REWRAP_WITHOUT_PERSISTING_ANY_PLAINTEXT_DERIVED_DETERMINISTIC_HASH") "Secret envelope key rotation semantics drifted"
Assert-Contract ($rotationByPurpose.backup_recovery_encryption -ceq "PER_BUNDLE_KEY_ID_RETAIN_DECRYPT_KEY_THROUGH_BUNDLE_RETENTION") "backup recovery key rotation semantics drifted"
Assert-Contract ($rotationByPurpose.offline_recovery_authentication -ceq "ROTATE_PER_CUSTODIAN_KEY_AND_ANCHOR_REGISTRY_VERSION") "offline recovery signing-key rotation semantics drifted"
Assert-Contract (Test-SameSet @($keyManagement.compromise_response.PSObject.Properties.Name) @(
    "high_risk_request_hmac",
    "sensitive_request_digest_hmac",
    "restore_continuity_envelope_hmac",
    "recovery_ledger",
    "session_csrf_or_token_verifier",
    "device_verifier",
    "one_time_response_encryption",
    "secret_encryption",
    "backup_recovery",
    "offline_recovery_authentication",
    "human_operator_attestation_signature",
    "disaster_envelope_nonce_hmac",
    "operational_fence_hmac",
    "production_readiness_nonce_hmac",
    "emergency_authority_reduction_nonce_hmac"
)) "key compromise response registry drifted"
Assert-Contract ($keyManagement.compromise_response.high_risk_request_hmac -ceq "FAIL_PENDING_ACTIONS_KEY_EPOCH_CHANGED") "high-risk request HMAC compromise response drifted"
Assert-Contract ($keyManagement.compromise_response.recovery_ledger -ceq "FREEZE_SECURITY_MUTATION_AND_RESTORE_INCIDENT_REQUIRED") "recovery-ledger key compromise response drifted"
Assert-Contract ($keyManagement.compromise_response.session_csrf_or_token_verifier -ceq "REVOKE_AFFECTED_AUTHENTICATION_EPOCHS") "session/token verifier compromise response drifted"
Assert-Contract ($keyManagement.compromise_response.device_verifier -ceq "REENROLL_REQUIRED") "device verifier compromise response drifted"
Assert-Contract ($keyManagement.compromise_response.secret_encryption -ceq "SECRET_ROTATION_REQUIRED") "Secret encryption compromise response drifted"
Assert-Contract ($keyManagement.compromise_response.backup_recovery -ceq "BACKUP_UNRECOVERABLE_UNTIL_AUTHORIZED_KEY_RECOVERY") "backup recovery compromise response drifted"
Assert-Contract ($keyManagement.compromise_response.offline_recovery_authentication -ceq "DISABLE_CUSTODIAN_KEY_AND_REQUIRE_FRESH_QUORUM") "offline recovery key compromise response drifted"

$purposeDomainReferences = [System.Collections.Generic.List[object]]::new()
function Find-PurposeDomainReferences {
    param(
        [AllowNull()][object]$Value,
        [string]$Path
    )
    if ($null -eq $Value) {
        return
    }
    if ($Value -is [System.Management.Automation.PSCustomObject]) {
        foreach ($property in $Value.PSObject.Properties) {
            $propertyPath = if ([string]::IsNullOrWhiteSpace($Path)) { $property.Name } else { "$Path.$($property.Name)" }
            if (($property.Name -match "purpose_domain$") -and ($property.Value -is [string])) {
                $script:purposeDomainReferences.Add([pscustomobject]@{ Path = $propertyPath; Value = [string]$property.Value })
            }
            Find-PurposeDomainReferences -Value $property.Value -Path $propertyPath
        }
        return
    }
    if (($Value -is [System.Collections.IEnumerable]) -and -not ($Value -is [string])) {
        $index = 0
        foreach ($item in $Value) {
            Find-PurposeDomainReferences -Value $item -Path "$Path[$index]"
            $index++
        }
    }
}
Find-PurposeDomainReferences -Value $contract -Path ""
foreach ($reference in $purposeDomainReferences) {
    Assert-Contract ($keyManagement.purpose_domains -contains $reference.Value) "unknown key purpose domain $($reference.Value) at $($reference.Path)"
}

Assert-Contract (Test-SameSet @($contract.storage.PSObject.Properties.Name) @("embedded", "external", "backup", "recovery_security_ledger")) "storage policy schema differs from the frozen contract"
Assert-Contract (Test-SameSet @($contract.storage.embedded.PSObject.Properties.Name) @("engine", "minimum_version", "journal_mode", "synchronous", "foreign_keys", "active_control_plane_instances", "network_filesystem_allowed")) "embedded storage schema drifted"
Assert-Contract ($contract.storage.embedded.engine -ceq "SQLite") "embedded engine must be SQLite"
Assert-Contract ($contract.storage.embedded.minimum_version -ceq "3.45") "embedded SQLite minimum version must be 3.45"
Assert-Contract ($contract.storage.embedded.journal_mode -ceq "WAL") "embedded SQLite must use WAL"
Assert-Contract ($contract.storage.embedded.synchronous -ceq "FULL") "embedded SQLite must use synchronous FULL"
Assert-Contract ($contract.storage.embedded.foreign_keys -eq $true) "embedded SQLite foreign keys must be enabled"
Assert-Contract ($contract.storage.embedded.active_control_plane_instances -eq 1) "embedded profile must have one active control-plane instance"
Assert-Contract ($contract.storage.embedded.network_filesystem_allowed -eq $false) "embedded SQLite must not use network storage"
Assert-Contract (Test-SameSet @($contract.storage.external.PSObject.Properties.Name) @("engine", "major_version", "current_supported_minor_required", "certification_status")) "external storage schema drifted"
Assert-Contract ($contract.storage.external.engine -ceq "PostgreSQL") "external control-plane store must be PostgreSQL"
Assert-Contract ($contract.storage.external.major_version -eq 16) "external PostgreSQL major must be 16"
Assert-Contract ($contract.storage.external.current_supported_minor_required -eq $true) "external PostgreSQL must require a supported minor"
Assert-Contract ($contract.storage.external.certification_status -ceq "UNVERIFIED") "external PostgreSQL must remain UNVERIFIED in P1.0"
Assert-Contract (Test-SameSet @($contract.storage.backup.PSObject.Properties.Name) @(
    "backend",
    "separate_mount_required_for_production",
    "schedule_minutes",
    "retention_hourly",
    "retention_daily",
    "retention_weekly",
    "rpo_minutes_target",
    "rto_minutes_target",
    "restore_in_place",
    "recovery_key_inside_bundle",
    "bundle_encryption",
    "bundle_encryption_record_schema",
    "bundle_encryption_nonce_unique_per_key",
    "bundle_encryption_associated_data_binds_manifest_hash_schema_product_and_ledger_heads",
    "password_hashes_and_secret_ciphertext_inside_encrypted_bundle",
    "manifest_key_ids",
    "manifest_forbidden_fields"
)) "backup policy schema drifted"
Assert-Contract ($contract.storage.backup.backend -ceq "filesystem_bundle") "backup backend must be a filesystem bundle"
Assert-Contract ($contract.storage.backup.separate_mount_required_for_production -eq $true) "production backup must use a separate mount"
Assert-Contract ($contract.storage.backup.schedule_minutes -eq 60) "default backup schedule must be hourly"
Assert-Contract ($contract.storage.backup.retention_hourly -eq 24) "hourly backup retention must be 24"
Assert-Contract ($contract.storage.backup.retention_daily -eq 7) "daily backup retention must be 7"
Assert-Contract ($contract.storage.backup.retention_weekly -eq 4) "weekly backup retention must be 4"
Assert-Contract ($contract.storage.backup.rpo_minutes_target -eq 60) "RPO target must be 60 minutes"
Assert-Contract ($contract.storage.backup.rto_minutes_target -eq 120) "RTO target must be 120 minutes"
Assert-Contract ($contract.storage.backup.restore_in_place -eq $false) "restore must not overwrite active storage"
Assert-Contract ($contract.storage.backup.recovery_key_inside_bundle -eq $false) "recovery key must remain outside the backup bundle"
Assert-Contract ($contract.storage.backup.bundle_encryption -ceq "AEAD_AES_256_GCM") "backup bundle must use the frozen AEAD profile"
Assert-Contract ($contract.storage.backup.password_hashes_and_secret_ciphertext_inside_encrypted_bundle -eq $true) "password verifiers and Secret ciphertext must stay inside the encrypted bundle"
Assert-Contract (Test-ExactSequence @($contract.storage.backup.manifest_key_ids) @("recovery_encryption_key_id", "ledger_chain_hmac_key_id", "ledger_record_aead_key_id")) "backup manifest key ID bindings drifted"
$requiredManifestForbidden = @("password", "password_hash", "secret_value", "token", "device_credential", "database_dsn", "recovery_key")
Assert-Contract (Test-ExactSequence @($contract.storage.backup.manifest_forbidden_fields) $requiredManifestForbidden) "backup manifest forbidden fields are incomplete"

$ledger = $contract.storage.recovery_security_ledger
Assert-Contract (Test-SameSet @($ledger.PSObject.Properties.Name) @(
    "format_version",
    "append_only",
    "chain_algorithm",
    "chain_hmac_purpose_domain",
    "chain_verification_requires_record_bound_key_id_and_exact_purpose",
    "chain_canonicalization",
    "chain_domain_separator",
    "chain_hmac_input",
    "duplicate_json_members_or_non_finite_numbers_result",
    "record_encryption",
    "record_encryption_purpose_domain",
    "record_decryption_requires_record_bound_key_id_and_exact_purpose",
    "record_encryption_schema",
    "record_encryption_nonce_unique_per_key",
    "record_encryption_associated_data_binds_sequence_state_subject_mutation_and_chain_key_id",
    "record_key_ids",
    "key_outside_live_store_and_backup_root",
    "ledger_outside_live_store_and_backup_root",
    "anchor_outside_live_store_backup_root_and_ledger",
    "anchor_type",
    "production_anchor_required",
    "restore_never_overwrites_replays_or_prunes_ledger",
    "record_states",
    "security_mutation_protocol",
    "ledger_backed_mutations",
    "unresolved_prepared_result",
    "role_scope_snapshot_schema",
    "user_identity_snapshot_schema",
    "retiring_applied_target_set_schema",
    "tracked_security_facts",
    "backup_manifest_binds",
    "restore_plan_and_approval_bind_current_ledger_head",
    "execute_requires_unchanged_current_ledger_head",
    "post_restore_checkpoint_required_before_completed",
    "restore_user_rules",
    "restore_device_rules",
    "restore_secret_rules",
    "restore_finereport_rules",
    "restore_degraded_credential_rules",
    "restore_token_rules",
    "restore_approval_rules",
    "restore_continuity",
    "missing_stale_or_unverifiable_result"
)) "recovery security ledger schema differs from the frozen contract"
Assert-Contract ($ledger.format_version -eq 1) "recovery security ledger format version must be 1"
Assert-Contract ($ledger.append_only -eq $true) "recovery security ledger must be append only"
Assert-Contract ($ledger.chain_algorithm -ceq "HMAC-SHA-256") "recovery security ledger chain must be authenticated"
Assert-Contract ($ledger.chain_hmac_purpose_domain -ceq "RECOVERY_LEDGER_CHAIN_HMAC") "recovery ledger chain purpose drifted"
Assert-Contract ($ledger.chain_verification_requires_record_bound_key_id_and_exact_purpose -eq $true) "recovery ledger chain must bind the exact key purpose"
Assert-Contract ($ledger.chain_canonicalization -ceq "RFC8785_JCS_AFTER_STRICT_TYPED_PARSE") "recovery ledger canonicalization drifted"
Assert-Contract ($ledger.duplicate_json_members_or_non_finite_numbers_result -ceq "CRYPTOGRAPHIC_INTEGRITY_FAILURE") "ambiguous recovery ledger JSON must fail integrity verification"
Assert-Contract ($ledger.record_encryption -ceq "AEAD_AES_256_GCM") "recovery security ledger records must be AEAD protected"
Assert-Contract ($ledger.record_encryption_purpose_domain -ceq "RECOVERY_LEDGER_RECORD_AEAD") "recovery ledger record-encryption purpose drifted"
Assert-Contract ($ledger.record_decryption_requires_record_bound_key_id_and_exact_purpose -eq $true) "recovery ledger decrypt must bind the exact key purpose"
Assert-Contract ($ledger.record_encryption_nonce_unique_per_key -eq $true) "recovery ledger record nonce must be unique per key"
Assert-Contract ($ledger.record_encryption_associated_data_binds_sequence_state_subject_mutation_and_chain_key_id -eq $true) "recovery ledger record associated data is incomplete"
Assert-Contract (Test-ExactSequence @($ledger.record_key_ids) @("chain_hmac_key_id", "record_aead_key_id")) "recovery security ledger record key IDs drifted"
foreach ($ledgerTrueField in @(
    "key_outside_live_store_and_backup_root",
    "ledger_outside_live_store_and_backup_root",
    "anchor_outside_live_store_backup_root_and_ledger",
    "production_anchor_required",
    "restore_never_overwrites_replays_or_prunes_ledger",
    "restore_plan_and_approval_bind_current_ledger_head",
    "execute_requires_unchanged_current_ledger_head",
    "post_restore_checkpoint_required_before_completed"
)) {
    Assert-Contract ($ledger.$ledgerTrueField -eq $true) "recovery security ledger $ledgerTrueField must remain true"
}
Assert-Contract ($ledger.anchor_type -ceq "admin_controlled_monotonic_worm_or_keystore") "recovery security anchor type is not frozen"
Assert-Contract (Test-ExactSequence @($ledger.record_states) @("PREPARED", "COMMITTED", "ABORTED")) "recovery security ledger record states drifted"
Assert-Contract (Test-ExactSequence @($ledger.security_mutation_protocol) @("append_prepared_and_fsync", "commit_domain_row_with_ledger_sequence", "append_committed_and_advance_anchor")) "recovery security mutation protocol drifted"
Assert-Contract (Test-ExactSequence @($ledger.ledger_backed_mutations) @(
    "bootstrap_completion",
    "deployment_production_activation",
    "deployment_production_readiness_recovery",
    "emergency_authority_reduction_reconciliation",
    "cryptographic_readiness_root_recovery_reconciliation",
    "user_identity_create",
    "user_identity_fields_update",
    "user_enabled_state_change",
    "user_password_change",
    "user_role_scope_assignment_replace",
    "device_credential_family_create_from_enrollment_claim",
    "device_credential_family_rotation_expiry_or_revoke",
    "secret_record_create_or_rotate",
    "finereport_identity_binding_create_or_replace",
    "key_registry_rotation_or_revocation",
    "human_operator_identity_or_user_binding_or_eligibility_change"
)) "ledger-backed security mutation set drifted"
Assert-Contract ($ledger.unresolved_prepared_result -ceq "FAIL_CLOSED_FOR_SUBJECT") "unresolved ledger preparation must fail closed"
Assert-Contract (Test-ExactSequence @($ledger.role_scope_snapshot_schema) @(
    "user_id",
    "assignment_generation",
    "authorization_epoch",
    "role_catalog_version",
    "assignments_sorted_by_role_scope",
    "assignment.role_id",
    "assignment.scope_type",
    "assignment.scope_id"
)) "role/scope snapshot schema is incomplete"
Assert-Contract (Test-ExactSequence @($ledger.user_identity_snapshot_schema) @(
    "user_id",
    "tenant_id",
    "deployment_id",
    "normalized_username",
    "display_name",
    "enabled",
    "account_state_generation",
    "authentication_epoch",
    "authorization_epoch",
    "human_operator_person_id",
    "person_binding_generation",
    "person_eligibility_generation",
    "credential_material_excluded"
)) "user identity snapshot schema is incomplete"
Assert-Contract (Test-ExactSequence @($ledger.retiring_applied_target_set_schema) @(
    "subject_id",
    "credential_version_id",
    "targets_sorted_by_screen_and_release_target",
    "target.screen_id",
    "target.release_target_id",
    "target.credential_version_id",
    "set_hash",
    "retire_deadline"
)) "retiring applied-target set schema is incomplete"
Assert-Contract (Test-ExactSequence @($ledger.tracked_security_facts) @(
    "control_plane_security_epoch",
    "key_registry_generation",
    "key_state_snapshot_hash",
    "person_registry_generation",
    "person_registry_state_hash",
    "deployment_mode",
    "deployment_operational_posture",
    "operational_fence_generation",
    "operational_fence_evidence_hash",
    "bootstrap_completed",
    "user_enabled_state",
    "user_identity_snapshot",
    "user_account_state_generation",
    "user_authentication_epoch",
    "user_authorization_epoch",
    "user_human_operator_person_id",
    "user_person_binding_generation",
    "user_person_eligibility_generation",
    "user_person_eligibility_state",
    "user_role_scope_assignment_generation",
    "user_role_scope_assignment_snapshot",
    "user_role_scope_assignment_hash",
    "user_credential_generation",
    "user_password_state",
    "device_family_state",
    "device_family_generation",
    "device_family_active_credential_version",
    "device_family_revocation_epoch",
    "secret_record_security_generation",
    "secret_record_owner_scope",
    "secret_record_state",
    "secret_record_current_version",
    "secret_record_revocation_epoch",
    "secret_record_revocation_tombstone",
    "secret_version_authorization_state",
    "secret_retiring_applied_target_set_snapshot",
    "secret_retiring_applied_target_set_hash",
    "secret_retire_deadline",
    "finereport_binding_security_generation",
    "finereport_binding_screen_id",
    "finereport_binding_state",
    "finereport_binding_current_version",
    "finereport_binding_revocation_epoch",
    "finereport_binding_revocation_tombstone",
    "finereport_binding_version_authorization_state",
    "finereport_retiring_applied_target_set_snapshot",
    "finereport_retiring_applied_target_set_hash",
    "finereport_retire_deadline",
    "latest_chain_head"
)) "recovery security ledger tracked facts are incomplete"
Assert-Contract (Test-ExactSequence @($ledger.backup_manifest_binds) @(
    "security_ledger_sequence",
    "security_ledger_head_hash",
    "ledger_chain_hmac_key_id",
    "ledger_record_aead_key_id",
    "control_plane_epoch",
    "deployment_mode",
    "deployment_operational_posture",
    "operational_fence_generation",
    "operational_fence_evidence_hash",
    "activation_readiness_candidate_hash",
    "key_registry_generation",
    "key_state_snapshot_hash",
    "person_registry_generation",
    "person_registry_state_hash",
    "selected_admin_user_person_credential_authentication_and_eligibility_generations"
)) "backup manifest does not bind both recovery security ledger keys"
Assert-Contract (Test-SameSet @($ledger.restore_user_rules.PSObject.Properties.Name) @(
    "newer_disabled_state_wins",
    "maximum_authentication_epoch_wins",
    "latest_role_scope_assignment_snapshot_is_authoritative",
    "role_scope_reconciliation_mode",
    "restored_assignment_absent_from_latest_snapshot_removed",
    "unknown_role_scope_or_catalog_result",
    "missing_or_mismatched_assignment_snapshot_result",
    "user_missing_from_backup_result",
    "reconstructed_user_contains_credential_material",
    "reconstructed_identity_conflict_result",
    "credential_usable_and_staged_authenticated_admins_required_before_cutover_by_deployment_mode",
    "production_admins_must_have_distinct_current_active_attested_person_ids",
    "staged_auth_proofs_bind_person_registry_binding_and_eligibility_generations",
    "restore_uses_current_external_person_registry_and_never_backup_person_authority",
    "revoked_or_stale_person_mapping_result",
    "missing_admin_access_path_result",
    "older_password_generation_authentication_allowed",
    "older_password_generation_result",
    "online_restore_stale_or_missing_selected_admin_credentials_use_provisional_setup_grants",
    "normal_grants_require_original_four_eyes_action_to_bind_exact_admin_user_person_tuples_and_missing_generations",
    "normal_grant_plaintext_delivered_only_to_each_selected_target_person_local_one_time_no_store",
    "normal_grants_follow_same_provisional_state_machine_and_commit_only_with_cutover_anchor",
    "normal_grant_pre_pointer_abort_requires_fresh_high_risk_action_and_grants"
)) "restore user reconciliation schema drifted"
Assert-Contract ($ledger.restore_user_rules.newer_disabled_state_wins -eq $true) "newer disabled-user state must win after restore"
Assert-Contract ($ledger.restore_user_rules.maximum_authentication_epoch_wins -eq $true) "maximum authentication epoch must win after restore"
Assert-Contract ($ledger.restore_user_rules.latest_role_scope_assignment_snapshot_is_authoritative -eq $true) "latest role/scope snapshot must be authoritative after restore"
Assert-Contract ($ledger.restore_user_rules.role_scope_reconciliation_mode -ceq "REPLACE_NOT_MERGE") "role/scope restore reconciliation must replace rather than merge"
Assert-Contract ($ledger.restore_user_rules.restored_assignment_absent_from_latest_snapshot_removed -eq $true) "restored role assignments absent from the latest snapshot must be removed"
Assert-Contract (
    ($ledger.restore_user_rules.unknown_role_scope_or_catalog_result.subject_state -ceq "ROLE_RECONCILIATION_REQUIRED") -and
    ($ledger.restore_user_rules.unknown_role_scope_or_catalog_result.authorization_effect -ceq "DENY_ALL")
) "unknown role, scope or catalog versions must deny all permissions"
Assert-Contract (
    ($ledger.restore_user_rules.missing_or_mismatched_assignment_snapshot_result.subject_state -ceq "ROLE_RECONCILIATION_REQUIRED") -and
    ($ledger.restore_user_rules.missing_or_mismatched_assignment_snapshot_result.authorization_effect -ceq "DENY_ALL")
) "missing or mismatched role snapshots must deny all permissions"
Assert-Contract (
    ($ledger.restore_user_rules.user_missing_from_backup_result.recovery_action -ceq "RECONSTRUCT_IDENTITY_FROM_LEDGER") -and
    ($ledger.restore_user_rules.user_missing_from_backup_result.credential_state -ceq "RESET_REQUIRED")
) "a ledger-only user identity must be reconstructed without credentials and require reset"
Assert-Contract ($ledger.restore_user_rules.reconstructed_user_contains_credential_material -eq $false) "a reconstructed ledger-only user must never receive credential material"
Assert-Contract ($ledger.restore_user_rules.reconstructed_identity_conflict_result -ceq "IDENTITY_RECONCILIATION_CONFLICT") "a reconstructed user identity conflict must fail restore before cutover"
Assert-Contract (
    ($ledger.restore_user_rules.credential_usable_and_staged_authenticated_admins_required_before_cutover_by_deployment_mode.SETUP -eq 1) -and
    ($ledger.restore_user_rules.credential_usable_and_staged_authenticated_admins_required_before_cutover_by_deployment_mode.PRODUCTION_ACTIVE_ANY_POSTURE -eq 2) -and
    ($ledger.restore_user_rules.production_admins_must_have_distinct_current_active_attested_person_ids -eq $true)
) "restore cutover must prove the deployment-mode exact distinct usable admins against the staged store"
Assert-Contract ($ledger.restore_user_rules.missing_admin_access_path_result -ceq "AUTHENTICATABLE_PLATFORM_ADMIN_REQUIRED") "restore without required admin access paths must fail before cutover"
Assert-Contract ($ledger.restore_user_rules.older_password_generation_authentication_allowed -eq $false) "an older restored password verifier must never authenticate"
Assert-Contract ($ledger.restore_user_rules.older_password_generation_result -ceq "RESET_REQUIRED") "older restored password generations must require reset"
Assert-Contract (Test-SameSet @($ledger.restore_device_rules.PSObject.Properties.Name) @("maximum_family_revocation_epoch_wins", "revoked_family_remains_revoked", "older_or_mismatched_active_version_authentication_allowed", "older_or_mismatched_active_version_result", "reenroll_recovery_operation", "reenroll_requires_current_family_generation_ledger_head_and_four_eyes")) "restore device reconciliation schema drifted"
Assert-Contract ($ledger.restore_device_rules.maximum_family_revocation_epoch_wins -eq $true) "maximum device revocation epoch must win"
Assert-Contract ($ledger.restore_device_rules.revoked_family_remains_revoked -eq $true) "a revoked device family must remain revoked"
Assert-Contract ($ledger.restore_device_rules.older_or_mismatched_active_version_authentication_allowed -eq $false) "a predecessor or mismatched device version must never authenticate"
Assert-Contract ($ledger.restore_device_rules.older_or_mismatched_active_version_result -ceq "REENROLL_REQUIRED") "mismatched device versions must require re-enrollment"
Assert-Contract ($ledger.restore_device_rules.reenroll_recovery_operation -ceq "issueDeviceEnrollment") "device re-enrollment recovery operation drifted"
Assert-Contract ($ledger.restore_device_rules.reenroll_requires_current_family_generation_ledger_head_and_four_eyes -eq $true) "device re-enrollment recovery must bind current generation, ledger head and four eyes"
Assert-Contract (Test-SameSet @($ledger.restore_secret_rules.PSObject.Properties.Name) @("maximum_security_generation_wins", "authoritative_version_authorization_state_wins", "restored_version_cannot_gain_usability", "revoked_version_use_allowed", "retiring_use_scope", "retiring_target_set_snapshot_required", "missing_or_mismatched_retiring_target_set_result", "latest_version_missing_result", "mismatch_blocks")) "restore Secret reconciliation schema drifted"
Assert-Contract ($ledger.restore_secret_rules.maximum_security_generation_wins -eq $true) "maximum Secret security generation must win"
Assert-Contract ($ledger.restore_secret_rules.authoritative_version_authorization_state_wins -eq $true) "ledger-authoritative Secret version state must win"
Assert-Contract ($ledger.restore_secret_rules.restored_version_cannot_gain_usability -eq $true) "restore must never increase Secret version usability"
Assert-Contract ($ledger.restore_secret_rules.revoked_version_use_allowed -eq $false) "revoked Secret versions must never be usable"
Assert-Contract ($ledger.restore_secret_rules.retiring_use_scope -ceq "EXACT_PRE_ROTATION_APPLIED_TARGETS_UNTIL_DEADLINE") "retiring Secret use scope drifted"
Assert-Contract ($ledger.restore_secret_rules.retiring_target_set_snapshot_required -eq $true) "restore must require the canonical Secret retiring target-set snapshot"
Assert-Contract (
    ($ledger.restore_secret_rules.missing_or_mismatched_retiring_target_set_result.authorization_effect -ceq "DENY_ALL") -and
    ($ledger.restore_secret_rules.missing_or_mismatched_retiring_target_set_result.credential_state -ceq "SECRET_ROTATION_REQUIRED")
) "missing or mismatched Secret retiring target set must deny all use"
Assert-Contract ($ledger.restore_secret_rules.latest_version_missing_result -ceq "SECRET_ROTATION_REQUIRED") "missing latest Secret version must require rotation"
Assert-Contract (Test-ExactSequence @($ledger.restore_secret_rules.mismatch_blocks) @("new_release_create", "new_publish", "rollback", "new_runtime_delivery", "decrypt_outside_frozen_retiring_targets")) "Secret restore mismatch block set drifted"
Assert-Contract (Test-SameSet @($ledger.restore_finereport_rules.PSObject.Properties.Name) @("maximum_security_generation_wins", "authoritative_version_authorization_state_wins", "restored_binding_cannot_gain_usability", "revoked_binding_use_allowed", "retiring_use_scope", "retiring_target_set_snapshot_required", "missing_or_mismatched_retiring_target_set_result", "latest_binding_missing_result", "mismatch_blocks")) "restore FineReport reconciliation schema drifted"
Assert-Contract ($ledger.restore_finereport_rules.maximum_security_generation_wins -eq $true) "maximum FineReport binding security generation must win"
Assert-Contract ($ledger.restore_finereport_rules.authoritative_version_authorization_state_wins -eq $true) "ledger-authoritative FineReport binding-version state must win"
Assert-Contract ($ledger.restore_finereport_rules.restored_binding_cannot_gain_usability -eq $true) "restore must never increase FineReport binding-version usability"
Assert-Contract ($ledger.restore_finereport_rules.revoked_binding_use_allowed -eq $false) "revoked FineReport bindings must never be usable"
Assert-Contract ($ledger.restore_finereport_rules.retiring_use_scope -ceq "EXACT_PRE_ROTATION_APPLIED_TARGETS_UNTIL_DEADLINE") "retiring FineReport binding use scope drifted"
Assert-Contract ($ledger.restore_finereport_rules.retiring_target_set_snapshot_required -eq $true) "restore must require the canonical FineReport retiring target-set snapshot"
Assert-Contract (
    ($ledger.restore_finereport_rules.missing_or_mismatched_retiring_target_set_result.authorization_effect -ceq "DENY_ALL") -and
    ($ledger.restore_finereport_rules.missing_or_mismatched_retiring_target_set_result.credential_state -ceq "FINEREPORT_REBIND_REQUIRED")
) "missing or mismatched FineReport retiring target set must deny all use"
Assert-Contract ($ledger.restore_finereport_rules.latest_binding_missing_result -ceq "FINEREPORT_REBIND_REQUIRED") "missing latest FineReport binding must require replacement"
Assert-Contract (Test-ExactSequence @($ledger.restore_finereport_rules.mismatch_blocks) @("new_release_create", "new_publish", "rollback", "new_runtime_delivery", "decrypt_outside_frozen_retiring_targets")) "FineReport restore mismatch block set drifted"
$degradedCredentialRules = $ledger.restore_degraded_credential_rules
Assert-Contract (Test-SameSet @($degradedCredentialRules.PSObject.Properties.Name) @(
    "default_cutover_when_authoritative_material_missing",
    "default_missing_material_result",
    "explicit_mode",
    "requires_exact_missing_subject_set_in_restore_action",
    "authorization_requirements_by_mode",
    "confirmation",
    "affected_secret_state",
    "affected_finereport_state",
    "affected_secret_recovery_operation",
    "affected_finereport_recovery_operation",
    "affected_recovery_operations_require_current_generation_ledger_head_and_four_eyes",
    "affected_subjects_blocked",
    "unaffected_subjects_may_recover",
    "restore_plan_result_state"
)) "degraded credential recovery schema drifted"
Assert-Contract ($degradedCredentialRules.default_cutover_when_authoritative_material_missing -eq $false) "restore must not cut over by default when authoritative credential material is missing"
Assert-Contract ($degradedCredentialRules.default_missing_material_result -ceq "AUTHORITATIVE_CREDENTIAL_MATERIAL_MISSING") "missing authoritative credential material must return the stable restore conflict"
Assert-Contract ($degradedCredentialRules.explicit_mode -ceq "DEGRADED_CREDENTIAL_RECOVERY") "degraded credential recovery mode is not frozen"
Assert-Contract ($degradedCredentialRules.requires_exact_missing_subject_set_in_restore_action -eq $true) "degraded credential recovery must bind the exact missing subject set"
Assert-Contract (
    ($degradedCredentialRules.authorization_requirements_by_mode.NORMAL_API_FOUR_EYES -ceq "DIFFERENT_ACTIVE_ATTESTED_PERSON_HIGH_RISK_APPROVAL_BINDS_EXACT_MISSING_SUBJECT_SET") -and
    ($degradedCredentialRules.authorization_requirements_by_mode.LOCAL_DISASTER_QUORUM -ceq "TWO_OF_THREE_CUSTODIAN_ENVELOPE_BINDS_EXACT_MISSING_SUBJECT_SET_NO_HIGH_RISK_ACTION_OR_USER_APPROVAL")
) "degraded credential recovery must require the authorization-mode exact independent evidence"
Assert-Contract ($degradedCredentialRules.confirmation -ceq "RESTORE_DEGRADED_CREDENTIALS") "degraded credential recovery confirmation text drifted"
Assert-Contract ($degradedCredentialRules.affected_secret_state -ceq "SECRET_ROTATION_REQUIRED") "degraded Secret recovery state drifted"
Assert-Contract ($degradedCredentialRules.affected_finereport_state -ceq "FINEREPORT_REBIND_REQUIRED") "degraded FineReport recovery state drifted"
Assert-Contract ($degradedCredentialRules.affected_secret_recovery_operation -ceq "rotateSecret") "degraded Secret recovery operation drifted"
Assert-Contract ($degradedCredentialRules.affected_finereport_recovery_operation -ceq "putFineReportIdentityBinding") "degraded FineReport recovery operation drifted"
Assert-Contract ($degradedCredentialRules.affected_recovery_operations_require_current_generation_ledger_head_and_four_eyes -eq $true) "degraded credential repair must bind current generation, ledger head and four eyes"
Assert-Contract (Test-ExactSequence @($degradedCredentialRules.affected_subjects_blocked) @("decrypt", "new_release_create", "new_publish", "rollback", "new_runtime_delivery")) "degraded credential recovery block set drifted"
Assert-Contract ($degradedCredentialRules.unaffected_subjects_may_recover -eq $true) "degraded credential recovery must preserve unaffected subjects"
Assert-Contract ($degradedCredentialRules.restore_plan_result_state -ceq "COMPLETED_DEGRADED") "degraded credential recovery result state drifted"
Assert-Contract (Test-SameSet @($ledger.restore_token_rules.PSObject.Properties.Name) @(
    "all_auth_sessions_invalidated",
    "all_one_time_tokens_invalidated",
    "all_device_sessions_invalidated",
    "all_one_time_secret_response_replay_records_and_ciphertexts_destroyed",
    "restored_secret_result_idempotency_records_cannot_return_prior_plaintext",
    "claimed_device_credential_with_authenticated_possession_evidence_may_remain_active",
    "claimed_device_credential_without_authenticated_possession_evidence_becomes_ledger_backed_reenroll_required",
    "unreachable_pending_rotation_successor_revoked_and_predecessor_remains_active"
)) "restore token invalidation schema drifted"
Assert-Contract ($ledger.restore_token_rules.all_auth_sessions_invalidated -eq $true) "restore must invalidate all AuthSessions"
Assert-Contract ($ledger.restore_token_rules.all_one_time_tokens_invalidated -eq $true) "restore must invalidate all one-time tokens"
Assert-Contract ($ledger.restore_token_rules.all_device_sessions_invalidated -eq $true) "restore must invalidate all device sessions"
Assert-Contract (Test-SameSet @($ledger.restore_approval_rules.PSObject.Properties.Name) @("all_restored_pending_or_approved_high_risk_actions_result", "all_restored_config_approvals_require_new_epoch_validation_preview_and_approval", "historical_evidence_preserved")) "restore approval reconciliation schema drifted"
Assert-Contract (
    ($ledger.restore_approval_rules.all_restored_pending_or_approved_high_risk_actions_result.state -ceq "FAILED") -and
    ($ledger.restore_approval_rules.all_restored_pending_or_approved_high_risk_actions_result.failure_reason -ceq "RESTORE_EPOCH_CHANGED")
) "restored unfinished high-risk actions must fail"
Assert-Contract ($ledger.restore_approval_rules.all_restored_config_approvals_require_new_epoch_validation_preview_and_approval -eq $true) "restored config approvals must not remain executable"
Assert-Contract ($ledger.restore_approval_rules.historical_evidence_preserved -eq $true) "restore must preserve historical approval evidence"
Assert-Contract (Test-SameSet @($ledger.restore_continuity.PSObject.Properties.Name) @(
    "external_authenticated_envelope_required",
    "envelope_binds_authorization_evidence_and_ledger_prepared_sequence",
    "authorization_modes",
    "authorization_mode_xor_required",
    "recovery_source_modes",
    "recovery_source_mode_xor_required",
    "allowed_authorization_and_source_mode_combinations",
    "full_loss_requires_local_disaster_quorum",
    "local_disaster_with_online_source_requires_no_credential_usable_enabled_deployment_platform_admin",
    "normal_api_four_eyes_with_full_loss_forbidden",
    "online_source_requires_maintenance_barrier_live_head_and_retained_pointer",
    "full_loss_previous_store_pointer",
    "full_loss_security_audit_suffix",
    "full_loss_recovery_audit_source",
    "common_carried_forward_records",
    "normal_authorization_records",
    "disaster_authorization_records",
    "disaster_mode_fabricates_user_actor_or_approval",
    "provisional_admin_grant_sequence",
    "normal_mode_grants_only_when_selected_admin_backup_credentials_are_stale_or_missing",
    "disaster_mode_required_grants_follow_deployment_mode_cardinality",
    "carried_forward_records_initial_atomic_insert_and_verification_before_cutover",
    "payload_contains_secret_request_body",
    "restore_plan_authorization_schema",
    "envelope_authentication_algorithm",
    "envelope_authentication_purpose_domain",
    "envelope_canonicalization",
    "envelope_domain_separator",
    "envelope_hmac_input",
    "envelope_duplicate_json_members_or_non_finite_numbers_result",
    "envelope_schema",
    "envelope_ttl_minutes_max",
    "envelope_time_source",
    "clock_rollback_never_extends_envelope",
    "authorization_branch_field_rules",
    "admin_readiness_branch_field_rules",
    "same_branch_nullability_applies_to_restore_plan_continuity_envelope_and_cutover_record",
    "envelope_single_use_cutover_id_and_nonce",
    "startup_recomputes_and_verifies_envelope_payload_and_keys",
    "envelope_key_temporarily_unavailable_result",
    "envelope_invalid_replay_revoked_or_permanently_lost_key_result",
    "security_audit_suffix_policy_by_source_mode",
    "security_audit_suffix_insert_order_and_hash_verified",
    "security_audit_suffix_contains_complete_canonical_sanitized_events",
    "security_audit_suffix_schema",
    "security_audit_events_inserted_into_primary_audit_table_in_chain_order",
    "external_recovery_audit_policy",
    "missing_actor_user_reconstructed_from_ledger_identity_snapshot",
    "maintenance_lock_blocks_control_plane_and_device_writes_during_cutover",
    "staged_execution_records_committed_before_pointer",
    "external_visibility_rule_by_deployment_mode",
    "cutover_completion_mode_frozen_before_prepared",
    "cutover_record_states",
    "restore_cutover_record_schema",
    "continuity_envelope_protocol",
    "cutover_protocol",
    "every_production_restore_finalization_sets_or_keeps_recovery_required_until_separate_local_production_readiness_recovery",
    "restore_finalized_but_readiness_incomplete_keeps_external_serving_fenced_until_generic_production_readiness_recovery",
    "ready_fence_without_matching_restore_finalized_result_is_invalid_and_never_opens_serving",
    "post_restore_posture_by_deployment_mode",
    "pre_pointer_abort_requires_atomic_grant_set_cleanup_and_applicable_disaster_nonce_aborted_consumed_before_return",
    "ledger_anchor_committed_nonce_still_reserved_result",
    "nonce_committed_without_matching_ledger_anchor_result",
    "nonce_registry_unavailable_during_reconciliation_result",
    "finalization_transaction_records",
    "already_finalized_replay_result",
    "disaster_authorization_nonce_replay_result",
    "startup_reconciliation_idempotent",
    "anchor_committed_db_terminal_missing_result",
    "pointer_switched_anchor_not_committed_result",
    "ledger_committed_anchor_not_advanced_result",
    "anchor_unavailable_during_reconciliation_result",
    "online_previous_store_retained_until_committed_anchor",
    "online_crash_before_pointer_result",
    "full_loss_crash_before_pointer_result",
    "crash_after_pointer_before_anchor_result",
    "missing_or_mismatch_result_by_source_mode"
)) "restore continuity schema drifted"
Assert-Contract ($ledger.restore_continuity.external_authenticated_envelope_required -eq $true) "restore continuity must use an external authenticated envelope"
Assert-Contract ($ledger.restore_continuity.envelope_binds_authorization_evidence_and_ledger_prepared_sequence -eq $true) "restore continuity envelope must bind exact authorization evidence and ledger preparation"
Assert-Contract (Test-ExactSequence @($ledger.restore_continuity.authorization_modes) @("NORMAL_API_FOUR_EYES", "LOCAL_DISASTER_QUORUM")) "restore authorization modes drifted"
Assert-Contract ($ledger.restore_continuity.authorization_mode_xor_required -eq $true) "restore authorization mode must be exclusive"
Assert-Contract (Test-ExactSequence @($ledger.restore_continuity.recovery_source_modes) @("ONLINE_ACTIVE_STORE", "FULL_LOSS_ACTIVE_STORE_UNAVAILABLE")) "restore source modes drifted"
Assert-Contract ($ledger.restore_continuity.recovery_source_mode_xor_required -eq $true) "restore source mode must be exclusive"
Assert-Contract (Test-SameSet @($ledger.restore_continuity.allowed_authorization_and_source_mode_combinations.PSObject.Properties.Name) @("NORMAL_API_FOUR_EYES", "LOCAL_DISASTER_QUORUM")) "restore authorization/source mode combination schema drifted"
Assert-Contract (Test-ExactSequence @($ledger.restore_continuity.allowed_authorization_and_source_mode_combinations.NORMAL_API_FOUR_EYES) @("ONLINE_ACTIVE_STORE")) "normal restore authorization must remain online-source only"
Assert-Contract (Test-ExactSequence @($ledger.restore_continuity.allowed_authorization_and_source_mode_combinations.LOCAL_DISASTER_QUORUM) @("ONLINE_ACTIVE_STORE", "FULL_LOSS_ACTIVE_STORE_UNAVAILABLE")) "local disaster restore source modes drifted"
Assert-Contract ($ledger.restore_continuity.full_loss_requires_local_disaster_quorum -eq $true) "full-loss restore must require local disaster quorum"
Assert-Contract ($ledger.restore_continuity.local_disaster_with_online_source_requires_no_credential_usable_enabled_deployment_platform_admin -eq $true) "online-source local disaster restore must require absence of a credential-usable enabled platform admin"
Assert-Contract ($ledger.restore_continuity.normal_api_four_eyes_with_full_loss_forbidden -eq $true) "normal API four-eyes restore must remain forbidden for full loss"
Assert-Contract ($ledger.restore_continuity.online_source_requires_maintenance_barrier_live_head_and_retained_pointer -eq $true) "online restore must bind the barrier head and retained prior pointer"
Assert-Contract ($null -eq $ledger.restore_continuity.full_loss_previous_store_pointer) "full-loss restore must have no previous-store pointer"
Assert-Contract ($ledger.restore_continuity.full_loss_security_audit_suffix -ceq "EMPTY_BACKUP_HEAD_TO_BACKUP_HEAD") "full-loss restore must use the explicit empty audit suffix"
Assert-Contract ($ledger.restore_continuity.full_loss_recovery_audit_source -ceq "SIGNED_EXTERNAL_RECOVERY_AUDIT_THEN_NEW_STAGED_AUDIT_CHAIN") "full-loss recovery audit source drifted"
Assert-Contract (Test-ExactSequence @($ledger.restore_continuity.common_carried_forward_records) @(
    "RestorePlan",
    "ImmutableTypedCommand",
    "AsyncOperation",
    "OutboxRecord",
    "IdempotencyRecord",
    "RestoreCutoverRecord",
    "SecurityAuditSuffix"
)) "restore continuity common record set drifted"
Assert-Contract (Test-ExactSequence @($ledger.restore_continuity.normal_authorization_records) @("HighRiskAction", "HighRiskApproval", "OptionalRecoveryPasswordSetupGrantProvisionalEvidence")) "normal restore authorization record set drifted"
Assert-Contract (Test-ExactSequence @($ledger.restore_continuity.disaster_authorization_records) @("DisasterRecoveryAuthorizationEnvelope", "ProvisionallyConsumedRecoveryPasswordSetupGrantEvidence", "ExternalRecoveryAudit")) "disaster restore authorization record set drifted"
Assert-Contract ($ledger.restore_continuity.disaster_mode_fabricates_user_actor_or_approval -eq $false) "disaster restore must never fabricate a user actor or approval"
Assert-Contract (Test-ExactSequence @($ledger.restore_continuity.provisional_admin_grant_sequence) @(
    "authorize_exact_selected_admin_user_person_tuples_and_missing_generations",
    "issue_digest_only_grants",
    "deliver_plaintext_once_to_each_selected_person_locally",
    "provisionally_consume_each_grant_and_set_staged_verifier",
    "authenticate_each_selected_admin_against_staged_store",
    "bind_provisional_password_mutations_to_same_cutover_prepared_sequence",
    "proceed_to_cutover_preconditions"
)) "disaster recovery grant sequence drifted"
Assert-Contract ($ledger.restore_continuity.normal_mode_grants_only_when_selected_admin_backup_credentials_are_stale_or_missing -eq $true) "normal restore recovery grants must be limited to stale or missing selected-admin credentials"
Assert-Contract ($ledger.restore_continuity.disaster_mode_required_grants_follow_deployment_mode_cardinality -eq $true) "disaster restore recovery grants must follow deployment-mode cardinality"
Assert-Contract ($ledger.restore_continuity.carried_forward_records_initial_atomic_insert_and_verification_before_cutover -eq $true) "restore continuity records must be inserted before cutover"
Assert-Contract ($ledger.restore_continuity.payload_contains_secret_request_body -eq $false) "restore continuity envelope must not contain Secret request bodies"
Assert-Contract (Test-ExactSequence @($ledger.restore_continuity.restore_plan_authorization_schema) @(
    "restore_plan_id",
    "deployment_id",
    "deployment_mode",
    "deployment_operational_posture",
    "authorization_mode",
    "recovery_source_mode",
    "high_risk_action_id",
    "high_risk_approval_id",
    "disaster_recovery_authorization_envelope_id",
    "authorization_evidence_hash",
    "admin_readiness_branch",
    "replacement_person_attestation_hash",
    "replacement_user_binding_hash",
    "disaster_entry_condition",
    "entry_condition_preflight_evidence_hash",
    "person_registry_generation",
    "operational_fence_generation"
)) "restore-plan authorization schema drifted"
Assert-Contract ($ledger.restore_continuity.envelope_authentication_algorithm -ceq "HMAC-SHA-256") "restore continuity envelope authentication algorithm drifted"
Assert-Contract ($ledger.restore_continuity.envelope_authentication_purpose_domain -ceq "RESTORE_CONTINUITY_ENVELOPE_HMAC") "restore continuity envelope key purpose drifted"
Assert-Contract (Test-ExactSequence @($ledger.restore_continuity.envelope_schema) @(
    "cutover_id",
    "deployment_id",
    "deployment_mode",
    "deployment_operational_posture",
    "restore_plan_id",
    "authorization_mode",
    "recovery_source_mode",
    "high_risk_action_id",
    "high_risk_approval_id",
    "disaster_recovery_authorization_envelope_id",
    "authorization_evidence_hash",
    "admin_readiness_branch",
    "replacement_person_attestation_hash",
    "replacement_user_binding_hash",
    "disaster_entry_condition",
    "entry_condition_preflight_evidence_hash",
    "person_registry_generation",
    "ledger_prepared_sequence",
    "ledger_prepared_head_hash",
    "ledger_chain_hmac_key_id",
    "envelope_hmac_key_id",
    "payload_hash",
    "previous_store_id",
    "staged_store_id",
    "nonce",
    "issued_at",
    "expires_at"
)) "restore continuity envelope schema drifted"
Assert-Contract ($ledger.restore_continuity.envelope_ttl_minutes_max -eq 30) "restore continuity envelope TTL drifted"
Assert-Contract ($ledger.restore_continuity.envelope_time_source -ceq "EXTERNAL_TRUSTED_MONOTONIC_TIME") "restore continuity envelope time source drifted"
Assert-Contract ($ledger.restore_continuity.clock_rollback_never_extends_envelope -eq $true) "clock rollback must not extend a restore continuity envelope"
Assert-Contract (Test-SameSet @($ledger.restore_continuity.authorization_branch_field_rules.PSObject.Properties.Name) @("NORMAL_API_FOUR_EYES", "LOCAL_DISASTER_QUORUM")) "restore authorization branch rules schema drifted"
Assert-Contract (
    ($ledger.restore_continuity.authorization_branch_field_rules.NORMAL_API_FOUR_EYES -ceq "high_risk_action_and_approval_evidence_required_disaster_entry_condition_and_preflight_evidence_null") -and
    ($ledger.restore_continuity.authorization_branch_field_rules.LOCAL_DISASTER_QUORUM -ceq "disaster_envelope_entry_condition_and_preflight_evidence_required_high_risk_action_and_user_approval_null")
) "restore authorization branch nullability drifted"
Assert-Contract (Test-SameSet @($ledger.restore_continuity.admin_readiness_branch_field_rules.PSObject.Properties.Name) @("NONE", "LOCAL_DISASTER_REPLACE_ONE")) "restore admin-readiness branch rules schema drifted"
Assert-Contract (
    ($ledger.restore_continuity.admin_readiness_branch_field_rules.NONE -ceq "replacement_person_attestation_and_user_binding_hashes_null") -and
    ($ledger.restore_continuity.admin_readiness_branch_field_rules.LOCAL_DISASTER_REPLACE_ONE -ceq "replacement_person_attestation_and_user_binding_hashes_required_and_match_disaster_envelope_human_signature_evidence")
) "restore admin-readiness branch nullability drifted"
Assert-Contract ($ledger.restore_continuity.same_branch_nullability_applies_to_restore_plan_continuity_envelope_and_cutover_record -eq $true) "restore branch nullability must match across plan, envelope and cutover records"
Assert-Contract ($ledger.restore_continuity.envelope_single_use_cutover_id_and_nonce -eq $true) "restore continuity envelope cutover ID and nonce must be single use"
Assert-Contract ($ledger.restore_continuity.startup_recomputes_and_verifies_envelope_payload_and_keys -eq $true) "startup must reverify restore continuity envelope payload and keys"
Assert-Contract (
    ($ledger.restore_continuity.envelope_key_temporarily_unavailable_result.error_code -ceq "KEY_SERVICE_UNAVAILABLE") -and
    ($ledger.restore_continuity.envelope_key_temporarily_unavailable_result.state_effect -ceq "RESTORE_FENCED_POINTER_AND_STORES_UNCHANGED") -and
    ($ledger.restore_continuity.envelope_key_temporarily_unavailable_result.retryable -eq $true) -and
    ($ledger.restore_continuity.envelope_invalid_replay_revoked_or_permanently_lost_key_result.error_code -ceq "RESTORE_CONTINUITY_AUTHENTICATION_FAILED") -and
    ($ledger.restore_continuity.envelope_invalid_replay_revoked_or_permanently_lost_key_result.retryable -eq $false)
) "restore continuity envelope verification failure drifted"
Assert-Contract ($ledger.restore_continuity.security_audit_suffix_policy_by_source_mode.ONLINE_ACTIVE_STORE.binds_backup_and_barrier_live_heads -eq $true) "restore continuity must bind the full post-backup security audit suffix"
Assert-Contract ($ledger.restore_continuity.security_audit_suffix_insert_order_and_hash_verified -eq $true) "restore continuity must verify audit suffix order and hashes"
Assert-Contract ($ledger.restore_continuity.security_audit_suffix_policy_by_source_mode.ONLINE_ACTIVE_STORE.range -ceq "BACKUP_MANIFEST_HEAD_EXCLUSIVE_TO_BARRIER_LIVE_HEAD_INCLUSIVE") "online restore audit suffix range drifted"
Assert-Contract ($ledger.restore_continuity.security_audit_suffix_contains_complete_canonical_sanitized_events -eq $true) "restore audit suffix must contain full canonical sanitized events"
Assert-Contract (Test-ExactSequence @($ledger.restore_continuity.security_audit_suffix_schema) @("backup_manifest_audit_head_hash", "barrier_live_audit_head_hash", "ordered_canonical_sanitized_security_audit_events", "first_event_previous_hash", "last_event_hash", "event_count", "suffix_hash")) "restore audit suffix schema drifted"
Assert-Contract ($ledger.restore_continuity.security_audit_events_inserted_into_primary_audit_table_in_chain_order -eq $true) "restored audit events must be inserted into the primary chain in order"
Assert-Contract ($ledger.restore_continuity.security_audit_suffix_policy_by_source_mode.ONLINE_ACTIVE_STORE.maintenance_lock_blocks_all_audit_producers_after_live_head_capture -eq $true) "restore audit barrier must block all audit producers"
Assert-Contract ($ledger.restore_continuity.security_audit_suffix_policy_by_source_mode.ONLINE_ACTIVE_STORE.pre_pointer_requires_unchanged_live_audit_head -eq $true) "restore must recheck the live audit head before pointer replacement"
$fullLossAuditSuffixPolicy = $ledger.restore_continuity.security_audit_suffix_policy_by_source_mode.FULL_LOSS_ACTIVE_STORE_UNAVAILABLE
Assert-Contract ($fullLossAuditSuffixPolicy.backup_and_barrier_heads_both_equal_backup_manifest_head -eq $true) "full-loss restore audit suffix heads must both equal the backup manifest head"
Assert-Contract ($fullLossAuditSuffixPolicy.event_count -eq 0) "full-loss restore audit suffix must contain zero live events"
Assert-Contract (@($fullLossAuditSuffixPolicy.ordered_events).Count -eq 0) "full-loss restore audit suffix ordered event list must be empty"
Assert-Contract ($null -eq $fullLossAuditSuffixPolicy.first_event_previous_hash) "full-loss restore audit suffix first-event previous hash must be null"
Assert-Contract ($fullLossAuditSuffixPolicy.last_event_hash -ceq "BACKUP_MANIFEST_AUDIT_HEAD_HASH") "full-loss restore audit suffix terminal hash drifted"
Assert-Contract ($fullLossAuditSuffixPolicy.suffix_hash_input -ceq "CANONICAL_COMPLETE_SUFFIX_SCHEMA_WITH_EMPTY_ORDERED_EVENTS") "full-loss restore audit suffix hash input drifted"
Assert-Contract ($fullLossAuditSuffixPolicy.live_head_or_maintenance_barrier_required -eq $false) "full-loss restore must not require an unavailable live head or maintenance barrier"
$externalRecoveryAuditPolicy = $ledger.restore_continuity.external_recovery_audit_policy
Assert-Contract ($externalRecoveryAuditPolicy.signature_algorithm -ceq "Ed25519") "external recovery audit signature algorithm drifted"
Assert-Contract ($externalRecoveryAuditPolicy.signature_purpose_domain -ceq "OFFLINE_RECOVERY_AUTHENTICATION") "external recovery audit signature purpose drifted"
Assert-Contract ($externalRecoveryAuditPolicy.signature_verification_requires_record_bound_key_id_and_exact_purpose -eq $true) "external recovery audit signatures must bind their key ID and exact purpose"
Assert-Contract ($externalRecoveryAuditPolicy.canonicalization -ceq "RFC8785_JCS_AFTER_STRICT_TYPED_PARSE") "external recovery audit canonicalization drifted"
Assert-Contract ($externalRecoveryAuditPolicy.domain_separator -ceq "shuziren:p1:external-recovery-audit:v1") "external recovery audit domain separator drifted"
Assert-Contract (Test-ExactSequence @($externalRecoveryAuditPolicy.record_schema) @(
    "sequence",
    "previous_record_hash",
    "authorization_envelope_hash",
    "disaster_entry_condition",
    "custodian_registry_generation",
    "custodian_ids_sorted_distinct",
    "custodian_signature_key_ids_sorted_distinct",
    "custodian_signature_tuples_sorted_by_custodian_id",
    "selected_admin_user_person_tuples_sorted_distinct",
    "command",
    "result",
    "created_at"
)) "external recovery audit record schema drifted"
Assert-Contract ($externalRecoveryAuditPolicy.each_record_requires_same_valid_two_of_three_distinct_custodian_quorum -eq $true) "external recovery audit records must retain the same two-of-three custodian quorum"
Assert-Contract ($externalRecoveryAuditPolicy.signed_payload_excludes_signature_tuples_but_carried_record_includes_them -eq $true) "external recovery audit signature tuple inclusion rule drifted"
Assert-Contract ($externalRecoveryAuditPolicy.record_hash_algorithm -ceq "SHA-256") "external recovery audit hash algorithm drifted"
Assert-Contract ($externalRecoveryAuditPolicy.ordered_hash_chain_required -eq $true) "external recovery audit records must form an ordered hash chain"
Assert-Contract ($externalRecoveryAuditPolicy.first_record_previous_hash -ceq "BACKUP_MANIFEST_AUDIT_HEAD_HASH") "external recovery audit first previous hash drifted"
Assert-Contract ($externalRecoveryAuditPolicy.first_staged_security_audit_event_binds_backup_head_and_external_recovery_audit_terminal_hash -eq $true) "staged security audit must bind the backup head and external recovery audit terminal hash"
Assert-Contract ($ledger.restore_continuity.missing_actor_user_reconstructed_from_ledger_identity_snapshot -eq $true) "restore continuity must reconstruct missing actor rows from the ledger identity snapshot"
foreach ($continuityTrueField in @(
    "maintenance_lock_blocks_control_plane_and_device_writes_during_cutover",
    "staged_execution_records_committed_before_pointer",
    "cutover_completion_mode_frozen_before_prepared",
    "startup_reconciliation_idempotent",
    "online_previous_store_retained_until_committed_anchor",
    "every_production_restore_finalization_sets_or_keeps_recovery_required_until_separate_local_production_readiness_recovery",
    "restore_finalized_but_readiness_incomplete_keeps_external_serving_fenced_until_generic_production_readiness_recovery",
    "ready_fence_without_matching_restore_finalized_result_is_invalid_and_never_opens_serving",
    "pre_pointer_abort_requires_atomic_grant_set_cleanup_and_applicable_disaster_nonce_aborted_consumed_before_return"
)) {
    Assert-Contract ($ledger.restore_continuity.$continuityTrueField -eq $true) "restore continuity $continuityTrueField must remain true"
}
Assert-Contract (
    ($ledger.restore_continuity.external_visibility_rule_by_deployment_mode.SETUP -ceq "FORBIDDEN_AFTER_RESTORE_UNTIL_LATER_PRODUCTION_ACTIVATION") -and
    ($ledger.restore_continuity.external_visibility_rule_by_deployment_mode.PRODUCTION_ACTIVE -ceq "BEGINS_ONLY_AFTER_LEDGER_AND_APPLICABLE_NONCE_ANCHORS_CUTOVER_FINALIZATION_SEPARATE_LOCAL_PRODUCTION_READINESS_RECOVERY_AND_AUTHENTICATED_READY_FENCE_SUCCESSOR")
) "restore continuity external visibility must remain fenced until deployment-mode exact readiness"
Assert-Contract (
    ($ledger.restore_continuity.post_restore_posture_by_deployment_mode.SETUP -ceq "RESTORE_REMAINS_SETUP_EXTERNAL_SERVING_FORBIDDEN_NO_PRODUCTION_READY_FENCE_REQUIRED") -and
    ($ledger.restore_continuity.post_restore_posture_by_deployment_mode.PRODUCTION_ACTIVE -ceq "RESTORE_FINALIZATION_REMAINS_RECOVERY_REQUIRED_UNTIL_SEPARATE_LOCAL_PRODUCTION_READINESS_RECOVERY_APPENDS_AUTHENTICATED_READY_FENCE_SUCCESSOR")
) "post-restore operational posture drifted"
Assert-Contract (Test-ExactSequence @($ledger.restore_continuity.cutover_record_states) @("CUTOVER_PREPARED", "POINTER_SWITCHED_PENDING_ANCHOR", "ANCHOR_COMMITTED_PENDING_FINALIZATION", "FINALIZED", "REVERTED")) "restore cutover record states drifted"
Assert-Contract (Test-ExactSequence @($ledger.restore_continuity.restore_cutover_record_schema) @(
    "cutover_id",
    "restore_plan_id",
    "deployment_mode",
    "deployment_operational_posture",
    "authorization_mode",
    "recovery_source_mode",
    "high_risk_action_id",
    "high_risk_approval_id",
    "disaster_recovery_authorization_envelope_id",
    "authorization_evidence_hash",
    "admin_readiness_branch",
    "replacement_person_attestation_hash",
    "replacement_user_binding_hash",
    "disaster_entry_condition",
    "entry_condition_preflight_evidence_hash",
    "person_registry_generation",
    "completion_mode",
    "continuity_payload_hash",
    "ledger_prepared_sequence",
    "previous_store_pointer",
    "staged_store_pointer",
    "state",
    "resource_revision",
    "created_at",
    "updated_at"
)) "restore cutover record schema drifted"
Assert-Contract (Test-ExactSequence @($ledger.restore_continuity.continuity_envelope_protocol) @(
    "compute_payload_and_hash",
    "append_prepared_binding_payload_hash_and_fsync",
    "authenticate_envelope_with_prepared_sequence",
    "insert_and_verify_records_in_staged_store",
    "verify_three_screen_complete_bindings_and_all_cutover_preconditions"
)) "restore continuity envelope protocol drifted"
Assert-Contract (Test-ExactSequence @($ledger.restore_continuity.cutover_protocol) @(
    "commit_staged_store_with_ledger_sequence_and_cutover_prepared_record",
    "atomic_replace_active_pointer",
    "idempotently_mark_or_infer_pointer_switched_from_actual_pointer_and_authenticated_cutover_record",
    "append_cutover_committed_and_advance_anchor",
    "compare_and_swap_disaster_nonce_reserved_to_committed_consumed_and_advance_nonce_anchor_when_disaster_mode",
    "idempotently_finalize_entire_restore_execution_audit_and_exact_result_from_committed_anchor",
    "when_production_append_or_confirm_recovery_required_fence_bound_to_restore_finalized_result",
    "require_separate_local_production_readiness_recovery_with_fresh_authorization_nonce_complete_readiness_external_audit_and_ready_fence_successor"
)) "restore cutover protocol drifted"
Assert-Contract (Test-ExactSequence @($ledger.restore_continuity.finalization_transaction_records) @("RestorePlanTerminalState", "AsyncOperationTerminalResult", "OutboxRecordDeliveredOrSuppressed", "IdempotencyRecordExactResult", "RestoreCutoverRecordFinalized", "SecurityAuditEvent")) "restore finalization transaction record set drifted"
Assert-Contract ($ledger.restore_continuity.already_finalized_replay_result -ceq "RETURN_EXACT_STORED_RESULT_NO_REDISPATCH") "finalized restore replay semantics drifted"
Assert-Contract ($ledger.restore_continuity.disaster_authorization_nonce_replay_result -ceq "RETURN_EXACT_STORED_RESULT_IF_FINALIZED_ELSE_REJECT_REPLAY") "disaster restore nonce replay semantics drifted"
Assert-Contract ($ledger.restore_continuity.anchor_committed_db_terminal_missing_result -ceq "FINALIZE_ENTIRE_EXECUTION_FROM_AUTHENTICATED_CUTOVER_RECORD") "anchor-committed finalization recovery drifted"
Assert-Contract ($ledger.restore_continuity.pointer_switched_anchor_not_committed_result -ceq "FENCE_AND_COMPLETE_IF_EXACT_LEDGER_COMMIT_EXISTS_ELSE_REVERT_AND_ABORT") "pointer-switched recovery decision drifted"
Assert-Contract ($ledger.restore_continuity.ledger_committed_anchor_not_advanced_result -ceq "FENCE_AND_ADVANCE_MATCHING_ANCHOR_OR_FAIL_CLOSED") "ledger-committed anchor recovery decision drifted"
Assert-Contract ($ledger.restore_continuity.anchor_unavailable_during_reconciliation_result -ceq "RESTORE_CUTOVER_RECONCILIATION_REQUIRED") "unavailable cutover anchor must fail closed"
Assert-Contract ($ledger.restore_continuity.online_crash_before_pointer_result -ceq "KEEP_PREVIOUS_STORE_ABORT_PREPARED") "online restore pre-pointer crash result drifted"
Assert-Contract ($ledger.restore_continuity.full_loss_crash_before_pointer_result -ceq "ABORT_PREPARED_KEEP_STAGED_UNSERVED") "full-loss restore pre-pointer crash result drifted"
Assert-Contract ($ledger.restore_continuity.crash_after_pointer_before_anchor_result -ceq "FENCE_AND_COMPLETE_IF_EXACT_LEDGER_COMMIT_EXISTS_ELSE_REVERT_AND_ABORT") "restore post-pointer/pre-anchor crash result drifted"
Assert-Contract (Test-SameSet @($ledger.restore_continuity.missing_or_mismatch_result_by_source_mode.PSObject.Properties.Name) @("ONLINE_ACTIVE_STORE", "FULL_LOSS_ACTIVE_STORE_UNAVAILABLE")) "restore mismatch source-mode registry drifted"
Assert-Contract (
    ($ledger.restore_continuity.missing_or_mismatch_result_by_source_mode.ONLINE_ACTIVE_STORE.error_code -ceq "RESTORE_CUTOVER_RECONCILIATION_REQUIRED") -and
    ($ledger.restore_continuity.missing_or_mismatch_result_by_source_mode.ONLINE_ACTIVE_STORE.state_effect -ceq "KEEP_PREVIOUS_ACTIVE") -and
    ($ledger.restore_continuity.missing_or_mismatch_result_by_source_mode.ONLINE_ACTIVE_STORE.retryable -eq $true)
) "online restore mismatch result drifted"
Assert-Contract (
    ($ledger.restore_continuity.missing_or_mismatch_result_by_source_mode.FULL_LOSS_ACTIVE_STORE_UNAVAILABLE.error_code -ceq "RESTORE_CUTOVER_RECONCILIATION_REQUIRED") -and
    ($ledger.restore_continuity.missing_or_mismatch_result_by_source_mode.FULL_LOSS_ACTIVE_STORE_UNAVAILABLE.state_effect -ceq "KEEP_STAGED_UNSERVED") -and
    ($ledger.restore_continuity.missing_or_mismatch_result_by_source_mode.FULL_LOSS_ACTIVE_STORE_UNAVAILABLE.retryable -eq $true)
) "full-loss restore mismatch result drifted"
Assert-Contract ($ledger.missing_stale_or_unverifiable_result -ceq "FAIL_CLOSED") "missing, stale or unverifiable security ledger state must fail closed"

Assert-Contract (Test-SameSet @($contract.retention.PSObject.Properties.Name) @("runtime_detail_days_default", "runtime_detail_days_configurable", "security_audit_uses_runtime_policy", "config_release_uses_runtime_policy", "device_revocation_uses_runtime_policy")) "retention policy schema drifted"
Assert-Contract ($contract.retention.runtime_detail_days_default -eq 3) "runtime detail retention must default to three days"
Assert-Contract ($contract.retention.runtime_detail_days_configurable -eq $true) "runtime detail retention must remain configurable"
Assert-Contract ($contract.retention.security_audit_uses_runtime_policy -eq $false) "security audit must not use runtime retention"
Assert-Contract ($contract.retention.config_release_uses_runtime_policy -eq $false) "releases must not use runtime retention"
Assert-Contract ($contract.retention.device_revocation_uses_runtime_policy -eq $false) "device revocations must not use runtime retention"

Assert-Contract (Test-SameSet @($contract.api.PSObject.Properties.Name) @("surfaces", "forbidden_request_scope_fields", "control_plane_forbidden_actor_fields", "device_forbidden_request_scope_fields", "forbidden_response_fields", "sensitive_request_digest", "one_time_secret_response_replay", "errors", "result_encoding_policy", "operations")) "API registry schema differs from the frozen contract"
Assert-Contract (Test-SameSet @($contract.api.surfaces.PSObject.Properties.Name) @("control_plane", "device")) "API surface registry differs from the frozen contract"
Assert-Contract ($contract.api.surfaces.control_plane -ceq "/api/v1/control-plane") "control-plane API namespace is incorrect"
Assert-Contract ($contract.api.surfaces.device -ceq "/api/v1/device") "device API namespace is incorrect"
Assert-Contract (Test-ExactSequence @($contract.api.forbidden_request_scope_fields) @("tenant_id", "deployment_id", "operator")) "API forbidden request scope fields are incomplete"
Assert-Contract (Test-ExactSequence @($contract.api.control_plane_forbidden_actor_fields) @("operator", "actor_id", "person_id", "person_registry_generation", "person_eligibility_generation", "person_identity_attestation")) "control-plane actor fields must come from the authenticated session"
Assert-Contract (Test-ExactSequence @($contract.api.device_forbidden_request_scope_fields) @("tenant_id", "deployment_id", "site_id", "screen_id", "digital_human_instance_id")) "device forbidden scope fields are incomplete"
Assert-Contract (Test-ExactSequence @($contract.api.forbidden_response_fields) @("password", "password_hash", "secret_value", "database_dsn", "recovery_key", "session_digest", "csrf_secret", "reauthentication_proof")) "API forbidden response fields are incomplete"
$sensitiveRequestDigest = $contract.api.sensitive_request_digest
Assert-Contract (Test-SameSet @($sensitiveRequestDigest.PSObject.Properties.Name) @(
    "purpose_domain",
    "algorithm",
    "canonicalization",
    "domain_separator",
    "duplicate_json_members_or_non_finite_numbers_result",
    "length_safe_typed_object_encoding",
    "key_outside_live_store_logs_and_backups",
    "key_id_stored_with_digest",
    "verification_uses_bound_key_id",
    "key_retention_policy",
    "plaintext_body_persisted",
    "key_temporarily_unavailable_result",
    "key_revoked_or_permanently_lost_result"
)) "sensitive request digest schema drifted"
Assert-Contract ($sensitiveRequestDigest.algorithm -ceq "HMAC-SHA-256") "sensitive request digests must use keyed HMAC-SHA-256"
Assert-Contract ($sensitiveRequestDigest.key_outside_live_store_logs_and_backups -eq $true) "sensitive request digest key must remain outside live storage, logs and backups"
Assert-Contract ($sensitiveRequestDigest.plaintext_body_persisted -eq $false) "sensitive request bodies must never be persisted"
Assert-Contract (
    ($sensitiveRequestDigest.key_temporarily_unavailable_result.error_code -ceq "SENSITIVE_REQUEST_DIGEST_KEY_UNAVAILABLE") -and
    ($sensitiveRequestDigest.key_temporarily_unavailable_result.state_effect -ceq "REQUEST_AND_DOMAIN_STATE_UNCHANGED") -and
    ($sensitiveRequestDigest.key_temporarily_unavailable_result.retryable -eq $true) -and
    ($sensitiveRequestDigest.key_revoked_or_permanently_lost_result.error_code -ceq "REQUEST_DIGEST_KEY_EPOCH_CHANGED") -and
    ($sensitiveRequestDigest.key_revoked_or_permanently_lost_result.retryable -eq $false)
) "missing sensitive request digest key must fail closed"

$oneTimeResponseReplay = $contract.api.one_time_secret_response_replay
Assert-Contract ($oneTimeResponseReplay.purpose_domain -ceq "ONE_TIME_RESPONSE_ENCRYPTION") "one-time response replay key purpose drifted"
Assert-Contract ($oneTimeResponseReplay.algorithm -ceq "AEAD_AES_256_GCM") "one-time response replay must use AES-256-GCM"
Assert-Contract (($oneTimeResponseReplay.nonce_bits -eq 96) -and ($oneTimeResponseReplay.authentication_tag_bits -eq 128)) "one-time response replay nonce or tag size drifted"
Assert-Contract ($oneTimeResponseReplay.nonce_unique_per_response_encryption_key -eq $true) "one-time response replay nonce must be unique per key"
Assert-Contract (Test-ExactSequence @($oneTimeResponseReplay.applicable_operations) @("issuePasswordReset", "issueDeviceEnrollment", "claimDeviceEnrollment", "rotateDeviceCredential")) "one-time response replay operation registry drifted"
Assert-Contract ($oneTimeResponseReplay.maximum_replay_minutes -eq 5) "one-time Secret response replay window must remain five minutes"
Assert-Contract ($oneTimeResponseReplay.ciphertext_only_persisted -eq $true) "one-time Secret response replay must persist ciphertext only"
Assert-Contract ($oneTimeResponseReplay.plaintext_never_persisted_or_logged -eq $true) "one-time Secret response plaintext must never persist"
Assert-Contract ($oneTimeResponseReplay.replay_ciphertext_domain_effect_idempotency_and_authorization_consumption_atomic -eq $true) "one-time replay ciphertext and domain effect must commit atomically"
Assert-Contract ($oneTimeResponseReplay.associated_data_operation_discriminator_and_branch_nullability_strict -eq $true) "one-time response associated-data branches must be strict"
Assert-Contract (Test-ExactSequence @($oneTimeResponseReplay.associated_data_branch_fields_by_operation.issuePasswordReset) @(
    "issuance_kind",
    "target_user_id",
    "target_person_id",
    "target_person_binding_generation",
    "target_person_eligibility_generation",
    "target_channel_event_id",
    "target_possession_challenge_hash"
)) "password reset one-time response associated-data binding drifted"
Assert-Contract ($oneTimeResponseReplay.issue_password_reset_associated_data_branch_rules.NORMAL_PASSWORD_RESET -ceq "TARGET_PERSON_AND_BINDING_FIELDS_REQUIRED_TARGET_CHANNEL_AND_CHALLENGE_FIELDS_REQUIRED") "normal password reset associated-data branch drifted"
Assert-Contract ($oneTimeResponseReplay.issue_password_reset_associated_data_branch_rules.PROVISIONING_CREDENTIAL_SETUP -ceq "TARGET_PERSON_AND_BINDING_FIELDS_NULL_TARGET_CHANNEL_AND_CHALLENGE_FIELDS_REQUIRED") "provisioning credential setup associated-data branch drifted"

$errorRegistry = @($contract.api.errors)
$errorCodes = @($errorRegistry | ForEach-Object { [string]$_.code })
Assert-Contract ($errorCodes.Count -eq 40) "API error registry count drifted"
Assert-Contract (($errorCodes | Sort-Object -Unique).Count -eq $errorCodes.Count) "API error codes must be unique"
foreach ($errorEntry in $errorRegistry) {
    Assert-Contract (Test-SameSet @($errorEntry.PSObject.Properties.Name) @("code", "http_status", "retryable")) "API error $($errorEntry.code) schema drifted"
    Assert-Contract ([string]$errorEntry.code -cmatch "^[A-Z][A-Z0-9_]*$") "API error $($errorEntry.code) must be a stable symbolic code"
    Assert-Contract (($errorEntry.http_status -ge 400) -and ($errorEntry.http_status -le 599)) "API error $($errorEntry.code) has an invalid HTTP status"
}
$actualErrorRegistryTuples = @($errorRegistry | ForEach-Object {
    "{0}|{1}|{2}" -f $_.code, $_.http_status, ([string]$_.retryable).ToLowerInvariant()
})
$expectedErrorRegistryTuples = @(
    "INVALID_REQUEST|400|false",
    "IDEMPOTENCY_KEY_REQUIRED|400|false",
    "AUTHENTICATION_REQUIRED|401|false",
    "SESSION_EXPIRED|401|false",
    "DEVICE_CREDENTIAL_INVALID|401|false",
    "FORBIDDEN|403|false",
    "RECENT_REAUTHENTICATION_REQUIRED|403|false",
    "RESOURCE_NOT_FOUND|404|false",
    "INVALID_STATE_TRANSITION|409|false",
    "DUPLICATE_RESOURCE|409|false",
    "IDEMPOTENCY_KEY_REUSED|409|false",
    "PUBLISH_TARGET_CHANGED|409|false",
    "RESOLUTION_FINGERPRINT_STALE|409|false",
    "HIGH_RISK_APPROVAL_REQUIRED|409|false",
    "HIGH_RISK_ACTION_MISMATCH|409|false",
    "ACTIVE_DEVICE_FAMILY_EXISTS|409|false",
    "SUCCESSOR_ALREADY_PENDING|409|false",
    "AUTHORITATIVE_CREDENTIAL_MATERIAL_MISSING|409|false",
    "AUTHENTICATABLE_PLATFORM_ADMIN_REQUIRED|409|false",
    "IDENTITY_RECONCILIATION_CONFLICT|409|false",
    "ONE_TIME_RESPONSE_REPLAY_EXPIRED|409|false",
    "REQUEST_DIGEST_KEY_EPOCH_CHANGED|409|false",
    "PRODUCTION_READINESS_REQUIRED|409|false",
    "RESOURCE_VERSION_CONFLICT|412|false",
    "ACTIVE_RELEASE_CHANGED|412|false",
    "SECURITY_LEDGER_HEAD_CHANGED|412|false",
    "SCHEMA_VALIDATION_FAILED|422|false",
    "PRECONDITION_REQUIRED|428|false",
    "RATE_LIMITED|429|true",
    "STORAGE_UNAVAILABLE|503|true",
    "DEPENDENCY_UNAVAILABLE|503|true",
    "KEY_SERVICE_UNAVAILABLE|503|true",
    "SECURITY_LEDGER_UNAVAILABLE|503|true",
    "SECURITY_LEDGER_RECONCILIATION_REQUIRED|503|true",
    "SENSITIVE_REQUEST_DIGEST_KEY_UNAVAILABLE|503|true",
    "ONE_TIME_RESPONSE_KEY_UNAVAILABLE|503|true",
    "RESTORE_CONTINUITY_AUTHENTICATION_FAILED|503|false",
    "RESTORE_CUTOVER_RECONCILIATION_REQUIRED|503|true",
    "CRYPTOGRAPHIC_INTEGRITY_FAILURE|503|false",
    "INTERNAL_ERROR|500|false"
)
Assert-Contract (Test-ExactSequence $actualErrorRegistryTuples $expectedErrorRegistryTuples) "API error code, HTTP status or retryability registry drifted"
Assert-Contract (Test-ExactSequence @($contract.api.result_encoding_policy.api_failure_shape) @("type", "title", "status", "code", "detail", "state_effect", "request_id", "retryable", "field_errors")) "API failure envelope shape drifted"
foreach ($trueField in @(
    "every_api_error_code_must_exist_in_error_registry",
    "http_status_is_derived_from_error_registry_not_embedded_in_error_code",
    "body_status_must_equal_http_status_and_registry_status",
    "type_is_stable_product_error_uri_and_title_is_safe_static_text",
    "detail_and_field_errors_never_contain_secrets",
    "internal_reconciliation_markers_are_not_api_error_codes"
)) {
    Assert-Contract ($contract.api.result_encoding_policy.$trueField -eq $true) "API result encoding rule $trueField must remain true"
}

$errorResultObjects = [System.Collections.Generic.List[object]]::new()
function Find-ErrorResultObjects {
    param([AllowNull()][object]$Value)
    if ($null -eq $Value) {
        return
    }
    if ($Value -is [System.Management.Automation.PSCustomObject]) {
        if ($Value.PSObject.Properties.Name -contains "error_code") {
            $script:errorResultObjects.Add($Value)
        }
        foreach ($property in $Value.PSObject.Properties) {
            Find-ErrorResultObjects -Value $property.Value
        }
        return
    }
    if (($Value -is [System.Collections.IEnumerable]) -and -not ($Value -is [string])) {
        foreach ($item in $Value) {
            Find-ErrorResultObjects -Value $item
        }
    }
}
Find-ErrorResultObjects -Value $contract
foreach ($errorResult in $errorResultObjects) {
    $code = [string]$errorResult.error_code
    $registryEntry = @($errorRegistry | Where-Object { $_.code -ceq $code })
    Assert-Contract ($registryEntry.Count -eq 1) "internal result references unknown API error code $code"
    Assert-Contract (($errorResult.PSObject.Properties.Name -contains "state_effect") -and -not [string]::IsNullOrWhiteSpace([string]$errorResult.state_effect)) "internal result $code must declare a state effect"
    Assert-Contract ($errorResult.PSObject.Properties.Name -contains "retryable") "internal result $code must declare retryability"
    if ($registryEntry.Count -eq 1 -and ($errorResult.PSObject.Properties.Name -contains "retryable")) {
        Assert-Contract ($errorResult.retryable -eq $registryEntry[0].retryable) "internal result $code retryability differs from the API registry"
    }
}

$operations = @($contract.api.operations)
$operationIds = @($operations | ForEach-Object { [string]$_.operation_id })
Assert-Contract (($operationIds | Sort-Object -Unique).Count -eq $operationIds.Count) "API operation IDs must be unique"
$operationRoutes = @($operations | ForEach-Object { "$($_.surface)|$($_.method)|$($_.path)" })
Assert-Contract (($operationRoutes | Sort-Object -Unique).Count -eq $operationRoutes.Count) "API method and path registry must be unique per surface"
Assert-Contract (-not @(
    $operations |
        Where-Object { $_.PSObject.Properties.Name -contains "security_ledger_mutation" } |
        Where-Object { $_.security_ledger_mutation -notin $ledger.ledger_backed_mutations }
).Count) "API operation references an unknown recovery-ledger mutation"

$expectedOperationRegistrySha256 = "81bf821bbdd662f2b6a8936e96b193251e777efefbacb052c2e2d02714450023"
$operationRegistryCanonical = ConvertTo-CanonicalJson -Value $operations
$operationRegistrySha256 = Get-Sha256 -Text $operationRegistryCanonical
Assert-Contract ($operationRegistrySha256 -ceq $expectedOperationRegistrySha256) "API operation registry differs from the frozen exact method, path, permission and policy mapping"

$allowedMethods = @("GET", "POST", "PUT", "PATCH", "DELETE")
$allowedScopes = @("unauthenticated", "authenticated_tenant", "authenticated_tenant_self", "bootstrap_secret", "password_reset_token", "credential_bound_screen", "enrollment_token")
$allowedSecretResponses = @("none", "one_time_auth_session_cookie", "one_time_csrf_token_response_header", "one_time_reset_token_target_person_channel_only", "one_time_enrollment_secret", "one_time_device_credential", "one_time_successor_credential")
$allowedHighRiskPolicies = @("different_user_recent_reauthentication_reason", "different_editor_reason", "self_service_current_password_recent_reauthentication", "production_four_eyes_v1")
$secretResponseOperations = @{
    "createAuthSession" = "one_time_auth_session_cookie"
    "refreshCsrfToken" = "one_time_csrf_token_response_header"
    "issuePasswordReset" = "one_time_reset_token_target_person_channel_only"
    "issueDeviceEnrollment" = "one_time_enrollment_secret"
    "claimDeviceEnrollment" = "one_time_device_credential"
    "rotateDeviceCredential" = "one_time_successor_credential"
}
$noStoreOperations = @(
    "completeBootstrap",
    "createAuthSession",
    "refreshCsrfToken",
    "reauthenticateAuthSession",
    "changeOwnPassword",
    "issuePasswordReset",
    "consumePasswordReset",
    "issueDeviceEnrollment",
    "claimDeviceEnrollment",
    "rotateDeviceCredential"
)
$emptyPermissionOperations = @(
    "completeBootstrap",
    "createAuthSession",
    "getCurrentAuthSession",
    "refreshCsrfToken",
    "reauthenticateAuthSession",
    "listOwnAuthSessions",
    "revokeOwnAuthSession",
    "deleteCurrentAuthSession",
    "changeOwnPassword",
    "consumePasswordReset",
    "claimDeviceEnrollment",
    "rotateDeviceCredential",
    "getDeviceRuntimeBinding",
    "getDeviceCurrentRelease",
    "acknowledgeDeviceRelease",
    "recordDeviceHeartbeat"
)

foreach ($operation in $operations) {
    $operationId = [string]$operation.operation_id
    Assert-Contract (-not [string]::IsNullOrWhiteSpace($operationId)) "API operation has no operation_id"
    Assert-Contract ($allowedMethods -contains [string]$operation.method) "API operation $operationId has unsupported method"
    Assert-Contract (([string]$operation.path).StartsWith("/")) "API operation $operationId path must be relative to its versioned surface"
    Assert-Contract (@("control_plane", "device") -contains [string]$operation.surface) "API operation $operationId has unknown surface"
    Assert-Contract ($allowedScopes -contains [string]$operation.scope) "API operation $operationId has unknown scope"
    Assert-Contract ($allowedSecretResponses -contains [string]$operation.response_secret) "API operation $operationId has unknown response_secret policy"

    $anyPermissions = @($operation.required_permissions_any | ForEach-Object { [string]$_ })
    $allPermissions = @()
    if ($operation.PSObject.Properties.Name -contains "required_permissions_all") {
        $allPermissions = @($operation.required_permissions_all | ForEach-Object { [string]$_ })
    }
    if ($emptyPermissionOperations -contains $operationId) {
        Assert-Contract (($anyPermissions.Count + $allPermissions.Count) -eq 0) "API operation $operationId must not use control-plane RBAC permissions"
    }
    else {
        Assert-Contract (($anyPermissions.Count + $allPermissions.Count) -gt 0) "API operation $operationId must define an RBAC permission"
    }
    foreach ($permission in @($anyPermissions + $allPermissions)) {
        Assert-Contract ($permissions -contains $permission) "API operation $operationId references unknown permission $permission"
    }
    Assert-Contract (-not (@($anyPermissions | Where-Object { $allPermissions -contains $_ }).Count)) "API operation $operationId overlaps any/all permission sets"

    if (($operation.method -eq "POST") -and (@("createAuthSession", "refreshCsrfToken") -notcontains $operationId)) {
        Assert-Contract ($operation.idempotency -ceq "required") "POST operation $operationId must require an idempotency key"
    }
    if (@("PUT", "PATCH") -contains [string]$operation.method) {
        Assert-Contract (([string]$operation.concurrency).Contains("if_match")) "mutable operation $operationId must require If-Match or the explicit create-or-replace variant"
    }
    if ($operation.surface -eq "device") {
        Assert-Contract (@("credential_bound_screen", "enrollment_token") -contains [string]$operation.scope) "device operation $operationId must derive or atomically bind its screen scope"
    }
    elseif ($operationId -eq "completeBootstrap") {
        Assert-Contract ($operation.scope -ceq "bootstrap_secret") "bootstrap completion must use bootstrap-secret scope"
    }
    elseif ($operationId -eq "consumePasswordReset") {
        Assert-Contract ($operation.scope -ceq "password_reset_token") "password reset consumption must use reset-token scope"
    }
    elseif ($operationId -eq "createAuthSession") {
        Assert-Contract ($operation.scope -ceq "unauthenticated") "login must use unauthenticated scope"
    }
    elseif ($operationId -eq "changeOwnPassword") {
        Assert-Contract ($operation.scope -ceq "authenticated_tenant_self") "own-password change must use authenticated self scope"
    }
    else {
        Assert-Contract ($operation.scope -ceq "authenticated_tenant") "control-plane operation $operationId must use authenticated tenant scope"
    }

    if ($secretResponseOperations.ContainsKey($operationId)) {
        Assert-Contract ($operation.response_secret -ceq $secretResponseOperations[$operationId]) "operation $operationId has the wrong one-time response policy"
    }
    else {
        Assert-Contract ($operation.response_secret -ceq "none") "operation $operationId must not return a Secret"
    }
    if ($noStoreOperations -contains $operationId) {
        Assert-Contract ($operation.response_cache_control -ceq "no-store") "sensitive operation $operationId must require Cache-Control no-store"
    }
    else {
        Assert-Contract (-not ($operation.PSObject.Properties.Name -contains "response_cache_control")) "ordinary operation $operationId must not invent a cache-control exception"
    }
    if ($operation.PSObject.Properties.Name -contains "high_risk_policy") {
        Assert-Contract ($allowedHighRiskPolicies -contains [string]$operation.high_risk_policy) "operation $operationId references an unknown high-risk policy"
    }
}

$markedProductionFourEyes = @($operations | Where-Object { $_.high_risk_policy -ceq "production_four_eyes_v1" } | ForEach-Object { [string]$_.operation_id })
Assert-Contract (Test-SameSet $markedProductionFourEyes $expectedProtectedOperations) "protected-operation registry and production four-eyes markers must match exactly"
Assert-Contract (-not @($operations | Where-Object { ($_.surface -eq "control_plane") -and ($_.method -eq "POST") -and ($_.path -eq "/high-risk-actions") }).Count) "generic high-risk action creation route must not exist"
$draftSpecOperation = @($operations | Where-Object { $_.operation_id -eq "replaceConfigDraftSpec" })
Assert-Contract (($draftSpecOperation.Count -eq 1) -and ($draftSpecOperation[0].field_permission_policy -ceq "config_draft_spec_fields")) "replaceConfigDraftSpec must use the frozen field-level authorization policy"
$reviseDraftOperation = @($operations | Where-Object { $_.operation_id -eq "reviseConfigDraft" })
Assert-Contract (
    ($reviseDraftOperation.Count -eq 1) -and
    ($reviseDraftOperation[0].transition_rule -ceq "validated_previewed_rejected_or_pending;approved_only_when_resolution_fingerprint_or_control_plane_epoch_stale;copy_current_spec") -and
    ($reviseDraftOperation[0].field_permission_policy -ceq "config_draft_all_present_field_classes") -and
    ($reviseDraftOperation[0].server_revalidates_stale_fingerprint_and_epoch -eq $true)
) "reviseConfigDraft must close the frozen revision and stale-fingerprint transitions"
$abandonDraftOperation = @($operations | Where-Object { $_.operation_id -eq "abandonConfigDraft" })
Assert-Contract (
    ($abandonDraftOperation.Count -eq 1) -and
    ($abandonDraftOperation[0].transition_rule -ceq "draft_validated_previewed_or_rejected_only") -and
    ($abandonDraftOperation[0].field_permission_policy -ceq "config_draft_all_present_field_classes")
) "abandonConfigDraft must close only the legal abandon transitions"
$fineReportPut = @($operations | Where-Object { $_.operation_id -eq "putFineReportIdentityBinding" })
Assert-Contract (($fineReportPut.Count -eq 1) -and (Test-ExactSequence @($fineReportPut[0].required_permissions_all) @("screen.manage", "secret.write", "finereport.binding.manage"))) "FineReport binding PUT must require all frozen permissions"
$highRiskRead = @($operations | Where-Object { $_.operation_id -eq "getHighRiskAction" })
Assert-Contract (($highRiskRead.Count -eq 1) -and ($highRiskRead[0].authorization_rule -ceq "requester_or_risk_approve_with_target_scope")) "HighRiskAction read must remain requester-or-approver scoped"
foreach ($approvalOperationId in @("approveHighRiskAction", "rejectHighRiskAction")) {
    $approvalOperation = @($operations | Where-Object { $_.operation_id -eq $approvalOperationId })
    Assert-Contract (($approvalOperation.Count -eq 1) -and ($approvalOperation[0].approval_requires_expected_request_hash -eq $true)) "operation $approvalOperationId must bind the expected request hash"
}
$revokeDeviceCredentialOperation = @($operations | Where-Object { $_.operation_id -eq "revokeDeviceCredential" })
Assert-Contract (
    ($revokeDeviceCredentialOperation.Count -eq 1) -and
    ($revokeDeviceCredentialOperation[0].concurrency -ceq "if_match_credential_family_and_expected_credential_epoch_and_ledger_head")
) "revokeDeviceCredential must bind DeviceCredentialFamily If-Match, credential epoch and ledger head"
$getDeviceCredentialMetadataOperation = @($operations | Where-Object { $_.operation_id -eq "getDeviceCredentialMetadata" })
Assert-Contract (
    ($getDeviceCredentialMetadataOperation.Count -eq 1) -and
    ($getDeviceCredentialMetadataOperation[0].concurrency -ceq "credential_family_etag_read")
) "getDeviceCredentialMetadata must expose sanitized family concurrency metadata"
$rotateDeviceCredentialOperation = @($operations | Where-Object { $_.operation_id -eq "rotateDeviceCredential" })
Assert-Contract (
    ($rotateDeviceCredentialOperation.Count -eq 1) -and
    ($rotateDeviceCredentialOperation[0].concurrency -ceq "credential_epoch_and_family_generation")
) "rotateDeviceCredential must bind credential epoch and family generation"
$replaceUserRolesOperation = @($operations | Where-Object { $_.operation_id -eq "replaceUserRoles" })
Assert-Contract (
    ($replaceUserRolesOperation.Count -eq 1) -and
    ($replaceUserRolesOperation[0].concurrency -ceq "if_match_and_assignment_generation_and_ledger_head")
) "replaceUserRoles must bind the user ETag, assignment generation and ledger head"
$allowedDeleteOperations = @("deleteCurrentAuthSession", "revokeOwnAuthSession")
$actualDeleteOperations = @($operations | Where-Object { $_.method -eq "DELETE" } | ForEach-Object { [string]$_.operation_id })
Assert-Contract (Test-SameSet $actualDeleteOperations $allowedDeleteOperations) "DELETE operation registry differs from the frozen safe set"
$immutableMutationOperations = @($operations | Where-Object {
    ($_.surface -eq "control_plane") -and
    ($_.method -ne "GET") -and
    (
        ([string]$_.path).StartsWith("/config-releases") -or
        ([string]$_.path).StartsWith("/release-targets") -or
        ([string]$_.path).StartsWith("/audit-events")
    )
})
Assert-Contract ($immutableMutationOperations.Count -eq 0) "immutable release, target or audit resource has a mutating API operation"

$requiredAsyncOperations = @("publishToScreen", "publishToScreenGroup", "rollbackScreen", "rollbackScreenGroup", "createBackup", "verifyBackup", "executeRestorePlan")
$actualAsyncOperations = @($operations | Where-Object { $_.async -eq $true } | ForEach-Object { [string]$_.operation_id })
Assert-Contract (Test-SameSet $actualAsyncOperations $requiredAsyncOperations) "asynchronous operation registry differs from the frozen set"

Assert-Contract (Test-SameSet @($contract.three_screen_fixture.PSObject.Properties.Name) @("site_id", "release_targets", "screens", "single_screen_publication")) "three-screen fixture schema drifted"
$fixtureScreens = @($contract.three_screen_fixture.screens)
Assert-Contract ($fixtureScreens.Count -eq 3) "three-screen fixture must contain exactly three screens"
$fixtureScreenIds = @($fixtureScreens | ForEach-Object { [string]$_.screen_id })
Assert-Contract (($fixtureScreenIds | Sort-Object -Unique).Count -eq 3) "three-screen fixture screen IDs must be unique"
$fixtureReleaseTargets = @($contract.three_screen_fixture.release_targets)
Assert-Contract ($fixtureReleaseTargets.Count -eq 4) "three-screen fixture must contain the three initial targets plus the new target"
$fixtureReleaseTargetIds = @($fixtureReleaseTargets | ForEach-Object { [string]$_.release_target_id })
Assert-Contract (($fixtureReleaseTargetIds | Sort-Object -Unique).Count -eq 4) "three-screen fixture ReleaseTarget IDs must be unique"
$fixtureReleaseIds = @($fixtureReleaseTargets | ForEach-Object { [string]$_.release_id })
Assert-Contract (($fixtureReleaseIds | Sort-Object -Unique).Count -eq 4) "three-screen fixture release IDs must be unique"
foreach ($fixtureReleaseTarget in $fixtureReleaseTargets) {
    Assert-Contract (Test-SameSet @($fixtureReleaseTarget.PSObject.Properties.Name) @("release_label", "release_id", "screen_id", "release_target_id")) "three-screen fixture ReleaseTarget schema drifted"
    Assert-Contract ($fixtureScreenIds -contains [string]$fixtureReleaseTarget.screen_id) "three-screen fixture ReleaseTarget must belong to one fixture screen"
}
$fixtureDigitalHumanIds = @($fixtureScreens | ForEach-Object { [string]$_.digital_human_instance_id })
Assert-Contract (
    ($fixtureDigitalHumanIds.Count -eq 3) -and
    (@($fixtureDigitalHumanIds | Where-Object { [string]::IsNullOrWhiteSpace($_) }).Count -eq 0) -and
    (($fixtureDigitalHumanIds | Sort-Object -Unique).Count -eq 3)
) "three-screen fixture DigitalHumanInstance IDs must be non-empty and unique"
foreach ($fixtureScreen in $fixtureScreens) {
    Assert-Contract (Test-SameSet @($fixtureScreen.PSObject.Properties.Name) @("screen_id", "digital_human_instance_id", "desired_release_target_id", "applied_release_target_id", "binding_generation", "last_acknowledged_marker", "resource_revision", "last_acknowledged_at")) "three-screen fixture initial RuntimeBinding schema drifted"
    Assert-Contract ($fixtureScreen.binding_generation -is [long] -or $fixtureScreen.binding_generation -is [int]) "three-screen fixture binding generation must be numeric"
    Assert-Contract ($fixtureScreen.binding_generation -gt 0) "three-screen fixture binding generation must be positive"
    Assert-Contract ($fixtureScreen.resource_revision -is [long] -or $fixtureScreen.resource_revision -is [int]) "three-screen fixture resource revision must be numeric"
    Assert-Contract ($fixtureScreen.resource_revision -gt 0) "three-screen fixture resource revision must be positive"
    Assert-Contract (-not [string]::IsNullOrWhiteSpace([string]$fixtureScreen.last_acknowledged_marker)) "three-screen fixture acknowledgement marker must be non-empty"
    Assert-Contract (-not [string]::IsNullOrWhiteSpace([string]$fixtureScreen.last_acknowledged_at)) "three-screen fixture acknowledgement timestamp must be non-empty"
    $desiredTarget = @($fixtureReleaseTargets | Where-Object { $_.release_target_id -eq $fixtureScreen.desired_release_target_id })
    $appliedTarget = @($fixtureReleaseTargets | Where-Object { $_.release_target_id -eq $fixtureScreen.applied_release_target_id })
    Assert-Contract (
        ($desiredTarget.Count -eq 1) -and
        ([string]$desiredTarget[0].screen_id -ceq [string]$fixtureScreen.screen_id)
    ) "three-screen fixture desired ReleaseTarget must resolve to the same screen"
    Assert-Contract (
        ($appliedTarget.Count -eq 1) -and
        ([string]$appliedTarget[0].screen_id -ceq [string]$fixtureScreen.screen_id)
    ) "three-screen fixture applied ReleaseTarget must resolve to the same screen"
}
$targetScreenId = [string]$contract.three_screen_fixture.single_screen_publication.target_screen_id
Assert-Contract (Test-SameSet @($contract.three_screen_fixture.single_screen_publication.PSObject.Properties.Name) @(
    "target_screen_id",
    "new_release_id",
    "new_release_target_id",
    "expected_binding_generation",
    "expected_resource_revision",
    "changed_screen_ids",
    "unchanged_screen_ids",
    "pre_publish_bindings",
    "post_publish_bindings",
    "post_ack_bindings"
)) "single-screen publication fixture schema drifted"
$changedScreenIds = @($contract.three_screen_fixture.single_screen_publication.changed_screen_ids | ForEach-Object { [string]$_ })
$unchangedScreenIds = @($contract.three_screen_fixture.single_screen_publication.unchanged_screen_ids | ForEach-Object { [string]$_ })
Assert-Contract ($fixtureScreenIds -contains $targetScreenId) "single-screen fixture target must exist"
Assert-Contract (Test-SameSet $changedScreenIds @($targetScreenId)) "single-screen publication must change only its explicit target"
Assert-Contract (Test-SameSet $unchangedScreenIds @($fixtureScreenIds | Where-Object { $_ -ne $targetScreenId })) "single-screen publication must preserve the other two screens"
$targetScreen = @($fixtureScreens | Where-Object { $_.screen_id -eq $targetScreenId })
Assert-Contract (
    ($targetScreen.Count -eq 1) -and
    ($targetScreen[0].binding_generation -eq $contract.three_screen_fixture.single_screen_publication.expected_binding_generation) -and
    ($targetScreen[0].resource_revision -eq $contract.three_screen_fixture.single_screen_publication.expected_resource_revision)
) "single-screen fixture must compare the target binding generation and strong ETag revision"
$newReleaseId = [string]$contract.three_screen_fixture.single_screen_publication.new_release_id
$newReleaseTargetId = [string]$contract.three_screen_fixture.single_screen_publication.new_release_target_id
$newReleaseTarget = @($fixtureReleaseTargets | Where-Object { $_.release_target_id -eq $newReleaseTargetId })
Assert-Contract (
    ($newReleaseTarget.Count -eq 1) -and
    ([string]$newReleaseTarget[0].release_id -ceq $newReleaseId) -and
    ([string]$newReleaseTarget[0].screen_id -ceq $targetScreenId)
) "single-screen fixture new ReleaseTarget must resolve to the target screen and release"
Assert-Contract ($newReleaseTargetId -cne [string]$targetScreen[0].desired_release_target_id) "single-screen fixture publication must not be a no-op ReleaseTarget"

$prePublishBindings = @($contract.three_screen_fixture.single_screen_publication.pre_publish_bindings)
$postPublishBindings = @($contract.three_screen_fixture.single_screen_publication.post_publish_bindings)
$postAckBindings = @($contract.three_screen_fixture.single_screen_publication.post_ack_bindings)
foreach ($bindingSnapshot in @($prePublishBindings, $postPublishBindings, $postAckBindings)) {
    Assert-Contract ($bindingSnapshot.Count -eq 3) "three-screen fixture binding snapshots must each contain exactly three screens"
    Assert-Contract (Test-SameSet @($bindingSnapshot | ForEach-Object { [string]$_.screen_id }) $fixtureScreenIds) "three-screen fixture binding snapshot screen set drifted"
    foreach ($bindingRow in $bindingSnapshot) {
        Assert-Contract (Test-SameSet @($bindingRow.PSObject.Properties.Name) @("screen_id", "digital_human_instance_id", "desired_release_target_id", "applied_release_target_id", "binding_generation", "last_acknowledged_marker", "resource_revision", "last_acknowledged_at")) "three-screen fixture snapshot must freeze the complete RuntimeBinding comparison fields"
    }
}

foreach ($fixtureScreen in $fixtureScreens) {
    $screenId = [string]$fixtureScreen.screen_id
    $pre = @($prePublishBindings | Where-Object { $_.screen_id -eq $screenId })
    $post = @($postPublishBindings | Where-Object { $_.screen_id -eq $screenId })
    $ack = @($postAckBindings | Where-Object { $_.screen_id -eq $screenId })
    Assert-Contract (($pre.Count -eq 1) -and ($post.Count -eq 1) -and ($ack.Count -eq 1)) "three-screen fixture snapshots must contain one row per screen"
    if (($pre.Count -ne 1) -or ($post.Count -ne 1) -or ($ack.Count -ne 1)) {
        continue
    }
    Assert-Contract (
        ([string]$pre[0].digital_human_instance_id -ceq [string]$fixtureScreen.digital_human_instance_id) -and
        ([string]$pre[0].desired_release_target_id -ceq [string]$fixtureScreen.desired_release_target_id) -and
        ([string]$pre[0].applied_release_target_id -ceq [string]$fixtureScreen.applied_release_target_id) -and
        ([long]$pre[0].binding_generation -eq [long]$fixtureScreen.binding_generation) -and
        ([string]$pre[0].last_acknowledged_marker -ceq [string]$fixtureScreen.last_acknowledged_marker) -and
        ([long]$pre[0].resource_revision -eq [long]$fixtureScreen.resource_revision) -and
        ([string]$pre[0].last_acknowledged_at -ceq [string]$fixtureScreen.last_acknowledged_at)
    ) "three-screen fixture pre-publish snapshot must equal the initial bindings"
    if ($screenId -ceq $targetScreenId) {
        Assert-Contract (
            ([string]$post[0].digital_human_instance_id -ceq [string]$pre[0].digital_human_instance_id) -and
            ([string]$post[0].desired_release_target_id -ceq $newReleaseTargetId) -and
            ([string]$post[0].applied_release_target_id -ceq [string]$pre[0].applied_release_target_id) -and
            ([long]$post[0].binding_generation -eq ([long]$pre[0].binding_generation + 1)) -and
            ([string]$post[0].last_acknowledged_marker -ceq [string]$pre[0].last_acknowledged_marker) -and
            ([long]$post[0].resource_revision -eq ([long]$pre[0].resource_revision + 1)) -and
            ([string]$post[0].last_acknowledged_at -ceq [string]$pre[0].last_acknowledged_at)
        ) "target screen must change desired ReleaseTarget, generation and resource revision only at publication"
        Assert-Contract (
            ([string]$ack[0].digital_human_instance_id -ceq [string]$post[0].digital_human_instance_id) -and
            ([string]$ack[0].desired_release_target_id -ceq $newReleaseTargetId) -and
            ([string]$ack[0].applied_release_target_id -ceq $newReleaseTargetId) -and
            ([long]$ack[0].binding_generation -eq [long]$post[0].binding_generation) -and
            (-not [string]::IsNullOrWhiteSpace([string]$ack[0].last_acknowledged_marker)) -and
            ([string]$ack[0].last_acknowledged_marker -cne [string]$post[0].last_acknowledged_marker) -and
            ([long]$ack[0].resource_revision -eq ([long]$post[0].resource_revision + 1)) -and
            (-not [string]::IsNullOrWhiteSpace([string]$ack[0].last_acknowledged_at)) -and
            ([string]$ack[0].last_acknowledged_at -cne [string]$post[0].last_acknowledged_at)
        ) "target screen applied release must change only after acknowledgement"
    }
    else {
        Assert-Contract (
            ([string]$post[0].digital_human_instance_id -ceq [string]$pre[0].digital_human_instance_id) -and
            ([string]$post[0].desired_release_target_id -ceq [string]$pre[0].desired_release_target_id) -and
            ([string]$post[0].applied_release_target_id -ceq [string]$pre[0].applied_release_target_id) -and
            ([long]$post[0].binding_generation -eq [long]$pre[0].binding_generation) -and
            ([string]$post[0].last_acknowledged_marker -ceq [string]$pre[0].last_acknowledged_marker) -and
            ([long]$post[0].resource_revision -eq [long]$pre[0].resource_revision) -and
            ([string]$post[0].last_acknowledged_at -ceq [string]$pre[0].last_acknowledged_at) -and
            ([string]$ack[0].digital_human_instance_id -ceq [string]$pre[0].digital_human_instance_id) -and
            ([string]$ack[0].desired_release_target_id -ceq [string]$pre[0].desired_release_target_id) -and
            ([string]$ack[0].applied_release_target_id -ceq [string]$pre[0].applied_release_target_id) -and
            ([long]$ack[0].binding_generation -eq [long]$pre[0].binding_generation) -and
            ([string]$ack[0].last_acknowledged_marker -ceq [string]$pre[0].last_acknowledged_marker) -and
            ([long]$ack[0].resource_revision -eq [long]$pre[0].resource_revision) -and
            ([string]$ack[0].last_acknowledged_at -ceq [string]$pre[0].last_acknowledged_at)
        ) "non-target screens must remain byte-for-byte binding-equivalent through publication and acknowledgement"
    }
}

if (-not $SkipMarkdown) {
    $contractDirectory = Join-Path $repoRootPath "docs\product\contracts"
    $requiredContractDocuments = @(
        "README.md",
        "DOMAIN_MODEL.md",
        "IDENTITY_AND_RBAC.md",
        "CONFIGURATION_RELEASE.md",
        "DATA_MODEL.md",
        "STORAGE_AND_RECOVERY.md",
        "CONTROL_PLANE_API.md"
    )
    $combinedContractText = [System.Text.StringBuilder]::new()
    foreach ($documentName in $requiredContractDocuments) {
        $documentPath = Join-Path $contractDirectory $documentName
        Assert-Contract (Test-Path -LiteralPath $documentPath -PathType Leaf) "missing target contract document $documentName"
        if (Test-Path -LiteralPath $documentPath -PathType Leaf) {
            $documentText = Get-Content -Raw -LiteralPath $documentPath
            Assert-Contract ($documentText.Contains('Lifecycle: `TARGET_NOT_IMPLEMENTED`')) "$documentName must declare TARGET_NOT_IMPLEMENTED"
            Assert-Contract ($documentText.Contains('p1.0-target-v1')) "$documentName must identify the contract version"
            [void]$combinedContractText.AppendLine($documentText)
        }
    }
    $allContractText = $combinedContractText.ToString()
    foreach ($entity in $entities) {
        Assert-Contract ($allContractText.Contains($entity)) "entity $entity is not explained in the Markdown contract pack"
    }
    foreach ($permission in $permissions) {
        Assert-Contract ($allContractText.Contains($permission)) "permission $permission is not explained in the Markdown contract pack"
    }
    $apiDocumentText = Get-Content -Raw -LiteralPath (Join-Path $contractDirectory "CONTROL_PLANE_API.md")
    foreach ($operation in $operations) {
        Assert-Contract ($apiDocumentText.Contains("``$($operation.operation_id)``")) "API operation $($operation.operation_id) is missing from CONTROL_PLANE_API.md"
        Assert-Contract ($apiDocumentText.Contains([string]$operation.path)) "API path $($operation.path) is missing from CONTROL_PLANE_API.md"
    }
    Assert-Contract ($allContractText.Contains("desired_release_target_id")) "desired release target is not documented"
    Assert-Contract ($allContractText.Contains("applied_release_target_id")) "applied release target is not documented"
    Assert-Contract ($allContractText.Contains("ResolutionFingerprint")) "resolution fingerprint is not documented"
    Assert-Contract ($allContractText.Contains("RecoverySecurityLedger")) "recovery anti-rollback ledger is not documented"
    Assert-Contract ($allContractText.Contains("DeviceCredentialFamily")) "device credential family concurrency aggregate is not documented"
    Assert-Contract ($allContractText.Contains("ROLE_RECONCILIATION_REQUIRED")) "role/scope fail-closed restore result is not documented"
    Assert-Contract ($allContractText.Contains("SECRET_ROTATION_REQUIRED")) "Secret restore anti-rollback result is not documented"
    Assert-Contract ($allContractText.Contains("FINEREPORT_REBIND_REQUIRED")) "FineReport restore anti-rollback result is not documented"
    Assert-Contract ($allContractText.Contains("RestoreContinuityEnvelope")) "restore authorization continuity is not documented"
    Assert-Contract ($allContractText.Contains("creation_kind")) "normal/rollback release provenance discriminator is not documented"
    Assert-Contract ($allContractText.Contains("HighRiskApproval")) "independent high-risk approval evidence is not documented"
    Assert-Contract ($apiDocumentText.Contains('Approval appends HighRiskApproval evidence and changes only `PENDING -> APPROVED`; it never queues or executes the command.')) "API document must keep approval separate from execution"
    Assert-Contract ($apiDocumentText.Contains('`High-Risk-Action-ID`')) "API document must identify the protected-endpoint execution header"
    Assert-Contract ($apiDocumentText.Contains('DeviceCredentialFamily `If-Match` + expected credential epoch + RecoverySecurityLedger head')) "API document must match the machine hard-revoke concurrency contract"
    Assert-Contract ($apiDocumentText.Contains('user `If-Match` + expected assignment generation + RecoverySecurityLedger head')) "API document must match the machine role-replacement concurrency contract"
    Assert-Contract ($apiDocumentText.Contains("config_draft_all_present_field_classes") -or $apiDocumentText.Contains("permissions for every field class currently present")) "API document must require complete current-draft field authorization for revise/abandon"
    Assert-Contract ($allContractText.Contains("permission denial")) "permission-denial fallback behavior is not documented"
    Assert-Contract (-not $allContractText.Contains("Control-plane UserSession")) "canonical AuthSession terminology must not regress to UserSession"
}

if ($failures.Count -gt 0) {
    Write-Output "P1_CONTRACT_FAILED checks=$checks failures=$($failures.Count)"
    foreach ($failure in $failures) {
        Write-Output " - $failure"
    }
    exit 1
}

Write-Output "P1_CONTRACT_OK checks=$checks operations=$($operations.Count) entities=$($entities.Count) roles=$($roleNames.Count)"
