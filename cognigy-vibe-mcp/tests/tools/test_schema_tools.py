import copy
import json
from cognigy_mcp.api import ApiError
from cognigy_mcp.cache import Cache
from cognigy_mcp.tools.schema_tools import (
    _normalise_rtype,
    _find_candidate_path,
    _known_resource_types,
    _extract_fields,
    _raw_schema_fragment,
    _merge_path_item_parameters,
    TOOLS,
    make_handlers,
)

def test_describe_resource_schema_missing_operation_and_node_type_returns_error(mock_client, state, cache):
    """operation is now optional at the pydantic level (node_type lookups don't need
    it), so the handler itself must reject the case where neither is given."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["describe_resource_schema"]({"resource_type": "node"})
    data = json.loads(result[0].text)
    assert data["error"] == "operation is required unless node_type is set"


def test_describe_resource_schema_node_type_missing_flow_id_returns_error(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["describe_resource_schema"]({"resource_type": "node", "node_type": "say"})
    data = json.loads(result[0].text)
    assert data["error"] == "flow_id is required when node_type is set"


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
        "/v2.0/widgets": {
            "parameters": [
                {
                    "in": "query",
                    "name": "projectId",
                    "required": True,
                    "description": "Shared project id (path-item level)",
                    "schema": {"type": "string"},
                },
                {
                    "in": "query",
                    "name": "sharedParam",
                    "required": False,
                    "description": "A path-item-level-only shared param",
                    "schema": {"type": "string"},
                },
            ],
            "get": {
                "parameters": [
                    {
                        "in": "query",
                        "name": "projectId",
                        "required": False,
                        "description": "Operation-level override, wins on conflict",
                        "schema": {"type": "string"},
                    },
                    {
                        "in": "query",
                        "name": "limit",
                        "required": False,
                        "schema": {"type": "integer"},
                    },
                ]
            },
        },
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


def test_find_candidate_path_ambiguous_substring_picks_alphabetically_first():
    """When multiple paths contain the resource_type as a substring, the fallback
    is a documented, warned-about limitation (not a bug) — this test locks in the
    actual current tie-breaking behavior: alphabetically-first match wins, since
    the implementation iterates `sorted(paths)` and returns on first hit."""
    paths = {
        "/v2.0/bar/connectors/extra": {"get": {}},
        "/v2.0/foo/connectors": {"get": {}},
    }
    path, exact = _find_candidate_path(paths, "connectors", "get")
    assert path == "/v2.0/bar/connectors/extra"
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


def test_describe_resource_schema_available_methods_excludes_non_http_keys(mock_client, state, cache):
    """available_methods must only list real HTTP verbs, not path-item siblings
    like parameters/summary/description that could appear at the path-item level."""
    spec = copy.deepcopy(FIXTURE_SPEC)
    spec["paths"]["/v2.0/onlygettable"]["summary"] = "Some summary"
    spec["paths"]["/v2.0/onlygettable"]["parameters"] = []
    mock_client.get_openapi_spec.return_value = spec
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["describe_resource_schema"]({"resource_type": "onlygettable", "operation": "create"})
    data = json.loads(result[0].text)
    assert data["available_methods"] == ["get"]


def test_describe_resource_schema_caches_spec_across_calls(mock_client, state, cache):
    mock_client.get_openapi_spec.return_value = copy.deepcopy(FIXTURE_SPEC)
    handlers = make_handlers(mock_client, state, cache)
    handlers["describe_resource_schema"]({"resource_type": "lexicons", "operation": "create"})
    handlers["describe_resource_schema"]({"resource_type": "lexicons", "operation": "update"})
    mock_client.get_openapi_spec.assert_called_once()


def test_describe_resource_schema_cache_persists_across_make_handlers_calls(mock_client, state, cache):
    """The on-disk spec cache must survive a fresh make_handlers() call using the
    same cache_dir — this is the actual server-restart scenario the 24h TTL protects."""
    mock_client.get_openapi_spec.return_value = copy.deepcopy(FIXTURE_SPEC)
    handlers1 = make_handlers(mock_client, state, cache)
    handlers1["describe_resource_schema"]({"resource_type": "lexicons", "operation": "create"})

    # Simulate a server restart: brand new make_handlers() call, same cache_dir.
    handlers2 = make_handlers(mock_client, state, cache)
    handlers2["describe_resource_schema"]({"resource_type": "lexicons", "operation": "update"})

    mock_client.get_openapi_spec.assert_called_once()


def test_describe_resource_schema_malformed_operation_returns_clean_error(mock_client, state, cache):
    """A structurally surprising spec (e.g. requestBody.content is a string, not a dict)
    must not raise — it should come back as a clean _ok(...) error envelope."""
    spec = copy.deepcopy(FIXTURE_SPEC)
    spec["paths"]["/v2.0/lexicons"]["post"]["requestBody"]["content"] = "not-a-dict"
    mock_client.get_openapi_spec.return_value = spec
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["describe_resource_schema"]({"resource_type": "lexicons", "operation": "create"})
    data = json.loads(result[0].text)
    assert data["error"] == "schema_parse_error"
    assert data["resource_type"] == "lexicons"
    assert data["operation"] == "create"


def test_describe_resource_schema_malformed_paths_returns_clean_error(mock_client, state, cache):
    """If spec['paths'] itself is structurally surprising (e.g. a string instead of a
    dict), the handler must still come back as a clean error envelope, not raise —
    the pre-dispatch parsing (spec.get('paths'), _normalise_rtype, _find_candidate_path)
    must be inside the same try/except boundary as the rest of the handler."""
    spec = {"openapi": "3.0.0", "paths": None}
    mock_client.get_openapi_spec.return_value = spec
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["describe_resource_schema"]({"resource_type": "lexicons", "operation": "create"})
    data = json.loads(result[0].text)
    assert "error" in data


def test_describe_resource_schema_handler_returns_api_error_response(mock_client, state, cache):
    """The handler's own except ApiError branch (schema_tools.py) must be exercised
    directly, not just CognigyClient.get_openapi_spec raising in isolation."""
    mock_client.get_openapi_spec.side_effect = ApiError(status_code=500, message="boom")
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["describe_resource_schema"]({"resource_type": "lexicons", "operation": "create"})
    data = json.loads(result[0].text)
    assert data["error"] == "api_error"
    assert data["status"] == 500
    assert "boom" in data["detail"]


def test_describe_resource_schema_handler_returns_unexpected_error_response(mock_client, state, cache):
    """The handler's own except Exception branch must be exercised directly with a
    generic, non-ApiError exception."""
    mock_client.get_openapi_spec.side_effect = RuntimeError("unexpected")
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["describe_resource_schema"]({"resource_type": "lexicons", "operation": "create"})
    data = json.loads(result[0].text)
    assert data["error"] == "unexpected_error"
    assert "unexpected" in data["detail"]


def test_extract_fields_list_merges_path_item_level_parameters():
    """OpenAPI allows 'parameters' as a sibling of 'get'/'post'/etc at the path-item
    level, applying to all methods on that path. _extract_fields's 'list' branch must
    pick these up too, not just operation-level parameters nested under 'get'."""
    path_item = FIXTURE_SPEC["paths"]["/v2.0/widgets"]
    op = path_item["get"]
    merged_params = _merge_path_item_parameters(path_item, op)
    fields = _extract_fields({**op, "parameters": merged_params}, "list")
    names = {f["field"] for f in fields}
    assert names == {"projectId", "sharedParam", "limit"}


def test_extract_fields_list_operation_level_wins_on_name_collision():
    """projectId is defined at both path-item level (required=True) and operation
    level (required=False) — operation-level must win per the OpenAPI spec."""
    path_item = FIXTURE_SPEC["paths"]["/v2.0/widgets"]
    op = path_item["get"]
    merged_params = _merge_path_item_parameters(path_item, op)
    fields = _extract_fields({**op, "parameters": merged_params}, "list")
    by_name = {f["field"]: f for f in fields}
    assert by_name["projectId"]["required"] is False
    assert by_name["projectId"]["description"] == "Operation-level override, wins on conflict"


def test_describe_resource_schema_list_handler_merges_path_item_parameters(mock_client, state, cache):
    """End-to-end: the handler's 'list' operation for resource_type=widgets must
    surface both the path-item-level shared param and the operation-level params,
    with operation-level winning the projectId name collision."""
    mock_client.get_openapi_spec.return_value = copy.deepcopy(FIXTURE_SPEC)
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["describe_resource_schema"]({"resource_type": "widgets", "operation": "list"})
    data = json.loads(result[0].text)
    by_name = {f["field"]: f for f in data["fields"]}
    assert set(by_name) == {"projectId", "sharedParam", "limit"}
    assert by_name["projectId"]["required"] is False


def test_describe_resource_schema_list_verbose_reflects_merged_parameters(mock_client, state, cache):
    """verbose=True's raw_schema fragment for 'list' must reflect the same merged
    parameter set as the simplified field list."""
    mock_client.get_openapi_spec.return_value = copy.deepcopy(FIXTURE_SPEC)
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["describe_resource_schema"](
        {"resource_type": "widgets", "operation": "list", "verbose": True}
    )
    data = json.loads(result[0].text)
    names = {p["name"] for p in data["raw_schema"]["parameters"]}
    assert names == {"projectId", "sharedParam", "limit"}


def test_describe_resource_schema_get_composed_schema_notes_no_fields(mock_client, state, cache):
    """A GET response schema using oneOf/allOf/anyOf/$ref composition (no top-level
    'properties') must not silently look like zero fields with no explanation."""
    spec = copy.deepcopy(FIXTURE_SPEC)
    spec["paths"]["/v2.0/lexicons/{lexiconId}"]["get"]["responses"]["200"]["content"]["application/json"]["schema"] = {
        "oneOf": [
            {"type": "object", "properties": {"_id": {"type": "string"}}},
            {"type": "object", "properties": {"name": {"type": "string"}}},
        ]
    }
    mock_client.get_openapi_spec.return_value = spec
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["describe_resource_schema"]({"resource_type": "lexicon", "operation": "get"})
    data = json.loads(result[0].text)
    assert data["fields"] == []
    assert "note" in data
    assert "verbose" in data["note"].lower()


def test_describe_resource_schema_create_composed_schema_notes_no_fields(mock_client, state, cache):
    """A POST request-body schema using oneOf/allOf/anyOf/$ref composition (no top-level
    'properties') must not silently look like zero fields with no explanation — this is
    the tool's primary use case (helping before cognigy_create/cognigy_update calls), so
    the composed-schema note must not be limited to 'get'."""
    spec = copy.deepcopy(FIXTURE_SPEC)
    spec["paths"]["/v2.0/lexicons"]["post"]["requestBody"]["content"]["application/json"]["schema"] = {
        "oneOf": [
            {"type": "object", "properties": {"name": {"type": "string"}}},
            {"type": "object", "properties": {"ref": {"type": "string"}}},
        ]
    }
    mock_client.get_openapi_spec.return_value = spec
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["describe_resource_schema"]({"resource_type": "lexicon", "operation": "create"})
    data = json.loads(result[0].text)
    assert data["fields"] == []
    assert "note" in data
    assert "verbose" in data["note"].lower()


def test_describe_resource_schema_update_composed_schema_notes_no_fields(mock_client, state, cache):
    """Same as create's composed-schema note, but for the 'update' (PATCH) operation —
    the reviewer's must-fix finding explicitly calls out both create and update."""
    spec = copy.deepcopy(FIXTURE_SPEC)
    spec["paths"]["/v2.0/lexicons/{lexiconId}"]["patch"]["requestBody"]["content"]["application/json"]["schema"] = {
        "allOf": [{"$ref": "#/components/schemas/LexiconUpdate"}]
    }
    mock_client.get_openapi_spec.return_value = spec
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["describe_resource_schema"]({"resource_type": "lexicon", "operation": "update"})
    data = json.loads(result[0].text)
    assert data["fields"] == []
    assert "note" in data
    assert "verbose" in data["note"].lower()


def test_describe_resource_schema_spec_cache_ttl_expiry_triggers_refetch(mock_client, state, cache):
    """make_handlers's internal spec_cache always uses a hardcoded ttl=86400, ignoring
    the ttl of the Cache instance passed in — so to force staleness we must write an
    on-disk entry whose _cached_at timestamp is already older than 86400s (mirroring
    tests/test_cache.py's ttl=-1 trick, but applied at the timestamp level since the
    handler's own Cache instance's ttl can't be overridden from the test)."""
    mock_client.get_openapi_spec.return_value = copy.deepcopy(FIXTURE_SPEC)

    # Pre-populate the same on-disk location make_handlers's spec_cache will read from,
    # using a Cache instance with ttl=-1 so the *write* itself considers any future read
    # stale — then directly age the file's _cached_at so make_handlers's own spec_cache
    # (hardcoded ttl=86400) also considers it stale, since freshness is ttl (per-instance)
    # compared against the persisted timestamp, not something baked into the entry itself.
    stale_cache = Cache(cache_dir=cache.cache_dir, ttl=-1)
    stale_cache.set("openapi", "spec", copy.deepcopy(FIXTURE_SPEC))
    entry_path = cache.cache_dir / "openapi" / "spec.json"
    entry = json.loads(entry_path.read_text())
    entry["_cached_at"] -= 100_000  # older than the 86400s ttl make_handlers uses
    entry_path.write_text(json.dumps(entry))

    handlers = make_handlers(mock_client, state, cache)
    handlers["describe_resource_schema"]({"resource_type": "lexicons", "operation": "create"})
    handlers["describe_resource_schema"]({"resource_type": "lexicons", "operation": "update"})

    # The pre-existing entry is stale on the very first call, triggering a refetch (which
    # re-persists a fresh entry) — so the *second* call then hits the fresh cache and does
    # NOT refetch again. This proves the stale entry did trigger exactly one refetch rather
    # than being silently reused.
    assert mock_client.get_openapi_spec.call_count == 1


def test_describe_resource_schema_node_resource_type_create(mock_client, state, cache):
    """resource_type='node' is explicitly special-cased in the tool description (only
    the generic envelope is covered, not per-node-type 'config') but was previously
    completely untested. Use a fixture path matching the real Cognigy API shape:
    /v2.0/flows/{flowId}/chart/nodes."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/v2.0/flows/{flowId}/chart/nodes": {
                "post": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["type"],
                                    "properties": {
                                        "type": {"type": "string", "description": "The node type"},
                                        "label": {"type": "string"},
                                        "target": {"type": "string"},
                                    },
                                }
                            }
                        }
                    }
                }
            }
        },
    }
    mock_client.get_openapi_spec.return_value = spec
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["describe_resource_schema"]({"resource_type": "node", "operation": "create"})
    data = json.loads(result[0].text)
    assert data["path"] == "/v2.0/flows/{flowId}/chart/nodes"
    names = {f["field"] for f in data["fields"]}
    assert "type" in names


def test_describe_resource_schema_verbose_get_returns_raw_schema(mock_client, state, cache):
    """verbose=True for 'get' must return raw_schema, matching the pattern already
    covered for 'create'."""
    mock_client.get_openapi_spec.return_value = copy.deepcopy(FIXTURE_SPEC)
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["describe_resource_schema"](
        {"resource_type": "lexicons", "operation": "get", "verbose": True}
    )
    data = json.loads(result[0].text)
    assert "fields" not in data
    assert data["raw_schema"]["properties"]["name"]["description"] == "The name"


def test_describe_resource_schema_ref_request_body_resolves_to_real_fields(mock_client, state, cache):
    """A bare {"$ref": "#/components/schemas/X"} request-body schema must be resolved
    against spec['components']['schemas']['X'] so the simplified 'fields' list reflects
    the target schema's real properties, not an empty list."""
    spec = copy.deepcopy(FIXTURE_SPEC)
    spec["paths"]["/v2.0/lexicons"]["post"]["requestBody"]["content"]["application/json"]["schema"] = {
        "$ref": "#/components/schemas/LexiconCreate"
    }
    spec["components"] = {
        "schemas": {
            "LexiconCreate": {
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name": {"type": "string", "description": "The name of the lexicon"},
                    "projectId": {"type": "string"},
                },
            }
        }
    }
    mock_client.get_openapi_spec.return_value = spec
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["describe_resource_schema"]({"resource_type": "lexicon", "operation": "create"})
    data = json.loads(result[0].text)
    by_name = {f["field"]: f for f in data["fields"]}
    assert by_name["name"]["required"] is True
    assert by_name["projectId"]["required"] is False
    assert "note" not in data


def test_describe_resource_schema_ref_target_missing_falls_back_gracefully(mock_client, state, cache):
    """If a $ref doesn't resolve to anything in components.schemas, resolution must
    fail gracefully (no crash) and the existing composed-schema note behavior kicks in."""
    spec = copy.deepcopy(FIXTURE_SPEC)
    spec["paths"]["/v2.0/lexicons"]["post"]["requestBody"]["content"]["application/json"]["schema"] = {
        "$ref": "#/components/schemas/DoesNotExist"
    }
    # No 'components' key at all in spec, to exercise the missing-lookup path.
    mock_client.get_openapi_spec.return_value = spec
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["describe_resource_schema"]({"resource_type": "lexicon", "operation": "create"})
    data = json.loads(result[0].text)
    assert data["fields"] == []
    assert "note" in data
    assert "verbose" in data["note"].lower()


def test_describe_resource_schema_verbose_ref_returns_resolved_schema(mock_client, state, cache):
    """verbose=True for a $ref-based schema must return the resolved target schema
    (with real properties), not the bare unresolved {"$ref": ...} pointer."""
    spec = copy.deepcopy(FIXTURE_SPEC)
    spec["paths"]["/v2.0/lexicons"]["post"]["requestBody"]["content"]["application/json"]["schema"] = {
        "$ref": "#/components/schemas/LexiconCreate"
    }
    spec["components"] = {
        "schemas": {
            "LexiconCreate": {
                "type": "object",
                "required": ["name"],
                "properties": {"name": {"type": "string"}},
            }
        }
    }
    mock_client.get_openapi_spec.return_value = spec
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["describe_resource_schema"](
        {"resource_type": "lexicons", "operation": "create", "verbose": True}
    )
    data = json.loads(result[0].text)
    assert "properties" in data["raw_schema"]
    assert data["raw_schema"]["properties"]["name"]["type"] == "string"


def test_describe_resource_schema_allof_ref_merges_inline_properties(mock_client, state, cache):
    """A single-level allOf: [{"$ref": ...}, {inline properties}] must merge the
    resolved $ref's properties with the inline properties in the simplified fields list."""
    spec = copy.deepcopy(FIXTURE_SPEC)
    spec["paths"]["/v2.0/lexicons/{lexiconId}"]["patch"]["requestBody"]["content"]["application/json"]["schema"] = {
        "allOf": [
            {"$ref": "#/components/schemas/LexiconBase"},
            {"type": "object", "properties": {"extra": {"type": "boolean"}}},
        ]
    }
    spec["components"] = {
        "schemas": {
            "LexiconBase": {
                "type": "object",
                "required": ["name"],
                "properties": {"name": {"type": "string"}},
            }
        }
    }
    mock_client.get_openapi_spec.return_value = spec
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["describe_resource_schema"]({"resource_type": "lexicon", "operation": "update"})
    data = json.loads(result[0].text)
    names = {f["field"] for f in data["fields"]}
    assert names == {"name", "extra"}


def test_describe_resource_schema_narrowed_exception_does_not_swallow_internal_bug(mock_client, state, cache):
    """The except clause must be narrowed to data-shape exceptions (AttributeError,
    TypeError, KeyError, IndexError) — a genuinely new bug class like ZeroDivisionError
    raised from within the try block must propagate, not be silently swallowed as
    schema_parse_error."""
    import cognigy_mcp.tools.schema_tools as schema_tools_module

    def _boom(*args, **kwargs):
        raise ZeroDivisionError("simulated internal bug")

    mock_client.get_openapi_spec.return_value = copy.deepcopy(FIXTURE_SPEC)
    handlers = make_handlers(mock_client, state, cache)
    original = schema_tools_module._find_candidate_path
    schema_tools_module._find_candidate_path = _boom
    try:
        try:
            handlers["describe_resource_schema"]({"resource_type": "lexicons", "operation": "create"})
            raised = False
        except ZeroDivisionError:
            raised = True
    finally:
        schema_tools_module._find_candidate_path = original
    assert raised is True


def test_describe_resource_schema_fallback_operation_not_available_has_warning(mock_client, state, cache):
    """When a fallback (substring) match's path lacks the requested HTTP method, the
    'operation not available' error must still carry the 'this was only a guess'
    warning — otherwise a caller could act on available_methods for an unrelated
    resource without knowing the match was non-exact."""
    spec = copy.deepcopy(FIXTURE_SPEC)
    # 'onlygettable' only has 'get' and will be found via fallback substring search
    # when the requested rtype doesn't exactly match any top-level path.
    spec["paths"]["/v2.0/somethingonlygettablewrapper"] = spec["paths"].pop("/v2.0/onlygettable")
    mock_client.get_openapi_spec.return_value = spec
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["describe_resource_schema"]({"resource_type": "onlygettable", "operation": "create"})
    data = json.loads(result[0].text)
    assert "error" in data
    assert "warning" in data


def test_describe_resource_schema_update_simplified_fields_lexicon(mock_client, state, cache):
    """Direct happy-path test for operation='update' in simplified (non-verbose) mode
    against the /v2.0/lexicons/{lexiconId} fixture path — asserts the 'fields' list
    directly rather than only incidentally via cache/composed-schema tests."""
    mock_client.get_openapi_spec.return_value = copy.deepcopy(FIXTURE_SPEC)
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["describe_resource_schema"]({"resource_type": "lexicon", "operation": "update"})
    data = json.loads(result[0].text)
    assert data["path"] == "/v2.0/lexicons/{lexiconId}"
    assert data["method"] == "patch"
    by_name = {f["field"]: f for f in data["fields"]}
    assert set(by_name) == {"name"}


def test_describe_resource_schema_invalid_operation_returns_validation_error(mock_client, state, cache):
    """An operation value outside the Literal[...] must produce the shared Pydantic
    validate() error path's response, mirroring test_flow_ops.py's validation-error
    tests for other tools."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["describe_resource_schema"]({"resource_type": "lexicons", "operation": "nonexistent"})
    assert result.isError is True
    data = json.loads(result.content[0].text)
    assert data["error"] == "Invalid tool arguments"
    assert any(d["field"] == "operation" for d in data["details"])


def test_describe_resource_schema_missing_resource_type_returns_validation_error(mock_client, state, cache):
    """A missing required resource_type must produce the shared Pydantic validate()
    error path's response."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["describe_resource_schema"]({"operation": "create"})
    assert result.isError is True
    data = json.loads(result.content[0].text)
    assert data["error"] == "Invalid tool arguments"
    assert any(d["field"] == "resource_type" for d in data["details"])


def test_describe_resource_schema_verbose_delete_returns_empty_raw_schema(mock_client, state, cache):
    """verbose=True for 'delete' must not fabricate content — delete has no body, and
    _raw_schema_fragment's current behavior for operation='delete' is to return {} (its
    final fallback branch). This test locks in that actual behavior rather than
    inventing new semantics for it."""
    mock_client.get_openapi_spec.return_value = copy.deepcopy(FIXTURE_SPEC)
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["describe_resource_schema"](
        {"resource_type": "lexicons", "operation": "delete", "verbose": True}
    )
    data = json.loads(result[0].text)
    assert "fields" not in data
    assert data["raw_schema"] == {}


FIXTURE_DESCRIPTORS_RESPONSE = {
    "items": [
        {
            "type": "say",
            "fields": [
                {
                    "type": "cognigyTextArray",
                    "key": "say",
                    "label": "Say",
                    "defaultValue": {"text": []},
                },
                {
                    "type": "select",
                    "key": "handoverOutput",
                    "label": "Handover Output",
                    "description": "Who sees this message",
                    "defaultValue": "userAndAgent",
                    "params": {
                        "required": True,
                        "options": [
                            {"label": "User and agent", "value": "userAndAgent"},
                            {"label": "User only", "value": "userOnly"},
                        ],
                    },
                },
                {
                    "type": "toggle",
                    "key": "preventTranscript",
                    "label": "Prevent Transcript",
                    "defaultValue": False,
                },
            ],
        },
        {
            "type": "if",
            "fields": [
                {"type": "condition", "key": "condition", "label": "Condition"},
            ],
        },
    ],
    "total": 2,
    "nextCursor": None,
    "previousCursor": None,
}


def test_describe_resource_schema_node_type_simplified_fields(mock_client, state, cache):
    mock_client.get.return_value = copy.deepcopy(FIXTURE_DESCRIPTORS_RESPONSE)
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["describe_resource_schema"](
        {"resource_type": "node", "node_type": "say", "flow_id": "flow-1"}
    )
    data = json.loads(result[0].text)
    assert data["resource_type"] == "node"
    assert data["node_type"] == "say"
    assert data["flow_id"] == "flow-1"
    by_field = {f["field"]: f for f in data["fields"]}
    assert set(by_field) == {"say", "handoverOutput", "preventTranscript"}
    assert by_field["handoverOutput"]["required"] is True
    assert by_field["handoverOutput"]["options"] == ["userAndAgent", "userOnly"]
    assert by_field["handoverOutput"]["default"] == "userAndAgent"
    assert by_field["preventTranscript"]["type"] == "toggle"
    mock_client.get.assert_called_once_with("/v2.0/flows/flow-1/chart/descriptors")


def test_describe_resource_schema_node_type_verbose_returns_raw_fields(mock_client, state, cache):
    mock_client.get.return_value = copy.deepcopy(FIXTURE_DESCRIPTORS_RESPONSE)
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["describe_resource_schema"](
        {"resource_type": "node", "node_type": "if", "flow_id": "flow-1", "verbose": True}
    )
    data = json.loads(result[0].text)
    assert "fields" not in data
    assert data["raw_fields"] == [{"type": "condition", "key": "condition", "label": "Condition"}]


def test_describe_resource_schema_node_type_unknown_lists_known_types(mock_client, state, cache):
    mock_client.get.return_value = copy.deepcopy(FIXTURE_DESCRIPTORS_RESPONSE)
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["describe_resource_schema"](
        {"resource_type": "node", "node_type": "doesNotExist", "flow_id": "flow-1"}
    )
    data = json.loads(result[0].text)
    assert "No node descriptor found" in data["error"]
    assert data["known_node_types"] == ["if", "say"]


def test_describe_resource_schema_node_type_caches_descriptors_across_calls(mock_client, state, cache):
    mock_client.get.return_value = copy.deepcopy(FIXTURE_DESCRIPTORS_RESPONSE)
    handlers = make_handlers(mock_client, state, cache)
    handlers["describe_resource_schema"]({"resource_type": "node", "node_type": "say", "flow_id": "flow-1"})
    handlers["describe_resource_schema"]({"resource_type": "node", "node_type": "if", "flow_id": "flow-1"})
    assert mock_client.get.call_count == 1


def test_describe_resource_schema_node_type_handler_returns_api_error_response(mock_client, state, cache):
    mock_client.get.side_effect = ApiError(500, "boom")
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["describe_resource_schema"](
        {"resource_type": "node", "node_type": "say", "flow_id": "flow-1"}
    )
    data = json.loads(result[0].text)
    assert data["error"] == "api_error"
    assert data["status"] == 500
    assert "boom" in data["detail"]
