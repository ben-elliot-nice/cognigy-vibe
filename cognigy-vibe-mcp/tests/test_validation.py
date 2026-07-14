from __future__ import annotations
import json
import pytest
from pydantic import BaseModel
from cognigy_mcp.validation import _ok, validate, make_schema


class _Simple(BaseModel):
    name: str
    count: int = 0


class _Multi(BaseModel):
    a: str
    b: int


def test_ok_returns_json_text_content():
    result = _ok({"key": "value"})
    assert len(result) == 1
    assert json.loads(result[0].text) == {"key": "value"}


def test_validate_valid_input_returns_model():
    m, err = validate(_Simple, {"name": "foo"})
    assert err is None
    assert m.name == "foo"
    assert m.count == 0


def test_validate_missing_required_returns_error():
    m, err = validate(_Simple, {})
    assert m is None
    assert err.isError is True
    data = json.loads(err.content[0].text)
    assert data["error"] == "Invalid tool arguments"
    assert any(d["field"] == "name" for d in data["details"])


def test_validate_wrong_type_returns_error():
    m, err = validate(_Simple, {"name": "foo", "count": "not-an-int"})
    assert m is None
    assert err.isError is True
    data = json.loads(err.content[0].text)
    assert data["error"] == "Invalid tool arguments"
    assert any(d["field"] == "count" for d in data["details"])


def test_validate_multiple_errors_all_surfaced():
    m, err = validate(_Multi, {})
    assert m is None
    assert err.isError is True
    data = json.loads(err.content[0].text)
    fields = [d["field"] for d in data["details"]]
    assert "a" in fields
    assert "b" in fields


def test_make_schema_strips_title():
    schema = make_schema(_Simple)
    assert "title" not in schema
    assert schema["type"] == "object"
    assert "name" in schema["properties"]


def test_make_schema_normalises_optional_str_field():
    class _WithOptional(BaseModel):
        name: str
        tag: str | None = None
    schema = make_schema(_WithOptional)
    # Optional str | None must NOT produce anyOf — must stay plain {"type": "string"}
    tag_schema = schema["properties"]["tag"]
    assert tag_schema["type"] == "string"
    assert "anyOf" not in tag_schema
    # Title is preserved during normalization
    assert "title" in tag_schema


def test_make_schema_normalises_optional_list_field():
    class _WithOptionalList(BaseModel):
        items: list[str] | None = None
    schema = make_schema(_WithOptionalList)
    items_schema = schema["properties"]["items"]
    assert items_schema["type"] == "array"
    assert items_schema["items"] == {"type": "string"}
    assert "anyOf" not in items_schema
    # Title may be preserved during normalization (acceptable)
