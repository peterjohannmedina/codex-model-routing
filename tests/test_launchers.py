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

    def launch(self, *args, env=None):
        result = subprocess.run(['powershell.exe', '-NoProfile', '-File',
            str(ROOT / 'scripts' / 'Invoke-Routing.ps1'), '-PacketPath', str(self.packet),
            '-ConfigPath', str(self.config), '-PythonPath', sys.executable,
            '-CredentialPath', str(self.credential), *args], capture_output=True, text=True, timeout=20, env=env)
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

    def test_synthetic_loader_targets_child_only(self):
        make = self.fixture / 'make.ps1'
        make.write_text('param([string]$Path)\n$ErrorActionPreference="Stop"\n'
            'Import-Module (Join-Path $PSHOME "Modules\\Microsoft.PowerShell.Security\\Microsoft.PowerShell.Security.psd1")\n'
            '$s=ConvertTo-SecureString "offline-placeholder" -AsPlainText -Force\n'
            'try { ConvertFrom-SecureString $s | Set-Content -LiteralPath $Path -Encoding ascii } finally { $s.Dispose() }')
        made = subprocess.run(['powershell.exe', '-NoProfile', '-File', str(make), '-Path', str(self.credential)],
                               capture_output=True, text=True, timeout=10)
        self.assertEqual(made.returncode, 0, made.stderr)
        fake = self.fixture / 'fake.py'
        fake.write_text('import os,json\nprint(json.dumps({"dummy_matches":os.environ.get("OPENAI_API_KEY")=="offline-placeholder"}))')
        result = self.launch('-Provider', 'decisions', '-AllowApi', '-RoutingScriptPath', str(fake))
        self.assertTrue(result['dummy_matches'])


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
            for name in ('Invoke-Routing.ps1', 'Set-RoutingApiKey.ps1', 'routing_runtime.py', 'invoke-routing.sh'):
                self.assertTrue((skill / 'scripts' / name).exists())
            result = subprocess.run(['sh', str(skill / 'scripts' / 'invoke-routing.sh'),
                str(skill / 'assets' / 'routing-packet.example.json'), '--offline'],
                capture_output=True, text=True, env=env, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['provenance']['used_provider'], 'rules')
