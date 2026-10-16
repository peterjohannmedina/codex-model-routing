# Dashboard screenshots

These checked-in images are actual browser screenshots of the initial dashboard release, rendered by
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

The checked-in images show HTML, CSS, JavaScript and four Python backend/routing
files from `f1423124e5cca1012ef7d64e6a44f2bc84fa703a`. They remain historical
examples; newer wording is verified by subsequent capture artifacts.
The [machine-readable provenance](../docs/images/dashboard-provenance.json)
records exact capture commit, file/image SHA-256 hashes, browser/version,
dimensions, locale and time zone. The checked-in images were captured from GitHub's
temporary PR merge `042f7281709fe2413b8fd1795104449f4f6aaaac` for branch head
`f79192c136774eb19e481aadf4d801b34b5843a5` by
[this CI run](https://github.com/peterjohannmedina/codex-model-routing/actions/runs/38820830785).
Subsequent workflow runs explicitly check out the PR head commit.
The current fixture helper pins all eight production files, including the OTel adapter, to
`80f73615240f4a8b040827b85fe56c2034209631` and verifies their Git blob IDs before
capture. No replacement markup or altered production backend is used for images.

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
The same Chromium run clicks Save with synthetic credential values and a missing
Decisions name. Native validation must show fixed hints and `aria-invalid`, clear
on correction, transmit no configuration or credential value, and leave the
synthetic config unchanged. These checks run after the Providers screenshot;
synthetic credential inputs are never included in captured images. Provenance
records case identifiers and zero transmission/write results without input values.

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
