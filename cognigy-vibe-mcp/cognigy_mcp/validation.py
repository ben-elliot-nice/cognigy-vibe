from __future__ import annotations
import json
from typing import TypeVar
from pydantic import BaseModel, ValidationError
from mcp import types
from mcp.types import TextContent

T = TypeVar("T", bound=BaseModel)


def _ok(data: dict) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(data, indent=2))]


def validate(
    model_cls: type[T], args: dict
) -> tuple[T | None, types.CallToolResult | None]:
    try:
        return model_cls.model_validate(args), None
    except ValidationError as exc:
        details = [
            {"field": ".".join(str(loc) for loc in err["loc"]), "message": err["msg"]}
            for err in exc.errors()
        ]
        error_content = [TextContent(
            type="text",
            text=json.dumps({"error": "Invalid tool arguments", "details": details}, indent=2),
        )]
        return None, types.CallToolResult(isError=True, content=error_content)


def make_schema(model_cls: type[BaseModel]) -> dict:
    s = model_cls.model_json_schema()
    s.pop("title", None)
    _normalise_nullable(s)
    return s


def _normalise_nullable(schema: dict) -> None:
    """Convert anyOf:[T, null] → T in all properties (restores pre-Pydantic schema shape)."""
    for prop in schema.get("properties", {}).values():
        any_of = prop.get("anyOf")
        if (
            any_of
            and len(any_of) == 2
            and {"type": "null"} in any_of
        ):
            non_null = [x for x in any_of if x != {"type": "null"}]
            if len(non_null) == 1:
                # Preserve description and title before clearing
                description = prop.get("description")
                title = prop.get("title")
                prop.clear()
                prop.update(non_null[0])
                # Restore description and title if they existed
                if description is not None:
                    prop["description"] = description
                if title is not None:
                    prop["title"] = title
