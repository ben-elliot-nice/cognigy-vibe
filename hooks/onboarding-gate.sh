#!/bin/bash
set -euo pipefail

input=$(cat)
tool_name=$(echo "$input" | jq -r '.tool_name')
session_id=$(echo "$input" | jq -r '.session_id')

# Let explain calls pass through — user is self-educating
if echo "$tool_name" | grep -qi "explain"; then
  exit 0
fi

# Check if primer already shown this session
flag_file="/tmp/.cognigy-primer-${session_id}"
if [ -f "$flag_file" ]; then
  exit 0
fi

# First Cognigy call this session — inject primer and deny
touch "$flag_file"

cat <<'PRIMER'
{
  "hookSpecificOutput": {
    "permissionDecision": "deny",
    "permissionDecisionReason": "First Cognigy session — loading architectural primer. Re-attempt your tool call.",
    "additionalContext": "COGNIGY ARCHITECTURAL PRIMER: This is a visual flow builder exposed as code. The hierarchy is Projects > Flows > Nodes > AI Agents > Tools. Flows are canvases with connected nodes (Say, Code, Once, HTTP Request, AI Agent Job). AI Agent Job nodes reference AI Agents which may have Tools attached. Key concepts: use cognigy_get/cognigy_create/cognigy_update by resource ID; use resolve_resource to look up IDs by friendly name; use get_flow_chart to see the full node tree; use explain(\"topic\") for detailed guidance on specific patterns. Call explain() with no arguments to see all available topics."
  }
}
PRIMER
