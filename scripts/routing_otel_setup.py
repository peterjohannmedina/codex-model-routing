"""Plan opt-in user-level Codex telemetry; apply/undo require exact hash approval.

The default operation only prints a redacted plan. It never enables telemetry.
Existing OTel tables are deliberately not rewritten or replaced.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
import subprocess
import tempfile
import tomllib
import uuid

import routing_dashboard as dashboard
import routing_otel as otel


def sha(raw): return hashlib.sha256(raw).hexdigest()


def linked_target(path):
    try: info = path.lstat()
    except FileNotFoundError: return False
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0) & 0x400)


def windows_private(path, compare_path=None):
    """Read-only conservative ACL probe; inability to verify is a blocker."""
    try:
        command = ['powershell.exe', '-NoProfile', '-NonInteractive', '-File',
            str(Path(__file__).with_name('Test-RoutingTelemetryAcl.ps1')), '-LiteralPath', str(path)]
        if compare_path is not None: command += ['-ComparePath', str(compare_path)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=5)
        return result.returncode == 0 and json.loads(result.stdout) == {'private': True}
    except (OSError, ValueError, subprocess.TimeoutExpired): return False


def private_permissions(home, config_path, root):
    """Do not chmod/alter ACLs. All secret destinations must already be safe."""
    paths = [p for p in (home, root, config_path) if p.exists()]
    if os.name == 'nt': return all(windows_private(path) for path in paths)
    for path in paths:
        info = path.stat()
        if info.st_uid != os.getuid(): return False
        mode = stat.S_IMODE(info.st_mode)
        if path.is_dir():
            if mode & 0o022: return False  # other users must not replace files
        elif mode & 0o077: return False  # config will contain a local capability
    return True


def read_config(path):
    if linked_target(path): raise ValueError('linked_config_target_not_supported')
    raw = path.read_bytes() if path.is_file() else b''
    if len(raw) > 1048576: raise ValueError('configuration_too_large')
    parsed = tomllib.loads(raw.decode('utf-8-sig'))
    return raw, parsed


def plan(home, port=8765):
    home = Path(home).resolve()
    root = dashboard.Store(home / 'routing').root
    if not 1 <= port <= 65535: raise ValueError('invalid_port')
    path = home / 'config.toml'
    linked = linked_target(path)
    raw, config = (b'', {}) if linked else read_config(path)
    private = False if linked else private_permissions(home, path, root)
    blocked = ('linked_config_target_not_supported' if linked else
               'existing_otel_requires_manual_fanout_review' if 'otel' in config else
               'configuration_permissions_not_private_or_unverified' if not private else None)
    return {'ready': blocked is None, 'blocked_reason': blocked, 'private_permissions_verified': private,
            'requires_explicit_approval': True, 'config_sha256': None if linked else sha(raw),
            'config': str(home / 'config.toml'), 'state_dir': str(root),
            'endpoint': 'http://127.0.0.1:' + str(port) + '/v1/logs',
            'protocol': 'json', 'local_capability_file': str(root / 'otel-receiver.capability'),
            'accepted_codex_versions': list(otel.SUPPORTED_VERSIONS),
            'privacy': {'log_user_prompt': False, 'log_agent_responses': False,
                        'log_guardian_assessments': False, 'tool_result_max_bytes': 0},
            'preserved': ['existing config bytes', 'profiles', 'hooks', 'analytics', 'metrics/trace exporters',
                          'provider settings and credentials', 'existing ledger'],
            'scope': 'future Codex processes loading this user config; no service/autostart or network rule change',
            'warning': 'Native OTel may still send tool arguments, identities and errors in request memory; the receiver discards them before persistence.'}


def atomic(path, raw, mode=0o600):
    if linked_target(path): raise ValueError('linked_target_not_supported')
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(prefix='.otel-setup-', dir=path.parent)
    try:
        if os.name == 'nt' and not windows_private(Path(name), path if path.exists() else None):
            raise ValueError('temporary_file_acl_not_private_or_unverified')
        with os.fdopen(handle, 'wb') as stream:
            handle = None
            stream.write(raw)
        if os.name != 'nt': os.chmod(name, mode)
        if linked_target(path): raise ValueError('linked_target_not_supported')
        os.replace(name, path)
    finally:
        if handle is not None: os.close(handle)
        Path(name).unlink(missing_ok=True)


@contextmanager
def setup_lock(home):
    root = dashboard.Store(Path(home).resolve() / 'routing').root
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = root / '.otel-setup.lock'
    handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        os.close(handle)
        yield
    finally: path.unlink(missing_ok=True)


def apply(home, approved_sha, port=8765):
    with setup_lock(home): return apply_locked(home, approved_sha, port)


def apply_locked(home, approved_sha, port=8765):
    prepared = plan(home, port)
    if not prepared['ready']: raise ValueError(prepared['blocked_reason'])
    if approved_sha != prepared['config_sha256']: raise ValueError('configuration_changed_replan')
    path, root = Path(prepared['config']), Path(prepared['state_dir'])
    token_path, receipt_path = root / 'otel-receiver.capability', root / 'otel-setup-receipt.json'
    if token_path.exists() or receipt_path.exists(): raise ValueError('existing_setup_preserved')
    original, before = read_config(path)
    if sha(original) != approved_sha: raise ValueError('configuration_changed_replan')
    if not private_permissions(path.parent, path, root): raise ValueError('configuration_permissions_not_private_or_unverified')
    existed = path.exists()
    token = secrets.token_urlsafe(32)
    section = ('\n# codex-model-routing: explicitly approved local OTel logs\n[otel]\n'
               'log_user_prompt = false\nlog_agent_responses = false\nlog_guardian_assessments = false\n'
               'tool_result = { max_bytes = 0 }\nexporter = { otlp-http = { endpoint = ' + json.dumps(prepared['endpoint']) +
               ', protocol = "json", headers = { "x-routing-otel" = ' + json.dumps(token) + ' } } }\n')
    updated = original + section.encode('utf-8')
    after = tomllib.loads(updated.decode('utf-8-sig'))
    assert {k:v for k,v in after.items() if k != 'otel'} == before
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    backup = root / ('otel-config-before-' + str(uuid.uuid4()) + '.toml')
    mode = stat.S_IMODE(path.stat().st_mode) if existed else 0o600
    atomic(backup, original)
    config_written = False
    try:
        if sha(read_config(path)[0]) != approved_sha: raise ValueError('configuration_changed_replan')
        atomic(token_path, (token + '\n').encode('ascii'))
        receipt = {'config': str(path), 'backup': str(backup), 'before_sha256': sha(original),
                   'after_sha256': sha(updated), 'config_existed': existed, 'capability_sha256': sha((token + '\n').encode()),
                   'endpoint': prepared['endpoint'], 'accepted_codex_versions': list(otel.SUPPORTED_VERSIONS)}
        atomic(receipt_path, (json.dumps(receipt, indent=2) + '\n').encode())
        if sha(read_config(path)[0]) != approved_sha: raise ValueError('configuration_changed_replan')
        if not private_permissions(path.parent, path, root): raise ValueError('configuration_permissions_not_private_or_unverified')
        atomic(path, updated, mode)
        config_written = True
    except BaseException:
        if not config_written:
            token_path.unlink(missing_ok=True)
            receipt_path.unlink(missing_ok=True)
        raise
    return {'applied': True, 'config_sha256': sha(updated), 'endpoint': prepared['endpoint'],
            'capability_file': str(token_path), 'backup': str(backup),
            'next_step': 'Start the reviewed dashboard with --otel-token-file, then restart Codex. No model request or service was started.'}


def undo(home, approved_sha):
    with setup_lock(home): return undo_locked(home, approved_sha)


def undo_locked(home, approved_sha):
    path = Path(home).resolve() / 'config.toml'
    root = dashboard.Store(path.parent / 'routing').root
    receipt_path, token_path = root / 'otel-setup-receipt.json', root / 'otel-receiver.capability'
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    if receipt['config'] != str(path): raise ValueError('receipt_target_changed')
    current, _ = read_config(path)
    if not private_permissions(path.parent, path, root): raise ValueError('configuration_permissions_not_private_or_unverified')
    if approved_sha != sha(current) or sha(current) != receipt['after_sha256']:
        raise ValueError('configuration_changed_manual_undo_required')
    backup = Path(receipt['backup'])
    if backup.parent != root or not backup.name.startswith('otel-config-before-'): raise ValueError('invalid_backup')
    original = backup.read_bytes()
    if sha(original) != receipt['before_sha256']: raise ValueError('backup_changed')
    if sha(token_path.read_bytes()) != receipt['capability_sha256']: raise ValueError('capability_changed')
    if receipt['config_existed']: atomic(path, original, stat.S_IMODE(path.stat().st_mode))
    else: path.unlink()
    token_path.unlink()
    receipt_path.unlink()
    return {'undone': True, 'config_restored': True, 'backup_preserved': True,
            'next_step': 'Stop the receiver and restart Codex; an already-running process keeps its startup configuration.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--codex-home', type=Path, default=Path(os.environ.get('CODEX_HOME', Path.home() / '.codex')))
    parser.add_argument('--port', type=int, default=8765)
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--apply', action='store_true')
    action.add_argument('--undo', action='store_true')
    parser.add_argument('--approved-config-sha256')
    args = parser.parse_args(argv)
    try:
        result = (apply(args.codex_home, args.approved_config_sha256, args.port) if args.apply else
                  undo(args.codex_home, args.approved_config_sha256) if args.undo else plan(args.codex_home, args.port))
        print(json.dumps(result))
        return 0
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        # Parser errors can contain source lines/header values; never echo them.
        print(json.dumps({'error': 'telemetry_setup_failed_no_raw_configuration_logged'}))
        return 2


if __name__ == '__main__': raise SystemExit(main())
