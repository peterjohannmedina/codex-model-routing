#!/bin/sh
# Install the complete package into the current user's Codex directories.
set -eu

usage() {
    cat <<'EOF'
Usage: scripts/install.sh [--source-root PATH] [--user-root PATH] [--skip-global-instruction]

Installs the skill at USER_ROOT/.codex/skills/codex-model-routing, the custom
agent profiles at USER_ROOT/.codex/agents, and—unless skipped—the marked
routing block in USER_ROOT/AGENTS.md.
EOF
}

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
source_root=$(CDPATH= cd -- "$script_dir/.." && pwd -P)
user_root=${HOME:?HOME must be set, or pass --user-root}
skip_global_instruction=false

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
    references/model-surfaces.md \
    references/switching-economics.md
do
    [ -f "$source_root/$relative_path" ] || {
        printf 'Router package is incomplete: missing %s\n' "$relative_path" >&2
        exit 1
    }
done

skill_parent=$user_root/.codex/skills
skill_destination=$skill_parent/codex-model-routing
agent_destination=$user_root/.codex/agents

case "$skill_destination" in
    "$source_root"|"$source_root"/*)
        printf 'Refusing to install the skill inside its own source directory: %s\n' "$skill_destination" >&2
        exit 1
        ;;
esac

mkdir -p "$skill_destination" "$agent_destination"

# rsync ships with macOS and preserves the package layout while excluding Git
# metadata, matching the PowerShell installer's behavior.
rsync -a --exclude=.git "$source_root/" "$skill_destination/"
cp "$source_root"/assets/agents/*.toml "$agent_destination/"

if [ "$skip_global_instruction" = false ]; then
    agents_path=$user_root/AGENTS.md
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
if [ "$skip_global_instruction" = true ]; then
    printf 'Global AGENTS.md instruction: skipped\n'
else
    printf 'Global AGENTS.md instruction: %s\n' "$user_root/AGENTS.md"
fi
printf 'The optional routing-bypass permission profile was not enabled.\n'
printf 'Start a new chat or restart Codex if the updated skill is not detected automatically.\n'
