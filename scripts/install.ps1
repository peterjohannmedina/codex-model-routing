[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$SourceRoot,
    [string]$UserRoot = [Environment]::GetFolderPath('UserProfile'),
    [switch]$SkipGlobalInstruction,
    [switch]$IncludeLegacyLocalProfiles
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($SourceRoot)) {
    $SourceRoot = Split-Path -Parent $PSScriptRoot
}

$resolvedSource = (Resolve-Path -LiteralPath $SourceRoot).Path
$requiredFiles = @(
    'SKILL.md',
    (Join-Path 'agents' 'openai.yaml'),
    (Join-Path 'assets' 'AGENTS.md.snippet'),
    (Join-Path 'assets' 'setup-prompt.md'),
    (Join-Path (Join-Path 'assets' 'agents') 'luna-efficient.toml'),
    (Join-Path (Join-Path 'assets' 'agents') 'terra-general.toml'),
    (Join-Path (Join-Path 'assets' 'agents') 'sol-expert.toml'),
    (Join-Path (Join-Path 'assets' 'agents') 'sol-general.toml'),
    (Join-Path (Join-Path 'assets' 'agents') 'astra-integrator.toml'),
    (Join-Path 'references' 'model-surfaces.md'),
    (Join-Path 'references' 'decision-providers.md'),
    (Join-Path 'assets' 'routing-packet.example.json'),
    (Join-Path 'scripts' 'routing_decision.py'),
    (Join-Path 'scripts' 'routing_runtime.py'),
    (Join-Path 'scripts' 'routing_state.py'),
    (Join-Path 'scripts' 'routing_dashboard.py'),
    (Join-Path 'scripts' 'collect_codex_json.py'),
    (Join-Path 'scripts' 'Start-RoutingDashboard.ps1'),
    (Join-Path 'scripts' 'Resolve-RoutingPython.ps1'),
    'assets/dashboard/index.html',
    'assets/dashboard/app.js',
    'assets/dashboard/style.css',
    (Join-Path 'scripts' 'Invoke-Routing.ps1'),
    (Join-Path 'scripts' 'Set-RoutingApiKey.ps1'),
    (Join-Path 'scripts' 'invoke-routing.sh'),
    (Join-Path 'assets' 'routing-config.example.json'),
    (Join-Path 'references' 'local-workers.md'),
    (Join-Path 'references' 'switching-economics.md'),
    (Join-Path (Join-Path 'assets' 'prompts') 'codex-routing.md')
)
if ($IncludeLegacyLocalProfiles) {
    $requiredFiles += @('assets/legacy-agents/muse-worker.toml', 'assets/legacy-agents/ganglion-worker.toml',
        'scripts/test-muse-access.ps1', 'scripts/test-ganglion-access.ps1',
        'scripts/invoke-ganglion-worker.ps1', 'scripts/sweep-ganglion-resources.ps1',
        'scripts/manage-codex-routing-policy.ps1')
}

foreach ($relativePath in $requiredFiles) {
    $candidate = Join-Path $resolvedSource $relativePath
    if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
        throw "Router package is incomplete: missing $relativePath"
    }
}

$codexRoot = Join-Path $UserRoot '.codex'
$skillParent = Join-Path $codexRoot 'skills'
$skillDestination = Join-Path $skillParent 'codex-model-routing'
$agentDestination = Join-Path $codexRoot 'agents'
$promptDestination = Join-Path $codexRoot 'prompts'
$sourcePrefix = $resolvedSource.TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
$existingSkillDestination = Get-Item -LiteralPath $skillDestination -Force -ErrorAction SilentlyContinue
$resolvedSkillDestination = if ($null -ne $existingSkillDestination -and $existingSkillDestination.LinkType -in @('Junction', 'SymbolicLink')) {
    [IO.Path]::GetFullPath([string]$existingSkillDestination.Target)
} else {
    [IO.Path]::GetFullPath($skillDestination)
}

if (
    -not [StringComparer]::OrdinalIgnoreCase.Equals($resolvedSource, $resolvedSkillDestination) -and
    $resolvedSkillDestination.StartsWith($sourcePrefix, [StringComparison]::OrdinalIgnoreCase)
) {
    throw "Refusing to install the skill inside its own source directory: $resolvedSkillDestination"
}

function Copy-RoutingPackage {
    param([string]$From, [string]$To)
    foreach ($entry in Get-ChildItem -LiteralPath $From -Force) {
        if ($entry.Name -eq '.git' -or $entry.Name -eq '__pycache__' -or
            $entry.Name -like '*.pyc' -or $entry.Name -like '*.dpapi' -or $entry.Name -like '.env*') { continue }
        if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Package links are not supported by this installer.' }
        if ($entry.PSIsContainer) {
            $childDestination = Join-Path $To $entry.Name
            New-Item -ItemType Directory -Force -Path $childDestination | Out-Null
            Copy-RoutingPackage -From $entry.FullName -To $childDestination
        } else {
            Copy-Item -LiteralPath $entry.FullName -Destination $To -Force
        }
    }
}

if ($PSCmdlet.ShouldProcess($skillDestination, 'Install Codex model-routing skill package')) {
    New-Item -ItemType Directory -Force -Path $skillParent | Out-Null
    if (-not [StringComparer]::OrdinalIgnoreCase.Equals($resolvedSource, $resolvedSkillDestination)) {
        New-Item -ItemType Directory -Force -Path $skillDestination | Out-Null
        Copy-RoutingPackage -From $resolvedSource -To $skillDestination
    }
}

if ($PSCmdlet.ShouldProcess($agentDestination, 'Install native profiles and requested legacy profiles')) {
    New-Item -ItemType Directory -Force -Path $agentDestination | Out-Null
    foreach ($profileName in @('luna-efficient', 'sol-general', 'terra-general', 'sol-expert', 'astra-integrator')) {
        Copy-Item -LiteralPath (Join-Path $resolvedSource "assets/agents/$profileName.toml") -Destination $agentDestination -Force
    }
    if ($IncludeLegacyLocalProfiles) {
        foreach ($profileName in @('muse-worker', 'ganglion-worker')) {
            $existingProfile = Join-Path $agentDestination "$profileName.toml"
            if (-not (Test-Path -LiteralPath $existingProfile)) {
                Copy-Item -LiteralPath (Join-Path $resolvedSource "assets/legacy-agents/$profileName.toml") -Destination $existingProfile
            }
        }
    }
}

if ($PSCmdlet.ShouldProcess($promptDestination, 'Install the codex-routing slash prompt')) {
    New-Item -ItemType Directory -Force -Path $promptDestination | Out-Null
    Copy-Item -LiteralPath (Join-Path (Join-Path (Join-Path $resolvedSource 'assets') 'prompts') 'codex-routing.md') -Destination $promptDestination -Force
}

if (-not $SkipGlobalInstruction) {
    $agentsPath = Join-Path $codexRoot 'AGENTS.md'
    $snippet = Get-Content -Raw -Encoding utf8 -LiteralPath (Join-Path (Join-Path $resolvedSource 'assets') 'AGENTS.md.snippet')
    $startMarker = '<!-- codex-model-routing:start -->'
    $endMarker = '<!-- codex-model-routing:end -->'

    $existing = if (Test-Path -LiteralPath $agentsPath) {
        Get-Content -Raw -Encoding utf8 -LiteralPath $agentsPath
    } else {
        ''
    }

    $markerPattern = '(?ms)^<!-- codex-model-routing:start -->.*?^<!-- codex-model-routing:end -->\s*'
    $legacyPattern = '(?ms)^## Default Codex Model Routing\s*\r?\n.*?(?=^## |\z)'

    if ($existing.Contains($startMarker) -and $existing.Contains($endMarker)) {
        $updated = [regex]::new($markerPattern).Replace($existing, "$snippet`r`n", 1)
    } elseif ([regex]::IsMatch($existing, $legacyPattern)) {
        $updated = [regex]::new($legacyPattern).Replace($existing, "$snippet`r`n", 1)
    } else {
        $separator = if ([string]::IsNullOrWhiteSpace($existing)) { '' } else { "`r`n`r`n" }
        $updated = "$($existing.TrimEnd())$separator$snippet`r`n"
    }

    if ($PSCmdlet.ShouldProcess($agentsPath, 'Enable global Codex model-routing instruction')) {
        Set-Content -LiteralPath $agentsPath -Value $updated -Encoding utf8
    }
}

Write-Output "Skill: $skillDestination"
Write-Output "Custom agents: $agentDestination"
Write-Output "Custom prompts: $promptDestination"
if ($SkipGlobalInstruction) {
    Write-Output 'Global AGENTS.md instruction: skipped'
} else {
    Write-Output "Global AGENTS.md instruction: $(Join-Path $codexRoot 'AGENTS.md')"
}
Write-Output 'The optional routing-bypass permission profile was not enabled.'
Write-Output 'Start a new chat or restart Codex if the updated skill is not detected automatically.'
