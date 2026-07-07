from __future__ import annotations
import json
from typing import TypeVar
from pydantic import BaseModel, ValidationError
from mcp.types import TextContent

T = TypeVar("T", bound=BaseModel)


def _ok(data: dict) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(data, indent=2))]


def validate(
    model_cls: type[T], args: dict
) -> tuple[T | None, list[TextContent] | None]:
    try:
        return model_cls.model_validate(args), None
    except ValidationError as exc:
        details = [
            {"field": ".".join(str(loc) for loc in err["loc"]), "message": err["msg"]}
            for err in exc.errors()
        ]
        return None, _ok({"error": "Invalid tool arguments", "details": details})


def make_schema(model_cls: type[BaseModel]) -> dict:
    s = model_cls.model_json_schema()
    s.pop("title", None)
    return s
