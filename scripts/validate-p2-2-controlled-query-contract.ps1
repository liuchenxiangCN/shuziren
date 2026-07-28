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
    $ContractPath = Join-Path $repoRootPath "docs\product\contracts\p2-2-controlled-query-contract.json"
}
$contractFullPath = (Resolve-Path -LiteralPath $ContractPath).Path
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

function Test-ExactProperties {
    param([AllowNull()][object]$Value, [string[]]$Expected)
    if ($null -eq $Value) {
        return $false
    }
    return Test-ExactSequence @($Value.PSObject.Properties.Name) $Expected
}

try {
    $utf8 = New-Object System.Text.UTF8Encoding($false, $true)
    $contractText = [System.IO.File]::ReadAllText($contractFullPath, $utf8)
    $contract = $contractText | ConvertFrom-Json
}
catch {
    Write-Error "P2_2_CONTROLLED_QUERY_CONTRACT_INVALID_JSON $($_.Exception.Message)"
    exit 1
}

$expectedSha256 = "a25337a35ec285546443113db485a0d630ed67ab5d1478274fbb15ba3beaf33b"
$actualSha256 = (Get-FileHash -LiteralPath $contractFullPath -Algorithm SHA256).Hash.ToLowerInvariant()
Assert-Contract ($actualSha256 -ceq $expectedSha256) "contract SHA-256 differs from the frozen contract"
Assert-Contract (Test-ExactProperties $contract @(
    "contract_version", "lifecycle", "engines", "source", "dataset",
    "execution", "excel", "database", "storage", "deferred"
)) "top-level schema is not closed and ordered"
Assert-Contract ($contract.contract_version -ceq "p2.2-controlled-querying-v1") "contract version changed"
Assert-Contract ($contract.lifecycle -ceq "TARGET_NOT_IMPLEMENTED") "target lifecycle changed"
Assert-Contract (Test-ExactSequence $contract.engines @("EXCEL", "MYSQL", "ORACLE", "POSTGRESQL")) "engine set changed"
Assert-Contract (Test-ExactProperties $contract.source @(
    "site_owned", "version_immutable", "secret_write_only",
    "secret_encryption_purpose", "qualification_states", "product_certification"
)) "source schema changed"
Assert-Contract ($contract.source.site_owned -eq $true) "sources must remain site-owned"
Assert-Contract ($contract.source.version_immutable -eq $true) "source versions must remain immutable"
Assert-Contract ($contract.source.secret_write_only -eq $true) "source secrets must remain write-only"
Assert-Contract ($contract.source.secret_encryption_purpose -ceq "SECRET_ENVELOPE_ENCRYPTION") "secret purpose changed"
Assert-Contract (Test-ExactSequence $contract.source.qualification_states @("UNVERIFIED", "AVAILABLE", "FAILED")) "qualification states changed"
Assert-Contract ($contract.source.product_certification -ceq "UNVERIFIED") "product certification must remain unverified"
Assert-Contract (Test-ExactProperties $contract.dataset @(
    "version_immutable", "parameter_types", "row_limit", "timeout_ms",
    "runtime_sql_allowed", "relation_allowlist_required", "output_allowlist_required"
)) "dataset schema changed"
Assert-Contract ($contract.dataset.version_immutable -eq $true) "dataset versions must remain immutable"
Assert-Contract (Test-ExactSequence $contract.dataset.parameter_types @("string", "integer", "number", "boolean", "date")) "parameter types changed"
Assert-Contract (([int]$contract.dataset.row_limit.minimum -eq 1) -and ([int]$contract.dataset.row_limit.maximum -eq 500)) "row limits changed"
Assert-Contract (([int]$contract.dataset.timeout_ms.minimum -eq 100) -and ([int]$contract.dataset.timeout_ms.maximum -eq 120000)) "timeout limits changed"
Assert-Contract ($contract.dataset.runtime_sql_allowed -eq $false) "runtime SQL must remain forbidden"
Assert-Contract ($contract.dataset.relation_allowlist_required -eq $true) "relation allowlist must remain required"
Assert-Contract ($contract.dataset.output_allowlist_required -eq $true) "output allowlist must remain required"
Assert-Contract (Test-ExactProperties $contract.execution @(
    "permission_scope", "states", "worker_slots_minimum",
    "per_screen_inflight_maximum", "fallback_provider_ids",
    "idempotency_required_for_start_and_cancel"
)) "execution schema changed"
Assert-Contract ($contract.execution.permission_scope -ceq "screen_bound") "permission scope changed"
Assert-Contract (Test-ExactSequence $contract.execution.states @(
    "QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "TIMED_OUT",
    "CANCELLED", "REJECTED_BACKPRESSURE"
)) "execution states changed"
Assert-Contract ([int]$contract.execution.worker_slots_minimum -eq 3) "minimum worker slots changed"
Assert-Contract ([int]$contract.execution.per_screen_inflight_maximum -eq 2) "per-screen bound changed"
Assert-Contract (@($contract.execution.fallback_provider_ids).Count -eq 0) "fallback must remain empty"
Assert-Contract ($contract.execution.idempotency_required_for_start_and_cancel -eq $true) "start/cancel idempotency changed"
Assert-Contract (Test-ExactProperties $contract.excel @(
    "extension", "formula_allowed", "macro_allowed",
    "external_link_allowed", "arbitrary_path_allowed"
)) "Excel schema changed"
Assert-Contract ($contract.excel.extension -ceq ".xlsx") "Excel extension changed"
Assert-Contract ($contract.excel.formula_allowed -eq $false) "Excel formula must remain forbidden"
Assert-Contract ($contract.excel.macro_allowed -eq $false) "Excel macro must remain forbidden"
Assert-Contract ($contract.excel.external_link_allowed -eq $false) "Excel external link must remain forbidden"
Assert-Contract ($contract.excel.arbitrary_path_allowed -eq $false) "arbitrary path must remain forbidden"
Assert-Contract (Test-ExactProperties $contract.database @(
    "single_read_only_statement", "named_bind_parameters_only",
    "comments_allowed", "statement_chaining_allowed", "writes_allowed",
    "dynamic_execution_allowed"
)) "database schema changed"
Assert-Contract ($contract.database.single_read_only_statement -eq $true) "single read-only statement changed"
Assert-Contract ($contract.database.named_bind_parameters_only -eq $true) "named binds changed"
Assert-Contract ($contract.database.comments_allowed -eq $false) "comments must remain forbidden"
Assert-Contract ($contract.database.statement_chaining_allowed -eq $false) "statement chaining must remain forbidden"
Assert-Contract ($contract.database.writes_allowed -eq $false) "writes must remain forbidden"
Assert-Contract ($contract.database.dynamic_execution_allowed -eq $false) "dynamic execution must remain forbidden"
Assert-Contract (Test-ExactProperties $contract.storage @(
    "logical_schema", "migration", "tables",
    "release_snapshots_immutable", "restore_preserves_current_authority"
)) "storage schema changed"
Assert-Contract ($contract.storage.logical_schema -ceq "p1_control_plane_001") "logical schema changed"
Assert-Contract ($contract.storage.migration -ceq "005_controlled_querying") "migration changed"
Assert-Contract (Test-ExactSequence $contract.storage.tables @(
    "query_secret_records", "query_secret_versions", "query_sources",
    "query_source_versions", "query_datasets", "query_dataset_versions",
    "config_draft_query_assignments", "query_validation_records",
    "release_target_query_snapshots", "query_executions"
)) "storage table set changed"
Assert-Contract ($contract.storage.release_snapshots_immutable -eq $true) "snapshot immutability changed"
Assert-Contract ($contract.storage.restore_preserves_current_authority -eq $true) "restore authority changed"
Assert-Contract (Test-ExactSequence $contract.deferred @(
    "P2.3_INTEGRATED_RESILIENCE_CERTIFICATION",
    "P2.4_FINEREPORT_PLUGIN",
    "P3_RENDERER_AVATAR_PACKAGE"
)) "deferred scope changed"

if ($failures.Count -gt 0) {
    Write-Output "P2_2_CONTROLLED_QUERY_CONTRACT_FAILED checks=$checks failures=$($failures.Count)"
    foreach ($failure in $failures) {
        Write-Output " - $failure"
    }
    exit 1
}
Write-Output "P2_2_CONTROLLED_QUERY_CONTRACT_OK checks=$checks engines=4 tables=10"
