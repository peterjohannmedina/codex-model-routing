[CmdletBinding()]
param([string]$StateDir, [ValidateRange(0, 65535)][int]$Port = 8765, [string]$PythonPath, [switch]$OpenBrowser, [string]$OtelTokenFile)
$ErrorActionPreference = 'Stop'
$PythonPath = & (Join-Path $PSScriptRoot 'Resolve-RoutingPython.ps1') -PythonPath $PythonPath
$routingArguments = @('-B', (Join-Path $PSScriptRoot 'routing_dashboard.py'), '--port', [string]$Port)
if ($StateDir) { $routingArguments += @('--state-dir', $StateDir) }
if ($OpenBrowser) { $routingArguments += '--open-browser' }
if ($OtelTokenFile) { $routingArguments += @('--otel-token-file', $OtelTokenFile) }
& $PythonPath @routingArguments
exit $LASTEXITCODE
