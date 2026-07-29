[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$EvidenceRoot,
    [string]$BaseCommit = "a75d3327fdc1ab4b83b0bba501d387af150353c4"
)

$ErrorActionPreference = "Stop"
$scriptPath = Join-Path $PSScriptRoot "test-p2-1-secret-surfaces.ps1"
& $scriptPath `
    -EvidenceRoot $EvidenceRoot `
    -BaseCommit $BaseCommit `
    -Gate "p2_3_secret_surfaces"
if (-not $?) {
    exit 1
}
