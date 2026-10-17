# Account-aware model controls

The dashboard's **Refresh Codex catalog** action starts the installed `codex
app-server` over local stdio. It calls `initialize`, `account/read` with
`refreshToken: false`, paginated `model/list` with `includeHidden: false`, and a
second `account/read`. It never calls login, logout, thread, turn, inference,
configuration, or generic API `/models` methods. There is one discovery process
at a time, an eight-second overall RPC deadline, bounded messages/pages/models,
and cleanup of only the process created for discovery. A missing CLI, non-ChatGPT
login, malformed reply, timeout, or observed account change fails refresh.

On Windows this discovery feature requires native `codex.exe` on PATH, such as
the desktop app's bundled CLI. An npm installation exposing only `codex.cmd`
or `codex.ps1` is not supported for discovery in this release. The dashboard
reports `codex_cli_unavailable`; bootstrap `doctor` reports `catalog_cli_found`
separately from its general CLI prerequisite. This avoids a shell wrapper whose
child could outlive the bounded discovery process. macOS/Linux use executable
`codex`, including a normal executable launcher. Existing recommendation and
local-provider behavior does not require catalog discovery until an explicit
native allowlist is enabled. No CLI is installed automatically.

The native client can perform its own metadata requests and authentication
recovery. `refreshToken: false` does not guarantee that Codex makes no network
request or updates no native authentication cache. This tool requests no new
credentials, access grants, or login setup.

## What the list proves

The list is **reported by Codex**, with a query time and, when available, the
native cache's fetch timestamp. It is not a verified list of paid entitlements.
In Codex 0.163.0, `model/list` uses `OnlineIfUncached`. A valid disk cache may be
used, and a failed remote refresh may still return current or bundled fallback
models. The supported RPC has no force-remote parameter or definitive freshness
indicator. Refresh does not delete or modify Codex's cache to force a fetch.

The dashboard consequently always marks remote freshness, entitlement and
workspace scope as **unverified**. It shows missing, queried, stale or error
states separately. A successful query is recent for 15 minutes; it does not
prove inference access or future capacity. Failed refresh preserves the last
complete catalog with an error; partial pages never replace it.

Account replies are compared only in memory, before and after discovery. Every
received `account/updated` notification invalidates the refresh, even when its
values are unchanged. No emails, account/workspace identifiers, tokens, raw
replies/errors or identity hashes are persisted or sent to the browser. Stable
account metadata cannot prove a workspace change under the same account/plan,
and persisted catalogs are historical reports across launches. Refresh after
switching accounts or workspaces. The caller must still supply its current
account's available model/effort catalog in each routing packet; the router
intersects it with the saved report, rather than treating this file as access
authorization. Actual execution failures belong to the native dispatcher.

## Eligibility rules

`native.allowed_models: null` preserves an existing installation's packet-based
policy. The **Restrict native routing to selected models** switch opts into an
explicit allowlist; saving `[]` disables every native recommendation. Choices
are multi-select checkboxes, not a single preferred-model selector.

- New model IDs start unchecked. Discovery never changes saved eligibility.
- A saved model must also appear in the recent complete report and caller's
  current catalog. Requested efforts must appear in both, and be supported by
  this router. Unknown future efforts are displayed but cannot be routed.
- `required_modalities` optionally lists `text`, `image` and/or `audio`; default
  is `text`. Reported capabilities must cover all requested modalities. Older
  catalogs without modality metadata use Codex's documented text/image default.
- Overrides, conservation mode, local-only requirements and existing budgets
  remain hard constraints. A disabled or unavailable pinned model produces an
  admission error; it never silently switches to another model.
- Rules and Decisions choose only admitted candidates. Provider errors can fall
  back only to an admitted route. Local inference failure re-applies the same
  native policy; it never restores disabled native candidates or starts native
  inference.
- Local adapters remain separately controlled and can work with no native
  models or an unavailable native catalog. If none remain eligible, routing
  stops without inference.
- The optional Decisions evaluator uses `gpt-6-luna`. An explicit native
  allowlist excluding that ID also skips evaluation, reports
  `evaluator_model_disabled`, and retains an eligible rules fallback. API
  consent, credentials and spending controls remain separate.

The portable runtime and direct `routing_decision.py` CLI load the persisted
allowlist. Library callers must pass the parsed configuration and catalog to
the runtime. Low-level `Request`/`DecisionProvider` primitives operate on an
already-admitted request; constructing them yourself is not global policy
enforcement. Direct Codex invocations and other tools are not intercepted.

Example saved policy (in the external routing `config.json`):

```json
"native": {"allowed_models": ["gpt-6.1-sol", "gpt-6-luna"]}
```

The catalog lives beside it in `model-catalog.json`, outside the repository.
Saving settings uses the dashboard's existing optimistic version check and
browser cookie/CSRF/origin protections. Refresh is an authenticated POST; normal
two-second observation polling does not perform discovery or contact providers.

## Automatic switching feasibility

Supported App Server `turn/start` accepts `model` and `effort` overrides for a
specific thread, and those settings become defaults for later turns. CLI
`exec resume EXACT_UUID --model MODEL` can continue a saved conversation with
an explicit model change. Neither surface makes this router an automatic
dispatcher. Automatic switching would require a separately authorized adapter
that owns turn boundaries, revalidates current catalog/eligibility/budgets,
handles pinned choices and failures, and records requested versus reported
models. This change implements recommendation controls only.

Sources verified against the official guide and Codex 0.163.0 source:

- [App Server: model discovery, accounts and turn controls](https://learn.chatgpt.com/docs/app-server)
- [Model-list processor](https://github.com/openai/codex/blob/rust-v0.163.0/codex-rs/app-server/src/request_processors/catalog_processor.rs#L262)
- [Model manager fallback behavior](https://github.com/openai/codex/blob/rust-v0.163.0/codex-rs/models-manager/src/manager.rs#L461)
- [Native account reads and recovery](https://github.com/openai/codex/blob/rust-v0.163.0/codex-rs/app-server/src/request_processors/account_processor/workspace_routing.rs#L164)

## Dashboard labels and mark

**Observed Codex sessions** and **Model-response observations** use the OTel
ledger. Responses may include zero-output setup observations; they do not prove
completed tasks or Codex turns. **Router / collector records**, **Recorded
execution completions**, evaluator/downstream usage and the daily activity
chart retain their separate router/JSON-collector contracts. The copy and
placement changed; counts, deduplication, cost accounting and event contracts
did not. Native ChatGPT plan charges remain unobserved.

The SVG router mark uses a terminal prompt and a branching path. Its visual
reference is the generic `>_` motif visible in the
[official Codex CLI splash](https://github.com/openai/codex/blob/main/.github/codex-cli-splash.png).
It does not reproduce or modify the OpenAI Blossom or claim official ownership.
The dashboard identifies itself as an independent tool. The 40-unit viewBox,
solid contrasting strokes and two endpoints remain readable without color;
the header image is decorative alongside the product name.
