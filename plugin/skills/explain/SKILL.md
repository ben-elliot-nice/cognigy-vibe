---
name: explain
description: Retrieve implementation guidance for Cognigy topics before brute-forcing or web-searching
---

# Explain

## When to Use

Call `explain` before brute-forcing or web-searching for Cognigy implementation guidance. It returns authoritative reference for the topics below — faster and more accurate than inference.

## Available Topics

Topics and what they cover:

```
  aiagent                    AI Agent Job node configuration, persona authoring, tool design, turn structure, and multi-agent architecture patterns
  code                       Code node runtime objects, CognigyScript interpolation, async function execution, output formatting, and profile editing
  nodes                      Flow chart structure, node type strings, node wiring/positioning, and the full node-type reference
  platform                   Project-level platform resources — connections, endpoints, extensions, LLMs, locales, playbooks, knowledge store, and resource_type discovery recipes
  voice                      Voice Gateway session configuration and silence-timeout handling
  xapp                       xApp architecture overview, variant selection, and channel differences
```

## How to Use

- **Orientation:** `explain()` with no args — returns the list of topic groups with one-line descriptions
- **Group primer:** `explain("group-name")` — returns that group's primer plus an index of the topics inside it
- **Full reference:** `explain("topic-name")` — returns complete guidance for that specific topic
