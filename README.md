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

The router chooses whether to keep work in the current session or delegate a bounded task. Native defaults are GPT-6 Luna (`high`), GPT-6.1 Sol (`low`, or `high` for expert work), and optional GPT-6 Astra (`low`). GPT-6 Sol remains a compatibility route. Availability and supported efforts depend on the active Codex catalog. `terra-general` remains an alias profile for existing callers and now uses GPT-6.1 Sol; new tasks should use `sol-general`.

## Decisions routing provider

An optional Python 3.11+ helper (standard library only) implements a provider
interface with offline rules and OpenAI Decisions. Decisions selects one complete
model/effort/action combination from prevalidated candidates, considering quality,
budget, token efficiency, latency, and context transfer. Direct-user model or
effort overrides take precedence over automatic selection; hard eligibility and
budget constraints still apply. "High intelligence" is a quality preference.

```sh
python scripts/routing_decision.py assets/routing-packet.example.json
python -m unittest discover -s tests -v
```

The default makes no API calls. Selecting `--provider decisions` also requires
`--allow-api` and an existing `OPENAI_API_KEY` in the environment. Installation
does not enable spending, obtain credentials, or change the user's main model.
Refusal, invalid output, network errors and timeout return the parent's safe
route. Recommendations do not execute work. See
[provider configuration, trust boundary and contract](references/decision-providers.md)
for enabling it after authorization, packet fields, provenance, budgets, costs,
and the remaining live-validation requirements.

See [implementation verification](references/verification-2026-10-15.md) for
the dated source evidence and offline checks performed for this change.

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
