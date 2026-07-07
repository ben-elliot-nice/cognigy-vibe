---
name: explain
description: Retrieve implementation guidance for Cognigy topics before brute-forcing or web-searching
---

# Explain

## When to Use

Call `explain_dev` before brute-forcing or web-searching for Cognigy implementation guidance. It returns authoritative reference for the topics below — faster and more accurate than inference.

## Available Topics

Topics and what they cover:


aiagent:
  agent-avatar-image         Custom avatar image on AI Agent — data URI pattern, imageOptimizedFormat, file spec, push_agent_avatar usage
  agent-behavioral-rules     Silent tool execution, outcome-based framing, compliance rules in tool descriptions
  agent-handover             Escalation to human pattern and handover context artefact design (two-consumer model)
  agent-persona-authoring    AI Agent description and instructions field authoring — structure, constraints, speaking style
  agent-tool-branch          aiAgentJobTool + code + toolAnswer assembly, tool args access
  agent-tool-json            .tool.json convention — field reference, toolType selection, toolId uniqueness rule
  agent-tool-patterns        Tool granularity options (granular/consolidated/action-parameterized) and context.toolResponse channel
  multi-agent-architecture   Concierge + Specialists pattern, specialist job types, routing, context schema, stub agent
  tool-conditions            CognigyScript condition field, hiding tools from LLM
  tool-selection             when to use push_agent_tool vs push_code_node vs cognigy_create vs cognigy_update
  turn-structure             Once/OnFirstTime/Afterwards, input.execution, context reset prevention, child branch API patterns
  two-pass-confirm           inter-turn flag management, STOP gate wording

code:
  code-node-patterns         api.* functions, execution model, runtime objects (input/context/profile/analyticsdata), utility functions (getVar/setVar/mergeVar), as const bug, httpRequest response shape and storage config
  cognigyScript              interpolation contexts, what works where
  function-execution         async pattern, inject-back via sessions API
  output-formats             api.say() channel output shapes — quick replies, buttons, gallery, image, audio, adaptive card
  profile-editing            Writing to the Cognigy contact profile — why direct mutation doesn't persist, api.updateProfile behaviour, and getProfileVar/setProfileVar/mergeProfileVar utility functions
  session-injection          context/state inject for in-session testing

nodes:
  flow-chart-reading         reading chart output, node type strings, extension field
  node-config-update         full-replace semantics, merge_config pattern, silent field deletion
  node-positioning           append vs appendChild modes, child branch population for Once, IF, ifThenElse nodes, lookup default branch
  node-types                 quick reference for all node type strings
  node-wiring                chart structure, relations array, sequential vs child chains

platform:
  endpoint-config            referenceId vs _id gotcha, urlToken caching, VoiceGateway webRTC endpoint
  extension-map              complete type → extension lookup table
  knowledge-store            chunking, connector run, source management
  llm-resources              org-level vs project-level LLMs, assign_org_llm tool, discovery pattern, referenceId resolution, manage_packages fallback
  mcp-comparison             when to use cognigy-vibe vs NiCE official MCP
  outbound-trigger           6-step CXone trigger, Accept-Encoding: identity requirement
  project-snapshots          create project snapshots for versioning (flow-level versioning does not exist in the API)
  say-node                   say node config schema: correct text field, required _cognigy/_data fields, generativeAI_customInputs
  session-workspace          session workspace directory model — cwd vs Demo Builds/, .env scope, sync_remote_state project binding

voice:
  voice-gateway              VG endpoint routing, Set Session Config, SIP headers, DTMF
  voice-silence-timeout      Voice Gateway silence detection — three modes, noUserInput intent wiring, reprompt-then-escalate counter

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
