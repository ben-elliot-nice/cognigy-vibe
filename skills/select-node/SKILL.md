---
name: select-node
description: Resolve a Cognigy flow node by ID, label, or type — returns nodeId plus relational context (prev/next nodes in the graph)
---

# Cognigy Select Node

Resolves a node reference within a Cognigy flow into a confirmed nodeId plus relational context — what comes immediately before and after it in the flow graph.

## When to Use

Use this skill whenever you need to identify a specific node in a flow, whether to read it, update it, or insert before/after it. Any composite skill that targets a flow node should call this skill rather than re-implementing node discovery.

## Finding the CLI

When Claude Code loads this skill, it injects `Base directory for this skill: <path>` into context. That path ends in `skills/select-node`. Go two directories up to get the plugin root. The CLI entry point is `<plugin-root>/cli/src/index.ts`.

## Inputs

- `flowId` — Required. From the user, `.env`, or a calling skill.
- Node hint — Optional. One of: a nodeId (24-char hex string), a label string, or a node type (`code`, `say`, `if`, `question`, `start`, `end`, etc.).

## Steps

### 1. Resolve the node

**If a nodeId was provided (24-char hex, no spaces):**

Invoke the `cognigy:get` skill: get node `<nodeId>` with `--flowId <flowId>`.
- Success → node confirmed. Proceed to step 2.
- Error `requires --flowId` → ask user for flowId, then retry.
- Other error → tell user the node was not found, stop.

**If a label, type, or nothing was provided:**

Invoke the `cognigy:get` skill: get chart with `--flowId <flowId>`.

From the response `nodes[]` array:
- Filter by label (case-insensitive substring match) or type if a hint was given.
- If exactly one match → proceed to step 2 with that nodeId.
- If multiple matches → present the list with label, type, and `_id` for each. Ask: *"Which node did you mean?"* Wait for selection.
- If no matches → tell user, show all available nodes (label + type), ask them to choose.

### 2. Extract relational context

Get the chart if not already fetched by invoking the `cognigy:get` skill: get chart with `--flowId <flowId>`.

From the `relations[]` array, for the resolved `nodeId`:
- **successor (`next`)**: find the relation where `relation.node === nodeId` → `relation.next`
- **predecessor (`prev`)**: find any relation where `relation.next === nodeId` → `relation.node`
- **children**: `relation.children[]` on the node's own relation entry (non-empty for If/Then/Else nodes)

Resolve labels and types for prev/next/children by looking them up in the `nodes[]` array.

### 3. Confirm with user (only when ambiguous)

Only ask for confirmation when the node was **inferred** (matched by label/type search, or chosen from a list). If the user stated the node explicitly by nodeId or unambiguous label, skip confirmation and return immediately.

When confirmation is needed, present:

> "Found: **[label]** (`[type]`)
> — preceded by **[prev label]** (`[prev type]`)
> — followed by **[next label]** (`[next type]`)
>
> Is this the right node?"

The resolved context:
```
nodeId:   <id>
label:    <label>
type:     <type>
prev:     { nodeId, label, type } | null
next:     { nodeId, label, type } | null
children: [{ nodeId, label, type }]
```

If declined → return to step 1 and ask the user to clarify.

## Notes

- Only confirm node identity when it was inferred or ambiguous — not when the user stated it explicitly.
- If `flowId` is not provided and not in `.env`, ask the user before running anything.
- The chart endpoint returns all nodes with types and labels. Prefer it over `list nodes` which returns only metadata.
- For nodes with no predecessor (e.g. Start), `prev` is `null`. For nodes with no successor (e.g. End, terminal code nodes), `next` is `null`.
- Exit codes (Exit 2 `.env` confirmation, `No .env file found`, API errors) are handled by the `cognigy:get` skill when it is invoked. You do not need to handle them separately in this skill.
