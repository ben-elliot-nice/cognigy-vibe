import pytest
from cognigy_mcp.filters import strip_response


def test_strips_top_level_v():
    data = {"_id": "x", "__v": 5, "name": "foo"}
    result = strip_response(data)
    assert "__v" not in result
    assert result["_id"] == "x"
    assert result["name"] == "foo"


def test_strips_transpiled_from_config():
    data = {"_id": "x", "config": {"code": "input.text", "transpiled": "compiled..."}}
    result = strip_response(data)
    assert "transpiled" not in result["config"]
    assert result["config"]["code"] == "input.text"


def test_strips_transpiled_from_config_mock():
    data = {"_id": "x", "config": {"mock": {"code": "input.text", "transpiled": "compiled..."}}}
    result = strip_response(data)
    assert "transpiled" not in result["config"]["mock"]
    assert result["config"]["mock"]["code"] == "input.text"


def test_leaves_unrelated_fields_intact():
    data = {"_id": "x", "name": "foo", "config": {"answer": "42"}}
    result = strip_response(data)
    assert result["name"] == "foo"
    assert result["config"]["answer"] == "42"


def test_non_mutating():
    original = {"__v": 5, "config": {"transpiled": "big", "code": "small"}}
    strip_response(original)
    assert "__v" in original
    assert "transpiled" in original["config"]


def test_noop_when_nothing_to_strip():
    data = {"_id": "x", "name": "foo", "config": {"code": "input.text"}}
    result = strip_response(data)
    assert result == data


def test_no_config_key_is_safe():
    data = {"_id": "x", "__v": 1, "name": "bar"}
    result = strip_response(data)
    assert "__v" not in result
    assert "config" not in result


def test_config_mock_non_dict_is_left_alone():
    """If config.mock is not a dict (e.g. None or a string), do not crash."""
    data = {"_id": "x", "config": {"mock": None}}
    result = strip_response(data)
    assert result["config"]["mock"] is None


def test_config_null_does_not_crash():
    data = {"_id": "x", "config": None}
    result = strip_response(data)
    assert result["config"] is None
