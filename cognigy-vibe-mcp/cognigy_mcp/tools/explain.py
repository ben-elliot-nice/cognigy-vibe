# cognigy_mcp/tools/explain.py
from __future__ import annotations
from pydantic import BaseModel
from mcp.types import Tool, TextContent
from cognigy_mcp.api import CognigyClient
from cognigy_mcp.cache import Cache
from cognigy_mcp.state import ProjectState
from cognigy_mcp.validation import validate, make_schema
from cognigy_mcp.tools._explain_topics_generated import (
    TOPICS,
    _TOPIC_INDEX,
    _CONTENT,
)


class ExplainArgs(BaseModel):
    topic: str = ""

TOOLS: list[Tool] = [
    Tool(
        name="explain",
        description=(
            "Retrieve implementation guidance before brute-forcing or web-searching.\n\n"
            "Topics: " + " | ".join(TOPICS) + "\n\n"
            "Call explain() for orientation — lists top-level topic groups.\n"
            "Call explain(\"group\") for that group's primer plus an index of its topics.\n"
            "Call explain(\"topic\") for full reference on that specific topic."
        ),
        inputSchema=make_schema(ExplainArgs),
    ),
]


def _ok(text: str) -> list[TextContent]:
    return [TextContent(type="text", text=text)]


def make_handlers(client: CognigyClient, state: ProjectState, cache: Cache) -> dict:

    def _explain(args: dict) -> list[TextContent]:
        m, err = validate(ExplainArgs, args)
        if err:
            return err
        topic = m.topic.strip()
        if not topic:
            return _ok("# cognigy-vibe-mcp Reference Library\n\n" + _TOPIC_INDEX)
        if topic in _CONTENT:
            return _ok(_CONTENT[topic].strip())
        return _ok(
            f"Unknown topic: '{topic}'\n\n"
            f"Available Topics:\n{_TOPIC_INDEX}"
        )

    return {"explain": _explain}
