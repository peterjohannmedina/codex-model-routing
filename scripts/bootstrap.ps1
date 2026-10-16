[CmdletBinding()]
param(
    [ValidateSet('install','update','repair','rollback','uninstall','status','doctor','start','open','stop')][string]$Command='install',
    [string]$PythonPath, [string]$UserRoot, [string]$CodexHome, [string]$SourceRoot,
    [ValidateRange(1,65535)][int]$Port=8765,
    [switch]$Start, [switch]$OpenBrowser, [switch]$Shortcuts, [switch]$LoginStartup,
    [switch]$OtelReceiver, [switch]$AdoptExisting
)
$ErrorActionPreference='Stop'
$routingPython = & (Join-Path $PSScriptRoot 'Resolve-RoutingPython.ps1') -PythonPath $PythonPath
$routingArguments=@('-B',(Join-Path $PSScriptRoot 'routing_bootstrap.py'),$Command)
if($UserRoot){$routingArguments+=@('--user-root',$UserRoot)}
if($CodexHome){$routingArguments+=@('--codex-home',$CodexHome)}
if($SourceRoot){$routingArguments+=@('--source-root',$SourceRoot)}
if($PSBoundParameters.ContainsKey('Port')){$routingArguments+=@('--port',[string]$Port)}
if($Start){$routingArguments+='--start'}
if($OpenBrowser){$routingArguments+='--open-browser'}
if($PSBoundParameters.ContainsKey('Shortcuts')){$routingArguments+= $(if($Shortcuts){'--shortcuts'}else{'--no-shortcuts'})}
if($PSBoundParameters.ContainsKey('LoginStartup')){$routingArguments+= $(if($LoginStartup){'--login-startup'}else{'--no-login-startup'})}
if($PSBoundParameters.ContainsKey('OtelReceiver')){$routingArguments+= $(if($OtelReceiver){'--otel-receiver'}else{'--no-otel-receiver'})}
if($AdoptExisting){$routingArguments+='--adopt-existing'}
& $routingPython @routingArguments
exit $LASTEXITCODE
