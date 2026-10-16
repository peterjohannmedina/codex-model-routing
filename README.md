# Codex Model Routing

A Codex skill for choosing models, reasoning effort, and subagents to fit the task. It weighs capability, available usage, context transfer, and coordination costs, with a built-in option to delegate bounded subtasks to local LLMs.

Native Codex routing works with **no extra providers**. OpenAI Decisions and
generic local execution are independently optional and disabled by default.

| Local provider | Decisions | Behavior |
| --- | --- | --- |
| Off | Off | Parent's native model/effort recommendation; no provider request |
| On | Off | Configured, eligible local choices may join the native choices; rules select |
| Off | On | Decisions may select a native model/effort pair after explicit API consent |
| On | On | Decisions may choose from admitted native and configured local pairs |

Missing keys, unconfigured/offline providers, refusals and errors retain an
admissible recommendation. Explicit require-local requests, unsupported overrides
and hard ceilings fail closed when no route satisfies them. Recommendations do
not execute native work or authorize a paid fallback.

The complete portable entrypoint is included:

```powershell
# Windows: selects an existing Python 3.11+ runtime, skipping Store aliases.
powershell.exe -NoProfile -File .\scripts\Invoke-Routing.ps1 -PacketPath .\assets\routing-packet.example.json -Offline
```

```sh
# Unix, or use python3 scripts/routing_runtime.py with the same arguments.
sh scripts/invoke-routing.sh assets/routing-packet.example.json --offline
```

Set `CODEX_ROUTING_PYTHON` for an explicit existing interpreter. No SDK, tokenizer,
local server or key is required for the baseline. See
[portable providers and local execution](references/local-workers.md) for config,
secure credential options, readiness checks and bounded execution.

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
powershell.exe -NoProfile -File .\scripts\install.ps1
```

PowerShell 7 (`pwsh`) can run the same installer.

Both installers copy the complete skill, including launchers and configuration examples, to `~/.codex/skills/codex-model-routing`, register the native profiles, install the routing prompt, and merge instructions into `~/.codex/AGENTS.md`. Existing named local profiles are preserved. Legacy local profiles are installed only with `-IncludeLegacyLocalProfiles` / `--include-legacy-local-profiles`, without overwriting existing profiles. On Windows, `~` means the current user's profile directory. Installation does not create a user configuration or credential file.

Start a new Codex chat or restart Codex after installation so the updated skill and agents are discovered.

## Local dashboard and live observations

![Routing dashboard overview with eight synthetic requests across two demo sessions, separate usage totals, activity chart, and labeled cost estimates.](docs/images/dashboard-overview.png)

*Actual dashboard rendered in Chromium with synthetic demo data. The values are
illustrative; no provider calls, real account activity or measured bills were used.
These images document the initial dashboard release.*
See [capture provenance and reproduction steps](references/dashboard-screenshots.md).

<details>
<summary>Provider controls and activity screenshots (synthetic demo)</summary>

![Dashboard provider controls showing independent Decisions and local LLM settings, historical observations, and local history retention controls.](docs/images/dashboard-providers.png)

*Saved provider settings and historical observations. Saving settings does not
run inference or grant spending permission.*

![Dashboard activity ledger with eight synthetic requests and one expanded local execution showing dummy identifiers, model and effort, execution status, and separate evaluator and downstream usage.](docs/images/dashboard-activity.png)

*Synthetic activity with dummy identifiers and illustrative usage. A recommendation
is displayed separately from an observed execution.*

</details>

One localhost dashboard aggregates the instrumented runtime and opt-in Codex
exec JSON streams. It includes persistent provider controls, session drilldown,
retained daily totals, model/effort and override/fallback metadata, separate
evaluator/downstream usage, and labeled cost estimates. It refreshes every two
seconds without provider health checks or toggle-triggered execution.

```powershell
powershell.exe -NoProfile -File .\scripts\Start-RoutingDashboard.ps1 -OpenBrowser
```

```sh
sh scripts/invoke-routing.sh dashboard --open-browser
```

The launcher opens a private one-use authorization file, then the dashboard at
`http://127.0.0.1:8765`. Provider credentials are never read by the
dashboard. The instrumented runtime keeps a bounded local metadata ledger by
default (7 days / 500 requests), with disable/clear controls and no external
export. Existing older/private adapters, arbitrary already-open TUI sessions and
the ChatGPT app are unobserved. A recommendation does not switch a running CLI
model or prove execution. See [setup, privacy and supported sources](references/dashboard.md)
and the [dashboard requirements](references/dashboard-prd.md).

New local Codex CLI 0.162.1 sessions can also appear automatically through an
explicitly approved user-level OTel exporter. The local receiver retains only
allowlisted metadata and shows startup settings and model-response usage separately
from exec-turn totals. It is disabled by default; installation does not enable it
or replace existing exporters. See [automatic session pickup, privacy, activation
and undo](references/automatic-telemetry.md). Other app surfaces and ordinary
ChatGPT chats remain unverified or unsupported.

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

The routing prompt reports configuration by default:

```text
/prompts:codex-routing status
```

The public default local route uses a configured endpoint/model, with no Muse or Ganglion dependency. Existing deployments can still explicitly use the legacy capacity sweep, share-target helper and named profiles. See [Local LLM setup](references/local-workers.md) and the separate [legacy adapters](references/legacy-local-workers.md). Installation does not provision or contact an LLM server.

## Scope

Install the package once per Codex environment or user profile. Publishing or updating a repository does not update an existing installation; rerun the installer when you want to deploy a newer version.

Routing decisions do not change permissions. The optional `routing-bypass` profile is provided as a reference and is not enabled by the installer.
