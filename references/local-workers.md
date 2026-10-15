# Portable optional providers

## Recommended design and evidence

The default is native Codex model/effort routing with neither extra provider.
Three approaches were considered: keep named deployment profiles as defaults,
provide one generic configured local adapter, or require an external orchestration
service. The generic adapter preserves local inference with the least setup and
no additional orchestrator. Named profiles remain opt-in compatibility examples.
This is an architecture choice, not a measured claim about model quality or cost.

Before this iteration, native routing and Decisions error fallback already worked
without local services. Sharing was hindered by two named local adapters in
admission, default registration of deployment profiles, and missing packaged
local launchers. The new runtime keeps admission independent of execution and
ships its complete launcher package. The installer also writes the actual Codex
global instruction path, `~/.codex/AGENTS.md`.

## Configuration

Python 3.11+ standard library only. Copy
[`assets/routing-config.example.json`](../assets/routing-config.example.json) to
`$CODEX_HOME/routing/config.json` (default `~/.codex/routing/config.json`), or pass
`--config PATH` / `-ConfigPath PATH`. Configuration is external to the package;
installation neither creates nor overwrites it. Unknown fields and invalid hard
settings fail before a model request. Credentials are environment-variable names,
never literal key values in JSON.

Both providers start disabled. A minimal baseline config is:

```json
{"schema_version": 1}
```

To configure a local OpenAI-compatible Chat Completions service, supply your own
endpoint and exact model. No server/model name is assumed:

```json
{
  "schema_version": 1,
  "local": {
    "enabled": true,
    "base_url": "http://127.0.0.1:8000/v1",
    "model": "YOUR_LOCAL_MODEL",
    "efforts": ["default"],
    "prefer_when_eligible": true
  },
  "decisions": {"enabled": false}
}
```

This is an example to edit, not an active default. Loopback is accepted; another
host requires explicit `allow_remote: true`. Embedded URL credentials, queries,
fragments and redirects are rejected. Local requests bypass ambient HTTP proxies.
An optional `api_key_env` supplies local-server authentication. Know whether your
configured gateway itself incurs charges; “local” identifies the adapter, not a
guarantee of free inference.

`efforts: ["default"]` means leave the server's effort unset. Only list other
efforts when the server actually accepts the `reasoning_effort` parameter with
those values. The runtime validates offered local pairs against this config.
Do not confuse a local model's controls with the native Codex catalog.

For an eligible bounded worker, add a candidate to the trusted routing packet:

```json
{"id":"local_task","action":"delegate","adapter":"local",
 "model":"YOUR_LOCAL_MODEL","effort":"default"}
```

Set `local_work_eligible: true` only after suitability/data-handling review. The
runtime makes one bounded `GET /models` to check advertisement, with no completion
probe or retries. Advertisement is not proof of scheduler capacity or successful
inference; the parent must recheck live capacity when its deployment exposes it.
Disabled, unconfigured, missing-key, unavailable-model, invalid-auth, malformed
and unreachable local routes are excluded while native routing continues.
`require_local: true` instead rejects unsatisfied requests. Trusted overrides,
conservation and execution ceilings remain hard filters.

## Entrypoints and execution

Windows:

```powershell
powershell.exe -NoProfile -File .\scripts\Invoke-Routing.ps1 -PacketPath PACKET -Offline
```

Unix:

```sh
sh scripts/invoke-routing.sh PACKET --offline
```

The PowerShell launcher uses `-PythonPath`, `CODEX_ROUTING_PYTHON`, an existing
bundled Codex Python, or an installed Python 3.11+ interpreter, and skips Windows
Store aliases. The Unix launcher uses `CODEX_ROUTING_PYTHON` or python3/python.
Neither installs a runtime or changes execution policy. The Python entrypoint is
`scripts/routing_runtime.py`. `--offline` forbids provider requests and inference;
`--preflight-only` performs admission and configured local advertisement checks,
but never loads a Decisions credential or calls Decisions. It may use the local
server's configured authentication environment variable for that read-only probe.

Recommendations do not execute work. Explicit local execution is separate:

```sh
python3 scripts/routing_runtime.py PACKET --config CONFIG --execute-local --allow-local-inference
```

The PowerShell equivalents are `-ExecuteLocal -AllowLocalInference`. This chooses
an admitted configured local pair and sends one bounded text-only
`POST /chat/completions`, no tools, streaming, retries or automatic delegation.
`max_output_tokens` defaults to 512 (range 1–4096). The request sends `max_tokens`
and, only for a configured non-default effort, `reasoning_effort`. Response bytes,
request bytes and wait time are bounded. Token/cost ceilings on the whole task
block this executor when complete execution accounting cannot be verified;
`max_tokens` is only an output limit. Latency ceilings bound waiting, not a promise
of remote cancellation. Model output is untrusted text for the parent to validate.

Execution failure returns an admissible native recommendation only when allowed;
it never executes native inference or authorizes spending. Require-local or a
binding local override stops if the required route fails. Native model/effort
application still belongs to the parent and supported Codex controls. There is
no automatic native dispatcher, JEV contract or deployment step.

## Optional Decisions and credentials

Enable `decisions.enabled` or pass `--provider decisions` / `-Provider decisions`.
A network request additionally requires explicit `--allow-api` / `-AllowApi` and
an existing key from the configured `api_key_env` (default `OPENAI_API_KEY`).
No key, network error, refusal, timeout or invalid output retains the safe route;
none changes native permissions or starts paid native fallback work.

The Windows launcher optionally loads a user-created DPAPI value at
`$CODEX_HOME/routing/openai-key.dpapi`; use `-CredentialPath` for an existing
external loader location. Otherwise the admitted child may use the configured
environment key. The key is passed only in the child's environment, never command
arguments, stdout, files in the package, or a global environment setting.
`scripts/Set-RoutingApiKey.ps1` is an optional **human-only** hidden-entry helper;
it rejects storage inside repositories. Installation does not run it. Unix users
use their existing secure environment/credential mechanism. No credentials were
created or real credentials accessed during release testing.

Admission, exact single-candidate resolution and hard evaluator cap checks occur
before the Windows DPAPI loader. There is no verified complete Decisions token
counter. `max_input_tokens` / `-MaxDecisionInputTokens` and `max_cost_usd` /
`-MaxDecisionCostUsd` therefore block a network-required decision rather than
treating bytes or Responses token counts as proof. A single admissible candidate
resolves locally without a key or request. See
[decision-providers.md](decision-providers.md) for contract and pricing boundaries.

## Compatibility and release state

Native profile names and the lower-level `routing_decision.py` interface remain.
The generic runtime manages `adapter: local` from configuration. It deliberately
does not trust legacy readiness flags as permission to contact an arbitrary
service. Existing named custom agents remain usable through their established
parent-controlled workflow. Legacy scripts and opt-in templates are documented
in [legacy-local-workers.md](legacy-local-workers.md). The routing prompt reports
status by default and supports explicit legacy share-target requests separately.
There is no generic local-share target.

Publishing changes does not update an existing installation. Install a reviewed
revision explicitly when ready. See the dated verification record for the
release/installed revision distinction and the scope of offline evidence.
