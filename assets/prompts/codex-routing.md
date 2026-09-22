---
description: Set the Codex local LLM sub-agent target percentage and synchronous wait policy.
argument-hint: [TARGET_PERCENT]
---

Update the persistent Codex model-routing policy for this chat and future work.

Arguments supplied after this command: $ARGUMENTS

Interpret the arguments as follows:

- No argument means a local LLM sub-agent target of 50%.
- A bare integer means that target percentage, from 0 through 100.
- `TARGET_PERCENT=75` sets the target to 75%.
- Keep `WAIT_FOR_RESULTS=true` unless the user explicitly asks to disable synchronous waiting.

Use the installed `manage-codex-routing-policy.ps1` helper to persist the
resolved target and wait policy. Then read back the JSON state and report the
target, wait setting, current eligible-task count, and current Ganglion share.

The target applies to eligible bounded sub-agent inference tasks. Do not force
local inference for secrets, high-stakes final judgment, tool-heavy edits, or
tasks where the resource sweep reports no usable route. When a local worker is
selected, wait for its result before continuing and validate the returned
evidence in the parent Codex session.
