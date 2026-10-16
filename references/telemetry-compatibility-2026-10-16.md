# CLI 0.163.0 compatibility and empty feeds

Runtime 2026.10.16.3 separates missing, invalid and unreviewed versions from
unrelated events. Earlier runtimes classified every record lacking the log-record
`app.version` as an unsupported CLI version, even API/process events that have no
session/response usage. The parser now classifies event kinds first. This corrects
a reproduced diagnostic defect; it does not establish why a live producer has sent
no session or response events.

The exact source-reviewed versions remain 0.162.1 and 0.163.0. Within the reviewed
0.162/0.163 series, unlisted patch and numeric alpha/beta/rc builds may match the
existing schema after stricter validation: the required event-level version,
event name, model, UUID and source timestamp must be valid; starts require a known
effort; completed responses require both nonnegative input/output counts and a
valid cached count if supplied. Stable exported timestamps remain mandatory for
response deduplication. Malformed or missing features do not create observations.
New minor/major series still require review. No prerelease prefix is stripped to
pretend an exact build was source-reviewed.

Accepted observations retain `producer_version` and `contract_validation`.
`reviewed_series_schema` means a structural match, with exact build semantics
unverified. It is visibly distinct from `reviewed_version`. Extra payload fields
remain discarded; fixed counters indicate unknown top-level fields or an absent
`event.name` without persisting their names or values.

OpenAI's source at `rust-v0.162.1` and `rust-v0.163.0` has identical Git blobs for
the [session events](https://github.com/openai/codex/blob/rust-v0.163.0/codex-rs/otel/src/events/session_telemetry.rs)
(`53dbe317376ed96b739ed6e69228dd1668ce0c8e`) and
[common fields](https://github.com/openai/codex/blob/rust-v0.163.0/codex-rs/otel/src/events/shared.rs)
(`f962e828c42373d96825a63b08ab2e38af2f6dc5`). The
[provider](https://github.com/openai/codex/blob/rust-v0.163.0/codex-rs/otel/src/provider.rs)
change only suppresses additional trace spans; JSON log export and configured
headers retain the same contract. An independent review also reproduced the old
gate ignoring 0.163.0 fixtures. No inference is needed to test this contract.

The [0.163.0-alpha.10.2 common-fields macro](https://github.com/openai/codex/blob/rust-v0.163.0-alpha.10.2/codex-rs/otel/src/events/shared.rs)
also emits `app.version` on the log record. The provider's resource
`service.version` describes the producer process; it is diagnostic context and
never silently replaces the required event version. OpenTelemetry's tracing bridge
uses an empty instrumentation scope, so a scope version is not a substitute.

## Identify the missing stage

The UI says **listening**, **metadata received**, and **recorded sessions** based
on separate evidence. A browser connection, enabled provider or approved config
never makes a session observed. The receiver's current runtime version and local
state ID identify which process/state a tab is reading. Session totals come only
from retained ledger observations, including the selected session filter.

| Receiver evidence | Interpretation and next check |
| --- | --- |
| No validated batch | Check the producer's host, Codex home, loaded startup config, endpoint and receiver lifetime. A connected tab is not exporter evidence. |
| Unauthorized requests | Review the existing approved endpoint/header capability; never print the capability or replace it automatically. Browser requests are intentionally refused. |
| Invalid batches | Confirm uncompressed OTLP/HTTP JSON, size limits and supported schema. |
| Unsupported-version records | The event version belongs to an unreviewed minor/major series. Review the contract before expanding compatibility. PATH CLI version does not establish desktop-backend version. |
| Missing/invalid-version records | A relevant session/response event lacks a valid event-level version. A resource version alone cannot establish the session contract. |
| Schema-mismatch records | An unlisted build in a reviewed series failed the stricter feature checks. Do not guess missing model, timestamps or counts. |
| Only API/process event classes | Genuine traffic arrived, but it is not evidence of a session start or response usage. A version change cannot manufacture the absent events. |
| Other ignored records | Generic transport events, failed responses and unrelated event kinds do not create session/usage observations. |
| Recording-disabled batches | Export arrived, but local recording was disabled. Those records were deliberately not stored. |
| Storage errors | Inspect state access; raw error text and payloads are never logged. |
| Accepted metadata, missing selected session | Check the session filter, retention and whether accepted metadata describes a different observed session. No active-process inventory is inferred. |

`routing/receiver-status.json` stores fixed counters and event classes, bounded
numeric build labels, installed/running revisions, PID, runtime version,
timestamps and a state-directory fingerprint. Resource/event version labels are
separate. It contains no raw records, arbitrary attribute names, session
IDs, exporter headers, capabilities or user configuration. It resets per receiver
process. Each first failure category is written immediately; repeated invalid/
unauthorized burst updates are limited to once per second. Authenticated UI counters
are current. The file is best-effort and may be
stale after a receiver exits. Its existence alone is not live health.

The browser retains its cookie plus per-tab origin capability. On authorization
failure it stops polling, disables writes and preserves reopening guidance, even
if an older successful request finishes later. Reopen through the installed
shortcut or `bootstrap open` to renew the one-use handoff. Do not restart Codex or
relax Host, Origin, cookie or CSRF checks to repair a stale browser tab.

The routing runtime does not depend on the dashboard process. Ledger write errors
remain best-effort: an offline routing recommendation still succeeds and reports
`ledger.status=unavailable`. Regression coverage exercises failure both before
routing and while publishing its result. No provider request is required.

## Minimum real acceptance

Keep the already approved log-export configuration and privacy scope. Do not
reapply setup or create another capability merely because history is empty.

A supported CLI producer must initialize an actual new/resumed conversation using
the same user config while the receiver is available. `--version` and `--help`
do not initialize one. Use the next normal authorized session/task; do not send a
dummy paid task to populate the dashboard. Export batching is asynchronous and
flushes at shutdown, so an instant new row is not guaranteed.

For an existing desktop/shared app-server, a new UI chat may reuse the existing
exporter: [startup](https://github.com/openai/codex/blob/rust-v0.163.0/codex-rs/app-server/src/lib.rs)
constructs it from loaded configuration, and the
[reloader](https://github.com/openai/codex/blob/rust-v0.163.0/codex-rs/app-server/src/otel_reloader.rs)
reacts to authentication changes rather than ordinary config edits. If that backend
predates setup, save work and use its supported restart lifecycle yourself when
appropriate. The installer never restarts an active session or daemon. Desktop
pickup remains unverified until its actual backend/config and a real accepted
event are observed; cloud chats have no supported feed here.

0.163.0 also changes explicit OTLP **metrics** consent behavior in
[core initialization](https://github.com/openai/codex/blob/rust-v0.163.0/codex-rs/core/src/otel_init.rs).
This repair remains confined to the existing approved log exporter and does not
add a metrics exporter, alter analytics, read transcript archives or change permissions.
