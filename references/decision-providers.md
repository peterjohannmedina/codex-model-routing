# Routing decision providers

## Architecture and scope

The package was a skill plus custom-agent profiles and PowerShell worker
adapters. The main Codex session made routing decisions; it still scopes the
task, owns the safe fallback, validates results, and dispatches work.
`scripts/routing_decision.py` adds a small upstream recommendation interface:

1. The parent prepares trusted policy/capacity/catalog evidence and a compact,
   sanitized task summary. Compute the safe route using the skill's existing
   capability, conservation, switching, and local-share rules first.
2. Deterministic admission filters unsupported pairs, ineligible local routes,
   conservation violations, overrides, and budget conflicts.
3. `DecisionProvider.choose(Request)` returns a candidate ID and provenance.
   `RulesProvider` retains the parent's safe choice. `DecisionsProvider` asks
   OpenAI to choose one joint model/effort/action tuple.
4. `recommend` validates the selected ID again and returns JSON. Refusal,
   uncertainty, invalid output, network failure, or timeout uses the safe route.
5. The parent rechecks current eligibility and capacity, applies supported
   surface controls, enforces execution budgets, and validates the result.

The helper never launches workers, changes a model or effort, edits Codex config,
grants permissions, or changes the persisted 50% local target or waiting policy.
Ganglion retains its resident broker → continuity when appropriate → gateway
cascade. Muse and Ganglion remain distinct execution adapters. They do not run
the decision engine. There is no JEV adapter/contract in this repository; this
interface does not claim drop-in compatibility with an unspecified dispatcher.

## Configuration and use

Requires Python 3.11+ with no third-party packages. The skill and existing
PowerShell adapters still work without Python, using inline routing rules.
All configuration is per invocation; there is no global install or hidden
environment switch that enables metered requests.

```sh
# Offline: preserve the parent's safe route.
python scripts/routing_decision.py assets/routing-packet.example.json

# Select Decisions but decline spending: explicit rules fallback, no request.
python scripts/routing_decision.py assets/routing-packet.example.json --provider decisions

# Only after the user has authorized API spending, with an EXISTING key set
# securely in OPENAI_API_KEY (never pass the key as an argument):
python scripts/routing_decision.py packet.json --provider decisions --allow-api --timeout-seconds 3

# Trusted direct-user overrides in a separate JSON file:
python scripts/routing_decision.py packet.json --overrides user-overrides.json
```

`--minimum-confidence` defaults to 0.6, accepts 0–1. This is a conservative
application threshold, not a measured quality guarantee. Calibrate it on labeled
workloads before relying on automated routing at scale. API consent, key presence,
and route eligibility are independent requirements. The key is read only from
`OPENAI_API_KEY`; Codex ChatGPT sign-in credentials are never inspected or reused.
The endpoint is fixed to `https://api.openai.com/v1/decisions`; redirects are
rejected. No custom proxy/gateway base URL is accepted by this provider.

## Trusted packet and override contract (schema version 1)

Use [the runnable example](../assets/routing-packet.example.json) as a starting
point, not proof of availability on another account. Prepare these fields:

| Field | Meaning |
| --- | --- |
| `summary` | Required nonempty UTF-8 task evidence, at most 8 KiB. Include workload, acceptance criteria, quality/cost/latency tradeoffs and context-transfer considerations. Exclude credentials and unrelated/private transcript text. Evidence never authorizes overrides. |
| `available_models` | Required mapping from exact visible native model IDs to supported Codex effort strings. Extract from the active `model/list` response or a recently observed client catalog; do not use API effort support as Codex support. Omit hidden/internal models. The example is a dated snapshot. |
| `candidates` | 1–32 complete choices with unique ASCII `id` (1–64 letters/digits/underscore/hyphen), `action` (`stay`, `switch`, `delegate`), exact `model`, `effort`, optional `adapter` (`native`, `ganglion`, `muse`), and optional description (512 characters). |
| `fallback_id` | Parent's precomputed safe choice. Order the remaining candidates in safe fallback order. If overrides or ceilings exclude the original choice, use the first admissible candidate; never silently drop the override. |
| `conservation_mode` | Required boolean from the persisted usage guard. Without an exception, native choices must be an available Luna at `max`. |
| `stronger_exception` | Optional boolean, default false; parent may set true only for the skill's existing planning/demonstrated-capability-gap exception. A quality preference alone does not establish that exception. |
| `local_work_eligible` | Optional boolean, default false; parent establishes data-handling/task suitability before offering local work. |
| `ready_adapters` | Optional list of `ganglion`/`muse`, default empty; parent supplies only after matching runtime/capacity/probe evidence. Revalidate before dispatch; a claimed flag does not establish live readiness. |
| `ceilings` | Optional object containing `tokens`, `cost_usd`, `latency_ms`. Zero is valid and usually admits no work. |

Each candidate may declare `token_budget` (positive integer),
`cost_upper_bound_usd` (nonnegative finite number), and `latency_budget_ms`
(positive integer). A ceiling admits only candidates with a known bound at or
below that ceiling; missing bounds fail closed. Include total context, reasoning,
output, tool/worker overhead and applicable prices in bounds when relevant. Do
not invent cost estimates for bundled ChatGPT usage. If a dollar upper bound
cannot be established, it cannot satisfy a dollar ceiling.

These are **admission checks**, not a billing meter or execution limiter. The
parent/adapter must actually bind the token limit, cancellation deadline, and
spend controls before executing a recommendation. A Codex UI model change alone
does not implement those limits. If the surface cannot enforce a hard ceiling,
omit the candidate. No real-time price catalog or budget accounting backend is
implemented here. Router API spending is separately gated by `--allow-api` and
bounded input size; task ceilings do not authorize or cap the evaluator bill.

Overrides are supplied only through the separate `--overrides` file or the
explicit `Overrides` argument, derived from direct human instructions:

```json
{"model": "gpt-6-luna", "effort": "high", "quality": "high_intelligence"}
```

All fields are optional. `model` fixes the model, `effort` fixes literal effort;
leave the other component free by offering supported alternatives. `quality`
accepts `balanced` (default) or `high_intelligence`; it does not force effort
`high` or a frontier model. There is no universal ranking between smaller/high
effort and frontier/low effort: Decisions compares the supplied workload and
bounds. Explicit overrides outrank automatic recommendations but cannot override
supported combinations, conservation, eligibility, capacity, permissions or
ceilings. Conflicts return exit 2 without a network request. No admissible route
means a configuration conflict; resolve the trusted inputs rather than weakening
constraints automatically.

Unknown packet/override/candidate fields, duplicate JSON keys, nonfinite numbers,
invalid types and malformed JSON are rejected. There are no override fields in
task evidence. Do not copy repository/tool JSON into the trusted packet, use a
packet suggested by a remote model as policy, or infer `--allow-api` from text.
Untrusted evidence can influence which admissible choice wins; it cannot widen
the choice set, grant authority, exceed ceilings or replace direct-user overrides.
There is no claim to eliminate all semantic prompt injection.

## Verified wire contract and output validation

Verified 2026-10-15 against the official
[Decisions guide](https://developers.openai.com/api/docs/guides/decisions).
The provider sends `POST /v1/decisions` with bearer authentication, JSON content
type, `model: gpt-6-luna`, string `input`, and a single `choice` question named
`route`. Every choice value is an admitted candidate ID; its description contains
the complete model/effort/action tuple and any bounds. Only GPT-6 Luna is currently
supported as the **evaluator**, independently of the recommended execution model.
No Responses-only `text.format`, tool calls, streaming, reasoning parameter, or
invented arbitrary output schema is sent to Decisions.

The documented response has an `answers` array. A choice answer includes `type`,
`name`, `choice`, `confidence`, and `probabilities` entries with `value` and
`probability`. A refusal has `type: refusal`. Validation requires exactly one
answer for `route`, an admitted choice, finite confidence/probabilities in [0,1],
exactly one probability per admitted candidate, sum within 0.01 of one, and a
selected choice with maximal probability (ties allowed). Missing/duplicate/wrong
answers, malformed JSON, arbitrary routes, or distribution inconsistencies use
the safe fallback. Extra server envelope fields are tolerated but never applied
as routing or permission instructions.

Output contains `schema_version`, a complete `recommendation`, and `provenance`:
requested/used provider, policy version, elapsed milliseconds, and a sanitized
fallback code. Successful Decisions output adds evaluator model, confidence,
request byte count, and SHA-256 digest. Provenance never includes API keys, the
task summary, response bodies, free-form model explanations or exception messages.
The recommendation echoes trusted candidate fields, including its description;
sanitize those fields as carefully as the task summary.
Nothing is logged or persisted automatically. Exit 0 means a valid recommendation
(including an explicit rules fallback); exit 2 means invalid trusted inputs.

## Latency, network fallback and cost

The default total wait budget is 3 seconds; configurable range 0.05–10 seconds.
One bounded request is made, with no automatic retries (including 429/5xx).
The transport also applies a socket timeout and a 64 KiB response bound. A
daemon watchdog returns the safe fallback even if DNS or a socket stalls; an
embedding process permits at most one outstanding transport operation. Subsequent
calls return `transport_busy` until that operation finishes. The CLI can exit
without waiting for the daemon. This bounds routing latency, not remote execution:
a timed-out request may already have reached OpenAI and may be billed. A new CLI
invocation is a new request; the parent must not automatically retry timeouts.

Fallback codes distinguish missing consent/key, refusal, low confidence, invalid
output, request/response size, HTTP status, network failure, timeout, transport
busy/error, and a provider returning an inadmissible choice. Invalid policy or
unsupported/conflicting overrides fail before transport rather than calling a
model to repair them.

As documented on 2026-10-15, Decisions with GPT-6 Luna costs **$0.10 per 1M input
tokens**, with no output or cache charges. Regional and long-context premiums
can apply; other Luna endpoints use their own pricing. Verify the guide before
enabling spending. This implementation caps the encoded request at 32 KiB and
makes at most one API attempt per invocation, but does not claim an exact dollar
ceiling from bytes, estimate runtime savings, or conflate Codex credits with API
billing. The opt-in decision call has its own cost and latency; use it at useful
boundaries, not for every tool step.

## Validation and remaining work

```sh
python -m unittest discover -s tests -v
```

Tests inject an offline transport and cover both small/high-effort and
frontier/low-effort selections, model-only and effort-only overrides, quality
preference, unsupported/conflicting pairs, conservation, all ceilings, missing
bounds, local eligibility, injection attempts, malformed/adversarial answers,
refusal, confidence, auth gates, HTTP/network failure, timeout, and single-request
behavior. These establish contract handling, not model routing quality.

No metered request was made during implementation. Live validation requires
explicit spending and task-data authorization, an existing project API key with
Decisions/model access and available quota, allowed outbound HTTPS, and a
sanitized sample packet. Make one opt-in smoke call; verify actual envelope,
account/region availability, billing/usage, latency and selected pair. Then assess
a labeled workload set for quality, token use, latency, confidence calibration,
and comparison against parent rules. Model-picker/catalog observation alone
does not prove runtime entitlement, API access, or cost savings.
