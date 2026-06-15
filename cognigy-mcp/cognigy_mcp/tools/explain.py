# cognigy_mcp/tools/explain.py
from __future__ import annotations
from mcp.types import Tool, TextContent
from cognigy_mcp.api import CognigyClient
from cognigy_mcp.cache import Cache
from cognigy_mcp.state import ProjectState
from cognigy_mcp.tools._explain_topics_generated import (
    TOPICS,
    _TOPIC_INDEX,
    _CONTENT,
)

TOOLS: list[Tool] = [
    Tool(
        name="explain",
        description=(
            "Retrieve implementation guidance before brute-forcing or web-searching.\n\n"
            "Topics: " + " | ".join(TOPICS) + "\n\n"
            "Call explain() for orientation and topic descriptions.\n"
            "Call explain(\"topic\") for full reference on that topic."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Topic name from the list above. Omit for orientation overview.",
                },
            },
        },
    ),
]


def _ok(text: str) -> list[TextContent]:
    return [TextContent(type="text", text=text)]


def make_handlers(client: CognigyClient, state: ProjectState, cache: Cache) -> dict:

    def _explain(args: dict) -> list[TextContent]:
        topic = args.get("topic", "").strip()
        if not topic:
            return _ok("# cognigy-vibe-mcp Reference Library\n\n" + _TOPIC_INDEX)
        content = _CONTENT.get(topic)
        if content:
            return _ok(content.strip())
        return _ok(
            f"Unknown topic: '{topic}'\n\n"
            f"Available Topics:\n{_TOPIC_INDEX}"
        )

    return {"explain": _explain}
