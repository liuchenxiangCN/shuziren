[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$suiteRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("shuziren-doc-lint-" + [guid]::NewGuid().ToString("N"))
$templateRoot = Join-Path $suiteRoot "baseline"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$results = [System.Collections.Generic.List[object]]::new()

function Copy-DirectoryContent {
    param(
        [string]$Source,
        [string]$Destination,
        [scriptblock]$Exclude
    )

    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    foreach ($item in Get-ChildItem -LiteralPath $Source -Recurse -Force) {
        $relativePath = $item.FullName.Substring($Source.Length).TrimStart("\")
        if (& $Exclude $relativePath $item) {
            continue
        }
        $target = Join-Path $Destination $relativePath
        if ($item.PSIsContainer) {
            New-Item -ItemType Directory -Path $target -Force | Out-Null
        }
        else {
            $parent = Split-Path -Parent $target
            New-Item -ItemType Directory -Path $parent -Force | Out-Null
            Copy-Item -LiteralPath $item.FullName -Destination $target -Force
        }
    }
}

function Add-Utf8Text {
    param(
        [string]$Path,
        [string]$Text
    )
    [System.IO.File]::AppendAllText($Path, $Text, $utf8NoBom)
}

function Write-Utf8Text {
    param(
        [string]$Path,
        [string]$Text
    )
    $parent = Split-Path -Parent $Path
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    [System.IO.File]::WriteAllText($Path, $Text, $utf8NoBom)
}

function Invoke-Lint {
    param([string]$FixtureRoot)
    $output = @(
        & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $FixtureRoot "scripts\lint-doc-lifecycle.ps1") -RepoRoot $FixtureRoot 2>&1
    )
    return [pscustomobject]@{
        ExitCode = $LASTEXITCODE
        Output = ($output -join "`n")
    }
}

function New-CaseFixture {
    param([string]$Name)
    $caseRoot = Join-Path $suiteRoot $Name
    & git clone --quiet $templateRoot $caseRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to create lint fixture: $Name"
    }
    & git -C $caseRoot config core.autocrlf false
    & git -C $caseRoot config core.safecrlf false
    return $caseRoot
}

function Assert-LintRejects {
    param(
        [string]$Name,
        [scriptblock]$Mutate
    )
    $caseRoot = New-CaseFixture $Name
    & $Mutate $caseRoot
    $result = Invoke-Lint $caseRoot
    $passed = $result.ExitCode -ne 0 -and $result.Output -match "DOC_LIFECYCLE_FAILED"
    $results.Add([pscustomobject]@{
        Case = $Name
        Expected = "Reject"
        Passed = $passed
        Output = $result.Output
    })
}

try {
    New-Item -ItemType Directory -Path $suiteRoot -Force | Out-Null
    New-Item -ItemType Directory -Path $templateRoot -Force | Out-Null

    foreach ($fileName in @("README.md", "AGENTS.md", ".gitignore")) {
        Copy-Item -LiteralPath (Join-Path $repoRoot $fileName) -Destination (Join-Path $templateRoot $fileName)
    }
    Copy-DirectoryContent (Join-Path $repoRoot "docs") (Join-Path $templateRoot "docs") {
        param($relativePath, $item)
        return -not $item.PSIsContainer -and $item.Name -match '(?i)^fine-plugin-.*\.zip$'
    }
    Copy-DirectoryContent (Join-Path $repoRoot "scripts") (Join-Path $templateRoot "scripts") {
        param($relativePath, $item)
        return $false
    }

    & git -C $templateRoot init --quiet
    & git -C $templateRoot config user.name "Doc Lint Self Test"
    & git -C $templateRoot config user.email "doc-lint@example.invalid"
    & git -C $templateRoot config core.autocrlf false
    & git -C $templateRoot config core.safecrlf false
    & git -C $templateRoot add .
    & git -C $templateRoot commit --quiet -m "fixture baseline"
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to commit lint fixture baseline"
    }

    $baselineResult = Invoke-Lint $templateRoot
    $results.Add([pscustomobject]@{
        Case = "valid_baseline"
        Expected = "Accept"
        Passed = $baselineResult.ExitCode -eq 0 -and $baselineResult.Output -match "DOC_LIFECYCLE_OK"
        Output = $baselineResult.Output
    })

    Assert-LintRejects "duplicate_task_heading" {
        param($root)
        Add-Utf8Text (Join-Path $root "docs\DEV_LOG.md") "`n## 下一步`n`n执行旧任务。`n"
    }

    Assert-LintRejects "root_dynamic_status" {
        param($root)
        Add-Utf8Text (Join-Path $root "README.md") "`n- 当前阶段: V1.0 客户验收`n"
    }

    Assert-LintRejects "root_readme_line_budget" {
        param($root)
        $extraLines = (1..15 | ForEach-Object { "extra governance line $_" }) -join "`n"
        Add-Utf8Text (Join-Path $root "README.md") "`n$extraLines`n"
    }

    Assert-LintRejects "root_suggested_prompt" {
        param($root)
        Add-Utf8Text (Join-Path $root "README.md") "`n建议提示词：继续开发下一阶段。`n"
    }

    Assert-LintRejects "root_integration_deep_link" {
        param($root)
        Add-Utf8Text (Join-Path $root "README.md") "`n[direct integration](docs/integrations/FVS_INTEGRATION.md)`n"
    }

    Assert-LintRejects "root_backtick_broken_path" {
        param($root)
        Add-Utf8Text (Join-Path $root "AGENTS.md") "`nRead ``docs/missing-root-guide.md``.`n"
    }

    Assert-LintRejects "root_secret_literal" {
        param($root)
        Add-Utf8Text (Join-Path $root "README.md") "`nExample secret: sk-proj-AAAAAAAAAAAAAAAAAAAAAAAA`n"
    }

    Assert-LintRejects "tracked_vendor_archive" {
        param($root)
        Write-Utf8Text (Join-Path $root "vendor-fixture.jar") "fixture"
        & git -C $root add vendor-fixture.jar
    }

    Assert-LintRejects "root_customer_id" {
        param($root)
        Add-Utf8Text (Join-Path $root "README.md") "`nDefault customer: zt-securities`n"
    }

    Assert-LintRejects "root_binary_link" {
        param($root)
        Write-Utf8Text (Join-Path $root "docs\vendor-fixture.zip") "fixture"
        Add-Utf8Text (Join-Path $root "README.md") "`n[vendor](docs/vendor-fixture.zip)`n"
    }

    Assert-LintRejects "root_missing_task_router" {
        param($root)
        $path = Join-Path $root "AGENTS.md"
        $text = (Get-Content -Raw -LiteralPath $path).Replace("docs/NEXT_ACTIONS.md", "docs/NEXT_REMOVED.md")
        Write-Utf8Text $path $text
    }

    Assert-LintRejects "stale_poc_directive" {
        param($root)
        Add-Utf8Text (Join-Path $root "docs\CODEX_CONTEXT.md") "`n下一步是客户现场验收复演。`n"
    }

    Assert-LintRejects "customer_pollution" {
        param($root)
        Add-Utf8Text (Join-Path $root "docs\17_STANDARD_PRODUCT_DESIGN.md") "`n产品默认使用汽车营销客户话术。`n"
    }

    Assert-LintRejects "missing_product_lifecycle" {
        param($root)
        Write-Utf8Text (Join-Path $root "docs\product\contracts\UNMARKED.md") "# Unmarked Target`n"
    }

    Assert-LintRejects "missing_archive_lifecycle" {
        param($root)
        Write-Utf8Text (Join-Path $root "docs\archive\poc-v1\UNMARKED.md") "# Unmarked Archive`n"
    }

    Assert-LintRejects "root_readme_broken_link" {
        param($root)
        Add-Utf8Text (Join-Path $root "README.md") "`n[broken](docs/does-not-exist.md)`n"
    }

    Assert-LintRejects "untracked_trailing_whitespace" {
        param($root)
        Write-Utf8Text (Join-Path $root "docs\product\contracts\TRAILING.md") "# Candidate `n`n- Lifecycle: ``TARGET_NOT_IMPLEMENTED```n"
    }

    Assert-LintRejects "staged_trailing_whitespace" {
        param($root)
        Add-Utf8Text (Join-Path $root "README.md") "`nStaged whitespace `n"
        & git -C $root add README.md
    }

    Assert-LintRejects "plugin_copy_or_rename" {
        param($root)
        $localPlugin = Get-ChildItem -LiteralPath (Join-Path $repoRoot "docs") -File -Filter "fine-plugin-*.zip" | Select-Object -First 1
        $target = Join-Path $root "docs\delivery\v1.0\vendor-evidence.dat"
        if ($localPlugin) {
            Copy-Item -LiteralPath $localPlugin.FullName -Destination $target
        }
        else {
            Write-Utf8Text (Join-Path $root "docs\delivery\v1.0\fine-plugin-renamed.dat") "fixture"
        }
    }

    Assert-LintRejects "plugin_not_ignored" {
        param($root)
        $localPlugin = Get-ChildItem -LiteralPath (Join-Path $repoRoot "docs") -File -Filter "fine-plugin-*.zip" | Select-Object -First 1
        $target = Join-Path $root "docs\fine-plugin-com.fr.plugin.decision.ai.v11-fixture.zip"
        if ($localPlugin) {
            Copy-Item -LiteralPath $localPlugin.FullName -Destination $target
        }
        else {
            Write-Utf8Text $target "fixture"
        }
        $ignorePath = Join-Path $root ".gitignore"
        $ignoreText = Get-Content -Raw -LiteralPath $ignorePath
        $ignoreText = [regex]::Replace($ignoreText, '(?m)^docs/fine-plugin-com\.fr\.plugin\.decision\.ai\.v11-\*\.zip\r?\n?', '')
        Write-Utf8Text $ignorePath $ignoreText
    }

    $failedCases = @($results | Where-Object { -not $_.Passed })
    if ($failedCases.Count -gt 0) {
        Write-Host "DOC_LIFECYCLE_SELF_TEST_FAILED cases=$($results.Count) failures=$($failedCases.Count)" -ForegroundColor Red
        foreach ($case in $failedCases) {
            Write-Host "- $($case.Case): $($case.Output)" -ForegroundColor Red
        }
        exit 1
    }

    Write-Host "DOC_LIFECYCLE_SELF_TEST_OK cases=$($results.Count)" -ForegroundColor Green
}
finally {
    if (Test-Path -LiteralPath $suiteRoot) {
        $resolvedSuiteRoot = (Resolve-Path -LiteralPath $suiteRoot).Path
        $tempRoot = [System.IO.Path]::GetTempPath().TrimEnd("\")
        if ($resolvedSuiteRoot.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase) -and
            (Split-Path -Leaf $resolvedSuiteRoot) -like "shuziren-doc-lint-*") {
            Remove-Item -LiteralPath $resolvedSuiteRoot -Recurse -Force
        }
        else {
            Write-Warning "Temporary fixture was not removed because its path failed the safety check: $resolvedSuiteRoot"
        }
    }
}
