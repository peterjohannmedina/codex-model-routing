"""Offline checks for the public screenshot fixture and exact reviewed sources."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from dashboard_screenshot_fixture import ROOT, load_fixture, reviewed_assets, seed_fixture


class ScreenshotFixture(unittest.TestCase):
    def test_published_images_match_capture_provenance(self):
        directory = ROOT / 'docs/images'
        provenance = json.loads((directory / 'dashboard-provenance.json').read_text(encoding='utf-8'))
        self.assertTrue(provenance['synthetic'])
        self.assertFalse(provenance['real_user_data'])
        self.assertEqual(provenance['provider_calls'], 0)
        self.assertEqual(provenance['external_browser_requests'], 0)
        self.assertEqual(len(provenance['images']), 3)
        for name, metadata in provenance['images'].items():
            self.assertEqual(Path(name).name, name)
            self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(), metadata['sha256'])

    def test_capture_uses_exact_reviewed_sources(self):
        self.assertEqual(len(reviewed_assets()), 7)

    def test_synthetic_fixture_renders_expected_totals_without_providers(self):
        fixture = load_fixture()
        with tempfile.TemporaryDirectory(dir=ROOT.parent) as directory:
            snapshot = seed_fixture(Path(directory), fixture).snapshot()
            self.assertEqual(snapshot['observed_at'], fixture['snapshot_time'])
            self.assertEqual(snapshot['totals']['requests'], 8)
            self.assertEqual(snapshot['totals']['completed_executions'], 4)
            self.assertEqual(snapshot['totals']['evaluator']['input_tokens']['known'], 1070)
            self.assertEqual(snapshot['totals']['downstream']['input_tokens']['known'], 23320)
            self.assertEqual(snapshot['totals']['downstream']['input_tokens']['unknown_requests'], 4)
            self.assertEqual(len(snapshot['sessions']), 2)
            exported = json.dumps(snapshot)
            for forbidden in ('prompt', 'command_text', 'output_text', 'api_key_value', str(Path.home())):
                self.assertNotIn(forbidden, exported)


if __name__ == '__main__':
    unittest.main()
