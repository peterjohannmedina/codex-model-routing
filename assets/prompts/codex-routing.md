---
description: Inspect or configure native routing and optional decision/local providers.
argument-hint: [status or requested configuration change]
---

Use the codex-model-routing skill to inspect routing or apply the user's requested configuration change.

Arguments supplied after this command: $ARGUMENTS

Interpret the arguments as follows:

- No argument or `status` means report configuration and available native model/effort pairs without changing anything or contacting providers.
- Native routing works without extra providers. Decisions and generic local execution are independently optional and disabled by default.
- Read `references/local-workers.md` for the external configuration path and packaged launchers. Preserve existing user configuration and named local profiles.
- Apply only the requested changes. Enabling a provider does not authorize metered requests or local inference; retain the separate execution consent gates.
- For a legacy numeric local-share request, read `references/legacy-local-workers.md` and explain its deployment-specific policy before making the requested change.

Honor explicit model/effort overrides, require-local, budgets and permissions.
When a worker is authorized and selected, wait for its bounded result and
validate the evidence in the parent Codex session. Report the concrete changes
and any constraints that prevented the requested configuration.
