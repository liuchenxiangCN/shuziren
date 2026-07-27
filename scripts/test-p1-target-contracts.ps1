[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$validator = Join-Path $PSScriptRoot "validate-p1-target-contracts.ps1"
$sourceContract = Join-Path $repoRoot "docs\product\contracts\p1-target-contract.json"
$tempRoot = [System.IO.Path]::GetTempPath()
$suiteRoot = Join-Path $tempRoot ("shuziren-p1-contract-" + [guid]::NewGuid().ToString("N"))
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$results = [System.Collections.Generic.List[object]]::new()

function Invoke-Validator {
    param(
        [string]$Path,
        [switch]$IncludeMarkdown
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
    $output = @(& powershell @arguments 2>&1)
    return [pscustomobject]@{
        ExitCode = $LASTEXITCODE
        Output = ($output -join "`n")
    }
}

function Read-SourceContract {
    return (Get-Content -Raw -LiteralPath $sourceContract | ConvertFrom-Json)
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

New-Item -ItemType Directory -Path $suiteRoot -Force | Out-Null

try {
    $baseline = Invoke-Validator -Path $sourceContract -IncludeMarkdown
    if ($baseline.ExitCode -ne 0) {
        throw "Baseline P1 contract failed: $($baseline.Output)"
    }
    $results.Add([pscustomobject]@{ Name = "baseline"; Result = "ACCEPTED" })

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

    Assert-Rejects "restore-skips-security-reconciliation" {
        param($contract)
        $transition = $contract.state_machines.restore_plan.transitions |
            Where-Object { $_.from -eq "EXECUTING" -and $_.to -eq "RECONCILING_SECURITY" }
        $transition.to = "COMPLETED"
        $transition.operation = "verified_cutover"
    } "legal transition set differs"

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

    Assert-Rejects "stale-fingerprint-relabels-error" {
        param($contract)
        $contract.resolution_policy.source_change_result = "PUBLISH_TARGET_CHANGED"
    } "stale resolution must have its own stable error"

    Assert-Rejects "publication-creates-release-targets" {
        param($contract)
        $contract.resolution_policy.publication_creates_release_targets = $true
    } "Publication must never create ReleaseTargets"

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

    Assert-Rejects "reset-token-not-single-use" {
        param($contract)
        $contract.iam_policy.reset_token.single_use = $false
    } "reset token must be single use"

    Assert-Rejects "password-reset-can-enable-user" {
        param($contract)
        $contract.invariants.password_reset_never_enables_user = $false
    } "password_reset_never_enables_user"

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

    Assert-Rejects "restore-old-password-active" {
        param($contract)
        $contract.storage.recovery_security_ledger.restore_user_rules.older_password_generation_authentication_allowed = $true
    } "older restored password verifier must never authenticate"

    Assert-Rejects "restore-disabled-user-enabled" {
        param($contract)
        $contract.storage.recovery_security_ledger.restore_user_rules.newer_disabled_state_wins = $false
    } "newer disabled-user state must win"

    Assert-Rejects "restore-predecessor-device-active" {
        param($contract)
        $contract.storage.recovery_security_ledger.restore_device_rules.older_or_mismatched_active_version_authentication_allowed = $true
    } "predecessor or mismatched device version must never authenticate"

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

    Assert-Rejects "duplicate-operation-id" {
        param($contract)
        $contract.api.operations[1].operation_id = $contract.api.operations[0].operation_id
    } "operation IDs must be unique"

    Assert-Rejects "duplicate-digital-human-instance" {
        param($contract)
        $contract.three_screen_fixture.screens[1].digital_human_instance_id = $contract.three_screen_fixture.screens[0].digital_human_instance_id
    } "DigitalHumanInstance IDs must be non-empty and unique"

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
