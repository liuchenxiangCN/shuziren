[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$EvidenceRoot,
    [string]$BaseCommit = "8939b8a7eadb9ba5493b1a74d4fbae23b2459cae"
)

$ErrorActionPreference = "Stop"
$scriptPath = Join-Path $PSScriptRoot "test-p2-1-secret-surfaces.ps1"
& $scriptPath `
    -EvidenceRoot $EvidenceRoot `
    -BaseCommit $BaseCommit `
    -Gate "p2_2_secret_surfaces"
if (-not $?) {
    exit 1
}
