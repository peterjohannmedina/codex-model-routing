# Local LLM setup

The router can delegate bounded work to a local inference service while the
parent Codex session owns task selection, validation, and the final answer.
The bundled adapters target existing Ganglion and Muse deployments. Configure
their endpoint, model, and authentication settings for your environment before
use; the bundled LAN addresses are deployment defaults, not public services.

## Choose a connection

| Connection | Worker | Requirement |
|---|---|---|
| Codex custom agent | `ganglion-worker` or `muse-worker` | A compatible Responses API provider and custom-agent support in the active client |
| Bounded process worker | `scripts/invoke-ganglion-worker.ps1` | A compatible Chat Completions endpoint; this worker receives text and has no tools |

The profiles live in `assets/agents/` and are copied to `~/.codex/agents/`
by the installer. Set `model` and the provider's `base_url` to match your
deployment. Store any required key in the environment variable named by
`env_key`, never in the profile. A catalog response alone does not establish
that a route can complete a task. Check the protocol that the worker actually
uses before assigning work.

Custom agents and provider configuration are described in the official
[Codex subagent documentation](https://learn.chatgpt.com/docs/agent-configuration/subagents)
and [provider configuration guide](https://learn.chatgpt.com/docs/config-file/config-advanced).

## Ganglion route selection

Use PowerShell 7 (`pwsh`) or Windows PowerShell (`powershell.exe`) for the
scripts below. Start with the ordered resource sweep:

```powershell
pwsh -File .\scripts\sweep-ganglion-resources.ps1
```

It checks the resident broker first, including health, advertised models,
runtime occupancy, and a bounded completion. If the broker is ready, the sweep
stops there. If it is unavailable, the sweep checks the resident continuity
endpoint. If it is occupied, continuity is skipped to avoid oversubscribing the
same host. The remote gateway is considered only after resident routes cannot
take the work. Use `-SkipCompletion` for a capacity snapshot without inference.

| Setting | Default | Override |
|---|---|---|
| Resident broker | `http://127.0.0.1:8471/v1` | `GANGLION_BASE_URL` / `-LocalBaseUrl` |
| Resident continuity | `http://127.0.0.1:8472/v1` | `GANGLION_CONTINUITY_BASE_URL` / `-ContinuityBaseUrl` |
| Responses gateway | `http://192.168.1.216:4000/v1` | `GANGLION_GATEWAY_BASE_URL` / `-GatewayBaseUrl` |

The resident route defaults to model `ganglion` and key environment variable
`HELIOS_API_TOKEN`. The gateway defaults to `ganglion-auto` and
`GANGLION_API_KEY`. The sweep also accepts model and key-variable overrides;
see its parameter block. Configure the custom-agent profile separately to
match the selected gateway; changing a sweep parameter does not edit a profile.

For a Responses gateway, probe the same endpoint and model as the profile:

```powershell
pwsh -File .\scripts\test-ganglion-access.ps1 `
  -BaseUrl http://192.168.1.216:4000/v1 `
  -Model ganglion-auto -ApiKeyEnv GANGLION_API_KEY -WireApi Responses
```

For a direct Chat Completions worker:

```powershell
pwsh -File .\scripts\test-ganglion-access.ps1
pwsh -File .\scripts\invoke-ganglion-worker.ps1 `
  -Prompt 'Summarize the acceptance risks in the following task packet: ...'
```

Pass `-BaseUrl`, `-Model`, and `-ApiKeyEnv` to both scripts when the deployment
differs from their defaults. The process worker requires an explicit bounded
task packet and returns text for the parent to validate.

## Local-worker target and waiting

The installed prompt configures the Ganglion local-worker target:

```text
/prompts:codex-routing
/prompts:codex-routing 75
/prompts:codex-routing TARGET_PERCENT=75
```

With no argument the target is 50%. The policy persists in the Codex state
directory, counts eligible worker outcomes, and waits for results by default
with a 1,800-second budget. It counts both the direct Ganglion process route
and the Ganglion-backed gateway as local inference. The separate Muse adapter
is not counted as a Ganglion outcome. The target never overrides suitability,
capacity, or the requirement to keep secrets out of task packets.

Use `scripts/manage-codex-routing-policy.ps1` to inspect or update the policy
and record outcomes. Read `SKILL.md` for the parent agent's routing workflow.

## Muse adapter

The included `muse-worker` profile targets an existing LiteLLM deployment at
`http://192.168.1.214:4000/v1` with model `muse`. Adapt the profile for another
compatible deployment. The bundled diagnostic checks model advertisement and
a Chat Completions request:

```powershell
pwsh -File .\scripts\test-muse-access.ps1
```

Override `-BaseUrl`, `-Model`, `-MaxTokens`, or `-TimeoutSec` as needed. This
diagnostic does not by itself verify the Responses protocol used by the custom
agent; the gateway must support that protocol too. Neither adapter changes
the parent session's model or global provider settings.
