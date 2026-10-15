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
import tempfile
import tomllib
import uuid

import routing_dashboard as dashboard
import routing_otel as otel


def sha(raw): return hashlib.sha256(raw).hexdigest()


def read_config(path):
    raw = path.read_bytes() if path.is_file() else b''
    if len(raw) > 1048576: raise ValueError('configuration_too_large')
    parsed = tomllib.loads(raw.decode('utf-8-sig'))
    return raw, parsed


def plan(home, port=8765):
    home = Path(home).resolve()
    root = dashboard.Store(home / 'routing').root
    if not 1 <= port <= 65535: raise ValueError('invalid_port')
    raw, config = read_config(home / 'config.toml')
    return {'ready': 'otel' not in config, 'blocked_reason': 'existing_otel_requires_manual_fanout_review' if 'otel' in config else None,
            'requires_explicit_approval': True, 'config_sha256': sha(raw),
            'config': str(home / 'config.toml'), 'state_dir': str(root),
            'endpoint': 'http://127.0.0.1:' + str(port) + '/v1/logs',
            'protocol': 'json', 'local_capability_file': str(root / 'otel-receiver.capability'),
            'accepted_codex_versions': [otel.SUPPORTED_VERSION],
            'privacy': {'log_user_prompt': False, 'log_agent_responses': False,
                        'log_guardian_assessments': False, 'tool_result_max_bytes': 0},
            'preserved': ['existing config bytes', 'profiles', 'hooks', 'analytics', 'metrics/trace exporters',
                          'provider settings and credentials', 'existing ledger'],
            'scope': 'future Codex processes loading this user config; no service/autostart or network rule change',
            'warning': 'Native OTel may still send tool arguments, identities and errors in request memory; the receiver discards them before persistence.'}


def atomic(path, raw, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(prefix='.otel-setup-', dir=path.parent)
    try:
        with os.fdopen(handle, 'wb') as stream: stream.write(raw)
        if os.name != 'nt': os.chmod(name, mode)
        os.replace(name, path)
    finally: Path(name).unlink(missing_ok=True)


@contextmanager
def setup_lock(home):
    root = dashboard.Store(Path(home).resolve() / 'routing').root
    root.mkdir(parents=True, exist_ok=True)
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
    if not prepared['ready']: raise ValueError('existing_otel_requires_manual_fanout_review')
    if approved_sha != prepared['config_sha256']: raise ValueError('configuration_changed_replan')
    path, root = Path(prepared['config']), Path(prepared['state_dir'])
    token_path, receipt_path = root / 'otel-receiver.capability', root / 'otel-setup-receipt.json'
    if token_path.exists() or receipt_path.exists(): raise ValueError('existing_setup_preserved')
    original, before = read_config(path)
    existed = path.exists()
    token = secrets.token_urlsafe(32)
    section = ('\n# codex-model-routing: explicitly approved local OTel logs\n[otel]\n'
               'log_user_prompt = false\nlog_agent_responses = false\nlog_guardian_assessments = false\n'
               'tool_result = { max_bytes = 0 }\nexporter = { otlp-http = { endpoint = ' + json.dumps(prepared['endpoint']) +
               ', protocol = "json", headers = { "x-routing-otel" = ' + json.dumps(token) + ' } } }\n')
    updated = original + section.encode('utf-8')
    after = tomllib.loads(updated.decode('utf-8-sig'))
    assert {k:v for k,v in after.items() if k != 'otel'} == before
    root.mkdir(parents=True, exist_ok=True)
    if os.name != 'nt': root.chmod(0o700)
    backup = root / ('otel-config-before-' + str(uuid.uuid4()) + '.toml')
    mode = stat.S_IMODE(path.stat().st_mode) if existed else 0o600
    atomic(backup, original)
    config_written = False
    try:
        if read_config(path)[0] != original: raise ValueError('configuration_changed_replan')
        atomic(token_path, (token + '\n').encode('ascii'))
        receipt = {'config': str(path), 'backup': str(backup), 'before_sha256': sha(original),
                   'after_sha256': sha(updated), 'config_existed': existed, 'capability_sha256': sha((token + '\n').encode()),
                   'endpoint': prepared['endpoint'], 'protocol_version': otel.SUPPORTED_VERSION}
        atomic(receipt_path, (json.dumps(receipt, indent=2) + '\n').encode())
        if read_config(path)[0] != original: raise ValueError('configuration_changed_replan')
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
