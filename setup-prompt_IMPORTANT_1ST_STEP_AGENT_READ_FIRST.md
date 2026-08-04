Set up the Codex model router from this local source directory:

`C:\Users\NM2\Documents\DevProjects\codex-model-routing`

Treat this as a local Codex configuration task and complete it end to end.

1. Read the entire source package before changing anything, including `SKILL.md`, both files under `references/`, `agents/openai.yaml`, `assets/AGENTS.md.snippet`, every file under `assets/agents/`, and `scripts/install.ps1`.
2. Verify the package is complete and that the Luna, Terra, and Sol model identifiers are available in the active Codex model catalog. Do not invent substitute model names. If a route is unavailable, preserve the package and report the exact unavailable route before adapting its installed custom-agent copy.
3. Install the entire directory as the personal skill at `%USERPROFILE%\.agents\skills\codex-model-routing`. Do not install only `SKILL.md`; its references, assets, UI metadata, and installer are part of the package.
4. Run `scripts/install.ps1` from the source package to install or update the skill, copy `assets/agents/*.toml` into `%USERPROFILE%\.codex\agents`, and merge the marked router block into `%USERPROFILE%\AGENTS.md` without duplicating it. If the script cannot run, perform those same operations manually and idempotently.
5. Do not change the user's default main-session model. Do not enable `assets/profiles/routing-bypass.config.toml`, change approval policy, or change sandbox permissions; routing and permissions are separate.
6. Verify the installed skill has valid YAML frontmatter, the installed package matches the source files, all three custom-agent TOMLs are present, and the home `AGENTS.md` contains exactly one `codex-model-routing` marked block.
7. Confirm that the routing policy plans the main model and reasoning effort from the hardest tightly coupled phase, scopes any subagents before execution, prefers staying in a coherent thread when context-transfer costs exceed savings, and switches or delegates only when the remaining work clearly repays context, coordination, and rework costs.
8. If Codex does not detect the updated skill or agents immediately, tell me to start a new chat or restart Codex. Do not claim installation succeeded until the filesystem checks pass.

Finish with a concise report containing the installed skill path, installed custom-agent files, whether global routing was enabled, whether any model substitution was necessary, validation results, and whether a restart or new chat is needed.
