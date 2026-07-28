[CmdletBinding()]
param([string]$RepoRoot)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = Join-Path $PSScriptRoot ".."
}
$repoRootPath = (Resolve-Path -LiteralPath $RepoRoot).Path
$validator = Join-Path $repoRootPath "scripts\validate-p2-2-controlled-query-contract.ps1"
$source = Join-Path $repoRootPath "docs\product\contracts\p2-2-controlled-query-contract.json"
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("shuziren-p22-contract-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $temporaryRoot | Out-Null
$mutations = [ordered]@{
    lifecycle = { param($value) $value.lifecycle = "AS_BUILT_POC" }
    engine = { param($value) $value.engines[0] = "CSV" }
    runtime_sql = { param($value) $value.dataset.runtime_sql_allowed = $true }
    write = { param($value) $value.database.writes_allowed = $true }
    fallback = { param($value) $value.execution.fallback_provider_ids = @("broader_source") }
    table = { param($value) $value.storage.tables = @($value.storage.tables | Select-Object -Skip 1) }
}
try {
    & $validator -RepoRoot $repoRootPath
    if (-not $?) {
        throw "Frozen P2.2 contract did not pass its validator."
    }
    $passed = 0
    foreach ($entry in $mutations.GetEnumerator()) {
        $value = Get-Content -Raw -LiteralPath $source -Encoding utf8 | ConvertFrom-Json
        & $entry.Value $value
        $path = Join-Path $temporaryRoot ($entry.Key + ".json")
        $value | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $path -Encoding utf8
        & $validator -RepoRoot $repoRootPath -ContractPath $path *> $null
        if ($?) {
            throw "Mutation '$($entry.Key)' was not rejected."
        }
        $passed++
    }
    Write-Output "P2_2_CONTROLLED_QUERY_CONTRACT_SELF_TEST_OK mutations=$passed"
}
finally {
    if (Test-Path -LiteralPath $temporaryRoot) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
}
