# Codex Model Routing

A personal Codex skill for choosing model tier, reasoning effort, and bounded subagents according to task complexity, context-transfer cost, coordination cost, and rework risk.

## Install

Clone this repository into a temporary or development directory, then run the installer from its root:

```powershell
git clone https://github.com/peterjohannmedina/codex-model-routing.git
Set-Location .\codex-model-routing
pwsh -File .\scripts\install.ps1
```

The installer registers the complete skill package at `%USERPROFILE%\.codex\skills\codex-model-routing`, installs the Luna, Terra, and Sol custom-agent profiles under `%USERPROFILE%\.codex\agents`, and merges the marked routing block into `%USERPROFILE%\AGENTS.md`.

Start a new Codex chat or restart Codex after installation so the updated skill and agents are discovered.

## Usage

The routing skill is intended to apply automatically to nontrivial work. It can also be invoked explicitly with:

```text
$codex-model-routing
```

The optional `routing-bypass` profile is included as a reference only and is not enabled by the installer.

## Scope

Installation is per local Codex environment or user profile. A GitHub repository is the distribution source; Codex does not automatically load a skill merely because it exists on GitHub. Each machine, account, container, or isolated Codex environment must install the package once before it can discover the skill.
