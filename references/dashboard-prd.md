# Local routing dashboard requirements

Status: review iteration above merged PR #3 (`d4eb8b4`). This iteration is not
installed on Peter's working environment. No dashboard merge is authorized.

## Outcome

Ship one persistent localhost dashboard in the public codex-model-routing
package. It aggregates connected, explicitly instrumented sessions and retains a
bounded history. Users can inspect each session, see model/effort choices and
execution evidence, and persist optional-provider settings without launching work.
The dashboard is separate from any infrastructure dashboard or hosted service.

## Required behavior

| Requirement | Implementation / acceptance evidence |
| --- | --- |
| One dashboard for all instrumented sessions | Fixed loopback default port 8765 and shared external state directory; session filter and retained daily totals. |
| Live updates | Browser polls local state every 2 seconds, one request at a time with a 5-second abort deadline; explicit stale/disconnected state. Synthetic HTTP integration exercises updates after collector events. |
| Persistent controls | Separate Decisions/local enablement, endpoint/model/efforts, env-variable names, bounds, preference, optional cost rates and retention. Save uses atomic replacement and version checking; toggles make no provider calls. |
| Distinct evidence | Current saved settings, historical local observations, recommendations, requested execution pair, completion status, override/fallback, session/request IDs, source and observation timestamps. Source timestamp is unknown when unavailable. |
| Honest usage/cost | Evaluator and downstream usage separated; missing usage is unknown, reported zero is zero. Provider-reported counts are distinguished from base/configured-rate estimates; measured billed costs unavailable. Native plan billing is unobserved. |
| Correlation and dedup | Router request UUID shared across Windows preflight/child. Explicit session UUID groups commands. Collector stream UUID identifies one exec invocation; canonical request upsert supports replay and late usage without summing twice. |
| Privacy | Allowlisted scalar metadata only; no prompts, outputs, commands, headers, endpoints, key values or prompt hashes in ledger. Read path reapplies allowlist. Dashboard never reads credentials or internal session stores. |
| Retention | Local SQLite, default 7 days / 500 requests, configurable 1–30 days / 10–5000 requests; prune on writes/reads; disable and explicit clear. Local filesystem backups are outside deletion guarantees. |
| Browser boundary | Bind 127.0.0.1, exact Host/Origin, cross-site rejection, random per-process HttpOnly SameSite cookie plus CSRF header for mutations, no CORS, restrictive CSP, no external assets, size/time/concurrency bounds. |
| Portable package | Python 3.11 standard library, PowerShell/Unix startup paths, no server/runtime provisioning, clean-install completeness checks and offline default. |

## Supported sources and exclusions

- The instrumented `routing_runtime.py` CLI owns router events and provider
  usage observations. Low-level direct helper calls and legacy/private adapters
  remain unobserved unless routed through an explicitly supported adapter.
- `collect_codex_json.py` accepts the documented stdout stream of one
  `codex exec --json` invocation. It never launches Codex, grants permissions or
  reads a session archive. A stream ID must be reused only when replaying that
  same invocation. Thread IDs come from the stream; model/effort annotations are
  marked as operator annotations, not attestation.
- Arbitrary already-open interactive TUI sessions are unobserved. Official OTel
  export exists and is opt-in, but this release does not configure global OTel
  settings or implement an OTLP/app-server receiver.
- A ChatGPT app live feed has not been verified and is unsupported. No browser,
  credential or internal-store scraping is permitted as a substitute.
- Recommendations do not change an active CLI session's model. Native dispatch,
  spending consent and verification remain with the parent harness.

## Release gate

Run the existing routing suite, ledger/collector/config security regressions,
real HTTP synthetic-event tests where sockets are permitted, dependency-free UI
behavior tests, and Windows/Ubuntu Python 3.11/3.12 CI. Report denied local preview
or browser QA explicitly; do not bypass host restrictions. Open a separate PR
against merged main, with no installation or merge of this iteration.
