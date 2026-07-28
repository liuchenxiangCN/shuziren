[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$EvidenceRoot,
    [string]$BaseCommit = "c24f041a0414ea5361a6fcb7216d7be99ea0bb56"
)

$ErrorActionPreference = "Stop"
$repoRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$repoPrefix = $repoRoot.TrimEnd("\") + "\"
$resolvedEvidenceRoot = [System.IO.Path]::GetFullPath($EvidenceRoot)
if (-not $resolvedEvidenceRoot.StartsWith($repoPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "EvidenceRoot must stay inside the repository."
}

$exactSecrets = [System.Collections.Generic.List[string]]::new()
foreach ($envName in @(".env.p2-1-preview", ".env.p1-3-preview")) {
    $envPath = Join-Path $repoRoot $envName
    if (-not (Test-Path -LiteralPath $envPath -PathType Leaf)) {
        continue
    }
    foreach ($line in Get-Content -LiteralPath $envPath -Encoding utf8) {
        if ($line -like "CONTROL_PLANE_ROOT_KEY_B64=*") {
            $value = $line.Substring($line.IndexOf("=") + 1)
            if (-not [string]::IsNullOrWhiteSpace($value) -and -not $exactSecrets.Contains($value)) {
                $exactSecrets.Add($value)
            }
        }
    }
}
if (-not [string]::IsNullOrWhiteSpace($env:CONTROL_PLANE_ROOT_KEY_B64)) {
    if (-not $exactSecrets.Contains($env:CONTROL_PLANE_ROOT_KEY_B64)) {
        $exactSecrets.Add($env:CONTROL_PLANE_ROOT_KEY_B64)
    }
}
if ($exactSecrets.Count -eq 0) {
    throw "No local root-key value was available for exact-value scanning."
}

$candidatePaths = [System.Collections.Generic.HashSet[string]]::new(
    [System.StringComparer]::OrdinalIgnoreCase
)
foreach ($path in @(& git -C $repoRoot diff --name-only $BaseCommit)) {
    if ($path) {
        [void]$candidatePaths.Add((Join-Path $repoRoot $path))
    }
}
foreach ($path in @(& git -C $repoRoot ls-files --others --exclude-standard)) {
    if ($path) {
        [void]$candidatePaths.Add((Join-Path $repoRoot $path))
    }
}

$scanFiles = [System.Collections.Generic.HashSet[string]]::new(
    [System.StringComparer]::OrdinalIgnoreCase
)
foreach ($path in $candidatePaths) {
    if (Test-Path -LiteralPath $path -PathType Leaf) {
        [void]$scanFiles.Add([System.IO.Path]::GetFullPath($path))
    }
}
foreach ($root in @(
    $resolvedEvidenceRoot,
    (Join-Path $repoRoot "apps\web\dist"),
    (Join-Path $repoRoot "data")
)) {
    if (-not (Test-Path -LiteralPath $root -PathType Container)) {
        continue
    }
    foreach ($file in Get-ChildItem -LiteralPath $root -Recurse -File) {
        if (
            $root.EndsWith("\data") -and
            $file.Name -notlike "control-plane-p1-*.db" -and
            $file.Name -notlike "control-plane-p1-*.db-*" -and
            $file.Name -notlike "control-plane-p2-*.db" -and
            $file.Name -notlike "control-plane-p2-*.db-*"
        ) {
            continue
        }
        [void]$scanFiles.Add($file.FullName)
    }
}

$exactFindings = [System.Collections.Generic.List[object]]::new()
$patternFindings = [System.Collections.Generic.List[object]]::new()
$textExtensions = @(
    ".css", ".html", ".js", ".json", ".log", ".md", ".sha256",
    ".txt", ".xml", ".yaml", ".yml"
)
$dangerousPatterns = @(
    [regex]::new(
        '(?i)\b(?:authorization\s*:\s*(?:bearer|basic)|devicecredential)\s+[A-Za-z0-9._~+/=-]{12,}',
        [System.Text.RegularExpressions.RegexOptions]::CultureInvariant
    ),
    [regex]::new(
        '(?i)\bCONTROL_PLANE_ROOT_KEY_B64\s*=\s*[A-Za-z0-9+/=]{16,}',
        [System.Text.RegularExpressions.RegexOptions]::CultureInvariant
    ),
    [regex]::new(
        '(?i)\b(?:postgres(?:ql)?|mysql|oracle|mongodb(?:\+srv)?)://[^/\s:@]+:[^@\s/]+@',
        [System.Text.RegularExpressions.RegexOptions]::CultureInvariant
    ),
    [regex]::new(
        '(?i)\b(?:api[_-]?key|client[_-]?secret|password|passwd|pwd|dsn)\s*[:=]\s*["''](?!replace_me\b|synthetic\b|<)[^"'']{12,}["'']',
        [System.Text.RegularExpressions.RegexOptions]::CultureInvariant
    )
)

foreach ($path in $scanFiles) {
    $bytes = [System.IO.File]::ReadAllBytes($path)
    $text = [System.Text.Encoding]::UTF8.GetString($bytes)
    foreach ($secret in $exactSecrets) {
        if ($text.Contains($secret)) {
            $exactFindings.Add([ordered]@{
                path = $path.Substring($repoPrefix.Length).Replace("\", "/")
                kind = "exact_local_root_key"
            })
        }
    }
    if (
        $path.StartsWith($resolvedEvidenceRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
        $path.StartsWith(
            (Join-Path $repoRoot "apps\web\dist"),
            [System.StringComparison]::OrdinalIgnoreCase
        )
    ) {
        if ([System.IO.Path]::GetExtension($path).ToLowerInvariant() -in $textExtensions) {
            foreach ($pattern in $dangerousPatterns) {
                if ($pattern.IsMatch($text)) {
                    $patternFindings.Add([ordered]@{
                        path = $path.Substring($repoPrefix.Length).Replace("\", "/")
                        kind = "unapproved_secret_pattern"
                        pattern = $pattern.ToString()
                    })
                }
            }
        }
    }
}

$status = if ($exactFindings.Count -eq 0 -and $patternFindings.Count -eq 0) {
    "PASS"
}
else {
    "FAIL"
}
$result = [ordered]@{
    schema_version = 1
    gate = "p2_1_secret_surfaces"
    status = $status
    scanned_file_count = $scanFiles.Count
    exact_secret_value_count = $exactSecrets.Count
    exact_secret_findings = @($exactFindings)
    unapproved_pattern_findings = @($patternFindings)
    notes = @(
        "Exact local root-key values were scanned without recording their values.",
        "Synthetic rejection fixtures are outside generic-pattern classification.",
        "Profile/API/audit/SQLite/backup surfaces are also asserted in backend tests.",
        "Screenshots are visually reviewed; exact values are scanned as binary data."
    )
}
$securityRoot = Join-Path $resolvedEvidenceRoot "security"
New-Item -ItemType Directory -Path $securityRoot -Force | Out-Null
$outputPath = Join-Path $securityRoot "secret-scan.json"
[System.IO.File]::WriteAllText(
    $outputPath,
    (($result | ConvertTo-Json -Depth 10) + "`n"),
    (New-Object System.Text.UTF8Encoding($false))
)
$result | ConvertTo-Json -Depth 10
if ($status -ne "PASS") {
    exit 1
}
