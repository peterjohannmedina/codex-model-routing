# Automatic pickup of new local Codex sessions

This opt-in adapter lets normal new Codex CLI sessions appear in the local
dashboard without piping each invocation through a collector. It uses official
OTel log export, not session files, credentials, transcript paths, private app
databases or a passive attachment to unrelated app-server threads.

It is validated against the installed **Codex CLI 0.162.1** contract. Other
versions are ignored until their fields are verified. A session appears after a
`codex.conversation_starts` batch reaches the receiver. Export is asynchronous;
this is not an immediate process-discovery or heartbeat guarantee. Already-open
processes keep their startup configuration and must be restarted to opt in.

## Review and activation

Installation alone enables nothing. The existing dashboard/ledger works as before.
First generate a read-only plan from the reviewed package:

```powershell
powershell.exe -NoProfile -File .\scripts\Prepare-RoutingTelemetry.ps1
```

```sh
sh scripts/invoke-routing.sh telemetry-setup
```

The plan reports the current config SHA-256 and exact proposed scope. It refuses
any existing `otel` table, including a disabled one: manually reconcile or fan out
an existing exporter in a separately reviewed change. No exporter is silently
replaced. User-level configuration is required; project-local `otel` is ignored
by Codex. A selected user profile can also override user-level telemetry and is
not changed by this tool.

**Obtain explicit approval for this concrete change before applying:** append a
new `[otel]` section to the user-level `config.toml`; export JSON logs only to
`http://127.0.0.1:8765/v1/logs`; set prompt, agent-response and Guardian-response
logging to false; set tool-result output limit to zero; create a private local
receiver capability file and matching exporter header. No provider key, OAuth
grant, network rule, analytics preference, metric/trace exporter, hook, service
or autostart setting is changed. Standard installation never invokes this step.

Only after approval, replace the placeholder with the plan's exact hash:

```powershell
powershell.exe -NoProfile -File .\scripts\Prepare-RoutingTelemetry.ps1 -Apply -ApprovedConfigSha256 APPROVED_CONFIG_SHA256
powershell.exe -NoProfile -File .\scripts\Start-RoutingDashboard.ps1 -OtelTokenFile "$env:USERPROFILE\.codex\routing\otel-receiver.capability" -OpenBrowser
```

```sh
sh scripts/invoke-routing.sh telemetry-setup --apply --approved-config-sha256 APPROVED_CONFIG_SHA256
sh scripts/invoke-routing.sh dashboard --otel-token-file "$HOME/.codex/routing/otel-receiver.capability" --open-browser
```

When `CODEX_HOME` is set, use that directory in place of `~/.codex`. `-CodexHome` /
`--codex-home` and the dashboard's state-directory options support explicit paths.
Use the same port in planning and dashboard startup. Start one receiver/dashboard,
then restart Codex before starting normal new sessions. A shared app-server
daemon may also retain its startup telemetry settings; save work and restart it
through the supported lifecycle before acceptance testing when applicable. This
tool never restarts or interrupts a daemon. No wrapper, hook trust bypass or per-session
collector is required. No model request is made by the setup or dashboard.

Setup preserves the original config bytes in an owner-private backup and checks
the approved hash again before writing. It refuses existing setup files and uses
an exclusive setup lock. The appended configuration is parsed and all non-OTel
values must remain identical. Do not edit config concurrently with applying it.
On Windows, files inherit the user's private directory ACL; on Unix, capability,
receipt and backup files are mode 0600. Never share them or commit them to Git.

To undo, stop the receiver, then use the applied config hash returned by setup:

```sh
python3 -B scripts/routing_otel_setup.py --undo --approved-config-sha256 APPLIED_CONFIG_SHA256
```

PowerShell supports `Prepare-RoutingTelemetry.ps1 -Undo -ApprovedConfigSha256`.
Undo restores exact original bytes only when config and backup hashes still
match. Later edits cause a refusal, requiring a manual reviewed merge. It removes
the owned capability/receipt, retains the backup, and does not clear usage history.
Restart Codex after undo; already-running processes retain their old settings.

## What is observed and counted

| Native event | Stored metadata | Meaning |
| --- | --- | --- |
| `codex.conversation_starts` | Conversation UUID, model, startup reasoning effort, source timestamp when present | Observed configuration; one retained row per conversation, enriched on resume |
| `codex.sse_event` with `event.kind=response.completed` and usage fields | Conversation UUID, response metadata model/effort, reported input/output/cached input counts | A model-response usage observation; not a completed Codex turn |
| Generic SSE notifications, errors, tool/prompt/response events, unknown versions | None | Ignored; no text or inferred execution status is retained |

Some counts arrive as decimal strings. Missing/invalid counts stay unknown;
reported zero stays zero. The source's `tool_token_count` is total tokens, not
tool tokens, and is intentionally not imported. No inferred billing or native
subscription cost is added. Provider rerouting/actual internal reasoning are not
attested by a metadata model/effort field.

Response events lack a response or turn ID. Their derived observation IDs use the
conversation UUID and the exported source or SDK-observed nanosecond timestamp.
The original timestamp survives batch replay, so repeats upsert and late partial
usage enriches one row. This is **best-effort deduplication**, not exactly-once
correlation: equal timestamps can collapse distinct observations; newly timestamped
re-emissions can duplicate. Missing stable timestamps are rejected. No prompt or
content fingerprint is calculated.

OTel usage is displayed separately from router request/exec-turn totals. Both
feeds can describe the same work and must not be summed. Session-start rows do
not fabricate requests or completed executions. The session selector includes
retained OTel-only conversations even before a response arrives. Model/effort
changes are visible only when exported; a completed model response before an
interrupt does not prove completion of the user turn.

The receiver status distinguishes locally enabled ingestion, unverified exporter
configuration, and a last accepted batch. It cannot prove every open session is
connected. If it is down or a batch is lost, there is no archive backfill. Dashboard
polling is every two seconds after a batch is retained. Recording disable, shared
retention (7 days / 500 observations by default), and clear apply to all feeds.
Disabling recording does not remove Codex's exporter; undo is the exporter opt-out.

## Privacy and transport boundary

`log_user_prompt=false` is not complete native-log redaction. Codex can still emit
account email/IDs, tool arguments and errors, even with tool output limited to
zero. These can transit bounded local request memory. The receiver allowlists
metadata before any ledger write and drops all bodies, resource identities,
paths, prompts, agent text, tool data and freeform errors. It never records raw
requests, headers, traces or debug payloads. Error responses use fixed codes.

The `/v1/logs` endpoint is disabled unless an explicit capability file is supplied
at startup. It binds only on the existing 127.0.0.1 dashboard port, requires exact
Host and an independent local capability, rejects all browser Origin/Fetch headers,
compression, chunked bodies and oversized batches. JSON is bounded to 1 MiB,
512 records and fixed resource/scope/attribute limits. Existing request timeout
and concurrency bounds still apply. Browser authorization grants no ingest access;
the exporter capability grants no dashboard read/config access. There is no CORS,
public port, external forwarding, tunnel or firewall change. This is a per-user
local boundary, not isolation from other processes running as that same user.

## Supported surfaces and evidence

Normal new local **Codex CLI 0.162.1** sessions using the approved user config are
the acceptance target. Codex Desktop, IDE and ChatGPT local Work surfaces may use
different versions/configuration; they remain unverified until their actual
exports are validated. No general supported feed for ordinary personal cloud
ChatGPT chats was established. Those chats remain explicitly unsupported.

Official sources checked 2026-10-15:

- [OTel configuration and emission](https://learn.chatgpt.com/docs/config-file/config-advanced#observability-and-telemetry)
- [User-level telemetry and profile precedence](https://learn.chatgpt.com/docs/config-file/config-reference)
- [Config JSON schema](https://learn.chatgpt.com/docs/config-schema.json)
- [App-server notification subscription boundary](https://learn.chatgpt.com/docs/app-server)
- [Hooks and their trust/surface limits](https://learn.chatgpt.com/docs/hooks): optional hooks can register startup metadata, but are not required or installed here; transcript paths are not read.

Exact CLI source: OpenAI `rust-v0.162.1`, commit
`092d3acd6bec3e3a14bdc7e7a2810ab628ab759d`:
[events](https://github.com/openai/codex/blob/092d3acd6bec3e3a14bdc7e7a2810ab628ab759d/codex-rs/otel/src/events/session_telemetry.rs),
[common fields](https://github.com/openai/codex/blob/092d3acd6bec3e3a14bdc7e7a2810ab628ab759d/codex-rs/otel/src/events/shared.rs),
[JSON exporter/bridge](https://github.com/openai/codex/blob/092d3acd6bec3e3a14bdc7e7a2810ab628ab759d/codex-rs/otel/src/provider.rs),
[schema](https://github.com/openai/codex/blob/092d3acd6bec3e3a14bdc7e7a2810ab628ab759d/codex-rs/core/config.schema.json).
The dependency's [OpenTelemetry 0.31 tracing bridge](https://github.com/open-telemetry/opentelemetry-rust/blob/v0.31.0/opentelemetry-appender-tracing/src/layer.rs)
does not set event time; the receiver also accepts the SDK-observed timestamp.
Installed app-server JSON schemas were generated read-only to confirm its methods;
no live thread was started or subscribed. Fixture/HTTP tests make no model calls.
Real acceptance still requires approval for the exact user-level activation,
an allowed local receiver/browser, and a separately authorized real Codex task.
