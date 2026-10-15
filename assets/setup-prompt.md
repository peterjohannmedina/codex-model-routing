Set up the Codex model router from the local package directory containing this prompt.

Treat this as a local Codex configuration task and complete it end to end.

1. Read the entire source package before changing anything, including `SKILL.md`, relevant files under `references/`, `agents/openai.yaml`, `assets/AGENTS.md.snippet`, every file under `assets/agents/`, and the installers under `scripts/`.
2. Verify native model/effort pairs against the active catalog. Extra providers are optional and disabled by default. Do not probe or invoke local inference or Decisions during installation. Install the complete portable launcher/runtime/configuration package; preserve existing local profiles and user credentials.
3. Install the entire directory as the personal skill at `~/.codex/skills/codex-model-routing`. Do not install only `SKILL.md`; its references, assets, UI metadata, and installers are part of the package.
4. Run `scripts/install.sh` on macOS or Linux, or `scripts/install.ps1` on Windows, to install or update the skill, copy `assets/agents/*.toml` into `~/.codex/agents`, and merge the marked router block into `~/.codex/AGENTS.md` without duplicating it. If the appropriate script cannot run, perform those same operations manually and idempotently.
5. Do not change the user's default main-session model. Do not enable `assets/profiles/routing-bypass.config.toml`, change approval policy, or change sandbox permissions; routing and permissions are separate.
6. Verify the installed skill has valid YAML frontmatter, the installed package matches the source files, every source custom-agent TOML is present, the portable launchers, routing_runtime.py, routing_decision.py, optional credential-entry helper and configuration sample are present, the `codex-routing` custom prompt is installed under the Codex prompts directory, and `~/.codex/AGENTS.md` contains exactly one `codex-model-routing` marked block. Check the active instruction chain; a higher-priority `AGENTS.override.md` can supersede it.
7. Confirm that the routing policy plans the main model and reasoning effort from the hardest tightly coupled phase, scopes any subagents before execution, prefers staying in a coherent thread when context-transfer costs exceed savings, and switches or delegates only when the remaining work clearly repays context, coordination, and rework costs.
8. If Codex does not detect the updated skill or agents immediately, tell me to start a new chat or restart Codex. Do not claim installation succeeded until the filesystem checks pass.

Finish with a concise report containing the installed skill path, installed custom-agent files, whether global routing was enabled, whether any model substitution was necessary, validation results, and whether a restart or new chat is needed.
