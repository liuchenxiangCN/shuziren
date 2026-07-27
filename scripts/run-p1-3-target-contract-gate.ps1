[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$EvidenceRoot
)

$ErrorActionPreference = "Stop"
$repoRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$resolvedEvidenceRoot = [System.IO.Path]::GetFullPath($EvidenceRoot)
$repoPrefix = $repoRoot.TrimEnd("\") + "\"
if (-not $resolvedEvidenceRoot.StartsWith($repoPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "EvidenceRoot must stay inside the repository."
}

$resultRoot = Join-Path $resolvedEvidenceRoot "test-results"
New-Item -ItemType Directory -Path $resultRoot -Force | Out-Null
$outputPath = Join-Path $resultRoot "target-contract-self-test.txt"
$resultPath = Join-Path $resultRoot "target-contract-self-test-result.json"
$started = [DateTimeOffset]::UtcNow
$output = @(
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
        (Join-Path $repoRoot "scripts\test-p1-target-contracts.ps1") 2>&1
)
$exitCode = $LASTEXITCODE
$finished = [DateTimeOffset]::UtcNow
[System.IO.File]::WriteAllLines(
    $outputPath,
    [string[]]$output,
    (New-Object System.Text.UTF8Encoding($false))
)
$result = [ordered]@{
    gate = "p1_target_contract_self_test"
    status = $(if ($exitCode -eq 0) { "PASS" } else { "FAIL" })
    exit_code = $exitCode
    started_at = $started.ToString("O")
    finished_at = $finished.ToString("O")
    elapsed_seconds = [Math]::Round(($finished - $started).TotalSeconds, 3)
    output_path = $outputPath.Substring($repoPrefix.Length).Replace("\", "/")
}
[System.IO.File]::WriteAllText(
    $resultPath,
    (($result | ConvertTo-Json -Depth 4) + "`n"),
    (New-Object System.Text.UTF8Encoding($false))
)
exit $exitCode
