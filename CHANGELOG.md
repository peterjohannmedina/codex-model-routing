# Changelog

## 2026-08-14

### Changed

- Published the skill as a standalone repository with installation documentation.
- Updated the installer and setup prompts to register the personal skill under `%USERPROFILE%\\.codex\\skills`, the active Codex personal-skill location.
- Removed the machine-specific source path from the setup prompts.

## 2026-08-09

### Added

- Added a persistent usage-limit conservation guard. When an observed session or weekly Codex usage bucket reaches 90% used, it records the state and preserves conservation mode until the triggering bucket is positively observed to reset.
- Integrated the `cost-tracker` guidance into routing: live Codex usage data takes priority when it is available, while context reduction and batching remain the supporting conservation practices.

### Changed

- Luna now uses `max` reasoning effort by default.
- In conservation mode, Luna at `max` is the main route for all operations. Terra and Sol are restricted to planning or a clearly demonstrated Luna capability gap; routine implementation, exploration, testing, formatting, and review remain on Luna.

### Clarified

- Codex does not expose a machine-readable background usage meter through the installed CLI. The guard consumes the usage page, banner, or in-session `/status` when the active surface exposes it, and retains the last persisted state otherwise.

## 2026-08-04

### Added

- Added a complete Windows installer that installs the full skill package, registers the Luna, Terra, and Sol custom-agent profiles, and idempotently merges the global routing instructions into the user's home `AGENTS.md`.
- Added a root-level first-step setup prompt so Codex can discover the installation workflow immediately after extracting the package.
- Added a paste-ready ZIP bootstrap workflow: attach the archive, explicitly instruct Codex to extract it, recursively locate and read the setup prompt, install the complete package, validate the result, and remove the temporary extraction directory.
- Added context-aware model-routing guidance that scopes main-session and subagent models during planning and weighs capability, context transfer, coordination, and rework costs before switching.
- Added Codex surface and switching-economics references with documented evidence boundaries.

### Changed

- Clarified that changing models does not inherently require a new Codex session; supported surfaces can change models within the current chat.
- Prefer remaining in the current model for coherent work, increasing reasoning effort before switching when appropriate, and using bounded subagents for isolated work.
- Require installation of the entire package rather than copying only `SKILL.md`.

### Clarified

- `/init` only scaffolds an `AGENTS.md` for the current project. It does not extract archives, install skills, or execute prompts found inside a ZIP.
- An attached ZIP is inert until the user explicitly tells Codex to extract and inspect it. Codex does not automatically execute a prompt merely because the prompt exists in the archive.
- The optional `routing-bypass` profile remains disabled unless the user explicitly requests it.
