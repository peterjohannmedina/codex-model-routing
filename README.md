# Codex Model Routing

A Codex skill for choosing models, reasoning effort, and subagents to fit the task. It weighs capability, available usage, context transfer, and coordination costs, with a built-in option to delegate bounded subtasks to local LLMs.

## Install

Clone this repository into a temporary or development directory, then use the installer for your platform.

### macOS or Linux

```sh
git clone https://github.com/peterjohannmedina/codex-model-routing.git
cd codex-model-routing
./scripts/install.sh
```

The shell installer requires `rsync`.

### Windows

```powershell
git clone https://github.com/peterjohannmedina/codex-model-routing.git
Set-Location .\codex-model-routing
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

PowerShell 7 (`pwsh`) can run the same installer.

Both installers copy the complete skill to `~/.codex/skills/codex-model-routing`, register the bundled custom-agent profiles, install the routing prompt, and merge the routing instructions into `~/AGENTS.md`. On Windows, `~` means the current user's profile directory.

Start a new Codex chat or restart Codex after installation so the updated skill and agents are discovered.

## Usage

The routing skill is intended to apply automatically to nontrivial work. It can also be invoked explicitly with:

```text
$codex-model-routing
```

The router chooses whether to keep work in the current session or delegate a bounded task. Bundled native profiles cover Luna, Terra, Sol, and an optional Astra integrator; availability depends on the active Codex environment.

## Optional local LLM delegation

The router has built-in support for delegating subagent work to local LLMs. This is useful for self-contained tasks such as summarizing documents, classifying items, drafting text, reading code, or providing a second opinion. The main Codex session scopes the task, validates the result, and remains responsible for the final answer.

Connect a compatible local inference service or gateway using the bundled worker profiles and scripts. The router checks availability before assigning work and can prefer local capacity when it is suitable. If no configured local route is usable, work stays on an available native Codex route.

The included Ganglion integration provides capacity-aware route selection and a configurable target for the share of eligible tasks handled locally. Its default target is 50%, with result waiting and outcome tracking enabled. The target is best effort and applies only to suitable bounded work. For example:

```text
/prompts:codex-routing 75
```

See [Local LLM setup](references/local-workers.md) for provider configuration, supported protocols, connectivity checks, and the included Ganglion and Muse adapters. Local inference is optional; installation does not provision an LLM server.

## Scope

Install the package once per Codex environment or user profile. Publishing or updating a repository does not update an existing installation; rerun the installer when you want to deploy a newer version.

Routing decisions do not change permissions. The optional `routing-bypass` profile is provided as a reference and is not enabled by the installer.
