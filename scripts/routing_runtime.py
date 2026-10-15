"""Portable optional providers. Recommendation is separate from explicit local execution."""
from __future__ import annotations

import argparse
import copy
from dataclasses import dataclass, field, replace
import ipaddress
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import urlsplit
import urllib.error
import urllib.request

import routing_decision as core


@dataclass(frozen=True)
class DecisionsConfig:
    enabled: bool = False
    api_key_env: str = 'OPENAI_API_KEY'
    timeout_seconds: float = 3.0
    minimum_confidence: float = 0.6
    max_input_tokens: int | None = None
    max_cost_usd: float | None = None


@dataclass(frozen=True)
class LocalConfig:
    enabled: bool = False
    base_url: str | None = None
    model: str | None = None
    api_key_env: str | None = None
    timeout_seconds: float = 2.0
    max_output_tokens: int = 512
    efforts: list[str] = field(default_factory=lambda: ['default'])
    allow_remote: bool = False
    prefer_when_eligible: bool = False


@dataclass(frozen=True)
class Config:
    decisions: DecisionsConfig = field(default_factory=DecisionsConfig)
    local: LocalConfig = field(default_factory=LocalConfig)

    @classmethod
    def parse(cls, raw):
        value = core.object_fields(raw, {'schema_version', 'decisions', 'local'}, {'schema_version'})
        if type(value['schema_version']) is not int or value['schema_version'] != 1:
            raise core.RoutingError('unsupported_config_schema')
        decisions = DecisionsConfig(**core.object_fields(value.get('decisions', {}), set(DecisionsConfig.__dataclass_fields__), set()))
        local = LocalConfig(**core.object_fields(value.get('local', {}), set(LocalConfig.__dataclass_fields__), set()))
        for flag in (decisions.enabled, local.enabled, local.allow_remote, local.prefer_when_eligible):
            if type(flag) is not bool:
                raise core.RoutingError('invalid_config_flag')
        for name in (decisions.api_key_env, local.api_key_env):
            if name is not None and (not isinstance(name, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,127}', name)):
                raise core.RoutingError('invalid_key_environment_name')
        if decisions.api_key_env is None:
            raise core.RoutingError('missing_key_environment_name')
        for timeout in (decisions.timeout_seconds, local.timeout_seconds):
            if not core.number(timeout, 0.05, 10):
                raise core.RoutingError('invalid_timeout')
        if not core.number(decisions.minimum_confidence, 0, 1):
            raise core.RoutingError('invalid_confidence_threshold')
        if decisions.max_input_tokens is not None and (type(decisions.max_input_tokens) is not int or decisions.max_input_tokens < 0):
            raise core.RoutingError('invalid_evaluator_token_cap')
        if decisions.max_cost_usd is not None and not core.number(decisions.max_cost_usd, 0, 10**6):
            raise core.RoutingError('invalid_evaluator_cost_cap')
        if type(local.max_output_tokens) is not int or not 1 <= local.max_output_tokens <= 4096:
            raise core.RoutingError('invalid_output_budget')
        if (not isinstance(local.efforts, list) or not local.efforts
                or any(not isinstance(e, str) or e not in core.EFFORTS | {'default'} for e in local.efforts)):
            raise core.RoutingError('invalid_local_efforts')
        if local.model is not None and (not isinstance(local.model, str) or len(local.model) > 256):
            raise core.RoutingError('invalid_local_model')
        if local.base_url is not None and not isinstance(local.base_url, str):
            raise core.RoutingError('invalid_local_url')
        return cls(decisions, local)


def local_url(config: LocalConfig):
    if not config.base_url or not config.model:
        raise core.ProviderFailure('unconfigured')
    try:
        parsed = urlsplit(config.base_url)
        if (parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username is not None
                or parsed.password is not None or parsed.query or parsed.fragment):
            raise ValueError()
        loopback = parsed.hostname == 'localhost'
        try:
            loopback = loopback or ipaddress.ip_address(parsed.hostname).is_loopback
        except ValueError:
            pass
        if not loopback and not config.allow_remote:
            raise core.ProviderFailure('remote_not_enabled')
    except ValueError:
        raise core.ProviderFailure('invalid_url') from None
    return config.base_url.rstrip('/')


def local_http(method, url, body, key, timeout):
    headers = {'Content-Type': 'application/json'}
    if key:
        headers['Authorization'] = 'Bearer ' + key
    request = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({}), core.NoRedirect).open(request, timeout=timeout) as response:
            data = response.read(core.MAX_RESPONSE_BYTES + 1)
            if len(data) > core.MAX_RESPONSE_BYTES:
                raise core.ProviderFailure('response_too_large')
            return data
    except urllib.error.HTTPError as error:
        code = 'http_' + str(error.code)
        error.close()
        raise core.ProviderFailure(code) from None
    except (OSError, TimeoutError, urllib.error.URLError):
        raise core.ProviderFailure('network') from None


def local_request(config, environment, transport, method='GET', body=None):
    base = local_url(config)
    key = environment.get(config.api_key_env, '') if config.api_key_env else ''
    if config.api_key_env and not key:
        raise core.ProviderFailure('missing_key')
    suffix = '/models' if method == 'GET' else '/chat/completions'
    raw = core.bounded_call(lambda: transport(method, base + suffix, body, key, config.timeout_seconds), config.timeout_seconds)
    try:
        if not isinstance(raw, bytes) or len(raw) > core.MAX_RESPONSE_BYTES:
            raise ValueError()
        return core.read_json(raw.decode('utf-8'))
    except (ValueError, UnicodeError, RecursionError):
        raise core.ProviderFailure('malformed_output') from None


def prepare(packet, config=Config(), overrides=core.Overrides(), environment=None, local_transport=local_http, offline=False):
    """Probe configured local capacity without inference; failures remove only local choices."""
    environment = os.environ if environment is None else environment
    packet = copy.deepcopy(packet)
    # Check the original trusted schema before changing readiness fields.
    core.object_fields(packet, {'schema_version', 'summary', 'available_models', 'candidates', 'fallback_id',
        'conservation_mode', 'stronger_exception', 'local_work_eligible', 'ready_adapters', 'ceilings', 'require_local'},
        {'schema_version', 'summary', 'available_models', 'candidates', 'fallback_id', 'conservation_mode'})
    # Hypothetical readiness lets admission reject overrides/budgets before a
    # probe. It does not establish readiness; only the validated probe does.
    packet['ready_adapters'] = ['local']
    prospective = None
    try:
        prospective = core.Request.parse(packet, overrides)
    except core.RoutingError as error:
        if str(error) != 'no_admissible_route':
            raise
    packet['ready_adapters'] = []
    local_status = 'disabled'
    if config.local.enabled:
        local_status = 'unconfigured' if not config.local.model or not config.local.base_url else ('offline' if offline else 'ineligible')
        eligible_local = [c for c in prospective.candidates if c.adapter == 'local'
                          and c.model == config.local.model and c.effort in config.local.efforts] if prospective else []
        if not offline and packet.get('local_work_eligible', False) and eligible_local:
            try:
                probe_timeout = min(config.local.timeout_seconds,
                    prospective.ceilings.get('latency_ms', 10000) / 1000,
                    min((c.latency_budget_ms or 10000) / 1000 for c in eligible_local))
                data = local_request(replace(config.local, timeout_seconds=probe_timeout), environment, local_transport)
                if (not isinstance(data, dict) or not isinstance(data.get('data'), list)
                        or any(not isinstance(item, dict) or not isinstance(item.get('id'), str) for item in data['data'])):
                    raise core.ProviderFailure('malformed_output')
                if config.local.model not in {item['id'] for item in data['data']}:
                    raise core.ProviderFailure('model_unavailable')
                packet['ready_adapters'] = ['local']
                local_status = 'ready'
            except core.ProviderFailure as error:
                local_status = str(error)
            except Exception:
                local_status = 'probe_error'
    try:
        request = core.Request.parse(packet, overrides)
    except core.RoutingError as error:
        if packet.get('require_local', False) and str(error) == 'no_admissible_route':
            raise core.RoutingError('require_local_unavailable') from None
        raise
    admitted = tuple(c for c in request.candidates if c.adapter != 'local' or
                     (c.model == config.local.model and c.effort in config.local.efforts))
    if not admitted:
        raise core.RoutingError('no_admissible_route')
    fallback = next((c for c in admitted if c.id == request.fallback.id), admitted[0])
    if config.local.prefer_when_eligible:
        fallback = next((c for c in admitted if c.adapter == 'local'), fallback)
    request = core.Request(request.summary, admitted, fallback, request.quality, request.ceilings)
    return request, local_status


def route(packet, config=Config(), overrides=core.Overrides(), environment=None,
          decision_transport=core.post_decisions, local_transport=local_http, allow_api=False,
          preflight_only=False, offline=False):
    environment = os.environ if environment is None else environment
    request, local_status = prepare(packet, config, overrides, environment, local_transport, offline)
    baseline = core.recommend(request, core.RulesProvider())
    requires_api = config.decisions.enabled and len(request.candidates) > 1
    reason = None
    if requires_api:
        if offline:
            reason = 'offline'
        elif config.decisions.max_input_tokens is not None:
            reason = 'verified_decisions_token_counter_unavailable'
        elif config.decisions.max_cost_usd is not None:
            reason = 'verified_decisions_cost_bound_unavailable'
        elif not allow_api:
            reason = 'api_not_authorized'
    may_load = requires_api and reason is None and allow_api
    baseline['provenance'].update(requested_provider='decisions' if config.decisions.enabled else 'rules',
                                  fallback_reason=reason, local_status=local_status)
    if config.decisions.enabled and len(request.candidates) == 1:
        baseline['provenance']['resolution'] = 'single_admissible_route'
    if preflight_only:
        return {'preflight': {'admissible_candidates': len(request.candidates), 'may_load_credential': may_load,
                             'requires_api': requires_api, 'block_reason': reason,
                             'api_key_env': config.decisions.api_key_env,
                             'complete_decisions_input_tokens': None, 'decisions_credential_accessed': False,
                             'local_status': local_status,
                             'decisions_api_calls': 0}, 'safe_result': baseline}
    if may_load:
        provider = core.DecisionsProvider(api_key=environment.get(config.decisions.api_key_env, ''), allow_api=True,
            timeout_seconds=config.decisions.timeout_seconds, minimum_confidence=config.decisions.minimum_confidence,
            transport=decision_transport)
        result = core.recommend(request, provider)
        result['provenance']['local_status'] = local_status
        return result
    return baseline


def execute_local(packet, config, overrides=core.Overrides(), environment=None, transport=local_http,
                  allow_local_inference=False):
    """Explicit bounded text execution. Failure returns a recommendation, never paid native execution."""
    environment = os.environ if environment is None else environment
    started = time.monotonic()
    request, status = prepare(packet, config, overrides, environment, transport)
    local = next((c for c in request.candidates if c.adapter == 'local'), None)
    baseline = core.recommend(request, core.RulesProvider())
    if not allow_local_inference or local is None:
        baseline['execution'] = {'status': 'not_started', 'reason': 'local_inference_not_authorized' if not allow_local_inference else status}
        return baseline
    if 'tokens' in request.ceilings or 'cost_usd' in request.ceilings:
        baseline['execution'] = {'status': 'not_started', 'reason': 'execution_budget_unverifiable'}
        return baseline
    payload = {'model': local.model, 'messages': [
        {'role': 'system', 'content': 'Complete only this bounded text task. No tools, secrets or external actions.'},
        {'role': 'user', 'content': request.summary}], 'stream': False,
        'max_tokens': min(config.local.max_output_tokens, local.token_budget or config.local.max_output_tokens)}
    if local.effort != 'default':
        payload['reasoning_effort'] = local.effort
    try:
        encoded = json.dumps(payload).encode()
        if len(encoded) > core.MAX_PACKET_BYTES:
            raise core.ProviderFailure('request_too_large')
        elapsed = time.monotonic() - started
        timeout = min(config.local.timeout_seconds,
                      request.ceilings.get('latency_ms', 10000) / 1000 - elapsed,
                      (local.latency_budget_ms or 10000) / 1000 - elapsed)
        if timeout <= 0:
            raise core.ProviderFailure('deadline_exhausted')
        data = local_request(replace(config.local, timeout_seconds=timeout), environment, transport, 'POST', encoded)
        content = data['choices'][0]['message']['content']
        if not isinstance(content, str) or not content.strip():
            raise ValueError()
        baseline['recommendation'] = core.asdict(local)
        baseline['provenance'].update(local_status=status, elapsed_ms=round((time.monotonic() - started) * 1000))
        baseline['execution'] = {'status': 'completed', 'text': content.strip(),
                                 'adapter': 'local', 'max_output_tokens': payload['max_tokens']}
        return baseline
    except Exception as error:
        reason = str(error) if isinstance(error, core.ProviderFailure) else 'malformed_output'
        # Re-admit with local unavailable; require-local fails rather than switching.
        native_packet = copy.deepcopy(packet)
        native_packet['ready_adapters'] = []
        try:
            request = core.Request.parse(native_packet, overrides)
        except core.RoutingError:
            return {'error': 'required_route_failed', 'recommendation': None,
                    'execution': {'status': 'failed', 'reason': reason, 'native_execution_started': False}}
        baseline = core.recommend(request, core.RulesProvider())
        baseline['execution'] = {'status': 'failed', 'reason': reason, 'native_execution_started': False}
        return baseline


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('packet', type=Path)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--overrides', type=Path)
    parser.add_argument('--provider', choices=('rules', 'decisions'))
    parser.add_argument('--allow-api', action='store_true')
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--preflight-only', action='store_true')
    parser.add_argument('--max-decision-input-tokens', type=int)
    parser.add_argument('--max-decision-cost-usd', type=float)
    parser.add_argument('--execute-local', action='store_true')
    parser.add_argument('--allow-local-inference', action='store_true')
    args = parser.parse_args(argv)
    try:
        config_path = args.config or Path(os.environ.get('CODEX_HOME', Path.home() / '.codex')) / 'routing' / 'config.json'
        raw = core.load_file(config_path) if config_path.is_file() else {'schema_version': 1}
        if args.config and not config_path.is_file():
            raise core.RoutingError('config_not_found')
        raw = copy.deepcopy(raw)
        if args.provider:
            raw.setdefault('decisions', {})['enabled'] = args.provider == 'decisions'
        if args.max_decision_input_tokens is not None:
            raw.setdefault('decisions', {})['max_input_tokens'] = args.max_decision_input_tokens
        if args.max_decision_cost_usd is not None:
            raw.setdefault('decisions', {})['max_cost_usd'] = args.max_decision_cost_usd
        config = Config.parse(raw)
        packet = core.load_file(args.packet)
        overrides = core.Overrides.parse(core.load_file(args.overrides)) if args.overrides else core.Overrides()
        # Preflight is advisory even when execution/consent switches are also
        # present. Match the PowerShell launcher: never infer during preflight.
        if args.preflight_only:
            result = route(packet, config, overrides, allow_api=args.allow_api,
                           preflight_only=True, offline=args.offline)
        elif args.execute_local:
            if args.offline:
                raise core.RoutingError('local_execution_in_offline_mode')
            result = execute_local(packet, config, overrides, allow_local_inference=args.allow_local_inference)
        else:
            result = route(packet, config, overrides, allow_api=args.allow_api,
                           preflight_only=args.preflight_only, offline=args.offline)
        print(json.dumps(result, allow_nan=False))
        return 2 if result.get('error') else 0
    except core.RoutingError as error:
        print(json.dumps({'error': 'invalid_or_unsatisfied_routing_configuration', 'reason': str(error), 'execution_started': False}))
        return 2
    except (ValueError, TypeError, OSError, RecursionError):
        print(json.dumps({'error': 'invalid_or_unsatisfied_routing_configuration', 'execution_started': False}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
