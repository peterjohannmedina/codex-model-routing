"""Actual CLI main paths with synthetic settings/keys and a fake Decisions wire."""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import routing_decision as core
import routing_runtime as runtime
import routing_state as state
import routing_catalog as catalog
from test_routing_decision import packet
from test_model_catalog import snapshot


def reply(body, selected='luna_high'):
    choices=json.loads(body)['questions'][0]['choices']
    return json.dumps({'answers':[{'type':'choice','name':'route','choice':selected,'confidence':0.9,
        'probabilities':[{'value':c['value'],'probability':int(c['value']==selected)} for c in choices]}],
        'usage':{'input_tokens':11,'output_tokens':0}}).encode()


class EntryPoints(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT.parent)
        self.root=Path(self.temp.name);self.packet=self.root/'packet.json';self.config=self.root/'config.json'
        self.packet.write_text(json.dumps(packet()))
        self.settings={'schema_version':1,'decisions':{'enabled':True,'api_key_env':'SYNTHETIC_DECISIONS_KEY',
            'timeout_seconds':0.5,'minimum_confidence':0.8}}
        self.save()
        self.environment=patch.dict(os.environ,{'CODEX_HOME':str(self.root/'unused'),
            'SYNTHETIC_DECISIONS_KEY':'offline-placeholder'},clear=True)
        self.environment.start()

    def tearDown(self):self.environment.stop();self.temp.cleanup()
    def save(self):self.config.write_text(json.dumps(self.settings))
    def invoke(self, entry, *args, transport=None):
        calls=[]
        def wire(body,key,timeout):
            calls.append(json.loads(body));self.assertEqual(key,'offline-placeholder');self.assertEqual(timeout,0.5)
            return transport(body) if transport else reply(body)
        output=io.StringIO()
        with patch.object(core,'post_decisions',side_effect=wire),patch('urllib.request.build_opener',side_effect=AssertionError('real HTTP forbidden')),redirect_stdout(output):
            code=entry([str(self.packet),'--config',str(self.config),*args])
        return code,json.loads(output.getvalue()),calls

    def test_saved_enabled_setting_reaches_both_entrypoints_and_records_one_evaluation(self):
        for entry in (runtime.main,core.main):
            code,result,calls=self.invoke(entry,'--allow-api')
            self.assertEqual(code,0);self.assertEqual(len(calls),1)
            self.assertEqual(result['recommendation']['id'],'luna_high')
            self.assertEqual(result['provenance']['requested_provider'],'decisions')
            self.assertEqual(result['provenance']['evaluator_status'],'succeeded')
            self.assertTrue(result['provenance']['evaluator_attempted']);self.assertTrue(result['provenance']['evaluator_succeeded'])
            row=next(e for e in state.Ledger(self.root).snapshot() if e['request_id']==result['ledger']['request_id'])
            self.assertEqual(row['evaluator_attempts'],1);self.assertEqual(row['evaluator_usage']['input_tokens'],11)
            self.assertEqual(row['requested_provider'],'decisions');self.assertEqual(row['used_provider'],'decisions')
            self.assertEqual(row['credential_source'],'environment');self.assertTrue(row['evaluator_succeeded'])

    def test_explicit_rules_and_no_spending_consent_never_call(self):
        for entry in (runtime.main,core.main):
            for args,reason in [(('--provider','rules','--allow-api'),'provider_disabled'),((),'api_not_authorized')]:
                code,result,calls=self.invoke(entry,*args)
                self.assertEqual(code,0);self.assertFalse(calls);self.assertFalse(result['provenance']['evaluator_attempted'])
                self.assertEqual(result['provenance']['evaluator_reason'],reason)

    def test_caps_apply_to_compatibility_entrypoint_before_key_access(self):
        self.settings['decisions']['max_cost_usd']=0.01;self.save()
        original=os.environ.get
        def no_key(name,*args):
            self.assertNotEqual(name,'SYNTHETIC_DECISIONS_KEY');return original(name,*args)
        with patch.object(os.environ,'get',side_effect=no_key):
            code,result,calls=self.invoke(core.main,'--allow-api')
        self.assertEqual(code,0);self.assertFalse(calls)
        self.assertEqual(result['provenance']['evaluator_reason'],'verified_decisions_cost_bound_unavailable')

    def test_allowlist_efforts_and_override_are_admitted_before_wire(self):
        self.settings['native']={'allowed_models':['gpt-6-luna','gpt-6.1-sol']};self.save()
        value=snapshot();value['models'][0]['efforts']=['low','medium']
        catalog.installation.atomic(self.root/'model-catalog.json',catalog.installation.encoded(value))
        code,result,calls=self.invoke(core.main,'--allow-api')
        self.assertEqual(code,0)
        self.assertEqual({c['value'] for c in calls[0]['questions'][0]['choices']},{'sol_medium','luna_high'})
        overrides=self.root/'overrides.json';overrides.write_text(json.dumps({'model':'gpt-6-luna','effort':'high'}))
        code,result,calls=self.invoke(core.main,'--allow-api','--overrides',str(overrides))
        self.assertEqual(code,0);self.assertFalse(calls)
        self.assertEqual(result['provenance']['evaluator_status'],'single_candidate')
        overrides.write_text(json.dumps({'model':'gpt-6-astra'}))
        code,result,calls=self.invoke(core.main,'--allow-api','--overrides',str(overrides))
        self.assertEqual(code,2);self.assertFalse(calls);self.assertNotIn('recommendation',result)

    def test_credential_loader_failure_retains_requested_provider_and_records_reason(self):
        code,result,calls=self.invoke(runtime.main,'--allow-api','--credential-error','local_credential_error')
        self.assertEqual(code,0);self.assertFalse(calls)
        self.assertEqual(result['provenance']['requested_provider'],'decisions')
        self.assertEqual(result['provenance']['evaluator_status'],'blocked')
        self.assertEqual(result['provenance']['evaluator_reason'],'local_credential_error')
        row=state.Ledger(self.root).snapshot()[0]
        self.assertTrue(row['decisions_enabled']);self.assertEqual(row['evaluator_reason'],'local_credential_error')

    def test_refusal_network_and_untrusted_failure_reasons_are_sanitized_fallbacks(self):
        for reason,transport in [('refusal',lambda _:b'{"answers":[{"type":"refusal","name":"route"}]}'),
                                 ('network',lambda _:(_ for _ in ()).throw(core.ProviderFailure('network'))),
                                 ('provider_error',lambda _:(_ for _ in ()).throw(core.ProviderFailure('private key/path must never escape')))]:
            code,result,calls=self.invoke(core.main,'--allow-api',transport=transport)
            self.assertEqual(code,0);self.assertEqual(len(calls),1)
            self.assertEqual(result['recommendation']['id'],'sol_medium')
            self.assertEqual(result['provenance']['evaluator_status'],'fallback')
            self.assertTrue(result['provenance']['evaluator_fallback']);self.assertFalse(result['provenance']['evaluator_succeeded'])
            self.assertEqual(result['provenance']['evaluator_reason'],reason)
            self.assertNotIn('private key/path',json.dumps(state.Ledger(self.root).snapshot()))

    def test_real_python_script_entrypoints_use_config_without_provider_flag(self):
        # Run each actual __main__ path in a subprocess, replacing only its wire.
        runner=self.root/'fake_wire_runner.py'
        runner.write_text('import sys,runpy,json\nsys.path.insert(0,'+repr(str(ROOT/'scripts'))+')\n'
            'import routing_decision as core\n'
            'def fake(body,key,timeout):\n'
            ' assert key=="offline-placeholder"\n'
            ' ids=[c["value"] for c in json.loads(body)["questions"][0]["choices"]]\n'
            ' return json.dumps({"answers":[{"type":"choice","name":"route","choice":"luna_high","confidence":0.9,"probabilities":[{"value":i,"probability":int(i=="luna_high")} for i in ids]}]}).encode()\n'
            'core.post_decisions=fake\n'
            'import urllib.request\nurllib.request.build_opener=lambda *a,**k: (_ for _ in ()).throw(AssertionError("HTTP forbidden"))\n'
            'sys.argv=sys.argv[1:]\nrunpy.run_path(sys.argv[0],run_name="__main__")\n')
        for name in ('routing_runtime.py','routing_decision.py'):
            result=subprocess.run([sys.executable,'-B',str(runner),str(ROOT/'scripts'/name),str(self.packet),
                '--config',str(self.config),'--allow-api'],capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['provenance']['evaluator_status'],'succeeded')


if __name__=='__main__':unittest.main()
