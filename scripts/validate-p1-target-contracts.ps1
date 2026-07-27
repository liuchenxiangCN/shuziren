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
        foreach ($property in @($Value.PSObject.Properties | Sort-Object Name)) {
            $nameJson = ConvertTo-Json -Compress -InputObject ([string]$property.Name)
            $valueJson = ConvertTo-CanonicalJson -Value $property.Value
            $parts.Add($nameJson + ":" + $valueJson)
        }
        return "{" + ($parts -join ",") + "}"
    }
    if ($Value -is [System.Collections.IDictionary]) {
        $parts = [System.Collections.Generic.List[string]]::new()
        foreach ($key in @($Value.Keys | ForEach-Object { [string]$_ } | Sort-Object)) {
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

try {
    $contractText = Get-Content -Raw -LiteralPath $contractFullPath
    $contract = $contractText | ConvertFrom-Json
}
catch {
    Write-Error "P1_CONTRACT_INVALID_JSON $($_.Exception.Message)"
    exit 1
}

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
    "permissions",
    "roles",
    "state_machines",
    "invariants",
    "configuration_authorization",
    "resolution_policy",
    "data_integrity",
    "high_risk_policy",
    "iam_policy",
    "device_policy",
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

$requiredPermissions = @(
    "user.manage",
    "role.assign",
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
            "APPROVED|DRAFT|create_revision_after_stale_fingerprint",
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
        States = @("VALIDATING", "READY", "EXECUTING", "RECONCILING_SECURITY", "COMPLETED", "FAILED", "ABORTED")
        Initial = "VALIDATING"
        Terminal = @("COMPLETED", "FAILED", "ABORTED")
        Transitions = @(
            "VALIDATING|READY|validation_pass",
            "VALIDATING|FAILED|validation_fail",
            "READY|EXECUTING|execute",
            "READY|ABORTED|abort",
            "EXECUTING|RECONCILING_SECURITY|verified_data_cutover",
            "EXECUTING|FAILED|safe_failure",
            "RECONCILING_SECURITY|COMPLETED|security_ledger_reconciled_and_epochs_advanced",
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
            "APPROVED|CONSUMED|atomically_execute_exact_request_hash",
            "APPROVED|EXPIRED|expire",
            "APPROVED|FAILED|precondition_or_authorization_changed"
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

$expectedInvariants = @{
    "max_active_digital_humans_per_screen" = 1
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
    "user_and_device_security_mutations_require_ledger_commit" = $true
    "permission_denial_fallback_allowed" = $false
}
Assert-Contract (Test-SameSet @($contract.invariants.PSObject.Properties.Name) @($expectedInvariants.Keys)) "invariant registry differs from the frozen set"
foreach ($entry in $expectedInvariants.GetEnumerator()) {
    Assert-Contract ($contract.invariants.($entry.Key) -eq $entry.Value) "invariant $($entry.Key) has an unsafe value"
}

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
foreach ($fieldName in @($expectedFieldPermissions.Keys)) {
    $actualFieldPermissions = @($configurationAuthorization.field_permissions.PSObject.Properties[$fieldName].Value)
    Assert-Contract (Test-ExactSequence $actualFieldPermissions $expectedFieldPermissions[$fieldName]) "draft field $fieldName permissions are incorrect"
}
Assert-Contract (Test-ExactSequence @($configurationAuthorization.fine_report_binding_permissions_all) @("screen.manage", "secret.write", "finereport.binding.manage")) "FineReport binding must require all three frozen permissions"

$resolutionPolicy = $contract.resolution_policy
Assert-Contract (Test-SameSet @($resolutionPolicy.PSObject.Properties.Name) @(
    "fingerprint_algorithm",
    "bound_at",
    "inheritance_layer_entity",
    "inheritance_order",
    "approval_binds",
    "release_creation",
    "source_change_result",
    "publication_creates_release_targets"
)) "resolution policy schema differs from the frozen contract"
Assert-Contract ($resolutionPolicy.fingerprint_algorithm -ceq "SHA-256") "resolution fingerprint algorithm is incorrect"
Assert-Contract ($resolutionPolicy.bound_at -ceq "validation") "resolution fingerprint must be bound at validation"
Assert-Contract ($resolutionPolicy.inheritance_layer_entity -ceq "ConfigLayerRevision") "resolution inputs must use ConfigLayerRevision"
Assert-Contract (Test-ExactSequence @($resolutionPolicy.inheritance_order) @("product_default", "tenant", "deployment", "site", "screen_group", "screen_instance")) "configuration inheritance order drifted"
Assert-Contract (Test-ExactSequence @($resolutionPolicy.approval_binds) @(
    "draft_revision_id",
    "draft_content_hash",
    "resolution_fingerprint_hash",
    "target_set_hash",
    "group_resource_revision",
    "inheritance_layer_revisions",
    "per_screen_effective_content_hashes",
    "fine_report_binding_versions",
    "secret_versions"
)) "approval does not bind the exact frozen resolution facts"
Assert-Contract ($resolutionPolicy.release_creation -ceq "atomically_revalidate_fingerprint_and_create_release_targets") "release creation must revalidate and create all targets atomically"
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
    "execution_rechecks_requester_and_executor_target_authorization",
    "request_hash_binds",
    "development_test_auto_approval_requires_explicit_audit_policy",
    "protected_operations"
)) "high-risk policy schema differs from the frozen contract"
Assert-Contract ($highRiskPolicy.standard_production_policy_id -ceq "production_four_eyes_v1") "production high-risk policy ID is incorrect"
Assert-Contract ($highRiskPolicy.approval_ttl_minutes -eq 15) "high-risk approval TTL must be 15 minutes"
Assert-Contract ($highRiskPolicy.request_hash_algorithm -ceq "SHA-256") "high-risk request hash must be SHA-256"
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
    "execution_rechecks_requester_and_executor_target_authorization",
    "development_test_auto_approval_requires_explicit_audit_policy"
)) {
    Assert-Contract ($highRiskPolicy.$trueField -eq $true) "high-risk policy $trueField must remain true"
}
$expectedRequestHashBindings = @(
    "http_method",
    "canonical_path",
    "tenant_id",
    "deployment_id",
    "requester_user_id",
    "resource_ids",
    "canonical_body",
    "if_match",
    "expected_generations",
    "reason",
    "policy_version",
    "recovery_security_ledger_head"
)
Assert-Contract (Test-ExactSequence @($highRiskPolicy.request_hash_binds) $expectedRequestHashBindings) "high-risk request hash bindings are incomplete"
$expectedProtectedOperations = @(
    "publishToScreen",
    "publishToScreenGroup",
    "rollbackScreen",
    "rollbackScreenGroup",
    "revokeDeviceCredential",
    "rotateSecret",
    "putFineReportIdentityBinding",
    "executeRestorePlan"
)
Assert-Contract (Test-ExactSequence @($highRiskPolicy.protected_operations) $expectedProtectedOperations) "production four-eyes operation set drifted"

Assert-Contract (Test-SameSet @($contract.iam_policy.PSObject.Properties.Name) @(
    "password_min_code_points",
    "password_max_code_points",
    "password_composition_required",
    "periodic_password_change_required",
    "bootstrap_secret",
    "password_hash",
    "lockout",
    "session",
    "reset_token"
)) "IAM policy schema differs from the frozen contract"
Assert-Contract ($contract.iam_policy.password_min_code_points -eq 15) "password minimum must be 15 code points"
Assert-Contract ($contract.iam_policy.password_max_code_points -eq 128) "password maximum must be 128 code points"
Assert-Contract ($contract.iam_policy.password_composition_required -eq $false) "password composition rules must remain disabled"
Assert-Contract ($contract.iam_policy.periodic_password_change_required -eq $false) "periodic password changes must remain disabled"
Assert-Contract (Test-SameSet @($contract.iam_policy.bootstrap_secret.PSObject.Properties.Name) @("entropy_bits_min", "ttl_minutes", "single_use", "stored_as_digest")) "bootstrap-secret policy schema drifted"
Assert-Contract ($contract.iam_policy.bootstrap_secret.entropy_bits_min -eq 256) "bootstrap secret entropy must be exactly 256 bits"
Assert-Contract ($contract.iam_policy.bootstrap_secret.ttl_minutes -eq 30) "bootstrap secret TTL must be 30 minutes"
Assert-Contract ($contract.iam_policy.bootstrap_secret.single_use -eq $true) "bootstrap secret must be single use"
Assert-Contract ($contract.iam_policy.bootstrap_secret.stored_as_digest -eq $true) "bootstrap secret must be digest stored"
Assert-Contract (Test-SameSet @($contract.iam_policy.password_hash.PSObject.Properties.Name) @("algorithm", "memory_kib_min", "iterations_min", "parallelism_min")) "password-hash policy schema drifted"
Assert-Contract ($contract.iam_policy.password_hash.algorithm -ceq "Argon2id") "password hash must be Argon2id"
Assert-Contract ($contract.iam_policy.password_hash.memory_kib_min -eq 19456) "Argon2id memory floor must be exactly 19456 KiB"
Assert-Contract ($contract.iam_policy.password_hash.iterations_min -eq 2) "Argon2id iteration floor must be exactly 2"
Assert-Contract ($contract.iam_policy.password_hash.parallelism_min -eq 1) "Argon2id parallelism floor must be exactly 1"
Assert-Contract (Test-SameSet @($contract.iam_policy.lockout.PSObject.Properties.Name) @("attempts", "window_minutes", "durations_minutes")) "lockout policy schema drifted"
Assert-Contract ($contract.iam_policy.lockout.attempts -eq 5) "lockout threshold must be 5"
Assert-Contract ($contract.iam_policy.lockout.window_minutes -eq 15) "lockout window must be 15 minutes"
Assert-Contract (Test-ExactSequence @($contract.iam_policy.lockout.durations_minutes) @(15, 30, 60)) "lockout durations must remain ordered 15, 30 and 60 minutes"
Assert-Contract (Test-SameSet @($contract.iam_policy.session.PSObject.Properties.Name) @("idle_minutes", "absolute_hours", "high_risk_reauthentication_minutes", "entropy_bits_min")) "session policy schema drifted"
Assert-Contract ($contract.iam_policy.session.idle_minutes -eq 30) "session idle timeout must be 30 minutes"
Assert-Contract ($contract.iam_policy.session.absolute_hours -eq 8) "session absolute timeout must be 8 hours"
Assert-Contract ($contract.iam_policy.session.high_risk_reauthentication_minutes -eq 10) "session reauthentication window must be 10 minutes"
Assert-Contract ($contract.iam_policy.session.entropy_bits_min -eq 256) "session entropy must be exactly 256 bits"
Assert-Contract (Test-SameSet @($contract.iam_policy.reset_token.PSObject.Properties.Name) @("ttl_minutes", "entropy_bits_min", "single_use", "stored_as_digest")) "reset-token policy schema drifted"
Assert-Contract ($contract.iam_policy.reset_token.ttl_minutes -eq 15) "reset token TTL must be 15 minutes"
Assert-Contract ($contract.iam_policy.reset_token.entropy_bits_min -eq 256) "reset token entropy must be exactly 256 bits"
Assert-Contract ($contract.iam_policy.reset_token.single_use -eq $true) "reset token must be single use"
Assert-Contract ($contract.iam_policy.reset_token.stored_as_digest -eq $true) "reset token must be digest stored"

Assert-Contract (Test-SameSet @($contract.device_policy.PSObject.Properties.Name) @("enrollment_ttl_minutes", "credential_entropy_bits_min", "rotation_activation_minutes", "hard_revoke_increments_epoch")) "device policy schema differs from the frozen contract"
Assert-Contract ($contract.device_policy.enrollment_ttl_minutes -eq 15) "device enrollment TTL must be 15 minutes"
Assert-Contract ($contract.device_policy.credential_entropy_bits_min -eq 256) "device credential entropy must be exactly 256 bits"
Assert-Contract ($contract.device_policy.rotation_activation_minutes -eq 10) "device successor activation window must be 10 minutes"
Assert-Contract ($contract.device_policy.hard_revoke_increments_epoch -eq $true) "hard device revocation must increment the credential epoch"

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
    "password_hashes_and_secret_ciphertext_inside_encrypted_bundle",
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
$requiredManifestForbidden = @("password", "password_hash", "secret_value", "token", "device_credential", "database_dsn", "recovery_key")
Assert-Contract (Test-ExactSequence @($contract.storage.backup.manifest_forbidden_fields) $requiredManifestForbidden) "backup manifest forbidden fields are incomplete"

$ledger = $contract.storage.recovery_security_ledger
Assert-Contract (Test-SameSet @($ledger.PSObject.Properties.Name) @(
    "format_version",
    "append_only",
    "chain_algorithm",
    "record_encryption",
    "key_outside_live_store_and_backup_root",
    "ledger_outside_live_store_and_backup_root",
    "anchor_outside_live_store_backup_root_and_ledger",
    "anchor_type",
    "production_anchor_required",
    "restore_never_overwrites_replays_or_prunes_ledger",
    "record_states",
    "security_mutation_protocol",
    "unresolved_prepared_result",
    "tracked_security_facts",
    "backup_manifest_binds",
    "restore_plan_and_approval_bind_current_ledger_head",
    "execute_requires_unchanged_current_ledger_head",
    "post_restore_checkpoint_required_before_completed",
    "restore_user_rules",
    "restore_device_rules",
    "restore_token_rules",
    "missing_stale_or_unverifiable_result"
)) "recovery security ledger schema differs from the frozen contract"
Assert-Contract ($ledger.format_version -eq 1) "recovery security ledger format version must be 1"
Assert-Contract ($ledger.append_only -eq $true) "recovery security ledger must be append only"
Assert-Contract ($ledger.chain_algorithm -ceq "HMAC-SHA-256") "recovery security ledger chain must be authenticated"
Assert-Contract ($ledger.record_encryption -ceq "AEAD_AES_256_GCM") "recovery security ledger records must be AEAD protected"
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
Assert-Contract ($ledger.unresolved_prepared_result -ceq "FAIL_CLOSED_FOR_SUBJECT") "unresolved ledger preparation must fail closed"
Assert-Contract (Test-ExactSequence @($ledger.tracked_security_facts) @(
    "control_plane_security_epoch",
    "bootstrap_completed",
    "user_enabled_state",
    "user_account_state_generation",
    "user_authentication_epoch",
    "user_authorization_epoch",
    "user_credential_generation",
    "user_password_state",
    "device_family_state",
    "device_family_generation",
    "device_family_active_credential_version",
    "device_family_revocation_epoch",
    "latest_chain_head"
)) "recovery security ledger tracked facts are incomplete"
Assert-Contract (Test-ExactSequence @($ledger.backup_manifest_binds) @("security_ledger_sequence", "security_ledger_head_hash", "security_ledger_key_id")) "backup manifest does not bind the recovery security ledger"
Assert-Contract (Test-SameSet @($ledger.restore_user_rules.PSObject.Properties.Name) @("newer_disabled_state_wins", "maximum_authentication_epoch_wins", "older_password_generation_authentication_allowed", "older_password_generation_result")) "restore user reconciliation schema drifted"
Assert-Contract ($ledger.restore_user_rules.newer_disabled_state_wins -eq $true) "newer disabled-user state must win after restore"
Assert-Contract ($ledger.restore_user_rules.maximum_authentication_epoch_wins -eq $true) "maximum authentication epoch must win after restore"
Assert-Contract ($ledger.restore_user_rules.older_password_generation_authentication_allowed -eq $false) "an older restored password verifier must never authenticate"
Assert-Contract ($ledger.restore_user_rules.older_password_generation_result -ceq "RESET_REQUIRED") "older restored password generations must require reset"
Assert-Contract (Test-SameSet @($ledger.restore_device_rules.PSObject.Properties.Name) @("maximum_family_revocation_epoch_wins", "revoked_family_remains_revoked", "older_or_mismatched_active_version_authentication_allowed", "older_or_mismatched_active_version_result")) "restore device reconciliation schema drifted"
Assert-Contract ($ledger.restore_device_rules.maximum_family_revocation_epoch_wins -eq $true) "maximum device revocation epoch must win"
Assert-Contract ($ledger.restore_device_rules.revoked_family_remains_revoked -eq $true) "a revoked device family must remain revoked"
Assert-Contract ($ledger.restore_device_rules.older_or_mismatched_active_version_authentication_allowed -eq $false) "a predecessor or mismatched device version must never authenticate"
Assert-Contract ($ledger.restore_device_rules.older_or_mismatched_active_version_result -ceq "REENROLL_REQUIRED") "mismatched device versions must require re-enrollment"
Assert-Contract (Test-SameSet @($ledger.restore_token_rules.PSObject.Properties.Name) @("all_auth_sessions_invalidated", "all_one_time_tokens_invalidated", "all_device_sessions_invalidated")) "restore token invalidation schema drifted"
Assert-Contract ($ledger.restore_token_rules.all_auth_sessions_invalidated -eq $true) "restore must invalidate all AuthSessions"
Assert-Contract ($ledger.restore_token_rules.all_one_time_tokens_invalidated -eq $true) "restore must invalidate all one-time tokens"
Assert-Contract ($ledger.restore_token_rules.all_device_sessions_invalidated -eq $true) "restore must invalidate all device sessions"
Assert-Contract ($ledger.missing_stale_or_unverifiable_result -ceq "FAIL_CLOSED") "missing, stale or unverifiable security ledger state must fail closed"

Assert-Contract (Test-SameSet @($contract.retention.PSObject.Properties.Name) @("runtime_detail_days_default", "runtime_detail_days_configurable", "security_audit_uses_runtime_policy", "config_release_uses_runtime_policy", "device_revocation_uses_runtime_policy")) "retention policy schema drifted"
Assert-Contract ($contract.retention.runtime_detail_days_default -eq 3) "runtime detail retention must default to three days"
Assert-Contract ($contract.retention.runtime_detail_days_configurable -eq $true) "runtime detail retention must remain configurable"
Assert-Contract ($contract.retention.security_audit_uses_runtime_policy -eq $false) "security audit must not use runtime retention"
Assert-Contract ($contract.retention.config_release_uses_runtime_policy -eq $false) "releases must not use runtime retention"
Assert-Contract ($contract.retention.device_revocation_uses_runtime_policy -eq $false) "device revocations must not use runtime retention"

Assert-Contract (Test-SameSet @($contract.api.PSObject.Properties.Name) @("surfaces", "forbidden_request_scope_fields", "control_plane_forbidden_actor_fields", "device_forbidden_request_scope_fields", "forbidden_response_fields", "operations")) "API registry schema differs from the frozen contract"
Assert-Contract (Test-SameSet @($contract.api.surfaces.PSObject.Properties.Name) @("control_plane", "device")) "API surface registry differs from the frozen contract"
Assert-Contract ($contract.api.surfaces.control_plane -ceq "/api/v1/control-plane") "control-plane API namespace is incorrect"
Assert-Contract ($contract.api.surfaces.device -ceq "/api/v1/device") "device API namespace is incorrect"
Assert-Contract (Test-ExactSequence @($contract.api.forbidden_request_scope_fields) @("tenant_id", "deployment_id", "operator")) "API forbidden request scope fields are incomplete"
Assert-Contract (Test-ExactSequence @($contract.api.control_plane_forbidden_actor_fields) @("operator", "actor_id")) "control-plane actor fields must come from the authenticated session"
Assert-Contract (Test-ExactSequence @($contract.api.device_forbidden_request_scope_fields) @("tenant_id", "deployment_id", "site_id", "screen_id", "digital_human_instance_id")) "device forbidden scope fields are incomplete"
Assert-Contract (Test-ExactSequence @($contract.api.forbidden_response_fields) @("password", "password_hash", "secret_value", "database_dsn", "recovery_key", "session_digest", "csrf_secret", "reauthentication_proof")) "API forbidden response fields are incomplete"

$operations = @($contract.api.operations)
$operationIds = @($operations | ForEach-Object { [string]$_.operation_id })
Assert-Contract (($operationIds | Sort-Object -Unique).Count -eq $operationIds.Count) "API operation IDs must be unique"

$expectedOperationRegistrySha256 = "c5d948c1f03273f3659b6bc68ce15727cb85f1c3bdf5c669cb3cc3ad00cae884"
$operationRegistryCanonical = ConvertTo-CanonicalJson -Value $operations
$operationRegistrySha256 = Get-Sha256 -Text $operationRegistryCanonical
Assert-Contract ($operationRegistrySha256 -ceq $expectedOperationRegistrySha256) "API operation registry differs from the frozen exact method, path, permission and policy mapping"

$allowedMethods = @("GET", "POST", "PUT", "PATCH", "DELETE")
$allowedScopes = @("unauthenticated", "authenticated_tenant", "bootstrap_secret", "password_reset_token", "credential_bound_screen", "enrollment_token")
$allowedSecretResponses = @("none", "one_time_auth_session_cookie", "one_time_reset_token", "one_time_enrollment_secret", "one_time_device_credential", "one_time_successor_credential")
$allowedHighRiskPolicies = @("recent_reauthentication_reason", "different_user_recent_reauthentication_reason", "different_editor_reason", "production_four_eyes_v1")
$secretResponseOperations = @{
    "createAuthSession" = "one_time_auth_session_cookie"
    "issuePasswordReset" = "one_time_reset_token"
    "issueDeviceEnrollment" = "one_time_enrollment_secret"
    "claimDeviceEnrollment" = "one_time_device_credential"
    "rotateDeviceCredential" = "one_time_successor_credential"
}
$noStoreOperations = @(
    "completeBootstrap",
    "createAuthSession",
    "reauthenticateAuthSession",
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
    "reauthenticateAuthSession",
    "listOwnAuthSessions",
    "revokeOwnAuthSession",
    "deleteCurrentAuthSession",
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

    if (($operation.method -eq "POST") -and ($operationId -ne "createAuthSession")) {
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
$fineReportPut = @($operations | Where-Object { $_.operation_id -eq "putFineReportIdentityBinding" })
Assert-Contract (($fineReportPut.Count -eq 1) -and (Test-ExactSequence @($fineReportPut[0].required_permissions_all) @("screen.manage", "secret.write", "finereport.binding.manage"))) "FineReport binding PUT must require all frozen permissions"
$highRiskRead = @($operations | Where-Object { $_.operation_id -eq "getHighRiskAction" })
Assert-Contract (($highRiskRead.Count -eq 1) -and ($highRiskRead[0].authorization_rule -ceq "requester_or_risk_approve_with_target_scope")) "HighRiskAction read must remain requester-or-approver scoped"
foreach ($approvalOperationId in @("approveHighRiskAction", "rejectHighRiskAction")) {
    $approvalOperation = @($operations | Where-Object { $_.operation_id -eq $approvalOperationId })
    Assert-Contract (($approvalOperation.Count -eq 1) -and ($approvalOperation[0].approval_requires_expected_request_hash -eq $true)) "operation $approvalOperationId must bind the expected request hash"
}
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

$fixtureScreens = @($contract.three_screen_fixture.screens)
Assert-Contract ($fixtureScreens.Count -eq 3) "three-screen fixture must contain exactly three screens"
$fixtureScreenIds = @($fixtureScreens | ForEach-Object { [string]$_.screen_id })
Assert-Contract (($fixtureScreenIds | Sort-Object -Unique).Count -eq 3) "three-screen fixture screen IDs must be unique"
$fixtureDigitalHumanIds = @($fixtureScreens | ForEach-Object { [string]$_.digital_human_instance_id })
Assert-Contract (
    ($fixtureDigitalHumanIds.Count -eq 3) -and
    (@($fixtureDigitalHumanIds | Where-Object { [string]::IsNullOrWhiteSpace($_) }).Count -eq 0) -and
    (($fixtureDigitalHumanIds | Sort-Object -Unique).Count -eq 3)
) "three-screen fixture DigitalHumanInstance IDs must be non-empty and unique"
foreach ($fixtureScreen in $fixtureScreens) {
    Assert-Contract ($fixtureScreen.binding_generation -is [long] -or $fixtureScreen.binding_generation -is [int]) "three-screen fixture binding generation must be numeric"
    Assert-Contract ($fixtureScreen.binding_generation -gt 0) "three-screen fixture binding generation must be positive"
}
$targetScreenId = [string]$contract.three_screen_fixture.single_screen_publication.target_screen_id
$changedScreenIds = @($contract.three_screen_fixture.single_screen_publication.changed_screen_ids | ForEach-Object { [string]$_ })
$unchangedScreenIds = @($contract.three_screen_fixture.single_screen_publication.unchanged_screen_ids | ForEach-Object { [string]$_ })
Assert-Contract ($fixtureScreenIds -contains $targetScreenId) "single-screen fixture target must exist"
Assert-Contract (Test-SameSet $changedScreenIds @($targetScreenId)) "single-screen publication must change only its explicit target"
Assert-Contract (Test-SameSet $unchangedScreenIds @($fixtureScreenIds | Where-Object { $_ -ne $targetScreenId })) "single-screen publication must preserve the other two screens"
$targetScreen = @($fixtureScreens | Where-Object { $_.screen_id -eq $targetScreenId })
Assert-Contract (($targetScreen.Count -eq 1) -and ($targetScreen[0].binding_generation -eq $contract.three_screen_fixture.single_screen_publication.expected_binding_generation)) "single-screen fixture must compare the target binding generation"

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
