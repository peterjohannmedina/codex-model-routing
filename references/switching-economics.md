# When to switch models, and when to stay

Verified against the Codex manual and OpenAI documentation on 2026-08-04.

## Correct the premise

Changing models does not inherently require a new Codex session:

- The ChatGPT desktop app exposes model and reasoning controls beneath the composer.
- Interactive Codex CLI supports `/model` for changing the model or reasoning effort.
- Codex app-server accepts per-turn model and effort overrides that become defaults for later turns on the same thread.

A completely new chat does not generically inherit another chat's transcript. A fork explicitly copies stored history into a new thread. A subagent performs separate model and tool work from the bounded context it receives.

The user's cost concern is still directionally correct: long transcripts, forks, handoffs, and subagents can cause more context to be processed. However, do not claim that an in-thread model change necessarily creates extra input tokens beyond the context the next turn would already process.

## Keep the evidence boundary clear

OpenAI documents prompt caching and discounted cache reads for the OpenAI API. The public Codex manual does not establish an exact cross-model cache-hit rule, a per-model cache invalidation rule, or a token-price break-even formula for ChatGPT-authenticated Codex Desktop sessions.

Therefore:

- Do not present API prompt-cache pricing as Codex Desktop billing behavior.
- Do not claim that switching models always loses a warm prefix unless the active surface exposes evidence for that run.
- Do not invent exact token, dollar, credit, or cache-hit savings.
- Use observed per-response usage when the active client exposes it; otherwise make a qualitative routing decision.

## Evaluate total remaining work

Use these factors instead of a fabricated numeric threshold:

1. **Capability fit:** Can the current model finish correctly at an appropriate effort?
2. **Remaining duration:** Is the alternate route useful for several meaningful future turns or only one small action?
3. **Context dependence:** Does the remaining work require the accumulated reasoning trail, or can a compact task-state packet specify it safely?
4. **Boundary quality:** Is there a clean phase boundary, independent subtask, compaction point, or artifact handoff?
5. **Coordination cost:** Will another thread or agent require duplicated exploration, reconciliation, or revalidation?
6. **Rework risk:** Could a weaker route miss architectural, security, or product constraints that the current route already understands?

## Decision matrix

| Situation | Default decision | Reason |
|---|---|---|
| Same coherent task; current model is capable | Stay | Preserve continuity and avoid coordination overhead. |
| Same model fits, but the task needs deeper checking | Raise effort | Change depth before changing capability class. |
| One isolated deterministic batch exists | Delegate to Luna | A bounded child can return a compact result without moving the parent. |
| A large routine phase is cleanly separable | Delegate to Terra or start a scoped handoff | The remaining work can repay a small context packet. |
| Architecture, security, or repeated ambiguous failure appears | Escalate to Sol | Correctness dominates token savings. |
| Only a short cleanup phase remains | Stay | A new route is unlikely to repay its setup and review cost. |
| Work truly branches into an independent outcome | Start a new thread or fork intentionally | Separate transcripts prevent unrelated context growth. |
| Surface behavior is uncertain | Stay and verify | Do not spend tokens on an assumed transition mechanism. |

Prefer a pinned subagent over changing the main model when only one independent unit needs a different capability class. Prefer a compact new-thread handoff over a full-history fork when the exact reasoning trail is not required.

## Scope routes during planning

Before execution:

1. Identify the hardest tightly coupled phase and choose the main model for that ceiling.
2. Separate genuinely independent work units; do not split sequential dependencies merely to use cheaper models.
3. Assign each child a role, model, effort, bounded input packet, acceptance criteria, and concise return format.
4. Pass only the files, decisions, constraints, and evidence needed for that child.
5. Batch same-shape items into one worker.
6. Define the escalation condition and destination before the first attempt.
7. Keep the main thread stable unless a later phase boundary makes a switch clearly beneficial.

If a plan cannot state why each model boundary repays its context, coordination, and rework cost, keep the work inline.
