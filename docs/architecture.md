# Cognigy Claude Plugin — Architecture

## Overview

This plugin gives Claude Code structured, discoverable access to the Cognigy API. It is built in three layers: a TypeScript CLI, atomic skills, and composite skills. Each layer has a single responsibility and depends only on the layer below it.

```
Composite skills       write-code-node, select-node, ...
      ↓ call
Atomic skills          get, list, create, update, delete, invoke
      ↓ invoke
TypeScript CLI         cli/src/index.ts
      ↓ calls
Cognigy REST API
```

---

## Layer 1: TypeScript CLI

**Location:** `cli/src/`

The CLI is the only thing that talks to the Cognigy API. It handles authentication, `.env` discovery, request routing, and JSON output. Every resource (flows, nodes, projects, etc.) is a module in `cli/src/resources/` that exports a `ResourceHandlers` object.

Invoked as:
```bash
npx tsx cli/src/index.ts <verb> <resource> [id] [--flag value ...]
```

Exit codes:
- `0` — success, JSON on stdout
- `1` — error, `{ "error": "..." }` on stderr
- `2` — `.env` found via git root walk, requires user confirmation before proceeding

Skills never construct API calls themselves. All Cognigy API access goes through this CLI.

---

## Layer 2: Atomic Skills

**Location:** `skills/get/`, `skills/list/`, `skills/create/`, `skills/update/`, `skills/delete/`, `skills/invoke/`

One skill per CLI verb. Each skill knows how to:
- Derive the plugin root from the injected `Base directory for this skill:` path
- Run the CLI with the right arguments
- Handle all three exit codes (including the Exit 2 `.env` confirmation flow)
- Surface errors clearly

Atomic skills are **resource-agnostic**. `cognigy:get` works for flows, nodes, projects, charts — anything the CLI supports. Resource-specific knowledge lives in the CLI layer, not in the skill.

---

## Layer 3: Composite Skills

**Location:** `skills/select-node/`, `skills/write-code-node/`, ...

Composite skills orchestrate sequences of atomic skill calls to accomplish a higher-level goal. They contain workflow logic, user interaction, and domain knowledge — but **no direct CLI invocations**.

### The key rule: composite skills call atomic skills, not the CLI

**Wrong:**
```bash
# Hardcoded CLI call in a composite skill
npx tsx ~/.claude/plugins/.../cli/src/index.ts get node <nodeId> --flowId <flowId>
```

**Right:**
```
Invoke the `cognigy:get` skill: get node <nodeId> with --flowId <flowId>
```

Why this matters:
- **Exit code handling is already solved.** Atomic skills handle Exit 2 `.env` confirmation, `No .env file found`, and error display. Duplicating this in every composite skill creates inconsistency and maintenance burden.
- **Path derivation is already solved.** The atomic skills know how to find the CLI from the injected `Base directory` path. Composite skills don't need to re-derive it.
- **Composability.** If CLI invocation syntax changes, only the atomic skills need updating — composite skills remain unchanged.

---

## Reference Docs

**Location:** `docs/`

Composite skills that generate content (e.g. `write-code-node`) need domain knowledge that would be expensive to re-fetch at runtime. This knowledge lives in reference docs that skills read once before starting work:

| File | Purpose |
|---|---|
| `docs/cognigy-api-reference.md` | Runtime objects (`input`, `context`, `profile`), all `api.*` functions, available libraries |
| `docs/cognigy-output-formats.md` | Channel output structures and code examples |
| `docs/cognigy-code-conventions.md` | Code node structural conventions (`main`, `getVar`, `setVar`, `mergeVar`, `allSettled`, `log`) |

Skills instruct Claude to read these files before writing any code:
> "Before writing any code, read `<plugin-root>/docs/cognigy-api-reference.md` ..."

The plugin root is always derived from the `Base directory for this skill:` path injected at skill load time — two directories up from the skill file.

---

## Adding a New Resource

New Cognigy API resources need only a CLI module. The atomic skills require no changes.

1. Run the type extraction script to generate the types file:
   ```bash
   cd cli && npx tsx scripts/extract-resource-types.ts <resource>
   # For sub-resources (e.g. nodes under flows):
   npx tsx scripts/extract-resource-types.ts <resource> --path /v2.0/parent/{parentId}/resources
   ```
2. Implement `cli/src/resources/<resource>.ts` — follow `flows.ts` as the reference pattern
3. Register it in `cli/src/index.ts`

The private skill `/private:cognigy-generate-resource` automates this process.

---

## Adding a New Composite Skill

1. Identify which atomic skills it will call (`cognigy:get`, `cognigy:create`, etc.)
2. Identify which reference docs it needs to read before generating content
3. Write `skills/<skill-name>/SKILL.md` — call atomic skills by name, never hardcode CLI paths
4. If the skill needs to resolve a flow node by label or type, call `cognigy:select-node` rather than reimplementing node discovery

---

## Sub-Resources

Some Cognigy resources live under a parent (e.g. nodes under flows, intents under flows). These declare a `requires` field in their handler:

```typescript
export const nodes: ResourceHandlers = {
  requires: ['flowId'],
  // ...
}
```

The CLI validates `requires` before dispatch. The parent ID comes from a `--flag` (e.g. `--flowId`) or from the matching env var (`COGNIGY_FLOW_ID`). Sub-resources do not use a positional ID for the parent — only the child resource ID is positional.
