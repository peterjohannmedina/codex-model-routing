#!/bin/sh
# Install the complete package into the current user's Codex directories.
set -eu

usage() {
    cat <<'EOF'
Usage: scripts/install.sh [--source-root PATH] [--user-root PATH] [--skip-global-instruction] [--include-legacy-local-profiles]

Installs the skill at USER_ROOT/.codex/skills/codex-model-routing, the custom
agent profiles at USER_ROOT/.codex/agents, and—unless skipped—the marked
routing block in USER_ROOT/.codex/AGENTS.md.
EOF
}

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
source_root=$(CDPATH= cd -- "$script_dir/.." && pwd -P)
user_root=${HOME:?HOME must be set, or pass --user-root}
skip_global_instruction=false
include_legacy_local_profiles=false

while [ "$#" -gt 0 ]; do
    case "$1" in
        --source-root)
            [ "$#" -ge 2 ] || { usage >&2; exit 2; }
            source_root=$(CDPATH= cd -- "$2" && pwd -P)
            shift 2
            ;;
        --user-root)
            [ "$#" -ge 2 ] || { usage >&2; exit 2; }
            user_root=$2
            shift 2
            ;;
        --skip-global-instruction)
            skip_global_instruction=true
            shift
            ;;
        --include-legacy-local-profiles)
            include_legacy_local_profiles=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            printf 'Unknown option: %s\n' "$1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

for relative_path in \
    SKILL.md \
    agents/openai.yaml \
    assets/AGENTS.md.snippet \
    assets/setup-prompt.md \
    assets/agents/luna-efficient.toml \
    assets/agents/terra-general.toml \
    assets/agents/sol-expert.toml \
    assets/agents/sol-general.toml \
    assets/agents/astra-integrator.toml \
    references/model-surfaces.md \
    references/decision-providers.md \
    assets/routing-packet.example.json \
    scripts/routing_decision.py \
    scripts/routing_runtime.py \
    scripts/routing_catalog.py \
    scripts/routing_state.py \
    scripts/routing_otel.py \
    scripts/routing_otel_setup.py \
    scripts/Prepare-RoutingTelemetry.ps1 \
    scripts/Test-RoutingTelemetryAcl.ps1 \
    scripts/routing_dashboard.py \
    scripts/collect_codex_json.py \
    scripts/Start-RoutingDashboard.ps1 \
    scripts/Resolve-RoutingPython.ps1 \
    assets/dashboard/index.html \
    assets/dashboard/app.js \
    assets/dashboard/style.css \
    assets/dashboard/router-mark.svg \
    scripts/Invoke-Routing.ps1 \
    scripts/Set-RoutingApiKey.ps1 \
    scripts/invoke-routing.sh \
    assets/routing-config.example.json \
    references/local-workers.md \
    references/switching-economics.md \
    assets/prompts/codex-routing.md
do
    [ -f "$source_root/$relative_path" ] || {
        printf 'Router package is incomplete: missing %s\n' "$relative_path" >&2
        exit 1
    }
done

if [ "$include_legacy_local_profiles" = true ]; then
    for legacy_path in assets/legacy-agents/muse-worker.toml assets/legacy-agents/ganglion-worker.toml \
        scripts/test-muse-access.ps1 scripts/test-ganglion-access.ps1 scripts/invoke-ganglion-worker.ps1 \
        scripts/sweep-ganglion-resources.ps1 scripts/manage-codex-routing-policy.ps1; do
        [ -f "$source_root/$legacy_path" ] || { printf 'Missing legacy file: %s\n' "$legacy_path" >&2; exit 1; }
    done
fi

skill_parent=$user_root/.codex/skills
skill_destination=$skill_parent/codex-model-routing
agent_destination=$user_root/.codex/agents
prompt_destination=$user_root/.codex/prompts

case "$skill_destination" in
    "$source_root"|"$source_root"/*)
        printf 'Refusing to install the skill inside its own source directory: %s\n' "$skill_destination" >&2
        exit 1
        ;;
esac

mkdir -p "$skill_destination" "$agent_destination" "$prompt_destination"

# rsync ships with macOS and preserves the package layout while excluding Git
# metadata, matching the PowerShell installer's behavior.
rsync -a --exclude=.git --exclude=__pycache__ --exclude='*.pyc' --exclude='*.dpapi' --exclude='.env*' --exclude='usage.sqlite3*' --exclude='*.capability' --exclude='otel-config-before-*' --exclude='otel-setup-receipt.json' --exclude='.otel-setup.lock' --exclude='.dashboard-launch-*' "$source_root/" "$skill_destination/"
for profile in luna-efficient sol-general terra-general sol-expert astra-integrator; do
    cp "$source_root/assets/agents/$profile.toml" "$agent_destination/"
done
if [ "$include_legacy_local_profiles" = true ]; then
    for profile in muse-worker ganglion-worker; do
        if [ ! -e "$agent_destination/$profile.toml" ]; then
            cp "$source_root/assets/legacy-agents/$profile.toml" "$agent_destination/"
        fi
    done
fi
cp "$source_root"/assets/prompts/codex-routing.md "$prompt_destination/"

if [ "$skip_global_instruction" = false ]; then
    agents_path=$user_root/.codex/AGENTS.md
    temp_agents=$(mktemp "${TMPDIR:-/tmp}/codex-model-routing-agents.XXXXXX")
    trap 'rm -f "$temp_agents"' EXIT HUP INT TERM

    if [ -f "$agents_path" ]; then
        awk '
            /^<!-- codex-model-routing:start -->$/ { in_marked_block = 1; next }
            /^<!-- codex-model-routing:end -->$/ { in_marked_block = 0; next }
            /^## Default Codex Model Routing$/ { in_legacy_block = 1; next }
            in_legacy_block && /^## / { in_legacy_block = 0 }
            !in_marked_block && !in_legacy_block { print }
        ' "$agents_path" > "$temp_agents"
    fi

    if [ -s "$temp_agents" ]; then
        printf '\n\n' >> "$temp_agents"
    fi
    cat "$source_root/assets/AGENTS.md.snippet" >> "$temp_agents"
    printf '\n' >> "$temp_agents"
    mv "$temp_agents" "$agents_path"
    trap - EXIT HUP INT TERM
fi

printf 'Skill: %s\n' "$skill_destination"
printf 'Custom agents: %s\n' "$agent_destination"
printf 'Custom prompts: %s\n' "$prompt_destination"
if [ "$skip_global_instruction" = true ]; then
    printf 'Global AGENTS.md instruction: skipped\n'
else
    printf 'Global AGENTS.md instruction: %s\n' "$user_root/.codex/AGENTS.md"
fi
printf 'The optional routing-bypass permission profile was not enabled.\n'
printf 'Start a new chat or restart Codex if the updated skill is not detected automatically.\n'
