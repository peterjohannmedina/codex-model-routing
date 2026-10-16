"""Isolated user roots only. No keys, user config, autostart or browser is touched."""
from contextlib import redirect_stdout
import http.client
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import hashlib
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import routing_bootstrap as bootstrap
import routing_installation as installation
import routing_platform as platform


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='routing-otel-setup-bootstrap-',dir=ROOT.parent)
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        if os.name=='nt':
            result=subprocess.run(['powershell.exe','-NoProfile','-File',str(ROOT/'tests/set_private_acl_fixture.ps1'),
                '-LiteralPath',str(self.root)],capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,'private synthetic ACL fixture failed')
        self.user=self.root/'user with spaces';self.user.mkdir(mode=0o700)
        self.paths=installation.Paths(self.user)

    def install(self,source=ROOT,**options):
        with installation.lock(self.paths):return installation.install(self.paths,source,**options)

    def archive(self):
        source=self.root/'downloaded source';source.mkdir()
        for name,body in installation.source_files(ROOT).items():
            path=source/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body)
        return source

    def backup_file(self,identifier,name):
        backup=self.paths.service/'backups'/identifier
        record=installation.read_json(backup/'originals.json')[str(installation.SKILL/name)]
        return backup/'files'/record['blob']


class InstallTransactions(Fixture):
    def test_clean_install_idempotent_and_user_state_preserved(self):
        home=self.paths.codex
        (home/'agents').mkdir(parents=True)
        (home/'agents/luna-efficient.toml').write_text('# personal profile\n')
        (home/'config.toml').write_text('# unrelated synthetic config\n')
        (home/'AGENTS.md').write_text('Personal instructions\n')
        self.paths.state.mkdir()
        cipher=self.paths.state/'openai-key.dpapi';cipher.write_bytes(b'synthetic-unread-credential')
        original={p:p.read_bytes() for p in (home/'agents/luna-efficient.toml',home/'config.toml',home/'AGENTS.md',cipher)}
        result=self.install();self.assertTrue(result['changed'])
        receipt=installation.receipt(self.paths);backup=receipt['backup_id']
        self.assertTrue((self.paths.skill/'SKILL.md').is_file())
        self.assertFalse(self.paths.cap.exists());self.assertFalse(receipt['login_startup'])
        self.assertFalse(self.install()['changed'])
        self.assertEqual(installation.receipt(self.paths)['backup_id'],backup)
        self.assertTrue(all(p.read_bytes()==body for p,body in original.items()))
        self.assertTrue(all(name.startswith(str(installation.SKILL)) for name in receipt['files']))

    def test_update_rollback_and_uninstall_preserve_user_profiles_and_history(self):
        self.install();original=(self.paths.skill/'README.md').read_bytes()
        profile=self.paths.codex/'agents/sol-general.toml';profile.write_text('# customized after install\n')
        history=self.paths.state/'usage.sqlite3';history.write_bytes(b'synthetic-history-no-open')
        source=self.archive();(source/'VERSION').write_text('2099.1\n');(source/'README.md').write_bytes(original+b'\nnew fixture release\n')
        self.assertTrue(self.install(source)['changed'])
        self.assertNotEqual((self.paths.skill/'README.md').read_bytes(),original)
        with installation.lock(self.paths):self.assertTrue(installation.rollback(self.paths)['rolled_back'])
        self.assertEqual((self.paths.skill/'README.md').read_bytes(),original)
        with installation.lock(self.paths):result=installation.uninstall(self.paths)
        self.assertTrue(result['uninstalled']);self.assertFalse(self.paths.receipt.exists())
        self.assertEqual(profile.read_text(),'# customized after install\n')
        self.assertEqual(history.read_bytes(),b'synthetic-history-no-open')
        self.assertFalse(installation.uninstall(self.paths)['changed'])

    def test_modified_package_requires_repair_and_keeps_recovery_copy(self):
        self.install();readme=self.paths.skill/'README.md';readme.write_bytes(b'synthetic customized package file')
        with self.assertRaises(ValueError):self.install()
        result=self.install(repair=True)
        backup=self.backup_file(result['backup_id'],'README.md')
        self.assertEqual(backup.read_bytes(),b'synthetic customized package file')
        self.assertEqual(readme.read_bytes(),(ROOT/'README.md').read_bytes())

    def test_uninstall_keeps_modified_and_untracked_package_files(self):
        self.install();readme=self.paths.skill/'README.md';readme.write_bytes(b'user edit')
        extra=self.paths.skill/'personal-notes.txt';extra.write_text('user data')
        with installation.lock(self.paths):result=installation.uninstall(self.paths)
        self.assertIn(str(installation.SKILL/'README.md'),result['preserved_modified_files'])
        self.assertEqual(readme.read_bytes(),b'user edit');self.assertEqual(extra.read_text(),'user data')

    def test_downloaded_archive_and_explicit_legacy_adoption_rollback(self):
        source=self.archive();self.paths.skill.mkdir(parents=True)
        old=self.paths.skill/'README.md';old.write_bytes(b'previous unmanaged public package')
        with self.assertRaises(ValueError):self.install(source)
        self.install(source,adopt=True)
        with installation.lock(self.paths):installation.rollback(self.paths)
        self.assertEqual(old.read_bytes(),b'previous unmanaged public package')
        self.assertFalse(self.paths.receipt.exists())

    def test_changed_backup_refuses_rollback(self):
        self.install();source=self.archive();(source/'VERSION').write_text('2099.2\n')
        self.install(source);receipt=installation.receipt(self.paths)
        backup=self.backup_file(receipt['backup_id'],'README.md')
        backup.write_bytes(b'synthetic tampered backup')
        with self.assertRaises(ValueError):installation.rollback(self.paths)
        self.assertEqual(installation.receipt(self.paths)['version'],'2099.2')

    def test_shortcuts_and_login_are_explicit_fixture_only_and_removed(self):
        self.install(shortcuts=True,login=True)
        receipt=installation.receipt(self.paths)
        self.assertEqual(receipt.get('shortcut_errors'),[])
        self.assertTrue(receipt['shortcut_files'])
        self.assertTrue(all(Path(name).is_relative_to(self.user) for name in receipt['shortcut_files']))
        owned=list(receipt['shortcut_files'])
        self.install(shortcuts=False,login=False)
        self.assertTrue(all(not Path(name).exists() for name in owned))

    def test_unverified_private_state_blocks_install(self):
        with patch.object(platform,'private',return_value=False):
            with self.assertRaises(ValueError):self.install()
        self.assertFalse(self.paths.receipt.exists());self.assertFalse(self.paths.cap.exists())

    def test_repository_state_is_refused_before_creating_control_material(self):
        (self.user/'.git').mkdir()
        with self.assertRaises(ValueError):self.install()
        self.assertFalse(self.paths.cap.exists());self.assertFalse(self.paths.receipt.exists())

    def test_owned_path_escape_and_reparse_are_refused(self):
        for name in ('../outside','/outside'):
            with self.assertRaises(ValueError):self.paths.target(name)
        if os.name!='nt':
            self.paths.codex.mkdir();(self.paths.codex/'skills').symlink_to(self.root,target_is_directory=True)
            with self.assertRaises(ValueError):self.paths.target('skills/codex-model-routing/file')

    def test_platform_adapter_arguments_and_browser_bookmarks_are_not_edited(self):
        arguments=['/path with spaces/python','literal%file','$HOME','quote"here']
        value=platform.desktop_exec(arguments)
        self.assertIn('%%',value);self.assertIn('\\\\$',value)
        for target in ('darwin','linux','win32'):
            specs=platform.launcher_specs(self.user,self.paths.codex,sys.executable,True,True,platform=target)
            self.assertTrue(specs)
            self.assertTrue(all(Path(p).is_relative_to(self.user) for p,_,_ in specs))

    def test_supported_platform_wrapper_installs_in_isolated_root(self):
        if os.name=='nt':
            command=['powershell.exe','-NoProfile','-File',str(ROOT/'scripts/bootstrap.ps1'),
                '-Command','install','-PythonPath',sys.executable,'-UserRoot',str(self.user),'-SourceRoot',str(ROOT)]
        else:command=['sh',str(ROOT/'scripts/bootstrap.sh'),'install','--user-root',str(self.user),'--source-root',str(ROOT)]
        result=subprocess.run(command,capture_output=True,text=True,timeout=30,
                              env={**os.environ,'CODEX_ROUTING_PYTHON':sys.executable})
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertTrue(json.loads(result.stdout)['installed'])
        self.assertFalse(self.paths.run.exists());self.assertFalse(self.paths.cap.exists())

    def test_approved_telemetry_ignores_unrelated_edits_but_rejects_scope_changes(self):
        installation.prepare(self.paths)
        token='synthetic-private-exporter-only-for-fixture-123456789'
        cap=self.paths.state/'otel-receiver.capability'
        installation.atomic(cap,(token+'\n').encode())
        config=self.paths.codex/'config.toml'
        body=('model="gpt-6-luna"\n[otel]\nlog_user_prompt=false\nlog_agent_responses=false\n'
            'log_guardian_assessments=false\ntool_result={max_bytes=0}\n'
            'exporter={otlp-http={endpoint="http://127.0.0.1:8765/v1/logs",protocol="json",'
            'headers={x-routing-otel="'+token+'"}}}\n').encode()
        installation.atomic(config,body)
        installation.atomic(self.paths.state/'otel-setup-receipt.json',installation.encoded({'config':str(config),
            'endpoint':'http://127.0.0.1:8765/v1/logs','capability_sha256':hashlib.sha256(cap.read_bytes()).hexdigest()}))
        self.assertEqual(bootstrap.approved_otel(self.paths,8765),token)
        installation.atomic(config,b'# unrelated edit\n'+body)
        self.assertEqual(bootstrap.approved_otel(self.paths,8765),token)
        installation.atomic(config,body.replace(b'log_user_prompt=false',b'log_user_prompt=true'))
        with self.assertRaises(ValueError):bootstrap.approved_otel(self.paths,8765)

    def test_blocked_control_does_not_report_stopped_or_bypass_permissions(self):
        self.install()
        with patch.object(bootstrap,'controller',side_effect=PermissionError('synthetic blocked')):
            result=bootstrap.status(self.paths)
        self.assertIsNone(result['running']);self.assertIn('blocked',result['lifecycle_access'])


@unittest.skipIf(os.environ.get('ROUTING_SKIP_SOCKET_TESTS')=='1','Restricted local HTTP; CI exercises detached lifecycle')
class RealLifecycle(Fixture):
    def setUp(self):
        super().setUp();self.install(port=0)
        self.addCleanup(self.cleanup_server)

    def cleanup_server(self):
        try:bootstrap.stop(self.paths)
        except (OSError,ValueError):pass

    def test_clean_detached_start_reopen_identity_stop_and_update(self):
        with installation.lock(self.paths):first=bootstrap.start(self.paths)
        self.assertTrue(first['running'])
        with installation.lock(self.paths):again=bootstrap.start(self.paths)
        self.assertEqual(first['instance_id'],again['instance_id']);self.assertFalse(again['changed'])
        with installation.lock(self.paths):opened=bootstrap.open_dashboard(self.paths,browser=False)
        launch=Path(opened['private_launch_file']);self.assertTrue(launch.is_file())
        nonce=launch.read_text().split('/#authorize=',1)[1].split('"',1)[0]
        port=installation.read_json(self.paths.run)['port'];connection=http.client.HTTPConnection('127.0.0.1',port,timeout=2)
        origin='http://127.0.0.1:'+str(port)
        connection.request('POST','/api/auth','{}',{'Origin':origin,'Content-Type':'application/json','X-Routing-Bootstrap':nonce})
        response=connection.getresponse();response.read();connection.close()
        self.assertEqual(response.status,200);self.assertFalse(launch.exists())
        with installation.lock(self.paths):reopened=bootstrap.open_dashboard(self.paths,browser=False)
        self.assertEqual(first['instance_id'],reopened['instance_id'])
        self.assertTrue(Path(reopened['private_launch_file']).is_file())
        output=io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(bootstrap.main(['install','--user-root',str(self.user),'--source-root',str(ROOT)]),0)
        self.assertEqual(bootstrap.status(self.paths)['instance_id'],first['instance_id'])
        source=self.archive();(source/'VERSION').write_text('2099.3\n')
        with redirect_stdout(io.StringIO()):
            self.assertEqual(bootstrap.main(['update','--user-root',str(self.user),'--source-root',str(source)]),0)
        self.assertNotEqual(bootstrap.status(self.paths)['instance_id'],first['instance_id'])
        with installation.lock(self.paths):self.assertTrue(bootstrap.stop(self.paths)['stopped'])
        self.assertFalse(self.paths.run.exists());self.assertFalse(self.paths.cap.exists())

    def test_unknown_port_process_never_killed(self):
        import socket
        sock=socket.socket();sock.bind(('127.0.0.1',0));sock.listen();self.addCleanup(sock.close)
        receipt=installation.receipt(self.paths);receipt['port']=sock.getsockname()[1]
        installation.atomic(self.paths.receipt,installation.encoded(receipt))
        with installation.lock(self.paths):
            with self.assertRaises(ValueError):bootstrap.start(self.paths)
        self.assertFalse(self.paths.cap.exists())

    def test_command_exit_does_not_stop_background_server(self):
        result=subprocess.run([sys.executable,'-B',str(self.paths.skill/'scripts/routing_bootstrap.py'),
            'start','--user-root',str(self.user)],capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertTrue(json.loads(result.stdout)['running'])
        self.assertTrue(bootstrap.status(self.paths)['running'])

    def test_native_login_job_hosts_foreground_worker_until_authenticated_stop(self):
        process=subprocess.Popen([sys.executable,'-B',str(self.paths.skill/'scripts/routing_bootstrap.py'),
            '_login','--user-root',str(self.user)],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,**platform.detached())
        import time
        deadline=time.monotonic()+15;live=None
        while time.monotonic()<deadline:
            if self.paths.run.exists():
                live=bootstrap.controller(self.paths)
                if live:break
            time.sleep(.05)
        self.assertIsNotNone(live);self.assertIsNone(process.poll())
        bootstrap.stop(self.paths)
        self.assertEqual(process.wait(timeout=5),0)


if __name__=='__main__':unittest.main()
