import copy
import json
from cognigy_mcp.tools.schema_tools import (
    _normalise_rtype,
    _find_candidate_path,
    _known_resource_types,
    _extract_fields,
    _raw_schema_fragment,
    TOOLS,
    make_handlers,
)

FIXTURE_SPEC = {
    "openapi": "3.0.0",
    "paths": {
        "/v2.0/lexicons": {
            "post": {
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["name"],
                                "properties": {
                                    "name": {
                                        "type": "string",
                                        "example": "EU countries",
                                        "description": "The name of the lexicon",
                                    },
                                    "projectId": {
                                        "type": "string",
                                        "description": "The project id",
                                    },
                                },
                            }
                        }
                    }
                }
            },
            "get": {
                "parameters": [
                    {"in": "header", "name": "Accept", "required": False, "schema": {"type": "string"}},
                    {
                        "in": "query",
                        "name": "projectId",
                        "required": False,
                        "description": "Project id filter",
                        "schema": {"type": "string"},
                    },
                    {
                        "in": "query",
                        "name": "limit",
                        "required": False,
                        "example": 100,
                        "schema": {"type": "integer"},
                    },
                ]
            },
        },
        "/v2.0/lexicons/{lexiconId}": {
            "get": {
                "responses": {
                    "200": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "_id": {"type": "string"},
                                        "name": {"type": "string", "description": "The name"},
                                    },
                                }
                            }
                        }
                    }
                }
            },
            "patch": {
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {"name": {"type": "string"}},
                            }
                        }
                    }
                }
            },
            "delete": {},
        },
        "/v2.0/onlygettable": {"get": {"parameters": []}},
        "/v2.0/knowledgestores/{knowledgeStoreId}/connectors": {"get": {"parameters": []}},
    },
}


def test_normalise_rtype_singular_to_plural():
    assert _normalise_rtype("lexicon") == "lexicons"


def test_normalise_rtype_passthrough_for_unknown():
    assert _normalise_rtype("widgets") == "widgets"


def test_find_candidate_path_exact_create():
    path, exact = _find_candidate_path(FIXTURE_SPEC["paths"], "lexicons", "create")
    assert path == "/v2.0/lexicons"
    assert exact is True


def test_find_candidate_path_exact_update():
    path, exact = _find_candidate_path(FIXTURE_SPEC["paths"], "lexicons", "update")
    assert path == "/v2.0/lexicons/{lexiconId}"
    assert exact is True


def test_find_candidate_path_fallback_substring():
    path, exact = _find_candidate_path(FIXTURE_SPEC["paths"], "connectors", "list")
    assert path == "/v2.0/knowledgestores/{knowledgeStoreId}/connectors"
    assert exact is False


def test_find_candidate_path_no_match():
    path, exact = _find_candidate_path(FIXTURE_SPEC["paths"], "nonexistent", "create")
    assert path is None
    assert exact is False


def test_known_resource_types():
    types = _known_resource_types(FIXTURE_SPEC["paths"])
    assert "lexicons" in types
    assert "onlygettable" in types
    # nested/multi-segment paths must not appear as a bare top-level type
    assert "connectors" not in types


def test_extract_fields_create():
    op = FIXTURE_SPEC["paths"]["/v2.0/lexicons"]["post"]
    fields = _extract_fields(op, "create")
    by_name = {f["field"]: f for f in fields}
    assert by_name["name"]["required"] is True
    assert by_name["name"]["example"] == "EU countries"
    assert by_name["projectId"]["required"] is False


def test_extract_fields_get_uses_response_schema():
    op = FIXTURE_SPEC["paths"]["/v2.0/lexicons/{lexiconId}"]["get"]
    fields = _extract_fields(op, "get")
    names = {f["field"] for f in fields}
    assert names == {"_id", "name"}


def test_extract_fields_list_only_query_params():
    op = FIXTURE_SPEC["paths"]["/v2.0/lexicons"]["get"]
    fields = _extract_fields(op, "list")
    names = {f["field"] for f in fields}
    assert names == {"projectId", "limit"}  # header 'Accept' excluded


def test_extract_fields_delete_is_empty():
    op = FIXTURE_SPEC["paths"]["/v2.0/lexicons/{lexiconId}"]["delete"]
    assert _extract_fields(op, "delete") == []


def test_raw_schema_fragment_create_returns_full_schema():
    op = FIXTURE_SPEC["paths"]["/v2.0/lexicons"]["post"]
    raw = _raw_schema_fragment(op, "create")
    assert raw["properties"]["name"]["example"] == "EU countries"


def test_all_tools_exported():
    names = [t.name for t in TOOLS]
    assert "describe_resource_schema" in names


def test_describe_resource_schema_create_simplified(mock_client, state, cache):
    mock_client.get_openapi_spec.return_value = copy.deepcopy(FIXTURE_SPEC)
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["describe_resource_schema"]({"resource_type": "lexicon", "operation": "create"})
    data = json.loads(result[0].text)
    assert data["path"] == "/v2.0/lexicons"
    assert data["method"] == "post"
    assert "warning" not in data
    by_name = {f["field"]: f for f in data["fields"]}
    assert by_name["name"]["required"] is True


def test_describe_resource_schema_verbose_returns_raw_schema(mock_client, state, cache):
    mock_client.get_openapi_spec.return_value = copy.deepcopy(FIXTURE_SPEC)
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["describe_resource_schema"](
        {"resource_type": "lexicons", "operation": "create", "verbose": True}
    )
    data = json.loads(result[0].text)
    assert "fields" not in data
    assert data["raw_schema"]["properties"]["name"]["example"] == "EU countries"


def test_describe_resource_schema_fallback_match_has_warning(mock_client, state, cache):
    mock_client.get_openapi_spec.return_value = copy.deepcopy(FIXTURE_SPEC)
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["describe_resource_schema"]({"resource_type": "connectors", "operation": "list"})
    data = json.loads(result[0].text)
    assert data["path"] == "/v2.0/knowledgestores/{knowledgeStoreId}/connectors"
    assert "warning" in data


def test_describe_resource_schema_no_match_lists_known_types(mock_client, state, cache):
    mock_client.get_openapi_spec.return_value = copy.deepcopy(FIXTURE_SPEC)
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["describe_resource_schema"]({"resource_type": "nonexistent", "operation": "create"})
    data = json.loads(result[0].text)
    assert "error" in data
    assert "lexicons" in data["known_resource_types"]


def test_describe_resource_schema_operation_not_available(mock_client, state, cache):
    mock_client.get_openapi_spec.return_value = copy.deepcopy(FIXTURE_SPEC)
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["describe_resource_schema"]({"resource_type": "onlygettable", "operation": "create"})
    data = json.loads(result[0].text)
    assert "error" in data
    assert data["available_methods"] == ["get"]


def test_describe_resource_schema_caches_spec_across_calls(mock_client, state, cache):
    mock_client.get_openapi_spec.return_value = copy.deepcopy(FIXTURE_SPEC)
    handlers = make_handlers(mock_client, state, cache)
    handlers["describe_resource_schema"]({"resource_type": "lexicons", "operation": "create"})
    handlers["describe_resource_schema"]({"resource_type": "lexicons", "operation": "update"})
    mock_client.get_openapi_spec.assert_called_once()
