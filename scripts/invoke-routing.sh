#!/bin/sh
# Portable launcher. Does not install packages, obtain keys, or enable providers.
set -eu
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
if [ -n "${CODEX_ROUTING_PYTHON:-}" ]; then
    exec "$CODEX_ROUTING_PYTHON" -B "$script_dir/routing_runtime.py" "$@"
fi
for runtime in python3 python; do
    if command -v "$runtime" >/dev/null 2>&1 && "$runtime" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)' 2>/dev/null; then
        exec "$runtime" -B "$script_dir/routing_runtime.py" "$@"
    fi
done
printf '%s\n' 'Python 3.11+ required; set CODEX_ROUTING_PYTHON to an existing interpreter.' >&2
exit 2
