[CmdletBinding()]
param(
    [ValidateSet('Get', 'Set', 'Record', 'Reset')]
    [string]$Action = 'Get',
    [ValidateRange(0, 100)]
    [int]$LocalTargetPercent = 50,
    [bool]$WaitForResults = $true,
    [ValidateRange(1, 86400)]
    [int]$WaitTimeoutSec = 1800,
    [ValidateSet('ganglion', 'native', 'unavailable', 'none')]
    [string]$SubagentRoute = 'none',
    [switch]$EligibleTask,
    [string]$StatePath
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($StatePath)) {
    $routingCodexRoot = [Environment]::GetEnvironmentVariable('CODEX_HOME')
    if ([string]::IsNullOrWhiteSpace($routingCodexRoot)) {
        $routingCodexRoot = Join-Path ([Environment]::GetFolderPath('UserProfile')) '.codex'
    }
    $StatePath = Join-Path (Join-Path $routingCodexRoot 'state') 'codex-routing-policy.json'
}

function Set-PolicyProperty {
    param(
        [Parameter(Mandatory = $true)][object]$Policy,
        [Parameter(Mandatory = $true)][string]$Name,
        [AllowNull()][object]$Value
    )

    if ($null -eq $Policy.PSObject.Properties[$Name]) {
        Add-Member -InputObject $Policy -MemberType NoteProperty -Name $Name -Value $Value
    } else {
        $Policy.$Name = $Value
    }
}

function New-DefaultPolicy {
    return [pscustomobject]@{
        schema_version = 1
        local_llm_target_percent = 50
        wait_for_results = $true
        wait_timeout_sec = 1800
        eligible_subagent_tasks = 0
        ganglion_subagent_tasks = 0
        other_subagent_tasks = 0
        unavailable_subagent_tasks = 0
        local_llm_share_percent = $null
        target_met = $true
        last_route = 'none'
        updated_at = $null
    }
}

function Read-Policy {
    if (-not (Test-Path -LiteralPath $StatePath -PathType Leaf)) {
        return New-DefaultPolicy
    }

    $raw = Get-Content -Raw -LiteralPath $StatePath
    if ([string]::IsNullOrWhiteSpace($raw)) {
        return New-DefaultPolicy
    }

    try {
        $policy = $raw | ConvertFrom-Json
    } catch {
        throw "Routing policy state is not valid JSON: $StatePath"
    }

    $defaults = New-DefaultPolicy
    foreach ($property in $defaults.PSObject.Properties) {
        if ($null -eq $policy.PSObject.Properties[$property.Name]) {
            Set-PolicyProperty -Policy $policy -Name $property.Name -Value $property.Value
        }
    }
    return $policy
}

function Update-PolicySummary {
    param([Parameter(Mandatory = $true)][object]$Policy)

    $eligible = [int]$Policy.eligible_subagent_tasks
    $ganglion = [int]$Policy.ganglion_subagent_tasks
    $target = [int]$Policy.local_llm_target_percent
    $share = $null
    if ($eligible -gt 0) {
        $share = [math]::Round((100.0 * $ganglion) / $eligible, 1)
    }

    Set-PolicyProperty -Policy $Policy -Name 'local_llm_share_percent' -Value $share
    Set-PolicyProperty -Policy $Policy -Name 'target_met' -Value ($null -eq $share -or $share -ge $target)
    Set-PolicyProperty -Policy $Policy -Name 'updated_at' -Value ([DateTime]::UtcNow.ToString('o'))
}

function Write-Policy {
    param([Parameter(Mandatory = $true)][object]$Policy)

    $parent = Split-Path -Parent $StatePath
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $Policy | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $StatePath -Encoding utf8
}

$policy = Read-Policy

switch ($Action) {
    'Set' {
        Set-PolicyProperty -Policy $policy -Name 'local_llm_target_percent' -Value $LocalTargetPercent
        Set-PolicyProperty -Policy $policy -Name 'wait_for_results' -Value $WaitForResults
        Set-PolicyProperty -Policy $policy -Name 'wait_timeout_sec' -Value $WaitTimeoutSec
        Set-PolicyProperty -Policy $policy -Name 'last_route' -Value 'none'
    }
    'Record' {
        if (-not $EligibleTask.IsPresent) {
            throw 'Record requires -EligibleTask so the local-worker share has a defined denominator.'
        }

        $policy.eligible_subagent_tasks = [int]$policy.eligible_subagent_tasks + 1
        switch ($SubagentRoute) {
            'ganglion' { $policy.ganglion_subagent_tasks = [int]$policy.ganglion_subagent_tasks + 1 }
            'native' { $policy.other_subagent_tasks = [int]$policy.other_subagent_tasks + 1 }
            'unavailable' { $policy.unavailable_subagent_tasks = [int]$policy.unavailable_subagent_tasks + 1 }
            default { throw "Record requires -SubagentRoute ganglion, native, or unavailable." }
        }
        Set-PolicyProperty -Policy $policy -Name 'last_route' -Value $SubagentRoute
    }
    'Reset' {
        $policy.eligible_subagent_tasks = 0
        $policy.ganglion_subagent_tasks = 0
        $policy.other_subagent_tasks = 0
        $policy.unavailable_subagent_tasks = 0
        Set-PolicyProperty -Policy $policy -Name 'last_route' -Value 'none'
    }
}

Update-PolicySummary -Policy $policy
Write-Policy -Policy $policy
Write-Output ($policy | ConvertTo-Json -Depth 8)
