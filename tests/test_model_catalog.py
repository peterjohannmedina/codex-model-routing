"""Synthetic account/model metadata only. No Codex subprocess or inference."""
import copy
from dataclasses import replace
import json
from pathlib import Path
import sys
import tempfile
import queue
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import routing_catalog as catalog
import routing_dashboard as dashboard
import routing_decision as core
import routing_runtime as runtime
from test_routing_decision import packet
from test_optional_providers import local_packet, configuration, catalog as local_catalog


def model(name='gpt-6.1-sol',efforts=('low','medium'),**extra):
    return {'model':name,'hidden':False,'supportedReasoningEfforts':[{'reasoningEffort':e} for e in efforts],
            'defaultReasoningEffort':efforts[0], 'inputModalities':['text','image'],**extra}


def snapshot():
    return {'schema_version':1,'source':'codex_app_server_model_list','queried_at':catalog.clock(),
            'auth_type':'chatgpt','plan_type':'pro','last_error':None,'scope_verified':False,'cache_fetched_at':None,
            'models':catalog.normalize_models([model(),model('gpt-6-luna',('high','max')),model('gpt-6-astra')])}


class FakeRpc:
    def __init__(self,pages=None,account=None,changed=False,notify=False):
        self.pages=iter(pages or [{'data':[model()],'nextCursor':None}]);self.calls=[];self.closed=False
        self.account=account or {'type':'chatgpt','email':'synthetic-private@example.invalid','planType':'pro'}
        self.changed=changed;self.notify=notify;self.reads=0;self.account_updates=0
    def send(self,value): self.calls.append(value)
    def call(self,method,params):
        self.calls.append({'method':method,'params':params})
        if method=='initialize':return {}
        if method=='account/read':
            self.reads+=1
            if self.reads==2 and self.notify:self.account_updates+=1
            return {'account':dict(self.account,planType='plus') if self.reads==2 and self.changed else self.account}
        if method=='model/list':return next(self.pages)
        raise AssertionError('unexpected RPC')
    def close(self): self.closed=True


class Discovery(unittest.TestCase):
    def test_rpc_deadline_and_method_allowlist_without_process(self):
        rpc=object.__new__(catalog.Rpc);rpc.sequence=0;rpc.messages=queue.Queue();rpc.account_updates=0
        rpc.deadline=time.monotonic()+.001;rpc.send=lambda _value:None
        with self.assertRaisesRegex(catalog.CatalogError,'catalog_refresh_timeout'):rpc.call('model/list',{})
        with self.assertRaisesRegex(catalog.CatalogError,'unsupported_discovery_method'):rpc.call('turn/start',{})
        rpc.deadline=time.monotonic()+1;rpc.messages.put({'method':'account/updated','params':{'authMode':'chatgpt'}})
        rpc.messages.put({'id':2,'result':{'data':[],'nextCursor':None}})
        self.assertEqual(rpc.call('model/list',{})['data'],[]);self.assertEqual(rpc.account_updates,1)

    def test_rpc_cleanup_terminates_only_created_process_and_kills_on_timeout(self):
        from unittest.mock import Mock
        import subprocess
        rpc=object.__new__(catalog.Rpc);rpc.process=Mock()
        rpc.process.wait.side_effect=[subprocess.TimeoutExpired('synthetic',1),0]
        rpc.close()
        rpc.process.terminate.assert_called_once();rpc.process.kill.assert_called_once()
        rpc.process.stdin.close.assert_called_once();rpc.process.stdout.close.assert_called_once()

    def test_pagination_limits_and_concurrent_refresh_do_not_publish(self):
        for pages in ([{'data':[model('m'+str(i))],'nextCursor':str(i)} for i in range(8)],
                      [{'data':[model('m'+str(i)) for i in range(129)],'nextCursor':None}]):
            with tempfile.TemporaryDirectory(dir=ROOT.parent) as directory:
                with self.assertRaises(catalog.CatalogError):catalog.refresh(directory,directory,lambda:FakeRpc(pages))
                self.assertFalse((Path(directory)/'model-catalog.json').exists())
        with catalog._slot,self.assertRaisesRegex(catalog.CatalogError,'catalog_refresh_busy'):
            catalog.refresh('unused','unused',lambda:self.fail('concurrent discovery started'))

    def test_supported_metadata_only_pagination_and_no_identity_persistence(self):
        rpc=FakeRpc([{'data':[model()],'nextCursor':'page2'},
                     {'data':[model('gpt-6-luna',('high',)),model('hidden-model',hidden=True)],'nextCursor':None}])
        with tempfile.TemporaryDirectory(dir=ROOT.parent) as directory:
            result=catalog.refresh(directory,directory,lambda:rpc)
            raw=(Path(directory)/'model-catalog.json').read_text()
            self.assertNotIn('synthetic-private',raw);self.assertNotIn('account_scope',raw)
            self.assertNotIn('identity',raw);self.assertNotIn('email',raw)
            self.assertEqual([m['id'] for m in result['models']],['gpt-6.1-sol','gpt-6-luna'])
            self.assertEqual(result['entitlement'],'unverified');self.assertFalse(result['scope_verified'])
            self.assertEqual(result['remote_freshness'],'unverified')
        self.assertTrue(rpc.closed)
        self.assertEqual({c['method'] for c in rpc.calls},{'initialize','initialized','account/read','model/list'})
        self.assertTrue(all(c['params']=={'refreshToken':False} for c in rpc.calls if c['method']=='account/read'))
        self.assertTrue(all(c['params']['includeHidden'] is False for c in rpc.calls if c['method']=='model/list'))

    def test_account_change_same_mode_notification_and_missing_login_fail_closed(self):
        for rpc in [FakeRpc(changed=True),FakeRpc(notify=True),FakeRpc(account={'type':'apiKey'})]:
            with self.subTest(rpc=rpc),tempfile.TemporaryDirectory(dir=ROOT.parent) as directory:
                with self.assertRaises(catalog.CatalogError):catalog.refresh(directory,directory,lambda:rpc)
                self.assertFalse((Path(directory)/'model-catalog.json').exists())
                self.assertTrue(rpc.closed)

    def test_partial_failure_does_not_publish_partial_catalog_or_raw_error(self):
        with tempfile.TemporaryDirectory(dir=ROOT.parent) as directory:
            catalog.installation.atomic(Path(directory)/'model-catalog.json',catalog.installation.encoded(snapshot()))
            rpc=FakeRpc([{'data':[model('new-model')],'nextCursor':'again'}, {'data':[],'nextCursor':'again'}])
            with self.assertRaisesRegex(catalog.CatalogError,'invalid_catalog_cursor'):
                catalog.refresh(directory,directory,lambda:rpc)
            retained=catalog.load(directory)
            self.assertNotIn('new-model',[m['id'] for m in retained['models']])
            self.assertEqual(catalog.public(retained)['status'],'error')

    def test_malformed_hidden_duplicate_and_sensitive_models_rejected(self):
        cases=[[model(),model()],[model('sk-proj-synthetic-credential')],[model(hidden='false')],
               [model(supportedReasoningEfforts='bad')],[model(inputModalities=['unknown'])]]
        for value in cases:
            with self.subTest(value=value),self.assertRaises(catalog.CatalogError):catalog.normalize_models(value)
        self.assertFalse(catalog.normalize_models([model(efforts=('none',))])[0]['policy_supported'])

    def test_stale_future_missing_and_failure_are_explicit(self):
        value=snapshot();self.assertEqual(catalog.public(value)['status'],'queried')
        value['queried_at']='2000-01-01T00:00:00+00:00';self.assertEqual(catalog.public(value)['status'],'stale')
        value['queried_at']='2099-01-01T00:00:00+00:00';self.assertEqual(catalog.public(value)['status'],'stale')
        value['last_error']='catalog_rpc_error';self.assertEqual(catalog.public(value)['status'],'error')
        self.assertEqual(catalog.public(None)['status'],'unverified')

    def test_cli_unavailable_and_transport_errors_are_static(self):
        with patch.object(catalog.shutil,'which',return_value=None),self.assertRaisesRegex(catalog.CatalogError,'codex_cli_unavailable'):catalog.Rpc()
        with tempfile.TemporaryDirectory(dir=ROOT.parent) as directory:
            with self.assertRaisesRegex(catalog.CatalogError,'catalog_unavailable'):
                catalog.refresh(directory,directory,lambda:(_ for _ in ()).throw(OSError('synthetic private path')))

    def test_windows_native_cli_requirement_is_explicit_in_doctor(self):
        import routing_bootstrap as bootstrap
        with patch.object(catalog.os,'name','nt'),patch.object(catalog.shutil,'which',side_effect=lambda name:'synthetic-codex.cmd' if name=='codex' else None),patch.object(bootstrap,'status',return_value={'installed':False}):
            result=bootstrap.doctor(None)
        self.assertTrue(result['codex_cli_found']);self.assertFalse(result['catalog_cli_found'])
        self.assertIn('native codex.exe',result['catalog_cli_requirement'])


class Eligibility(unittest.TestCase):
    def config(self,allowed,**kwargs):
        return replace(runtime.Config(**kwargs),native=runtime.NativeConfig(allowed))

    def test_disabled_fallback_is_removed_before_provider_selection(self):
        value=runtime.route(packet(),self.config(['gpt-6-luna']),native_catalog=snapshot(),offline=True)
        self.assertEqual(value['recommendation']['model'],'gpt-6-luna')
        with self.assertRaisesRegex(core.RoutingError,'requested_native_model_disabled'):
            runtime.route(packet(),self.config(['gpt-6-luna']),core.Overrides(model='gpt-6.1-sol'),native_catalog=snapshot())

    def test_empty_selection_never_implicitly_enables_any_native_model(self):
        with self.assertRaisesRegex(core.RoutingError,'no_native_models_enabled'):
            runtime.route(packet(),self.config([]),native_catalog=snapshot())
        value=runtime.route(packet(),self.config(None),offline=True)
        self.assertEqual(value['recommendation']['model'],'gpt-6.1-sol')

    def test_absent_stale_removed_effort_and_modality_constraints(self):
        for value in (None,dict(snapshot(),queried_at='2000-01-01T00:00:00+00:00')):
            with self.subTest(value=value),self.assertRaisesRegex(core.RoutingError,'native_catalog_refresh_required'):
                runtime.route(packet(),self.config(['gpt-6.1-sol']),native_catalog=value)
        for override in (core.Overrides(effort='max'),core.Overrides(model='gpt-5.6-terra')):
            with self.subTest(override=override),self.assertRaises(core.RoutingError):
                runtime.route(packet(),self.config(['gpt-6.1-sol','gpt-5.6-terra']),override,native_catalog=snapshot())
        value=packet();value['required_modalities']=['audio']
        with self.assertRaisesRegex(core.RoutingError,'native_model_or_effort_unavailable'):
            runtime.route(value,self.config(['gpt-6.1-sol']),native_catalog=snapshot())

    def test_new_model_requires_explicit_selection_and_returned_effort(self):
        value=packet();value['available_models']['future-codex-model']=['low']
        value['candidates'].insert(0,{'id':'new','action':'switch','model':'future-codex-model','effort':'low'})
        value['fallback_id']='new'
        discovered=snapshot();discovered['models']+=catalog.normalize_models([model('future-codex-model',('low',))])
        result=runtime.route(value,self.config(['gpt-6-luna']),native_catalog=discovered)
        self.assertEqual(result['recommendation']['model'],'gpt-6-luna')
        result=runtime.route(value,self.config(['future-codex-model']),native_catalog=discovered)
        self.assertEqual(result['recommendation']['model'],'future-codex-model')

    def test_provider_failure_uses_only_admitted_fallback(self):
        config=self.config(['gpt-6-luna','gpt-6-astra'],decisions=runtime.DecisionsConfig(enabled=True))
        def fail(*_):raise core.ProviderFailure('network')
        value=runtime.route(packet(),config,native_catalog=snapshot(),allow_api=True,environment={'OPENAI_API_KEY':'synthetic'},decision_transport=fail)
        self.assertEqual(value['recommendation']['model'],'gpt-6-luna')
        self.assertEqual(value['provenance']['fallback_reason'],'network')

    def test_disabled_evaluator_model_blocks_paid_evaluation(self):
        config=self.config(['gpt-6.1-sol','gpt-6-astra'],decisions=runtime.DecisionsConfig(enabled=True))
        def forbidden(*_):self.fail('disabled evaluator model invoked')
        result=runtime.route(packet(),config,native_catalog=snapshot(),allow_api=True,
                             environment={'OPENAI_API_KEY':'synthetic'},decision_transport=forbidden)
        self.assertEqual(result['provenance']['fallback_reason'],'evaluator_model_disabled')
        self.assertEqual(result['observations']['evaluator_attempts'],0)

    def test_both_cli_entrypoints_enforce_persisted_allowlist(self):
        from contextlib import redirect_stdout
        import io
        with tempfile.TemporaryDirectory(dir=ROOT.parent) as directory:
            root=Path(directory);p=root/'packet.json';p.write_text(json.dumps(packet()))
            c=root/'config.json';c.write_text(json.dumps({'schema_version':1,'native':{'allowed_models':[]}}))
            for entry,args in [(runtime.main,[str(p),'--config',str(c),'--offline','--no-ledger']),
                               (core.main,[str(p),'--config',str(c)])]:
                output=io.StringIO()
                with redirect_stdout(output):status=entry(args)
                self.assertEqual(status,2);self.assertNotIn('recommendation',json.loads(output.getvalue()))

    def test_core_cli_does_not_load_or_invoke_disabled_evaluator(self):
        from contextlib import redirect_stdout
        import io
        with tempfile.TemporaryDirectory(dir=ROOT.parent) as directory:
            root=Path(directory);p=root/'packet.json';p.write_text(json.dumps(packet()))
            c=root/'config.json';c.write_text(json.dumps({'schema_version':1,'native':{'allowed_models':['gpt-6.1-sol','gpt-6-astra']}}))
            catalog.installation.atomic(root/'model-catalog.json',catalog.installation.encoded(snapshot()))
            original=core.os.environ.get
            def environment(key,*args):
                self.assertNotEqual(key,'OPENAI_API_KEY','disabled evaluator credential loaded')
                return original(key,*args)
            output=io.StringIO()
            with patch.object(core.os.environ,'get',side_effect=environment),patch.object(core.DecisionsProvider,'choose',side_effect=AssertionError('paid call')),redirect_stdout(output):
                status=core.main([str(p),'--config',str(c),'--provider','decisions','--allow-api'])
            self.assertEqual(status,0)
            self.assertEqual(json.loads(output.getvalue())['provenance']['fallback_reason'],'evaluator_model_disabled')

    def test_missing_explicit_config_never_reverts_to_unmanaged_policy(self):
        from contextlib import redirect_stdout
        import io
        with tempfile.TemporaryDirectory(dir=ROOT.parent) as directory:
            root=Path(directory);p=root/'packet.json';p.write_text(json.dumps(packet()))
            for entry,extra in [(core.main,[]),(runtime.main,['--no-ledger','--offline'])]:
                output=io.StringIO()
                with redirect_stdout(output):status=entry([str(p),'--config',str(root/'missing.json'),*extra])
                self.assertEqual(status,2);self.assertNotIn('recommendation',json.loads(output.getvalue()))

    def test_local_route_survives_no_native_models_and_cannot_fall_back_to_disabled_native(self):
        config=replace(configuration(local=True),native=runtime.NativeConfig([]))
        value=runtime.route(local_packet(),config,local_transport=local_catalog)
        self.assertEqual(value['recommendation']['adapter'],'local')
        def wire(method,*args):
            if method=='GET':return local_catalog()
            raise core.ProviderFailure('network')
        value=runtime.execute_local(local_packet(),config,transport=wire,allow_local_inference=True)
        self.assertIsNone(value['recommendation']);self.assertFalse(value['execution']['native_execution_started'])

    def test_configuration_round_trip_and_invalid_eligibility_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT.parent) as directory:
            store=dashboard.Store(directory);value,version=store.config()
            self.assertIsNone(value['native']['allowed_models'])
            value['native']['allowed_models']=[]
            saved,_=store.save(value,version);self.assertEqual(saved['native']['allowed_models'],[])
            for invalid in (True,['gpt-6-luna']*2,['sk-proj-synthetic-secret']):
                value['native']['allowed_models']=invalid
                with self.assertRaises(dashboard.ConfigValidationError):dashboard.safe_config(value)

if __name__=='__main__':unittest.main()
