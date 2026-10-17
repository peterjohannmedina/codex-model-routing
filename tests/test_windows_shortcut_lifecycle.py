"""Real .lnk/pythonw lifecycle in a private synthetic root on Windows CI only."""
import http.client
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest

from test_bootstrap import Fixture, bootstrap, installation, platform, ROOT


@unittest.skipUnless(sys.platform=='win32','Windows shortcut lifecycle')
@unittest.skipIf(os.environ.get('ROUTING_SKIP_SOCKET_TESTS')=='1','Restricted host; mandatory Windows CI')
class WindowsShortcutLifecycle(Fixture):
    def test_shortcut_open_survives_launcher_exit_reuses_instance_and_recovers_stale_state(self):
        self.install(port=0)
        self.addCleanup(self.stop_owned)
        pythonw=Path(sys.executable).with_name('pythonw.exe')
        self.assertTrue(pythonw.is_file(),'Windows package must support its actual hidden interpreter')
        shortcut=self.root/'Dashboard with spaces.lnk'
        arguments=[str(Path(sys.executable)),'-B',str(self.paths.skill/'scripts/routing_bootstrap.py'),
            'open','--user-root',str(self.user),'--no-browser']
        platform.windows_shortcut(shortcut,arguments,ROOT/'scripts/New-RoutingShortcut.ps1')

        def launch():
            # Same OS shortcut activation as the desktop. The sole fixture-only
            # addition is --no-browser, avoiding a CI user's real browser/profile.
            literal=str(shortcut).replace("'","''")
            result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',
                "$p=Start-Process -FilePath '"+literal+"' -PassThru; if(-not $p.WaitForExit(30000)){$p.Kill(); exit 124}; exit $p.ExitCode"],
                capture_output=True,text=True,timeout=40)
            if result.returncode != 0:
                # Same pythonw target/arguments, now with captured streams so a
                # fixed bootstrap error can be diagnosed without automating a
                # modal dialog. This never changes permissions or skips checks.
                diagnostic=subprocess.run([str(pythonw),*arguments[1:]],capture_output=True,text=True,timeout=25)
                try: fixed=json.loads(diagnostic.stdout).get('error','no_error')
                except (ValueError,TypeError): fixed='diagnostic_unavailable'
                self.fail('shortcut_exit='+str(result.returncode)+'; same_pythonw_diagnostic='+fixed)
            live=bootstrap.controller(self.paths)
            self.assertTrue(live,'Server must survive shortcut/launcher command exit')
            return live

        first=launch();again=launch()
        self.assertEqual(first['instance_id'],again['instance_id'])
        self.authenticate_data()
        stale_run=self.paths.run.read_bytes();stale_cap=self.paths.cap.read_bytes()
        bootstrap.stop(self.paths)
        self.assertFalse(self.paths.run.exists())
        # Simulate leftovers from an unclean exit without killing any process.
        installation.atomic(self.paths.run,stale_run);installation.atomic(self.paths.cap,stale_cap)
        restarted=launch()
        self.assertNotEqual(first['instance_id'],restarted['instance_id'])
        self.authenticate_data()

    def authenticate_data(self):
        opened=bootstrap.controller(self.paths,'open')
        file=Path(opened['launch_file'])
        nonce=file.read_text(encoding='utf-8').split('/#authorize=',1)[1].split('"',1)[0]
        port=installation.read_json(self.paths.run)['port']
        origin='http://127.0.0.1:'+str(port)
        connection=http.client.HTTPConnection('127.0.0.1',port,timeout=3)
        try:
            connection.request('POST','/api/auth','{}',{'Origin':origin,'Content-Type':'application/json','X-Routing-Bootstrap':nonce})
            response=connection.getresponse();auth=json.loads(response.read());cookie=response.getheader('Set-Cookie').split(';',1)[0]
            self.assertEqual(response.status,200);self.assertFalse(file.exists())
            connection.request('GET','/api/state',headers={'Cookie':cookie,'X-Routing-CSRF':auth['csrf']})
            response=connection.getresponse();state=json.loads(response.read())
            self.assertEqual(response.status,200);self.assertIn('events',state);self.assertIn('config',state)
        finally:connection.close()

    def stop_owned(self):
        try:bootstrap.stop(self.paths)
        except (OSError,ValueError):pass


if __name__=='__main__':unittest.main()
