[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Batch,
    [Parameter(Mandatory = $true)]
    [string]$BaseCommit,
    [string]$OutputPath
)

$ErrorActionPreference = "Stop"

if ($Batch -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]*$') {
    throw "Batch contains unsupported characters: $Batch"
}

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$sha256 = [System.Security.Cryptography.SHA256]::Create()

$resolvedBaseCommit = (& git -C $repoRoot rev-parse "$BaseCommit^{commit}").Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($resolvedBaseCommit)) {
    throw "Base commit is not available: $BaseCommit"
}

$acceptancePrefix = "docs/acceptance/productization/$Batch/"
$candidatePaths = @(
    @(& git -C $repoRoot diff --name-only $resolvedBaseCommit --)
    @(& git -C $repoRoot ls-files --others --exclude-standard)
) |
    ForEach-Object { $_.Replace("\", "/") } |
    Where-Object {
        -not [string]::IsNullOrWhiteSpace($_) -and
        -not $_.StartsWith($acceptancePrefix, [System.StringComparison]::Ordinal) -and
        -not $_.StartsWith("logs/", [System.StringComparison]::Ordinal)
    } |
    Sort-Object -Unique

$fileRecords = @()
foreach ($relativePath in $candidatePaths) {
    $fullPath = Join-Path $repoRoot $relativePath
    if (Test-Path -LiteralPath $fullPath -PathType Leaf) {
        $fileRecords += [pscustomobject]@{
            path = $relativePath
            state = "present"
            bytes = (Get-Item -LiteralPath $fullPath).Length
            sha256 = (Get-FileHash -LiteralPath $fullPath -Algorithm SHA256).Hash
        }
    }
    else {
        $fileRecords += [pscustomobject]@{
            path = $relativePath
            state = "deleted"
            bytes = 0
            sha256 = $null
        }
    }
}

$canonicalLines = @(
    $fileRecords | ForEach-Object {
        "$($_.path)|$($_.state)|$($_.bytes)|$($_.sha256)"
    }
)
$canonicalText = ($canonicalLines -join "`n") + "`n"
$canonicalBytes = $utf8NoBom.GetBytes($canonicalText)
$candidateFingerprint = ([System.BitConverter]::ToString($sha256.ComputeHash($canonicalBytes))).Replace("-", "")

$result = [ordered]@{
    schema_version = 1
    batch = $Batch
    generated_at = (Get-Date).ToUniversalTime().ToString("o")
    base_commit = $resolvedBaseCommit
    scope = "all committed and working-tree changes from the accepted base, excluding this batch acceptance package and logs"
    canonical_format = "path|state|bytes|sha256 sorted by path with LF terminators"
    candidate_fingerprint_sha256 = $candidateFingerprint
    candidate_file_count = $fileRecords.Count
    files = $fileRecords
}
$json = $result | ConvertTo-Json -Depth 6

if (-not [string]::IsNullOrWhiteSpace($OutputPath)) {
    $absoluteOutputPath = if ([System.IO.Path]::IsPathRooted($OutputPath)) {
        [System.IO.Path]::GetFullPath($OutputPath)
    }
    else {
        [System.IO.Path]::GetFullPath((Join-Path $repoRoot $OutputPath))
    }
    New-Item -ItemType Directory -Path (Split-Path -Parent $absoluteOutputPath) -Force | Out-Null
    [System.IO.File]::WriteAllText($absoluteOutputPath, $json + "`n", $utf8NoBom)
    [pscustomobject]@{
        status = "PRODUCTIZATION_CANDIDATE_FINGERPRINT_OK"
        batch = $Batch
        output = $absoluteOutputPath
        candidate_fingerprint_sha256 = $candidateFingerprint
        candidate_file_count = $fileRecords.Count
        output_sha256 = (Get-FileHash -LiteralPath $absoluteOutputPath -Algorithm SHA256).Hash
    } | ConvertTo-Json -Compress
}
else {
    $json
}
