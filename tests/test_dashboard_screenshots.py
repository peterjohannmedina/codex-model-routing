"""Offline checks for the public screenshot fixture and exact reviewed sources."""
import json
from pathlib import Path
import tempfile
import unittest

from dashboard_screenshot_fixture import ROOT, load_fixture, reviewed_assets, seed_fixture


class ScreenshotFixture(unittest.TestCase):
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
