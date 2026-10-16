# CLI 0.163.0 compatibility and empty feeds

Runtime 2026.10.16.1 accepted only `app.version=0.162.1`. The installed CLI
subsequently reported 0.163.0, so otherwise valid new-version records were ignored.
Runtime 2026.10.16.2 accepts exactly 0.162.1 and 0.163.0, preserves the metadata
allowlist, and exposes reasons for ignored records. Unknown future versions still
fail closed. This is a reproduced parser defect; it does not prove why any one
live producer has sent no events.

OpenAI's source at `rust-v0.162.1` and `rust-v0.163.0` has identical Git blobs for
the [session events](https://github.com/openai/codex/blob/rust-v0.163.0/codex-rs/otel/src/events/session_telemetry.rs)
(`53dbe317376ed96b739ed6e69228dd1668ce0c8e`) and
[common fields](https://github.com/openai/codex/blob/rust-v0.163.0/codex-rs/otel/src/events/shared.rs)
(`f962e828c42373d96825a63b08ab2e38af2f6dc5`). The
[provider](https://github.com/openai/codex/blob/rust-v0.163.0/codex-rs/otel/src/provider.rs)
change only suppresses additional trace spans; JSON log export and configured
headers retain the same contract. An independent review also reproduced the old
gate ignoring 0.163.0 fixtures. No inference is needed to test this contract.

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
| Unsupported-version records | Verify the producer's actual backend version before reviewing another exact contract. PATH CLI version does not establish desktop-backend version. |
| Other ignored records | Generic transport events, failed responses and unrelated event kinds do not create session/usage observations. |
| Recording-disabled batches | Export arrived, but local recording was disabled. Those records were deliberately not stored. |
| Storage errors | Inspect state access; raw error text and payloads are never logged. |
| Accepted metadata, missing selected session | Check the session filter, retention and whether accepted metadata describes a different observed session. No active-process inventory is inferred. |

`routing/receiver-status.json` stores only fixed counters, runtime version,
timestamps and a state-directory fingerprint. It contains no raw records, session
IDs, exporter headers, capabilities or user configuration. It resets per receiver
process. Each first failure category is written immediately; repeated invalid/
unauthorized burst updates are limited to once per second. Authenticated UI counters
are current. The file is best-effort and may be
stale after a receiver exits. Its existence alone is not live health.

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
