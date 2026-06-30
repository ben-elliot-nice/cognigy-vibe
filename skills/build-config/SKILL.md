---
name: build-config
description: Canonical reference for `default-demo-config.json` ($schemaVersion: 2). Covers the full field schema, cascade discovery order, which build steps consume which fields, `get_build_state` config output, and common failure modes. Read this skill before writing, validating, or consuming the build config. When invoked by a user, outputs the reference content and points to `get_build_state` (check what's loaded) and `cognigy:init-cognigy-vibe` (write or edit). Triggers — "build config schema", "what's in the build config", "how does config discovery work", "default-demo-config schema", "what fields does the build config have".
---

# cognigy:build-config — build config reference

## When invoked

Output the schema reference below. Do not call any MCP tools. Do not redirect to or orchestrate any other skill.

Tell the user:
- To check what config is currently loaded: call `get_build_state` (no filter) and inspect `config_loaded`, `config_source`, and `config_summary`.
- To write or edit their config: run `cognigy:init-cognigy-vibe`.

## Schema reference

### 1. Full field table

Every field in `default-demo-config.json` at `$schemaVersion: 2`.

| Field path | Type | Req? | Description | Example |
|---|---|---|---|---|
| `$schemaVersion` | integer | required | Schema version — must be `2` | `2` |
| `owner.name` | string | required | Build owner display name | `"Jane Smith"` |
| `owner.initials` | string | required | 2–3 char tag used in build artefact naming | `"JS"` |
| `connection.baseUrl` | string | required | Cognigy API base URL for this tenant | `"https://cognigy-api-au1.nicecxone.com"` |
| `connection.endpointBase` | string | required | Cognigy endpoint host for this tenant | `"https://cognigy-endpoint-au1.nicecxone.com"` |
| `connection.region` | string | required | Short region tag; used in summary display and as-built docs | `"au1"` |
| `llm.default` | string | required | Label of the LLM to select by default at §0.0 | `"Azure GPT-4o"` |
| `llm.options` | array | required | List of available generation LLMs for this tenant | see rows below |
| `llm.options[].label` | string | required | Human-readable LLM name | `"Azure GPT-4o"` |
| `llm.options[].referenceId` | string (uuid) | required | Cognigy LLM `referenceId` — must exist in the target project | `"a793f9ea-befd-4fdf-8be8-b1c8a8385a91"` |
| `llm.embedding` | object | optional | Embedding LLM for Knowledge AI (§0.5 / §1.8) | `{ "label": "...", "referenceId": "" }` |
| `llm.embedding.label` | string | optional | Human-readable embedding model name | `"text-embedding-3-large"` |
| `llm.embedding.referenceId` | string (uuid) | optional | Cognigy referenceId for the embedding model | `"..."` |
| `llm.temperatureVoice` | number | optional | Temperature for voice/transactional builds | `0.2` |
| `llm.temperatureChat` | number | optional | Temperature for chat-primary builds | `0.5` |
| `llm.maxTokens` | integer | optional | Max tokens for generation | `400` |
| `llm.toolChoice` | string | optional | Tool selection mode | `"auto"` |
| `locale` | string | required | BCP-47 locale for the agent and endpoint | `"en-AU"` |
| `tts.vendor` | string | required | TTS provider name | `"ElevenLabs"` |
| `tts.model` | string | required | TTS model identifier | `"eleven_turbo_v2_5"` |
| `tts.language` | string | required | TTS language code | `"en"` |
| `tts.voiceType` | string | required | TTS voice type | `"Custom"` |
| `tts.voiceId` | string | required | Provider-specific voice ID | `"kqVqVtE8vZVRm6uoad9t"` |
| `tts.label` | string | required | Cognigy synthesizer connection label | `"nexora_elevenlabs"` |
| `stt.vendor` | string | required | STT provider name | `"Microsoft"` |
| `stt.language` | string | required | STT language/locale code | `"en-AU"` |
| `stt.label` | string | required | Cognigy recognizer connection label | `"nexora-azure-speech-services-australiaeast"` |
| `stt.hints` | array | optional | Static STT hint phrases | `[]` |
| `stt.dynamicHints.enabled` | boolean | optional | Enable dynamic STT hints | `true` |
| `channel.type` | string | required | Channel type identifier | `"voice-webrtc"` |
| `channel.voiceGateway.endpointName` | string | required | VoiceGateway endpoint name to bind | `"Click-to-Call"` |
| `channel.voiceGateway.mode` | string | required | VoiceGateway transport mode | `"webrtc"` |
| `channel.voiceGateway.bindFlow` | boolean | required | Whether to bind this endpoint to the flow | `true` |
| `voicePreview.speechProvider` | string | required | In-UI preview speech provider name | `"Microsoft Azure Speech Services"` |
| `voicePreview.connectionName` | string | required | Cognigy connection label for preview | `"Test"` |
| `voicePreview.region` | string | required | Azure region for preview | `"AU"` |
| `voicePreview.apiKeyRef` | string | required | API key reference for preview connection | `"test"` |
| `voiceBehaviour.bargeIn` | boolean | optional | Enable barge-in (caller interrupts agent) | `false` |
| `voiceBehaviour.vad` | boolean | optional | Enable voice activity detection | `false` |

### 2. Cascade discovery order

Handled by `server.py` at startup. **First file found wins — no field merging between layers.**

1. `<cwd>/default-demo-config.json`
2. Walk up from `cwd` toward `$HOME`, checking each directory — first match wins
3. `~/.config/cognigy-vibe/config.json`
4. Nothing found → `config_loaded: false`; server runs normally; skills fall back to hardcoded defaults

**Boundaries and semantics:**
- Walk stops at `$HOME`. Never traverses above it.
- Loaded **once** at server startup. A config change requires a session restart — there is no hot-reload.
- A project-level file must be **complete** if it exists. There is no field-level merging. Partial files are not supported.
- The path of the winning file is reported as `config_source` in `get_build_state`.

**Writing:** `cognigy:init-cognigy-vibe` always writes `.env` to `cwd`. On first-time setup it writes the non-secret config to `~/.config/cognigy-vibe/config.json` (global). For a project-only override, write a complete `default-demo-config.json` to the project directory — it will win over the global config on next session start.

### 3. Field → build step map

| Field | Consumed by | How |
|---|---|---|
| `llm.default` | §0.0 preflight | Shown in config summary; user may switch to another from `llm.options` |
| `llm.options` | §1.1 Step 3 | `update_ai_agent.jobConfig.llmProviderReferenceId` — default selected, alternates offered |
| `llm.embedding` | §0.5 / §1.8 | Knowledge AI connector — gated, only wired if knowledge is enabled |
| `llm.temperatureVoice` | §1.1 Step 3 | `update_ai_agent.jobConfig.temperature` — used when channel is voice/transactional |
| `llm.temperatureChat` | §1.1 Step 3 | `update_ai_agent.jobConfig.temperature` — used when channel is primarily chat |
| `llm.maxTokens` | §1.1 Step 3 | `update_ai_agent.jobConfig.maxTokens` |
| `llm.toolChoice` | §1.2 | Node patch for `toolChoice` (not reachable via `update_ai_agent`) |
| `locale` | §1.5(c) | Set Session Config `locale`; also endpoint locale binding |
| `tts.*` | §1.5(c) | Set Session Config synthesizer fields (vendor, model, language, voiceType, voiceId, connection label) |
| `stt.*` | §1.5(c) | Set Session Config recognizer fields (vendor, language, connection label, hints, dynamicHints) |
| `channel.voiceGateway.endpointName` | §1.5(d) | Endpoint binding — matches or creates the named VoiceGateway endpoint |
| `channel.voiceGateway.mode` | §1.5(d) | VoiceGateway transport mode for the endpoint (e.g. `webrtc`) |
| `channel.voiceGateway.bindFlow` | §1.5(d) | Whether to bind this endpoint to the demo flow |
| `connection.baseUrl` | MCP auth + as-built doc | API host for all Cognigy API calls in this session |
| `connection.endpointBase` | As-built doc / baseline | Endpoint host recorded in `[customer]-baseline.md` |
| `connection.region` | §0.0 summary display | Shown in config confirmation table |
| `voicePreview.*` | §1.5(c) | In-UI voice preview connection (Azure Speech Services) |
| `voiceBehaviour.bargeIn` | §1.5(c) | Set Session Config `bargeIn` |
| `voiceBehaviour.vad` | §1.5(c) | Set Session Config `enableVoiceActivityDetection` |
| `owner.initials` | §1.1 | Build artefact naming prefix |

### 4. `get_build_state` config fields

Three fields are injected into every `get_build_state` response:

| Field | Type | Present when | Meaning |
|---|---|---|---|
| `config_loaded` | boolean | always | `true` if a config file was found and parsed at startup |
| `config_source` | string | `config_loaded: true` | Absolute path of the winning file |
| `config_summary` | object | `config_loaded: true` | `{ region, llm_default, tts_label, stt_label, locale }` |

These fields are always included even when a `resource_type` filter is passed.

When `config_loaded: false`, `config_source` and `config_summary` are absent. Run `cognigy:init-cognigy-vibe` to create a config.

### 5. Common failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| `config_loaded: false` after wizard ran | Config written to wrong location, or session not restarted after write | Check `~/.config/cognigy-vibe/config.json` exists and parses; restart the Claude Code session |
| Agent generates empty output despite config loaded | Stale `llm.options[].referenceId` — LLM exists in config but not in this project | Run §1.1 Step 2 LLM gate; import LLM via `manage_packages` or `setup_llm` |
| Set Session Config uses wrong voice | `tts.label` or `stt.label` doesn't match a real connection in this project | Re-run `cognigy:init-cognigy-vibe` and pick correct connection labels from live list |
| Project-level config ignored | Project `default-demo-config.json` is a partial file | File must be complete — no field merging. Write a full file or delete it to fall through to global. |
| Config change not reflected mid-session | Config loaded once at startup; hot-reload not supported | Restart the Claude Code session after editing the config file |
| Wrong region values (TTS/STT/endpoint) | Global config has AU1 values but build targets a different region | Write a project-level `default-demo-config.json` with the correct region values, restart session |
