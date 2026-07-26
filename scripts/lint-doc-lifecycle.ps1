[CmdletBinding()]
param(
    [string]$RepoRoot
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = Join-Path $PSScriptRoot ".."
}

$repoRootPath = (Resolve-Path -LiteralPath $RepoRoot).Path
$failures = [System.Collections.Generic.List[string]]::new()
$checks = 0
$linkCount = 0
$utf8Strict = New-Object System.Text.UTF8Encoding($false, $true)

function Add-Failure {
    param([string]$Message)
    $script:failures.Add($Message)
}

function Get-RepoPath {
    param([string]$RelativePath)
    return Join-Path $repoRootPath $RelativePath
}

function Get-RepoRelativePath {
    param([string]$FullName)
    return $FullName.Substring($repoRootPath.Length).TrimStart("\").Replace("\", "/")
}

function Read-RepoText {
    param([string]$RelativePath)
    $path = Get-RepoPath $RelativePath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        Add-Failure "Missing required file: $RelativePath"
        return ""
    }
    return Get-Content -Raw -LiteralPath $path
}

function Get-OutsideFenceLines {
    param([string]$Path)
    $inFence = $false
    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line.TrimStart().StartsWith('```')) {
            $inFence = -not $inFence
            continue
        }
        if (-not $inFence) {
            $line
        }
    }
}

$requiredEntryFiles = @(
    "README.md",
    "AGENTS.md",
    "docs/CODEX_CONTEXT.md",
    "docs/NEXT_ACTIONS.md",
    "docs/00_INDEX.md",
    "docs/05_DEVELOPMENT_PLAN.md",
    "docs/13_RISKS_AND_TODO.md",
    "docs/17_STANDARD_PRODUCT_DESIGN.md",
    "docs/DOCUMENT_GOVERNANCE.md",
    "docs/RESULT_ACCEPTANCE_STANDARD.md",
    "docs/06_API_CONTRACT.md",
    "docs/07_DATA_CONTRACT.md",
    "docs/product/contracts/README.md",
    "docs/archive/poc-v1/README.md"
)

foreach ($relativePath in $requiredEntryFiles) {
    $checks++
    [void](Read-RepoText $relativePath)
}

$allMarkdownFiles = @(
    Get-ChildItem -LiteralPath (Get-RepoPath "docs") -Recurse -File -Filter "*.md"
)

$governedLifecycleFiles = @(
    $allMarkdownFiles | Where-Object {
        $relativePath = Get-RepoRelativePath $_.FullName
        $relativePath -match '^docs/[^/]+\.md$' -or
        $relativePath -match '^docs/(integrations|product|acceptance|archive)/' -or
        $_.Name -eq "README.md"
    }
)

$allowedLifecyclePattern = 'Lifecycle:\s*`?(AUTHORITATIVE_CURRENT|AUTHORITATIVE_POLICY|TARGET_NOT_IMPLEMENTED|AS_BUILT_POC|CUSTOMER_SPECIFIC|ARCHIVED_POC_SNAPSHOT|ACCEPTANCE_EVIDENCE)`?'
$lifecycleRecords = @()
foreach ($file in $governedLifecycleFiles) {
    $relativePath = Get-RepoRelativePath $file.FullName
    $content = Get-Content -Raw -LiteralPath $file.FullName
    $checks++
    $match = [regex]::Match($content, $allowedLifecyclePattern)
    if (-not $match.Success) {
        Add-Failure "Missing or invalid lifecycle marker: $relativePath"
        continue
    }
    $lifecycleRecords += [pscustomobject]@{
        Path = $relativePath
        FullName = $file.FullName
        Lifecycle = $match.Groups[1].Value
        Content = $content
    }
}

$archiveFiles = @(
    $allMarkdownFiles | Where-Object {
        (Get-RepoRelativePath $_.FullName) -match '^docs/archive/'
    }
)
foreach ($file in $archiveFiles) {
    $relativePath = Get-RepoRelativePath $file.FullName
    $content = Get-Content -Raw -LiteralPath $file.FullName
    $checks++
    if ($content -notmatch 'ARCHIVED_POC_SNAPSHOT') {
        Add-Failure "Archive marker missing: $relativePath"
    }
}

$lineBudgets = @{
    "AGENTS.md" = 120
    "README.md" = 80
    "docs/CODEX_CONTEXT.md" = 100
    "docs/NEXT_ACTIONS.md" = 120
}
foreach ($entry in $lineBudgets.GetEnumerator()) {
    $path = Get-RepoPath $entry.Key
    if (Test-Path -LiteralPath $path -PathType Leaf) {
        $lineCount = (Get-Content -LiteralPath $path).Count
        $checks++
        if ($lineCount -gt $entry.Value) {
            Add-Failure "Line budget exceeded: $($entry.Key) has $lineCount lines; limit is $($entry.Value)"
        }
    }
}

$activeMarkdownFiles = @(
    (Get-Item -LiteralPath (Get-RepoPath "README.md")),
    (Get-Item -LiteralPath (Get-RepoPath "AGENTS.md"))
) + @(
    $allMarkdownFiles | Where-Object {
        (Get-RepoRelativePath $_.FullName) -notmatch '^docs/archive/'
    }
)

$phaseHeadings = @()
$taskHeadings = @()
foreach ($file in $activeMarkdownFiles) {
    $relativePath = Get-RepoRelativePath $file.FullName
    $lineNumber = 0
    foreach ($line in Get-OutsideFenceLines $file.FullName) {
        $lineNumber++
        if ($line -match '^#{1,6}\s*(Current Phase|当前阶段)\s*$') {
            $phaseHeadings += "${relativePath}:${lineNumber}"
        }
        if ($line -match '^#{1,6}\s*(Next Task|Next|下一任务|下一步|后续任务)\s*$') {
            $taskHeadings += "${relativePath}:${lineNumber}"
        }
    }
}

$checks++
if ($phaseHeadings.Count -ne 1 -or $phaseHeadings[0] -notlike "docs/NEXT_ACTIONS.md:*") {
    Add-Failure "Expected exactly one Current Phase heading, in docs/NEXT_ACTIONS.md; found: $($phaseHeadings -join ', ')"
}

$checks++
if ($taskHeadings.Count -ne 1 -or $taskHeadings[0] -notlike "docs/NEXT_ACTIONS.md:*") {
    Add-Failure "Expected exactly one Next Task heading, in docs/NEXT_ACTIONS.md; found: $($taskHeadings -join ', ')"
}

$rootStatusDeclarations = @()
foreach ($relativePath in @("README.md", "AGENTS.md")) {
    $lineNumber = 0
    foreach ($line in Get-OutsideFenceLines (Get-RepoPath $relativePath)) {
        $lineNumber++
        if ($line -match '^\s*>?\s*(?:[-*]\s*)?(Current Phase|当前阶段|Next Task|下一任务)\s*(?:[:：]|is\b|为)\s*\S') {
            $rootStatusDeclarations += "${relativePath}:${lineNumber}"
        }
    }
}
$checks++
if ($rootStatusDeclarations.Count -gt 0) {
    Add-Failure "Root entry documents must not declare dynamic phase or task status: $($rootStatusDeclarations -join ', ')"
}

$requiredRootReferences = [ordered]@{
    "README.md" = @("AGENTS.md", "docs/00_INDEX.md", "docs/CODEX_CONTEXT.md", "docs/NEXT_ACTIONS.md")
    "AGENTS.md" = @("docs/DOCUMENT_GOVERNANCE.md", "docs/00_INDEX.md", "docs/CODEX_CONTEXT.md", "docs/NEXT_ACTIONS.md")
}
foreach ($entry in $requiredRootReferences.GetEnumerator()) {
    $content = Read-RepoText $entry.Key
    foreach ($requiredReference in $entry.Value) {
        $checks++
        if ($content -notmatch [regex]::Escape($requiredReference)) {
            Add-Failure "Root entry is missing required routing reference: $($entry.Key) -> $requiredReference"
        }
    }
}

$rootEntryText = (Read-RepoText "README.md") + "`n" + (Read-RepoText "AGENTS.md")
$rootDriftPatterns = [ordered]@{
    "dynamic_status_heading" = '(?im)^#{1,6}\s*(当前状态|Current Status)\s*$'
    "suggested_prompt" = '建议提示词|(?i)recommended\s+prompt'
    "post_acceptance_phase_copy" = '通过后进入\s*(G|P|V)\d|(?i)after\s+acceptance.{0,30}(G|P|V)\d'
    "historical_milestone_list" = '(?m)^\s*[-*]\s*(已完成基线|代码状态|本地访问)\s*[:：]'
}
foreach ($entry in $rootDriftPatterns.GetEnumerator()) {
    $checks++
    if ($rootEntryText -match $entry.Value) {
        Add-Failure "Root entry contains drift-prone content: $($entry.Key)"
    }
}

$checks++
if ((Read-RepoText "README.md") -match '\]\(docs/(integrations/[^)]+|customers/(?!README\.md)[^)]+)\)') {
    Add-Failure "README must route integrations and customers through indexes, not deep-link scoped material"
}

$checks++
if ((Read-RepoText "README.md") -match '\]\([^)]*\.(zip|jar|bin|dat|plugin|pkg|7z|rar|exe|dll|msi|whl|deb|rpm)(?:[)#]|$)') {
    Add-Failure "README must not link vendor or executable binary artifacts"
}

$rootPathReferences = @()
foreach ($relativePath in @("README.md", "AGENTS.md")) {
    $content = Read-RepoText $relativePath
    foreach ($match in [regex]::Matches($content, '`((?:docs|scripts)/[^`]+|README\.md|AGENTS\.md)`')) {
        $target = $match.Groups[1].Value.TrimEnd("/")
        if ($target -match '<[^>]+>') {
            continue
        }
        $rootPathReferences += [pscustomobject]@{
            Source = $relativePath
            Target = $target
        }
    }
}
foreach ($reference in $rootPathReferences) {
    $checks++
    $candidate = Get-RepoPath $reference.Target
    if (-not (Test-Path -LiteralPath $candidate)) {
        Add-Failure "Broken backtick repository path: $($reference.Source) -> $($reference.Target)"
    }
}

$rootSecretPatterns = [ordered]@{
    "private_key" = '-----BEGIN [A-Z ]*PRIVATE KEY-----'
    "openai_key" = 'sk-(?:proj-)?[A-Za-z0-9_-]{20,}'
    "aws_access_key" = 'AKIA[0-9A-Z]{16}'
    "github_token" = 'gh[pousr]_[A-Za-z0-9]{20,}'
    "credential_url" = 'https?://[^/\s:@]+:[^@\s/]+@'
}
foreach ($entry in $rootSecretPatterns.GetEnumerator()) {
    $checks++
    if ($rootEntryText -match $entry.Value) {
        Add-Failure "High-confidence secret pattern found in a root entry: $($entry.Key)"
    }
}

foreach ($requiredStateMarker in @("AS_BUILT_POC", "TARGET_NOT_IMPLEMENTED")) {
    foreach ($relativePath in @("README.md", "AGENTS.md")) {
        $checks++
        if ((Read-RepoText $relativePath) -notmatch [regex]::Escape($requiredStateMarker)) {
            Add-Failure "Root entry does not preserve target/as-built distinction: $relativePath -> $requiredStateMarker"
        }
    }
}

$entryDirectiveFiles = @(
    "README.md",
    "AGENTS.md",
    "docs/CODEX_CONTEXT.md",
    "docs/NEXT_ACTIONS.md",
    "docs/00_INDEX.md"
)
$entryDirectiveText = ($entryDirectiveFiles | ForEach-Object { Read-RepoText $_ }) -join "`n"
$staleDirectivePatterns = @(
    'Archived POC Recommended Prompt',
    'Files Likely To Touch Next',
    'V0\.7 Acceptance Draft',
    'V1\.0 Acceptance Draft',
    'liuchenxiang\.uk',
    '默认\s*(进入|执行)\s*V0\.',
    '下一轮推荐\s*(goal|目标|提示词)',
    '(下一步|下一轮|下一阶段|接下来)\s*(是|为|进入|执行|开展|推荐|继续).{0,80}(客户现场|验收复演|POC|V0\.|V1\.0)',
    '(?i)(next\s+(task|step|phase)|recommended\s+prompt)\s*[:：-]?\s*.{0,80}(POC|V0\.|V1\.0|customer\s+site|demo\s+replay)',
    '客户现场验收复演'
)
foreach ($pattern in $staleDirectivePatterns) {
    $checks++
    if ($entryDirectiveText -match $pattern) {
        Add-Failure "Stale POC directive found in current entry documents: $pattern"
    }
}

$productTruthRecords = @(
    $lifecycleRecords | Where-Object {
        $_.Lifecycle -in @("AUTHORITATIVE_CURRENT", "AUTHORITATIVE_POLICY", "TARGET_NOT_IMPLEMENTED") -and
        $_.Path -ne "docs/00_INDEX.md" -and
        $_.Path -notmatch '^docs/customers/'
    }
)
$productTruthFiles = @(
    [pscustomobject]@{ Path = "README.md"; Content = (Read-RepoText "README.md") },
    [pscustomobject]@{ Path = "AGENTS.md"; Content = (Read-RepoText "AGENTS.md") }
) + @(
    $productTruthRecords | ForEach-Object {
        [pscustomobject]@{ Path = $_.Path; Content = $_.Content }
    }
)
$customerTermsPattern = '中天证券|zt-securities|finance-dashboard|党建|党员|党支部|汽车营销|小天|张书记|liuchenxiang\.uk'
foreach ($record in $productTruthFiles) {
    $checks++
    if ($record.Content -match $customerTermsPattern) {
        Add-Failure "Customer-specific term found in product truth: $($record.Path)"
    }
}

$asBuiltContractFiles = @(
    "docs/06_API_CONTRACT.md",
    "docs/07_DATA_CONTRACT.md"
)
foreach ($relativePath in $asBuiltContractFiles) {
    $content = Read-RepoText $relativePath
    $checks++
    if ($content -notmatch 'AS_BUILT_POC') {
        Add-Failure "Implemented POC contract lacks AS_BUILT_POC marker: $relativePath"
    }
}

$pluginDocument = Read-RepoText "docs/integrations/FINEREPORT_AI_PLUGIN_INTEGRATION.md"
$pluginHashMatch = [regex]::Match($pluginDocument, '(?i)SHA-256:\s*`?([A-F0-9]{64})')
$expectedPluginHash = if ($pluginHashMatch.Success) { $pluginHashMatch.Groups[1].Value.ToUpperInvariant() } else { "" }
$checks++
if ([string]::IsNullOrWhiteSpace($expectedPluginHash)) {
    Add-Failure "FineReport plugin evidence document has no SHA-256"
}

$binaryEvidenceCandidates = @(
    Get-ChildItem -LiteralPath $repoRootPath -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object {
            $_.FullName -notmatch '\\(\.git|node_modules|\.venv|logs)\\' -and
            (
                $_.Length -ge 1MB -or
                $_.Extension -eq ".zip" -or
                (
                    $_.Name -match '(?i)(fine.*plugin|plugin.*decision.*ai|com\.fr\.plugin\.decision\.ai)' -and
                    $_.Extension -in @(".zip", ".bin", ".dat", ".jar", ".plugin", ".pkg")
                )
            )
        }
)
$pluginEvidenceFiles = @()
foreach ($file in $binaryEvidenceCandidates) {
    $relativePath = Get-RepoRelativePath $file.FullName
    $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToUpperInvariant()
    $looksLikePlugin = $file.Name -match '(?i)(fine.*plugin|plugin.*decision.*ai|com\.fr\.plugin\.decision\.ai)' -and
        $file.Extension -in @(".zip", ".bin", ".dat", ".jar", ".plugin", ".pkg")
    if ($looksLikePlugin -or ($expectedPluginHash -and $hash -eq $expectedPluginHash)) {
        $pluginEvidenceFiles += $relativePath
        $checks++
        if ($relativePath -notmatch '^docs/fine-plugin-com\.fr\.plugin\.decision\.ai\.v11-[^/]+\.zip$') {
            Add-Failure "FineReport plugin archive exists outside the approved local evidence path: $relativePath"
        }

        $tracked = @(& git -C $repoRootPath ls-files -- $relativePath)
        if ($LASTEXITCODE -ne 0) {
            Add-Failure "Unable to inspect plugin tracking state: $relativePath"
        }
        elseif ($tracked.Count -gt 0) {
            Add-Failure "FineReport plugin archive is tracked by Git: $relativePath"
        }

        & git -C $repoRootPath check-ignore -q -- $relativePath
        if ($LASTEXITCODE -ne 0) {
            Add-Failure "FineReport plugin archive is not ignored by Git: $relativePath"
        }

        if ($relativePath -match '^docs/fine-plugin-' -and $expectedPluginHash -and $hash -ne $expectedPluginHash) {
            Add-Failure "FineReport plugin archive hash differs from documented evidence: $relativePath"
        }
    }
}

$trackedBinaryPaths = @(& git -C $repoRootPath ls-files -- "*.zip" "*.bin" "*.dat" "*.jar" "*.plugin" "*.pkg")
foreach ($relativePath in $trackedBinaryPaths) {
    $checks++
    if ($relativePath -match '(?i)(fine.*plugin|plugin.*decision.*ai|com\.fr\.plugin\.decision\.ai)') {
        Add-Failure "FineReport plugin-like archive is tracked by Git: $relativePath"
    }
}

$trackedVendorBinaryPaths = @(
    & git -C $repoRootPath ls-files |
        Where-Object {
            $_ -match '(?i)\.(zip|jar|bin|dat|plugin|pkg|7z|rar|exe|dll|msi|whl|deb|rpm)$'
        }
)
$checks++
if ($trackedVendorBinaryPaths.Count -gt 0) {
    Add-Failure "Tracked vendor or executable binary artifacts are forbidden: $($trackedVendorBinaryPaths -join ', ')"
}

$linkFiles = @(
    (Get-Item -LiteralPath (Get-RepoPath "README.md")),
    (Get-Item -LiteralPath (Get-RepoPath "AGENTS.md"))
) + @(
    $allMarkdownFiles | Where-Object {
        (Get-RepoRelativePath $_.FullName) -notmatch '^docs/archive/'
    }
)
foreach ($file in $linkFiles) {
    $relativeFile = Get-RepoRelativePath $file.FullName
    $lineNumber = 0
    $inFence = $false
    foreach ($line in Get-Content -LiteralPath $file.FullName) {
        $lineNumber++
        if ($line.TrimStart().StartsWith('```')) {
            $inFence = -not $inFence
            continue
        }
        if ($inFence) {
            continue
        }
        foreach ($match in [regex]::Matches($line, '\[[^\]]+\]\(([^)]+)\)')) {
            $target = $match.Groups[1].Value.Trim().Trim("<", ">")
            if ($target -match '^(https?://|mailto:|#|/)') {
                continue
            }
            $pathPart = ($target -split "#", 2)[0]
            if ([string]::IsNullOrWhiteSpace($pathPart)) {
                continue
            }
            $candidate = Join-Path $file.DirectoryName $pathPart
            $linkCount++
            if (-not (Test-Path -LiteralPath $candidate)) {
                Add-Failure "Broken Markdown link: ${relativeFile}:${lineNumber} -> $target"
            }
        }
    }
}

$candidateTextFiles = @(
    (Get-Item -LiteralPath (Get-RepoPath "README.md")),
    (Get-Item -LiteralPath (Get-RepoPath "AGENTS.md"))
) + $allMarkdownFiles + @(
    Get-ChildItem -LiteralPath (Get-RepoPath "scripts") -Recurse -File -Include "*.ps1"
)
foreach ($file in $candidateTextFiles) {
    $relativePath = Get-RepoRelativePath $file.FullName
    $checks++
    try {
        $bytes = [System.IO.File]::ReadAllBytes($file.FullName)
        [void]$utf8Strict.GetString($bytes)
    }
    catch {
        Add-Failure "File is not strict UTF-8: $relativePath"
        continue
    }

    $lineNumber = 0
    foreach ($line in Get-Content -LiteralPath $file.FullName) {
        $lineNumber++
        if ($line -match '[ \t]+$') {
            Add-Failure "Trailing whitespace: ${relativePath}:${lineNumber}"
        }
    }
}

$checks++
$workingDiffCheck = @(& git -C $repoRootPath diff --check 2>&1)
if ($LASTEXITCODE -ne 0) {
    Add-Failure "git diff --check failed: $($workingDiffCheck -join '; ')"
}

$checks++
$stagedDiffCheck = @(& git -C $repoRootPath diff --cached --check 2>&1)
if ($LASTEXITCODE -ne 0) {
    Add-Failure "git diff --cached --check failed: $($stagedDiffCheck -join '; ')"
}

if ($failures.Count -gt 0) {
    Write-Host "DOC_LIFECYCLE_FAILED failures=$($failures.Count) checks=$checks links=$linkCount" -ForegroundColor Red
    foreach ($failure in $failures) {
        Write-Host "- $failure" -ForegroundColor Red
    }
    exit 1
}

Write-Host "DOC_LIFECYCLE_OK checks=$checks links=$linkCount files=$($allMarkdownFiles.Count) plugin_files=$($pluginEvidenceFiles.Count)" -ForegroundColor Green
