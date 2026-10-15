[CmdletBinding()]
param([string]$StateDir, [ValidateRange(0, 65535)][int]$Port = 8765, [string]$PythonPath)
$ErrorActionPreference = 'Stop'
$PythonPath = & (Join-Path $PSScriptRoot 'Resolve-RoutingPython.ps1') -PythonPath $PythonPath
$routingArguments = @('-B', (Join-Path $PSScriptRoot 'routing_dashboard.py'), '--port', [string]$Port)
if ($StateDir) { $routingArguments += @('--state-dir', $StateDir) }
& $PythonPath @routingArguments
exit $LASTEXITCODE
