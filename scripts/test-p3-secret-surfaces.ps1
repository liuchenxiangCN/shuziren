[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$EvidenceRoot,
    [string]$BaseCommit = "a124f63b8f3b5e499b6c561e78199a26f860edc9"
)

$ErrorActionPreference = "Stop"
$scriptPath = Join-Path $PSScriptRoot "test-p2-1-secret-surfaces.ps1"
& $scriptPath -EvidenceRoot $EvidenceRoot -BaseCommit $BaseCommit -Gate "p3_secret_surfaces"
if (-not $?) {
    exit 1
}
