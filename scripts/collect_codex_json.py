"""Opt-in stdin collector for one codex exec --json invocation. Never launches Codex."""
import argparse
import json
import sys
import uuid
from pathlib import Path

import routing_decision as core
import routing_runtime as runtime
import routing_state as state

MAX_LINE = 1024 * 1024


class Collector:
    def __init__(self, ledger, stream_id, model=None, effort=None, settings_loader=None):
        self.ledger = ledger
        self.session = state.identifier(stream_id)
        self.request = str(uuid.uuid5(uuid.NAMESPACE_URL, 'codex_exec:' + self.session))
        self.items = set()
        self.settings_loader = settings_loader
        self.thread = None
        self.seen = False
        self.event = {'source': 'codex_exec', 'session_id': self.session, 'request_id': self.request,
                      'stage': 1, 'mode': 'exec_stream', 'model': state.label(model), 'effort': state.label(effort),
                      'model_source': 'collector_annotation' if model or effort else 'unobserved',
                      'adapter': 'native', 'execution_status': 'started', 'evaluator_attempts': 0,
                      'stream_status': 'open',
                      'evaluator_usage': {'input_tokens': 0, 'output_tokens': 0}}

    def consume(self, raw):
        if not isinstance(raw, dict): return False
        if self.settings_loader: self.ledger.settings = self.settings_loader()
        kind = raw.get('type')
        if kind == 'thread.started':
            incoming = state.identifier(raw.get('thread_id'))
            if self.thread is not None and incoming != self.thread: raise ValueError('one_invocation_per_stream')
            self.thread = self.session = incoming
            self.event['session_id'] = self.session
        elif kind == 'turn.started':
            pass  # One exec invocation/turn per stream-id, including replay.
        elif kind in ('item.started', 'item.completed', 'item.updated'):
            item = raw.get('item')
            if not isinstance(item, dict): return False
            if item.get('type') == 'command_execution' and isinstance(item.get('id'), str) and len(item['id']) <= 128:
                if len(self.items) < 10000: self.items.add(item['id'])
                self.event['command_items'] = len(self.items)
            else: return False  # Discard messages, reasoning, commands and tool output.
        elif kind == 'turn.completed':
            self.event.update(stage=2, execution_status='completed', downstream_attempts=1, error=None)
            incoming = state.usage(raw.get('usage'))
            previous = self.event.get('downstream_usage') or {}
            if incoming:
                self.event['downstream_usage'] = {k: v if v is not None else previous.get(k) for k, v in incoming.items()}
        elif kind in ('turn.failed', 'error'):
            self.event.update(stage=2, execution_status='failed', error='codex_exec_failed')
        else: return False
        self.seen = True
        return self.ledger.put(self.event)

    def close(self):
        if not self.seen: return False
        if self.settings_loader: self.ledger.settings = self.settings_loader()
        self.event['stream_status'] = 'closed'
        if self.event['stage'] < 2:
            self.event.update(stage=2, execution_status='unobserved', error='stream_ended_without_completion')
        return self.ledger.put(self.event)


def consume_stream(stream, collector):
    changed = rejected = 0
    while True:
        line = stream.readline(MAX_LINE + 1)
        if not line: break
        if len(line) > MAX_LINE:
            while line and not line.endswith(b'\n'): line = stream.readline(MAX_LINE + 1)
            rejected += 1
            continue
        try:
            changed += bool(collector.consume(core.read_json(line.decode('utf-8-sig'))))
        except (ValueError, TypeError, AttributeError, UnicodeError, RecursionError):
            rejected += 1
    return {'updated_events': changed, 'rejected_lines': rejected}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stream-id', required=True, help='UUID identifying this exec invocation; reuse only for replay/dedup')
    parser.add_argument('--state-dir', type=Path, default=state.state_root())
    parser.add_argument('--model', help='Optional operator annotation, not provider attestation')
    parser.add_argument('--effort', help='Optional operator annotation')
    args = parser.parse_args(argv)
    try:
        config_path = args.state_dir / 'config.json'
        config = runtime.Config.parse(core.load_file(config_path)) if config_path.is_file() else runtime.Config()
        def settings():
            current = runtime.Config.parse(core.load_file(config_path)) if config_path.is_file() else runtime.Config()
            return current.observability
        collector = Collector(state.Ledger(args.state_dir, config.observability), args.stream_id, args.model, args.effort, settings)
        result = consume_stream(sys.stdin.buffer, collector)
        collector.close()
        result['ledger_enabled'] = config.observability.enabled
        print(json.dumps(result))
        return 0
    except (ValueError, TypeError, OSError, state.sqlite3.Error):
        print(json.dumps({'error': 'collector_configuration_or_storage_failed'}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
