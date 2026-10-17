"""Fixed diagnostics only; no host ACL scripts, GUI, sockets or credentials."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import tempfile
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import routing_bootstrap as bootstrap
import routing_platform as platform
import routing_installation as installation


class LauncherDiagnostics(unittest.TestCase):
    def probe(self, result=None, error=None):
        with patch.object(platform,'os',SimpleNamespace(name='nt')), \
             patch.object(platform.subprocess,'run',return_value=result,side_effect=error) as run:
            try: return platform.private(ROOT,ROOT/'scripts/Test-RoutingTelemetryAcl.ps1')
            finally:
                args,kwargs=run.call_args
                self.assertNotIn('-ExecutionPolicy',args[0]);self.assertEqual(kwargs['stdin'],subprocess.DEVNULL)

    def test_private_verdict_is_required_and_unsafe_still_refused(self):
        self.assertTrue(self.probe(SimpleNamespace(returncode=0,stdout='{"private":true}')))
        self.assertFalse(self.probe(SimpleNamespace(returncode=0,stdout='{"private":false,"reason":"other_principal_allow_rule"}')))
        for value in ('', 'not json', '{"private":true,"extra":"untrusted"}', '{"private":1}'):
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'private_state_probe_invalid_response'):
                self.probe(SimpleNamespace(returncode=0,stdout=value))

    def test_denial_timeout_and_unavailable_are_not_unsafe_acl_verdicts(self):
        failures=[(SimpleNamespace(returncode=1,stdout='',stderr='AuthorizationManager private/path secret'),None,'execution_failed'),
                  (None,subprocess.TimeoutExpired(['private/path'],5),'timeout'),
                  (None,PermissionError('private/path'),'unavailable'),
                  (SimpleNamespace(returncode=0,stdout='{"private":false,"reason":"acl_probe_unavailable"}'),None,'unavailable')]
        for result,error,code in failures:
            with self.subTest(code=code),self.assertRaisesRegex(ValueError,'^private_state_probe_'+code+'$'):
                self.probe(result,error)

    def test_pythonw_error_surfaces_only_fixed_code_and_hint_without_private_output(self):
        with patch.object(bootstrap.sys,'stdout',None),patch.object(bootstrap,'os',SimpleNamespace(name='nt')), \
             patch.object(bootstrap,'show_windows_error') as show:
            bootstrap.emit({'error':'private_state_probe_execution_failed','hint':'untrusted sk-private/path'})
            args=show.call_args.args
            self.assertEqual(args[0],'private_state_probe_execution_failed')
            self.assertNotIn('sk-private',json.dumps(args))
            self.assertIn('do not bypass',args[1])
            show.reset_mock();bootstrap.emit({'running':True,'private_launch_file':'private/path','token':'sk-private'})
            show.assert_not_called()
            bootstrap.emit({'error':'private/path sk-private'})
            self.assertEqual(show.call_args.args[0],'bootstrap_operation_failed')

    def test_cli_error_code_is_specific_and_never_calls_lifecycle_when_lock_check_denied(self):
        output=io.StringIO()
        with patch.object(bootstrap.installation,'lock',side_effect=ValueError('private_state_probe_execution_failed')), \
             patch.object(bootstrap,'open_dashboard') as open_dashboard,redirect_stdout(output):
            code=bootstrap.main(['open','--user-root',str(ROOT.parent/'synthetic-user')])
        self.assertEqual(code,2);open_dashboard.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())['error'],'private_state_probe_execution_failed')

    def test_detached_child_preserves_only_fixed_permission_failure_codes(self):
        with tempfile.TemporaryDirectory(dir=ROOT.parent) as directory:
            paths=installation.Paths(Path(directory)/'user')
            for message,expected in [('private_state_probe_execution_failed','private_state_probe_execution_failed'),
                                     ('sk-private/path must not escape','receiver_start_failed')]:
                with patch.object(bootstrap,'build_server',side_effect=ValueError(message)):
                    self.assertEqual(bootstrap.serve(paths,'synthetic-instance'),2)
                self.assertEqual(installation.read_json(paths.service/'ready.json')['error'],expected)
                self.assertNotIn('sk-private',(paths.service/'ready.json').read_text())

    def test_parent_start_preserves_fixed_child_denial_without_network_or_real_child(self):
        with tempfile.TemporaryDirectory(dir=ROOT.parent) as directory:
            paths=installation.Paths(Path(directory)/'user')
            installed={'python':sys.executable,'port':8765,'otel_receiver':False,'revision':'synthetic'}
            def child(*args,**kwargs):
                identity=args[0][-1]
                installation.atomic(paths.service/'ready.json',installation.encoded(
                    {'instance_id':identity,'error':'private_state_probe_execution_failed'}))
                return SimpleNamespace(wait=lambda **kwargs:0)
            with patch.object(installation,'receipt',return_value=installed),patch.object(installation,'integrity',return_value=[]), \
                 patch.object(bootstrap,'controller',return_value=None),patch.object(bootstrap.socket,'socket'), \
                 patch.object(bootstrap.platform,'detached',return_value={}),patch.object(bootstrap.subprocess,'Popen',side_effect=child):
                with self.assertRaisesRegex(ValueError,'^private_state_probe_execution_failed$'):
                    bootstrap.start(paths)

    def test_stop_marker_is_removed_after_old_control_capability(self):
        order=[]
        run=SimpleNamespace(is_file=lambda:True,unlink=lambda:order.append('run'))
        cap=SimpleNamespace(unlink=lambda **kwargs:order.append('cap'))
        with patch.object(installation,'read_json',return_value={'instance_id':'owned'}):
            bootstrap.cleanup_server(SimpleNamespace(run=run,cap=cap),'owned',None)
        self.assertEqual(order,['cap','run'])


if __name__=='__main__':unittest.main()
