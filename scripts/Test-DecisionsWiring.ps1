[CmdletBinding()]
param(
    [string]$ConfigPath,
    [string]$CredentialPath,
    [string]$PythonPath,
    [switch]$AllowApi
)
$ErrorActionPreference = 'Stop'
$routingRoot = Split-Path -Parent $PSScriptRoot
$routingArgs = @{ PacketPath = (Join-Path $routingRoot 'assets\decisions-validation.packet.json'); NoLedger = $true; DecisionTimeoutSeconds = 3 }
foreach ($name in @('ConfigPath','CredentialPath','PythonPath')) {
    if ($PSBoundParameters.ContainsKey($name)) { $routingArgs[$name] = $PSBoundParameters[$name] }
}
# Default is metadata/admission only, with no key load, inference or config save.
if (-not $AllowApi) {
    & (Join-Path $PSScriptRoot 'Invoke-Routing.ps1') @routingArgs -PreflightOnly
    return
}
# Passing AllowApi is a separate spending/secure-loader authorization. Check that
# this test would exercise the evaluator, then invoke the canonical launcher once.
$routingPreflight = (& (Join-Path $PSScriptRoot 'Invoke-Routing.ps1') @routingArgs -AllowApi -PreflightOnly) | ConvertFrom-Json
if (-not $routingPreflight.preflight.may_load_credential -or $routingPreflight.preflight.admissible_candidates -ne 2) {
    $routingReason = if ($routingPreflight.preflight.block_reason) { $routingPreflight.preflight.block_reason } else { $routingPreflight.safe_result.provenance.evaluator_reason }
    @{ validation = 'not_run'; reason = $routingReason; admissible_candidates = $routingPreflight.preflight.admissible_candidates; provider_calls = 0 } | ConvertTo-Json -Compress
    return
}
$routingArgs.Remove('NoLedger')
& (Join-Path $PSScriptRoot 'Invoke-Routing.ps1') @routingArgs -AllowApi
