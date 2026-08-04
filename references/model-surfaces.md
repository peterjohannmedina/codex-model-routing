# Codex routing surfaces

Verified against the local Codex manual on 2026-08-04.

## Models

- `gpt-5.6-sol`: detail, polish, difficult open-ended work, complex coding, research, computer use, and security.
- `gpt-5.6-terra`: the everyday balance of capability, latency, and cost; particularly useful for read-heavy subagents.
- `gpt-5.6-luna`: fastest and lowest-cost GPT-5.6 option for clear, repeatable tasks with an explicit success shape.

Reasoning effort is independent of the model. Prefer the lowest supported effort that meets the quality bar.

## Thread and model behavior

- The ChatGPT desktop app exposes model and reasoning controls beneath the composer.
- Interactive Codex CLI supports `/model` for changing the model or reasoning effort.
- Codex app-server accepts per-turn model and effort overrides; those values become defaults for later turns on the same thread.
- A generic model change therefore does not inherently require a new chat. Confirm the behavior of the active surface instead of assuming a session boundary.
- Continuing a coherent chat preserves its reasoning trail. A new chat has its own transcript; a fork copies stored history into a new thread.
- Subagents do their own model and tool work and therefore consume more tokens than a comparable inline run.

Even without a new thread, later turns process relevant retained context. Optimize the amount and relevance of context, not merely the number of thread IDs.

The measurable cost of a model change is the loss of the warm prompt prefix: previously-seen context is billed at a discount that is keyed to the serving model, so a switch re-prices the accumulated transcript as cold input on the next turn. Reasoning-effort changes stay on the same model and keep that prefix. See [switching-economics.md](switching-economics.md) for the break-even analysis and planning checklist.

## Custom agents

Codex loads personal custom-agent TOML files from `~/.codex/agents/` and project agents from `.codex/agents/`. Required fields are `name`, `description`, and `developer_instructions`. Optional `model` and `model_reasoning_effort` fields pin the route.

The canonical templates for this skill are under `assets/agents/`. Installation must copy them separately to `~/.codex/agents/`; keeping them only inside the skill directory does not register them as custom agents.

## Package installation

Install the entire `codex-model-routing` directory, not only `SKILL.md`, because the workflow refers to this reference and ships custom-agent templates, a setup prompt, and an installer.

Two personal skill roots exist and they are not interchangeable on every
machine. Check which one the active Codex build actually loads before
installing, and prefer the root where the client's other skills already
live:

- `~/.agents/skills/` — shared, vendor-neutral root used by several tools.
- `~/.codex/skills/` — Codex's own root.

`scripts/install.ps1` targets `~/.agents/skills/` by default. Override
`-UserRoot`, or copy the directory manually, when the active client loads
from `~/.codex/skills/` instead. Installing to the wrong root fails
silently: the skill simply never appears.

For a personal installation:

1. Copy the package to the correct skill root, e.g.
   `~/.agents/skills/codex-model-routing/` or
   `~/.codex/skills/codex-model-routing/`.
2. Copy `assets/agents/*.toml` to `~/.codex/agents/`.
3. Merge `assets/AGENTS.md.snippet` into the user's home `AGENTS.md` when routing should apply to every nontrivial task under that home directory.
4. Do not enable `assets/profiles/routing-bypass.config.toml` unless the user explicitly requests that permission profile.
5. Start a new chat or restart Codex if the updated skill or custom agents are not detected automatically.

On Windows, `scripts/install.ps1` performs steps 1-3 and leaves the optional bypass profile disabled.
The complete prompt in `assets/setup-prompt.md` can be pasted into another Codex Desktop chat to perform and verify the setup.

## Constraints

- Model names, supported effort levels, and UI controls can change. Re-check the current Codex manual or active model catalog before updating templates.
- Custom-agent selection depends on the active Codex client and tool surface.
- Do not use undocumented model aliases or copy pricing assumptions from another provider into Codex.
