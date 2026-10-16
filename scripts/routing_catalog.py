"""Account-scoped Codex picker discovery. No inference, login, or credential reads."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import threading
import time

import routing_installation as installation

MAX_BYTES = 1024 * 1024
MAX_MODELS = 128
TTL_SECONDS = 900
EFFORTS = {'low', 'medium', 'high', 'xhigh', 'max', 'ultra'}
_slot = threading.Lock()
ERRORS = {'invalid_catalog','codex_cli_unavailable','catalog_refresh_timeout','catalog_transport_error',
          'catalog_rpc_error','catalog_message_limit','chatgpt_login_required','catalog_model_limit',
          'invalid_catalog_cursor','catalog_page_limit','account_changed_during_refresh','catalog_refresh_busy',
          'unsupported_discovery_method','catalog_unavailable'}


class CatalogError(ValueError): pass


def cli_path():
    # A Windows shell shim needs process-tree ownership to guarantee timeout
    # cleanup. Require the native executable rather than weakening that bound.
    return shutil.which('codex.exe' if os.name=='nt' else 'codex')


def model_id(value):
    return isinstance(value, str) and bool(re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}', value)) and not re.search(r'(?i)(sk-|token|secret|password)', value)


def clock(): return datetime.now(timezone.utc).isoformat()


def read_json(path):
    path = Path(path)
    if path.is_symlink() or getattr(path.lstat(),'st_file_attributes',0)&0x400 or path.stat().st_size > MAX_BYTES: raise CatalogError('invalid_catalog')
    return json.loads(path.read_text(encoding='utf-8-sig'))


def cache_time(home):
    """Timestamp diagnostic only; cache contents never establish entitlement."""
    try:
        value = read_json(Path(home)/'models_cache.json')
        value = value.get('fetched_at')
        if not isinstance(value,str): return None
        datetime.fromisoformat(value.replace('Z','+00:00'))
        return value
    except (OSError, ValueError, TypeError, AttributeError): return None


def normalize_models(items):
    if not isinstance(items, list) or len(items) > MAX_MODELS: raise CatalogError('invalid_catalog')
    result = []
    seen = set()
    for item in items:
        if not isinstance(item, dict): raise CatalogError('invalid_catalog')
        if type(item.get('hidden',False)) is not bool: raise CatalogError('invalid_catalog')
        if item.get('hidden') is True: continue
        name = item.get('model')
        if not model_id(name) or name in seen: raise CatalogError('invalid_catalog')
        seen.add(name)
        efforts = item.get('supportedReasoningEfforts')
        if not isinstance(efforts, list) or len(efforts) > 16: raise CatalogError('invalid_catalog')
        supported = []
        for effort in efforts:
            if not isinstance(effort, dict): raise CatalogError('invalid_catalog')
            value = effort.get('reasoningEffort')
            if not isinstance(value, str) or not re.fullmatch('[a-z]{1,16}', value): raise CatalogError('invalid_catalog')
            if value not in supported: supported.append(value)
        modalities = item.get('inputModalities', ['text', 'image'])
        if not isinstance(modalities, list) or any(x not in ('text','image','audio') for x in modalities): raise CatalogError('invalid_catalog')
        # Names, descriptions, upgrade notices and account fields are untrusted;
        # display the validated public model ID instead of freeform provider text.
        result.append({'id': name, 'efforts': supported,
                       'default_effort': item.get('defaultReasoningEffort') if item.get('defaultReasoningEffort') in supported else None,
                       'input_modalities': sorted(set(modalities)),
                       'policy_supported': bool(set(supported) & EFFORTS)})
    return result


class Rpc:
    """Bounded stdio client for initialize/account/read/model/list only."""
    def __init__(self, command=None, timeout=8):
        executable = cli_path() if command is None else command
        if not executable: raise CatalogError('codex_cli_unavailable')
        self.deadline = time.monotonic() + timeout
        self.process = subprocess.Popen([str(executable), 'app-server'], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        self.messages = queue.Queue(maxsize=64)
        self.sequence = 0
        self.account_updates = 0
        def read():
            size = 0
            try:
                while True:
                    line = self.process.stdout.readline(MAX_BYTES + 1)
                    size += len(line)
                    if not line or len(line) > MAX_BYTES or size > MAX_BYTES:
                        self.messages.put_nowait(None); return
                    self.messages.put_nowait(json.loads(line))
            except (OSError, ValueError, queue.Full):
                try: self.messages.put_nowait(None)
                except queue.Full: pass
        try: threading.Thread(target=read, daemon=True).start()
        except RuntimeError:
            self.close()
            raise CatalogError('catalog_transport_error') from None

    def send(self, value):
        self.process.stdin.write((json.dumps(value)+'\n').encode())
        self.process.stdin.flush()

    def call(self, method, params):
        if method not in ('initialize', 'account/read', 'model/list'): raise CatalogError('unsupported_discovery_method')
        self.sequence += 1
        request_id = self.sequence
        self.send({'id':request_id, 'method':method, 'params':params})
        for _ in range(256):
            remaining = self.deadline-time.monotonic()
            if remaining <= 0: raise CatalogError('catalog_refresh_timeout')
            try: value = self.messages.get(timeout=remaining)
            except queue.Empty: raise CatalogError('catalog_refresh_timeout') from None
            if not isinstance(value, dict): raise CatalogError('catalog_transport_error')
            if value.get('method') == 'account/updated': self.account_updates += 1
            if value.get('id') == request_id:
                if 'error' in value or 'result' not in value: raise CatalogError('catalog_rpc_error')
                return value['result']
        raise CatalogError('catalog_message_limit')

    def close(self):
        try:
            self.process.stdin.close()
            self.process.terminate()
            self.process.wait(timeout=1)
        except (OSError, subprocess.TimeoutExpired):
            self.process.kill(); self.process.wait(timeout=1)
        finally:
            self.process.stdout.close()


def discover(home, rpc_factory=Rpc):
    rpc = rpc_factory()
    try:
        rpc.call('initialize', {'clientInfo':{'name':'codex-model-routing-catalog','version':'1.0.0'}})
        rpc.send({'method':'initialized','params':{}})
        account = rpc.call('account/read', {'refreshToken':False}).get('account')
        if not isinstance(account, dict) or account.get('type') != 'chatgpt': raise CatalogError('chatgpt_login_required')
        updates = rpc.account_updates
        items, cursor, cursors = [], None, set()
        for _ in range(8):
            page = rpc.call('model/list', {'limit':32,'includeHidden':False, 'cursor':cursor})
            if not isinstance(page, dict) or not isinstance(page.get('data'), list): raise CatalogError('invalid_catalog')
            items.extend(page['data'])
            if len(items)>MAX_MODELS: raise CatalogError('catalog_model_limit')
            cursor = page.get('nextCursor')
            if cursor is None: break
            if not isinstance(cursor,str) or len(cursor)>1024 or cursor in cursors: raise CatalogError('invalid_catalog_cursor')
            cursors.add(cursor)
        else: raise CatalogError('catalog_page_limit')
        after = rpc.call('account/read', {'refreshToken':False}).get('account')
        if after != account or rpc.account_updates != updates: raise CatalogError('account_changed_during_refresh')
        plan = account.get('planType')
        return {'schema_version':1,'source':'codex_app_server_model_list','queried_at':clock(),
                'auth_type':'chatgpt','plan_type':plan if plan in ('free','go','plus','pro','prolite','business','team','enterprise','edu') else 'unknown',
                'models':normalize_models(items), 'cache_fetched_at':cache_time(home),
                'scope_verified':False, 'last_error':None}
    finally: rpc.close()


def load(root):
    try:
        value = read_json(Path(root)/'model-catalog.json')
        if value.get('schema_version') != 1 or value.get('source') != 'codex_app_server_model_list': raise ValueError()
        # Re-validate private on-disk metadata before any policy use.
        value['models'] = normalize_models([{'model':m['id'],'supportedReasoningEfforts':[{'reasoningEffort':e} for e in m['efforts']],
            'defaultReasoningEffort':m['default_effort'],'inputModalities':m['input_modalities']} for m in value['models']])
        datetime.fromisoformat(value['queried_at'])
        value['last_error'] = value.get('last_error') if value.get('last_error') in ERRORS else None
        value['plan_type'] = value.get('plan_type') if value.get('plan_type') in ('free','go','plus','pro','prolite','business','team','enterprise','edu') else 'unknown'
        value['auth_type'] = 'chatgpt'
        return value
    except (OSError, ValueError, TypeError, KeyError, AttributeError): return None


def public(value, home=None):
    if not value: return {'status':'unverified','source':None,'queried_at':None,'models':[], 'last_error':None,'entitlement':'unverified'}
    result = {key:value.get(key) for key in ('source','queried_at','auth_type','plan_type','models','last_error','cache_fetched_at')}
    try: age = (datetime.now(timezone.utc)-datetime.fromisoformat(value['queried_at'])).total_seconds()
    except (ValueError, TypeError): age = -1
    result['status'] = 'stale' if age<0 or age>TTL_SECONDS else 'queried'
    if value.get('last_error'): result['status'] = 'error'
    result.update(entitlement='unverified', scope_verified=False, remote_freshness='unverified', freshness_seconds=TTL_SECONDS)
    return result


def refresh(root, home, rpc_factory=Rpc):
    if not _slot.acquire(blocking=False): raise CatalogError('catalog_refresh_busy')
    try:
        try:
            try: value = discover(home, rpc_factory)
            except (OSError,TypeError,AttributeError,KeyError,subprocess.SubprocessError): raise CatalogError('catalog_unavailable') from None
        except CatalogError as error:
            value = load(root)
            if value:
                value['last_error'] = str(error)
                installation.atomic(Path(root)/'model-catalog.json', installation.encoded(value))
            raise
        installation.atomic(Path(root)/'model-catalog.json', installation.encoded(value))
        return public(value, home)
    finally: _slot.release()


def restrict(packet, allowed, value, home=None):
    """Intersect persisted choices, discovered capabilities, and the caller's packet."""
    if allowed is None: return packet
    # Local providers remain separately controlled, including with no native models.
    from copy import deepcopy
    import routing_decision as core
    packet = deepcopy(packet)
    models = {m['id']:m for m in value['models']} if value and public(value,home)['status']=='queried' else {}
    required = packet.get('required_modalities', ['text'])
    if not isinstance(required,list) or not required or any(m not in ('text','image','audio') for m in required): raise core.RoutingError('invalid_required_modalities')
    catalog = packet.get('available_models')
    if not isinstance(catalog,dict): raise core.RoutingError('missing_catalog')
    packet['available_models'] = {name:[e for e in efforts if e in models[name]['efforts'] and e in EFFORTS]
        for name,efforts in catalog.items() if name in allowed and name in models and isinstance(efforts,list)
        and set(required)<=set(models[name]['input_modalities'])}
    packet['available_models'] = {m:e for m,e in packet['available_models'].items() if e}
    return packet
