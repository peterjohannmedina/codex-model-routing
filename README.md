# Codex Model Routing

A personal Codex skill for choosing model tier, reasoning effort, and bounded subagents according to task complexity, context-transfer cost, coordination cost, and rework risk.

## Install

Clone this repository into a temporary or development directory, then use the installer for your platform.

### macOS or Linux

```sh
git clone https://github.com/peterjohannmedina/codex-model-routing.git
cd codex-model-routing
./scripts/install.sh
```

### Windows

```powershell
git clone https://github.com/peterjohannmedina/codex-model-routing.git
Set-Location .\codex-model-routing
pwsh -File .\scripts\install.ps1
```

Both installers register the complete skill package at `~/.codex/skills/codex-model-routing`, install the Luna, Terra, and Sol custom-agent profiles under `~/.codex/agents`, and merge the marked routing block into `~/AGENTS.md`. On Windows, `~` means the current user's profile directory.

Start a new Codex chat or restart Codex after installation so the updated skill and agents are discovered.

## Usage

The routing skill is intended to apply automatically to nontrivial work. It can also be invoked explicitly with:

```text
$codex-model-routing
```

The optional `routing-bypass` profile is included as a reference only and is not enabled by the installer.

## Scope

Installation is per local Codex environment or user profile. A GitHub repository is the distribution source; Codex does not automatically load a skill merely because it exists on GitHub. Each machine, account, container, or isolated Codex environment must install the package once before it can discover the skill.
