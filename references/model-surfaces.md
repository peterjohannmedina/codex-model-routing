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

Do not claim a measured billing or cache penalty for changing models unless the active Codex surface exposes that evidence. The routing policy treats context transfer, coordination, and rework as real costs; exact cross-model cache behavior remains an evidence boundary. Reasoning-effort changes stay on the same model when the surface supports them. See [switching-economics.md](switching-economics.md) for the break-even analysis and planning checklist.

## Custom agents

Codex loads personal custom-agent TOML files from `~/.codex/agents/` and project agents from `.codex/agents/`. Required fields are `name`, `description`, and `developer_instructions`. Optional `model` and `model_reasoning_effort` fields pin the route.

The canonical templates for this skill are under `assets/agents/`. Installation must copy them separately to `~/.codex/agents/`; keeping them only inside the skill directory does not register them as custom agents. `muse-worker.toml` is a provider-backed local worker: it pins `model = "muse"` and `model_provider = "litellm"` inside the child-agent profile, leaving the parent model and global provider unchanged.

## Package installation

Install the entire `codex-model-routing` directory, not only `SKILL.md`, because the workflow refers to this reference and ships custom-agent templates, a setup prompt, and an installer.

For a personal Codex installation, use Codex's own skill root:
`~/.codex/skills/`. The separate `~/.agents/skills/` root is shared by other
tools and is not an installation target for this package.

For a personal installation:

1. Copy the package to `~/.codex/skills/codex-model-routing/`.
2. Copy `assets/agents/*.toml` to `~/.codex/agents/`.
3. Merge `assets/AGENTS.md.snippet` into the user's home `AGENTS.md` when routing should apply to every nontrivial task under that home directory.
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
