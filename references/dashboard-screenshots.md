# Dashboard screenshots

These are actual browser screenshots of the initial dashboard release, rendered by
official Playwright with Chromium on Ubuntu GitHub Actions. All activity and
configuration values come from the committed [synthetic fixture](../tests/fixtures/dashboard-screenshot.json).
They contain two dummy session UUIDs and eight dummy request UUIDs, no real
account activity, prompts, outputs, private paths or credential values. Credential
environment variable names are examples only. Costs are illustrative estimates;
measured billed cost remains unavailable.

| View | Description |
| --- | --- |
| [Overview](../docs/images/dashboard-overview.png) | Eight requests, four completed executions, separate evaluator/downstream usage, retained activity and labeled estimates |
| [Providers](../docs/images/dashboard-providers.png) | Independent saved provider settings, historical observations, retention controls and environment variable names |
| [Activity](../docs/images/dashboard-activity.png) | Synthetic request history and an expanded local execution with correlation and usage evidence |

The captured HTML, CSS, JavaScript and four Python backend/routing files matched
commit `f1423124e5cca1012ef7d64e6a44f2bc84fa703a`; the fixture helper verifies
their pinned Git blob IDs before capture. No production UI or backend changes
were made for the images. The [machine-readable provenance](../docs/images/dashboard-provenance.json)
records exact capture commit, file/image SHA-256 hashes, browser/version,
dimensions, locale and time zone. The checked-in images were captured from GitHub's
temporary PR merge `042f7281709fe2413b8fd1795104449f4f6aaaac` for branch head
`f79192c136774eb19e481aadf4d801b34b5843a5` by
[this CI run](https://github.com/peterjohannmedina/codex-model-routing/actions/runs/38820830785).
Subsequent workflow runs explicitly check out the PR head commit. The automatic
telemetry iteration adds a new panel; current CI captures verify its frozen
source `2a83a6d6fc496903f539ef3e5566cb7fc760a1df`, including the new OTel adapter.
The checked-in PNGs and their original provenance remain historical examples.

The real backend serves temporary synthetic SQLite/config state on loopback to
a fresh browser context. Only the displayed observation clock and fixture dates
are fixed to October 15, 2026; retention uses the capture's current time so later
runs retain the demo records. Browser requests are restricted to the dashboard
origin and required read/auth routes. Provider transports are patched to fail if
called, and capture asserts zero provider calls, external browser requests and
JavaScript errors. Private bootstrap state remains in memory and is never
included in artifacts. No traces, HAR files, browser profiles, storage exports or
temporary database files are uploaded. Screenshots use browser capture bounds;
there is no image editing or replacement UI markup.

## Reproduce

Run the **Synthetic dashboard screenshots** workflow on the dashboard PR. Its
artifact contains three PNGs and `provenance.json` and expires after seven days;
the reviewed copies above remain in the repository. The workflow installs the
CI-only pinned Playwright dependency and its matching Chromium. The dashboard
itself still uses only Python's standard library.

In an environment where loopback sockets and Chromium execution are permitted:

```sh
python -m pip install -r tests/requirements-screenshots.txt
python -m playwright install --with-deps chromium
python -B tests/capture_dashboard.py --output-dir screenshot-artifacts
```

For socket-free fixture/source verification, without installing Playwright:

```sh
python -B tests/capture_dashboard.py --validate-fixture-only
python -m unittest discover -s tests -p test_dashboard_screenshots.py -v
```

Rendering remains in authorized Ubuntu CI because the attached host denies
localhost connections. That restriction was not bypassed. A rerun records its
own source commit and browser version; exact pixels may vary when Chromium or
system fonts change. Do not overwrite the checked-in images without inspecting
the new artifacts and updating their provenance.
