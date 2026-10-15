[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$PacketPath,
    [ValidateSet('rules', 'decisions')][string]$Provider,
    [string]$ConfigPath,
    [string]$OverridesPath,
    [switch]$AllowApi,
    [switch]$PreflightOnly,
    [switch]$Offline,
    [switch]$ExecuteLocal,
    [switch]$AllowLocalInference,
    [string]$RequestId = ([Guid]::NewGuid().ToString()),
    [string]$SessionId,
    [switch]$NoLedger,
    [Nullable[int]]$MaxDecisionInputTokens,
    [Nullable[decimal]]$MaxDecisionCostUsd,
    [string]$PythonPath,
    [string]$SkillRoot,
    [string]$CredentialPath,
    [string]$PreflightScriptPath,
    [string]$RoutingScriptPath
)

$ErrorActionPreference = 'Stop'
$routingUserRoot = [Environment]::GetFolderPath('UserProfile')
$routingCodexRoot = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $routingUserRoot '.codex' }
if (-not $PythonPath) {
    $routingPythonCandidates = @($env:CODEX_ROUTING_PYTHON, (Join-Path $routingUserRoot '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'))
    foreach ($routingCommand in @('python3', 'python')) {
        $routingFoundCommand = Get-Command $routingCommand -ErrorAction SilentlyContinue
        if ($routingFoundCommand -and $routingFoundCommand.Source -notmatch 'WindowsApps') { $routingPythonCandidates += $routingFoundCommand.Source }
    }
    foreach ($routingCandidate in $routingPythonCandidates) {
        if ($routingCandidate -and (Test-Path -LiteralPath $routingCandidate -PathType Leaf)) {
            & $routingCandidate -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)' 2>$null
            if ($LASTEXITCODE -eq 0) { $PythonPath = $routingCandidate; break }
        }
    }
    if (-not $PythonPath) { throw 'Python 3.11+ is required. Set CODEX_ROUTING_PYTHON to an existing interpreter; no runtime was installed.' }
}
if (-not $SkillRoot) { $SkillRoot = Split-Path -Parent $PSScriptRoot }
if (-not $CredentialPath) { $CredentialPath = Join-Path $routingCodexRoot 'routing\openai-key.dpapi' }
if (-not $PreflightScriptPath) { $PreflightScriptPath = Join-Path $SkillRoot 'scripts\routing_runtime.py' }
if (-not $RoutingScriptPath) { $RoutingScriptPath = Join-Path $SkillRoot 'scripts\routing_runtime.py' }

function Invoke-RoutingPython {
    param([string[]]$RoutingArguments, [AllowNull()][Security.SecureString]$RoutingKey,
          [string]$KeyEnvironment = 'OPENAI_API_KEY', [switch]$PermitEnvironmentKey)
    $routingStart = New-Object Diagnostics.ProcessStartInfo
    $routingStart.FileName = $PythonPath
    # Arguments are file paths, fixed switches or numeric bounds, never shell code.
    $routingQuoted = foreach ($routingArgument in $RoutingArguments) {
        if ($routingArgument.Contains('"')) { throw 'Invalid routing argument.' }
        '"' + $routingArgument + '"'
    }
    $routingStart.Arguments = $routingQuoted -join ' '
    $routingStart.UseShellExecute = $false
    $routingStart.CreateNoWindow = $true
    $routingStart.RedirectStandardOutput = $true
    $routingStart.RedirectStandardError = $true
    if (-not $PermitEnvironmentKey) { $routingStart.EnvironmentVariables.Remove('OPENAI_API_KEY') }
    if ($null -ne $RoutingKey) {
        $routingCredential = New-Object Net.NetworkCredential('', $RoutingKey)
        $routingStart.EnvironmentVariables[$KeyEnvironment] = $routingCredential.Password
        $routingCredential = $null
    }
    $routingProcess = New-Object Diagnostics.Process
    $routingProcess.StartInfo = $routingStart
    try {
        [void]$routingProcess.Start()
        $routingStart.EnvironmentVariables.Remove('OPENAI_API_KEY')
        if ($null -ne $RoutingKey) { $routingStart.EnvironmentVariables.Remove($KeyEnvironment) }
        $routingOutputTask = $routingProcess.StandardOutput.ReadToEndAsync()
        $routingErrorTask = $routingProcess.StandardError.ReadToEndAsync()
        # A configured route may perform a 10s readiness probe plus a 10s
        # decision or local completion. Retain a finite outer process bound.
        if (-not $routingProcess.WaitForExit(25000)) {
            $routingProcess.Kill()
            throw 'Local routing process timed out.'
        }
        $routingOutput = $routingOutputTask.GetAwaiter().GetResult()
        [void]$routingErrorTask.GetAwaiter().GetResult()
        return [pscustomobject]@{ Output = $routingOutput; ExitCode = $routingProcess.ExitCode }
    } finally {
        $routingStart.EnvironmentVariables.Remove('OPENAI_API_KEY')
        if ($null -ne $RoutingKey) { $routingStart.EnvironmentVariables.Remove($KeyEnvironment) }
        $routingProcess.Dispose()
    }
}

function Write-RoutingChildResult {
    param($RoutingResult)
    if ($RoutingResult.ExitCode -ne 0) {
        # Admission can change after preflight. Preserve its failure instead of
        # returning a stale candidate. Never print arbitrary failed-child output.
        $routingFailure = @{ error = 'routing_child_failed'; recommendation = $null }
        try {
            $routingChildFailure = $RoutingResult.Output | ConvertFrom-Json
            if ($routingChildFailure.error -in @('invalid_or_unsatisfied_routing_configuration', 'required_route_failed')) {
                $routingFailure.error = $routingChildFailure.error
                if ($routingChildFailure.error -eq 'invalid_or_unsatisfied_routing_configuration') {
                    $routingFailure.execution_started = $false
                } else {
                    $routingFailure.execution = @{ status = 'failed'; native_execution_started = $false }
                }
                $routingReason = if ($routingChildFailure.reason) { $routingChildFailure.reason } else { $routingChildFailure.execution.reason }
                if ($routingReason -cmatch '^[a-z0-9_]{1,80}$') { $routingFailure.reason = $routingReason }
            }
        } catch { }
        $routingFailure | ConvertTo-Json -Compress
        exit 2
    }
    $RoutingResult.Output
}

foreach ($routingRequired in @($PythonPath, $PreflightScriptPath, $RoutingScriptPath, $PacketPath)) {
    if (-not (Test-Path -LiteralPath $routingRequired -PathType Leaf)) { throw 'A required local routing file is missing.' }
}
$routingPacket = (Resolve-Path -LiteralPath $PacketPath).Path
$routingPreflightArguments = @('-B', $PreflightScriptPath, $routingPacket, '--preflight-only', '--request-id', $RequestId)
$routingArguments = @('-B', $RoutingScriptPath, $routingPacket, '--request-id', $RequestId)
if ($SessionId) { $routingPreflightArguments += @('--session-id', $SessionId); $routingArguments += @('--session-id', $SessionId) }
if ($NoLedger) { $routingPreflightArguments += '--no-ledger'; $routingArguments += '--no-ledger' }
if ($Provider) { $routingPreflightArguments += @('--provider', $Provider); $routingArguments += @('--provider', $Provider) }
if ($ConfigPath) { $routingPreflightArguments += @('--config', $ConfigPath); $routingArguments += @('--config', $ConfigPath) }
if ($Offline) { $routingPreflightArguments += '--offline'; $routingArguments += '--offline' }
if ($OverridesPath) {
    $routingOverrides = (Resolve-Path -LiteralPath $OverridesPath).Path
    $routingPreflightArguments += @('--overrides', $routingOverrides)
    $routingArguments += @('--overrides', $routingOverrides)
}
if ($AllowApi) { $routingPreflightArguments += '--allow-api'; $routingArguments += '--allow-api' }
if ($null -ne $MaxDecisionInputTokens) { $routingPreflightArguments += @('--max-decision-input-tokens', [string]$MaxDecisionInputTokens) }
if ($null -ne $MaxDecisionCostUsd) { $routingPreflightArguments += @('--max-decision-cost-usd', $MaxDecisionCostUsd.ToString([Globalization.CultureInfo]::InvariantCulture)) }
if ($null -ne $MaxDecisionInputTokens) { $routingArguments += @('--max-decision-input-tokens', [string]$MaxDecisionInputTokens) }
if ($null -ne $MaxDecisionCostUsd) { $routingArguments += @('--max-decision-cost-usd', $MaxDecisionCostUsd.ToString([Globalization.CultureInfo]::InvariantCulture)) }
# Preflight never loads DPAPI or calls Decisions. It may authenticate the
# explicitly configured local readiness GET, including with OPENAI_API_KEY.
# Preserve ambient credentials for that configured use; Python enforces the
# provider boundary rather than treating one environment-variable name as global.
$routingPreflightResult = Invoke-RoutingPython -RoutingArguments $routingPreflightArguments -RoutingKey $null -PermitEnvironmentKey
if ($routingPreflightResult.ExitCode -ne 0) { Write-RoutingChildResult $routingPreflightResult; return }
$routingPreflight = $routingPreflightResult.Output | ConvertFrom-Json
if ($PreflightOnly) { $routingPreflight | ConvertTo-Json -Depth 12 -Compress; return }
if ($ExecuteLocal) {
    $routingArguments += '--execute-local'
    if ($AllowLocalInference) { $routingArguments += '--allow-local-inference' }
    $routingResult = Invoke-RoutingPython -RoutingArguments $routingArguments -RoutingKey $null -PermitEnvironmentKey
    Write-RoutingChildResult $routingResult
    return
}
if (-not $routingPreflight.preflight.may_load_credential) {
    $routingPreflight.safe_result | ConvertTo-Json -Depth 12 -Compress
    return
}

# Reached only after admission, hard ceilings and explicit consent. Never invoke
# this branch without authority for spending and credential-loader use.
if (-not (Test-Path -LiteralPath $CredentialPath -PathType Leaf)) {
    $routingResult = Invoke-RoutingPython -RoutingArguments $routingArguments -RoutingKey $null -PermitEnvironmentKey
    Write-RoutingChildResult $routingResult
    return
}
$routingSecureKey = $null
try {
    $routingCredentialFailed = $false
    try {
        if (-not (Get-Module -Name Microsoft.PowerShell.Security)) {
            Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Security\Microsoft.PowerShell.Security.psd1') -ErrorAction Stop
        }
        $routingSecureKey = ConvertTo-SecureString -String ((Get-Content -LiteralPath $CredentialPath -Raw).Trim())
    } catch {
        $routingCredentialFailed = $true
    }
    if ($routingCredentialFailed) {
        # Revalidate current admission with rules, without attempting Decisions.
        # A required route that disappeared must still fail with exit 2.
        $routingResult = Invoke-RoutingPython -RoutingArguments ($routingArguments + @('--provider', 'rules')) -RoutingKey $null -PermitEnvironmentKey
        if ($routingResult.ExitCode -ne 0) { Write-RoutingChildResult $routingResult; return }
        $routingFallback = $routingResult.Output | ConvertFrom-Json
        $routingFallback.provenance.fallback_reason = 'local_credential_error'
        $routingFallback | ConvertTo-Json -Depth 12 -Compress
    } else {
        $routingResult = Invoke-RoutingPython -RoutingArguments $routingArguments -RoutingKey $routingSecureKey -KeyEnvironment $routingPreflight.preflight.api_key_env -PermitEnvironmentKey
        Write-RoutingChildResult $routingResult
    }
} finally {
    if ($null -ne $routingSecureKey) { $routingSecureKey.Dispose() }
}
