# Automatic telemetry verification — 2026-10-15

## Independent-review repairs — 2026-10-16

The original setup review reproduced three preservation/security bugs; this PR
now includes regressions and fixes for all three:

- Refuse to embed a local capability in a broadly readable config. Unix rejects
  0644 config files without changing their modes. Windows verifies owner and
  DACL privacy read-only, with SYSTEM/administrators as privileged exceptions;
  unknown/unavailable ACL checks fail closed. Empty temporary files are checked
  before receiving secret bytes, and replacement owner/group/DACL must match.
  No existing permissions are automatically repaired or broadened.
- Compare the second baseline read to the exact approved hash, as well as every
  pre-write read. A synthetic edit between plan and baseline now rejects instead
  of applying an unapproved baseline. No capability/receipt/backup is created for
  that rejected baseline.
- Refuse symlink/reparse config targets during plan, reads, atomic replacement
  and undo. Synthetic symlinks remain links and their managed targets remain
  unchanged. Windows reparse flags are also exercised without requiring link
  creation privileges.

Windows ACL tests alter only guarded disposable fixture directories and use
access-only DACL operations, requiring no audit/security privilege. A second
fixture grants Everyone read access to its dummy config and verifies refusal.
Read-only production probes return fixed verdicts without identity/ACL contents.
Microsoft documents [OWNER RIGHTS](https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/understand-security-identifiers)
as the current object's owner; it is accepted only after the owner is verified.
The earlier 86-test evidence below remains historical; final post-fix CI is linked
from the PR description. No live JJP config, ACL, installed package or telemetry
activation was changed during these repairs.

## Initial implementation evidence

Acceptance target: installed JJP Codex CLI **0.162.1**, verified with `--version`
and read-only help/schema generation. The official source tag resolves to
`092d3acd6bec3e3a14bdc7e7a2810ab628ab759d`. Its OTel JSON exporter and
OpenTelemetry 0.31 tracing bridge were inspected; source links and semantics are
in [the architecture/activation guide](automatic-telemetry.md).

Implementation source `2a83a6d6fc496903f539ef3e5566cb7fc760a1df` is frozen for
browser capture. At PR head `1b24c0ebd7f24d83b301bc85954f8db5faed7f48`:

- [Windows/Ubuntu × Python 3.11/3.12 CI](https://github.com/peterjohannmedina/codex-model-routing/actions/runs/38825031673)
  passes 86 tests per job. Windows skips one Unix-only test; Ubuntu skips seven
  Windows-only tests. All four real HTTP tests ran successfully, including native
  OTel capability/Host/Origin/body guards, metadata ingestion/browser session
  visibility and recording disable. CI fails on unavailable sockets.
- Both Node suites pass, including configuration-save regressions and separate
  OTel display/unchanged request totals. Unix clean install checks package
  completeness, private-capability exclusion and read-only setup planning.
- [Actual Chromium capture](https://github.com/peterjohannmedina/codex-model-routing/actions/runs/38825031591)
  passes using the existing synthetic fixture. The updated overview with disabled
  receiver/zero OTel observations was visually inspected. All eight captured
  source files match pinned Git blobs. No provider or external browser request
  occurs; only PNGs/provenance are uploaded.
- Local Windows/Python 3.12: 86 tests pass, five skips (four denied socket tests,
  one Unix-only). Node suites, shell syntax and whitespace checks pass. Local
  socket restrictions were retained, without outside-sandbox HTTP retries.

Fixture tests cover startup and resumed metadata, model/effort changes when
reported, source and SDK-observed timestamps, zero/unknown usage, generic/error/
interrupt events, unsupported versions, replay/late usage, retention/disable/clear,
pre-persistence redaction, duplicate/invalid/bounded JSON, exact-hash setup,
exclusive setup lock, byte-preserving backup/undo and later-edit/corrupt-backup
refusal. They are synthetic contract tests, not a claim that a real new session
has been observed.

JJP remains installed at merged PR #4, `ea8af4f42b2302da38bff8f316fcc7852da335c7`.
All 67 public files, seven profiles, existing settings/global instructions and
private helpers were reverified unchanged; the real ledger remains empty and the
separate eight-event demo is preserved. A read-only activation plan is compatible
with the current user config. No capability file or exporter has been created;
no global config, hook trust, daemon lifecycle, network rule or service changed.
No private session/archive/credential store or real model/provider call was used.

Remaining acceptance requires separate exact approval for the user-level OTel
append and private local capability, review/installation of this PR, an allowed
local receiver, appropriate Codex/shared-daemon restart after saving work, and a
separately authorized real task. Check normal startup, new session, resume,
model/effort changes, interrupt and receiver-down behavior on the actual surface.
Ordinary cloud ChatGPT chat telemetry and other unverified app versions are not
claimed supported. Response/turn correlation and export completeness remain
limited as documented; reported usage is not an invoice.
