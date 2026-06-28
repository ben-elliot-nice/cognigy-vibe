---
name: init-cognigy-vibe
description: First-time-user setup wizard for the Cognigy-Vibe plugin. Run once per workstation/workspace to capture every variable a demo build needs — Cognigy API URL + key, LLM reference IDs, TTS, STT, voice channel (VoiceGateway webRTC), and voice-preview settings — and write them as a reusable workspace default at the `Demo Builds` root. After this runs, `cognigy:build-orchestrator` builds for any customer with zero further manual setup. Triggers — "/init-cognigy-vibe", "set up cognigy vibe", "set up cognigy vibe MCP", "set up the cognigy plugin", "cognigy first-time setup", "configure my demo build defaults", "show/edit my Cognigy build config". Also auto-delegated by `build-orchestrator` §0.0 when no workspace config is found. Writes a non-secret `default-demo-config.json` and a secret `.env` at the `Demo Builds` workspace root; never commits secrets.
---

# cognigy:init-cognigy-vibe — first-time setup wizard

This is the **front door** for a new Cognigy-Vibe user. It captures, once, everything a build needs and stores it at the **workspace level** (the `Demo Builds` folder that holds every `<customer>-demo/` sub-build). From then on, `cognigy:build-orchestrator` reads these defaults and never re-asks for tenant, credentials, LLM, voice, or naming.

> **Run order.** Run this **before your first build**, or just start a build — `build-orchestrator` §0.0 auto-delegates here if no workspace config exists. Re-run any time to view or change your defaults.

> **⚠️ Assumptions (pre-design — see [#82](https://github.com/ben-elliot-nice/cognigy-claude-plugin/issues/82)).** This skill bakes in a specific workspace layout and discovery model that has **not** yet been through a full design pass. Known assumptions, each tracked in #82:
> - **Folder name.** The workspace root is assumed to be a folder literally named `Demo Builds` (or `demo-builds`). Users who organise demos under a different name aren't covered yet.
> - **Single workspace.** One workspace root is assumed. **Multi-tenant** setups (two peer roots, e.g. different Cognigy tenants) aren't handled — the walk-up finds the nearest one, with no way to choose.
> - **Walk-up boundary.** Ancestor search **stops at `$HOME`** (never walks past it to `/`). If no workspace root is found at or below `$HOME`, setup creates one rather than guessing.
> - **`demoBuildsRoot`.** Stored as the **absolute path** of the workspace root at write time (a relative `"."` is meaningless when the config is read from a child build folder).
> - **Creation location.** When no `Demo Builds` folder exists, it is created at the **current working directory** and the path is reported to the user — cwd-dependent, so launch from where you want it.
>
> These are acceptable as a v1 shipping default **because they're documented here and called out as pre-design in the PR**; the settled design lands via #82.

## The end-state this skill creates

```
Demo Builds/                         ← workspace root (open your Claude session here)
├── .env                             ← SECRETS: COGNIGY_BASE_URL, COGNIGY_API_KEY  (gitignored)
├── default-demo-config.json         ← non-secret build defaults (source of truth)
├── acme-demo/                       ← a build (created later by build-orchestrator)
└── liberty-financial-demo/          ← another build
```

- `cognigy-vibe` is registered **projectless at plugin level** (the plugin's own `.mcp.json`), so it auto-loads every session and reads `.env` from the folder the session launched in. Open your session in `Demo Builds/` and credentials resolve with **no restart and no per-project `.claude/mcp.json`** — this supersedes the legacy per-project `cognigy:init-mcp` restart dance for the common case.
- `default-demo-config.json` is the single source of truth for build values. It syncs with your workspace (e.g. OneDrive) — that's fine, it holds **no secrets**.

> **🔴 Secrets & cloud sync.** `COGNIGY_API_KEY` is the one true secret. It is written **only** to `.env`. If your `Demo Builds` folder is in a synced location (OneDrive/Dropbox/iCloud), `.env` syncs to that cloud — treat that as publishing the key. Offer the user the choice to (a) keep `.env` at the workspace root (simplest, works with the projectless MCP today), or (b) store it outside the synced tree and point `COGNIGY_PROJECT_ROOT` at it. Never write the API key into `default-demo-config.json` and never commit it.

## Config schema — `default-demo-config.json` (`$schemaVersion: 2`)

```json
{
  "$schemaVersion": 2,
  "owner": { "name": "<name>", "initials": "<2-3 char build-owner tag>" },
  "connection": {
    "baseUrl": "https://cognigy-api-<region>.nicecxone.com",
    "endpointBase": "https://cognigy-endpoint-<region>.nicecxone.com",
    "region": "<region, e.g. au1>"
  },
  "llm": {
    "default": "<label of the default generation LLM>",
    "options": [
      { "label": "<name>", "referenceId": "<uuid>" }
    ],
    "embedding": { "label": "<optional, for Knowledge AI>", "referenceId": "" },
    "temperatureVoice": 0.2,
    "temperatureChat": 0.5,
    "maxTokens": 400,
    "toolChoice": "auto"
  },
  "locale": "en-AU",
  "tts": {
    "vendor": "ElevenLabs",
    "model": "eleven_turbo_v2_5",
    "language": "en",
    "voiceType": "Custom",
    "voiceId": "<voice id>",
    "label": "<synthesizer connection label>"
  },
  "stt": {
    "vendor": "Microsoft",
    "language": "en-AU",
    "label": "<recognizer connection label>",
    "hints": [],
    "dynamicHints": { "enabled": true }
  },
  "channel": {
    "type": "voice-webrtc",
    "voiceGateway": { "endpointName": "Click-to-Call", "mode": "webrtc", "bindFlow": true }
  },
  "voicePreview": {
    "speechProvider": "Microsoft Azure Speech Services",
    "connectionName": "<preview speech-connection name in Cognigy, e.g. Test>",
    "region": "AU",
    "apiKeyRef": "<api key for that preview connection; a throwaway value like 'test' is fine for a demo speech-preview connection>"
  },
  "voiceBehaviour": { "bargeIn": false, "vad": false },
  "conventions": {
    "projectNamePattern": "[CUSTOMER]_Demo_<initials>",
    "folderPattern": "[customer]-demo",
    "demoBuildsRoot": "<absolute path of the workspace root — written at setup time, NOT a relative '.'>"
  }
}
```

> `apiKeyRef` is the API key for the **voice-preview speech connection** in Cognigy (used for the in-UI preview only). It is *not* the Cognigy `COGNIGY_API_KEY` — that lives in `.env`. For a demo preview connection a placeholder like `test` is acceptable. `demoBuildsRoot` is resolved to an **absolute** path when the file is written (Step 6), so the config is unambiguous when read from a child build folder.

`.env` (secret, separate file):

```
COGNIGY_BASE_URL=https://cognigy-api-<region>.nicecxone.com
COGNIGY_API_KEY=<your api key>
```

**What each block feeds** (see `build-orchestrator` "Default build values"): `connection` → MCP auth + as-built endpoint host; `llm.options`/`default` → `update_ai_agent.jobConfig.llmProviderReferenceId` (default selected, alternates offered); `llm.embedding` → Knowledge AI (§0.5/§1.8); `tts`/`stt` → voice config (Synthesizer/Recognizer); `stt.hints`/`dynamicHints` → Set Session Config `sttHints`; `channel.voiceGateway` → the webRTC Click-to-Call endpoint bound to the flow; `voicePreview` → the Azure speech connection used for in-UI preview; `conventions` → project + folder naming.

## Steps

### 1. Welcome + detect first run

Greet the user — e.g. *"Welcome to the Cognigy-Vibe plugin. Looks like your first time — I'll run a quick one-time setup so every build after this needs zero manual config."* (Skip the welcome flourish on a deliberate re-run.)

### 2. Locate the `Demo Builds` workspace root

- If the current directory **is** a `Demo Builds` folder (or contains `default-demo-config.json`), use it.
- Else look for a `Demo Builds` / `demo-builds` folder in the cwd or its parents — **walking up only as far as `$HOME`, never past it to `/`** (see the Assumptions callout / #82).
- **If none exists, create one at the current working directory** and tell the user the absolute path. This is the workspace root; all customer builds become sub-folders here. (Creation is cwd-dependent — see #82.)

### 3. Check for existing workspace config

Look for `default-demo-config.json` and `.env` at the workspace root.

- **Both present:** show a compact summary table and ask: keep as-is / edit specific fields / start fresh. Keep → done.
- **Missing or partial:** continue to the wizard (step 4), pre-filling from whatever exists.

### 4. (Optional) discover live resource IDs

If `cognigy-vibe` is connected, offer to list real resources so the user picks instead of pasting — most valuable for **LLM referenceIds**. Use `cognigy_list` (snake_case params); `resource_type` passes straight through to the REST path, so LLM discovery needs **no NiCE MCP dependency**:

```
cognigy_list { resource_type: "projects" }
cognigy_list { resource_type: "largelanguagemodels", project_id: "<id>", full_objects: true }
# → GET /v2.0/largelanguagemodels?projectId=<id> — each item has name (label), referenceId, modelType, provider
```

Match LLMs by `name` (label) and capture each `referenceId` into `llm.options[]`; embedding models likewise into `llm.embedding`. See `explain("llm-resources")` for referenceId resolution and project-scope details. If `cognigy-vibe` isn't connected, collect as free text and note they can re-run setup to validate later.

### 5. Wizard interview (`AskUserQuestion` batches)

Collect the schema. Pre-fill each option with sensible defaults so a user on the reference tenant can accept fast; others override. Group into ≤3 batches:

| Group | Captures |
|---|---|
| **Identity & tenant** | owner initials; `connection.region` → derives baseUrl + endpointBase; **API key** (→ `.env`) |
| **LLM** | one or more generation LLMs (label + referenceId), which is `default`; optional embedding LLM; temperatures |
| **Voice — TTS/STT** | TTS vendor/model/voiceType/voiceId/label/language; STT vendor/label/language; STT hints + dynamic hints on/off |
| **Channel & preview** | channel type (default voice-webRTC); VoiceGateway endpoint name (default `Click-to-Call`); voice-preview speech provider + connection name/region |

`maxTokens` (400), `toolChoice` (auto), `voiceBehaviour` (barge-in/VAD off) are written at defaults without a question unless the user asks.

### 6. Write the files

```bash
mkdir -p "<workspace root>"
```

- Set `conventions.demoBuildsRoot` to the **absolute path** of the resolved workspace root (not `.`), so the config is unambiguous when later read from a child build folder.
- Write `default-demo-config.json` (pretty JSON, `$schemaVersion: 2`) at the workspace root.
- Write `.env` with `COGNIGY_BASE_URL` + `COGNIGY_API_KEY` at the workspace root (unless the user chose the outside-the-synced-tree option — then write it there and tell them to set `COGNIGY_PROJECT_ROOT`).
- Ensure `.env` is gitignored if the workspace is a git repo. Re-read both files back and confirm they parse / are well-formed.

### 7. Confirm + next step

Report: workspace root path, both files written, a non-secret summary table, and the secret/cloud-sync note from above. Then: *"You're set up. Open (or stay in) `Demo Builds/` and say e.g. 'build a demo for Liberty Financial' — the build will use these defaults with no further setup."*

## Notes

- This skill replaces the per-user `~/.config/cognigy-mcp/build-config.json` location with a **workspace-level** config at the `Demo Builds` root, so the defaults travel with the workspace and `cognigy-vibe` (launched from that root) finds the `.env` automatically.
- The live **LLM gate** (`build-orchestrator` §1.1 Step 2) still verifies the chosen generation LLM exists in the target project before generation is relied on — the config supplies the *suggested* referenceId, not a guarantee.
- Voice provisioning (VoiceGateway webRTC endpoint + speech-preview connection) is **in scope of the config** here; whether the MCP creates it end-to-end without UI depends on `manage_voice_gateway` capabilities — see the plugin issues filed alongside this skill.
