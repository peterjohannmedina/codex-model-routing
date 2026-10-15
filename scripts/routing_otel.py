"""Metadata-only adapter for Codex 0.162.1 OTLP/HTTP JSON log export.

Raw records exist in bounded request memory only. Never log or persist them.
Session configuration and model-response observations are separate from exec turns.
"""
import datetime as dt
import json
import re
import uuid

import routing_state as state

MAX_BYTES = 1048576
MAX_RECORDS = 512
SUPPORTED_VERSION = '0.162.1'
HEADER = 'X-Routing-OTel'


def capability(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{43,128}', value):
        raise ValueError('invalid_local_capability')
    return value


def scalar(value):
    if not isinstance(value, dict) or len(value) != 1: return None
    for key in ('stringValue', 'intValue'):
        if key in value and type(value[key]) in (str, int): return value[key]
    return None


def attributes(record):
    items = record.get('attributes', [])
    if not isinstance(items, list) or len(items) > 96: raise ValueError('attribute_limit')
    # Only these fields can leave the parser. Ignore resource identities, bodies,
    # headers, prompts, paths, error text, tool arguments/results and all others.
    allowed = {'event.name', 'event.kind', 'event.timestamp', 'conversation.id', 'app.version',
               'model', 'reasoning_effort', 'model_reasoning_effort',
               'input_token_count', 'output_token_count', 'cached_token_count', 'error.message'}
    result = {}
    for item in items:
        if not isinstance(item, dict): raise ValueError('invalid_attribute')
        key = item.get('key')
        if key not in allowed: continue
        if key in result: raise ValueError('duplicate_attribute')
        # Keep only presence for a freeform error; its contents are never copied.
        result[key] = True if key == 'error.message' else scalar(item.get('value'))
    return result


def token_count(value):
    if isinstance(value, str) and re.fullmatch(r'[0-9]{1,13}', value): value = int(value)
    return state.count(value)


def metadata(record):
    if not isinstance(record, dict): raise ValueError('invalid_record')
    attrs = attributes(record)
    if attrs.get('app.version') != SUPPORTED_VERSION: return None
    name = attrs.get('event.name')
    if name not in ('codex.conversation_starts', 'codex.sse_event'): return None
    session = state.identifier(attrs.get('conversation.id'), allow_unassigned=False)
    event = {'source': 'codex_otel', 'session_id': session, 'session_source': 'codex_thread',
             'stage': 2, 'adapter': 'native', 'model': state.label(attrs.get('model')),
             'evaluator_usage': {'input_tokens': 0, 'output_tokens': 0}, 'evaluator_attempts': 0}
    if name == 'codex.conversation_starts':
        identity = 'session-configuration'
        event.update(mode='otel_session', model_source='startup_configuration',
                     execution_status='session_observed', effort=state.label(attrs.get('reasoning_effort')))
    else:
        if attrs.get('event.kind') != 'response.completed' or 'error.message' in attrs: return None
        # The same source also emits a generic SSE notification without usage.
        # Ignore it rather than counting one response twice.
        if not {'input_token_count', 'output_token_count'} & attrs.keys(): return None
        nano = record.get('timeUnixNano')
        clock = 'source'
        # Codex's OpenTelemetry 0.31 tracing bridge does not set event time.
        # Its SDK supplies observedTimeUnixNano at emission; retain that stable
        # exported timestamp for batch replay dedup, never receiver arrival time.
        if nano in (None, '', 0, '0'):
            nano = record.get('observedTimeUnixNano')
            clock = 'sdk-observed'
        if type(nano) is int: nano = str(nano)
        if not isinstance(nano, str) or not re.fullmatch(r'[1-9][0-9]{0,19}', nano):
            raise ValueError('stable_source_timestamp_required')
        seconds = int(nano) // 1_000_000_000
        if not 0 < seconds <= 32503680000: raise ValueError('invalid_source_timestamp')
        identity = 'model-response:' + clock + ':' + nano
        event.update(mode='otel_response', model_source='otel_response_metadata',
                     execution_status='response_observed', effort=state.label(attrs.get('model_reasoning_effort')),
                     downstream_attempts=1, downstream_usage={
                         'input_tokens': token_count(attrs.get('input_token_count')),
                         'output_tokens': token_count(attrs.get('output_token_count')),
                         'cached_input_tokens': token_count(attrs.get('cached_token_count'))})
        if clock == 'source': event['source_timestamp'] = dt.datetime.fromtimestamp(seconds, dt.timezone.utc).isoformat()
    if not event.get('source_timestamp'): event['source_timestamp'] = state.timestamp(attrs.get('event.timestamp'))
    # No response/turn ID is exported. Timestamp-based replay dedup is best
    # effort: equal timestamps collapse; re-emission with a new timestamp can
    # duplicate. Never claim exactly-once response/turn correlation.
    event['request_id'] = str(uuid.uuid5(uuid.UUID(session), identity))
    for key in ('model', 'effort', 'source_timestamp'):
        if event.get(key) is None: event.pop(key, None)
    normalized = state.sanitize(event)
    return {key: value for key, value in normalized.items() if key in event}


def records(payload):
    if not isinstance(payload, dict) or set(payload) - {'resourceLogs'}: raise ValueError('invalid_otlp_logs')
    resources = payload.get('resourceLogs', [])
    if not isinstance(resources, list) or len(resources) > 16: raise ValueError('resource_limit')
    result = []
    for resource in resources:
        if not isinstance(resource, dict): raise ValueError('invalid_resource')
        scopes = resource.get('scopeLogs', [])
        if not isinstance(scopes, list) or len(scopes) > 16: raise ValueError('scope_limit')
        for scope in scopes:
            if not isinstance(scope, dict): raise ValueError('invalid_scope')
            logs = scope.get('logRecords', [])
            if not isinstance(logs, list): raise ValueError('invalid_logs')
            result.extend(logs)
            if len(result) > MAX_RECORDS: raise ValueError('record_limit')
    return result


def decode(raw):
    if len(raw) > MAX_BYTES: raise ValueError('body_limit')
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value: raise ValueError('duplicate_json_key')
            value[key] = item
        return value
    def invalid(_): raise ValueError('invalid_number')
    return records(json.loads(raw.decode('utf-8'), object_pairs_hook=unique, parse_constant=invalid))


def ingest(raw, ledger):
    items = decode(raw)
    accepted = ignored = rejected = 0
    # Fully normalize before any write. Exceptions never include raw values.
    events = []
    for item in items:
        try: event = metadata(item)
        except (ValueError, TypeError, OverflowError, OSError):
            rejected += 1
            continue
        if event is None: ignored += 1
        else: events.append(event)
    for event in events:
        ledger.put(event)
        accepted += 1
    return {'accepted': accepted, 'ignored': ignored, 'rejected': rejected}
