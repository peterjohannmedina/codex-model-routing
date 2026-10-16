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

REVIEWED_SOURCE = '6c60192a3d23e95815f1e0c2678ef567b821ac49'
FIXTURE = ROOT / 'tests/fixtures/dashboard-screenshot.json'
# Git blob IDs from REVIEWED_SOURCE; no history fetch is needed in shallow CI.
REVIEWED_FILES = {
    'assets/dashboard/index.html': 'eb211e03d83cd6807c2c4ed04afbce37bfd7c27e',
    'assets/dashboard/app.js': 'd583b99ee54f403aa8e5453ae7fa247d831d1c25',
    'assets/dashboard/style.css': '6087cc41fd3897a479076ccc6c85c6c786ce23f8',
    'scripts/routing_dashboard.py': '518fe7cdbb6c03a92973df7653a4053f4277fe23',
    'scripts/routing_state.py': '6961b6c3a18c596750c3c35c0033dac3667f1b40',
    'scripts/routing_runtime.py': 'eb2a69397602d72af1160e8f0f55f50b8431c733',
    'scripts/routing_decision.py': '5b1d1c36408c0c0a0cf69f962c8832a9d1bf3f4b',
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
    return fixture


class ScreenshotStore(dashboard.Store):
    """Use the production backend; only the displayed observation clock is synthetic."""
    def __init__(self, root, fixture):
        super().__init__(root)
        self.fixture_clock = fixture['snapshot_time']

    def snapshot(self, session=None):
        result = super().snapshot(session)
        result['observed_at'] = self.fixture_clock
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
