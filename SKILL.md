---
name: codex-model-routing
description: Route Codex work across GPT-5.6 Luna, Terra, and Sol with context-aware stay-versus-switch decisions, reasoning-effort selection, and up-front agent scoping. Apply automatically at the start of every nontrivial task, and use explicitly when planning work, choosing a Codex model, delegating to subagents, minimizing context-transfer and orchestration cost, estimating token/latency tradeoffs, or deciding whether work should remain in the current thread and model.
---

# Codex Model Routing

Optimize the total cost of a correct result, not the price of the next model call. Keep the main session responsible for requirements, coordination, and final judgment.

## Keep permissions separate

Treat routing as task policy, never as authorization. Do not grant approvals, change the sandbox, or elevate permissions through this skill.

Treat the optional `routing-bypass` profile as an explicit launch-time choice. Use it only when the user intentionally starts Codex with `codex --profile routing-bypass`; never infer or activate it from a task prompt. Keep Plan mode independent.

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
| Luna (`gpt-5.6-luna`) | low | Clear, repeatable, high-volume work: extraction, classification, formatting, known-pattern scans, mechanical transformations, and structured summaries. |
| Terra (`gpt-5.6-terra`) | medium | Everyday engineering: repository exploration, routine fixes, tests from a clear specification, documentation, and standard tool-driven work. |
| Sol (`gpt-5.6-sol`) | medium or high | Ambiguous or high-value work: multi-file implementation, unclear debugging, architecture, security, consequential review, and polished final judgment. |

Increase effort before changing models when the task still fits the current model but needs more checking. Use `high` for complex logic and edge cases. Reserve `xhigh`, `max`, or `ultra` for the hardest supported workloads; availability varies by surface.

When uncertain between adjacent routes, choose the stronger route. Never trade correctness or safety for token savings.

## Decide whether to stay or switch

Do not assume that changing models requires a new session. The desktop app and CLI expose model controls, and programmatic clients can apply model overrides to later turns on the same thread. Verify the active surface before deciding how to switch.

Prefer staying with the current main model when:

- The remaining work is part of the same coherent problem and depends on the existing reasoning trail.
- The current model is capable and a higher effort setting is enough.
- The cheaper or stronger phase is short relative to the handoff cost.
- The transcript is large and no compact, trustworthy handoff artifact exists.
- Surface support for an in-thread model change is uncertain.

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

Prefer the smallest context fork or self-contained task packet that fully specifies the child task. Do not copy the entire parent transcript by default. Batch similar small items into one worker, limit workers to independent units and available concurrency, and request distilled evidence instead of raw logs.

Prefer a pinned subagent over switching the main model when the different route is needed for one isolated work unit and the parent can integrate a short result.

## Escalate without looping

1. Retry at the same route at most once, and only when failure came from a correctable prompt or tool issue.
2. Otherwise raise reasoning effort when depth is the issue, or escalate Luna -> Terra -> Sol when capability is the issue.
3. Give the stronger route the failed attempt's evidence and a compact current-state packet so it does not repeat the same work.
4. Stop delegating when coordination costs exceed the remaining work.

## Respect the active surface

- Do not silently change the user's main-session model or global `config.toml`.
- Prefer installed custom agent profiles when the spawn surface supports them.
- If the spawn surface cannot select an agent model or role, state that routing is advisory and either work inline or ask before launching a separate `codex exec -m ...` process.
- Confirm a model exists in the active catalog before pinning it. Fall back Luna -> Terra -> Sol -> current default if a lower tier is unavailable.
- Treat `Ultra` as an orchestration/intelligence mode, not a fourth model name.

Read [model-surfaces.md](references/model-surfaces.md) when installing the package, maintaining model names or agent profiles, or reasoning about thread/model behavior on a specific Codex surface.

## Report routing

For a multi-model plan, briefly report the main route, each worker route, the context-handoff strategy, and whether escalation occurred. Skip routing narration for ordinary inline work.
