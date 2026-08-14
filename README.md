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

Both installers register the complete skill package at `~/.codex/skills/codex-model-routing`, install the Luna, Terra, Sol, and `muse-worker` custom-agent profiles under `~/.codex/agents`, and merge the marked routing block into `~/AGENTS.md`. On Windows, `~` means the current user's profile directory.

Start a new Codex chat or restart Codex after installation so the updated skill and agents are discovered.

## Usage

The routing skill is intended to apply automatically to nontrivial work. It can also be invoked explicitly with:

```text
$codex-model-routing
```

### Optional LiteLLM/Muse probe

The skill can also document and validate access to the local OpenAI-compatible LiteLLM `muse` route. This is not a native Codex model alias and requires the gateway to be reachable from the current environment:

```powershell
pwsh -File .\scripts\test-muse-access.ps1
```

The probe must see `muse` in `/v1/models` and receive usable completion content from `/v1/chat/completions`. Override `-BaseUrl`, `-Model`, `-MaxTokens`, or `-TimeoutSec` for another gateway or deployment. It emits only connection and response metadata, not model output or credentials.

When the probe passes, Codex can select the installed `muse-worker` custom agent for a bounded subtask. This is a provider-backed sub-agent route, not a native model-picker entry: the child agent uses `model = "muse"` and its own LiteLLM provider settings while the parent remains on its current Codex model.

The optional `routing-bypass` profile is included as a reference only and is not enabled by the installer.

## Scope

Installation is per local Codex environment or user profile. A GitHub repository is the distribution source; Codex does not automatically load a skill merely because it exists on GitHub. Each machine, account, container, or isolated Codex environment must install the package once before it can discover the skill.
