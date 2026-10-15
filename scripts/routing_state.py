"""Bounded local-only usage ledger. All persisted fields are allowlisted metadata."""
from dataclasses import dataclass
from contextlib import contextmanager
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import time
import uuid

SECRET = re.compile(r'(?:sk-|gh[pousr]_|bearer|password|secret|token=|PRIVATE.KEY)', re.I)


def label(value):
    return value if (isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}', value)
                     and not SECRET.search(value)) else None


def identifier(value, allow_unassigned=True):
    if allow_unassigned and value == 'unassigned': return value
    if not isinstance(value, str) or len(value) > 64: raise ValueError('invalid_identifier')
    return str(uuid.UUID(value))


def count(value):
    return value if type(value) is int and 0 <= value <= 10**12 else None


def usage(value):
    if not isinstance(value, dict): return None
    result = {key: count(value.get(key)) for key in ('input_tokens', 'output_tokens', 'cached_input_tokens')}
    return result if any(v is not None for v in result.values()) else None


def timestamp(value):
    try:
        parsed = dt.datetime.fromisoformat(value) if isinstance(value, str) and len(value) <= 40 else None
        return parsed.astimezone(dt.timezone.utc).isoformat() if parsed and parsed.tzinfo else None
    except ValueError:
        return None


@dataclass(frozen=True)
class LedgerSettings:
    enabled: bool = True
    retention_days: int = 7
    max_events: int = 500
    local_input_usd_per_million: float | None = None
    local_output_usd_per_million: float | None = None

    @classmethod
    def parse(cls, raw):
        if not isinstance(raw, dict) or set(raw) - set(cls.__dataclass_fields__): raise ValueError('invalid_ledger_settings')
        obj = cls(**raw)
        if type(obj.enabled) is not bool: raise ValueError('invalid_ledger_settings')
        if type(obj.retention_days) is not int or not 1 <= obj.retention_days <= 30: raise ValueError('invalid_retention')
        if type(obj.max_events) is not int or not 10 <= obj.max_events <= 5000: raise ValueError('invalid_retention')
        for price in (obj.local_input_usd_per_million, obj.local_output_usd_per_million):
            if price is not None and (type(price) not in (int, float) or not math.isfinite(price) or not 0 <= price <= 10**6):
                raise ValueError('invalid_rate')
        return obj


def state_root():
    return Path(os.environ.get('CODEX_HOME', Path.home() / '.codex')) / 'routing'


def sanitize(raw):
    """No arbitrary text, endpoints, paths, payloads, headers, keys or hashes of prompts."""
    if not isinstance(raw, dict): raise ValueError('invalid_event')
    source = raw.get('source')
    if source not in ('router', 'codex_exec'): raise ValueError('invalid_source')
    result = {'source': source, 'session_id': identifier(raw.get('session_id')),
              'request_id': identifier(raw.get('request_id'), allow_unassigned=False), 'stage': raw.get('stage', 2)}
    if type(result['stage']) is not int or result['stage'] not in (0, 1, 2): raise ValueError('invalid_stage')
    for key in ('model', 'effort', 'adapter', 'override_model', 'override_effort', 'fallback_reason',
                'local_status', 'execution_status', 'model_source', 'mode', 'error', 'stream_status',
                'execution_adapter', 'execution_model', 'execution_effort'):
        result[key] = label(raw.get(key))
    for key in ('evaluator_attempts', 'downstream_attempts', 'command_items', 'elapsed_ms'):
        result[key] = count(raw.get(key))
    for key in ('local_enabled', 'decisions_enabled'):
        result[key] = raw.get(key) if type(raw.get(key)) is bool else None
    for key in ('evaluator_usage', 'downstream_usage'):
        result[key] = usage(raw.get(key))
    # Source-reported timestamps are optional; observation time is always local.
    result['source_timestamp'] = timestamp(raw.get('source_timestamp'))
    return result


class Ledger:
    def __init__(self, root, settings=LedgerSettings()):
        self.root, self.settings = Path(root), settings
        self.path = self.root / 'usage.sqlite3'

    @contextmanager
    def connect(self):
        self.root.mkdir(parents=True, exist_ok=True)
        if os.name != 'nt': self.root.chmod(0o700)
        connection = sqlite3.connect(self.path, timeout=0.25)
        connection.execute('PRAGMA secure_delete=ON')
        connection.execute('CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, updated REAL NOT NULL, body TEXT NOT NULL)')
        if os.name != 'nt': self.path.chmod(0o600)
        try:
            with connection: yield connection
        finally:
            connection.close()

    def prune(self, connection):
        connection.execute('DELETE FROM events WHERE updated < ?', (time.time() - self.settings.retention_days * 86400,))
        connection.execute('DELETE FROM events WHERE id NOT IN (SELECT id FROM events ORDER BY updated DESC, id LIMIT ?)', (self.settings.max_events,))

    def put(self, raw):
        if not self.settings.enabled: return False
        event = sanitize(raw)
        event_id = hashlib.sha256((event['source'] + ':' + event['request_id']).encode()).hexdigest()
        with self.connect() as connection:
            old = connection.execute('SELECT body FROM events WHERE id=?', (event_id,)).fetchone()
            if old:
                previous = json.loads(old[0])
                if previous['stage'] > event['stage']: return False
                # Late non-null usage enriches the same request; repeats never sum.
                for key, value in event.items():
                    if key not in raw: event[key] = previous.get(key)
                    elif value is None and key.endswith('_usage'): event[key] = previous.get(key)
                    elif key.endswith('_usage') and previous.get(key):
                        event[key] = {k: v if v is not None else previous[key].get(k) for k, v in value.items()}
                if all(previous.get(k) == v for k, v in event.items()): return False
            event['observed_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
            event['first_observed_at'] = previous.get('first_observed_at', event['observed_at']) if old else event['observed_at']
            connection.execute('INSERT INTO events VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET updated=excluded.updated, body=excluded.body',
                               (event_id, time.time(), json.dumps(event, allow_nan=False)))
            self.prune(connection)
        return True

    def snapshot(self):
        if not self.path.exists(): return []
        with self.connect() as connection:
            self.prune(connection)
            rows = connection.execute('SELECT body FROM events ORDER BY updated DESC, id').fetchall()
        result = []
        for row in rows:
            raw = json.loads(row[0])
            event = sanitize(raw)
            event['observed_at'] = timestamp(raw.get('observed_at'))
            event['first_observed_at'] = timestamp(raw.get('first_observed_at')) or event['observed_at']
            if not event['observed_at']: raise ValueError('invalid_observation_timestamp')
            result.append(event)
        return result

    def clear(self):
        if self.path.exists():
            with self.connect() as connection:
                connection.execute('DELETE FROM events')
                connection.commit()
                connection.execute('VACUUM')


def totals(events, settings=LedgerSettings()):
    result = {'requests': len(events), 'completed_executions': sum(e.get('execution_status') == 'completed' for e in events)}
    for name in ('evaluator', 'downstream'):
        reports = [e.get(name + '_usage') for e in events]
        result[name] = {key: {'known': sum((r.get(key) or 0) for r in reports if r),
                             'unknown_requests': sum(not r or r.get(key) is None for r in reports)}
                        for key in ('input_tokens', 'output_tokens')}
    evaluator_reports = [e['evaluator_usage']['input_tokens'] for e in events
                         if e.get('evaluator_usage') and e['evaluator_usage'].get('input_tokens') is not None]
    result['evaluator_base_cost_estimate_usd'] = sum(evaluator_reports) * 0.10 / 1_000_000 if evaluator_reports else None
    local = [e for e in events if e.get('execution_adapter', e.get('adapter')) == 'local' and e.get('downstream_usage')]
    rates = (settings.local_input_usd_per_million, settings.local_output_usd_per_million)
    known = [e for e in local if all(e['downstream_usage'].get(k) is not None for k in ('input_tokens', 'output_tokens'))]
    result['local_cost_estimate_usd'] = sum((e['downstream_usage']['input_tokens'] * rates[0] +
        e['downstream_usage']['output_tokens'] * rates[1]) / 1_000_000 for e in known) if known and None not in rates else None
    result['measured_billed_cost_usd'] = None
    return result
