"""Render the reviewed UI in isolated CI Chromium, using only public synthetic data."""
import argparse
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import struct
import subprocess
import tempfile
import threading
from urllib.parse import urlsplit
from unittest.mock import patch

from dashboard_screenshot_fixture import ROOT, FIXTURE, REVIEWED_SOURCE, reviewed_assets, load_fixture, seed_fixture
import routing_dashboard as dashboard
import routing_runtime as runtime


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--validate-fixture-only', action='store_true')
    args = parser.parse_args(argv)
    stage = 'validate-fixture'
    try:
        assets, fixture = reviewed_assets(), load_fixture()
        if args.validate_fixture_only:
            print(json.dumps({'synthetic_fixture_valid': True, 'reviewed_source': REVIEWED_SOURCE,
                              'reviewed_files_verified': len(assets), 'events': len(fixture['events']), 'provider_calls': 0}))
            return 0
        if args.output_dir is None: parser.error('--output-dir is required for capture')
        from playwright.sync_api import sync_playwright, expect
        output = args.output_dir.resolve()
        output.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='routing-screenshot-') as directory:
            stage = 'seed-synthetic-state'
            store = seed_fixture(Path(directory), fixture)
            server = dashboard.Server(0, store)
            thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
            thread.start()
            blocked, paths, errors, provider_attempts = [], set(), [], []
            def forbidden_provider(*_args, **_kwargs):
                provider_attempts.append(True)
                raise AssertionError('providers_are_forbidden_in_capture')
            try:
                with (patch.object(runtime, 'local_request', side_effect=forbidden_provider),
                      patch.object(runtime.core.DecisionsProvider, 'choose', side_effect=forbidden_provider),
                      sync_playwright() as playwright):
                    stage = 'launch-chromium'
                    browser = playwright.chromium.launch()
                    context = browser.new_context(viewport={'width': 1440, 'height': 1100}, device_scale_factor=1,
                                                  locale='en-US', timezone_id='UTC', color_scheme='light', service_workers='block')
                    def only_dashboard(route):
                        request = route.request
                        parsed = urlsplit(request.url)
                        method, path = request.method, parsed.path
                        allowed = ((method == 'GET' and path in ('/', '/app.js', '/style.css', '/favicon.ico', '/api/session', '/api/state'))
                                   or (method == 'POST' and path == '/api/auth'))
                        if parsed.scheme != 'http' or parsed.netloc != urlsplit(server.origin).netloc or not allowed:
                            blocked.append(True)
                            route.abort()
                            return
                        paths.add(method + ' ' + path)  # Never headers, query, fragment or tokens.
                        route.continue_()
                    context.route('**/*', only_dashboard)
                    page = context.new_page()
                    page.on('pageerror', lambda _error: errors.append(True))
                    page.set_default_timeout(15000)
                    stage = 'authorize-and-render'
                    # HTTP entry matches the private-file handoff, without a file/data
                    # URL or user profile. The nonce is temporary CI process state only.
                    page.goto(server.origin + '/#authorize=' + server.bootstrap, wait_until='domcontentloaded')
                    expect(page.locator('#requests')).to_have_text('8')
                    expect(page.locator('#executions')).to_have_text('4')
                    expect(page.locator('#connection')).to_have_text('Dashboard live · 2s')
                    expect(page).to_have_url(server.origin + '/')
                    expect(page.locator('#message')).to_be_empty()
                    expect(page.locator('#save')).to_be_enabled()
                    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')

                    stage = 'capture-overview'
                    overview = page.locator('#overview').bounding_box()
                    height = math.ceil(overview['y'] + overview['height'] + 20)
                    if height > 1100: page.set_viewport_size({'width': 1440, 'height': height})
                    page.screenshot(path=str(output / 'dashboard-overview.png'), clip={'x': 0, 'y': 0, 'width': 1440, 'height': height}, animations='disabled')

                    stage = 'providers-navigation-refresh'
                    page.set_viewport_size({'width': 1440, 'height': 2000})
                    page.get_by_role('link', name='Providers', exact=True).click()
                    page.reload(wait_until='domcontentloaded')
                    expect(page.locator('#requests')).to_have_text('8')
                    expect(page.locator('#save')).to_be_enabled()
                    expect(page.locator('#decisions-enabled')).to_be_checked()
                    expect(page.locator('#local-enabled')).to_be_checked()
                    expect(page.locator('#local-model')).to_have_value('synthetic-local-model')
                    page.locator('#providers').screenshot(path=str(output / 'dashboard-providers.png'), animations='disabled')

                    stage = 'activity-navigation-refresh'
                    page.get_by_role('link', name='Activity', exact=True).click()
                    page.reload(wait_until='domcontentloaded')
                    expect(page.locator('#requests')).to_have_text('8')
                    expect(page.locator('#events details')).to_have_count(8)
                    page.locator('#events details').first.locator('summary').click()
                    page.locator('#activity').screenshot(path=str(output / 'dashboard-activity.png'), animations='disabled')
                    assert not blocked and not errors and not provider_attempts
                    browser_version = browser.version
                    context.close()
                    browser.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(2)
        stage = 'write-provenance'
        images = {}
        for name in ('dashboard-overview.png', 'dashboard-providers.png', 'dashboard-activity.png'):
            raw = (output / name).read_bytes()
            assert raw[:8] == b'\x89PNG\r\n\x1a\n'
            width, height = struct.unpack('>II', raw[16:24])
            images[name] = {'sha256': hashlib.sha256(raw).hexdigest(), 'width': width, 'height': height, 'bytes': len(raw)}
        provenance = {'synthetic': True, 'reviewed_source': REVIEWED_SOURCE,
            'capture_source_commit': subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip(),
            'fixture_sha256': hashlib.sha256(FIXTURE.read_bytes()).hexdigest(), 'assets': assets, 'images': images,
            'playwright_version': importlib.metadata.version('playwright'), 'browser': 'Chromium ' + browser_version,
            'locale': 'en-US', 'timezone': 'UTC', 'device_scale_factor': 1, 'viewport_width': 1440,
            'fixture_clock': fixture['snapshot_time'], 'network_paths': sorted(paths),
            'provider_calls': 0, 'external_browser_requests': 0, 'real_user_data': False,
            'note': 'Real reviewed HTML/CSS/JS and backend; only generated fixtures and the displayed observation clock are synthetic. No image editing or UI DOM substitution.'}
        (output / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({'captured': list(images), 'reviewed_source': REVIEWED_SOURCE, 'provider_calls': 0}))
        return 0
    except Exception as error:
        # Playwright error messages can include the temporary bootstrap URL.
        # Never upload traces/storage or print raw browser exceptions.
        print(json.dumps({'capture_failed': True, 'stage': stage, 'error_type': type(error).__name__}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
