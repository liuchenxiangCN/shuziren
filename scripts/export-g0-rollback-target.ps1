[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Destination,

    [string]$BaseCommit = "8e293af"
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$destinationPath = [System.IO.Path]::GetFullPath($Destination)
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$repoPrefix = $repoRoot.TrimEnd("\") + "\"
$allowedWorkspaceEvidenceRoot = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "logs\productization")).TrimEnd("\") + "\"

if ($destinationPath -eq $repoRoot) {
    throw "Destination must not be the repository root."
}

if ($destinationPath.StartsWith($repoPrefix, [System.StringComparison]::OrdinalIgnoreCase) -and
    -not $destinationPath.StartsWith($allowedWorkspaceEvidenceRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "A destination inside the repository is allowed only under logs\productization."
}

if ($destinationPath.Split([System.IO.Path]::DirectorySeparatorChar) -contains ".git") {
    throw "Destination must not be inside a .git directory."
}

$existingAncestor = $destinationPath
while (-not (Test-Path -LiteralPath $existingAncestor)) {
    $parent = Split-Path -Parent $existingAncestor
    if ([string]::IsNullOrWhiteSpace($parent) -or $parent -eq $existingAncestor) {
        break
    }
    $existingAncestor = $parent
}
while (Test-Path -LiteralPath $existingAncestor) {
    $ancestorItem = Get-Item -LiteralPath $existingAncestor -Force
    if (($ancestorItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Destination ancestry contains a junction or symbolic link: $existingAncestor"
    }
    $parent = Split-Path -Parent $existingAncestor
    if ([string]::IsNullOrWhiteSpace($parent) -or $parent -eq $existingAncestor) {
        break
    }
    $existingAncestor = $parent
}

if (Test-Path -LiteralPath $destinationPath) {
    $existingItems = @(Get-ChildItem -LiteralPath $destinationPath -Force)
    if ($existingItems.Count -gt 0) {
        throw "Destination must be absent or empty: $destinationPath"
    }
}
else {
    New-Item -ItemType Directory -Path $destinationPath -Force | Out-Null
}

$resolvedBaseCommit = (& git -C $repoRoot rev-parse "$BaseCommit^{commit}").Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($resolvedBaseCommit)) {
    throw "Base commit is not available: $BaseCommit"
}

$archivePath = Join-Path (Split-Path -Parent $destinationPath) ("g0-rollback-base-" + [guid]::NewGuid().ToString("N") + ".zip")

try {
    & git -C $repoRoot archive --format=zip --output=$archivePath $resolvedBaseCommit
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $archivePath -PathType Leaf)) {
        throw "Unable to export base commit: $resolvedBaseCommit"
    }
    Expand-Archive -LiteralPath $archivePath -DestinationPath $destinationPath
}
finally {
    if (Test-Path -LiteralPath $archivePath -PathType Leaf) {
        Remove-Item -LiteralPath $archivePath -Force
    }
}

$snapshotMap = [ordered]@{
    "docs/archive/poc-v1/root-snapshots/CODEX_CONTEXT_FULL_HISTORY.md" = "docs/CODEX_CONTEXT.md"
    "docs/archive/poc-v1/root-snapshots/NEXT_ACTIONS_FULL_HISTORY.md" = "docs/NEXT_ACTIONS.md"
    "docs/archive/poc-v1/root-snapshots/DEV_LOG_FULL_HISTORY.md" = "docs/DEV_LOG.md"
    "docs/archive/poc-v1/root-snapshots/DEVELOPMENT_PLAN_FULL_HISTORY.md" = "docs/05_DEVELOPMENT_PLAN.md"
    "docs/archive/poc-v1/root-snapshots/RISKS_AND_TODO_FULL_HISTORY.md" = "docs/13_RISKS_AND_TODO.md"
    "docs/archive/poc-v1/root-snapshots/CHANGELOG_FULL_HISTORY.md" = "docs/CHANGELOG.md"
}

foreach ($entry in $snapshotMap.GetEnumerator()) {
    $source = Join-Path $repoRoot $entry.Key
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        throw "Missing archived P0 source: $($entry.Key)"
    }

    $lines = @(Get-Content -LiteralPath $source)
    $bannerIndex = -1
    for ($index = 0; $index -lt $lines.Count; $index++) {
        if ($lines[$index] -match "ARCHIVED_POC_SNAPSHOT") {
            $bannerIndex = $index
            break
        }
    }
    if ($bannerIndex -lt 0 -or $bannerIndex + 1 -ge $lines.Count -or $lines[$bannerIndex + 1] -ne "") {
        throw "Unexpected archive banner in: $($entry.Key)"
    }

    $target = Join-Path $destinationPath $entry.Value
    New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
    $restoredLines = @()
    if ($bannerIndex -gt 0) {
        $restoredLines += $lines[0..($bannerIndex - 1)]
    }
    if ($bannerIndex + 2 -lt $lines.Count) {
        $restoredLines += $lines[($bannerIndex + 2)..($lines.Count - 1)]
    }
    $restoredText = ($restoredLines -join [Environment]::NewLine) + [Environment]::NewLine
    [System.IO.File]::WriteAllText($target, $restoredText, $utf8NoBom)
}

$p0OverlayFiles = @(
    ".gitignore",
    "docs/01_PROJECT_BRIEF.md",
    "docs/02_PRODUCT_BLUEPRINT.md",
    "docs/17_STANDARD_PRODUCT_DESIGN.md",
    "docs/decisions/ADR-0001-project-scope.md",
    "docs/decisions/ADR-0023-generic-configurable-digital-human-positioning.md",
    "docs/decisions/ADR-0026-finereport-fvs-productization.md",
    "docs/integrations/FINEREPORT_AI_PLUGIN_INTEGRATION.md"
)

foreach ($relativePath in $p0OverlayFiles) {
    $source = Join-Path $repoRoot $relativePath
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        throw "Missing P0 overlay source: $relativePath"
    }
    $target = Join-Path $destinationPath $relativePath
    New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
    Copy-Item -LiteralPath $source -Destination $target -Force
}

$p0EntryTemplates = [ordered]@{
    "docs/acceptance/productization/G0/rollback/P0_AGENTS.txt" = "AGENTS.md"
    "docs/acceptance/productization/G0/rollback/P0_README.txt" = "README.md"
    "docs/acceptance/productization/G0/rollback/P0_DOCS_INDEX.txt" = "docs/00_INDEX.md"
}
foreach ($entry in $p0EntryTemplates.GetEnumerator()) {
    $source = Join-Path $repoRoot $entry.Key
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        throw "Missing P0 entry-template source: $($entry.Key)"
    }
    $target = Join-Path $destinationPath $entry.Value
    New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
    Copy-Item -LiteralPath $source -Destination $target -Force
}

$g0OnlyFiles = @(
    "docs/DOCUMENT_GOVERNANCE.md",
    "docs/RESULT_ACCEPTANCE_STANDARD.md",
    "docs/decisions/ADR-0027-result-driven-development-and-document-lifecycle.md",
    "docs/acceptance/productization/G0/ACCEPTANCE_CARD.md"
)
$unexpectedG0Files = @(
    $g0OnlyFiles | Where-Object {
        Test-Path -LiteralPath (Join-Path $destinationPath $_)
    }
)
if ($unexpectedG0Files.Count -gt 0) {
    throw "G0-only files unexpectedly exist in recovery target: $($unexpectedG0Files -join ', ')"
}

$requiredP0Anchors = [ordered]@{
    "docs/17_STANDARD_PRODUCT_DESIGN.md" = "FineReport"
    "docs/decisions/ADR-0026-finereport-fvs-productization.md" = "Accepted"
    "docs/integrations/FINEREPORT_AI_PLUGIN_INTEGRATION.md" = "D1F1F6BFA70C44652231293318ED4124B97B8A227209C0A35156F7EB1E4D68AB"
    "docs/CODEX_CONTEXT.md" = "Productization P1"
    "AGENTS.md" = "FineReport / FVS multi-screen"
    "README.md" = "FineReport / FVS 多大屏数字人平台"
    "docs/00_INDEX.md" = "P0 Productization"
}

$anchorResults = @()
foreach ($entry in $requiredP0Anchors.GetEnumerator()) {
    $path = Join-Path $destinationPath $entry.Key
    $present = Test-Path -LiteralPath $path -PathType Leaf
    $containsAnchor = $present -and (Get-Content -Raw -LiteralPath $path) -match [regex]::Escape($entry.Value)
    $anchorResults += [pscustomobject]@{
        path = $entry.Key
        anchor = $entry.Value
        passed = [bool]$containsAnchor
    }
}
if (@($anchorResults | Where-Object { -not $_.passed }).Count -gt 0) {
    throw "P0 anchor verification failed."
}

$evidenceFiles = @($snapshotMap.Values) + $p0OverlayFiles + @($p0EntryTemplates.Values)
$fileHashes = @()
foreach ($relativePath in ($evidenceFiles | Sort-Object -Unique)) {
    $path = Join-Path $destinationPath $relativePath
    $fileHashes += [pscustomobject]@{
        path = $relativePath.Replace("\", "/")
        sha256 = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
        bytes = (Get-Item -LiteralPath $path).Length
    }
}

$proofDirectory = Join-Path $destinationPath "_recovery"
New-Item -ItemType Directory -Path $proofDirectory -Force | Out-Null
$proofPath = Join-Path $proofDirectory "G0_ROLLBACK_PROOF.json"
$proof = [ordered]@{
    schema_version = 1
    generated_at = (Get-Date).ToUniversalTime().ToString("o")
    purpose = "G0 documentation rollback target that preserves the P0 product-definition artifacts"
    base_commit = $resolvedBaseCommit
    runtime_source = "git archive of base_commit"
    restored_root_documents = @($snapshotMap.Values)
    p0_overlay_files = $p0OverlayFiles
    p0_entry_files = @($p0EntryTemplates.Values)
    g0_only_files_absent = $g0OnlyFiles
    p0_anchor_checks = $anchorResults
    evidence_files = $fileHashes
    verification = "PASS"
}
[System.IO.File]::WriteAllText($proofPath, ($proof | ConvertTo-Json -Depth 8), $utf8NoBom)

$proofHash = (Get-FileHash -LiteralPath $proofPath -Algorithm SHA256).Hash
[pscustomobject]@{
    status = "G0_ROLLBACK_TARGET_OK"
    base_commit = $resolvedBaseCommit
    destination = $destinationPath
    proof = $proofPath
    proof_sha256 = $proofHash
    restored_root_documents = $snapshotMap.Count
    preserved_p0_artifacts = $p0OverlayFiles.Count + $p0EntryTemplates.Count
} | ConvertTo-Json -Compress
