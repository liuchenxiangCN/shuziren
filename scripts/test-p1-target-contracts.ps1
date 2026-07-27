[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$validator = Join-Path $PSScriptRoot "validate-p1-target-contracts.ps1"
$sourceContract = Join-Path $repoRoot "docs\product\contracts\p1-target-contract.json"
$tempRoot = [System.IO.Path]::GetTempPath()
$suiteRoot = Join-Path $tempRoot ("shuziren-p1-contract-" + [guid]::NewGuid().ToString("N"))
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$strictUtf8 = New-Object System.Text.UTF8Encoding($false, $true)
$results = [System.Collections.Generic.List[object]]::new()

function Invoke-Validator {
    param(
        [string]$Path,
        [switch]$IncludeMarkdown,
        [string]$HostExecutable = "powershell.exe"
    )
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
    if (-not $IncludeMarkdown) {
        $arguments += "-SkipMarkdown"
    }
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        # Windows PowerShell promotes native stderr to non-terminating ErrorRecord
        # instances. Keep those records as fixture output instead of allowing the
        # suite-wide Stop preference to abort expected negative validations.
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
    foreach ($hostExecutable in @("powershell.exe", "pwsh.exe")) {
        $result = Invoke-Validator -Path $path -HostExecutable $hostExecutable
        if ($result.ExitCode -eq 0) {
            throw "Negative raw fixture $Name was accepted by $hostExecutable"
        }
        if (-not $result.Output.Contains($ExpectedFragment)) {
            throw "Negative raw fixture $Name did not report expected fragment '$ExpectedFragment' under $hostExecutable. Output: $($result.Output)"
        }
        $hostLabel = [System.IO.Path]::GetFileNameWithoutExtension($hostExecutable)
        $results.Add([pscustomobject]@{ Name = "$Name-$hostLabel"; Result = "REJECTED" })
    }
}

New-Item -ItemType Directory -Path $suiteRoot -Force | Out-Null

try {
    $baseline = Invoke-Validator -Path $sourceContract -IncludeMarkdown
    if ($baseline.ExitCode -ne 0) {
        throw "Baseline P1 contract failed: $($baseline.Output)"
    }
    $results.Add([pscustomobject]@{ Name = "baseline"; Result = "ACCEPTED" })

    Assert-RawRejects "duplicate-json-member" {
        param($text)
        $text.Replace('"schema_version": 1,', '"schema_version": 1, "schema_version": 1,')
    } "P1_CONTRACT_INVALID_JSON"

    Assert-RawRejects "unicode-escaped-duplicate-json-member" {
        param($text)
        $text.Replace('"schema_version": 1,', '"schema_version": 1, "\u0073chema_version": 1,')
    } "P1_CONTRACT_INVALID_JSON"

    Assert-RawRejects "non-finite-json-number" {
        param($text)
        $text.Replace('"schema_version": 1,', '"schema_version": NaN,')
    } "P1_CONTRACT_INVALID_JSON"

    Assert-RawRejects "positive-infinity-json-number" {
        param($text)
        $text.Replace('"schema_version": 1,', '"schema_version": Infinity,')
    } "P1_CONTRACT_INVALID_JSON"

    Assert-RawRejects "negative-infinity-json-number" {
        param($text)
        $text.Replace('"schema_version": 1,', '"schema_version": -Infinity,')
    } "P1_CONTRACT_INVALID_JSON"

    Assert-RawRejects "leading-zero-json-number" {
        param($text)
        $text.Replace('"schema_version": 1,', '"schema_version": 01,')
    } "P1_CONTRACT_INVALID_JSON"

    Assert-RawRejects "leading-plus-json-number" {
        param($text)
        $text.Replace('"schema_version": 1,', '"schema_version": +1,')
    } "P1_CONTRACT_INVALID_JSON"

    Assert-RawRejects "missing-fraction-json-number" {
        param($text)
        $text.Replace('"schema_version": 1,', '"schema_version": 1.,')
    } "P1_CONTRACT_INVALID_JSON"

    Assert-RawRejects "missing-exponent-json-number" {
        param($text)
        $text.Replace('"schema_version": 1,', '"schema_version": 1e,')
    } "P1_CONTRACT_INVALID_JSON"

    Assert-RawRejects "out-of-range-json-number" {
        param($text)
        $text.Replace('"schema_version": 1,', '"schema_version": 1e400,')
    } "P1_CONTRACT_INVALID_JSON"

    Assert-RawRejects "multiple-top-level-json-values" {
        param($text)
        $text + "`n{}"
    } "P1_CONTRACT_INVALID_JSON"

    Assert-RawRejects "trailing-json-garbage" {
        param($text)
        $text + "`ngarbage"
    } "P1_CONTRACT_INVALID_JSON"

    Assert-Rejects "implemented-claim" {
        param($contract)
        $contract.implemented = $true
    } "must not claim implementation"

    Assert-Rejects "missing-bootstrap-machine" {
        param($contract)
        $contract.state_machines.PSObject.Properties.Remove("bootstrap_grant")
    } "state-machine registry differs"

    Assert-Rejects "reset-token-reusable-transition" {
        param($contract)
        $contract.state_machines.password_reset_token.transitions = @($contract.state_machines.password_reset_token.transitions) + [pscustomobject]@{
            from = "CONSUMED"
            to = "ISSUED"
            operation = "reuse"
        }
    } "legal transition set differs"

    Assert-Rejects "revoked-session-reopens" {
        param($contract)
        $contract.state_machines.auth_session.transitions = @($contract.state_machines.auth_session.transitions) + [pscustomobject]@{
            from = "REVOKED"
            to = "ACTIVE"
            operation = "resume"
        }
    } "legal transition set differs"

    Assert-Rejects "config-draft-bypass-transition" {
        param($contract)
        $contract.state_machines.config_draft.transitions = @($contract.state_machines.config_draft.transitions) + [pscustomobject]@{
            from = "DRAFT"
            to = "RELEASED"
            operation = "bypass"
        }
    } "legal transition set differs"

    Assert-Rejects "missing-required-transition" {
        param($contract)
        $contract.state_machines.config_draft.transitions = @(
            $contract.state_machines.config_draft.transitions |
                Where-Object { -not (($_.from -eq "APPROVED") -and ($_.to -eq "RELEASED")) }
        )
    } "legal transition set differs"

    Assert-Rejects "device-credential-entry-ambiguity" {
        param($contract)
        $contract.state_machines.device_credential.entry_states.rotation_successor = "ACTIVE"
    } "entry rotation_successor is incorrect"

    Assert-Rejects "revoked-device-family-reopens" {
        param($contract)
        $contract.state_machines.device_credential_family.transitions = @($contract.state_machines.device_credential_family.transitions) + [pscustomobject]@{
            from = "REVOKED"
            to = "ACTIVE"
            operation = "reopen"
        }
    } "legal transition set differs"

    Assert-Rejects "restore-skips-security-reconciliation" {
        param($contract)
        $transition = $contract.state_machines.restore_plan.transitions |
            Where-Object { $_.from -eq "EXECUTING" -and $_.to -eq "RECONCILING_SECURITY" }
        $transition.to = "COMPLETED"
        $transition.operation = "verified_cutover"
    } "legal transition set differs"

    Assert-Rejects "degraded-restore-skips-security-reconciliation" {
        param($contract)
        $transition = $contract.state_machines.restore_plan.transitions |
            Where-Object { $_.to -eq "COMPLETED_DEGRADED" }
        $transition.from = "READY"
    } "legal transition set differs"

    Assert-Rejects "recovery-grant-commit-hardcodes-restore-anchor" {
        param($contract)
        $transition = $contract.state_machines.recovery_password_setup_grant.transitions |
            Where-Object { $_.from -eq "PROVISIONALLY_CONSUMED" -and $_.to -eq "COMMITTED_CONSUMED" }
        $transition.operation = "commit_with_restore_cutover_anchor"
    } "legal transition set differs"

    Assert-Rejects "recovery-grant-expiry-hardcodes-restore-pointer" {
        param($contract)
        $transition = $contract.state_machines.recovery_password_setup_grant.transitions |
            Where-Object { $_.from -eq "PROVISIONALLY_CONSUMED" -and $_.to -eq "EXPIRED" }
        $transition.operation = "expire_before_pointer_advance_destroy_provisional_verifiers_and_abort_entire_grant_set"
    } "legal transition set differs"

    Assert-Rejects "recovery-grant-abort-hardcodes-restore-cutover" {
        param($contract)
        $transition = $contract.state_machines.recovery_password_setup_grant.transitions |
            Where-Object { $_.from -eq "PROVISIONALLY_CONSUMED" -and $_.to -eq "ABORTED_REVOKED" }
        $transition.operation = "destroy_provisional_verifiers_and_abort_entire_grant_set_before_restore_cutover"
    } "legal transition set differs"

    Assert-Rejects "disaster-replacement-remains-provisional-until-ready" {
        param($contract)
        $replacement = $contract.iam_policy.disaster_recovery_authorization.local_disaster_admin_readiness_replacement
        $replacement.PSObject.Properties.Remove("replacement_user_person_binding_role_password_and_eligibility_generations_provisional_until_same_cutover_ledger_and_disaster_nonce_anchors")
        $replacement | Add-Member -NotePropertyName "replacement_user_person_binding_role_password_and_eligibility_generations_provisional_until_same_cutover_ledger_disaster_nonce_and_ready_fence_anchors" -NotePropertyValue $true
    } "local-disaster replacement field set differs"

    Assert-Rejects "platform-admin-permission-removed" {
        param($contract)
        $contract.roles.platform_admin = @($contract.roles.platform_admin | Where-Object { $_ -ne "risk.approve" })
    } "platform_admin permissions differ"

    Assert-Rejects "implementation-engineer-secret-write" {
        param($contract)
        $contract.roles.implementation_engineer = @($contract.roles.implementation_engineer) + "secret.write"
    } "implementation_engineer permissions differ"

    Assert-Rejects "operations-engineer-secret-write" {
        param($contract)
        $contract.roles.operations_engineer = @($contract.roles.operations_engineer) + "secret.write"
    } "operations_engineer permissions differ"

    Assert-Rejects "permission-registry-extra" {
        param($contract)
        $contract.permissions = @($contract.permissions) + "secret.reveal"
    } "permission registry differs"

    Assert-Rejects "draft-default-allow" {
        param($contract)
        $contract.configuration_authorization.deny_unclassified_fields = $false
    } "must deny unclassified fields"

    Assert-Rejects "draft-any-changed-path-authorizes" {
        param($contract)
        $contract.configuration_authorization.authorization_mode = "any_changed_path_any_permission"
    } "must require all changed-path permissions"

    Assert-Rejects "draft-partial-write" {
        param($contract)
        $contract.configuration_authorization.partial_write_allowed = $true
    } "partial draft writes must remain forbidden"

    Assert-Rejects "business-edits-fvs-field" {
        param($contract)
        $contract.configuration_authorization.field_permissions.PSObject.Properties["/fvs_binding_ref"].Value = @("config.edit_business")
    } "draft field /fvs_binding_ref permissions are incorrect"

    Assert-Rejects "fine-report-reference-loses-admin-permission" {
        param($contract)
        $contract.configuration_authorization.field_permissions.PSObject.Properties["/fine_report_identity_ref"].Value = @("config.edit_technical")
    } "draft field /fine_report_identity_ref permissions are incorrect"

    Assert-Rejects "draft-field-match-becomes-subtree" {
        param($contract)
        $contract.configuration_authorization.field_match_modes."/technical_policy" = "subtree"
    } "draft field /technical_policy must use exact path matching"

    Assert-Rejects "stale-fingerprint-relabels-error" {
        param($contract)
        $contract.resolution_policy.source_change_result = "PUBLISH_TARGET_CHANGED"
    } "stale resolution must have its own stable error"

    Assert-Rejects "publication-creates-release-targets" {
        param($contract)
        $contract.resolution_policy.publication_creates_release_targets = $true
    } "Publication must never create ReleaseTargets"

    Assert-Rejects "release-creation-kind-xor-disabled" {
        param($contract)
        $contract.resolution_policy.release_creation_branch_xor = $false
    } "normal and rollback release provenance must be mutually exclusive"

    Assert-Rejects "rollback-release-omits-high-risk-approval" {
        param($contract)
        $contract.resolution_policy.rollback_release_requires = @(
            $contract.resolution_policy.rollback_release_requires |
                Where-Object { $_ -ne "approved_high_risk_action" }
        )
    } "rollback release provenance requirements drifted"

    Assert-Rejects "rollback-source-crosses-screen" {
        param($contract)
        $contract.resolution_policy.rollback_source_screen_must_equal_destination_screen = $false
    } "rollback source screen must equal destination screen"

    Assert-Rejects "rollback-source-map-omits-destination" {
        param($contract)
        $contract.resolution_policy.rollback_source_map_destination_set_equals_release_target_set = $false
    } "rollback source-map destinations must equal the new release target set"

    Assert-Rejects "rollback-substitutes-current-secret" {
        param($contract)
        $contract.resolution_policy.rollback_substitution_allowed = $true
    } "rollback must not substitute content or versions"

    Assert-Rejects "approval-omits-layer-revisions" {
        param($contract)
        $contract.resolution_policy.approval_binds = @(
            $contract.resolution_policy.approval_binds |
                Where-Object { $_ -ne "inheritance_layer_revisions" }
        )
    } "approval does not bind the exact frozen resolution facts"

    Assert-Rejects "publication-composite-fk-loses-screen" {
        param($contract)
        $contract.data_integrity.publication_target_composite_foreign_key = @(
            $contract.data_integrity.publication_target_composite_foreign_key |
                Where-Object { $_ -ne "screen_id" }
        )
    } "PublicationTarget composite foreign key is incomplete"

    Assert-Rejects "publication-fk-loses-release" {
        param($contract)
        $contract.data_integrity.publication_target_references_publication_key = @(
            $contract.data_integrity.publication_target_references_publication_key |
                Where-Object { $_ -ne "release_id" }
        )
    } "PublicationTarget does not prove Publication release ownership"

    Assert-Rejects "mutable-secret-version" {
        param($contract)
        $contract.data_integrity.immutable_api_resources = @(
            $contract.data_integrity.immutable_api_resources |
                Where-Object { $_ -ne "SecretVersion" }
        )
    } "immutable API resource registry drifted"

    Assert-Rejects "production-auto-approval" {
        param($contract)
        $contract.high_risk_policy.production_requires_human_approval = $false
    } "production_requires_human_approval must remain true"

    Assert-Rejects "same-user-approval" {
        param($contract)
        $contract.high_risk_policy.initiator_must_differ_from_approver = $false
    } "initiator_must_differ_from_approver must remain true"

    Assert-Rejects "requester-lacks-target-authorization" {
        param($contract)
        $contract.high_risk_policy.request_requires_target_operation_authorization = $false
    } "request_requires_target_operation_authorization must remain true"

    Assert-Rejects "approval-omits-generation" {
        param($contract)
        $contract.high_risk_policy.request_hash_binds = @(
            $contract.high_risk_policy.request_hash_binds |
                Where-Object { $_ -ne "expected_generations" }
        )
    } "high-risk request hash bindings are incomplete"

    Assert-Rejects "protected-operation-removed" {
        param($contract)
        $contract.high_risk_policy.protected_operations = @(
            $contract.high_risk_policy.protected_operations |
                Where-Object { $_ -ne "executeRestorePlan" }
        )
    } "production four-eyes operation set drifted"

    Assert-Rejects "approval-executes-domain-effect" {
        param($contract)
        $contract.high_risk_policy.approval_only_records_evidence = $false
    } "approval_only_records_evidence must remain true"

    Assert-Rejects "high-risk-execution-not-resubmitted" {
        param($contract)
        $contract.high_risk_policy.execution_requires_protected_endpoint_resubmission = $false
    } "execution_requires_protected_endpoint_resubmission must remain true"

    Assert-Rejects "high-risk-consume-not-atomic" {
        param($contract)
        $contract.high_risk_policy.authorization_commit_semantics_by_kind.STANDARD_HIGH_RISK = "CONSUME_ACTION_AND_EFFECT_IN_DIFFERENT_TRANSACTIONS"
    } "consume_and_effect_atomic must remain true"

    Assert-Rejects "high-risk-approval-queues-execution" {
        param($contract)
        $contract.high_risk_policy.approval_queues_execution = $true
    } "high-risk approval must not enqueue execution"

    Assert-Rejects "high-risk-executor-changes-user" {
        param($contract)
        $contract.high_risk_policy.execution_caller_must_be_initiator = $false
    } "execution_caller_must_be_initiator must remain true"

    Assert-Rejects "high-risk-action-stores-secret-body" {
        param($contract)
        $contract.high_risk_policy.stored_request_body_policy = "FULL_BODY"
    } "must not persist a Secret-bearing request body"

    Assert-Rejects "high-risk-secret-body-uses-bare-sha" {
        param($contract)
        $contract.high_risk_policy.request_hash_algorithm = "SHA-256"
    } "must use keyed HMAC-SHA-256"

    Assert-Rejects "sensitive-request-hmac-key-enters-backup" {
        param($contract)
        $contract.api.sensitive_request_digest.key_outside_live_store_logs_and_backups = $false
    } "digest key must remain outside live storage, logs and backups"

    Assert-Rejects "async-high-risk-worker-reparses-request" {
        param($contract)
        $contract.high_risk_policy.async_worker_reparses_mutable_request_state = $true
    } "workers must not reparse mutable request state"

    Assert-Rejects "direct-permission-authorizes-restore" {
        param($contract)
        $contract.high_risk_policy.direct_permission_async_policy.allowed_operation_ids = @(
            $contract.high_risk_policy.direct_permission_async_policy.allowed_operation_ids
        ) + "executeRestorePlan"
    } "direct async authorization operation set drifted"

    Assert-Rejects "direct-permission-drops-evidence-id" {
        param($contract)
        $contract.high_risk_policy.execution_authorization_reference_schema = @(
            $contract.high_risk_policy.execution_authorization_reference_schema |
                Where-Object { $_ -ne "direct_operation_authorization_id" }
        )
    } "execution authorization reference schema drifted"

    Assert-Rejects "direct-permission-uses-high-risk-action-id" {
        param($contract)
        $contract.high_risk_policy.execution_authorization_reference_by_kind.DIRECT_PERMISSION =
            "high_risk_action_id_required_direct_operation_authorization_id_and_disaster_recovery_authorization_envelope_id_null"
    } "execution authorization ID nullability drifted"

    Assert-Rejects "disaster-command-fabricates-user-generations" {
        param($contract)
        $contract.high_risk_policy.execution_actor_nullability_by_kind.DISASTER_CUSTODIAN =
            "initiator_and_approver_user_person_and_all_identity_generation_fields_required"
    } "execution actor nullability drifted"

    Assert-Rejects "direct-permission-worker-reauthorizes" {
        param($contract)
        $contract.high_risk_policy.direct_permission_async_policy.worker_uses_only_frozen_intent_and_never_reauthorizes_from_mutable_state = $false
    } "worker_uses_only_frozen_intent_and_never_reauthorizes_from_mutable_state must remain true"

    Assert-Rejects "direct-permission-key-id-unregistered" {
        param($contract)
        $contract.key_management_policy.protected_record_key_id_fields.PSObject.Properties.Remove("DirectOperationAuthorization")
    } "protected-record key ID registry drifted"

    Assert-Rejects "ledger-high-risk-retry-returns-before-anchor" {
        param($contract)
        $contract.high_risk_policy.ledger_prepared_retry_result = "RETURN_DOMAIN_SUCCESS"
    } "retry must reconcile the anchor before success"

    Assert-Rejects "reset-token-not-single-use" {
        param($contract)
        $contract.iam_policy.reset_token.single_use = $false
    } "reset token must be single use"

    Assert-Rejects "password-reset-can-enable-user" {
        param($contract)
        $contract.invariants.password_reset_never_enables_user = $false
    } "password_reset_never_enables_user"

    Assert-Rejects "last-platform-admin-can-be-removed" {
        param($contract)
        $contract.invariants.network_product_mutation_may_remove_last_enabled_deployment_platform_admin = $true
    } "network_product_mutation_may_remove_last_enabled_deployment_platform_admin"

    Assert-Rejects "platform-admin-floor-lowered-to-one" {
        param($contract)
        $contract.invariants.product_mutations_may_not_reduce_credential_usable_enabled_deployment_platform_admins_below = 1
    } "product_mutations_may_not_reduce_credential_usable_enabled_deployment_platform_admins_below"

    Assert-Rejects "bootstrap-ttl-drift" {
        param($contract)
        $contract.iam_policy.bootstrap_secret.ttl_minutes = 60
    } "bootstrap secret TTL must be 30 minutes"

    Assert-Rejects "reset-token-not-digest" {
        param($contract)
        $contract.iam_policy.reset_token.stored_as_digest = $false
    } "reset token must be digest stored"

    Assert-Rejects "lockout-window-drift" {
        param($contract)
        $contract.iam_policy.lockout.window_minutes = 16
    } "lockout window must be 15 minutes"

    Assert-Rejects "lockout-order-drift" {
        param($contract)
        $contract.iam_policy.lockout.durations_minutes = @(60, 30, 15)
    } "lockout durations must remain ordered"

    Assert-Rejects "argon2-parallelism-drift" {
        param($contract)
        $contract.iam_policy.password_hash.parallelism_min = 2
    } "Argon2id parallelism floor must be exactly 1"

    Assert-Rejects "session-entropy-drift" {
        param($contract)
        $contract.iam_policy.session.entropy_bits_min = 255
    } "session entropy must be exactly 256 bits"

    Assert-Rejects "reauth-window-drift" {
        param($contract)
        $contract.iam_policy.session.high_risk_reauthentication_minutes = 11
    } "session reauthentication window must be 10 minutes"

    Assert-Rejects "device-activation-window-drift" {
        param($contract)
        $contract.device_policy.rotation_activation_minutes = 11
    } "device successor activation window must be 10 minutes"

    Assert-Rejects "device-family-revoke-not-atomic" {
        param($contract)
        $contract.device_policy.hard_revoke_atomic_family = $false
    } "hard device revocation must revoke the family atomically"

    Assert-Rejects "screen-allows-two-active-device-families" {
        param($contract)
        $contract.invariants.max_active_device_credential_families_per_screen = 2
    } "max_active_device_credential_families_per_screen"

    Assert-Rejects "family-allows-two-pending-successors" {
        param($contract)
        $contract.invariants.max_pending_device_successors_per_family = 2
    } "max_pending_device_successors_per_family"

    Assert-Rejects "device-rotation-loses-family-generation" {
        param($contract)
        $operation = $contract.api.operations | Where-Object { $_.operation_id -eq "rotateDeviceCredential" }
        $operation.concurrency = "credential_epoch"
    } "rotateDeviceCredential must bind credential epoch and family generation"

    Assert-Rejects "credential-rotation-revoked-version-usable" {
        param($contract)
        $contract.external_credential_rotation_policy.revoked_use_allowed = $true
    } "revoked external credential versions must never be usable"

    Assert-Rejects "credential-rotation-revoked-version-reopens" {
        param($contract)
        $contract.external_credential_rotation_policy.version_transitions = @($contract.external_credential_rotation_policy.version_transitions) + "REVOKED|ACTIVE|restore"
    } "external credential version transitions drifted"

    Assert-Rejects "credential-rotation-unbounded-retiring-window" {
        param($contract)
        $contract.external_credential_rotation_policy.retiring_max_hours = 720
    } "retiring window must be capped at 24 hours"

    Assert-Rejects "sqlite-version-drift" {
        param($contract)
        $contract.storage.embedded.minimum_version = "3.44"
    } "embedded SQLite minimum version must be 3.45"

    Assert-Rejects "backup-retention-hourly-drift" {
        param($contract)
        $contract.storage.backup.retention_hourly = 23
    } "hourly backup retention must be 24"

    Assert-Rejects "backup-retention-daily-drift" {
        param($contract)
        $contract.storage.backup.retention_daily = 6
    } "daily backup retention must be 7"

    Assert-Rejects "backup-retention-weekly-drift" {
        param($contract)
        $contract.storage.backup.retention_weekly = 3
    } "weekly backup retention must be 4"

    Assert-Rejects "ledger-inside-backup" {
        param($contract)
        $contract.storage.recovery_security_ledger.ledger_outside_live_store_and_backup_root = $false
    } "ledger_outside_live_store_and_backup_root must remain true"

    Assert-Rejects "ledger-anchor-optional" {
        param($contract)
        $contract.storage.recovery_security_ledger.production_anchor_required = $false
    } "production_anchor_required must remain true"

    Assert-Rejects "ledger-unauthenticated-chain" {
        param($contract)
        $contract.storage.recovery_security_ledger.chain_algorithm = "SHA-256"
    } "ledger chain must be authenticated"

    Assert-Rejects "ledger-missing-password-generation" {
        param($contract)
        $contract.storage.recovery_security_ledger.tracked_security_facts = @(
            $contract.storage.recovery_security_ledger.tracked_security_facts |
                Where-Object { $_ -ne "user_credential_generation" }
        )
    } "ledger tracked facts are incomplete"

    Assert-Rejects "ledger-missing-device-active-version" {
        param($contract)
        $contract.storage.recovery_security_ledger.tracked_security_facts = @(
            $contract.storage.recovery_security_ledger.tracked_security_facts |
                Where-Object { $_ -ne "device_family_active_credential_version" }
        )
    } "ledger tracked facts are incomplete"

    Assert-Rejects "ledger-missing-role-scope-snapshot" {
        param($contract)
        $contract.storage.recovery_security_ledger.tracked_security_facts = @(
            $contract.storage.recovery_security_ledger.tracked_security_facts |
                Where-Object { $_ -ne "user_role_scope_assignment_snapshot" }
        )
    } "ledger tracked facts are incomplete"

    Assert-Rejects "ledger-omits-bootstrap-completion" {
        param($contract)
        $contract.storage.recovery_security_ledger.ledger_backed_mutations = @(
            $contract.storage.recovery_security_ledger.ledger_backed_mutations |
                Where-Object { $_ -ne "bootstrap_completion" }
        )
    } "ledger-backed security mutation set drifted"

    Assert-Rejects "ledger-omits-enrollment-family-create" {
        param($contract)
        $contract.storage.recovery_security_ledger.ledger_backed_mutations = @(
            $contract.storage.recovery_security_ledger.ledger_backed_mutations |
                Where-Object { $_ -ne "device_credential_family_create_from_enrollment_claim" }
        )
    } "ledger-backed security mutation set drifted"

    Assert-Rejects "ledger-user-identity-snapshot-can-carry-credential" {
        param($contract)
        $contract.storage.recovery_security_ledger.user_identity_snapshot_schema[9] = "password_verifier"
    } "user identity snapshot schema is incomplete"

    Assert-Rejects "restore-resurrects-old-admin-role" {
        param($contract)
        $contract.storage.recovery_security_ledger.restore_user_rules.latest_role_scope_assignment_snapshot_is_authoritative = $false
    } "latest role/scope snapshot must be authoritative after restore"

    Assert-Rejects "restore-merges-old-role-scope" {
        param($contract)
        $contract.storage.recovery_security_ledger.restore_user_rules.role_scope_reconciliation_mode = "MERGE"
    } "must replace rather than merge"

    Assert-Rejects "unknown-role-scope-allowed" {
        param($contract)
        $contract.iam_policy.authorization_scope.unknown_role_scope_or_catalog_result = "ALLOW"
    } "unknown role/scope/catalog entries must deny"

    Assert-Rejects "restore-old-password-active" {
        param($contract)
        $contract.storage.recovery_security_ledger.restore_user_rules.older_password_generation_authentication_allowed = $true
    } "older restored password verifier must never authenticate"

    Assert-Rejects "restore-disabled-user-enabled" {
        param($contract)
        $contract.storage.recovery_security_ledger.restore_user_rules.newer_disabled_state_wins = $false
    } "newer disabled-user state must win"

    Assert-Rejects "restore-reconstructed-user-gains-credential" {
        param($contract)
        $contract.storage.recovery_security_ledger.restore_user_rules.reconstructed_user_contains_credential_material = $true
    } "reconstructed ledger-only user must never receive credential material"

    Assert-Rejects "restore-identity-conflict-cuts-over" {
        param($contract)
        $contract.storage.recovery_security_ledger.restore_user_rules.reconstructed_identity_conflict_result = "MERGE_BY_USERNAME"
    } "identity conflict must fail restore before cutover"

    Assert-Rejects "restore-predecessor-device-active" {
        param($contract)
        $contract.storage.recovery_security_ledger.restore_device_rules.older_or_mismatched_active_version_authentication_allowed = $true
    } "predecessor or mismatched device version must never authenticate"

    Assert-Rejects "restore-predecessor-secret-usable" {
        param($contract)
        $contract.storage.recovery_security_ledger.restore_secret_rules.restored_version_cannot_gain_usability = $false
    } "restore must never increase Secret version usability"

    Assert-Rejects "restore-predecessor-finereport-binding-usable" {
        param($contract)
        $contract.storage.recovery_security_ledger.restore_finereport_rules.restored_binding_cannot_gain_usability = $false
    } "restore must never increase FineReport binding-version usability"

    Assert-Rejects "restore-revives-pending-high-risk-action" {
        param($contract)
        $contract.storage.recovery_security_ledger.restore_approval_rules.all_restored_pending_or_approved_high_risk_actions_result = "PRESERVE"
    } "restored unfinished high-risk actions must fail"

    Assert-Rejects "restore-loses-own-authorization-evidence" {
        param($contract)
        $contract.storage.recovery_security_ledger.restore_continuity.external_authenticated_envelope_required = $false
    } "restore continuity must use an external authenticated envelope"

    Assert-Rejects "restore-continuity-drops-audit-suffix" {
        param($contract)
        $contract.storage.recovery_security_ledger.restore_continuity.common_carried_forward_records = @(
            $contract.storage.recovery_security_ledger.restore_continuity.common_carried_forward_records |
                Where-Object { $_ -ne "SecurityAuditSuffix" }
        )
    } "restore continuity common record set drifted"

    Assert-Rejects "restore-continuity-authenticates-before-ledger-prepare" {
        param($contract)
        $protocol = @($contract.storage.recovery_security_ledger.restore_continuity.continuity_envelope_protocol)
        $protocol[1] = "authenticate_envelope_with_prepared_sequence"
        $protocol[2] = "append_prepared_binding_payload_hash_and_fsync"
        $contract.storage.recovery_security_ledger.restore_continuity.continuity_envelope_protocol = $protocol
    } "restore continuity envelope protocol drifted"

    Assert-Rejects "restore-missing-authoritative-credential-cuts-over-by-default" {
        param($contract)
        $contract.storage.recovery_security_ledger.restore_degraded_credential_rules.default_cutover_when_authoritative_material_missing = $true
    } "must not cut over by default when authoritative credential material is missing"

    Assert-Rejects "restore-cutover-drops-previous-store-early" {
        param($contract)
        $contract.storage.recovery_security_ledger.restore_continuity.online_previous_store_retained_until_committed_anchor = $false
    } "restore continuity online_previous_store_retained_until_committed_anchor must remain true"

    Assert-Rejects "unresolved-ledger-prepared-allows-access" {
        param($contract)
        $contract.storage.recovery_security_ledger.unresolved_prepared_result = "ALLOW"
    } "unresolved ledger preparation must fail closed"

    Assert-Rejects "missing-ledger-allows-cutover" {
        param($contract)
        $contract.storage.recovery_security_ledger.missing_stale_or_unverifiable_result = "ALLOW"
    } "missing, stale or unverifiable security ledger state must fail closed"

    Assert-Rejects "missing-consume-password-reset-operation" {
        param($contract)
        $contract.api.operations = @($contract.api.operations | Where-Object { $_.operation_id -ne "consumePasswordReset" })
    } "API operation registry differs"

    Assert-Rejects "missing-reauthentication-operation" {
        param($contract)
        $contract.api.operations = @($contract.api.operations | Where-Object { $_.operation_id -ne "reauthenticateAuthSession" })
    } "API operation registry differs"

    Assert-Rejects "missing-session-list-operation" {
        param($contract)
        $contract.api.operations = @($contract.api.operations | Where-Object { $_.operation_id -ne "listOwnAuthSessions" })
    } "API operation registry differs"

    Assert-Rejects "missing-revise-draft-operation" {
        param($contract)
        $contract.api.operations = @($contract.api.operations | Where-Object { $_.operation_id -ne "reviseConfigDraft" })
    } "API operation registry differs"

    Assert-Rejects "missing-abandon-draft-operation" {
        param($contract)
        $contract.api.operations = @($contract.api.operations | Where-Object { $_.operation_id -ne "abandonConfigDraft" })
    } "API operation registry differs"

    Assert-Rejects "business-only-revises-mixed-draft" {
        param($contract)
        $operation = $contract.api.operations | Where-Object { $_.operation_id -eq "reviseConfigDraft" }
        $operation.field_permission_policy = "any_editor_permission"
    } "reviseConfigDraft must close the frozen revision"

    Assert-Rejects "client-asserts-approved-draft-stale" {
        param($contract)
        $operation = $contract.api.operations | Where-Object { $_.operation_id -eq "reviseConfigDraft" }
        $operation.server_revalidates_stale_fingerprint_and_epoch = $false
    } "reviseConfigDraft must close the frozen revision"

    Assert-Rejects "role-replace-loses-generation" {
        param($contract)
        $operation = $contract.api.operations | Where-Object { $_.operation_id -eq "replaceUserRoles" }
        $operation.concurrency = "if_match"
    } "replaceUserRoles must bind the user ETag"

    Assert-Rejects "device-revoke-loses-family-etag" {
        param($contract)
        $operation = $contract.api.operations | Where-Object { $_.operation_id -eq "revokeDeviceCredential" }
        $operation.concurrency = "expected_credential_epoch"
    } "revokeDeviceCredential must bind DeviceCredentialFamily"

    Assert-Rejects "publish-permission-swap" {
        param($contract)
        $operation = $contract.api.operations | Where-Object { $_.operation_id -eq "publishToScreen" }
        $operation.required_permissions_any = @("audit.read")
    } "API operation registry differs"

    Assert-Rejects "operation-path-drift" {
        param($contract)
        $operation = $contract.api.operations | Where-Object { $_.operation_id -eq "getConfigRelease" }
        $operation.path = "/config-releases/{release_id}/changed"
    } "API operation registry differs"

    Assert-Rejects "immutable-release-delete" {
        param($contract)
        $operation = $contract.api.operations | Where-Object { $_.operation_id -eq "getConfigRelease" }
        $operation.operation_id = "deleteConfigRelease"
        $operation.method = "DELETE"
    } "immutable release, target or audit resource"

    Assert-Rejects "generic-high-risk-create" {
        param($contract)
        $operation = $contract.api.operations | Where-Object { $_.operation_id -eq "getHighRiskAction" }
        $operation.operation_id = "createHighRiskAction"
        $operation.method = "POST"
        $operation.path = "/high-risk-actions"
        $operation.idempotency = "required"
    } "generic high-risk action creation route must not exist"

    Assert-Rejects "fine-report-required-all-dropped" {
        param($contract)
        $operation = $contract.api.operations | Where-Object { $_.operation_id -eq "putFineReportIdentityBinding" }
        $operation.required_permissions_all = @("screen.manage", "secret.write")
    } "FineReport binding PUT must require all frozen permissions"

    Assert-Rejects "protected-policy-marker-dropped" {
        param($contract)
        $operation = $contract.api.operations | Where-Object { $_.operation_id -eq "revokeDeviceCredential" }
        $operation.high_risk_policy = "recent_reauthentication_reason"
    } "production four-eyes markers must match exactly"

    Assert-Rejects "publish-loses-if-match" {
        param($contract)
        $operation = $contract.api.operations | Where-Object { $_.operation_id -eq "publishToScreen" }
        $operation.concurrency = "binding_generation"
    } "API operation registry differs"

    Assert-Rejects "device-ack-uses-control-plane-if-match" {
        param($contract)
        $operation = $contract.api.operations | Where-Object { $_.operation_id -eq "acknowledgeDeviceRelease" }
        $operation.concurrency = "if_match_and_binding_generation_and_content_hash"
    } "API operation registry differs"

    Assert-Rejects "sensitive-response-cacheable" {
        param($contract)
        $operation = $contract.api.operations | Where-Object { $_.operation_id -eq "issuePasswordReset" }
        $operation.PSObject.Properties.Remove("response_cache_control")
    } "must require Cache-Control no-store"

    Assert-Rejects "session-list-can-expose-digest" {
        param($contract)
        $contract.api.forbidden_response_fields = @(
            $contract.api.forbidden_response_fields |
                Where-Object { $_ -ne "session_digest" }
        )
    } "API forbidden response fields are incomplete"

    Assert-Rejects "setup-allows-publication" {
        param($contract)
        $contract.deployment_mode_policy.setup_allowed_operations = @($contract.deployment_mode_policy.setup_allowed_operations) + "publishToScreen"
    } "SETUP operation allowlist drifted"

    Assert-Rejects "recovery-required-allows-secret-mutation" {
        param($contract)
        $contract.deployment_mode_policy.production_recovery_required_policy.allowed_network_operations = @(
            $contract.deployment_mode_policy.production_recovery_required_policy.allowed_network_operations
        ) + "createSecret"
    } "RECOVERY_REQUIRED operation allowlist drifted"

    Assert-Rejects "bootstrap-allows-identity-substitution" {
        param($contract)
        $contract.iam_policy.bootstrap_secret.complete_bootstrap_cannot_substitute_person_user_role_or_target_channel = $false
    } "bootstrap identity binding complete_bootstrap_cannot_substitute_person_user_role_or_target_channel must remain true"

    Assert-Rejects "provisioning-reset-grants-authority" {
        param($contract)
        $contract.iam_policy.reset_token.provisioning_setup_consumption_sets_only_credential_and_possession_evidence_and_never_enables_or_grants_role = $false
    } "provisioning credential setup must not grant authority"

    Assert-Rejects "update-user-allows-enabled-field" {
        param($contract)
        $operation = $contract.api.operations | Where-Object { $_.operation_id -eq "updateUser" }
        $operation.request_allowed_fields = @($operation.request_allowed_fields) + "enabled"
    } "updateUser must not bypass dedicated credential, authority or person-binding operations"

    Assert-Rejects "csrf-bootstrap-not-unique-exception" {
        param($contract)
        $contract.iam_policy.browser_session_security.authenticated_session_bootstrap_is_the_only_cookie_mutation_exempt_from_existing_csrf_header = $false
    } "authenticated CSRF bootstrap must be the one narrow cookie-mutation CSRF exception"

    Assert-Rejects "reauthentication-does-not-rotate-csrf" {
        param($contract)
        $security = $contract.iam_policy.browser_session_security
        $security.PSObject.Properties.Remove("csrf_token_rotated_after_authentication_reauthentication_and_privilege_change")
        $security | Add-Member -NotePropertyName "csrf_token_rotated_after_authentication_and_privilege_change" -NotePropertyValue $true
    } "browser session security schema drifted"

    Assert-Rejects "same-person-high-risk-approval" {
        param($contract)
        $contract.iam_policy.human_operator_independence.high_risk_initiator_and_approver_person_ids_must_differ = $false
    } "high-risk approvers must be different people"

    Assert-Rejects "aead-nonce-reuse-allowed" {
        param($contract)
        $contract.key_management_policy.aead_policy.nonce_unique_per_key_required = $false
    } "AEAD nonce uniqueness is mandatory"

    Assert-Rejects "password-reset-verifier-omits-issuance-kind" {
        param($contract)
        $contract.key_management_policy.keyed_verifier_policy.input_by_record.PasswordResetToken =
            $contract.key_management_policy.keyed_verifier_policy.input_by_record.PasswordResetToken.Replace("|issuance_kind", "")
    } "password reset verifier must bind issuance kind and target channel"

    Assert-Rejects "hmac-alone-opens-ready-fence" {
        param($contract)
        $contract.deployment_mode_policy.operational_fence_policy.hmac_only_ready_successor_without_verified_offline_or_activation_evidence_result = "READY"
    } "an HMAC-only READY fence must fail integrity verification"

    Assert-Rejects "ready-fence-clears-without-offline-authority" {
        param($contract)
        $contract.deployment_mode_policy.operational_fence_policy.clear_fence_requires_local_offline_authorization_complete_readiness_and_ledger_anchor = $false
    } "clearing a production fence requires offline authority, complete readiness and the ledger anchor"

    Assert-Rejects "emergency-recovery-increases-authority" {
        param($contract)
        $contract.deployment_mode_policy.emergency_authority_reduction.authority_increase_enable_role_grant_or_new_credential_forbidden = $false
    } "emergency authority reduction must never increase authority"

    Assert-Rejects "crypto-root-recovery-writes-ready" {
        param($contract)
        $contract.deployment_mode_policy.cryptographic_root_recovery.cannot_write_ready_fence_modify_users_roles_credentials_or_business_state = $false
    } "cryptographic root recovery must not grant READY or business authority"

    Assert-Rejects "readiness-external-audit-loses-final-result" {
        param($contract)
        $contract.deployment_mode_policy.production_readiness_recovery.external_audit_policy.record_schema = @(
            $contract.deployment_mode_policy.production_readiness_recovery.external_audit_policy.record_schema |
                Where-Object { $_ -ne "finalized_result_hash" }
        )
    } "production readiness external audit schema drifted"

    Assert-Rejects "crypto-root-external-audit-loses-checkpoint" {
        param($contract)
        $contract.deployment_mode_policy.cryptographic_root_recovery.external_audit_policy.record_schema = @(
            $contract.deployment_mode_policy.cryptographic_root_recovery.external_audit_policy.record_schema |
                Where-Object { $_ -ne "recovery_required_checkpoint_hash" }
        )
    } "cryptographic root recovery external audit schema drifted"

    Assert-Rejects "local-recovery-audit-record-unregistered" {
        param($contract)
        $contract.internal_security_records = @(
            $contract.internal_security_records |
                Where-Object { $_ -ne "ExternalProductionReadinessRecoveryAudit" }
        )
    } "local recovery external audit record is absent from the internal registry"

    Assert-Rejects "local-maintenance-audit-drops-terminal-nonce" {
        param($contract)
        $contract.deployment_mode_policy.local_maintenance_security_audit_policy.common_record_schema = @(
            $contract.deployment_mode_policy.local_maintenance_security_audit_policy.common_record_schema |
                Where-Object { $_ -ne "terminal_nonce_hash" }
        )
    } "local maintenance security-audit record schema drifted"

    Assert-Rejects "local-maintenance-audit-fabricates-network-action" {
        param($contract)
        $contract.deployment_mode_policy.local_maintenance_security_audit_policy.network_execution_authorization_ids_are_null = $false
    } "network_execution_authorization_ids_are_null must remain true"

    Assert-Rejects "readiness-audit-uses-emergency-nonce" {
        param($contract)
        $contract.deployment_mode_policy.local_maintenance_security_audit_policy.by_operation.recoverProductionReadiness.terminal_nonce_record =
            "EmergencyAuthorityReductionNonceRecord"
    } "local maintenance audit mapping drifted for recoverProductionReadiness"

    Assert-Rejects "normal-restore-accepts-full-loss-source" {
        param($contract)
        $contract.storage.recovery_security_ledger.restore_continuity.allowed_authorization_and_source_mode_combinations.NORMAL_API_FOUR_EYES = @(
            "ONLINE_ACTIVE_STORE",
            "FULL_LOSS_ACTIVE_STORE_UNAVAILABLE"
        )
    } "normal restore authorization must remain online-source only"

    Assert-Rejects "full-loss-fabricates-audit-event" {
        param($contract)
        $contract.storage.recovery_security_ledger.restore_continuity.security_audit_suffix_policy_by_source_mode.FULL_LOSS_ACTIVE_STORE_UNAVAILABLE.event_count = 1
    } "full-loss restore audit suffix must contain zero live events"

    Assert-Rejects "full-loss-requires-missing-live-barrier" {
        param($contract)
        $contract.storage.recovery_security_ledger.restore_continuity.security_audit_suffix_policy_by_source_mode.FULL_LOSS_ACTIVE_STORE_UNAVAILABLE.live_head_or_maintenance_barrier_required = $true
    } "full-loss restore must not require an unavailable live head or maintenance barrier"

    Assert-Rejects "external-recovery-audit-loses-quorum" {
        param($contract)
        $contract.storage.recovery_security_ledger.restore_continuity.external_recovery_audit_policy.each_record_requires_same_valid_two_of_three_distinct_custodian_quorum = $false
    } "external recovery audit records must retain the same two-of-three custodian quorum"

    Assert-Rejects "external-recovery-audit-unanchored-first-record" {
        param($contract)
        $contract.storage.recovery_security_ledger.restore_continuity.external_recovery_audit_policy.first_record_previous_hash = "NULL"
    } "external recovery audit first previous hash drifted"

    Assert-Rejects "external-recovery-audit-terminal-chain-disconnected" {
        param($contract)
        $contract.storage.recovery_security_ledger.restore_continuity.external_recovery_audit_policy.first_staged_security_audit_event_binds_backup_head_and_external_recovery_audit_terminal_hash = $false
    } "staged security audit must bind the backup head and external recovery audit terminal hash"

    Assert-Rejects "external-recovery-audit-signature-purpose-unbound" {
        param($contract)
        $contract.storage.recovery_security_ledger.restore_continuity.external_recovery_audit_policy.signature_verification_requires_record_bound_key_id_and_exact_purpose = $false
    } "external recovery audit signatures must bind their key ID and exact purpose"

    Assert-Rejects "production-restore-directly-opens-ready" {
        param($contract)
        $contract.storage.recovery_security_ledger.restore_continuity.every_production_restore_finalization_sets_or_keeps_recovery_required_until_separate_local_production_readiness_recovery = $false
    } "restore continuity every_production_restore_finalization_sets_or_keeps_recovery_required_until_separate_local_production_readiness_recovery must remain true"

    Assert-Rejects "internal-error-retryability-disagrees-with-registry" {
        param($contract)
        $contract.high_risk_policy.request_hash_key_temporarily_unavailable_result.retryable = $false
    } "internal result KEY_SERVICE_UNAVAILABLE retryability differs from the API registry"

    Assert-Rejects "password-reset-response-aad-omits-issuance-kind" {
        param($contract)
        $contract.api.one_time_secret_response_replay.associated_data_branch_fields_by_operation.issuePasswordReset = @(
            $contract.api.one_time_secret_response_replay.associated_data_branch_fields_by_operation.issuePasswordReset |
                Where-Object { $_ -ne "issuance_kind" }
        )
    } "password reset one-time response associated-data binding drifted"

    Assert-Rejects "duplicate-operation-id" {
        param($contract)
        $contract.api.operations[1].operation_id = $contract.api.operations[0].operation_id
    } "operation IDs must be unique"

    Assert-Rejects "duplicate-digital-human-instance" {
        param($contract)
        $contract.three_screen_fixture.screens[1].digital_human_instance_id = $contract.three_screen_fixture.screens[0].digital_human_instance_id
    } "DigitalHumanInstance IDs must be non-empty and unique"

    Assert-Rejects "single-screen-publication-no-op-release" {
        param($contract)
        $targetId = $contract.three_screen_fixture.single_screen_publication.target_screen_id
        $target = $contract.three_screen_fixture.screens | Where-Object { $_.screen_id -eq $targetId }
        $currentTarget = $contract.three_screen_fixture.release_targets |
            Where-Object { $_.release_target_id -eq $target.desired_release_target_id }
        $contract.three_screen_fixture.single_screen_publication.new_release_id = $currentTarget.release_id
        $contract.three_screen_fixture.single_screen_publication.new_release_target_id = $currentTarget.release_target_id
    } "publication must not be a no-op ReleaseTarget"

    Assert-Rejects "single-screen-publication-applies-before-ack" {
        param($contract)
        $targetId = $contract.three_screen_fixture.single_screen_publication.target_screen_id
        $target = $contract.three_screen_fixture.single_screen_publication.post_publish_bindings |
            Where-Object { $_.screen_id -eq $targetId }
        $target.applied_release_target_id = $contract.three_screen_fixture.single_screen_publication.new_release_target_id
    } "target screen must change desired ReleaseTarget, generation and resource revision only at publication"

    Assert-Rejects "single-screen-publication-uses-cross-screen-release-target" {
        param($contract)
        $targetId = $contract.three_screen_fixture.single_screen_publication.target_screen_id
        $crossScreenTarget = $contract.three_screen_fixture.release_targets |
            Where-Object { $_.screen_id -ne $targetId } |
            Select-Object -First 1
        $contract.three_screen_fixture.single_screen_publication.new_release_id = $crossScreenTarget.release_id
        $contract.three_screen_fixture.single_screen_publication.new_release_target_id = $crossScreenTarget.release_target_id
    } "new ReleaseTarget must resolve to the target screen and release"

    Assert-Rejects "single-screen-publication-changes-neighbor-generation" {
        param($contract)
        $targetId = $contract.three_screen_fixture.single_screen_publication.target_screen_id
        $neighbor = $contract.three_screen_fixture.single_screen_publication.post_publish_bindings |
            Where-Object { $_.screen_id -ne $targetId } |
            Select-Object -First 1
        $neighbor.binding_generation = [long]$neighbor.binding_generation + 1
    } "non-target screens must remain byte-for-byte binding-equivalent"

    Assert-Rejects "single-screen-publication-changes-target-digital-human" {
        param($contract)
        $targetId = $contract.three_screen_fixture.single_screen_publication.target_screen_id
        $target = $contract.three_screen_fixture.single_screen_publication.post_publish_bindings |
            Where-Object { $_.screen_id -eq $targetId }
        $target.digital_human_instance_id = $contract.three_screen_fixture.screens[0].digital_human_instance_id
    } "target screen must change desired ReleaseTarget, generation and resource revision only at publication"

    Assert-Rejects "single-screen-ack-changes-neighbor-timestamp" {
        param($contract)
        $targetId = $contract.three_screen_fixture.single_screen_publication.target_screen_id
        $neighbor = $contract.three_screen_fixture.single_screen_publication.post_ack_bindings |
            Where-Object { $_.screen_id -ne $targetId } |
            Select-Object -First 1
        $neighbor.last_acknowledged_at = "2026-07-27T00:30:00Z"
    } "non-target screens must remain byte-for-byte binding-equivalent"

    Assert-Rejects "single-screen-publication-changes-neighbor-resource-revision" {
        param($contract)
        $targetId = $contract.three_screen_fixture.single_screen_publication.target_screen_id
        $neighbor = $contract.three_screen_fixture.single_screen_publication.post_publish_bindings |
            Where-Object { $_.screen_id -ne $targetId } |
            Select-Object -First 1
        $neighbor.resource_revision = [long]$neighbor.resource_revision + 1
    } "non-target screens must remain byte-for-byte binding-equivalent"

    Assert-Rejects "cross-screen-change" {
        param($contract)
        $contract.three_screen_fixture.single_screen_publication.changed_screen_ids = @(
            $contract.three_screen_fixture.single_screen_publication.target_screen_id,
            $contract.three_screen_fixture.screens[0].screen_id
        )
    } "must change only its explicit target"

    Assert-Rejects "security-audit-three-day-cleanup" {
        param($contract)
        $contract.retention.security_audit_uses_runtime_policy = $true
    } "security audit must not use runtime retention"

    Write-Output "P1_CONTRACT_SELF_TEST_OK cases=$($results.Count)"
}
finally {
    $resolvedTempRoot = [System.IO.Path]::GetFullPath($tempRoot)
    $resolvedSuiteRoot = [System.IO.Path]::GetFullPath($suiteRoot)
    if (
        (Test-Path -LiteralPath $resolvedSuiteRoot) -and
        $resolvedSuiteRoot.StartsWith($resolvedTempRoot, [System.StringComparison]::OrdinalIgnoreCase) -and
        ([System.IO.Path]::GetFileName($resolvedSuiteRoot).StartsWith("shuziren-p1-contract-", [System.StringComparison]::Ordinal))
    ) {
        Remove-Item -LiteralPath $resolvedSuiteRoot -Recurse -Force
    }
}
