#!/bin/sh
# Portable launcher. Does not install packages, obtain keys, or enable providers.
set -eu
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
entry=routing_runtime.py
case "${1:-}" in
    dashboard) entry=routing_dashboard.py; shift ;;
    collect-codex) entry=collect_codex_json.py; shift ;;
    telemetry-setup) entry=routing_otel_setup.py; shift ;;
esac
if [ -n "${CODEX_ROUTING_PYTHON:-}" ]; then
    exec "$CODEX_ROUTING_PYTHON" -B "$script_dir/$entry" "$@"
fi
for runtime in python3 python; do
    if command -v "$runtime" >/dev/null 2>&1 && "$runtime" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)' 2>/dev/null; then
        exec "$runtime" -B "$script_dir/$entry" "$@"
    fi
done
printf '%s\n' 'Python 3.11+ required; set CODEX_ROUTING_PYTHON to an existing interpreter.' >&2
exit 2
