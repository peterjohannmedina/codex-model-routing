# Changelog

## Unreleased - 2026-10-16

- Clarify credential environment-name fields and reject invalid names before a
  save request. Return static field-specific validation hints without echoing
  submitted values; reserve reload guidance for actual version conflicts.
- Handle native required/pattern rejection with fixed hints and accessible error
  state; clear custom validity on correction/reload. Exercise actual Save-button
  validation in Chromium with synthetic credentials and no requests or writes.
- Distinguish dashboard connectivity, saved enablement and retained observations
  from active session feeds or verified credentials. No credential is stored or
  tested by saving settings; telemetry activation remains separate.

## Unreleased — 2026-10-15

- Add disabled-by-default automatic local Codex CLI 0.162.1 session pickup from
  OTLP/HTTP JSON logs, with metadata filtering before storage, bounded authenticated
  loopback ingestion and separate model-response usage to avoid exec double counts.
- Add a read-only activation plan and explicit hash-approved user-config append,
  private local capability, byte-preserving backup/undo and existing-exporter refusal.
  Installation does not activate telemetry, start services or change hook trust.

- Preserve authoritative Codex thread identity and known annotations across
  partial replay; distinguish authorization fragments from navigation anchors;
  preserve edits made while an earlier configuration snapshot is being saved.

- Add a standalone loopback dashboard with persistent optional-provider controls,
  bounded local metadata ledger, session scope, daily totals, live polling and
  separate evaluator/downstream usage and estimated costs. No provider traffic
  originates from the dashboard; no global telemetry setting is changed.
- Add opt-in Codex exec JSON collection with stable correlation, replay dedup,
  late-usage enrichment, redaction and retention. Explicitly label unsupported
  TUI/ChatGPT feeds, unknown usage and unavailable measured billing.
- Package dashboard assets/startup and interpreter discovery for clean installs;
  add ledger/security/live HTTP and dependency-free UI regressions.
- Authorize local browsers through a private, expiring one-use bootstrap file;
  public static pages alone grant no settings/data access. Exclude launch files
  and ledgers from installers and Git alongside credentials.

- Make preflight dominate local-execution and consent flags on every platform.
  Preserve configured local readiness authentication in Windows preflight without
  loading DPAPI or invoking Decisions; add fake-transport and child-env regressions.
- Preserve Windows child admission failures and nonzero exit status instead of
  returning stale preflight success. Revalidate rules admission on credential
  errors and cover required-local readiness loss across all credential paths.

- Add a portable configured runtime, PowerShell/Unix launchers, external config
  sample and optional human-only Windows credential entry helper. Both extra
  providers default off; native routing needs neither credentials nor a local LLM.
- Add generic local model/effort admission and explicit bounded Chat Completions
  execution. Optional-provider failures preserve an admissible recommendation;
  require-local, overrides and hard budgets never authorize a paid fallback.
- Move named local profile templates to opt-in compatibility examples. Clean
  installs register native profiles only and preserve existing named profiles.
  Peter's running/private local installation is unchanged by this release work.

- Fix both installers to merge global routing guidance into
  `~/.codex/AGENTS.md`, the documented Codex global instruction location.
  Leave the legacy user-root `~/AGENTS.md` and unrelated instructions intact;
  add a repeated-install regression covering this discovery boundary.

- Update native defaults to GPT-6 Luna, GPT-6.1 Sol, and optional GPT-6 Astra,
  verified against official guidance and the installed Codex catalog. Add
  `sol-general`; retain `terra-general` as a compatibility profile using Sol.
- Add an optional standard-library Python decision-provider interface, offline
  rules fallback, and opt-in OpenAI Decisions integration selecting complete
  model/effort pairs. Keep eligibility, trusted component overrides, conservation,
  and declared budget ceilings outside model discretion.
- Bound decision latency and request/response sizes, disable automatic retries,
  validate choice/refusal/distribution output, and emit sanitized provenance.
- Resolve a single admissible candidate locally without a metered request, and
  enforce the Decisions API's 2–255 choice count at the provider boundary.
- Document configuration, API costs, trust boundaries, model-effort compatibility,
  execution-budget responsibilities, and the live validation still required.
  Add offline behavioral tests. Local adapters and their dispatch policy are
  unchanged; no global installation, deployment, or metered validation occurred.
- Remove the global instruction snippet's unsupported universal warm-cache-loss
  claim, aligning it with the existing switching-economics evidence boundary.

## 2026-09-22

### Added

- Published the deployed local LLM delegation implementation: Ganglion worker
  profile, process worker, capacity sweep, probes, routing policy, and prompt.
- Retained the optional Astra integrator from the Ganglion repository alongside
  the deployed Luna, Terra, Sol, Muse, and Ganglion profiles.
- Added a local-worker setup reference covering adapter configuration and the
  distinction between Responses custom agents and Chat Completions workers.

### Changed

- Reconciled the installed production package with the standalone GitHub history
  and the Astra additions from Ganglion commit `193e7d8b7201a7a2dcff73ed33bdd2f9143ec044`.
- Reframed the README around optional local LLM delegation and moved deployment
  addresses and provider-specific probes into the setup reference.
- Preserved the deployed worker implementation and 50% Ganglion target with
  synchronous waiting; no running service or active user configuration is changed.
- Required the reconciled profiles and reference in both installers, documented
  the Windows PowerShell entry point, and enforced LF endings for shell scripts.

### Fixed

- Resolve the default source directory after parameter binding so the Windows
  installer also runs under Windows PowerShell 5.1.
- Read instruction files as UTF-8 so Windows PowerShell preserves non-ASCII
  text when merging the global routing block.

## Earlier unreleased changes

### Added

- Added `scripts/install.sh` for native macOS and Linux installation.
- Added the optional `ganglion-worker` profile for a Responses-capable
  LiteLLM gateway backed by Ganglion.
- Added a live Ganglion catalog/completion probe and a bounded direct
  Chat-Completions process worker for loopback Ganglion deployments.
- Added the resident-first `sweep-ganglion-resources.ps1` cascade, including
  runtime occupancy checks and deferred LiteLLM gateway probing.
- Added the `/prompts:codex-routing` control, a persistent 50% local-worker
  target by default, synchronous result waiting, and usage accounting.

### Changed

- Standardized every installer and setup document on Codex's
  `~/.codex/skills/codex-model-routing` skill path.
- Made `scripts/install.ps1` construct paths with `Join-Path` components so it
  also works in PowerShell on macOS and Linux.

## 2026-08-14

### Changed

- Published the skill as a standalone repository with installation documentation.
- Updated the installer and setup prompts to register the personal skill under `%USERPROFILE%\\.codex\\skills`, the active Codex personal-skill location.
- Removed the machine-specific source path from the setup prompts.
- Kept Git repository metadata out of the installed skill copy.
- Documented the optional local LiteLLM/Muse worker surface and added a live probe that verifies both model catalog presence and usable completion output.
- Added the provider-backed `muse-worker` custom agent so Codex can assign bounded subtasks to Muse without making Muse a native main-session model alias.
- Corrected the model-surface reference so it does not present unverified cross-model cache billing behavior as measured fact.

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
