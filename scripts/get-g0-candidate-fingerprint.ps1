[CmdletBinding()]
param(
    [string]$BaseCommit = "8e293af",
    [string]$OutputPath
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$sha256 = [System.Security.Cryptography.SHA256]::Create()

$resolvedBaseCommit = (& git -C $repoRoot rev-parse "$BaseCommit^{commit}").Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($resolvedBaseCommit)) {
    throw "Base commit is not available: $BaseCommit"
}

$candidatePaths = @(
    @(& git -C $repoRoot diff --name-only)
    @(& git -C $repoRoot diff --cached --name-only)
    @(& git -C $repoRoot ls-files --others --exclude-standard)
) |
    Where-Object {
        -not [string]::IsNullOrWhiteSpace($_) -and
        $_ -notmatch '^docs/acceptance/productization/G0/' -and
        $_ -notmatch '^logs/'
    } |
    Sort-Object -Unique

$fileRecords = @()
foreach ($relativePath in $candidatePaths) {
    $normalizedPath = $relativePath.Replace("\", "/")
    $fullPath = Join-Path $repoRoot $relativePath
    if (Test-Path -LiteralPath $fullPath -PathType Leaf) {
        $fileRecords += [pscustomobject]@{
            path = $normalizedPath
            state = "present"
            bytes = (Get-Item -LiteralPath $fullPath).Length
            sha256 = (Get-FileHash -LiteralPath $fullPath -Algorithm SHA256).Hash
        }
    }
    else {
        $fileRecords += [pscustomobject]@{
            path = $normalizedPath
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
    generated_at = (Get-Date).ToUniversalTime().ToString("o")
    base_commit = $resolvedBaseCommit
    scope = "modified, staged and untracked non-ignored files, excluding G0 acceptance summaries and logs"
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
    [System.IO.File]::WriteAllText($absoluteOutputPath, $json, $utf8NoBom)
    [pscustomobject]@{
        status = "G0_CANDIDATE_FINGERPRINT_OK"
        output = $absoluteOutputPath
        candidate_fingerprint_sha256 = $candidateFingerprint
        candidate_file_count = $fileRecords.Count
        output_sha256 = (Get-FileHash -LiteralPath $absoluteOutputPath -Algorithm SHA256).Hash
    } | ConvertTo-Json -Compress
}
else {
    $json
}
