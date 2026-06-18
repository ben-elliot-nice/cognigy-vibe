# Design: Migrate Agent Docs into Explain Resource Framework

**Issue:** #58
**Branch:** feat/issue-58-explain-docs-migration
**Date:** 2026-06-18

---

## Background

Two docs files serve as runtime reference for the agent design skills but sit outside the explain resource framework:

- `docs/agent-prompting-guide.md` — authoring guidance for AI Agent `description` and `instructions` fields
- `docs/cognigy-agent-patterns.md` — structural patterns for multi-agent Cognigy implementations

These are consumed by direct file reads in four skills. They were not included in the PR #49 migration that moved all other reference content into `skills/explain/resources/`.

---

## Approach

Direct rewrite into explain resource format. Source docs are guide-style (example/anti-example scaffolding, "you should consider" prose). The explain format is terse reference — decision tables, short code blocks, bulleted rules. Rewriting at migration time produces clean, consistent topics rather than inheriting guide prose that would need cleanup later.

---

## Topic Splits

### From `docs/agent-prompting-guide.md` → 2 topics

| Topic | Sections |
|---|---|
| `agent-persona-authoring` | Field purposes, What NOT to include, Writing the Description, Writing the Instructions, Speaking Style Fields, Generation Principle |
| `agent-behavioral-rules` | Tool Execution — Silent by Default, Outcome-Based Framing, Tool Descriptions as Compliance Contracts |

### From `docs/cognigy-agent-patterns.md` → 3 topics

| Topic | Sections |
|---|---|
| `multi-agent-architecture` | Concierge + Specialists pattern, Specialist Job Patterns catalogue (info retrieval, transaction, booking, support), Return to Concierge, Stub Agent, Context Schema Examples |
| `agent-tool-patterns` | Tool Granularity (granular/consolidated/action-parameterized), `context.toolResponse` channel pattern |
| `agent-handover` | Escalation to Human pattern, Handover Context Pattern (two-consumer model, structured artefact) |

---

## Resource Files

5 new files under `skills/explain/resources/aiagent/`, each with frontmatter:

```
---
topic: <topic-name>
description: <one-line description>
group: aiagent
---
```

Written as terse reference. No guide prose, no example/anti-example scaffolding.

---

## Consuming Skills

4 skills currently read the docs files directly. After migration, replace all direct file read instructions with `explain()` calls:

| Skill | Replaces | With |
|---|---|---|
| `design-agent-persona` | `docs/agent-prompting-guide.md` | `explain("agent-persona-authoring")`, `explain("agent-behavioral-rules")` |
| `design-agent-jobs` | `docs/agent-prompting-guide.md`, `docs/cognigy-agent-patterns.md` | `explain("agent-behavioral-rules")`, `explain("agent-tool-patterns")`, `explain("multi-agent-architecture")`, `explain("agent-handover")` |
| `design-agent-contracts` | `docs/cognigy-agent-patterns.md` | `explain("agent-tool-patterns")`, `explain("agent-handover")` |
| `design-agent-interfaces` | `docs/cognigy-agent-patterns.md` | `explain("multi-agent-architecture")`, `explain("agent-handover")` |

All inline section references (e.g. "see Handover Context Pattern") updated to `explain("agent-handover")`.

---

## Docs File Removal

Both source docs files are deleted once the resource files are written and verified. No deprecation notices — the files are removed outright.

---

## Build

After writing resource files:

1. `uv run scripts/build_explain_topics.py` — regenerates `_explain_topics_generated.py` and `SKILL.md`
2. Verify all 5 new topics appear in the topic index
3. Patch increment `cognigy-mcp/pyproject.toml` and `.claude-plugin/plugin.json`

---

## Out of Scope

- Issue #59 (code-node-patterns: missing Runtime Objects + wrong directory placement) — tracked separately
