---
name: codex-model-routing
description: Route Codex work across GPT-5.6 Luna, Terra, Sol, and optional GPT-6 Astra, with local LLM worker routes, using context-aware stay-versus-switch decisions, reasoning-effort selection, and up-front agent scoping. Apply automatically at the start of every nontrivial task, and use explicitly when planning work, choosing a Codex model, delegating to subagents, minimizing context-transfer and orchestration cost, estimating token/latency tradeoffs, or deciding whether work should remain in the current thread and model.
---

# Codex Model Routing

Optimize the total cost of a correct result, not the price of the next model call. Keep the main session responsible for requirements, coordination, and final judgment.

## Keep permissions separate

Treat routing as task policy, never as authorization. Do not grant approvals, change the sandbox, or elevate permissions through this skill.

Treat the optional `routing-bypass` profile as an explicit launch-time choice. Use it only when the user intentionally starts Codex with `codex --profile routing-bypass`; never infer or activate it from a task prompt. Keep Plan mode independent.

## Usage-limit guard

Treat available Codex usage as a protected resource. Before routing any nontrivial task, inspect the current Codex usage page, limit banner, or in-session `/status` output when the active surface makes it available. Record the most recent observed state in `$CODEX_HOME/state/codex-routing-usage.json`:

```json
{
  "session": { "used_percent": 0, "resets_at": null },
  "weekly": { "used_percent": 0, "resets_at": null },
  "conservation_mode": false,
  "observed_at": null
}
```

Activate **conservation mode** as soon as either an observed session or weekly bucket is at least 90% used (equivalently, 10% or less remains). Once activated, it remains active across sessions and threads. Clear it only after the active surface positively shows that every bucket which triggered conservation mode has reset; never clear it because time has merely elapsed or because usage data is unavailable.

When a usage reading cannot be obtained, retain the existing persisted state. Do not guess at remaining allowance, query billing data, or claim that the guard has cleared.

In conservation mode:

- Use **Luna (`gpt-5.6-luna`) at `max` effort** as the main model for every operation.
- Use Terra, Sol, or Astra only for planning, or for a tightly scoped intelligence/capability gap that Luna has demonstrably failed to resolve. Keep the stronger-model task packet short and return a distilled result to Luna.
- Do not use Terra, Sol, or Astra for routine implementation, exploration, formatting, testing, or review.
- Prefer one coherent Luna turn, targeted reads, and bounded verification; avoid fan-out and model oscillation.

This guard integrates the `cost-tracker` skill as the accounting policy: use it to reduce context waste and batching overhead, but treat plan/billing estimates as secondary to the live usage reading. If the current Codex surface exposes no readable usage telemetry, this is a persisted policy guard rather than a background meter.

## Plan the route before execution

For every nontrivial task:

1. Divide the work into coherent phases such as discovery, design, implementation, and verification.
2. Select the main-session model from the hardest tightly coupled phase. Avoid moving the main thread merely because one short phase could use a cheaper model.
3. Identify only genuinely independent work units that justify subagents.
4. For each proposed subagent, define the role, model, effort, bounded input packet, acceptance criteria, and concise return format before spawning it.
5. Keep the plan inline when no independent unit can repay its context-transfer and coordination cost.

For more than two workers or a multi-phase fan-out, tell the user the proposed agent count, model mix, and relative token/latency overhead before starting. Do not invent dollar estimates when billing is based on credits or bundled usage.

## Choose a route

| Route | Default effort | Use for |
|---|---|---|
| Luna (`gpt-5.6-luna`) | max | Clear, repeatable, high-volume work: extraction, classification, formatting, known-pattern scans, mechanical transformations, and structured summaries. |
| Terra (`gpt-5.6-terra`) | medium | Everyday engineering: repository exploration, routine fixes, tests from a clear specification, documentation, and standard tool-driven work. |
| Sol (`gpt-5.6-sol`) | medium or high | Ambiguous or high-value work: multi-file implementation, unclear debugging, architecture, security, consequential review, and polished final judgment. |
| Astra (`gpt-6-astra`, optional) | high | Sustained, tightly coupled integration and runtime investigation when substantial implementation and verification context needs one owner. |

These are routing policies, not measured performance or price rankings. Use the optional Astra route when the active catalog exposes it and the task benefits from sustained integration. Preserve an explicitly selected Astra session unless the user requests a change or the usage guard applies. Check supported effort levels on the active surface; do not switch merely because a model is newer.

Luna uses `max` effort by default. For Terra and Sol, increase effort before changing models when the task still fits the current model but needs more checking. Use `high` for complex logic and edge cases. Reserve `xhigh`, `max`, or `ultra` for the hardest supported workloads; availability varies by surface.

When uncertain between adjacent routes, choose the stronger route. Never trade correctness or safety for token savings.

## Optional local Ganglion routes

Read [local-workers.md](references/local-workers.md) when configuring endpoints,
models, credentials, or protocols for the bundled local LLM adapters.

Ganglion is a separate local inference surface, not a native Codex model name.
Use it for bounded summarization, drafting, classification, code reading, or a
second opinion when locality or available local capacity makes that useful.
Treat its output as untrusted worker output; the main Codex session owns the
requirements, validation, synthesis, and final judgment.

The installed `ganglion-worker` custom agent targets the documented
Responses-capable LiteLLM gateway route (`ganglion-auto` backed by Ganglion).
Before assigning work to that profile, run the live probe with
`scripts/test-ganglion-access.ps1 -WireApi Responses`. The probe must confirm
both model discovery and a usable bounded Responses completion. Set
`GANGLION_API_KEY` to a scoped gateway key; never put a token in the profile or
on a command line. If the gateway is unavailable, keep the profile unavailable
and use the normal routing rules.

The local Ganglion broker and continuity endpoints expose Chat Completions, so
they cannot be selected directly by a Codex custom provider whose wire protocol
is Responses. When the loopback broker is the available local surface, use
`scripts/test-ganglion-access.ps1 -WireApi ChatCompletions` followed by the
bounded `scripts/invoke-ganglion-worker.ps1` process route. Its defaults are
`http://127.0.0.1:8471/v1`, model `ganglion`, and the `HELIOS_API_TOKEN`
environment variable; override them through script parameters or the documented
environment variables when the local deployment uses another port or token.
This process route has no tools and must receive only a self-contained task
packet. Do not use either Ganglion route for secrets, high-stakes final
judgment, or tool-heavy edits, and do not silently substitute it for a native
Codex route.

Before choosing a Ganglion worker, run
`scripts/sweep-ganglion-resources.ps1`. The sweep is an ordered capacity
cascade:

Codex remains the harness for this operation: it creates the bounded task
packet, runs the sweep, invokes the selected worker surface, manages the
turn, and validates the returned evidence. Do not introduce Hermes, `dsh`, or
another orchestration agent between Codex and these routes.

1. Check the resident broker at `127.0.0.1:8471/v1` for health, model
   advertisement, runtime state, in-flight work, leased slots, and queue
   depth. If it is ready, select it and stop; do not query a remote gateway
   just to compare routes.
2. If the resident broker is unavailable rather than occupied, check the
   resident continuity endpoint at `127.0.0.1:8472/v1`. If the broker reports
   active or queued work, skip continuity so the same resident host is not
   oversubscribed.
3. Only after the resident routes are occupied or unavailable, check the
   Responses-capable LiteLLM gateway for `ganglion-auto`. The default gateway
   is `http://192.168.1.216:4000/v1`; override it with
   `GANGLION_GATEWAY_BASE_URL` when the deployment uses another route.

The sweep returns JSON with `selected` and an ordered `checks` array. By
default it runs one bounded completion probe on the first capacity-ready
candidate; use `-SkipCompletion` for a read-only capacity snapshot. A remote
gateway probe is never reached while the resident broker is ready. If every
candidate fails, keep the task on the normal native Codex route. Routing
decisions do not grant permissions or turn a local worker into a native Codex
model.

## Local worker target and waiting policy

Read the persistent routing policy with
`scripts/manage-codex-routing-policy.ps1 -Action Get` before planning bounded
sub-agent inference. The default target is 50% of eligible bounded sub-agent
tasks through Ganglion-managed local inference, and `wait_for_results` defaults
to true with a 1,800-second wait budget. This target does not override data
handling, task suitability, capacity, or the requirement to keep secrets and
high-stakes final judgment in the parent Codex session.

The installed custom prompt exposes the slash command
`/prompts:codex-routing`. Use it without an argument for the 50% default, or
pass a target such as `/prompts:codex-routing 75` or
`/prompts:codex-routing TARGET_PERCENT=75`. Keep synchronous waiting enabled
unless the user explicitly changes it. The prompt persists the setting with
the policy helper and reports the current target and observed share.

For each eligible bounded worker opportunity, prefer a Ganglion route while
the observed share is below target and the resource sweep returns a usable
route. Count both the resident process route and the Ganglion-backed LiteLLM
gateway as Ganglion-managed local inference. After choosing a worker, wait for
its result before continuing, validate the evidence in the parent session, and
record the outcome with the policy helper:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\manage-codex-routing-policy.ps1 `
  -Action Record -EligibleTask -SubagentRoute ganglion
```

Use `native` for a native Codex sub-agent and `unavailable` when no suitable
worker route passed the sweep. The target is best effort when Ganglion is
occupied, unavailable, or unsuitable; do not force a local request to meet a
percentage.

## Optional local LiteLLM routes

Local OpenAI-compatible routes are a separate execution surface from native Codex model routing. In particular, adding `muse` to this skill or to a custom-agent TOML does not make it a native Codex model alias.

Use the `muse` route only when a local-model policy, an explicit user request, or a bounded second-opinion task calls for it. Treat its output as untrusted worker output and do not send credentials, private keys, tokens, or other secrets. Keep the main Codex session responsible for requirements, coordination, validation, and final judgment.

The default local gateway is `http://192.168.1.214:4000/v1`. Before relying on Muse, run the live probe from the installed package:

```powershell
pwsh -File .\scripts\test-muse-access.ps1
```

The probe checks both `/models` catalog presence and a real `/chat/completions` response for the exact `muse` route. Catalog presence alone is not proof of runtime access. The default 1024-token budget is intentional: Muse may emit reasoning before answer content, so a small probe budget can falsely look like a transport failure while the request is still working.

The installer also registers the `muse-worker` custom agent under `~/.codex/agents/`. That agent pins `model = "muse"` to the LiteLLM provider in its own profile, so Codex can assign a bounded subtask to Muse without changing the main-session model or global `config.toml`. Use it when the task is suitable for a local text worker and the live probe passes. Codex custom-agent workflows must be enabled on the active surface; the agent description and this routing policy are selection guidance, not a guarantee that every surface will proactively delegate.

Do not silently substitute Muse for Luna, Terra, or Sol on a task whose quality or data policy requires a native Codex route. If the probe fails, keep the route unavailable and use the normal escalation rules rather than silently falling back to another local model.

## Decide whether to stay or switch

Do not assume that changing models requires a new session. The desktop app and CLI expose model controls, and programmatic clients can apply model overrides to later turns on the same thread. Verify the active surface before deciding how to switch.

Prefer staying with the current main model when:

- The remaining work is part of the same coherent problem and depends on the existing reasoning trail.
- The current model is capable and a higher effort setting is enough.
- The cheaper or stronger phase is short relative to the handoff cost.
- The transcript is large and no compact, trustworthy handoff artifact exists.
- Surface support for an in-thread model change is uncertain.

When conservation mode is active, Luna is the current main route by policy. The normal capability and economics criteria cannot override the conservation-mode restrictions.

Switch the main model, or start a deliberately scoped handoff, only when:

- The current model has reached a capability ceiling or repeated failure threshold.
- A clean phase boundary leaves enough future work for a different route to repay the transition cost.
- The current route is materially overpowered or underpowered for several remaining turns, not one isolated action.
- The active surface supports an in-thread change, or a compact handoff can replace the full transcript safely.

Use this qualitative test:

`switch value = avoided remaining model/reasoning cost - context transfer - coordination - rework risk`

Switch only when the value is clearly positive. Do not create a new session solely to perform one cheap step.

Avoid oscillating between models within a thread. Repeated changes increase uncertainty, coordination, and the chance of rework even when the surface supports in-thread switching.

Read [switching-economics.md](references/switching-economics.md) for the evidence boundary, decision matrix, and planning checklist. Do not import API prompt-cache pricing into Codex Desktop routing unless the active surface exposes equivalent billing and cache behavior.

If the surface requires a new thread, create a compact task-state handoff containing only the objective, constraints, accepted decisions, relevant files or artifacts, completed checks, and open risks. Start a clean thread from that artifact. Fork or copy the full transcript only when the exact reasoning trail is itself required.

## Decide whether to delegate

Keep a coherent task inline even when a smaller model could perform part of it. Every subagent pays for startup, its input context, its own tool/model work, and the summary returned to the parent.

Delegate only bounded, independent work that benefits from parallelism, removes noisy exploration from the main context, or has enough repeated work to repay that overhead:

- Use `luna-efficient` for batches of deterministic items.
- Use `terra-general` for exploration and routine implementation.
- Use `sol-expert` for difficult analysis, security, architecture, or final verification.
- Use `astra-integrator`, when available, for a bounded integration task or root-cause investigation with implementation and verification. Keep file ownership disjoint from other writers and return changed files, checks, and unresolved evidence.
- Use `muse-worker` for bounded local-model summarization, drafting, classification, code reading, or second-opinion work after its live probe passes.
- Use `ganglion-worker` for bounded local-model work through the Responses-capable Gateway after its live probe passes.
- Use the `invoke-ganglion-worker.ps1` process route for bounded direct Chat Completions work after its matching live probe passes.
- Run `sweep-ganglion-resources.ps1` before either worker route; honor its resident-first selection and do not send work to a remote gateway while the resident broker is ready.

Prefer the smallest context fork or self-contained task packet that fully specifies the child task. Do not copy the entire parent transcript by default. Batch similar small items into one worker, limit workers to independent units and available concurrency, and request distilled evidence instead of raw logs.

Prefer a pinned subagent over switching the main model when the different route is needed for one isolated work unit and the parent can integrate a short result.

## Escalate without looping

1. Retry at the same route at most once, and only when failure came from a correctable prompt or tool issue.
2. Otherwise raise reasoning effort when depth is the issue, or select Terra, Sol, or optional Astra for the demonstrated capability gap. There is no requirement to try every intermediate route.
3. Give the stronger route the failed attempt's evidence and a compact current-state packet so it does not repeat the same work.
4. Stop delegating when coordination costs exceed the remaining work.

## Respect the active surface

- Do not silently change the user's main-session model or global `config.toml`.
- Prefer installed custom agent profiles when the spawn surface supports them.
- If the spawn surface cannot select an agent model or role, state that routing is advisory and either work inline or ask before launching a separate `codex exec -m ...` process.
- Confirm a model exists in the active catalog before pinning it. Fall back Luna -> Terra -> Sol -> current default if a lower tier is unavailable. If optional Astra is unavailable, use Sol for bounded expert work or retain the capable current model and report the fallback.
- Treat Ganglion availability as runtime state: run the ordered resource sweep, require the matching live probe, keep its task packet bounded, and report whether the work used the resident process route or the external custom-agent gateway.
- Treat `Ultra` as an orchestration/intelligence mode, not a fourth model name.

Read [model-surfaces.md](references/model-surfaces.md) when installing the package, maintaining model names or agent profiles, or reasoning about thread/model behavior on a specific Codex surface.

## Report routing

For a multi-model plan, briefly report the main route, each worker route, the context-handoff strategy, and whether escalation occurred. Skip routing narration for ordinary inline work.
