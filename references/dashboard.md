# Local dashboard and usage ledger

Start one dashboard and leave it running while supported instrumented sessions
write to the same state directory. The dashboard polls its local ledger every
2 seconds. It never contacts a provider, checks paid health, starts inference or
switches an active CLI model. Saving provider enablement does not grant execution
or spending permission.

## Start

From a reviewed source checkout or installed skill directory:

```powershell
powershell.exe -NoProfile -File .\scripts\Start-RoutingDashboard.ps1 -OpenBrowser
```

```sh
sh scripts/invoke-routing.sh dashboard --open-browser
# Equivalent: python3 -B scripts/routing_dashboard.py
```

The optional browser flag opens a private one-use launch file that redirects to
`http://127.0.0.1:8765` and authorizes that browser. Without the flag, open the
private file path printed in the terminal within five minutes. No token value
is printed. Root HTML is public but grants no session or data access on its own.
The file is deleted after successful authorization or normal server shutdown;
its nonce expires and is single-use. Restart if it expires or another browser
needs authorization. The browser removes the temporary fragment from history.
Use the same server process for all instrumented sessions and reuse the authorized
tab. Reloading preserves its tab-scoped session capability; a fresh browser/tab
needs bootstrap authorization. Restarting the view does not stop disk collectors.
A second server on that port fails instead of choosing another
dashboard automatically. Stop with Ctrl+C. No autostart service is installed.
`--port` / `-Port` and `--state-dir` / `-StateDir` are explicit overrides.
The server always binds 127.0.0.1; there is no LAN host option or remote exposure.
Changing port is not a way to bypass an environment's socket restrictions.

Python 3.11+ is required; nothing is installed automatically. Windows startup
uses the existing bundled/runtime/PATH discovery and skips Store aliases.
`CODEX_ROUTING_PYTHON` or `-PythonPath` selects an existing interpreter.

## Persistent state and configuration

Defaults are `$CODEX_HOME/routing/` or `~/.codex/routing/`:

- `config.json`: nonsecret provider settings plus `observability` settings.
- `usage.sqlite3`: bounded metadata for instrumented requests.
- `.dashboard-launch-*.html`: ephemeral browser-bootstrap file, never a provider key.

The dashboard refuses state directories inside a Git repository. Installation
copies the dashboard and config example but starts no server and creates no
configuration, ledger or credentials. Existing user config, personal profiles,
private launchers and encrypted values are not migrated or changed by this PR.

Save controls use a config version to reject conflicting edits from other tabs.
Live polling preserves unsaved edits. Edits made while a save is pending remain
unsaved after that earlier snapshot is stored; a response never clears a newer
edit revision. The saved snapshot's version supports the next save, while stale
poll responses cannot refill the form. Reload saved settings after a conflict;
the server writes the validated config atomically. The environment-variable
fields accept **names only**. There is no key-value form, credential endpoint or
credential-presence probe. URL credentials, query strings and fragments are
rejected. Treat model IDs and endpoint paths as nonsecret configuration.
Field-specific errors offer fixed correction hints; only version conflicts ask
for a reload. See [credential-save troubleshooting](dashboard-credential-save.md).
The connection label reports browser access to the ledger; session rows are
retained observations and do not prove an active feed.

An enabled provider is different from an observed provider. Availability shown
in the page is a timestamped historical routing observation. It is not an active
health or capacity check. Require-local, overrides, caps and separate inference
consent still apply at actual execution. Provider toggles have no execution side
effects and do not interrupt a request already in progress.

## Router-owned events

Use the portable runtime from this version. Native baseline is still available
without any provider:

```sh
python3 -B scripts/routing_runtime.py assets/routing-packet.example.json --offline \
  --session-id 11111111-1111-4111-8111-111111111111
```

The PowerShell launcher accepts `-SessionId`, `-RequestId`, and `-NoLedger`.
Each invocation generates a request UUID unless supplied; Windows preflight and
child share it. Reuse a request UUID only for stages/replay of the same invocation.
Set the documented `CODEX_ROUTING_SESSION_ID` in a terminal to a
UUID to group that terminal's explicit router commands. Without a session UUID,
commands appear under **Unassigned router commands**. Session IDs are labels for
correlation, not credentials, auto-discovery or proof of an attached CLI.

The ledger defaults on for this instrumented runtime only. Disable it with
`observability.enabled: false` or `--no-ledger` / `-NoLedger`. New commands read
the setting; an in-flight runtime may finish its metadata update. Recording
failure never blocks routing and is reported as unavailable in the CLI result.
No external telemetry is exported. Direct `routing_decision.py`, an already
installed older runtime, private launchers and legacy adapters do not silently
become instrumented.

## Opt-in Codex exec stream

The installed CLI 0.162.1 exposes `codex exec --json`. Official
[non-interactive documentation](https://learn.chatgpt.com/docs/non-interactive-mode)
describes thread/turn/item events and `turn.completed.usage`. The collector reads
stdin, retains only allowlisted metadata, and never launches Codex itself.

For a task you have already authorized, connect **one exec invocation** using a
fresh stream UUID:

```powershell
$RoutingPython = & .\scripts\Resolve-RoutingPython.ps1
$RoutingStreamId = [Guid]::NewGuid().ToString()
codex exec --json 'YOUR ALREADY AUTHORIZED TASK' | & $RoutingPython -B .\scripts\collect_codex_json.py --stream-id $RoutingStreamId
```

```sh
routing_stream_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
codex exec --json 'YOUR ALREADY AUTHORIZED TASK' | sh scripts/invoke-routing.sh collect-codex --stream-id "$routing_stream_id"
```

The pipeline consumes Codex's stdout; the collector prints only a metadata
summary at EOF. It does not retain or echo answers, commands, reasoning or tool
output. Use Codex's supported output options separately when you deliberately
need the task result. Collector exit status does not establish Codex success;
inspect the completion/failure evidence and the originating command's status.

One stream ID represents one invocation/turn. Reuse it only to replay that same
stream: the canonical request upserts instead of summing twice. Late usage fills
the existing request, including reported zero. An observed thread ID takes
precedence over the stream fallback, including partial replays that omit
`thread.started`; absent model/effort annotations preserve existing annotations.
A conflicting authoritative thread ID for the same invocation is rejected.
Deduplication applies to retained requests; replay after pruning creates a new
retained entry. Multiple stream IDs can aggregate
under the same source thread ID. A source thread change within one stream is
rejected. Model and effort are often absent from this stream; optional `--model`
and `--effort` are explicitly labeled operator annotations. They do not change
the CLI model or attest to actual model selection.

The collector observes metadata only when the stream emits it. It rechecks the
ledger enablement/retention settings on incoming events and EOF. A normal EOF
marks the stream closed; no completion event means execution/usage remain
unobserved. A killed collector cannot emit its closing update: inspect the last
observation time rather than treating an old open flag as a heartbeat.

## Interactive CLI and ChatGPT app limits

An arbitrary already-open TUI has no feed connected by default.
Official [advanced configuration](https://learn.chatgpt.com/docs/config-file/config-advanced)
documents opt-in OTel log/metric export, including model/conversation metadata,
API/stream/tool events and a prompt-redaction setting. The optional
[automatic session adapter](automatic-telemetry.md) accepts approved local OTel
exports from reviewed CLI 0.162.1 and 0.163.0 processes, with a metadata allowlist and separate
response-usage totals. It is disabled by default. Installation does not edit
`config.toml` or enable OTel; a separate exact-hash approval/apply step is needed.
It never attaches unrelated app-server threads or reads session/internal archives.
No verified official live export feed for the ChatGPT app was established;
the page therefore labels it unsupported. An open app or terminal is not proof
of observed usage.

## Usage, prices and completeness

Router results distinguish recommendations from actual bounded local execution.
The ledger separates the recommended pair from the local request's execution
pair, so a failed local POST followed by a native recommendation is not counted
as native execution. Only observed completion status increments completions.
Codex exec usage belongs to downstream execution; it is not evaluator usage.

Decisions response usage is documented in the official
[Decisions reference](https://developers.openai.com/api/reference/resources/decisions/methods/create).
Counts come from provider reports, not a local tokenizer or invoice. Missing,
invalid or timed-out usage is **unknown**, and a reported zero is **zero**.
Captured retries/streams are limited to this adapter's actual observations; an
unobserved session contributes neither fabricated zero nor an invented total.
There is no complete preflight token counter and hard evaluator caps still block.

The evaluator estimate applies the dated `$0.10 / 1M` base rate to known reported
input from the [Decisions guide](https://developers.openai.com/api/docs/guides/decisions),
verified 2026-10-15. It is not a billing total: cache treatment, regional premiums,
long-context multipliers and adjustments are not reconciled. Optional local
input/output rates apply to known local usage; blank rates mean unknown, not
free. Changing rates reprices retained history. Native plan/API costs and measured
billed cost remain unavailable. Totals show known usage and the number of
requests with unknown usage separately.

Daily buckets use first local observation time (UTC) and retained request IDs.
Late usage enriches the original bucket. Source timestamps remain unavailable
unless explicitly present in a supported event; observation time is not claimed
as the provider's original event time. History is bounded, not an all-time bill.

## Privacy and browser boundary

The ledger keeps only source/session/request IDs, bounded model/effort labels,
override/fallback/error codes, status, counts and timestamps. Credential-like
labels are redacted. Prompts, outputs, commands, endpoints, headers, key values
and prompt hashes are excluded; the read path reapplies the allowlist. No raw
stream archive or ingestion endpoint is exposed to the browser.

Default retention is 7 days / 500 requests; controls allow 1–30 days / 10–5000.
Pruning runs on reads and writes. Clear deletes retained rows and vacuums SQLite
with secure-delete enabled. This does not promise erasure from filesystem
snapshots, backups or forensic storage. Unix state is owner-only; Windows uses
the current user's inherited directory ACL. Use a private per-user state
directory; a custom shared directory weakens bootstrap-file privacy. This is a
local-user boundary, not protection against processes already running as that user.

Exact Host/Origin checks reject DNS rebinding and cross-site mutations. A private
five-minute, single-use bootstrap file authorizes the browser; opening public root
HTML alone yields no cookie. A random per-process HttpOnly SameSite browser cookie
and a tab-scoped capability in sessionStorage gate all API reads and writes.
Cookie possession alone cannot retrieve that capability, including from another
localhost port. The bootstrap travels in a URL
`#authorize=` fragment, not an HTTP query or access log; the browser removes it
immediately. Navigation anchors such as `#providers` and `#activity` remain
navigation anchors and reuse the tab's stored authorization on refresh.
Other control tokens remain in process/browser session state. These are not provider
credentials. There is no CORS allowance. CSP blocks external
assets/frames and unsafe script; request bytes, read time and concurrency are
bounded. No state file or credential path is served. Do not expose this server
through a reverse proxy or public tunnel.
