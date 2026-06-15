---
name: explain
description: Retrieve implementation guidance for Cognigy topics before brute-forcing or web-searching
---

# Explain

## When to Use

Call `explain_dev` before brute-forcing or web-searching for Cognigy implementation guidance. It returns authoritative reference for the topics below — faster and more accurate than inference.

## Available Topics

Topics and what they cover:

  code-node-patterns         api.* functions, as const bug, httpRequest .result, no fetch/import

xapp:
  xapp                       xApp architecture overview, variant selection, and channel differences
  xapp-delivery              session init, postMessage bridge, SDK.submit, dual xApp moments
  xapp-event-handling        non-blocking xApp pattern: flow structure, ephemeral data capture, SDK.submit vs webhook inject variants

## How to Use

- **Orientation:** `explain_dev()` with no args — returns topic list with one-line descriptions
- **Full reference:** `explain_dev("topic-name")` — returns complete guidance for that topic
- **Fallback:** if the topic is not listed above, use `explain("topic-name")` instead — the legacy tool covers the full 24-topic set until migration is complete

## Notes

This tool covers migrated topics only. The full topic set lives in `explain` until migration is complete (issue #45).
