# Codex routing surfaces

Verified 2026-10-15 against [official model guidance](https://learn.chatgpt.com/docs/models),
the installed Codex CLI 0.162.1 help, and its local `models_cache.json` catalog
(fetched 2026-10-15, catalog client version 0.162.0). A local catalog is runtime
selection evidence for this host, not a guarantee of access on another account.

## Models and reasoning effort

| Route | Exact ID | Package starting effort | Observed Codex efforts |
| --- | --- | --- | --- |
| Luna | `gpt-6-luna` | `high` (`max` in conservation mode) | low, medium, high, xhigh, max |
| Sol | `gpt-6.1-sol` | `low` (expert profile: `high`) | low, medium, high, xhigh, max, ultra |
| Previous Sol | `gpt-6-sol` | retain current supported effort | low, medium, high, xhigh, max, ultra |
| Astra | `gpt-6-astra` | `low` | low, medium, high, xhigh, max, ultra |

Official guidance recommends GPT-6.1 Sol for complex coding and Luna for focused,
repeatable work, starting at High for Luna or Light (`low`) for Astra. These are
starting policies rather than a universal ordering of model/effort pairs. Compare
task quality, available budgets, token use and latency jointly. The latest Sol
rollout depends on plan, client, and workspace settings; preserve a capable
explicitly selected model rather than switching merely because another is newer.

GPT-5.6 Luna, Terra, and Sol remain visible in the observed catalog during rollout;
they are compatibility routes, not the defaults. No `gpt-6-terra` model was found.
`sol-general` replaces the everyday Terra role with GPT-6.1 Sol. The old
`terra-general` filename/name remains as a compatibility profile using the same
Sol model/effort, so updates do not strand existing callers or obsolete profiles.
The optional `astra-integrator` uses GPT-6 Astra at `low`; increase effort when
the task warrants it. None of the native profiles uses a custom model provider.

Codex supports `ultra` on observed Sol/Astra routes as an orchestration mode;
Luna does not support it. API reasoning parameters are a different contract:
do not copy API `none` or omit surface checks because a model page lists an
API capability. The installed Codex catalog did not offer `none` on these routes.
The separate Decisions evaluator currently supports only `gpt-6-luna` and receives
no Codex effort parameter. See [decision-providers.md](decision-providers.md).

## Thread and model behavior

- The ChatGPT desktop app exposes model and reasoning controls beneath the composer.
- Interactive Codex CLI supports `/model` for changing the model or reasoning effort.
- Codex app-server accepts per-turn model and effort overrides; those values become defaults for later turns on the same thread.
- A generic model change therefore does not inherently require a new chat. Confirm the behavior of the active surface instead of assuming a session boundary.
- Continuing a coherent chat preserves its reasoning trail. A new chat has its own transcript; a fork copies stored history into a new thread.
- Subagents do their own model and tool work and therefore consume more tokens than a comparable inline run.

Even without a new thread, later turns process relevant retained context. Optimize the amount and relevance of context, not merely the number of thread IDs.

Do not claim a measured billing or cache penalty for changing models unless the active Codex surface exposes that evidence. The routing policy treats context transfer, coordination, and rework as real costs; exact cross-model cache behavior remains an evidence boundary. Reasoning-effort changes stay on the same model when the surface supports them. See [switching-economics.md](switching-economics.md) for the break-even analysis and planning checklist.

## Custom agents

Codex loads personal custom-agent TOML files from `~/.codex/agents/` and project agents from `.codex/agents/`. Required fields are `name`, `description`, and `developer_instructions`. Optional `model` and `model_reasoning_effort` fields pin the route.

The canonical templates for this skill are under `assets/agents/`. Installation must copy them separately to `~/.codex/agents/`; keeping them only inside the skill directory does not register them as custom agents. `muse-worker.toml` is a provider-backed local worker: it pins `model = "muse"` and `model_provider = "litellm"` inside the child-agent profile, leaving the parent model and global provider unchanged.

`ganglion-worker.toml` is a provider-backed local worker. It pins
`model = "ganglion-auto"` to a Responses-capable LiteLLM provider whose
upstream route is Ganglion, and reads the client key from `GANGLION_API_KEY`.
The installed Ganglion broker itself currently exposes Chat Completions, so the
direct loopback path uses `scripts/invoke-ganglion-worker.ps1` instead of a
Codex provider profile. Both paths require a live probe before use.

Use `scripts/sweep-ganglion-resources.ps1` as the route selector. It reads the
resident runtime and queue signals before checking the continuity endpoint or
the external LiteLLM gateway, so a ready local runtime short-circuits the
cascade and an occupied runtime causes the search to move outward.

The routing policy is persisted under the Codex state directory. Its default
is to target Ganglion-managed local inference for at least 50% of eligible
bounded sub-agent tasks and to wait synchronously for worker results. Use the
`/prompts:codex-routing` custom prompt to change the target.

See [local-workers.md](local-workers.md) for endpoint configuration, protocol
requirements, and the bundled local adapters.

## Package installation

Install the entire `codex-model-routing` directory, not only `SKILL.md`, because the workflow refers to this reference and ships custom-agent templates, a setup prompt, and an installer.

For a personal Codex installation, use Codex's own skill root:
`~/.codex/skills/`. The separate `~/.agents/skills/` root is shared by other
tools and is not an installation target for this package.

For a personal installation:

1. Copy the package to `~/.codex/skills/codex-model-routing/`.
2. Copy `assets/agents/*.toml` to `~/.codex/agents/`.
3. Merge `assets/AGENTS.md.snippet` into the user's Codex home `~/.codex/AGENTS.md` when routing should apply across projects. A user-root `~/AGENTS.md` is not the Codex global instruction file. Preserve unrelated instructions and keep local customizations outside the package's marked block.
4. Do not enable `assets/profiles/routing-bypass.config.toml` unless the user explicitly requests that permission profile.
5. Start a new chat or restart Codex if the updated skill or custom agents are not detected automatically.

On macOS and Linux, `scripts/install.sh` performs steps 1-3. On Windows,
`scripts/install.ps1` performs the same steps. Both leave the optional bypass
profile disabled.
The complete prompt in `assets/setup-prompt.md` can be pasted into another Codex Desktop chat to perform and verify the setup.

## Constraints

- Model names, supported effort levels, and UI controls can change. Re-check the current Codex manual or active model catalog before updating templates.
- Custom-agent selection depends on the active Codex client and tool surface.
- Do not use undocumented model aliases or copy pricing assumptions from another provider into Codex.
