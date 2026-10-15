"""Codex source-contract fixtures, privacy, dedup, setup CAS and real HTTP in CI."""
from contextlib import redirect_stderr
import http.client
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import subprocess
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import routing_dashboard as dashboard
import routing_otel as otel
import routing_otel_setup as setup
import routing_state as state

SESSION = '11111111-1111-4111-8111-111111111111'
TOKEN = 'synthetic-local-capability-for-offline-test-1234567890'
NANO = '1792069200123456789'


def record(kind='response', **changes):
    fields = {'event.name': 'codex.sse_event', 'event.kind': 'response.completed', 'conversation.id': SESSION,
              'app.version': '0.162.1', 'model': 'gpt-6.1-sol', 'model_reasoning_effort': 'high',
              'input_token_count': '120', 'output_token_count': '9', 'cached_token_count': 20,
              'event.timestamp': '2026-10-15T13:00:00.123Z'}
    if kind == 'start':
        fields = {k:v for k,v in fields.items() if k not in ('event.kind', 'input_token_count', 'output_token_count', 'cached_token_count', 'model_reasoning_effort')}
        fields.update({'event.name':'codex.conversation_starts', 'reasoning_effort':'low'})
    fields.update(changes)
    return {'timeUnixNano': '0', 'observedTimeUnixNano': NANO, 'attributes': [
        {'key':k, 'value':{'intValue' if type(v) is int else 'stringValue':v}} for k,v in fields.items()]}


def payload(*items):
    return json.dumps({'resourceLogs':[{'resource':{'attributes':[{'key':'user.email','value':{'stringValue':'synthetic-private@example.invalid'}}]},
                                       'scopeLogs':[{'logRecords':list(items)}]}]}).encode()


class OTelMetadata(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT.parent)
        self.root = Path(self.temp.name)
        self.ledger = state.Ledger(self.root)
        self.addCleanup(self.temp.cleanup)

    def test_source_contract_strings_zero_and_separate_units(self):
        result = otel.ingest(payload(record('start'),record()), self.ledger)
        self.assertEqual(result, {'accepted':2,'ignored':0,'rejected':0})
        events = self.ledger.snapshot()
        totals = state.totals(events)
        self.assertEqual(totals['requests'],0)
        self.assertEqual(totals['completed_executions'],0)
        self.assertEqual(totals['downstream']['input_tokens']['known'],0)
        self.assertEqual(totals['otel']['sessions'],1)
        self.assertEqual(totals['otel']['responses'],1)
        self.assertEqual(totals['otel']['input_tokens']['known'],120)
        start = next(e for e in events if e['mode']=='otel_session')
        response = next(e for e in events if e['mode']=='otel_response')
        self.assertEqual((start['model_source'],start['effort']),('startup_configuration','low'))
        self.assertEqual((response['model_source'],response['effort']),('otel_response_metadata','high'))
        self.assertEqual(response['downstream_usage']['cached_input_tokens'],20)
        zero = record(input_token_count='0', output_token_count='0')
        zero['timeUnixNano'] = str(int(NANO)+1)
        otel.ingest(payload(zero),self.ledger)
        self.assertEqual(state.totals(self.ledger.snapshot())['otel']['input_tokens']['unknown_responses'],0)

    def test_replay_late_usage_restart_and_identity_boundaries(self):
        partial=record(output_token_count='unknown')
        otel.ingest(payload(partial),self.ledger)
        first=self.ledger.snapshot()[0]['first_observed_at']
        for _ in range(2): otel.ingest(payload(record()),state.Ledger(self.root))
        rows=self.ledger.snapshot()
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['first_observed_at'],first)
        self.assertEqual(rows[0]['downstream_usage']['output_tokens'],9)
        second=record();second['timeUnixNano']=str(int(NANO)+1)
        otel.ingest(payload(second),self.ledger)
        self.assertEqual(len(self.ledger.snapshot()),2)
        missing=record();missing.pop('observedTimeUnixNano')
        self.assertEqual(otel.ingest(payload(missing),self.ledger)['rejected'],1)

    def test_ignore_generic_completion_errors_and_unknown_version(self):
        generic=record();generic['attributes']=[a for a in generic['attributes'] if a['key'] not in ('input_token_count','output_token_count')]
        error=record(**{'error.message':'synthetic-private-error'})
        changed=record(**{'app.version':'0.163.0'})
        self.assertEqual(otel.ingest(payload(generic,error,changed),self.ledger)['ignored'],3)
        self.assertEqual(self.ledger.snapshot(),[])

    def test_new_resume_model_effort_and_interrupt_observations(self):
        otel.ingest(payload(record('start')),self.ledger)
        resumed=record('start',model='gpt-6-luna',reasoning_effort='max')
        otel.ingest(payload(resumed),state.Ledger(self.root))
        sparse=record('start');sparse['attributes']=[a for a in sparse['attributes'] if a['key'] not in ('model','reasoning_effort')]
        otel.ingest(payload(sparse),self.ledger)
        self.assertEqual(len(self.ledger.snapshot()),1)
        self.assertEqual(self.ledger.snapshot()[0]['model'],'gpt-6-luna')
        self.assertEqual(self.ledger.snapshot()[0]['effort'],'max')
        interrupted=record(**{'event.kind':'response.failed','error.message':'synthetic-interrupt'})
        self.assertEqual(otel.ingest(payload(interrupted),self.ledger)['ignored'],1)
        self.assertEqual(state.totals(self.ledger.snapshot())['completed_executions'],0)

    def test_privacy_before_persistence_and_malformed_shapes(self):
        sentinel='synthetic-private-do-not-persist'
        raw=record(**{'user.email':sentinel,'user.account_id':sentinel,'cwd':sentinel,'prompt':sentinel,'tool.output':sentinel})
        raw['body']={'stringValue':sentinel}
        otel.ingest(payload(raw),self.ledger)
        with self.ledger.connect() as connection:
            body=connection.execute('SELECT body FROM events').fetchone()[0]
        self.assertNotIn(sentinel,body)
        self.assertNotIn('example.invalid',body)
        for invalid in (b'{"resourceLogs":[],"resourceLogs":[]}', b'{"resourceLogs":NaN}', b'[]', b'{"resourceLogs":"bad"}', b'x'*(otel.MAX_BYTES+1)):
            with self.assertRaises((ValueError,TypeError)): otel.ingest(invalid,self.ledger)
        duplicate=record();duplicate['attributes'].append(duplicate['attributes'][0])
        self.assertEqual(otel.ingest(payload(duplicate),self.ledger)['rejected'],1)
        with self.assertRaises(ValueError): otel.ingest(payload(*[record() for _ in range(otel.MAX_RECORDS+1)]),self.ledger)

    def test_disabled_retention_and_clear_cover_all_sources(self):
        self.ledger.settings=state.LedgerSettings(enabled=False)
        otel.ingest(payload(record()),self.ledger)
        self.assertEqual(self.ledger.snapshot(),[])
        self.ledger.settings=state.LedgerSettings(max_events=10)
        for index in range(12):
            item=record();item['timeUnixNano']=str(int(NANO)+index)
            otel.ingest(payload(item),self.ledger)
        self.assertEqual(len(self.ledger.snapshot()),10)
        self.ledger.clear();self.assertEqual(self.ledger.snapshot(),[])


class OTelSetup(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT.parent)
        self.home=Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.config=self.home/'config.toml'
        self.original=b'# synthetic config\nmodel = "gpt-6.1-sol"\n[analytics]\nenabled = false\n'
        self.config.write_bytes(self.original)

    def test_plan_writes_nothing_and_refuses_any_existing_exporter(self):
        result=setup.plan(self.home)
        self.assertTrue(result['requires_explicit_approval'])
        self.assertTrue(result['ready'])
        self.assertFalse((self.home/'routing').exists())
        for declaration in ('[otel]\nexporter = "none"\n','[otel]\nexporter = { otlp-http = { endpoint="http://example.invalid", protocol="json" } }\n'):
            self.config.write_bytes(self.original+declaration.encode())
            self.assertFalse(setup.plan(self.home)['ready'])
            with self.assertRaises(ValueError): setup.apply(self.home,setup.sha(self.config.read_bytes()))
            self.assertEqual(self.config.read_bytes(),self.original+declaration.encode())

    def test_exact_approval_backup_apply_and_undo_preserve_bytes(self):
        before=setup.plan(self.home)
        with self.assertRaises(ValueError): setup.apply(self.home,'wrong')
        result=setup.apply(self.home,before['config_sha256'])
        current=self.config.read_bytes()
        self.assertTrue(current.startswith(self.original))
        parsed=setup.tomllib.loads(current.decode())
        self.assertFalse(parsed['analytics']['enabled'])
        self.assertEqual(parsed['otel']['tool_result']['max_bytes'],0)
        token_path=Path(result['capability_file'])
        self.assertEqual(parsed['otel']['exporter']['otlp-http']['headers']['x-routing-otel'],token_path.read_text().strip())
        self.assertNotIn(token_path.read_text().strip(),json.dumps(result))
        with self.assertRaises(ValueError): setup.apply(self.home,setup.sha(current))
        if os.name!='nt': self.assertEqual(token_path.stat().st_mode & 0o777,0o600)
        setup.undo(self.home,result['config_sha256'])
        self.assertEqual(self.config.read_bytes(),self.original)
        self.assertFalse(token_path.exists())
        self.assertTrue(Path(result['backup']).exists())

    def test_edit_and_corrupt_backup_prevent_undo(self):
        applied=setup.apply(self.home,setup.plan(self.home)['config_sha256'])
        configured=self.config.read_bytes()
        self.config.write_bytes(configured+b'# later edit\n')
        with self.assertRaises(ValueError): setup.undo(self.home,applied['config_sha256'])
        self.assertTrue(self.config.read_bytes().endswith(b'# later edit\n'))
        self.config.write_bytes(configured)
        Path(applied['backup']).write_bytes(b'corrupt')
        with self.assertRaises(ValueError): setup.undo(self.home,applied['config_sha256'])
        self.assertEqual(self.config.read_bytes(),configured)

    def test_lock_and_new_config_undo_are_safe(self):
        self.config.unlink()
        with setup.setup_lock(self.home):
            with self.assertRaises(FileExistsError): setup.apply(self.home,setup.sha(b''))
        applied=setup.apply(self.home,setup.sha(b''))
        setup.undo(self.home,applied['config_sha256'])
        self.assertFalse(self.config.exists())

    @unittest.skipUnless(sys.platform=='win32','Windows plan launcher')
    def test_powershell_plan_is_read_only(self):
        result=subprocess.run(['powershell.exe','-NoProfile','-File',str(ROOT/'scripts/Prepare-RoutingTelemetry.ps1'),
            '-CodexHome',str(self.home),'-PythonPath',sys.executable],capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertTrue(json.loads(result.stdout)['ready'])
        self.assertEqual(self.config.read_bytes(),self.original)
        self.assertFalse((self.home/'routing').exists())


@unittest.skipIf(os.environ.get('ROUTING_SKIP_SOCKET_TESTS')=='1','Local socket restrictions; CI requires real HTTP')
class OTelHTTP(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT.parent)
        self.addCleanup(self.temp.cleanup)
        self.store=dashboard.Store(Path(self.temp.name))
        try: self.server=dashboard.Server(0,self.store,TOKEN)
        except PermissionError:
            if os.environ.get('ROUTING_REQUIRE_HTTP_TESTS')=='1': raise
            self.skipTest('Loopback denied')
        self.addCleanup(self.server.server_close)
        thread=threading.Thread(target=self.server.serve_forever,kwargs={'poll_interval':.02},daemon=True)
        thread.start();self.addCleanup(thread.join,1);self.addCleanup(self.server.shutdown)
        try: self.request({otel.HEADER:'invalid-probe'})
        except PermissionError:
            if os.environ.get('ROUTING_REQUIRE_HTTP_TESTS')=='1': raise
            self.skipTest('Loopback connections denied')

    def request(self,headers=None,raw=None):
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
        try:
            connection.request('POST','/v1/logs',payload(record('start'),record()) if raw is None else raw,
                               {otel.HEADER:TOKEN,'Content-Type':'application/json',**(headers or {})})
            response=connection.getresponse();body=response.read()
            return response.status,body
        finally: connection.close()

    def test_real_http_receiver_guards_redaction_and_browser_state(self):
        for headers in ({otel.HEADER:'wrong'},{'Origin':self.server.origin},{'Sec-Fetch-Site':'same-origin'},
                        {'Host':'localhost:'+str(self.server.server_port)}):
            self.assertEqual(self.request(headers)[0],403)
        self.assertEqual(self.request({'Content-Encoding':'gzip'})[0],415)
        self.assertEqual(self.request({'Content-Length':str(otel.MAX_BYTES+1)},raw=b'{}')[0],413)
        with redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(self.request(raw=b'{"synthetic-private":NaN}')[0],400)
        self.assertEqual(errors.getvalue(),'')
        self.assertEqual(self.request(),(200,b'{}'))
        snapshot=self.store.snapshot()
        self.assertEqual(snapshot['sessions'],[SESSION])
        self.assertEqual(snapshot['totals']['requests'],0)
        self.assertEqual(snapshot['totals']['otel']['responses'],1)
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
        connection.request('POST','/api/auth','{}',{'Origin':self.server.origin,'Content-Type':'application/json',
            'X-Routing-Bootstrap':self.server.bootstrap})
        response=connection.getresponse();csrf=json.loads(response.read())['csrf']
        cookie=response.getheader('Set-Cookie').split(';')[0];connection.close()
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
        connection.request('GET','/api/state?session='+SESSION,headers={'Cookie':cookie,'X-Routing-CSRF':csrf})
        response=connection.getresponse();snapshot=json.loads(response.read());connection.close()
        self.assertTrue(snapshot['otel_receiver']['enabled'])
        self.assertEqual(snapshot['otel_receiver']['accepted_records'],2)
        self.assertEqual(snapshot['totals']['otel']['responses'],1)
        self.assertNotIn(TOKEN,json.dumps(snapshot))
        self.server.otel_capability=None
        self.assertEqual(self.request()[0],404)

    def test_recording_disable_never_stores_a_batch(self):
        config,version=self.store.config();config['observability']['enabled']=False
        self.store.save(config,version)
        self.assertEqual(self.request()[0],200)
        self.assertEqual(state.Ledger(self.store.root).snapshot(),[])
        self.assertIsNone(self.store.otel_status['last_received_at'])


if __name__=='__main__': unittest.main()
