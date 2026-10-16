"""User-scoped skill files, version receipts, backups and guarded rollback.

No global config/AGENTS, credential, telemetry setup, browser profile or ACL is
rewritten. Missing profile/prompt templates become user-owned and are preserved.
"""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time

import routing_platform as platform

SOURCE = Path(__file__).resolve().parents[1]
SKILL = Path('skills/codex-model-routing')


def sha(raw): return hashlib.sha256(raw).hexdigest()
def read_json(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def encoded(value): return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


class Paths:
    def __init__(self, user=None, codex=None):
        self.user = Path(user or Path.home()).expanduser().absolute()
        self.codex = Path(codex or (os.environ.get('CODEX_HOME') if user is None else None) or self.user/'.codex').expanduser().absolute()
        self.skill = self.codex / SKILL
        self.state = self.codex/'routing'
        self.service = self.state/'dashboard-service'
        self.receipt = self.service/'installation.json'
        self.run = self.service/'run.json'
        self.cap = self.service/'control.capability'
        self.helper = SOURCE/'scripts/Test-RoutingTelemetryAcl.ps1'

    def target(self, relative): return contained(self.codex, relative)


def contained(base, relative):
    base, name = Path(base).absolute(), Path(relative)
    if name.is_absolute() or '..' in name.parts or not name.parts: raise ValueError('unsafe_owned_path')
    target = base/name
    for path in (base, target, *target.parents):
        if path == base.parent: break
        if path.exists() or path.is_symlink():
            info = path.lstat()
            if path.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400: raise ValueError('linked_install_destination')
    if not target.resolve().is_relative_to(base.resolve()): raise ValueError('owned_path_escape')
    return target


def atomic(path, raw, executable=False):
    path = Path(path)
    if path.is_symlink() or (path.exists() and getattr(path.lstat(), 'st_file_attributes', 0) & 0x400):
        raise ValueError('linked_write_target')
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, name = tempfile.mkstemp(prefix='.routing-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream: stream.write(raw)
        if os.name != 'nt': os.chmod(name, 0o700 if executable else 0o600)
        os.replace(name, path)
    finally: Path(name).unlink(missing_ok=True)


def prepare(paths):
    contained(paths.codex, 'routing/dashboard-service/installation.json')
    resolved=paths.service.resolve()
    if any((parent/'.git').exists() for parent in (resolved,*resolved.parents)):
        raise ValueError('state_must_be_outside_repository')
    paths.service.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not platform.private(paths.service, paths.helper): raise ValueError('private_state_permissions_required')


@contextmanager
def lock(paths):
    prepare(paths)
    with (paths.service/'.operation.lock').open('a+b') as stream:
        stream.seek(0)
        if stream.read(1) == b'': stream.write(b'0'); stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError: raise ValueError('another_lifecycle_operation_is_running') from None
        try: yield
        finally:
            stream.seek(0)
            if os.name == 'nt': msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else: fcntl.flock(stream, fcntl.LOCK_UN)


def receipt(paths):
    if not paths.receipt.is_file(): return None
    result = read_json(paths.receipt)
    if result.get('schema_version') != 1 or result.get('codex_home') != str(paths.codex): raise ValueError('invalid_installation_receipt')
    for name, digest in result.get('files', {}).items():
        paths.target(name)
        if not isinstance(digest, str) or len(digest) != 64: raise ValueError('invalid_owned_manifest')
    return result


def integrity(paths, installed):
    changed = []
    for name, expected in installed['files'].items():
        path = paths.target(name)
        if not path.is_file() or sha(path.read_bytes()) != expected: changed.append(name)
    return changed


def source_files(source):
    source = Path(source).resolve()
    if not (source/'SKILL.md').is_file() or not (source/'VERSION').is_file():raise ValueError('incomplete_skill_source')
    try:
        top = subprocess.check_output(['git', '-C', str(source), 'rev-parse', '--show-toplevel'], stderr=subprocess.DEVNULL, text=True, timeout=5).strip()
        if Path(top).resolve() != source: raise ValueError()
        names = subprocess.check_output(['git', '-C', str(source), 'ls-files', '-z'], timeout=5).decode().split('\0')
    except (OSError, ValueError, subprocess.SubprocessError):
        names = [str(p.relative_to(source)).replace('\\','/') for p in source.rglob('*') if p.is_file()]
    roots = {'scripts','assets','agents','references','docs','tests','.github'}
    top_files = {'SKILL.md','README.md','CHANGELOG.md','LICENSE','VERSION','.gitignore','.gitattributes'}
    result = {}
    for name in filter(None, names):
        parts = Path(name).parts
        if (parts[0] not in roots and name not in top_files) or any(p.startswith('.env') or p in ('.git','__pycache__') or
            p.endswith(('.pyc','.dpapi','.capability')) or p.startswith(('usage.sqlite3','otel-config-before-','.dashboard-launch-')) or
            p in ('otel-setup-receipt.json','.otel-setup.lock') for p in parts): continue
        path = contained(source, name)
        if path.stat().st_size > 4194304: raise ValueError('source_file_too_large')
        result[name] = path.read_bytes()
        if len(result)>1024 or sum(map(len,result.values()))>33554432:raise ValueError('source_package_too_large')
    required = ('SKILL.md','VERSION','scripts/routing_bootstrap.py','scripts/routing_dashboard.py','scripts/routing_platform.py')
    if any(name not in result for name in required) or b'name: codex-model-routing' not in result['SKILL.md']:
        raise ValueError('incomplete_skill_source')
    return result


def shortcut_allowed(paths, installed):
    return {str(path.absolute()) for path, _kind, _body in platform.launcher_specs(paths.user, paths.codex, installed['python'], True, True)}


def install(paths, source=SOURCE, repair=False, shortcuts=None, login=None, port=None, adopt=False, plan_only=False):
    before = receipt(paths)
    raw = source_files(source)
    version = raw['VERSION'].decode().strip()
    revision = version + '+' + sha(encoded({name:sha(body) for name,body in raw.items()}))[:16]
    settings = {'shortcuts': bool(shortcuts if shortcuts is not None else (before or {}).get('shortcuts_enabled',False)),
                'login': bool(login if login is not None else (before or {}).get('login_startup',False))}
    planned = {str(SKILL/name):body for name,body in raw.items()}
    preserved = []
    for name in ('luna-efficient','sol-general','terra-general','sol-expert','astra-integrator'):
        relative = 'agents/' + name + '.toml'; path = paths.target(relative)
        if not path.exists():
            planned[relative] = raw['assets/agents/'+name+'.toml']
        else: preserved.append(relative)
    relative = 'prompts/codex-routing.md'; prompt = paths.target(relative)
    if not prompt.exists():
        planned[relative] = raw['assets/prompts/codex-routing.md']
    else: preserved.append(relative)
    if before and not repair:
        if any(name.startswith(str(SKILL)) for name in integrity(paths,before)):
            raise ValueError('owned_package_changed_use_repair_after_review')
    for name in planned:
        path = paths.target(name)
        if path.exists() and (not before or name not in before['files']) and name.startswith(str(SKILL)) and not adopt:
            raise ValueError('existing_unmanaged_skill_requires_review')
    desired = {'schema_version':1,'version':version,'revision':revision,'codex_home':str(paths.codex),
               'user_root':str(paths.user),'python':sys.executable,'port':port if port is not None else (before or {}).get('port',8765),
               'files':{name:sha(body) for name,body in planned.items() if name.startswith(str(SKILL))},'preserved_user_files':preserved,
               'shortcuts_enabled':settings['shortcuts'],'login_startup':settings['login'],
               'otel_receiver':(before or {}).get('otel_receiver',False),'shortcut_files':(before or {}).get('shortcut_files',{})}
    if not 0 <= desired['port'] <= 65535: raise ValueError('invalid_port')
    shortcuts_healthy = before and all(Path(n).is_file() and sha(Path(n).read_bytes())==v for n,v in before.get('shortcut_files',{}).items())
    shortcuts_healthy = shortcuts_healthy and all(p.is_file() for p,_,_ in platform.launcher_specs(paths.user,paths.codex,sys.executable,settings['shortcuts'],settings['login']))
    same = before and all(before.get(k)==v for k,v in desired.items() if k not in ('shortcut_files','preserved_user_files')) and not integrity(paths,before) and shortcuts_healthy and not before.get('shortcut_errors')
    if plan_only:return {'changed':not bool(same),'revision':revision}
    if same: return {'installed':True,'changed':False,'revision':revision,'preserved_user_files':preserved,**launcher_state(paths,before)}
    backup_id = str(time.time_ns()) + '-' + secrets.token_hex(4)
    backup = paths.service/'backups'/backup_id
    originals = {}
    for name in set(planned) | set((before or {}).get('files',{})):
        path = paths.target(name)
        originals[name] = path.read_bytes() if path.is_file() else None
    backup.mkdir(parents=True, mode=0o700)
    atomic(backup/'before.json',encoded(before))
    # Flat names avoid duplicating long installed paths inside Windows backups.
    saved={name:{'sha256':sha(body) if body is not None else None,'blob':format(index,'06x')}
           for index,(name,body) in enumerate(sorted(originals.items()))}
    atomic(backup/'originals.json',encoded(saved))
    for name, body in originals.items():
        if body is not None: atomic(backup/'files'/saved[name]['blob'],body)
    try:
        for name, body in planned.items():
            path = paths.target(name)
            if not path.is_file() or path.read_bytes()!=body: atomic(path,body,name.endswith('.sh'))
        # Remove only unchanged formerly-owned public files absent in the new source.
        for name, expected in (before or {}).get('files',{}).items():
            if name not in planned and name.startswith(str(SKILL)):
                path=paths.target(name)
                if path.is_file() and sha(path.read_bytes())==expected: path.unlink()
        desired['backup_id']=backup_id
        atomic(paths.receipt,encoded(desired))
        sync_shortcuts(paths,desired)
    except BaseException:
        for name, body in originals.items():
            path=paths.target(name)
            if body is None: path.unlink(missing_ok=True)
            else: atomic(path,body,name.endswith('.sh'))
        if before: atomic(paths.receipt,encoded(before))
        else: paths.receipt.unlink(missing_ok=True)
        raise
    return {'installed':True,'changed':True,'revision':revision,'backup_id':backup_id,'preserved_user_files':preserved,
            'shortcuts_requested':desired['shortcuts_enabled'],**launcher_state(paths,desired),
            'discovery':'installed SKILL.md; start a new Codex chat if its skill catalog has not refreshed'}


def sync_shortcuts(paths, installed):
    desired = platform.launcher_specs(paths.user,paths.codex,installed['python'],installed['shortcuts_enabled'],installed['login_startup'])
    previous = dict(installed.get('shortcut_files',{})); kept={}; errors=[]; conflicts=[]
    allowed = shortcut_allowed(paths,installed)
    for path, kind, body in desired:
        path=path.absolute(); name=str(path)
        if name not in allowed or path.resolve()!=path.absolute(): raise ValueError('unsafe_shortcut_destination')
        if path.is_file():
            if name not in previous or sha(path.read_bytes())!=previous[name]:conflicts.append(path.name);continue
            kept[name]=previous[name]; continue
        path.parent.mkdir(parents=True,exist_ok=True)
        try:
            if kind=='windows': platform.windows_shortcut(path,body,paths.skill/'scripts/New-RoutingShortcut.ps1')
            else: atomic(path,body,kind=='executable')
            kept[name]=sha(path.read_bytes())
        except (OSError,subprocess.SubprocessError):errors.append(path.name)
    for name, expected in previous.items():
        path=Path(name)
        if name not in kept and name in allowed and path.is_file() and sha(path.read_bytes())==expected: path.unlink()
    installed['shortcut_files']=kept
    installed['shortcut_errors']=errors
    installed['shortcut_conflicts']=conflicts
    atomic(paths.receipt,encoded(installed))


def launcher_state(paths,installed):
    requested=installed['login_startup']
    specs=platform.launcher_specs(paths.user,paths.codex,installed['python'],False,requested)
    owned=installed.get('shortcut_files',{})
    configured=bool(specs) and all(str(p.absolute()) in owned and p.is_file() and sha(p.read_bytes())==owned[str(p.absolute())] for p,_,_ in specs)
    return {'login_startup_requested':requested,'login_startup_configured':configured,
            'shortcut_errors':installed.get('shortcut_errors',[]),'shortcut_conflicts':installed.get('shortcut_conflicts',[])}


def rollback(paths):
    current=receipt(paths)
    if not current: raise ValueError('not_installed')
    backup=contained(paths.service/'backups',current['backup_id'])
    before=read_json(backup/'before.json')
    if integrity(paths,current): raise ValueError('owned_files_changed_rollback_refused')
    originals=read_json(backup/'originals.json')
    restored={}
    for name,record in originals.items():
        expected=record['sha256']
        if expected is not None:
            if len(record['blob'])!=6 or any(c not in '0123456789abcdef' for c in record['blob']):raise ValueError('invalid_backup_blob')
            data=contained(backup/'files',record['blob']).read_bytes()
            if sha(data)!=expected: raise ValueError('rollback_backup_changed')
            restored[name]=data
    for name,expected in current['files'].items():
        if name not in restored:
            path=paths.target(name)
            if path.is_file() and sha(path.read_bytes())==expected:path.unlink()
    for name,body in restored.items():atomic(paths.target(name),body,name.endswith('.sh'))
    if before:
        before['shortcut_files']=current.get('shortcut_files',{})
        atomic(paths.receipt,encoded(before));sync_shortcuts(paths,before)
    else:
        for name,expected in current.get('shortcut_files',{}).items():
            path=Path(name)
            if name in shortcut_allowed(paths,current) and path.is_file() and sha(path.read_bytes())==expected:path.unlink()
        paths.receipt.unlink()
    return {'rolled_back':True,'revision':before['revision'] if before else None,'backups_retained':True}


def prune_empty(path):
    if not path.is_dir() or path.is_symlink() or getattr(path.lstat(),'st_file_attributes',0)&0x400:return
    for child in path.iterdir():
        if child.is_dir() and not child.is_symlink() and not getattr(child.lstat(),'st_file_attributes',0)&0x400:prune_empty(child)
    try:path.rmdir()
    except OSError:pass


def uninstall(paths):
    installed=receipt(paths)
    if not installed:return {'uninstalled':True,'changed':False}
    kept=[]
    for name,expected in installed['files'].items():
        path=paths.target(name)
        if path.is_file() and sha(path.read_bytes())==expected:path.unlink()
        elif path.exists():kept.append(name)
    allowed=shortcut_allowed(paths,installed)
    for name,expected in installed.get('shortcut_files',{}).items():
        path=Path(name)
        if name in allowed and path.resolve()==path.absolute() and path.is_file() and sha(path.read_bytes())==expected:path.unlink()
    # Remove empty folders only; never follow links or recursively delete files.
    prune_empty(paths.skill)
    paths.receipt.unlink()
    return {'uninstalled':True,'preserved_modified_files':kept,'history_credentials_config_and_backups_preserved':True,
            'telemetry_exporter_unchanged':'If configured, use approved telemetry undo separately; uninstall never rewrites Codex config.'}
