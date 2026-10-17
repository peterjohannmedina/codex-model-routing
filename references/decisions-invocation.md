# Decisions invocation and evidence

The dashboard saves provider settings. It does not intercept Codex turns or run
the router when a native model responds. OTel records therefore do not prove
that Decisions chose a route. The skill now requires a packaged invocation at
meaningful routing boundaries when Decisions is enabled, using a compact trusted
packet and the parent's safe fallback. Reuse a result during an unchanged phase.

Use the installed `scripts/Invoke-Routing.ps1` on Windows. Omit `-Provider` to
honor saved settings; explicit `-Provider rules` overrides them. The portable
Python and Unix entry points use the same policy. The `routing_decision.py`
command now delegates to that runtime too, honoring configured provider, key
variable, timeout, confidence, native eligibility and evaluator caps. Its Python
provider primitives remain available for callers that already enforce admission.

Older deployment-specific `Invoke-LocalRouting.ps1` launchers can default to rules
and use a separate preflight instead of current configuration. They are not
silently rewritten. Use the versioned packaged launcher for this workflow;
the existing key-entry helper and encrypted credential remain intact.

## Secure credential delivery on Windows

No key is loaded before admission and separate metered-call consent. Preflight,
disabled Decisions, one admitted choice, offline mode, disabled evaluator model,
and unverified hard evaluator caps all prevent loader access. Afterwards:

1. An explicit `-CredentialPath` selects only that store. Missing or invalid
   data produces `local_credential_error`, without falling through to another key.
2. Otherwise prefer an existing configured key environment variable.
3. Otherwise use the existing `$CODEX_HOME/routing/openai-key.dpapi` store.
4. If absent, reuse the known older
   `%LOCALAPPDATA%/CodexModelRouting/openai-key.dpapi` store.

Discovery checks existence only. It never creates, copies, rewrites or migrates
credentials or invokes the human-only key-entry helper. Authorized decryption
delivers the value only in the child environment and clears it from the launch
configuration. Key values and store paths never enter stdout or the ledger.
An absent variable in another executor does not prove the store is absent.
Python/Unix callers use their existing environment rather than decrypting DPAPI.

## Evidence

JSON provenance and sanitized ledger observations include requested/used provider,
`evaluator_status`, `evaluator_attempted`, `evaluator_succeeded`,
`evaluator_fallback`, `evaluator_reason`, and a fixed credential delivery label.
States distinguish disabled, single candidate, blocked, preflight, succeeded and
fallback. Attempts and reported usage remain separate. Arbitrary provider errors
become fixed codes. The dashboard exposes blocked observations and expanded
provider/status/reason/delivery fields. Event totals, OTel/completion semantics
and billing contracts do not change. Recommendations still do not dispatch work
or change the active native model.

## Tiny live validation, separately approved

The public synthetic `assets/decisions-validation.packet.json` offers two native
model/effort choices. Its serialized request is currently 1,446 UTF-8 bytes,
measured offline with a fake transport; this is not a complete billed token count.
The helper enforces a three-second evaluator timeout, one live invocation and
no automatic retry. It never starts downstream work or changes configuration.

Without spending approval, run the admission-only check. It writes no ledger,
loads no key and starts no inference:

```powershell
.\scripts\Test-DecisionsWiring.ps1
```

Only after approval for one separately charged evaluator request:

```powershell
.\scripts\Test-DecisionsWiring.ps1 -AllowApi
```

The live branch first requires two admitted choices and an unblocked saved
provider; otherwise it reports `not_run` before key access. It preserves saved
allowlists, efforts, confidence and hard caps, and the launcher revalidates
immediately before evaluation. The actual invocation records ordinary sanitized
metadata if recording is enabled. Proof requires one attempt, a validated choice,
`used_provider=decisions` and `evaluator_status=succeeded`; usage is recorded when
supplied. Refusal, missing credentials, access errors and timeout remain fallbacks.

The [official Decisions guide](https://developers.openai.com/api/docs/guides/decisions#pricing-and-availability)
lists $0.10 per million input tokens for `gpt-6-luna`, without output/cache charges.
For illustration, 1,000 tokens costs $0.0001 at the base rate; regional and
long-context premiums can apply. Neither that example nor request bytes establish
a hard bill ceiling: complete server formatting/token accounting is unverified.
Configured hard evaluator caps continue to block calls. No live call was made
while developing this fix.
