# Pydantic Validation at MCP Tool Entry Boundary

**Issue:** #131  
**Date:** 2026-07-07  
**Branch:** `feat/131-pydantic-validation`

## Problem

MCP tool inputs reach handler code as raw `dict` objects with no formal validation layer. Missing required fields produce `KeyError`; wrong types produce cryptic errors deep in handler logic or in Cognigy HTTP responses. Neither is actionable for an LLM caller.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Error format | `_ok({"error": "...", "details": [...]})` JSON text | Consistent with existing `_ok({"error": "..."})` pattern; no change to MCP protocol layer |
| Schema authority | Pydantic models are source of truth; `inputSchema` generated via `model_json_schema()` | Eliminates drift between validation and tool surface |
| Model placement | Co-located at top of each tool module | Schema and handler in one file; no new architectural layer |
| Scope | All 6 tool modules in one PR | Complete coverage; 19 models; Pydantic already a transitive dep |

## Architecture

### New file: `cognigy_mcp/validation.py`

Shared utilities used by all tool modules except `explain`:

```python
def _ok(data: dict) -> list[TextContent]: ...

def validate(
    model_cls: type[BaseModel], args: dict
) -> tuple[BaseModel | None, list[TextContent] | None]:
    """
    Returns (model, None) on success.
    Returns (None, error_response) on ValidationError.
    """
```

Error response shape:
```json
{
  "error": "Invalid tool arguments",
  "details": [
    {"field": "resource_type", "message": "Field required"},
    {"field": "limit", "message": "Input should be a valid integer"}
  ]
}
```

`details` is a list — all validation failures surface at once.

### Per-module changes (5 modules: flow_ops, state_tools, file_push, testing, voice_ops)

For each module:
1. Add Pydantic `BaseModel` subclasses at the top of the file (one per tool)
2. Replace hand-written `inputSchema` dicts with `Model.model_json_schema()`, stripping the top-level `title` key
3. Remove local `_ok` definition; import from `cognigy_mcp.validation`
4. Each handler: first line becomes `m, err = validate(ModelClass, args); if err: return err`; subsequent code uses `m.field` instead of `args["field"]` / `args.get("field")`

### explain.py

`explain._ok` takes `str`, not `dict` — kept as a module-local helper (different signature). `ExplainArgs` has one optional field (`topic: str = ""`); validation added for consistency.

## Model inventory

### `flow_ops.py` (7 models)

| Model | Required fields | Optional fields |
|---|---|---|
| `CognigyGetArgs` | `resource_type`, `resource_id` | `flow_id`, `fields: list[str]` |
| `CognigyListArgs` | `resource_type` | `project_id`, `agent_id`, `limit: int = 100`, `full_objects: bool = False`, `fields: list[str]` |
| `CognigyCreateArgs` | `resource_type`, `body: dict` | `flow_id`, `return_full_object: bool = False` |
| `CognigyUpdateArgs` | `resource_type`, `resource_id`, `body: dict` | `merge_config: bool = False`, `flow_id`, `return_full_object: bool = False` |
| `CognigyDeleteArgs` | `resource_type`, `resource_id` | `flow_id` |
| `CognigyInvokeArgs` | `resource_type`, `resource_id`, `operation` | `body: dict = {}`, `flow_id` |
| `GetFlowChartArgs` | `flow_id` | `format: Literal["hierarchy", "raw", "both"] = "hierarchy"` |

### `state_tools.py` (4 models)

| Model | Required fields | Optional fields |
|---|---|---|
| `SyncRemoteStateArgs` | — | `project_id` |
| `GetBuildStateArgs` | — | `resource_type` |
| `ResolveResourceArgs` | `name`, `resource_type` | — |
| `AssignOrgLlmArgs` | `project_id`, `llm_id` | — |

### `file_push.py` (5 models)

| Model | Required fields | Optional fields |
|---|---|---|
| `PushCodeNodeArgs` | `script_file`, `flow_id` | `node_id`, `mode`, `target`, `label` |
| `PushHtmlNodeArgs` | `html_file`, `node_id`, `flow_id` | — |
| `PushAgentToolArgs` | `tool_file`, `flow_id` | `node_id`, `job_node_id` |
| `PushAgentAvatarArgs` | `image_file`, `agent_id` | — |
| `ExportPackageArgs` | `project_id`, `output_path` | — |

### `testing.py` (1 model)

| Model | Required fields | Optional fields |
|---|---|---|
| `TalkToAgentArgs` | `session_id`, `user_id` | `message: str = ""`, `endpoint_token`, `flow_id`, `data: dict`, `minimal: bool = False` |

### `voice_ops.py` (1 model)

| Model | Required fields | Optional fields |
|---|---|---|
| `ProvisionWebrtcEndpointArgs` | `project_id`, `flow_id`, `flow_reference_id`, `endpoint_name`, `connection_name` | `region: str = "australiaeast"` |

### `explain.py` (1 model)

| Model | Required fields | Optional fields |
|---|---|---|
| `ExplainArgs` | — | `topic: str = ""` |

## Schema generation notes

- `model_json_schema()` top-level `title` stripped before passing to `Tool(inputSchema=...)`
- Optional `str | None = None` fields emit `anyOf: [{type: string}, {type: null}]` — a minor schema change from the current bare `{type: string}`, but semantically correct and handled by all MCP clients
- `Literal[...]` fields emit `{enum: [...]}` — matches current hand-written schema for `get_flow_chart`
- `dict` fields emit `{type: object}` — no key constraints, consistent with current behaviour

## Testing

### New: `tests/test_validation.py`

Unit tests for `validate()` in isolation:
- Missing required field → error with field name in `details`
- Wrong type (e.g. `limit: "not-an-int"`) → error with message in `details`
- Multiple invalid fields → all appear in `details`
- Valid input → returns model, no error

### Additive: per-tool test files

2–3 new cases per module, alongside existing tests:
- Missing required field returns validation error (not KeyError)
- Wrong type returns validation error
- Existing happy-path tests unchanged

## Files changed

| File | Change |
|---|---|
| `cognigy_mcp/validation.py` | New |
| `cognigy_mcp/tools/flow_ops.py` | Models + schema gen + handler updates + remove local `_ok` |
| `cognigy_mcp/tools/state_tools.py` | Models + schema gen + handler updates + remove local `_ok` |
| `cognigy_mcp/tools/file_push.py` | Models + schema gen + handler updates + remove local `_ok` |
| `cognigy_mcp/tools/testing.py` | Models + schema gen + handler updates + remove local `_ok` |
| `cognigy_mcp/tools/voice_ops.py` | Models + schema gen + handler updates + remove local `_ok` |
| `cognigy_mcp/tools/explain.py` | Model + schema gen + handler update (keeps local `_ok`) |
| `tests/test_validation.py` | New |
| `tests/tools/test_flow_ops.py` | Additive validation cases |
| `tests/tools/test_state_tools.py` | Additive validation cases |
| `tests/tools/test_file_push.py` | Additive validation cases |
| `tests/tools/test_testing.py` | Additive validation cases |
| `tests/tools/test_voice_ops.py` | Additive validation cases |
