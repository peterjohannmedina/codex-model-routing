# Dashboard verification — 2026-10-15

Base: merged PR #3 `d4eb8b47983ed6353f99c7b16410d8c2095ec769`.
Worktree/branch: `codex-routing-dashboard` / `feat/localhost-routing-dashboard`.
The dashboard is a separate review iteration, not an installed update.

## Evidence

- 70 Python tests pass locally on Windows/Python 3.12, with one Unix-only and
  two explicitly disabled socket integration tests skipped. The routing,
  private-credential fixture, admission, install and provider matrix regressions
  remain included. All new test data/credentials are synthetic.
- Dependency-free Node UI behavior tests pass: dynamic rendering and session
  scope, recommendation versus completion, unknown usage/cost, bounded polling,
  unsaved form preservation, save-version handling, no provider request on save,
  disconnected/stale feedback, recovery and explicit history clearing.
- Local browser authorization uses a private ephemeral launch file and a
  single-use expiring nonce; public root grants no cookie/data. Offline tests
  cover replay/expiry; HTTP tests cover authenticated bootstrap and file cleanup;
  fake-DOM tests cover nonce handoff and removal from browser history. API reads
  also require the tab's capability header; a host-scoped cookie alone is denied.
- Independent review regressions first failed at `799ef9c`, then passed after
  fixes: immediate partial-replay session/annotation assertions before full
  replay, late thread-identity enrichment/conflict rejection, authorized anchor
  refresh, failed-bootstrap recovery with existing capability, and delayed saves
  preserving newer edits and their next-save version. Both Node suites run in CI.
- A follow-up delayed-GET regression reproduced stale form/version restoration
  after successful POST. Successful save now invalidates polls that began during
  the pending write as well as polls that began before it.
- Both shell scripts pass Git Bash syntax checks. `git diff --check` passes.
- CI requires real HTTP tests (socket denial becomes a failure, not a skip).
  Read the dashboard PR's exact-head Windows/Ubuntu × Python 3.11/3.12 results.
  HTTP tests exercise cookie/session, Host/Origin/CSRF, size/path boundaries,
  live synthetic stream updates, session drilldown and late usage without a
  provider or paid request. Unix clean installation also runs its collector.

## Local preview limitation

The host's sandbox denies localhost connections with `WinError 10013`. Binding
the test server succeeded, but connecting to it was denied. The failure was not
retried outside that boundary. Local full suites explicitly disable only those
two socket tests. No live dashboard/browser preview or visual browser QA is
claimed here; DOM/fetch behavior is tested without sockets, and CI verifies the
real HTTP event path. No server is left running on JJP.

## Source contract and costs

Installed CLI `0.162.1` help confirms `exec --json`. Official
[non-interactive documentation](https://learn.chatgpt.com/docs/non-interactive-mode)
confirms the thread/turn/item and usage stream. Official
[advanced configuration](https://learn.chatgpt.com/docs/config-file/config-advanced)
documents opt-in OTel; this implementation neither enables it nor claims an
already-open TUI/app-server attachment. ChatGPT app live export remains unverified
and unsupported. No session archives, credentials or internal stores were read.

The Decisions [response usage contract](https://developers.openai.com/api/reference/resources/decisions/methods/create)
and [base-rate guide](https://developers.openai.com/api/docs/guides/decisions)
were checked against official sources. Estimates are dated and incomplete for
billing; hard preflight spend/token caps remain fail-closed. No metered call,
real inference, real credential read, new OAuth grant or global telemetry setting
change occurred in this iteration.

## Working installation boundary

JJP remains on approved merged PR #3 with its personal profiles/private helpers.
Dashboard code, sample config and tests are confined to the separate worktree.
Publishing this branch does not install or merge it. A live provider test would
require separate endpoint/data/spend authorization and existing account access;
that is not needed for the synthetic dashboard/HTTP test coverage.
