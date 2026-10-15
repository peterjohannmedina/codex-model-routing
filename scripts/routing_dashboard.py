"""One loopback dashboard for the local routing config and redacted usage ledger."""
import argparse
from dataclasses import asdict
import hashlib
import hmac
from http.cookies import SimpleCookie, CookieError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import tempfile
import threading
import time
import webbrowser
from urllib.parse import urlsplit, parse_qs

import routing_decision as core
import routing_runtime as runtime
import routing_state as state
import routing_otel as otel

ASSETS = Path(__file__).resolve().parents[1] / 'assets/dashboard'


def config_version(config):
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()


def safe_config(raw):
    config = runtime.Config.parse(raw)
    for value in (config.local.model, config.local.base_url):
        if value and state.SECRET.search(value): raise ValueError('sensitive_configuration_value')
    if config.local.base_url:
        # URL shape is checked even while a provider is disabled; never echo URL credentials.
        parsed = urlsplit(config.local.base_url)
        parsed.port  # Validate a supplied port before persisting or echoing it.
        if (parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username is not None
                or parsed.password is not None or parsed.query or parsed.fragment): raise ValueError('invalid_url')
    return {'schema_version': 1, **asdict(config)}


class Store:
    def __init__(self, root):
        self.root = Path(root).resolve()
        if any((p / '.git').exists() for p in (self.root, *self.root.parents)):
            raise ValueError('state_must_be_outside_repository')
        self.path = self.root / 'config.json'
        self.lock = threading.Lock()
        self.otel_status = {'enabled': False, 'last_received_at': None, 'accepted_records': 0,
                            'ignored_records': 0, 'rejected_records': 0, 'exporter_configuration': 'unverified'}

    def config(self):
        config = safe_config(core.load_file(self.path)) if self.path.is_file() else safe_config({'schema_version': 1})
        version = config_version(config)
        return config, version

    def save(self, raw, expected):
        config = safe_config(raw)
        with self.lock:
            _, current = self.config()
            if not isinstance(expected, str) or not hmac.compare_digest(current, expected): raise FileExistsError()
            self.root.mkdir(parents=True, exist_ok=True)
            if os.name != 'nt': self.root.chmod(0o700)
            descriptor, name = tempfile.mkstemp(prefix='.config-', dir=self.root)
            try:
                with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                    json.dump(config, stream, indent=2, allow_nan=False)
                    stream.write('\n')
                os.replace(name, self.path)
            finally:
                Path(name).unlink(missing_ok=True)
        # Return the version of this write, not a later concurrent writer's state.
        return config, config_version(config)

    def snapshot(self, session=None):
        config, version = self.config()
        settings = state.LedgerSettings.parse(config['observability'])
        all_events = state.Ledger(self.root, settings).snapshot()
        sessions = sorted({e['session_id'] for e in all_events})
        events = [e for e in all_events if session is None or e['session_id'] == session]
        daily = {}
        for event in events:
            day = event.get('first_observed_at', event['observed_at'])[:10]
            daily.setdefault(day, []).append(event)
        return {'config': config, 'config_version': version, 'events': events,
                'totals': state.totals(events, settings), 'sessions': sessions, 'selected_session': session,
                'daily': [{'day': day, **state.totals(items, settings)} for day, items in sorted(daily.items())],
                'observed_at': state.dt.datetime.now(state.dt.timezone.utc).isoformat(),
                'coverage': {'router': 'instrumented_runtime_only', 'codex_exec': 'opt_in_json_stream',
                             'interactive_tui': 'unobserved', 'chatgpt_app': 'unsupported_no_verified_feed'},
                'refresh_seconds': 2}


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False
    def __init__(self, port, store, otel_capability=None):
        self.store = store
        self.otel_capability = otel.capability(otel_capability) if otel_capability is not None else None
        self.otel_lock = threading.Lock()
        self.store.otel_status['enabled'] = self.otel_capability is not None
        self.session = secrets.token_urlsafe(32)
        self.csrf = secrets.token_urlsafe(32)
        self.bootstrap = secrets.token_urlsafe(32)
        self.bootstrap_until = time.monotonic() + 300
        self.bootstrap_used = False
        self.bootstrap_lock = threading.Lock()
        self.launch_path = None
        self.connections = threading.BoundedSemaphore(16)
        super().__init__(('127.0.0.1', port), Handler)
        self.origin = 'http://127.0.0.1:' + str(self.server_port)
        self.cookie_name = 'routing_' + str(self.server_port)

    def create_launch_file(self):
        self.store.root.mkdir(parents=True, exist_ok=True)
        if os.name != 'nt': self.store.root.chmod(0o700)
        descriptor, name = tempfile.mkstemp(prefix='.dashboard-launch-', suffix='.html', dir=self.store.root)
        self.launch_path = Path(name)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            stream.write('<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=' +
                         self.origin + '/#authorize=' + self.bootstrap + '"><title>Opening local routing dashboard</title>Opening the local routing dashboard…')
        return self.launch_path

    def authorize(self, token):
        with self.bootstrap_lock:
            try:
                if (self.bootstrap_used or time.monotonic() > self.bootstrap_until
                        or not hmac.compare_digest(token, self.bootstrap)): return False
            except TypeError: return False
            self.bootstrap_used = True
            if self.launch_path:
                try: self.launch_path.unlink(missing_ok=True)
                except OSError: pass
            return True

    def server_close(self):
        if self.launch_path:
            try: self.launch_path.unlink(missing_ok=True)
            except OSError: pass
        super().server_close()

    def process_request(self, request, address):
        if not self.connections.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try: super().process_request(request, address)
        except BaseException:
            self.connections.release()
            raise

    def process_request_thread(self, request, address):
        try: super().process_request_thread(request, address)
        finally: self.connections.release()

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(5)
        return connection, address


class Handler(BaseHTTPRequestHandler):
    server_version = 'RoutingDashboard'
    def log_message(self, *_): pass  # No request, token, endpoint or payload logging.

    def reply(self, status, body, content_type='application/json', cookie=False):
        if not isinstance(body, bytes): body = json.dumps(body, allow_nan=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if cookie:
            self.send_header('Set-Cookie', self.server.cookie_name + '=' + self.server.session + '; HttpOnly; SameSite=Strict; Path=/')
        self.end_headers()
        self.wfile.write(body)

    def allowed(self, mutate=False, session=True, public=False):
        hosts = self.headers.get_all('Host', [])
        if hosts != [self.server.origin.removeprefix('http://')]: return False
        if not public and self.headers.get('Sec-Fetch-Site') not in (None, 'none', 'same-origin'): return False
        origin = self.headers.get('Origin')
        if len(self.headers.get_all('Origin', [])) > 1: return False
        if origin is not None and origin != self.server.origin: return False
        if session:
            try:
                cookie = SimpleCookie(self.headers.get('Cookie', ''))
                value = cookie.get(self.server.cookie_name)
                if not value or not hmac.compare_digest(value.value, self.server.session): return False
            except (CookieError, TypeError): return False
            # Cookies are host-scoped across ports. Require the browser-origin
            # capability too, so a cookie exposed to another local port alone
            # cannot read this dashboard or obtain its CSRF capability.
            try:
                if not hmac.compare_digest(self.headers.get('X-Routing-CSRF', ''), self.server.csrf): return False
            except TypeError: return False
        if mutate:
            try:
                if origin != self.server.origin or not hmac.compare_digest(self.headers.get('X-Routing-CSRF', ''), self.server.csrf): return False
            except TypeError: return False
        return True

    def do_GET(self):
        public = self.path in ('/', '/app.js', '/style.css')
        if not self.allowed(session=not public, public=public): return self.reply(403, {'error': 'forbidden_origin_or_session'})
        try:
            if public:
                filename, kind = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                                  '/style.css': ('style.css', 'text/css; charset=utf-8')}[self.path]
                return self.reply(200, (ASSETS / filename).read_bytes(), kind)
            if self.path == '/api/session': return self.reply(200, {'csrf': self.server.csrf})
            if urlsplit(self.path).path == '/api/state':
                query = parse_qs(urlsplit(self.path).query, strict_parsing=True)
                if set(query) - {'session'} or any(len(v) != 1 for v in query.values()): raise ValueError()
                session = state.identifier(query['session'][0]) if 'session' in query else None
                snapshot = self.server.store.snapshot(session)
                with self.server.otel_lock: snapshot['otel_receiver'] = dict(self.server.store.otel_status)
                return self.reply(200, snapshot)
            return self.reply(404, {'error': 'not_found'})
        except (ValueError, TypeError, RecursionError, OSError, state.sqlite3.Error):
            return self.reply(503, {'error': 'configuration_or_ledger_unavailable'})

    def do_POST(self):
        if self.path == '/v1/logs': return self.otel_logs()
        bootstrap = self.path == '/api/auth'
        if bootstrap:
            if not self.allowed(session=False) or self.headers.get('Origin') != self.server.origin:
                return self.reply(403, {'error': 'forbidden_origin_or_session'})
        elif not self.allowed(mutate=True): return self.reply(403, {'error': 'forbidden_origin_or_session'})
        if self.headers.get('Content-Type') != 'application/json' or self.headers.get('Transfer-Encoding'):
            return self.reply(415, {'error': 'json_required'})
        try:
            if len(self.headers.get_all('Content-Length', [])) != 1: raise ValueError()
            length = int(self.headers['Content-Length'])
            if not 1 <= length <= core.MAX_PACKET_BYTES: return self.reply(413, {'error': 'body_too_large'})
            raw = core.read_json(self.rfile.read(length).decode('utf-8'))
            if bootstrap:
                if raw != {} or not self.server.authorize(self.headers.get('X-Routing-Bootstrap', '')):
                    return self.reply(403, {'error': 'local_browser_authorization_required'})
                return self.reply(200, {'authorized': True, 'csrf': self.server.csrf}, cookie=True)
            if self.path == '/api/config':
                core.object_fields(raw, {'config', 'version'}, {'config', 'version'})
                _, version = self.server.store.save(raw['config'], raw['version'])
                return self.reply(200, {'saved': True, 'config_version': version})
            if self.path == '/api/ledger/clear':
                if raw != {'confirm': True}: raise ValueError()
                state.Ledger(self.server.store.root).clear()
                return self.reply(200, {'cleared': True})
            return self.reply(404, {'error': 'not_found'})
        except FileExistsError:
            return self.reply(409, {'error': 'configuration_changed_reload_before_saving'})
        except (ValueError, TypeError, UnicodeError, runtime.core.ProviderFailure, RecursionError):
            return self.reply(400, {'error': 'invalid_or_sensitive_configuration'})
        except (OSError, state.sqlite3.Error):
            return self.reply(503, {'error': 'storage_unavailable'})

    def otel_logs(self):
        secret = self.server.otel_capability
        if secret is None: return self.reply(404, {'error': 'not_found'})
        # Dedicated native exporter capability; browser cookie/CSRF never grants
        # ingest permission. Browser Origin/Fetch headers are always rejected.
        if (self.headers.get_all('Host', []) != [urlsplit(self.server.origin).netloc]
                or len(self.headers.get_all(otel.HEADER, [])) != 1
                or not hmac.compare_digest(self.headers.get(otel.HEADER, '').encode('utf-8'), secret.encode('ascii'))
                or self.headers.get('Origin') is not None or self.headers.get('Sec-Fetch-Site') is not None):
            return self.reply(403, {'error': 'forbidden_exporter'})
        if (self.headers.get('Content-Type') != 'application/json' or self.headers.get('Content-Encoding')
                or self.headers.get('Transfer-Encoding')):
            return self.reply(415, {'error': 'uncompressed_json_required'})
        try:
            if len(self.headers.get_all('Content-Length', [])) != 1: raise ValueError()
            length = int(self.headers['Content-Length'])
            if not 1 <= length <= otel.MAX_BYTES: return self.reply(413, {'error': 'body_too_large'})
            raw = self.rfile.read(length)
            if len(raw) != length: raise ValueError()
            config, _ = self.server.store.config()
            settings = state.LedgerSettings.parse(config['observability'])
            if settings.enabled:
                counts = otel.ingest(raw, state.Ledger(self.server.store.root, settings))
                with self.server.otel_lock:
                    status = self.server.store.otel_status
                    status['last_received_at'] = state.dt.datetime.now(state.dt.timezone.utc).isoformat()
                    for field in ('accepted', 'ignored', 'rejected'): status[field + '_records'] += counts[field]
            # Empty OTLP ExportLogsServiceResponse; never echo raw records.
            return self.reply(200, {})
        except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError):
            return self.reply(400, {'error': 'invalid_otlp_logs'})
        except (OSError, state.sqlite3.Error):
            return self.reply(503, {'error': 'storage_unavailable'})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir', type=Path, default=state.state_root())
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--open-browser', action='store_true', help='Open the private one-use launch file in your browser')
    parser.add_argument('--otel-token-file', type=Path, help='Opt-in private local exporter capability file; never a provider key')
    args = parser.parse_args(argv)
    try:
        if not 0 <= args.port <= 65535: raise ValueError()
        token = args.otel_token_file.read_text(encoding='ascii').strip() if args.otel_token_file else None
        server = Server(args.port, Store(args.state_dir), token)
        launch = server.create_launch_file()
        print('Routing dashboard: ' + server.origin + ' (local browser authorization required)', flush=True)
        print('Open this private one-use launch file within 5 minutes: ' + str(launch), flush=True)
        if args.open_browser:
            try:
                if not webbrowser.open(launch.as_uri()): print('Open the private launch file manually; no browser was available.', flush=True)
            except (OSError, webbrowser.Error): print('Open the private launch file manually; automatic browser opening was unavailable.', flush=True)
        try: server.serve_forever(poll_interval=0.5)
        except KeyboardInterrupt: pass
        finally: server.server_close()
        return 0
    except (OSError, ValueError):
        print('Dashboard unavailable: check the state directory and loopback port. No settings were changed.', flush=True)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
