---
name: write-code-node
description: Write, overwrite, or synthesise code for a Cognigy Code Node — handles create, overwrite, and read-synthesize-write modes
---

# Cognigy Write Code Node

Write code for a Cognigy Code Node. Supports three modes: creating a new code node at a specified position, overwriting existing code, or reading existing code and synthesising changes.

## When to Use

Use this skill when the user wants to:
- Write code for a new code node in a flow
- Replace the code in an existing code node
- Update or improve existing code node code based on a description

## Finding the CLI and Reference Docs

When Claude Code loads this skill, it injects `Base directory for this skill: <path>` into context. That path ends in `skills/write-code-node`. Go two directories up to get the plugin root.

**Before writing any code**, read these reference files:
- `<plugin-root>/docs/cognigy-api-reference.md` — runtime objects (`input`, `context`, `profile`, `analyticsdata`), `api.*` functions, available libraries
- `<plugin-root>/docs/cognigy-output-formats.md` — channel output structures and code examples

The CLI entry point is `<plugin-root>/cli/src/index.ts`.

## Mode Detection

Determine mode from the user's request before starting:

| Mode | Signal |
|---|---|
| **Create** | User wants a new code node ("add a code node", "create a code node that...") |
| **Overwrite** | User targets an existing node AND provides the new code directly |
| **Read-synthesize-write** | User targets an existing node AND describes what to change without providing the full code |

---

## Create Mode

1. If not already provided, ask: what should the code do, what label should the node have, and after which existing node should it be inserted?

2. Invoke the `cognigy:select-node` skill to resolve the insertion reference node and get its relational context (`nodeId` of the node to insert after).

3. Read `<plugin-root>/docs/cognigy-api-reference.md` and `<plugin-root>/docs/cognigy-output-formats.md`.

4. Write the code.

5. **Code review gate — non-negotiable:** Present the code to the user before writing:
   > "Here's the code I'll write to the new node — please review before I create it:"
   > ````js
   > [code here]
   > ````
   > "OK to proceed?"

   Do NOT call the CLI until the user confirms.

6. Create the node by invoking the `cognigy:create` skill: create node with `--flowId <flowId>`, `--type code`, `--label "<label>"`, `--target <refNodeId>`, and `--mode append`.

   `--target` is the `nodeId` from `select-node`. `--mode append` inserts the new node after target and automatically wires the graph relations.

7. From the response, capture `_id` (the new nodeId). Confirm by invoking the `cognigy:get` skill: get node `<newNodeId>` with `--flowId <flowId>`, then show the returned `config.code`.

---

## Overwrite Mode

1. Invoke `cognigy:select-node` to confirm the target node (user may provide nodeId or label).

2. Read `<plugin-root>/docs/cognigy-api-reference.md` and `<plugin-root>/docs/cognigy-output-formats.md`.

3. **Code review gate — non-negotiable:** Present the code before writing:
   > "Here's the code I'll write — please review:"
   > ````js
   > [code here]
   > ````
   > "OK to proceed?"

   Do NOT call the CLI until the user confirms.

4. Write the code by invoking the `cognigy:update` skill: update node `<nodeId>` with `--flowId <flowId>` and `--config '{"code":"<escaped code>"}'`.

   Escape newlines as `\n` and double quotes as `\"` within the JSON string value.

5. Confirm by invoking the `cognigy:get` skill: get node `<nodeId>` with `--flowId <flowId>`, then show the returned `config.code`.

---

## Read-Synthesize-Write Mode

1. Invoke `cognigy:select-node` to confirm the target node.

2. Read the existing code by invoking the `cognigy:get` skill: get node `<nodeId>` with `--flowId <flowId>`. Extract `config.code` from the response and show it to the user.

3. Read `<plugin-root>/docs/cognigy-api-reference.md` and `<plugin-root>/docs/cognigy-output-formats.md`.

4. Synthesise the new code incorporating the user's requested changes.

5. **Code review gate — non-negotiable:** Present the updated code before writing:
   > "Here's the updated code — please review before I save it:"
   > ````js
   > [new code here]
   > ````
   > "OK to proceed?"

   Do NOT call the CLI until the user confirms.

6. Write the updated code by invoking the `cognigy:update` skill: update node `<nodeId>` with `--flowId <flowId>` and `--config '{"code":"<escaped code>"}'`.

7. Confirm by invoking the `cognigy:get` skill: get node `<nodeId>` with `--flowId <flowId>`, then show the returned `config.code`.

---

## Notes

- **The code review gate is non-negotiable.** Never write to the API without user confirmation of the code content.
- `update node` returns nothing (204 No Content) — always confirm with a follow-up `get node`.
- `flowId` may come from the user, from `COGNIGY_FLOW_ID` in `.env`, or from a prior step.
- When escaping code for the `--config` JSON value: replace `\` with `\\`, `"` with `\"`, newlines with `\n`, tabs with `\t`.
- Do not use `async/await`, `import`, or `require` in generated code — code nodes run synchronously in a sandboxed scope.
