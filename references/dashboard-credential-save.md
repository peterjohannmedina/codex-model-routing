# Saving provider settings and credentials

The Decisions **API key environment-variable name** field takes `OPENAI_API_KEY`
or another variable name. It does not take an API key. Keep the key in the existing
environment or Windows secure-entry mechanism. Saving dashboard settings does not
store, retrieve, decrypt, check or test a provider key, and makes no provider call.
Do not paste a key into this field, chat, screenshots or error reports.

For a rejected save, correct the named field and save again. The environment name
must start with a letter or underscore and contain only letters, digits and
underscores (at most 128 characters). A blank local-provider name means no local
authentication is configured. Decisions requires a name even while disabled.
Validation also checks confidence (0–1), timeouts (0.05–10 seconds), token/cost
bounds, supported local efforts and a nonsecret URL without credentials, query
strings or fragments. Errors contain fixed hints and field identifiers, never
submitted values. Unknown errors receive a generic safe hint.

Only a **settings changed in another tab** conflict requires reloading saved
settings. Reloading does not repair an invalid environment name or other field.
If the name is already valid, the old generic validation message alone cannot
establish which field caused rejection or whether the credential works.

The optional human-only Windows `scripts/Set-RoutingApiKey.ps1` helper prompts for
hidden input and stores a current-user DPAPI value. Use your existing credential
mechanism and location; this fix does not create, migrate or replace credentials.
Do not run credential-entry helpers through an agent or put a key on a command
line. Configuring credentials is separate from authorizing a metered execution.

**Dashboard connected** means the browser can reach its local ledger. **Enabled ·
settings only** means a saved provider toggle is on. Neither establishes a valid
key, provider availability, an active Codex session or automatic session pickup.
Session rows and provider observations are retained history. This release sees
explicit instrumented runtime commands and opt-in exec JSON streams; an unrelated
already-open TUI has no attached feed. Optional automatic telemetry requires its
own reviewed setup and process restart, and is not enabled by saving settings.

This change was diagnosed from source and synthetic inputs. A synthetic `sk-*`
literal reproduces environment-name rejection; that does not establish what a
user entered. No real key or credential store was inspected or tested.
