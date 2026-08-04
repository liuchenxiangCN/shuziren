[CmdletBinding()]
param([string]$RepoRoot)

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

function Read-RepoFile {
    param([string]$RelativePath)
    $path = Join-Path $repoRootPath $RelativePath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        return $null
    }
    return [System.IO.File]::ReadAllText(
        $path,
        (New-Object System.Text.UTF8Encoding($false, $true))
    )
}

function Assert-Contains {
    param(
        [AllowNull()][string]$Text,
        [string]$Needle,
        [string]$Message
    )
    Assert-Contract ($null -ne $Text -and $Text.Contains($Needle)) $Message
}

$card = Read-RepoFile "docs/acceptance/productization/P3/ACCEPTANCE_CARD.md"
$p3 = Read-RepoFile "apps/api/app/control_plane/p3.py"
$router = Read-RepoFile "apps/api/app/control_plane/router.py"
$service = Read-RepoFile "apps/api/app/control_plane/service.py"
$store = Read-RepoFile "apps/api/app/control_plane/store.py"
$recovery = Read-RepoFile "apps/api/app/control_plane/recovery.py"
$p13 = Read-RepoFile "apps/api/app/control_plane/p1_3.py"
$frontendApi = Read-RepoFile "apps/web/src/controlPlaneApi.ts"
$frontend = Read-RepoFile "apps/web/src/ControlPlaneApp.vue"
$nextActions = Read-RepoFile "docs/NEXT_ACTIONS.md"

Assert-Contract ($null -ne $card) "P3 acceptance card is missing"
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
    Assert-Contains $card $section "acceptance card section '$section' is missing"
}
Assert-Contains $card "ACTIVE_RESULT_CARD_FROZEN" "P3 acceptance card is not frozen"
Assert-Contains $card "TEST_ONLY" "P3 acceptance card lost the test-only boundary"
Assert-Contains $card "a124f63" "P3 acceptance card lost the accepted P2.3 runtime rollback target"
Assert-Contains $card "6488044" "P3 acceptance card lost the accepted P2.3 record commit"

Assert-Contract ($null -ne $p3) "p3.py is missing"
foreach ($constant in @(
    'RENDERER_REGISTRY_VERSION = "p3_renderer_registry_001"',
    'AVATAR_SCHEMA_VERSION = "p3_avatar_package_v1"',
    'TEST_RENDERER_TYPE = "test_card"',
    'TEST_RENDERER_VERSION = "1.0.0"',
    'TEST_RENDERER_RANGE = "^1.0.0"',
    'TEST_RESOURCE_MEDIA_TYPE = "application/vnd.shuziren.test-avatar+json"',
    'MAX_RESOURCE_FILES = 16',
    'MAX_PACKAGE_BYTES = 2 * 1024 * 1024'
)) {
    Assert-Contains $p3 $constant "P3 renderer constant '$constant' changed"
}
Assert-Contains $p3 '"test_only": True' "renderer registry must remain test-only"
Assert-Contains $p3 '"production_eligible": False' "renderer registry must remain production-ineligible"
Assert-Contains $p3 'entry_asset != "avatar.json"' "P3 must accept only the declarative avatar.json entry"
Assert-Contains $p3 '"TEST_ONLY"' "P3 test license enforcement is missing"
Assert-Contains $p3 '"DEVELOPMENT_PREVIEW"' "P3 preview-only usage scope is missing"
Assert-Contains $p3 'AVATAR_PREFETCH_REQUIRED' "publish-before-prefetch denial is missing"
Assert-Contains $p3 'CONTENT_HASH_MISMATCH' "content-hash failure result is missing"
Assert-Contains $p3 'RESOURCE_VERSION_CONFLICT' "optimistic concurrency denial is missing"
Assert-Contract (
    $null -ne $p3 -and -not [regex]::IsMatch(
        $p3,
        '(?i)(eval\s*\(|exec\s*\(|subprocess|importlib|webassembly|dynamic\s+import)'
    )
) "P3 implementation contains a dynamic execution surface"

$suffixMatch = [regex]::Match(
    [string]$p3,
    '(?s)blocked_suffixes\s*=\s*\((.*?)\)',
    [System.Text.RegularExpressions.RegexOptions]::CultureInvariant
)
$actualSuffixes = @()
if ($suffixMatch.Success) {
    $actualSuffixes = @(
        [regex]::Matches($suffixMatch.Groups[1].Value, '"([^"]+)"') |
            ForEach-Object { $_.Groups[1].Value }
    )
}
$expectedSuffixes = @(
    ".js", ".mjs", ".cjs", ".wasm", ".html", ".htm", ".css",
    ".svg", ".zip", ".tar", ".gz", ".exe", ".dll", ".ps1", ".sh"
)
Assert-Contract (
    ($actualSuffixes.Count -eq $expectedSuffixes.Count) -and
    (-not (Compare-Object $actualSuffixes $expectedSuffixes -SyncWindow 0))
) "blocked executable resource suffix set changed"

Assert-Contains $store 'MIGRATION_006_VERSION = "006_renderer_avatar_packages"' "migration 006 is missing"
Assert-Contains $store "MIGRATION_VERSION = MIGRATION_006_VERSION" "migration head is not 006"
foreach ($table in @(
    "avatar_packages",
    "avatar_package_versions",
    "avatar_package_resources",
    "screen_avatar_bindings",
    "avatar_prefetch_records",
    "avatar_switch_records"
)) {
    Assert-Contains $store "CREATE TABLE $table" "P3 table $table is missing"
    Assert-Contains $p13 ('"' + $table + '"') "retention protection omitted P3 table $table"
}
foreach ($trigger in @(
    "avatar_packages_no_update",
    "avatar_package_versions_no_update",
    "avatar_package_resources_no_update",
    "avatar_prefetch_records_no_update",
    "avatar_switch_records_no_update"
)) {
    Assert-Contains $store $trigger "immutability trigger $trigger is missing"
}
Assert-Contains $store "validate_p3_schema_integrity" "P3 schema integrity validation is missing"
Assert-Contains $recovery "BackupManager._validate_p3_avatar_data(connection)" "backup verification omits P3 data"
Assert-Contains $recovery "ControlPlaneStore.validate_p3_schema_integrity(connection)" "backup omits P3 schema verification"
Assert-Contains $recovery "dir=live_parent" "restore staging is not guaranteed to share the live database volume"

foreach ($route in @(
    'f"{CONTROL_PREFIX}/renderer-providers"',
    'f"{CONTROL_PREFIX}/avatar-packages"',
    'f"{CONTROL_PREFIX}/avatar-package-versions/{{package_version_id}}/preview"',
    'f"{CONTROL_PREFIX}/screen-instances/{{screen_id}}/avatar-binding"',
    'f"{CONTROL_PREFIX}/screen-instances/{{screen_id}}/avatar-publications"',
    'f"{CONTROL_PREFIX}/screen-instances/{{screen_id}}/avatar-rollbacks"',
    'f"{DEVICE_PREFIX}/avatar/current"'
)) {
    Assert-Contains $router $route "P3 API route '$route' is missing"
}
Assert-Contains $router 'avatar-package-versions/' "P3 prefetch route is missing"
Assert-Contract (
    $null -ne $router -and -not [regex]::IsMatch(
        $router,
        'DEVICE_PREFIX\}[^"]*(avatar-publications|avatar-rollbacks|avatar-package-versions)'
    )
) "device API exposes avatar mutation or prefetch routes"

Assert-Contains $service "from app.control_plane.p3 import P3ControlPlane" "P3ControlPlane is not imported"
Assert-Contains $service "self.p3 = P3ControlPlane(self)" "P3ControlPlane is not wired"
foreach ($operation in @(
    "createAvatarPackageVersion",
    "prefetchAvatarPackage",
    "publishAvatarToScreen",
    "rollbackAvatarOnScreen"
)) {
    Assert-Contains $service ('"' + $operation + '": (') "P3 idempotency route $operation is missing"
}

foreach ($functionName in @(
    "listRendererProviders",
    "listAvatarPackages",
    "createAvatarPackageVersion",
    "getAvatarPackagePreview",
    "prefetchAvatarPackage",
    "getScreenAvatarBinding",
    "publishAvatarToScreen",
    "rollbackAvatarOnScreen"
)) {
    Assert-Contains $frontendApi "export function $functionName(" "frontend API function $functionName is missing"
}
Assert-Contains $frontend "P3 test-only boundary" "frontend test-only boundary is missing"
Assert-Contains $frontend "模拟损坏哈希" "frontend hash-failure drill is missing"
Assert-Contains $frontend "原子切换到目标屏" "frontend atomic switch action is missing"
Assert-Contains $frontend "回退上一版本" "frontend rollback action is missing"
Assert-Contract (
    $null -ne $frontend -and
    -not $frontend.Contains("v-html") -and
    -not [regex]::IsMatch($frontend, '(?i)(eval\s*\(|new\s+Function\s*\(|WebAssembly)')
) "frontend contains a dynamic rendering or execution surface"

Assert-Contains $nextActions "Productization P3 Active" "NEXT_ACTIONS does not keep P3 active"
Assert-Contains $nextActions "P2.4 Deferred And Blocked By External Gate" "P2.4 deferment was lost"

if ($failures.Count -gt 0) {
    Write-Output "P3_RENDERER_CONTRACT_FAILED checks=$checks failures=$($failures.Count)"
    foreach ($failure in $failures) {
        Write-Output " - $failure"
    }
    exit 1
}
Write-Output "P3_RENDERER_CONTRACT_OK checks=$checks"
