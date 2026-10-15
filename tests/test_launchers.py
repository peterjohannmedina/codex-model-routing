import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform == 'win32', 'Windows PowerShell launcher tests')
class WindowsLauncher(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='portable routing ', dir=ROOT.parent)
        self.fixture = Path(self.temp.name)
        self.config = self.fixture / 'config.json'
        self.config.write_text(json.dumps({'schema_version': 1}))
        self.packet = ROOT / 'assets' / 'routing-packet.example.json'
        self.credential = self.fixture / 'synthetic.dpapi'
        self.credential.write_text('not-a-real-cipher')

    def tearDown(self):
        self.temp.cleanup()

    def run_launch(self, *args, env=None):
        return subprocess.run(['powershell.exe', '-NoProfile', '-File',
            str(ROOT / 'scripts' / 'Invoke-Routing.ps1'), '-PacketPath', str(self.packet),
            '-ConfigPath', str(self.config), '-PythonPath', sys.executable,
            '-CredentialPath', str(self.credential), *args], capture_output=True, text=True, timeout=20, env=env)

    def launch(self, *args, env=None):
        result = self.run_launch(*args, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_packaged_runtime_baseline_and_caps(self):
        result = self.launch('-Offline')
        self.assertEqual(result['provenance']['used_provider'], 'rules')
        result = self.launch('-Provider', 'decisions', '-AllowApi', '-MaxDecisionInputTokens', '1000',
                             '-MaxDecisionCostUsd', '0.01', '-PreflightOnly')
        self.assertFalse(result['preflight']['may_load_credential'])
        self.assertEqual(result['preflight']['block_reason'], 'verified_decisions_token_counter_unavailable')

    def test_single_override_does_not_decrypt_invalid_fixture(self):
        overrides = self.fixture / 'overrides.json'
        overrides.write_text(json.dumps({'model': 'gpt-6-luna', 'effort': 'high'}))
        result = self.launch('-Provider', 'decisions', '-AllowApi', '-OverridesPath', str(overrides))
        self.assertEqual(result['provenance']['resolution'], 'single_admissible_route')

    def test_preflight_preserves_configured_local_auth_without_inference(self):
        packet = json.loads(self.packet.read_text())
        packet['local_work_eligible'] = True
        packet['candidates'].append({'id': 'custom_local', 'action': 'delegate', 'adapter': 'local',
                                     'model': 'example-model', 'effort': 'default'})
        self.packet = self.fixture / 'local-packet.json'
        self.packet.write_text(json.dumps(packet))
        self.config.write_text(json.dumps({'schema_version': 1, 'decisions': {'enabled': True},
            'local': {'enabled': True, 'base_url': 'http://127.0.0.1:8000/v1', 'model': 'example-model',
                      'api_key_env': 'OPENAI_API_KEY', 'prefer_when_eligible': True}}))
        fake = self.fixture / 'fake-preflight.py'
        fake.write_text('import sys\nsys.path.insert(0,' + repr(str(ROOT / 'scripts')) + ')\n'
            'import routing_runtime as runtime\n'
            'def readiness(config, environment, *args, **kwargs):\n'
            '    if environment.get(config.api_key_env) != "offline-placeholder":\n'
            '        raise runtime.core.ProviderFailure("missing_key")\n'
            '    if kwargs.get("method", "GET") != "GET": raise AssertionError("inference forbidden")\n'
            '    return {"data":[{"id":"example-model"}]}\n'
            'runtime.local_request = readiness\n'
            'raise SystemExit(runtime.main(sys.argv[1:]))\n')
        result = self.launch('-PreflightOnly', '-ExecuteLocal', '-AllowLocalInference', '-AllowApi',
                             '-PreflightScriptPath', str(fake),
                             env=dict(os.environ, OPENAI_API_KEY='offline-placeholder'))
        self.assertEqual(result['preflight']['local_status'], 'ready')
        self.assertEqual(result['safe_result']['recommendation']['adapter'], 'local')
        self.assertEqual(result['preflight']['decisions_api_calls'], 0)
        self.assertFalse(result['preflight']['decisions_credential_accessed'])

    def make_synthetic_credential(self):
        make = self.fixture / 'make.ps1'
        make.write_text('param([string]$Path)\n$ErrorActionPreference="Stop"\n'
            'Import-Module (Join-Path $PSHOME "Modules\\Microsoft.PowerShell.Security\\Microsoft.PowerShell.Security.psd1")\n'
            '$s=ConvertTo-SecureString "offline-placeholder" -AsPlainText -Force\n'
            'try { ConvertFrom-SecureString $s | Set-Content -LiteralPath $Path -Encoding ascii } finally { $s.Dispose() }')
        made = subprocess.run(['powershell.exe', '-NoProfile', '-File', str(make), '-Path', str(self.credential)],
                               capture_output=True, text=True, timeout=10)
        self.assertEqual(made.returncode, 0, made.stderr)

    def test_synthetic_loader_targets_child_only(self):
        self.make_synthetic_credential()
        fake = self.fixture / 'fake.py'
        fake.write_text('import os,json\nprint(json.dumps({"dummy_matches":os.environ.get("OPENAI_API_KEY")=="offline-placeholder"}))')
        result = self.launch('-Provider', 'decisions', '-AllowApi', '-RoutingScriptPath', str(fake))
        self.assertTrue(result['dummy_matches'])

    def test_readiness_loss_preserves_required_route_failure(self):
        packet = json.loads(self.packet.read_text())
        packet.update(local_work_eligible=True, require_local=True)
        for effort in ('default', 'low'):
            packet['candidates'].append({'id': 'custom_' + effort, 'action': 'delegate', 'adapter': 'local',
                                         'model': 'example-model', 'effort': effort})
        self.packet = self.fixture / 'required-local.json'
        self.packet.write_text(json.dumps(packet))
        self.config.write_text(json.dumps({'schema_version': 1, 'decisions': {'enabled': True},
            'local': {'enabled': True, 'base_url': 'http://127.0.0.1:8000/v1', 'model': 'example-model',
                      'efforts': ['default', 'low']}}))
        prefix = ('import sys\nsys.path.insert(0,' + repr(str(ROOT / 'scripts')) + ')\n'
                  'import routing_runtime as runtime\n'
                  'def forbidden(*args, **kwargs): raise AssertionError("transport forbidden")\n'
                  'runtime.core.bounded_call = forbidden\n')
        preflight = self.fixture / 'ready.py'
        preflight.write_text(prefix +
            'runtime.local_request = lambda *args, **kwargs: {"data":[{"id":"example-model"}]}\n'
            'raise SystemExit(runtime.main(sys.argv[1:]))\n')
        actual = self.fixture / 'unavailable.py'
        actual.write_text(prefix +
            'def unavailable(*args, **kwargs): raise runtime.core.ProviderFailure("network")\n'
            'runtime.local_request = unavailable\n'
            'raise SystemExit(runtime.main(sys.argv[1:]))\n')
        for credential in ('absent', 'synthetic', 'invalid'):
            with self.subTest(credential=credential):
                if credential == 'absent': self.credential.unlink(missing_ok=True)
                elif credential == 'synthetic': self.make_synthetic_credential()
                else: self.credential.write_text('not-a-real-cipher')
                result = self.run_launch('-AllowApi', '-PreflightScriptPath', str(preflight),
                                         '-RoutingScriptPath', str(actual))
                self.assertEqual(result.returncode, 2, result.stderr)
                failure = json.loads(result.stdout)
                self.assertEqual(failure['error'], 'invalid_or_unsatisfied_routing_configuration')
                self.assertEqual(failure['reason'], 'require_local_unavailable')
                self.assertIsNone(failure['recommendation'])
                self.assertFalse(failure['execution_started'])


@unittest.skipUnless(sys.platform != 'win32' and shutil.which('sh') and shutil.which('rsync'), 'Unix clean install')
class UnixInstall(unittest.TestCase):
    def test_complete_clean_install_and_launcher(self):
        with tempfile.TemporaryDirectory(dir=ROOT.parent) as directory:
            user = Path(directory)
            source = user / 'source'
            shutil.copytree(ROOT, source, ignore=shutil.ignore_patterns('.git', '__pycache__'))
            (source / '.env').write_text('synthetic excluded fixture')
            (source / 'scripts' / 'synthetic.dpapi').write_text('synthetic excluded fixture')
            env = dict(os.environ, CODEX_HOME=str(user / '.codex'), CODEX_ROUTING_PYTHON=sys.executable)
            install = subprocess.run(['sh', str(source / 'scripts' / 'install.sh'), '--user-root', str(user)],
                                     capture_output=True, text=True, env=env, timeout=30)
            self.assertEqual(install.returncode, 0, install.stderr)
            skill = user / '.codex' / 'skills' / 'codex-model-routing'
            self.assertFalse((skill / '.env').exists())
            self.assertFalse((skill / 'scripts' / 'synthetic.dpapi').exists())
            self.assertTrue((user / '.codex' / 'AGENTS.md').exists())
            self.assertFalse((user / '.codex' / 'agents' / 'muse-worker.toml').exists())
            self.assertFalse((user / '.codex' / 'routing').exists())
            for name in ('Invoke-Routing.ps1', 'Set-RoutingApiKey.ps1', 'routing_runtime.py', 'invoke-routing.sh',
                         'routing_state.py', 'routing_dashboard.py', 'collect_codex_json.py',
                         'Resolve-RoutingPython.ps1', 'Start-RoutingDashboard.ps1'):
                self.assertTrue((skill / 'scripts' / name).exists())
            result = subprocess.run(['sh', str(skill / 'scripts' / 'invoke-routing.sh'),
                str(skill / 'assets' / 'routing-packet.example.json'), '--offline'],
                capture_output=True, text=True, env=env, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['provenance']['used_provider'], 'rules')
            collected = subprocess.run(['sh', str(skill / 'scripts' / 'invoke-routing.sh'), 'collect-codex',
                '--stream-id', '22222222-2222-4222-8222-222222222222'],
                input='{"type":"turn.completed","usage":{"input_tokens":0,"output_tokens":1}}\n',
                capture_output=True, text=True, env=env, timeout=15)
            self.assertEqual(collected.returncode, 0, collected.stderr)
            self.assertTrue((user / '.codex' / 'routing' / 'usage.sqlite3').exists())
