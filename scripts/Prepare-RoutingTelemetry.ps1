[CmdletBinding(DefaultParameterSetName = 'Plan')]
param(
    [string]$CodexHome,
    [ValidateRange(1, 65535)][int]$Port = 8765,
    [string]$PythonPath,
    [Parameter(Mandatory = $true, ParameterSetName = 'Apply')][switch]$Apply,
    [Parameter(Mandatory = $true, ParameterSetName = 'Undo')][switch]$Undo,
    [Parameter(Mandatory = $true, ParameterSetName = 'Apply')]
    [Parameter(Mandatory = $true, ParameterSetName = 'Undo')][string]$ApprovedConfigSha256
)
$ErrorActionPreference = 'Stop'
$PythonPath = & (Join-Path $PSScriptRoot 'Resolve-RoutingPython.ps1') -PythonPath $PythonPath
$telemetryArguments = @('-B', (Join-Path $PSScriptRoot 'routing_otel_setup.py'), '--port', [string]$Port)
if ($CodexHome) { $telemetryArguments += @('--codex-home', $CodexHome) }
if ($Apply) { $telemetryArguments += @('--apply', '--approved-config-sha256', $ApprovedConfigSha256) }
if ($Undo) { $telemetryArguments += @('--undo', '--approved-config-sha256', $ApprovedConfigSha256) }
& $PythonPath @telemetryArguments
exit $LASTEXITCODE
