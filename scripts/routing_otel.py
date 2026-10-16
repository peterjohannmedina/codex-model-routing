"""Metadata-only adapter for reviewed Codex OTLP/HTTP JSON log contracts.

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
SUPPORTED_VERSIONS = ('0.162.1', '0.163.0')
SCHEMA_SERIES = ('0.162', '0.163')
IGNORE_REASONS = ('unsupported_version', 'missing_version', 'invalid_version',
                  'unsupported_event', 'missing_event', 'non_usage_response', 'schema_mismatch')
EVENT_CLASSES = {'codex.conversation_starts': 'session_start', 'codex.sse_event': 'response_event',
                 'codex.api_request': 'api_request', 'codex.exec_server.process_start': 'process',
                 'codex.exec_server.process_exit': 'process'}
VERSION_TALLY_LIMIT = 16
RECORD_FIELDS = {'timeUnixNano','observedTimeUnixNano','severityNumber','severityText','body',
                 'attributes','droppedAttributesCount','flags','traceId','spanId','eventName','_resource_version'}
HEADER = 'X-Routing-OTel'


def capability(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{43,128}', value):
        raise ValueError('invalid_local_capability')
    return value


def scalar(value):
    if not isinstance(value, dict) or len(value) != 1: return None
    if 'stringValue' in value and isinstance(value['stringValue'], str): return value['stringValue']
    number = value.get('intValue')
    if type(number) is int or isinstance(number, str) and re.fullmatch(r'-?[0-9]{1,20}', number): return number
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


def version_label(value):
    # Only numeric release/build identifiers can enter diagnostics. No arbitrary
    # exporter strings, field names, bodies, identities or content hashes.
    return value if isinstance(value, str) and re.fullmatch(
        r'[0-9]{1,4}\.[0-9]{1,4}\.[0-9]{1,4}(?:-(?:alpha|beta|rc)\.[0-9]{1,4}(?:\.[0-9]{1,4})?)?', value) else 'invalid'


def tally(producer, kind, label):
    if producer is None: return
    counts = producer.setdefault(kind, {})
    if label not in counts and len(counts) >= VERSION_TALLY_LIMIT: label = 'other'
    counts[label] = counts.get(label, 0) + 1


def metadata(record, diagnostics=None, producer=None):
    def ignore(reason):
        if diagnostics is not None: diagnostics[reason] = diagnostics.get(reason, 0) + 1
        return None
    if not isinstance(record, dict): raise ValueError('invalid_record')
    attrs = attributes(record)
    if set(record) - RECORD_FIELDS: tally(producer, 'features', 'unknown_record_fields')
    if 'event.name' not in attrs and 'eventName' in record: tally(producer, 'features', 'top_level_event_name_only')
    # Resource service.version describes the producing process, not necessarily
    # the embedded session telemetry crate. Observe it; never silently substitute
    # it for the reviewed session event's required app.version.
    resource_version = record.get('_resource_version')
    if resource_version is not None: tally(producer, 'versions', 'resource:' + version_label(resource_version))
    if 'app.version' in attrs: tally(producer, 'versions', 'event:' + version_label(attrs['app.version']))
    name = attrs.get('event.name')
    tally(producer, 'events', EVENT_CLASSES.get(name, 'missing' if name is None else 'other'))
    if name is None: return ignore('missing_event')
    # Unrelated API/process events legitimately omit app.version. Classify the
    # event first so they cannot masquerade as an unsupported CLI release.
    if name not in ('codex.conversation_starts', 'codex.sse_event'): return ignore('unsupported_event')
    if 'app.version' not in attrs: return ignore('missing_version')
    version = attrs['app.version']
    if version_label(version) == 'invalid': return ignore('invalid_version')
    reviewed = version in SUPPORTED_VERSIONS
    if not reviewed and '.'.join(version.split('.')[:2]) not in SCHEMA_SERIES: return ignore('unsupported_version')
    session = state.identifier(attrs.get('conversation.id'), allow_unassigned=False)
    event = {'source': 'codex_otel', 'session_id': session, 'session_source': 'codex_thread',
             'stage': 2, 'adapter': 'native', 'model': state.label(attrs.get('model')),
             'evaluator_usage': {'input_tokens': 0, 'output_tokens': 0}, 'evaluator_attempts': 0}
    event.update(producer_version=version, contract_validation='reviewed_version' if reviewed else 'reviewed_series_schema')
    if not reviewed and (state.label(attrs.get('model')) is None or state.timestamp(attrs.get('event.timestamp')) is None):
        return ignore('schema_mismatch')
    if name == 'codex.conversation_starts':
        if not reviewed and attrs.get('reasoning_effort') not in ('none','minimal','low','medium','high','xhigh','max','ultra'):
            return ignore('schema_mismatch')
        identity = 'session-configuration'
        event.update(mode='otel_session', model_source='startup_configuration',
                     execution_status='session_observed', effort=state.label(attrs.get('reasoning_effort')))
    else:
        if attrs.get('event.kind') != 'response.completed' or 'error.message' in attrs: return ignore('non_usage_response')
        # The same source also emits a generic SSE notification without usage.
        # Ignore it rather than counting one response twice.
        if not {'input_token_count', 'output_token_count'} & attrs.keys(): return ignore('non_usage_response')
        if not reviewed:
            if any(token_count(attrs.get(key)) is None for key in ('input_token_count','output_token_count')):
                return ignore('schema_mismatch')
            if 'cached_token_count' in attrs and token_count(attrs['cached_token_count']) is None:
                return ignore('schema_mismatch')
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
    if not reviewed: tally(producer, 'events', 'schema_compatible')
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
            # Carry only the version scalar, never resource identities or raw
            # attributes. This is diagnostic context, not an acceptance fallback.
            resource_version = None
            envelope = resource.get('resource')
            if isinstance(envelope, dict):
                fields = envelope.get('attributes', [])
                if isinstance(fields, list):
                    for item in fields[:96]:
                        if isinstance(item, dict) and item.get('key') == 'service.version':
                            resource_version = scalar(item.get('value'))
                            break
            result.extend({**log, '_resource_version': resource_version} if isinstance(log, dict) else log for log in logs)
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


def ingest(raw, ledger, diagnostics=None, producer=None):
    items = decode(raw)
    accepted = ignored = rejected = 0
    # Fully normalize before any write. Exceptions never include raw values.
    events = []
    for item in items:
        try: event = metadata(item, diagnostics, producer)
        except (ValueError, TypeError, OverflowError, OSError):
            rejected += 1
            continue
        if event is None: ignored += 1
        else: events.append(event)
    for event in events:
        ledger.put(event)
        accepted += 1
    return {'accepted': accepted, 'ignored': ignored, 'rejected': rejected}
