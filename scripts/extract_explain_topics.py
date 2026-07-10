#!/usr/bin/env python3
"""One-time script: extract legacy explain.py inline topics into resource markdown files.

Run once from repo root with: uv run scripts/extract_explain_topics.py
"""
from __future__ import annotations
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
EXPLAIN_PY = REPO_ROOT / "cognigy-vibe-mcp" / "cognigy_mcp" / "tools" / "explain.py"
RESOURCES = REPO_ROOT / "plugin" / "skills" / "explain" / "resources"

# (relative_output_path, description, group)
TOPIC_MAP: dict[str, tuple[str, str, str]] = {
    "node-positioning":  ("nodes/node-positioning.md",  "append vs appendChild modes, child branch population, insertAfter + insertBefore 500 bug on AU1, insert-before workaround", "nodes"),
    "node-wiring":       ("nodes/node-wiring.md",        "chart structure, relations array, sequential vs child chains", "nodes"),
    "node-config-update":("nodes/node-config-update.md", "full-replace semantics, merge_config pattern, silent field deletion", "nodes"),
    "node-types":        ("nodes/node-types.md",         "quick reference for all node type strings", "nodes"),
    "flow-chart-reading":("nodes/flow-chart-reading.md", "reading chart output, node type strings, extension field", "nodes"),
    "agent-tool-branch": ("aiagent/agent-tool-branch.md","aiAgentJobTool + code + toolAnswer assembly, tool args access", "aiagent"),
    "tool-conditions":   ("aiagent/tool-conditions.md",  "CognigyScript condition field, hiding tools from LLM", "aiagent"),
    "two-pass-confirm":  ("aiagent/two-pass-confirm.md", "inter-turn flag management, STOP gate wording", "aiagent"),
    "turn-structure":    ("aiagent/turn-structure.md",   "Once/OnFirstTime/Afterwards, input.execution, context reset prevention, child branch API patterns", "aiagent"),
    "tool-selection":    ("aiagent/tool-selection.md",   "when to use push_code_node vs cognigy_create vs cognigy_update", "aiagent"),
    "cognigyScript":     ("code/cognigyScript.md",       "interpolation contexts, what works where", "code"),
    "function-execution":("code/function-execution.md",  "async pattern, inject-back via sessions API", "code"),
    "session-injection": ("code/session-injection.md",   "context/state inject for in-session testing", "code"),
    "voice-gateway":     ("voice/voice-gateway.md",      "VG endpoint routing, Set Session Config, SIP headers, DTMF", "voice"),
    "say-node":          ("platform/say-node.md",        "say node config schema: correct text field, required _cognigy/_data fields, generativeAI_customInputs", "platform"),
    "outbound-trigger":  ("platform/outbound-trigger.md","6-step CXone trigger, Accept-Encoding: identity requirement", "platform"),
    "knowledge-store":   ("platform/knowledge-store.md", "chunking, connector run, source management", "platform"),
    "endpoint-config":   ("platform/endpoint-config.md", "referenceId vs _id gotcha, urlToken caching", "platform"),
    "extension-map":     ("platform/extension-map.md",   "complete type → extension lookup table", "platform"),
    "mcp-comparison":    ("platform/mcp-comparison.md",  "when to use cognigy-vibe vs NiCE official MCP", "platform"),
    "project-snapshots": ("platform/project-snapshots.md","create project snapshots for versioning (flow-level versioning does not exist in the API)", "platform"),
}

# Topics already handled by the POC — skip them
POC_TOPICS = {"code-node-patterns", "xapp", "xapp-delivery", "xapp-event-handling"}


def extract_topics(source: str) -> dict[str, str]:
    """Extract all triple-quoted topic bodies from _CONTENT dict in explain.py."""
    pattern = re.compile(r'"([a-zA-Z][a-zA-Z0-9-]+)":\s*"""(.*?)""",', re.DOTALL)
    return {m.group(1): m.group(2) for m in pattern.finditer(source)}


def main() -> None:
    source = EXPLAIN_PY.read_text(encoding="utf-8")
    topics = extract_topics(source)
    print(f"Found {len(topics)} topics in explain.py")

    created = 0
    for topic, (rel_path, description, group) in TOPIC_MAP.items():
        if topic in POC_TOPICS:
            print(f"  SKIP (POC): {topic}")
            continue
        if topic not in topics:
            print(f"  ERROR: topic not found in explain.py: {topic}")
            continue
        out_path = RESOURCES / rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        body = topics[topic].strip()
        content = f"---\ntopic: {topic}\ndescription: {description}\ngroup: {group}\n---\n\n{body}\n"
        out_path.write_text(content, encoding="utf-8")
        print(f"  Created: skills/explain/resources/{rel_path}")
        created += 1

    print(f"Done. {created} files created.")


if __name__ == "__main__":
    main()
