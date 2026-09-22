[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$SourceRoot,
    [string]$UserRoot = [Environment]::GetFolderPath('UserProfile'),
    [switch]$SkipGlobalInstruction
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
    (Join-Path (Join-Path 'assets' 'agents') 'astra-integrator.toml'),
    (Join-Path (Join-Path 'assets' 'agents') 'muse-worker.toml'),
    (Join-Path (Join-Path 'assets' 'agents') 'ganglion-worker.toml'),
    (Join-Path 'references' 'model-surfaces.md'),
    (Join-Path 'references' 'local-workers.md'),
    (Join-Path 'references' 'switching-economics.md'),
    (Join-Path 'scripts' 'test-muse-access.ps1'),
    (Join-Path 'scripts' 'test-ganglion-access.ps1'),
    (Join-Path 'scripts' 'invoke-ganglion-worker.ps1'),
    (Join-Path 'scripts' 'sweep-ganglion-resources.ps1'),
    (Join-Path 'scripts' 'manage-codex-routing-policy.ps1'),
    (Join-Path (Join-Path 'assets' 'prompts') 'codex-routing.md')
)

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

if ($PSCmdlet.ShouldProcess($skillDestination, 'Install Codex model-routing skill package')) {
    New-Item -ItemType Directory -Force -Path $skillParent | Out-Null
    if (-not [StringComparer]::OrdinalIgnoreCase.Equals($resolvedSource, $resolvedSkillDestination)) {
        New-Item -ItemType Directory -Force -Path $skillDestination | Out-Null
        Get-ChildItem -LiteralPath $resolvedSource -Force |
            Where-Object { $_.Name -ne '.git' } |
            Copy-Item -Destination $skillDestination -Recurse -Force
    }
}

if ($PSCmdlet.ShouldProcess($agentDestination, 'Install native and local-worker custom-agent profiles')) {
    New-Item -ItemType Directory -Force -Path $agentDestination | Out-Null
    Get-ChildItem -LiteralPath (Join-Path (Join-Path $resolvedSource 'assets') 'agents') -Filter '*.toml' -File |
        Copy-Item -Destination $agentDestination -Force
}

if ($PSCmdlet.ShouldProcess($promptDestination, 'Install the codex-routing slash prompt')) {
    New-Item -ItemType Directory -Force -Path $promptDestination | Out-Null
    Copy-Item -LiteralPath (Join-Path (Join-Path (Join-Path $resolvedSource 'assets') 'prompts') 'codex-routing.md') -Destination $promptDestination -Force
}

if (-not $SkipGlobalInstruction) {
    $agentsPath = Join-Path $UserRoot 'AGENTS.md'
    $snippet = Get-Content -Raw -LiteralPath (Join-Path (Join-Path $resolvedSource 'assets') 'AGENTS.md.snippet')
    $startMarker = '<!-- codex-model-routing:start -->'
    $endMarker = '<!-- codex-model-routing:end -->'

    $existing = if (Test-Path -LiteralPath $agentsPath) {
        Get-Content -Raw -LiteralPath $agentsPath
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
    Write-Output "Global AGENTS.md instruction: $(Join-Path $UserRoot 'AGENTS.md')"
}
Write-Output 'The optional routing-bypass permission profile was not enabled.'
Write-Output 'Start a new chat or restart Codex if the updated skill is not detected automatically.'
