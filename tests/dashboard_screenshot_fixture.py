"""Public synthetic data only; no provider calls or user-home state is needed."""
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import routing_dashboard as dashboard
import routing_state as state

REVIEWED_SOURCE = '1edc53c6917f0a0a4b9ad97c8822c05f998eb023'
FIXTURE = ROOT / 'tests/fixtures/dashboard-screenshot.json'
# Git blob IDs from REVIEWED_SOURCE; no history fetch is needed in shallow CI.
REVIEWED_FILES = {
    'assets/dashboard/index.html': '469a45291eb0dd94be4b3223d01adde428a92ed4',
    'assets/dashboard/app.js': '24fab5f7944adab0dbe65afd807ac886fc0b4733',
    'assets/dashboard/style.css': 'b14911924be433b177ec9826e9763d838f69d9c9',
    'assets/dashboard/router-mark.svg': '26ccfb0cb47968c96187a1c9da5cf66f9b7122d1',
    'scripts/routing_dashboard.py': '48dca2d21402fa0aa890a4df2b8bcbe6c95faea0',
    'scripts/routing_state.py': 'd0f5e9440a412ef86064293f3346b0826b2eeed9',
    'scripts/routing_runtime.py': '50eed09f84c16d113b112dfea29141a7aca5d06a',
    'scripts/routing_decision.py': 'e5bd70de5011c21f5fc497b56e0c29e3a95342e0',
    'scripts/routing_otel.py': '948c3a56a3d6771ff063fb86c00e5c2e08c7feb5',
    'scripts/routing_catalog.py': 'eac2155ea005ec18afe168d8fd7f4e8f639c4f21',
}


def reviewed_assets():
    result = {}
    for name, blob in REVIEWED_FILES.items():
        actual = (ROOT / name).read_bytes()
        canonical = actual.replace(b'\r\n', b'\n')
        actual_blob = hashlib.sha1(b'blob ' + str(len(canonical)).encode() + b'\0' + canonical).hexdigest()
        if actual_blob != blob:
            raise ValueError('reviewed_source_changed')
        result[name] = {'sha256': hashlib.sha256(actual).hexdigest(),
                        'reviewed_git_blob': blob}
    return result


def load_fixture():
    fixture = json.loads(FIXTURE.read_text(encoding='utf-8'))
    if fixture.get('synthetic') is not True: raise ValueError('synthetic_fixture_required')
    dashboard.safe_config(fixture['config'])
    if fixture['config']['local']['base_url'] != 'http://127.0.0.1:8000/v1': raise ValueError('synthetic_endpoint_required')
    sessions = {'11111111-1111-4111-8111-111111111111', '22222222-2222-4222-8222-222222222222'}
    for index, event in enumerate(fixture['events'], 1):
        state.sanitize(event)
        if event['session_id'] not in sessions or event['request_id'] != 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa' + str(index):
            raise ValueError('demo_identifiers_required')
        if not state.timestamp(event['observed_at']): raise ValueError('fixture_timestamp_required')
        if event.get('selected_candidate_id'):
            selected = next((c for c in event.get('admitted_choices', []) if c['id'] == event['selected_candidate_id']), None)
            if (not selected or any(event.get(k) != selected[k] for k in ('model', 'effort', 'adapter'))
                    or event.get('selected_action') != selected['action']):
                raise ValueError('fixture_selected_route_mismatch')
    return fixture


class ScreenshotStore(dashboard.Store):
    """Use the production backend with generated catalog metadata and observation clock."""
    def __init__(self, root, fixture):
        super().__init__(root)
        self.fixture_clock = fixture['snapshot_time']
        self.catalog_fixture = fixture.get('model_catalog')

    def snapshot(self, session=None):
        result = super().snapshot(session)
        result['observed_at'] = self.fixture_clock
        if self.catalog_fixture: result['model_catalog'] = self.catalog_fixture
        return result


def seed_fixture(root, fixture):
    store = ScreenshotStore(root, fixture)
    _, version = store.config()
    store.save(fixture['config'], version)
    settings = state.LedgerSettings.parse(fixture['config']['observability'])
    ledger = state.Ledger(root, settings)
    seed_time = time.time()
    for index, event in enumerate(fixture['events']):
        ledger.put(event)
        identity = hashlib.sha256((event['source'] + ':' + event['request_id']).encode()).hexdigest()
        with ledger.connect() as connection:
            row = json.loads(connection.execute('SELECT body FROM events WHERE id=?', (identity,)).fetchone()[0])
            row['observed_at'] = row['first_observed_at'] = event['observed_at']
            # Keep fixture rows retained on future CI runs while their displayed
            # demo dates/ordering remain fixed. No production records are used.
            connection.execute('UPDATE events SET updated=?,body=? WHERE id=?',
                               (seed_time + index / 1000, json.dumps(row), identity))
    return store
