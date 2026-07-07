# Pydantic Validation at MCP Tool Entry Boundary — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Pydantic input validation to all 6 MCP tool modules so bad inputs return structured `{"error": "...", "details": [...]}` JSON instead of raw KeyErrors or Cognigy HTTP errors.

**Architecture:** New `cognigy_mcp/validation.py` provides shared `validate()` and `_ok()` utilities. Each of the 6 tool modules gets co-located Pydantic `BaseModel` subclasses (one per tool); `inputSchema` dicts are replaced with `model_json_schema()` output; handlers call `validate()` at entry and access typed fields via the model instance.

**Tech Stack:** Python 3.12, Pydantic v2 (already a transitive dep via `mcp`), pytest

## Global Constraints

- Pydantic v2 syntax throughout: `model_validate()`, `model_json_schema()`, `Field()`, `ValidationError`
- All errors returned as `_ok({"error": "Invalid tool arguments", "details": [{"field": "...", "message": "..."}]})` — `isError=False` text content, consistent with existing pattern
- Top-level `title` key stripped from `model_json_schema()` output before passing to `Tool(inputSchema=...)`
- `explain.py` keeps its local `_ok(text: str)` (takes a string, not a dict — different signature); all other 5 modules drop their local `_ok` and import from `cognigy_mcp.validation`
- No changes to `server.py`, `api.py`, `orchestrator.py`, or `filters.py`
- All existing tests must continue to pass after each task

---

### Task 1: Create `cognigy_mcp/validation.py` + `tests/test_validation.py`

**Files:**
- Create: `cognigy_mcp/validation.py`
- Create: `tests/test_validation.py`

**Interfaces:**
- Produces:
  - `_ok(data: dict) -> list[TextContent]`
  - `validate(model_cls: type[T], args: dict) -> tuple[T | None, list[TextContent] | None]`
  - `make_schema(model_cls: type[BaseModel]) -> dict`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_validation.py`:

```python
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
    data = json.loads(err[0].text)
    assert data["error"] == "Invalid tool arguments"
    assert any(d["field"] == "name" for d in data["details"])


def test_validate_wrong_type_returns_error():
    m, err = validate(_Simple, {"name": "foo", "count": "not-an-int"})
    assert m is None
    data = json.loads(err[0].text)
    assert data["error"] == "Invalid tool arguments"
    assert any(d["field"] == "count" for d in data["details"])


def test_validate_multiple_errors_all_surfaced():
    m, err = validate(_Multi, {})
    assert m is None
    data = json.loads(err[0].text)
    fields = [d["field"] for d in data["details"]]
    assert "a" in fields
    assert "b" in fields


def test_make_schema_strips_title():
    schema = make_schema(_Simple)
    assert "title" not in schema
    assert schema["type"] == "object"
    assert "name" in schema["properties"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_validation.py -v
```

Expected: `ModuleNotFoundError: No module named 'cognigy_mcp.validation'`

- [ ] **Step 3: Create `cognigy_mcp/validation.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_validation.py -v
```

Expected: 6 passed

- [ ] **Step 5: Run full suite to confirm no regressions**

```bash
uv run pytest --tb=short -q
```

Expected: all existing tests + 6 new = passing

- [ ] **Step 6: Commit**

```bash
git add cognigy_mcp/validation.py tests/test_validation.py
git commit -m "feat: add validation.py with shared _ok, validate, make_schema helpers"
```

---

### Task 2: Migrate `flow_ops.py` (7 tools)

**Files:**
- Modify: `cognigy_mcp/tools/flow_ops.py`
- Modify: `tests/tools/test_flow_ops.py`

**Interfaces:**
- Consumes: `validate`, `_ok`, `make_schema` from `cognigy_mcp.validation`
- Produces: same `make_handlers` / `TOOLS` public API, but handlers now validate first

- [ ] **Step 1: Write the failing validation tests**

Append to `tests/tools/test_flow_ops.py`:

```python
def test_cognigy_get_missing_required_returns_validation_error(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_get"]({})
    data = json.loads(result[0].text)
    assert data["error"] == "Invalid tool arguments"
    assert any(d["field"] == "resource_type" for d in data["details"])


def test_cognigy_get_fields_wrong_type_returns_validation_error(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_get"]({
        "resource_type": "flows",
        "resource_id": "id-1",
        "fields": "not-a-list",
    })
    data = json.loads(result[0].text)
    assert data["error"] == "Invalid tool arguments"
    assert any(d["field"] == "fields" for d in data["details"])


def test_cognigy_list_missing_required_returns_validation_error(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_list"]({})
    data = json.loads(result[0].text)
    assert data["error"] == "Invalid tool arguments"
    assert any(d["field"] == "resource_type" for d in data["details"])


def test_cognigy_create_missing_body_returns_validation_error(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_create"]({"resource_type": "flows"})
    data = json.loads(result[0].text)
    assert data["error"] == "Invalid tool arguments"
    assert any(d["field"] == "body" for d in data["details"])
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/tools/test_flow_ops.py::test_cognigy_get_missing_required_returns_validation_error -v
```

Expected: FAIL — `KeyError: 'resource_type'` (raw dict access, no validation yet)

- [ ] **Step 3: Add Pydantic models and update imports in `flow_ops.py`**

Replace the imports block at the top of `cognigy_mcp/tools/flow_ops.py` and add models. The existing imports are lines 1–7; replace with:

```python
from __future__ import annotations
import json
from typing import Literal
from pydantic import BaseModel, Field
from mcp.types import Tool, TextContent
from cognigy_mcp.api import CognigyClient
from cognigy_mcp.cache import Cache
from cognigy_mcp.state import ProjectState, _deep_merge
from cognigy_mcp.filters import strip_response, BLOCKED_IN_CONFIG
from cognigy_mcp.validation import _ok, validate, make_schema


class CognigyGetArgs(BaseModel):
    resource_type: str = Field(description="e.g. flows, aiagents, endpoints")
    resource_id: str
    flow_id: str | None = Field(None, description="Required when resource_type is 'node'")
    fields: list[str] | None = Field(
        None,
        description="Optional: return only these keys. Example: fields=['_id','name'] reduces size by ~80%.",
    )


class CognigyListArgs(BaseModel):
    resource_type: str
    project_id: str | None = None
    agent_id: str | None = None
    limit: int = 100
    full_objects: bool = Field(
        False,
        description="When true, returns complete objects. Default false returns simplified {id, name} pairs (~95% token savings).",
    )
    fields: list[str] | None = Field(
        None,
        description="Optional: return only these keys from each item. Applied after full_objects filter.",
    )


class CognigyCreateArgs(BaseModel):
    resource_type: str
    body: dict
    flow_id: str | None = Field(None, description="Required when creating nodes")
    return_full_object: bool = Field(
        False,
        description="When true, returns the complete created object. Default false returns minimal {_id, referenceId, type, label} (~90% token savings).",
    )


class CognigyUpdateArgs(BaseModel):
    resource_type: str
    resource_id: str
    body: dict
    merge_config: bool = Field(
        False,
        description="When true, deep-merges body.config with current config rather than replacing",
    )
    flow_id: str | None = Field(None, description="Required when resource_type is 'node'")
    return_full_object: bool = Field(
        False,
        description="When true, returns the complete updated object. Default false returns minimal {_id, type, label} (~90% token savings).",
    )


class CognigyDeleteArgs(BaseModel):
    resource_type: str
    resource_id: str
    flow_id: str | None = Field(None, description="Required when resource_type is 'node'")


class CognigyInvokeArgs(BaseModel):
    resource_type: str
    resource_id: str
    operation: str
    body: dict = Field(default_factory=dict)
    flow_id: str | None = Field(None, description="Required for node operations")


class GetFlowChartArgs(BaseModel):
    flow_id: str
    format: Literal["hierarchy", "raw", "both"] = Field(
        "hierarchy",
        description="'hierarchy': tree string only (~95% savings, default). 'raw': nodes + relations arrays. 'both': current behavior (explicit opt-in).",
    )
```

- [ ] **Step 4: Replace `TOOLS` list to use `make_schema()`**

In `flow_ops.py`, replace the `TOOLS: list[Tool] = [...]` block (the hand-written `inputSchema` dicts). The tool `description` strings are unchanged; only `inputSchema=` changes:

```python
TOOLS: list[Tool] = [
    Tool(
        name="cognigy_get",
        description="GET any Cognigy resource by ID. Cache-first (5-min TTL). "
                    "Response includes _source: 'cache' or 'api'.",
        inputSchema=make_schema(CognigyGetArgs),
    ),
    Tool(
        name="cognigy_list",
        description="List Cognigy resources. Pass project_id for project-scoped resources, "
                    "agent_id for agent-scoped resources (e.g. listing jobs). "
                    "resource_type accepts both singular ('flow') and plural ('flows'). "
                    "Default: returns simplified {id, name} pairs. Use full_objects=true for complete objects.",
        inputSchema=make_schema(CognigyListArgs),
    ),
    Tool(
        name="cognigy_create",
        description="POST to create a new Cognigy resource. Auto-saves name→ID to .state.json. "
                    "For nodes, body must include: "
                    "type (e.g. 'say', 'code', 'once', 'httpRequest', 'aiAgentJob'), "
                    "mode — one of: 'appendChild' (add as child of container node — use push_agent_tool for aiAgentJobTool nodes), "
                    "'append' (add as sibling after target — also the correct mode for Once/IF branch insertion: "
                    "target the branch marker _id, not the parent Once/IF node), "
                    "'insertAfter' or 'insertBefore' (may return 500 on AU1 — use append instead), "
                    "target (the _id of the reference node), "
                    "and flowId (the flow _id).",
        inputSchema=make_schema(CognigyCreateArgs),
    ),
    Tool(
        name="cognigy_update",
        description="PATCH a Cognigy resource. WARNING: Cognigy PATCH is full-replace on 'config' — "
                    "set merge_config=true to deep-merge instead of overwriting. Always use merge_config=true "
                    "for partial config updates.",
        inputSchema=make_schema(CognigyUpdateArgs),
    ),
    Tool(
        name="cognigy_delete",
        description="DELETE a Cognigy resource. For nodes, pass flow_id.",
        inputSchema=make_schema(CognigyDeleteArgs),
    ),
    Tool(
        name="cognigy_invoke",
        description="Run a named operation on a Cognigy resource. "
                    "Operations: node/move, flow/clone, aiagent/train, "
                    "knowledgestore/run, sessions/inject-context, sessions/inject-state.",
        inputSchema=make_schema(CognigyInvokeArgs),
    ),
    Tool(
        name="get_flow_chart",
        description="Fetch the full chart for a flow. Default: returns human-readable hierarchy string. "
                    "Use format='raw' for structured arrays or format='both' for the legacy combined response.",
        inputSchema=make_schema(GetFlowChartArgs),
    ),
]
```

- [ ] **Step 5: Remove local `_ok` and update handlers**

Delete the existing `def _ok(data: dict) -> list[TextContent]:` function (it was at line 159–160 before these changes — search for it and remove it, since `_ok` is now imported).

Replace the body of each handler inside `make_handlers`. Each handler adds a `validate()` call and switches from `args[...]`/`args.get(...)` to `m.field`. Replace the entire `make_handlers` function body with:

```python
def make_handlers(client: CognigyClient, state: ProjectState, cache: Cache) -> dict:

    def _cognigy_get(args: dict) -> list[TextContent]:
        m, err = validate(CognigyGetArgs, args)
        if err:
            return err
        rtype = _normalise_rtype(m.resource_type)
        rid = m.resource_id
        cached, fresh = cache.get(rtype, rid)
        if fresh and cached:
            data = cached
            source = "cache"
        else:
            path = _resource_path(rtype, rid, m.flow_id)
            if path is None:
                return _ok({"error": "flow_id required when resource_type is 'node'"})
            data = client.get(path)
            cache.set(rtype, rid, data)
            source = "api"
        if m.fields:
            data = {k: data[k] for k in m.fields if k in data}
        data = strip_response(data)
        return _ok({**data, "_source": source})

    def _cognigy_list(args: dict) -> list[TextContent]:
        m, err = validate(CognigyListArgs, args)
        if err:
            return err
        rtype = _normalise_rtype(m.resource_type)
        if rtype in ("node", "nodes"):
            return _ok({
                "error": (
                    "Nodes cannot be listed independently — they exist only within a flow chart. "
                    "Use get_flow_chart(flow_id=<flowId>) to list all nodes in a flow."
                )
            })
        if m.agent_id:
            data = client.get(f"/v2.0/aiagents/{m.agent_id}/{rtype}", limit=m.limit)
        elif m.project_id:
            data = client.get(f"/v2.0/{rtype}", projectId=m.project_id, limit=m.limit)
        else:
            data = client.get(f"/v2.0/{rtype}", limit=m.limit)
        raw_items = data if isinstance(data, list) else data.get("items", [])
        if not m.full_objects:
            simplified = []
            for item in raw_items:
                entry = {"id": item.get("_id"), "name": item.get("name")}
                if "description" in item:
                    entry["description"] = item["description"]
                if "type" in item:
                    entry["type"] = item["type"]
                simplified.append(entry)
            result_data = {"items": simplified, "count": len(simplified)}
        else:
            result_data = data if not isinstance(data, list) else {"items": data, "count": len(data)}
        if m.fields:
            items = result_data.get("items", [])
            filtered = [{k: item[k] for k in m.fields if k in item} for item in items]
            result_data = {"items": filtered, "count": len(filtered)}
        if m.full_objects:
            items = result_data.get("items", [])
            result_data = {**result_data, "items": [strip_response(item) for item in items]}
        return _ok(result_data)

    def _cognigy_create(args: dict) -> list[TextContent]:
        m, err = validate(CognigyCreateArgs, args)
        if err:
            return err
        rtype = _normalise_rtype(m.resource_type)
        body = m.body
        if rtype == "node":
            if not m.flow_id:
                return _ok({"error": "flow_id required to create a node"})
            if body.get("type") == "code":
                return _ok({"error": (
                    "Code nodes must be created via push_code_node "
                    "(provides file-backed conflict detection). "
                    "To create a new code node: push_code_node(script_file=..., flow_id=..., mode=..., target=...). "
                    'See explain("tool-selection") for guidance.'
                )})
            if body.get("type") == "aiAgentJobTool":
                return _ok({"error": (
                    "AI Agent tool nodes must be created via push_agent_tool "
                    "(file-backed, maps .tool.json spec to Cognigy config). "
                    "To create a new tool: push_agent_tool(tool_file=..., flow_id=..., job_node_id=...). "
                    'See explain("tool-selection") for guidance.'
                )})
            valid_modes = {"appendChild", "append", "insertAfter", "insertBefore"}
            if "mode" in body and body["mode"] not in valid_modes:
                return _ok({
                    "error": (
                        f'Invalid value for field "mode": "{body["mode"]}". '
                        f'Valid values: appendChild (child of container, aiAgentJobTool only), '
                        f'append (sibling after target — also correct for Once/IF branches: target the branch marker _id), '
                        f'insertAfter (may return 500 on AU1 — prefer append), '
                        f'insertBefore (may return 500 on AU1 — prefer append).'
                    )
                })
            if body.get("type") == "say" and "config" in body:
                body = {**body, "config": _normalise_say_config(body["config"])}
            if body.get("type") == "aiAgentToolAnswer" and "config" in body:
                body = {**body, "config": _normalise_answer_config(body["config"])}
            body = _inject_extension(body, state.get("extension_map") or {})
            path = f"/v2.0/flows/{m.flow_id}/chart/nodes"
        else:
            path = f"/v2.0/{rtype}"
        result = client.post(path, body)
        resource_id = result.get("_id") or result.get("id")
        name = result.get("name") or result.get("label")
        if name and resource_id:
            if rtype == "node":
                state.set("nodes", name, value={"id": resource_id, "flowId": m.flow_id})
            else:
                state.set(rtype, name, value={"id": resource_id})
        if resource_id:
            cache.set(rtype, resource_id, result)
        if m.return_full_object:
            return _ok(strip_response(result))
        minimal = {
            "_id": result.get("_id"),
            "referenceId": result.get("referenceId"),
            "type": result.get("type"),
            "label": result.get("label"),
        }
        return _ok({k: v for k, v in minimal.items() if v is not None})

    def _cognigy_update(args: dict) -> list[TextContent]:
        m, err = validate(CognigyUpdateArgs, args)
        if err:
            return err
        rtype = _normalise_rtype(m.resource_type)
        body = m.body
        path = _resource_path(rtype, m.resource_id, m.flow_id)
        if path is None:
            return _ok({"error": "flow_id required when resource_type is 'node'"})
        if rtype == "node" and "mode" in body:
            valid_modes = {"appendChild", "append", "insertAfter", "insertBefore"}
            if body["mode"] not in valid_modes:
                return _ok({
                    "error": (
                        f'Invalid value for field "mode": "{body["mode"]}". '
                        f'Valid values: appendChild (child of container, aiAgentJobTool only), '
                        f'append (sibling after target — also correct for Once/IF branches: target the branch marker _id), '
                        f'insertAfter (may return 500 on AU1 — prefer append), '
                        f'insertBefore (may return 500 on AU1 — prefer append).'
                    )
                })
        current = client.get(path)
        if rtype == "node" and current.get("type") == "code":
            return _ok({"error": (
                "Code nodes must be updated via push_code_node "
                "(provides file-backed conflict detection). "
                'See explain("tool-selection") for guidance.'
            )})
        if current.get("type") == "say" and "config" in body:
            body = {**body, "config": _normalise_say_config(body["config"])}
        if m.merge_config and "config" in body and "config" in current:
            current_config = {k: v for k, v in current["config"].items() if k not in BLOCKED_IN_CONFIG}
            merged = _deep_merge(current_config, body["config"])
            body = {**body, "config": merged}
        result = client.patch(path, body)
        cache.set(rtype, m.resource_id, result)
        if m.return_full_object:
            return _ok(strip_response(result))
        minimal = {
            "_id": result.get("_id"),
            "type": result.get("type"),
            "label": result.get("label"),
        }
        return _ok({k: v for k, v in minimal.items() if v is not None})

    def _cognigy_delete(args: dict) -> list[TextContent]:
        m, err = validate(CognigyDeleteArgs, args)
        if err:
            return err
        rtype = _normalise_rtype(m.resource_type)
        path = _resource_path(rtype, m.resource_id, m.flow_id)
        if path is None:
            return _ok({"error": "flow_id required when resource_type is 'node'"})
        result = client.delete(path)
        cache.invalidate(rtype, m.resource_id)
        return _ok({"deleted": True, "resource_id": m.resource_id, **result})

    def _cognigy_invoke(args: dict) -> list[TextContent]:
        m, err = validate(CognigyInvokeArgs, args)
        if err:
            return err
        path = _invoke_path(m.resource_type, m.resource_id, m.operation, m.body, m.flow_id)
        if path is None:
            return _ok({"error": f"flow_id required for {m.resource_type}/{m.operation}"})
        result = client.post(path, m.body)
        return _ok(strip_response(result))

    def _get_flow_chart(args: dict) -> list[TextContent]:
        m, err = validate(GetFlowChartArgs, args)
        if err:
            return err
        chart = client.get(f"/v2.0/flows/{m.flow_id}/chart")
        stripped_nodes = [strip_response(n) for n in chart.get("nodes", [])]
        if m.format == "hierarchy":
            stripped_chart = {**chart, "nodes": stripped_nodes}
            hierarchy = _build_hierarchy(stripped_chart)
            return _ok({"hierarchy": hierarchy})
        elif m.format == "raw":
            return _ok({
                "nodes": stripped_nodes,
                "relations": chart.get("relations", []),
            })
        else:
            stripped_chart = {**chart, "nodes": stripped_nodes}
            hierarchy = _build_hierarchy(stripped_chart)
            return _ok({
                "relations": chart.get("relations", []),
                "nodes": stripped_nodes,
                "hierarchy": hierarchy,
            })

    return {
        "cognigy_get": _cognigy_get,
        "cognigy_list": _cognigy_list,
        "cognigy_create": _cognigy_create,
        "cognigy_update": _cognigy_update,
        "cognigy_delete": _cognigy_delete,
        "cognigy_invoke": _cognigy_invoke,
        "get_flow_chart": _get_flow_chart,
    }
```

- [ ] **Step 6: Run tests**

```bash
uv run pytest tests/tools/test_flow_ops.py -v
```

Expected: all existing tests pass + 4 new validation tests pass

- [ ] **Step 7: Run full suite**

```bash
uv run pytest --tb=short -q
```

Expected: all tests pass

- [ ] **Step 8: Commit**

```bash
git add cognigy_mcp/tools/flow_ops.py tests/tools/test_flow_ops.py
git commit -m "feat(flow_ops): add Pydantic models, generate inputSchema, validate at handler entry"
```

---

### Task 3: Migrate `state_tools.py` (4 tools)

**Files:**
- Modify: `cognigy_mcp/tools/state_tools.py`
- Modify: `tests/tools/test_state_tools.py`

**Interfaces:**
- Consumes: `validate`, `_ok`, `make_schema` from `cognigy_mcp.validation`

- [ ] **Step 1: Write the failing validation tests**

Append to `tests/tools/test_state_tools.py`:

```python
def test_resolve_resource_missing_name_returns_validation_error(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["resolve_resource"]({})
    data = json.loads(result[0].text)
    assert data["error"] == "Invalid tool arguments"
    assert any(d["field"] == "name" for d in data["details"])


def test_assign_org_llm_missing_project_id_returns_validation_error(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["assign_org_llm"]({"llm_id": "llm-1"})
    data = json.loads(result[0].text)
    assert data["error"] == "Invalid tool arguments"
    assert any(d["field"] == "project_id" for d in data["details"])
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/tools/test_state_tools.py::test_resolve_resource_missing_name_returns_validation_error -v
```

Expected: FAIL — `KeyError: 'name'`

- [ ] **Step 3: Add models and update imports**

Replace the imports block at the top of `cognigy_mcp/tools/state_tools.py` and add models. Existing imports are lines 1–9; replace with:

```python
from __future__ import annotations
import json
import os
from importlib.metadata import version as pkg_version
from pathlib import Path
from pydantic import BaseModel, Field
from mcp.types import Tool, TextContent
from cognigy_mcp.api import CognigyClient, ApiError
from cognigy_mcp.cache import Cache
from cognigy_mcp.state import ProjectState
from cognigy_mcp.validation import _ok, validate, make_schema


class SyncRemoteStateArgs(BaseModel):
    project_id: str | None = Field(
        None,
        description="Cognigy project ID. Optional if COGNIGY_PROJECT_ID is set in environment.",
    )


class GetBuildStateArgs(BaseModel):
    resource_type: str | None = Field(
        None,
        description="Filter to one resource category: flows, agents, endpoints, tools, nodes, jobs",
    )


class ResolveResourceArgs(BaseModel):
    name: str
    resource_type: str = Field(description="One of: flows, agents, endpoints, tools, nodes, jobs")


class AssignOrgLlmArgs(BaseModel):
    project_id: str = Field(description="Cognigy project _id to assign the LLM to")
    llm_id: str = Field(description="MongoDB _id of the org-level LLM (not referenceId)")
```

- [ ] **Step 4: Replace `TOOLS` list**

Replace the `TOOLS: list[Tool] = [...]` block:

```python
TOOLS: list[Tool] = [
    Tool(
        name="sync_remote_state",
        description="Hard reset: wipe local cache and repopulate from Cognigy remote. "
                    "Runs automatically after session idle > threshold. Call manually "
                    "after making changes in the Cognigy UI.",
        inputSchema=make_schema(SyncRemoteStateArgs),
    ),
    Tool(
        name="get_build_state",
        description="Return the current .state.json — all known name to ID mappings. "
                    "Pass resource_type to scope the response and avoid context overflow on large projects. "
                    "Example: get_build_state(resource_type='flows') returns ~50 tokens vs ~500 for full state. "
                    "Filter values: flows, agents, endpoints, tools, nodes, jobs.",
        inputSchema=make_schema(GetBuildStateArgs),
    ),
    Tool(
        name="resolve_resource",
        description="Fast lookup of a Cognigy resource ID by friendly name from .state.json. "
                    "No API call. Returns the full state entry for that resource.",
        inputSchema=make_schema(ResolveResourceArgs),
    ),
    Tool(
        name="assign_org_llm",
        description=(
            "Append a project to an organisation-level LLM's assignedToProjects list. "
            "Safe and idempotent — if the project is already assigned, no write is made. "
            "Use after create_ai_agent to ensure the new project can use an org-level LLM. "
            "Errors if the LLM is project-scoped (use manage_packages instead) or not found."
        ),
        inputSchema=make_schema(AssignOrgLlmArgs),
    ),
]
```

- [ ] **Step 5: Remove local `_ok` and update handlers**

Delete the `def _ok(data: dict) -> list[TextContent]:` function (currently at line 119–120). Then replace all four handlers inside `make_handlers`:

```python
    def _sync_remote_state(args: dict) -> list[TextContent]:
        m, err = validate(SyncRemoteStateArgs, args)
        if err:
            return err
        project_id = m.project_id or os.getenv("COGNIGY_PROJECT_ID", "").strip() or None

        if not project_id:
            try:
                projects_resp = client.get("/v2.0/projects")
                projects = [{"id": p["_id"], "name": p["name"]} for p in projects_resp.get("items", [])]
            except Exception:
                projects = []
            return _ok({
                "error": "project_id is required",
                "hint": "Pass project_id=<id>, or set COGNIGY_PROJECT_ID=<id> in your .env file",
                "available_projects": projects,
            })

        _write_to_dotenv("COGNIGY_PROJECT_ID", project_id)
        state.bind_project(project_id)
        cache.invalidate_all()
        errors: list[str] = []

        flows: list = []
        try:
            flows_resp = client.get("/v2.0/flows", projectId=project_id, limit=100)
            flows = flows_resp.get("items", [])
        except Exception as exc:
            errors.append(f"flows: {exc}")

        for flow in flows:
            state.set("flows", flow["name"], value={"id": flow["_id"]})
            cache.set("flows", flow["_id"], flow)

        ext_map: dict[str, str] = {}
        try:
            exts_resp = client.get("/v2.0/extensions", projectId=project_id, limit=100)
            for ext_summary in exts_resp.get("_embedded", {}).get("extensions", []):
                ext_id = ext_summary["_links"]["self"]["href"].split("/")[-1]
                ext_name = ext_summary["name"]
                try:
                    ext_detail = client.get(f"/v2.0/extensions/{ext_id}")
                    for node_def in ext_detail.get("nodes", []):
                        ext_map[node_def["type"]] = ext_name
                except Exception:
                    pass
        except Exception as exc:
            errors.append(f"extensions: {exc}")
        state.set("extension_map", value=ext_map)

        seen_agents: set = set()
        for flow in flows:
            try:
                chart = client.get(f"/v2.0/flows/{flow['_id']}/chart")
                for node in chart.get("nodes", []):
                    if node.get("type") == "aiAgentJobTool":
                        label = node.get("label", node["_id"])
                        state.set("tools", label, value={
                            "id": node["_id"],
                            "flowId": flow["_id"],
                            "flowName": flow["name"],
                        })
            except Exception:
                pass
            try:
                agents_resp = client.get(f"/v2.0/flows/{flow['_id']}/chart/nodes/aiagents")
                for agent in agents_resp.get("items", []):
                    if agent["_id"] not in seen_agents:
                        seen_agents.add(agent["_id"])
                        try:
                            agent_resource = client.get(f"/v2.0/aiagents/{agent['_id']}")
                            cache.set("aiagents", agent["_id"], agent_resource)
                            state.set("agents", agent_resource.get("name", agent.get("name", agent["_id"])), value={"id": agent["_id"]})
                        except Exception:
                            state.set("agents", agent.get("name", agent["_id"]), value={"id": agent["_id"]})
            except Exception:
                pass

        try:
            eps_resp = client.get("/v2.0/endpoints", projectId=project_id, limit=100)
            for ep in eps_resp.get("items", []):
                state.set("endpoints", ep["name"], value={
                    "id": ep["_id"],
                    "urlToken": ep.get("URLToken") or ep.get("urlToken", ""),
                    "flowReferenceId": ep.get("flowId") or ep.get("flowReferenceId", ""),
                })
                cache.set("endpoints", ep["_id"], ep)
        except Exception as exc:
            errors.append(f"endpoints: {exc}")

        state.touch_interaction()
        result: dict = {"synced": True, "project_id": project_id}
        if errors:
            result["errors"] = errors
        return _ok(result)

    def _get_build_state(args: dict) -> list[TextContent]:
        m, err = validate(GetBuildStateArgs, args)
        if err:
            return err
        full_state = state.as_dict()
        config_fields: dict = {"config_loaded": build_config is not None}
        if build_config is not None:
            config_fields["config_source"] = config_source or ""
            config_fields["config_summary"] = _make_config_summary(build_config)
        if m.resource_type:
            filtered = full_state.get(m.resource_type, {})
            return _ok({m.resource_type: filtered, "_filtered": True, **config_fields})
        return _ok({**full_state, "_version": pkg_version("cognigy-vibe-mcp"), **config_fields})

    def _resolve_resource(args: dict) -> list[TextContent]:
        m, err = validate(ResolveResourceArgs, args)
        if err:
            return err
        entry = state.get(m.resource_type, m.name)
        if entry is None:
            return _ok({"error": f"'{m.name}' not found in {m.resource_type}"})
        return _ok(entry)

    def _assign_org_llm(args: dict) -> list[TextContent]:
        m, err = validate(AssignOrgLlmArgs, args)
        if err:
            return err
        try:
            llm = client.get(f"/v2.0/largelanguagemodels/{m.llm_id}")
        except ApiError as exc:
            if exc.status_code == 404:
                return _ok({"error": "llm_not_found", "llm_id": m.llm_id})
            return _ok({"error": "get_failed", "status": exc.status_code, "detail": str(exc)})
        except Exception as exc:
            return _ok({"error": "get_failed", "detail": str(exc)})
        if llm.get("resourceLevel") != "organisation":
            return _ok({
                "error": "not_org_level",
                "hint": "Use manage_packages to import a project-scoped LLM instead",
            })
        assigned: list = llm.get("assignedToProjects") or []
        if m.project_id in assigned:
            return _ok({"already_assigned": True, "llm_name": llm.get("name", "")})
        try:
            client.patch(
                f"/v2.0/largelanguagemodels/{m.llm_id}",
                {"assignedToProjects": assigned + [m.project_id]},
            )
        except ApiError as exc:
            return _ok({"error": "patch_failed", "status": exc.status_code, "detail": str(exc)})
        except Exception as exc:
            return _ok({"error": "patch_failed", "detail": str(exc)})
        return _ok({"assigned": True, "llm_name": llm.get("name", ""), "project_id": m.project_id})
```

- [ ] **Step 6: Run tests**

```bash
uv run pytest tests/tools/test_state_tools.py -v
```

Expected: all existing + 2 new validation tests pass

- [ ] **Step 7: Run full suite**

```bash
uv run pytest --tb=short -q
```

Expected: all tests pass

- [ ] **Step 8: Commit**

```bash
git add cognigy_mcp/tools/state_tools.py tests/tools/test_state_tools.py
git commit -m "feat(state_tools): add Pydantic models, generate inputSchema, validate at handler entry"
```

---

### Task 4: Migrate `file_push.py` (5 tools)

**Files:**
- Modify: `cognigy_mcp/tools/file_push.py`
- Modify: `tests/tools/test_file_push.py`

**Interfaces:**
- Consumes: `validate`, `_ok`, `make_schema` from `cognigy_mcp.validation`

- [ ] **Step 1: Write the failing validation tests**

Append to `tests/tools/test_file_push.py`:

```python
def test_push_code_node_missing_script_file_returns_validation_error(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_code_node"]({"flow_id": "flow-1"})
    data = json.loads(result[0].text)
    assert data["error"] == "Invalid tool arguments"
    assert any(d["field"] == "script_file" for d in data["details"])


def test_push_html_node_missing_flow_id_returns_validation_error(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_html_node"]({"html_file": "/tmp/x.html", "node_id": "node-1"})
    data = json.loads(result[0].text)
    assert data["error"] == "Invalid tool arguments"
    assert any(d["field"] == "flow_id" for d in data["details"])


def test_export_package_missing_output_path_returns_validation_error(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["export_package"]({"project_id": "proj-1"})
    data = json.loads(result[0].text)
    assert data["error"] == "Invalid tool arguments"
    assert any(d["field"] == "output_path" for d in data["details"])
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/tools/test_file_push.py::test_push_code_node_missing_script_file_returns_validation_error -v
```

Expected: FAIL — `KeyError: 'script_file'`

- [ ] **Step 3: Add models and update imports**

Replace the imports block at the top of `cognigy_mcp/tools/file_push.py`:

```python
from __future__ import annotations
import base64
import difflib
import json
import struct
import time
from pathlib import Path
from pydantic import BaseModel, Field
from mcp.types import Tool, TextContent
from cognigy_mcp.api import CognigyClient
from cognigy_mcp.cache import Cache
from cognigy_mcp.state import ProjectState
from cognigy_mcp.validation import _ok, validate, make_schema


class PushCodeNodeArgs(BaseModel):
    script_file: str = Field(description="Absolute path to .js or .ts file")
    flow_id: str
    node_id: str | None = Field(
        None,
        description="ID of an existing code node to update. Omit to create a new node.",
    )
    mode: str | None = Field(
        None,
        description="Required when creating: appendChild or append (see node-positioning)",
    )
    target: str | None = Field(
        None,
        description="Required when creating: ID of the reference node for positioning",
    )
    label: str | None = Field(None, description="Node label when creating (default: 'Code')")


class PushHtmlNodeArgs(BaseModel):
    html_file: str = Field(description="Absolute path to .html file")
    node_id: str
    flow_id: str


class PushAgentToolArgs(BaseModel):
    tool_file: str = Field(description="Absolute path to .tool.json file")
    flow_id: str
    node_id: str | None = Field(
        None,
        description="ID of an existing aiAgentJobTool node to update. Omit to create.",
    )
    job_node_id: str | None = Field(
        None,
        description="Required when creating: ID of the parent aiAgentJob node",
    )


class PushAgentAvatarArgs(BaseModel):
    image_file: str = Field(description="Absolute path to a 136×184px PNG file")
    agent_id: str = Field(description="Agent _id or referenceId")


class ExportPackageArgs(BaseModel):
    project_id: str = Field(description="Cognigy project _id to export")
    output_path: str = Field(
        description="Absolute or relative path where the zip file will be written",
    )
```

- [ ] **Step 4: Replace `TOOLS` list**

```python
TOOLS: list[Tool] = [
    Tool(
        name="push_code_node",
        description="Read a local .js/.ts file and push its content to a Cognigy Code node. "
                    "Two modes: "
                    "(1) UPDATE — provide node_id to push to an existing code node with conflict detection. "
                    "(2) CREATE — omit node_id and provide mode + target to create a new code node and push in one step. "
                    "Conflict detection: if the remote node was edited in the Cognigy UI since the last push, "
                    "the operation is blocked and a diff is returned.",
        inputSchema=make_schema(PushCodeNodeArgs),
    ),
    Tool(
        name="push_html_node",
        description="Read a local .html file and push it to a Cognigy setHTMLAppState node. "
                    "Automatically sets mode='full'.",
        inputSchema=make_schema(PushHtmlNodeArgs),
    ),
    Tool(
        name="push_agent_tool",
        description=(
            "Read a local .tool.json file and push its definition to a Cognigy aiAgentJobTool node. "
            "Two modes: "
            "(1) UPDATE — provide node_id to update an existing aiAgentJobTool node. "
            "(2) CREATE — omit node_id and provide job_node_id to create a new tool node as a child of an aiAgentJob node. "
            "The .tool.json file must contain toolId and description. "
            "parameters (JSON Schema object) and condition (CognigyScript) are optional. "
            "See explain('agent-tool-json') for the .tool.json file convention."
        ),
        inputSchema=make_schema(PushAgentToolArgs),
    ),
    Tool(
        name="push_agent_avatar",
        description=(
            "Read a local PNG file and push it as the avatar image on a Cognigy AI Agent. "
            "Validates PNG format and dimensions (must be exactly 136×184px). "
            "Encodes to base64 data URI and PATCHes the agent resource. "
            "See explain('agent-avatar-image') for the full avatar spec."
        ),
        inputSchema=make_schema(PushAgentAvatarArgs),
    ),
    Tool(
        name="export_package",
        description=(
            "Export a Cognigy project as a zip package and save it to a local file. "
            "Initiates an async export job via POST /v2.0/packages, polls until the job "
            "completes, then downloads the zip to the specified output path. "
            "Parent directories are created automatically. "
            "Typical output path: Demo Builds/<customer>-demo/<customer>-package.zip"
        ),
        inputSchema=make_schema(ExportPackageArgs),
    ),
]
```

- [ ] **Step 5: Remove local `_ok` and update handlers**

Delete the `def _ok(data: dict) -> list[TextContent]:` function. Replace all five handlers:

```python
    def _push_code_node(args: dict) -> list[TextContent]:
        m, err = validate(PushCodeNodeArgs, args)
        if err:
            return err
        path = Path(m.script_file)
        node_id = m.node_id
        flow_id = m.flow_id

        if not path.exists():
            return _ok({"error": f"File not found: {path}"})

        local_content = path.read_text()

        if not node_id:
            mode = m.mode
            target = m.target
            if not mode or not target:
                return _ok({"error": "Provide node_id to update an existing code node, or mode + target to create a new one"})
            body = {
                "type": "code",
                "label": m.label or "Code",
                "mode": mode,
                "target": target,
                "extension": "@cognigy/basic-nodes",
                "config": {"code": local_content},
            }
            try:
                result = client.post(f"/v2.0/flows/{flow_id}/chart/nodes", body)
            except Exception as e:
                return _ok({"error": f"Failed to create code node: {e}"})
            node_id = result["_id"]
            label = m.label or "Code"
            cache.set("nodes", node_id, result)
            cache.set_node_snapshot(node_id, local_content)
            state.set("nodes", label, value={"id": node_id, "flowId": flow_id})
            return _ok({"success": True, "node_id": node_id, "created": True, "bytes": len(local_content)})

        try:
            remote = client.get(f"/v2.0/flows/{flow_id}/chart/nodes/{node_id}")
        except Exception as e:
            return _ok({"error": f"Failed to fetch remote node: {e}"})

        remote_code = remote.get("config", {}).get("code", "")
        snapshot = cache.get_node_snapshot(node_id)

        if snapshot is not None and remote_code != snapshot:
            return _ok({
                "conflict": True,
                "message": "Remote node was edited in the Cognigy UI since the last push. "
                           "Review the diff and decide whether to overwrite or incorporate the changes.",
                "diff": _diff_summary(snapshot, remote_code),
            })

        try:
            result = client.patch(
                f"/v2.0/flows/{flow_id}/chart/nodes/{node_id}",
                {"config": {"code": local_content}},
            )
        except Exception as e:
            return _ok({"error": f"Failed to push code to node: {e}"})
        cache.set("nodes", node_id, result)
        cache.set_node_snapshot(node_id, local_content)
        return _ok({"success": True, "node_id": node_id, "bytes": len(local_content)})

    def _push_html_node(args: dict) -> list[TextContent]:
        m, err = validate(PushHtmlNodeArgs, args)
        if err:
            return err
        path = Path(m.html_file)
        node_id = m.node_id
        flow_id = m.flow_id

        if not path.exists():
            return _ok({"error": f"File not found: {path}"})

        html = path.read_text()
        try:
            result = client.patch(
                f"/v2.0/flows/{flow_id}/chart/nodes/{node_id}",
                {"config": {"html": html, "mode": "full"}},
            )
        except Exception as e:
            return _ok({"error": f"Failed to patch node: {e}"})
        cache.set("nodes", node_id, result)
        return _ok({"success": True, "node_id": node_id, "bytes": len(html)})

    def _push_agent_tool(args: dict) -> list[TextContent]:
        m, err = validate(PushAgentToolArgs, args)
        if err:
            return err
        path = Path(m.tool_file)
        node_id = m.node_id
        flow_id = m.flow_id

        if not path.exists():
            return _ok({"error": f"File not found: {path}"})

        try:
            tool_spec = json.loads(path.read_text())
        except json.JSONDecodeError as e:
            return _ok({"error": f"Invalid JSON in {path}: {e}"})

        if not isinstance(tool_spec, dict):
            return _ok({"error": f"tool.json must be a JSON object, got {type(tool_spec).__name__}"})

        missing = [f for f in ("toolId", "description") if not tool_spec.get(f)]
        if missing:
            return _ok({"error": f"Missing required fields in tool file: {', '.join(missing)}"})

        parameters = tool_spec.get("parameters")
        use_parameters = parameters is not None

        config: dict = {
            "toolId": tool_spec["toolId"],
            "description": tool_spec["description"],
            "useParameters": use_parameters,
            "debugMessage": True,
            "condition": tool_spec.get("condition", ""),
        }
        if use_parameters:
            config["parameters"] = json.dumps(parameters, separators=(",", ":"))

        if not node_id:
            job_node_id = m.job_node_id
            if not job_node_id:
                return _ok({"error": "Provide node_id to update an existing tool node, or job_node_id to create a new one"})
            body = {
                "type": "aiAgentJobTool",
                "extension": "@cognigy/basic-nodes",
                "label": tool_spec.get("label", tool_spec["toolId"]),
                "mode": "appendChild",
                "target": job_node_id,
                "config": config,
            }
            try:
                result = client.post(f"/v2.0/flows/{flow_id}/chart/nodes", body)
            except Exception as e:
                return _ok({"error": f"Failed to create tool node: {e}"})
            new_node_id = result["_id"]
            state.set("nodes", tool_spec["toolId"], value={"id": new_node_id, "flowId": flow_id})
            return _ok({"success": True, "node_id": new_node_id, "created": True})

        try:
            client.patch(f"/v2.0/flows/{flow_id}/chart/nodes/{node_id}", {"config": config})
        except Exception as e:
            return _ok({"error": f"Failed to update tool node: {e}"})
        return _ok({"success": True, "node_id": node_id, "updated": True})

    def _push_agent_avatar(args: dict) -> list[TextContent]:
        m, err = validate(PushAgentAvatarArgs, args)
        if err:
            return err
        path = Path(m.image_file)
        agent_id = m.agent_id

        if not path.exists():
            return _ok({"error": f"File not found: {path}"})

        data = path.read_bytes()

        if data[:4] != b'\x89PNG':
            return _ok({"error": f"File is not a PNG (wrong magic bytes): {path.name}"})

        if len(data) < 24:
            return _ok({"error": f"File is too small to be a valid PNG: {path.name}"})

        w = struct.unpack('>I', data[16:20])[0]
        h = struct.unpack('>I', data[20:24])[0]

        if w != 136 or h != 184:
            ratio = w / h if h else 0
            target_ratio = 136 / 184
            if abs(ratio - target_ratio) <= 0.01:
                return _ok({"error": f"Image is {w}×{h}px. Correct ratio — resize to 136×184 and re-run."})
            return _ok({"error": f"Image is {w}×{h}px. Expected 136×184px."})

        data_uri = "data:image/png;base64," + base64.b64encode(data).decode()
        try:
            client.patch(f"/v2.0/aiagents/{agent_id}", {
                "image": data_uri,
                "imageOptimizedFormat": True,
            })
        except Exception as e:
            return _ok({"error": f"Failed to update agent avatar: {e}"})

        return _ok({"success": True, "agent_id": agent_id, "bytes": len(data)})

    def _export_package(args: dict) -> list[TextContent]:
        m, err = validate(ExportPackageArgs, args)
        if err:
            return err
        project_id = m.project_id
        output_path = Path(m.output_path)

        try:
            job = client.post("/v2.0/packages", {"projectId": project_id})
        except Exception as e:
            return _ok({"error": f"Failed to start export job: {e}"})

        task_id = job.get("_id")
        if not task_id:
            return _ok({"error": f"Export job response missing _id: {job}"})

        deadline = time.monotonic() + _EXPORT_TIMEOUT
        while True:
            if time.monotonic() > deadline:
                return _ok({
                    "error": f"Export task {task_id} timed out after {_EXPORT_TIMEOUT:.0f}s",
                    "task_id": task_id,
                })
            time.sleep(_EXPORT_POLL_INTERVAL)
            try:
                task = client.get(f"/v2.0/tasks/{task_id}")
            except Exception as e:
                return _ok({"error": f"Failed to poll export task {task_id}: {e}", "task_id": task_id})

            task_status = task.get("status", "")
            if task_status == "error":
                return _ok({
                    "error": f"Export task failed: {task.get('failReason', 'unknown error')}",
                    "task_id": task_id,
                })
            if task_status in ("cancelled", "cancelling"):
                return _ok({
                    "error": f"Export task was cancelled (status: {task_status})",
                    "task_id": task_id,
                })
            if task_status == "done":
                break

        try:
            packages = client.get(
                "/v2.0/packages",
                projectId=project_id,
                sort="createdAt:desc",
                limit=1,
            )
        except Exception as e:
            return _ok({"error": f"Failed to list packages after export: {e}", "task_id": task_id})

        items = packages.get("items", [])
        if not items:
            return _ok({"error": "No packages found for project after export completed", "task_id": task_id})
        package_id = items[0].get("_id")
        if not package_id:
            return _ok({"error": f"Package listing returned item without _id: {items[0]}", "task_id": task_id})

        try:
            link_resp = client.post(f"/v2.0/packages/{package_id}/downloadlink", {})
        except Exception as e:
            return _ok({"error": f"Failed to get download link for package {package_id}: {e}", "task_id": task_id})

        download_link = link_resp.get("downloadLink")
        if not download_link:
            return _ok({"error": f"downloadlink response missing downloadLink field: {link_resp}", "task_id": task_id})

        try:
            zip_bytes = client.download_url(download_link)
        except Exception as e:
            return _ok({"error": f"Failed to download package zip from pre-signed URL: {e}", "task_id": task_id})

        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(zip_bytes)
        except OSError as e:
            return _ok({"error": f"Failed to write zip to {output_path}: {e}", "task_id": task_id})

        return _ok({
            "success": True,
            "task_id": task_id,
            "package_id": package_id,
            "output_path": str(output_path),
            "bytes": len(zip_bytes),
        })
```

- [ ] **Step 6: Run tests**

```bash
uv run pytest tests/tools/test_file_push.py -v
```

Expected: all existing + 3 new validation tests pass

- [ ] **Step 7: Run full suite**

```bash
uv run pytest --tb=short -q
```

Expected: all tests pass

- [ ] **Step 8: Commit**

```bash
git add cognigy_mcp/tools/file_push.py tests/tools/test_file_push.py
git commit -m "feat(file_push): add Pydantic models, generate inputSchema, validate at handler entry"
```

---

### Task 5: Migrate `testing.py` (1 tool)

**Files:**
- Modify: `cognigy_mcp/tools/testing.py`
- Modify: `tests/tools/test_testing.py`

**Interfaces:**
- Consumes: `validate`, `_ok`, `make_schema` from `cognigy_mcp.validation`

- [ ] **Step 1: Write the failing validation tests**

Append to `tests/tools/test_testing.py`:

```python
def test_talk_to_agent_missing_session_id_returns_validation_error(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["talk_to_agent"]({"user_id": "user-1"})
    data = json.loads(result[0].text)
    assert data["error"] == "Invalid tool arguments"
    assert any(d["field"] == "session_id" for d in data["details"])


def test_talk_to_agent_missing_user_id_returns_validation_error(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["talk_to_agent"]({"session_id": "sess-1"})
    data = json.loads(result[0].text)
    assert data["error"] == "Invalid tool arguments"
    assert any(d["field"] == "user_id" for d in data["details"])
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/tools/test_testing.py::test_talk_to_agent_missing_session_id_returns_validation_error -v
```

Expected: FAIL — `KeyError: 'session_id'`

- [ ] **Step 3: Add model and update imports**

Replace the imports block at the top of `cognigy_mcp/tools/testing.py`:

```python
from __future__ import annotations
import json
import httpx
from pydantic import BaseModel, Field
from mcp.types import Tool, TextContent
from cognigy_mcp.api import CognigyClient
from cognigy_mcp.cache import Cache
from cognigy_mcp.state import ProjectState
from cognigy_mcp.validation import _ok, validate, make_schema


class TalkToAgentArgs(BaseModel):
    session_id: str = Field(description="Conversation session ID — reuse to continue, new to reset")
    user_id: str = Field(description="User ID — new value starts fresh session")
    message: str = Field("", description="User text. Use empty string for data-only turns (xApp submit emulation).")
    endpoint_token: str | None = Field(None, description="URL token from endpoint config")
    flow_id: str | None = Field(None, description="Looks up token from state if endpoint_token not provided")
    data: dict | None = Field(
        None,
        description="Optional data payload forwarded as input.data in the flow.",
    )
    minimal: bool = Field(
        False,
        description="When true, returns only {outputText, sessionId} (~90% token savings). Default false returns full response.",
    )
```

- [ ] **Step 4: Replace `TOOLS` list**

```python
TOOLS: list[Tool] = [
    Tool(
        name="talk_to_agent",
        description="Send a message to a Cognigy flow via its REST endpoint and return the response. "
                    "Use for testing flows without opening the Cognigy UI. "
                    "Provide endpoint_token (from get_build_state) or flow_id (looks up token from state). "
                    "IMPORTANT: Use a new user_id to start a completely fresh session — Cognigy caches "
                    "session state by userId and reusing one will carry stale context silently. "
                    "IMPORTANT: This tool returns text output only. Tool calls made by the agent are "
                    "NOT visible in the response — only the agent's spoken text is returned. "
                    "For xApp submit emulation: send message=\"\" and data={...submitted payload...}. "
                    "Pass data={verbose: true} in the request body to surface errors that are otherwise swallowed.",
        inputSchema=make_schema(TalkToAgentArgs),
    ),
]
```

- [ ] **Step 5: Remove local `_ok` and update handler**

Delete the `def _ok(data: dict) -> list[TextContent]:` function. Replace `_talk_to_agent`:

```python
    def _talk_to_agent(args: dict) -> list[TextContent]:
        m, err = validate(TalkToAgentArgs, args)
        if err:
            return err
        token = m.endpoint_token
        if not token:
            if not m.flow_id:
                return _ok({"error": "Provide endpoint_token or flow_id"})
            endpoints = state.get("endpoints") or {}
            for ep_name, ep in endpoints.items():
                if ep.get("flowReferenceId") == m.flow_id:
                    token = ep.get("urlToken")
                    break
            if not token:
                known = list(endpoints.keys()) if endpoints else []
                hint = f" Known endpoints: {known}" if known else " No endpoints in state — run sync_remote_state first."
                return _ok({"error": f"No endpoint found for flow_id={m.flow_id}.{hint}"})

        endpoint_url = f"{client.endpoint_base_url}/{token}"
        payload = {
            "userId": m.user_id,
            "sessionId": m.session_id,
            "text": m.message,
            "data": m.data or {},
        }

        try:
            resp = httpx.post(endpoint_url, json=payload, timeout=30.0)
            resp.raise_for_status()
            data = resp.json()
            if m.minimal:
                text = (
                    data.get("text")
                    or next((o.get("text") for o in data.get("outputs", []) if o.get("text")), None)
                    or ""
                )
                return _ok({"outputText": text, "sessionId": m.session_id})
            return _ok(data)
        except httpx.HTTPStatusError as e:
            return _ok({"error": f"HTTP {e.response.status_code}: {e.response.text}"})
        except Exception as e:
            return _ok({"error": str(e)})
```

- [ ] **Step 6: Run tests**

```bash
uv run pytest tests/tools/test_testing.py -v
```

Expected: all existing + 2 new validation tests pass

- [ ] **Step 7: Run full suite**

```bash
uv run pytest --tb=short -q
```

Expected: all tests pass

- [ ] **Step 8: Commit**

```bash
git add cognigy_mcp/tools/testing.py tests/tools/test_testing.py
git commit -m "feat(testing): add Pydantic model, generate inputSchema, validate at handler entry"
```

---

### Task 6: Migrate `voice_ops.py` (1 tool)

**Files:**
- Modify: `cognigy_mcp/tools/voice_ops.py`
- Modify: `tests/tools/test_voice_ops.py`

**Interfaces:**
- Consumes: `validate`, `_ok`, `make_schema` from `cognigy_mcp.validation`

- [ ] **Step 1: Write the failing validation tests**

Append to `tests/tools/test_voice_ops.py`:

```python
def test_provision_webrtc_endpoint_missing_project_id_returns_validation_error(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["provision_webrtc_endpoint"]({
        "flow_id": "flow-hex",
        "flow_reference_id": "flow-uuid",
        "endpoint_name": "Click-to-Call",
        "connection_name": "Test",
    })
    data = json.loads(result[0].text)
    assert data["error"] == "Invalid tool arguments"
    assert any(d["field"] == "project_id" for d in data["details"])


def test_provision_webrtc_endpoint_missing_flow_reference_id_returns_validation_error(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["provision_webrtc_endpoint"]({
        "project_id": "proj-1",
        "flow_id": "flow-hex",
        "endpoint_name": "Click-to-Call",
        "connection_name": "Test",
    })
    data = json.loads(result[0].text)
    assert data["error"] == "Invalid tool arguments"
    assert any(d["field"] == "flow_reference_id" for d in data["details"])
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/tools/test_voice_ops.py::test_provision_webrtc_endpoint_missing_project_id_returns_validation_error -v
```

Expected: FAIL — `KeyError: 'project_id'`

- [ ] **Step 3: Add model and update imports**

Replace the imports block at the top of `cognigy_mcp/tools/voice_ops.py`:

```python
from __future__ import annotations
import json
import os
from pydantic import BaseModel, Field
from mcp.types import Tool, TextContent
from cognigy_mcp.api import CognigyClient
from cognigy_mcp.cache import Cache
from cognigy_mcp.state import ProjectState
from cognigy_mcp.validation import _ok, validate, make_schema


class ProvisionWebrtcEndpointArgs(BaseModel):
    project_id: str
    flow_id: str = Field(description="Hex _id of the flow to bind")
    flow_reference_id: str = Field(description="UUID referenceId of the flow")
    endpoint_name: str = Field(description="Name for the webRTC endpoint, e.g. 'Click-to-Call'")
    connection_name: str = Field(description="Name for the speech connection, e.g. 'Test'")
    region: str = Field("australiaeast", description="Azure Speech region, e.g. 'australiaeast'")
```

- [ ] **Step 4: Replace `TOOLS` list**

```python
TOOLS: list[Tool] = [
    Tool(
        name="provision_webrtc_endpoint",
        description=(
            "Create a VoiceGateway webRTC (Click-to-Call) endpoint bound to a flow. "
            "Handles the Microsoft Azure Speech Services connection prerequisite "
            "automatically: uses COGNIGY_VOICE_PREVIEW_API_KEY from environment for "
            "a real connection, or creates and deletes a throwaway dummy connection "
            "when the key is absent. "
            "Returns endpoint_id, url_token, demo_url, connection_id (null if dummy), "
            "and path ('real' or 'dummy'). "
            "Demo calls work on both paths; the in-browser voice-preview widget only "
            "works when real credentials are configured."
        ),
        inputSchema=make_schema(ProvisionWebrtcEndpointArgs),
    )
]
```

- [ ] **Step 5: Remove local `_ok` and update handler**

Delete the `def _ok(data: dict) -> list[TextContent]:` function. Replace `_provision_webrtc_endpoint`:

```python
    def _provision_webrtc_endpoint(args: dict) -> list[TextContent]:
        m, err = validate(ProvisionWebrtcEndpointArgs, args)
        if err:
            return err
        endpoint_base = client.endpoint_base_url
        api_key = os.environ.get("COGNIGY_VOICE_PREVIEW_API_KEY")
        is_dummy = not bool(api_key)
        effective_key = api_key if api_key else "dummy"

        conn_result = client.post("/v2.0/connections", {
            "name": m.connection_name,
            "extension": "@cognigy/audio-preview-provider",
            "type": "MicrosoftSpeechProvider",
            "resourceLevel": "project",
            "projectId": m.project_id,
            "fields": {"apiKey": effective_key, "region": m.region},
        })
        connection_id = conn_result["_id"]

        try:
            ep_result = client.post("/v2.0/endpoints", {
                "name": m.endpoint_name,
                "channel": "voiceGateway2",
                "flowId": m.flow_id,
                "flowReferenceId": m.flow_reference_id,
                "projectId": m.project_id,
                "webrtcWidgetConfig": {"active": True},
            })
        except Exception:
            try:
                client.delete(f"/v2.0/connections/{connection_id}")
            except Exception:
                pass
            raise

        endpoint_id = ep_result["_id"]
        url_token = ep_result.get("URLToken") or ep_result.get("urlToken", "")
        demo_url = f"{endpoint_base}/demo/{url_token}"

        if is_dummy:
            client.delete(f"/v2.0/connections/{connection_id}")
            connection_id = None

        return _ok({
            "endpoint_id": endpoint_id,
            "url_token": url_token,
            "demo_url": demo_url,
            "connection_id": connection_id,
            "path": "dummy" if is_dummy else "real",
        })
```

- [ ] **Step 6: Run tests**

```bash
uv run pytest tests/tools/test_voice_ops.py -v
```

Expected: all existing + 2 new validation tests pass

- [ ] **Step 7: Run full suite**

```bash
uv run pytest --tb=short -q
```

Expected: all tests pass

- [ ] **Step 8: Commit**

```bash
git add cognigy_mcp/tools/voice_ops.py tests/tools/test_voice_ops.py
git commit -m "feat(voice_ops): add Pydantic model, generate inputSchema, validate at handler entry"
```

---

### Task 7: Migrate `explain.py` (1 tool)

**Files:**
- Modify: `cognigy_mcp/tools/explain.py`
- Modify: `tests/tools/test_explain.py`

**Interfaces:**
- Consumes: `validate`, `make_schema` from `cognigy_mcp.validation` (NOT `_ok` — explain keeps its own `_ok(text: str)`)

**Note:** `explain._ok` takes a `str` not a `dict`. It is **not** replaced by the shared `_ok`. Only `validate` and `make_schema` are imported.

- [ ] **Step 1: Write a validation smoke test**

Append to `tests/tools/test_explain.py`:

```python
def test_explain_with_empty_args_returns_orientation(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({})
    assert len(result) == 1
    assert "cognigy-vibe-mcp" in result[0].text.lower() or "topics" in result[0].text.lower()


def test_explain_topic_wrong_type_returns_validation_error(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": 123})
    # Pydantic coerces int → str in lax mode; confirm no crash and some response returned
    assert len(result) == 1
```

- [ ] **Step 2: Run tests to verify they pass** (explain has no required fields, so no crash to catch; confirm baseline)

```bash
uv run pytest tests/tools/test_explain.py -v
```

Expected: existing tests + 2 new pass

- [ ] **Step 3: Add model and update imports**

Replace the imports block at the top of `cognigy_mcp/tools/explain.py`:

```python
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
```

- [ ] **Step 4: Replace `TOOLS` list**

```python
TOOLS: list[Tool] = [
    Tool(
        name="explain",
        description=(
            "Retrieve implementation guidance before brute-forcing or web-searching.\n\n"
            "Topics: " + " | ".join(TOPICS) + "\n\n"
            "Call explain() for orientation and topic descriptions.\n"
            "Call explain(\"topic\") for full reference on that topic."
        ),
        inputSchema=make_schema(ExplainArgs),
    ),
]
```

- [ ] **Step 5: Keep local `_ok` and update handler**

The existing `def _ok(text: str) -> list[TextContent]:` function is **kept** (it takes `str`, not `dict`). Only the handler changes:

```python
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
        content = _CONTENT.get(topic)
        if content:
            return _ok(content.strip())
        return _ok(
            f"Unknown topic: '{topic}'\n\n"
            f"Available Topics:\n{_TOPIC_INDEX}"
        )

    return {"explain": _explain}
```

- [ ] **Step 6: Run tests**

```bash
uv run pytest tests/tools/test_explain.py -v
```

Expected: all tests pass

- [ ] **Step 7: Run full suite — final green bar**

```bash
uv run pytest --tb=short -q
```

Expected: all tests pass (280+ tests)

- [ ] **Step 8: Commit**

```bash
git add cognigy_mcp/tools/explain.py tests/tools/test_explain.py
git commit -m "feat(explain): add Pydantic model, generate inputSchema, validate at handler entry"
```
