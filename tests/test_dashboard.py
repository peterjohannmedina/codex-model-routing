from dataclasses import asdict, replace
from contextlib import closing
import http.client
import io
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest
import uuid
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import routing_dashboard as dashboard
import routing_runtime as runtime
import routing_state as state
import collect_codex_json as collect
from test_optional_providers import local_packet, configuration, catalog
from test_routing_decision import packet


def event(**kwargs):
    return {'source': 'router', 'session_id': str(uuid.uuid4()), 'request_id': str(uuid.uuid4()), **kwargs}


class LocalState(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT.parent)
        self.root = Path(self.temp.name)
        self.ledger = state.Ledger(self.root)

    def tearDown(self): self.temp.cleanup()

    def test_dedup_late_usage_and_unknown_are_distinct_from_zero(self):
        item = event(stage=1)
        self.assertTrue(self.ledger.put(item))
        initial = self.ledger.snapshot()[0]
        self.assertFalse(self.ledger.put(item))
        self.assertEqual(state.totals(self.ledger.snapshot())['downstream']['input_tokens']['unknown_requests'], 1)
        item.update(stage=2, execution_status='completed', downstream_usage={'input_tokens': 0})
        self.ledger.put(item)
        item['downstream_usage'] = {'output_tokens': 9}
        self.ledger.put(item)
        rows = self.ledger.snapshot()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['downstream_usage'], {'input_tokens': 0, 'output_tokens': 9, 'cached_input_tokens': None})
        self.assertEqual(rows[0]['first_observed_at'], initial['first_observed_at'])
        self.assertEqual(state.totals(rows)['downstream']['input_tokens'], {'known': 0, 'unknown_requests': 0})
        self.assertFalse(self.ledger.put({**item, 'stage': 0, 'downstream_usage': {'input_tokens': 50}}))

    def test_metadata_allowlist_excludes_sensitive_payloads(self):
        secret = 'sk-proj-' + 'A' * 30
        self.ledger.put(event(prompt=secret, text=secret, endpoint='http://user:' + secret + '@host',
                              model=secret, override_model=secret, fallback_reason=secret, usage={'secret': secret}))
        raw = self.ledger.path.read_bytes()
        self.assertNotIn(secret.encode(), raw)
        stored = self.ledger.snapshot()[0]
        self.assertIsNone(stored['model'])
        self.assertNotIn('prompt', stored)
        self.assertNotIn('endpoint', stored)

    def test_final_admission_error_clears_stale_recommendation(self):
        item = event(stage=0, model='gpt-6.1-sol', fallback_reason='offline')
        self.ledger.put(item)
        self.ledger.put({**item, 'stage':2, 'model':None, 'fallback_reason':None, 'error':'require_local_unavailable'})
        stored = self.ledger.snapshot()[0]
        self.assertIsNone(stored['model'])
        self.assertIsNone(stored['fallback_reason'])
        self.assertEqual(stored['error'],'require_local_unavailable')

    def test_read_path_reapplies_allowlist(self):
        self.ledger.put(event())
        with closing(sqlite3.connect(self.ledger.path)) as connection:
            identity, body = connection.execute('SELECT id,body FROM events').fetchone()
            value = json.loads(body)
            value['arbitrary_prompt'] = 'never serve this'
            connection.execute('UPDATE events SET body=? WHERE id=?', (json.dumps(value), identity))
            connection.commit()
        self.assertNotIn('arbitrary_prompt', self.ledger.snapshot()[0])

    def test_retention_disable_clear_and_cost_evidence(self):
        settings = state.LedgerSettings(max_events=10)
        self.ledger.settings = settings
        for _ in range(12): self.ledger.put(event())
        self.assertEqual(len(self.ledger.snapshot()), 10)
        with closing(sqlite3.connect(self.ledger.path)) as connection:
            connection.execute('UPDATE events SET updated=0 WHERE id=(SELECT id FROM events LIMIT 1)')
            connection.commit()
        self.assertEqual(len(self.ledger.snapshot()), 9)
        self.ledger.settings = replace(settings, enabled=False)
        self.assertFalse(self.ledger.put(event()))
        sample = event(adapter='local', evaluator_usage={'input_tokens': 100, 'output_tokens': 0},
                       downstream_usage={'input_tokens': 20, 'output_tokens': 10})
        totals = state.totals([sample], state.LedgerSettings(local_input_usd_per_million=1, local_output_usd_per_million=2))
        self.assertAlmostEqual(totals['evaluator_base_cost_estimate_usd'], 0.00001)
        self.assertAlmostEqual(totals['local_cost_estimate_usd'], 0.00004)
        self.assertIsNone(totals['measured_billed_cost_usd'])
        self.assertIsNone(state.totals([sample])['local_cost_estimate_usd'])
        self.ledger.clear()
        self.assertEqual(self.ledger.snapshot(), [])

    def test_settings_validation(self):
        for bad in ({'enabled': 1}, {'retention_days': 0}, {'max_events': 100000}, {'api_key': 'no'},
                    {'local_input_usd_per_million': float('nan')}):
            with self.assertRaises(ValueError): state.LedgerSettings.parse(bad)

    def test_request_and_stream_ids_require_uuid_and_malformed_rows_fail_closed(self):
        for malformed in (None, [], {'source':'router'}, event(request_id='unassigned')):
            with self.assertRaises(ValueError): state.sanitize(malformed)
        with self.assertRaises(ValueError): collect.Collector(self.ledger,'unassigned')
        self.assertEqual(state.identifier('unassigned'),'unassigned')

    def test_config_cas_and_toggles_do_not_contact_providers(self):
        store = dashboard.Store(self.root)
        config, version = store.config()
        config['decisions']['enabled'] = True
        config['local'].update(enabled=True, base_url='http://127.0.0.1:9/v1', model='example-model')
        with patch.object(runtime, 'local_request', side_effect=AssertionError('toggle probed')), \
             patch.object(runtime.core.DecisionsProvider, 'choose', side_effect=AssertionError('toggle evaluated')):
            saved, new_version = store.save(config, version)
        self.assertTrue(saved['decisions']['enabled'])
        self.assertNotEqual(version, new_version)
        with self.assertRaises(FileExistsError): store.save(config, version)
        for field, value in (('base_url', 'http://user:password@127.0.0.1/v1'), ('model', 'sk-proj-' + 'A' * 30)):
            bad = json.loads(json.dumps(config)); bad['local'][field] = value
            with self.assertRaises(ValueError): store.save(bad, new_version)
        self.assertFalse((self.root / 'usage.sqlite3').exists())

    def test_store_rejects_repository_state(self):
        with self.assertRaises(ValueError): dashboard.Store(ROOT / 'routing-test-state')

    def test_browser_bootstrap_is_single_use_and_expires(self):
        server = object.__new__(dashboard.Server)  # Authorization logic needs no socket.
        server.bootstrap='synthetic-bootstrap'; server.bootstrap_lock=threading.Lock()
        server.bootstrap_used=False; server.bootstrap_until=state.time.monotonic()+10; server.launch_path=None
        self.assertFalse(server.authorize('wrong'))
        self.assertTrue(server.authorize('synthetic-bootstrap'))
        self.assertFalse(server.authorize('synthetic-bootstrap'))
        server.bootstrap_used=False; server.bootstrap_until=0
        self.assertFalse(server.authorize('synthetic-bootstrap'))

    def test_transport_usage_observations_without_text_persistence(self):
        wrapped, observed = runtime.transport_observer(lambda *_: b'{"usage":{"input_tokens":12,"output_tokens":0},"text":"ignored"}')
        wrapped(b'{}', 'offline-placeholder', 1)
        self.assertEqual(observed['attempts'], 1)
        self.assertEqual(observed['usage']['input_tokens'], 12)
        def wire(method, *_):
            return catalog() if method == 'GET' else b'{"choices":[{"message":{"content":"unpersisted output"}}],"usage":{"prompt_tokens":4,"completion_tokens":2}}'
        result = runtime.execute_local(local_packet(), configuration(True), environment={}, transport=wire, allow_local_inference=True)
        self.assertEqual(result['observations']['downstream_usage']['input_tokens'], 4)
        self.assertEqual(result['observations']['downstream_attempts'], 1)

    def test_collector_replay_late_updates_and_live_disable(self):
        stream, session = str(uuid.uuid4()), str(uuid.uuid4())
        collector = collect.Collector(self.ledger, stream)
        values = [{'type':'thread.started','thread_id':session}, {'type':'turn.started'},
                  {'type':'item.started','item':{'id':'item_1','type':'command_execution','command':'private command'}},
                  {'type':'item.completed','item':{'id':'item_1','type':'command_execution','aggregated_output':'private output'}},
                  {'type':'turn.completed','usage':{'input_tokens':10}}]
        for value in values: collector.consume(value)
        collect.Collector(self.ledger, stream).consume(values[-1])
        # Replay from the beginning must produce the same canonical request/session.
        replay = collect.Collector(self.ledger, stream)
        for value in values: replay.consume(value)
        replay.consume({'type':'turn.completed','usage':{'output_tokens':5}})
        rows = self.ledger.snapshot()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['session_id'], session)
        self.assertEqual(rows[0]['downstream_usage']['input_tokens'], 10)
        self.assertEqual(rows[0]['downstream_usage']['output_tokens'], 5)
        self.assertNotIn(b'private ', self.ledger.path.read_bytes())
        disabled = collect.Collector(self.ledger, str(uuid.uuid4()), settings_loader=lambda: state.LedgerSettings(enabled=False))
        self.assertFalse(disabled.consume({'type':'turn.started'}))

    def test_collector_bounds_and_malformed_lines(self):
        collector = collect.Collector(self.ledger, str(uuid.uuid4()))
        self.assertFalse(collector.close())
        self.assertFalse(self.ledger.path.exists())
        blob = b'{' + b'x' * collect.MAX_LINE + b'\nnot json\n' + b'{"type":"turn.completed","usage":{"input_tokens":0,"output_tokens":0}}\n'
        result = collect.consume_stream(io.BytesIO(blob), collector)
        self.assertEqual(result['rejected_lines'], 2)
        self.assertEqual(self.ledger.snapshot()[0]['downstream_usage']['input_tokens'], 0)
        with self.assertRaises(ValueError): collect.Collector(self.ledger, 'not-a-uuid')


@unittest.skipIf(os.environ.get('ROUTING_SKIP_SOCKET_TESTS') == '1', 'Local socket restrictions; CI runs HTTP integration')
class DashboardHTTP(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT.parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        try: self.server = dashboard.Server(0, dashboard.Store(self.root))
        except PermissionError:
            if os.environ.get('ROUTING_REQUIRE_HTTP_TESTS') == '1': raise
            self.skipTest('Loopback sockets unavailable in this environment')
        self.addCleanup(self.server.server_close)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval':0.02}, daemon=True)
        self.thread.start()
        self.addCleanup(self.thread.join, 1)
        self.addCleanup(self.server.shutdown)
        try: response, body = self.request('GET', '/')
        except PermissionError:
            if os.environ.get('ROUTING_REQUIRE_HTTP_TESTS') == '1': raise
            self.skipTest('Loopback connections denied; CI verifies real HTTP')
        self.assertIsNone(response.getheader('Set-Cookie'))
        self.assertIn(b'Routing desk', body)
        self.assertNotIn(self.server.bootstrap.encode(),body)
        self.assertEqual(self.request('GET','/api/session')[0].status,403)
        launch = self.server.create_launch_file()
        self.assertTrue(launch.is_file())
        if os.name != 'nt': self.assertEqual(launch.stat().st_mode & 0o777, 0o600)
        response, body = self.request('POST','/api/auth','{}',{'Origin':self.server.origin,
            'Content-Type':'application/json','X-Routing-Bootstrap':self.server.bootstrap})
        self.assertEqual(response.status,200)
        self.assertFalse(launch.exists())
        self.csrf = json.loads(body)['csrf']
        self.cookie = response.getheader('Set-Cookie').split(';')[0]
        self.assertIn('HttpOnly; SameSite=Strict', response.getheader('Set-Cookie'))
        response, body = self.request('GET', '/api/session', headers={'Cookie':self.cookie,'X-Routing-CSRF':self.csrf})
        self.csrf = json.loads(body)['csrf']

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        connection.request(method, path, body, headers or {})
        response = connection.getresponse(); data = response.read(); connection.close()
        return response, data

    def authenticated(self, method, path, body=None, **extra):
        headers={'Cookie':self.cookie, 'Origin':self.server.origin, 'X-Routing-CSRF':self.csrf, 'Content-Type':'application/json', **extra}
        return self.request(method, path, json.dumps(body) if body is not None else None, headers)

    def test_origin_host_session_csrf_and_size_guards(self):
        self.assertEqual(self.request('GET','/api/state')[0].status,403)
        self.assertEqual(self.request('GET','/api/session',headers={'Cookie':self.cookie})[0].status,403)
        self.assertEqual(self.request('GET','/api/state',headers={'Cookie':self.cookie})[0].status,403)
        for headers in ({'Host':'evil.test'}, {'Origin':'https://evil.test'}):
            self.assertEqual(self.request('GET','/',headers=headers)[0].status,403)
        self.assertEqual(self.authenticated('GET','/api/state',**{'Sec-Fetch-Site':'cross-site'})[0].status,403)
        # Static root navigation is public but grants no session/data access.
        self.assertEqual(self.request('GET','/',headers={'Sec-Fetch-Site':'cross-site'})[0].status,200)
        self.assertEqual(self.request('POST','/api/auth','{}',{'Origin':self.server.origin,
            'Content-Type':'application/json','X-Routing-Bootstrap':self.server.bootstrap})[0].status,403)
        response, data = self.authenticated('GET','/api/state')
        self.assertEqual(response.status,200)
        payload={'config':json.loads(data)['config'], 'version':json.loads(data)['config_version']}
        for extra in ({'Origin':'null'}, {'X-Routing-CSRF':''}, {'Host':'localhost:'+str(self.server.server_port)}):
            self.assertEqual(self.authenticated('POST','/api/config',payload,**extra)[0].status,403)
        self.assertEqual(self.authenticated('POST','/api/config',payload)[0].status,200)
        self.assertEqual(self.authenticated('POST','/api/config',{'config':payload['config'],'version':'stale'})[0].status,409)
        self.assertEqual(self.authenticated('POST','/api/config',{'large':'x'*33000})[0].status,413)
        self.assertEqual(self.authenticated('GET','/../../config.json')[0].status,404)
        self.assertEqual(self.authenticated('GET','/api/execute')[0].status,404)

    def test_real_live_updates_session_drilldown_and_replay(self):
        ledger = state.Ledger(self.root)
        session = str(uuid.uuid4())
        collector = collect.Collector(ledger, str(uuid.uuid4()))
        collector.consume({'type':'thread.started','thread_id':session})
        collector.consume({'type':'turn.started'})
        first=json.loads(self.authenticated('GET','/api/state')[1])
        self.assertEqual(first['totals']['completed_executions'],0)
        collector.consume({'type':'turn.completed'})
        collector.consume({'type':'turn.completed','usage':{'input_tokens':0,'output_tokens':7}})
        second=json.loads(self.authenticated('GET','/api/state?session='+session)[1])
        self.assertEqual(second['totals']['requests'],1)
        self.assertEqual(second['totals']['completed_executions'],1)
        self.assertEqual(second['totals']['downstream']['input_tokens'], {'known':0,'unknown_requests':0})
        other=collect.Collector(ledger,str(uuid.uuid4()))
        other.consume({'type':'turn.started'})
        all_events=json.loads(self.authenticated('GET','/api/state')[1])
        self.assertEqual(len(all_events['sessions']),2)
        self.assertEqual(all_events['coverage']['interactive_tui'],'unobserved')
        self.assertEqual(self.authenticated('POST','/api/ledger/clear',{'confirm':True})[0].status,200)
        self.assertEqual(json.loads(self.authenticated('GET','/api/state')[1])['events'],[])
