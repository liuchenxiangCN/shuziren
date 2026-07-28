[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Batch,
    [Parameter(Mandatory = $true)]
    [string]$BaseCommit,
    [Parameter(Mandatory = $true)]
    [string]$CandidateCommit,
    [string]$OutputPath
)

$ErrorActionPreference = "Stop"

if ($Batch -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]*$') {
    throw "Batch contains unsupported characters: $Batch"
}

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$sha256 = [System.Security.Cryptography.SHA256]::Create()

function Resolve-Commit {
    param([string]$Revision, [string]$Label)
    $resolved = (& git -C $repoRoot rev-parse "$Revision^{commit}").Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($resolved)) {
        throw "$Label commit is not available: $Revision"
    }
    return $resolved
}

$resolvedBaseCommit = Resolve-Commit -Revision $BaseCommit -Label "Base"
$resolvedCandidateCommit = Resolve-Commit -Revision $CandidateCommit -Label "Candidate"
$candidateTree = (& git -C $repoRoot show -s --format=%T $resolvedCandidateCommit).Trim()
if ($LASTEXITCODE -ne 0 -or $candidateTree -notmatch '^[0-9a-f]{40}$') {
    throw "Candidate tree could not be resolved."
}

$parentCommit = (& git -C $repoRoot show -s --format=%P $resolvedCandidateCommit).Trim()
if ($LASTEXITCODE -ne 0) {
    throw "Candidate parent could not be resolved."
}

$acceptancePrefix = "docs/acceptance/productization/$Batch/"
$changedPaths = @(
    & git -C $repoRoot diff --name-only $resolvedBaseCommit $resolvedCandidateCommit --
) |
    ForEach-Object { $_.Replace("\", "/") } |
    Where-Object {
        -not [string]::IsNullOrWhiteSpace($_) -and
        -not $_.StartsWith($acceptancePrefix, [System.StringComparison]::Ordinal) -and
        -not $_.StartsWith("logs/", [System.StringComparison]::Ordinal)
    } |
    Sort-Object -Unique
if ($LASTEXITCODE -ne 0) {
    throw "Candidate path diff failed."
}

Add-Type -AssemblyName System.IO.Compression.FileSystem
$temporaryArchive = Join-Path ([System.IO.Path]::GetTempPath()) (
    "shuziren-candidate-{0}.zip" -f [System.Guid]::NewGuid().ToString("N")
)
try {
    & git -C $repoRoot archive --format=zip --output=$temporaryArchive $resolvedCandidateCommit
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $temporaryArchive -PathType Leaf)) {
        throw "Candidate archive could not be created."
    }
    $archive = [System.IO.Compression.ZipFile]::OpenRead($temporaryArchive)
    try {
        $entries = @{}
        foreach ($entry in $archive.Entries) {
            if (-not $entry.FullName.EndsWith("/")) {
                $entries[$entry.FullName.Replace("\", "/")] = $entry
            }
        }
        $fileRecords = @()
        foreach ($relativePath in $changedPaths) {
            if ($entries.ContainsKey($relativePath)) {
                $entry = $entries[$relativePath]
                $stream = $entry.Open()
                try {
                    $contentHash = (
                        [System.BitConverter]::ToString($sha256.ComputeHash($stream))
                    ).Replace("-", "")
                }
                finally {
                    $stream.Dispose()
                }
                $fileRecords += [pscustomobject]@{
                    path = $relativePath
                    state = "present"
                    bytes = $entry.Length
                    sha256 = $contentHash
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
    }
    finally {
        $archive.Dispose()
    }
}
finally {
    if (Test-Path -LiteralPath $temporaryArchive) {
        Remove-Item -LiteralPath $temporaryArchive -Force
    }
}

$canonicalLines = @(
    $fileRecords | ForEach-Object {
        "$($_.path)|$($_.state)|$($_.bytes)|$($_.sha256)"
    }
)
$canonicalText = ($canonicalLines -join "`n") + "`n"
$candidateFingerprint = (
    [System.BitConverter]::ToString(
        $sha256.ComputeHash($utf8NoBom.GetBytes($canonicalText))
    )
).Replace("-", "")

$result = [ordered]@{
    schema_version = 2
    batch = $Batch
    generated_at = (Get-Date).ToUniversalTime().ToString("o")
    base_commit = $resolvedBaseCommit
    candidate_commit = $resolvedCandidateCommit
    candidate_tree = $candidateTree
    candidate_parent = $parentCommit
    scope = "exact candidate tree changes from the accepted base, excluding this batch acceptance package and logs"
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
        status = "COMMITTED_PRODUCTIZATION_CANDIDATE_FINGERPRINT_OK"
        batch = $Batch
        output = $absoluteOutputPath
        candidate_commit = $resolvedCandidateCommit
        candidate_tree = $candidateTree
        candidate_fingerprint_sha256 = $candidateFingerprint
        candidate_file_count = $fileRecords.Count
        output_sha256 = (Get-FileHash -LiteralPath $absoluteOutputPath -Algorithm SHA256).Hash
    } | ConvertTo-Json -Compress
}
else {
    $json
}
