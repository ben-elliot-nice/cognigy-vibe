---
name: init-cognigy-vibe
description: First-time-user setup wizard for the Cognigy-Vibe plugin. Run once per workstation to capture every variable a demo build needs — Cognigy API URL + key, LLM reference IDs, TTS, STT, voice channel (VoiceGateway webRTC), and voice-preview settings — and write them as reusable defaults. After this runs, `cognigy-vibe:build-orchestrator` builds for any customer with zero further manual setup. Triggers — "/init-cognigy-vibe", "set up cognigy vibe", "set up cognigy vibe MCP", "set up the cognigy plugin", "cognigy first-time setup", "configure my demo build defaults", "show/edit my Cognigy build config". Also auto-delegated by `build-orchestrator` S0.0 when no workspace config is found. Writes a non-secret `default-demo-config.json` to `~/.config/cognigy-vibe/config.json` and a secret `.env` to cwd; never commits secrets.
---

# cognigy-vibe:init-cognigy-vibe — first-time setup wizard

This is the **front door** for a new Cognigy-Vibe user. It captures, once, everything a build needs and stores the non-secret config globally at `~/.config/cognigy-vibe/config.json` and credentials in `.env` at cwd. From then on, `cognigy-vibe:build-orchestrator` reads these defaults and never re-asks for tenant, credentials, LLM, voice, or naming.

> **Run order.** Run this **before your first build**, or just start a build — `build-orchestrator` S0.0 auto-delegates here if no workspace config exists. Re-run any time to view or change your defaults.

> **Secrets & cloud sync.** `COGNIGY_API_KEY` is the one true secret. It is written **only** to `.env` in cwd. If cwd is in a cloud-synced folder (OneDrive/Dropbox/iCloud), `.env` syncs — treat that as publishing the key. Inform the user to move it outside the synced tree and set `COGNIGY_PROJECT_ROOT` if needed. Never write the API key into `default-demo-config.json` and never commit it.

> **Dependency:** Read `cognigy-vibe:build-config` before proceeding — it is the canonical reference for the schema, all field descriptions, cascade discovery order, and where to write each file. The wizard steps below assume that context.

## Steps

### 1. Welcome + detect first run

Greet the user — e.g. *"Welcome to the Cognigy-Vibe plugin. Looks like your first time — I'll run a quick one-time setup so every build after this needs zero manual config."* (Skip the welcome flourish on a deliberate re-run.)

### 2. Verify MCP connectivity (hard prerequisite — runs before config check)

Call `cognigy_list { resource_type: "projects" }`.

- **Success** → proceed to Step 3.
- **Failure** → **Hard stop:**
  > "MCP connection required before setup can continue. Check that `COGNIGY_BASE_URL` and `COGNIGY_API_KEY` are set in your `.env` file, restart the Claude Code session, and re-run `cognigy-vibe:init-cognigy-vibe`."

  Do not fall through to manual LLM entry. There is no manual entry path for LLMs.

### 3. Check for existing workspace config

Call `get_build_state`. Inspect `config_loaded`:

- **`config_loaded: true`** → show a compact summary table (region, LLM, TTS, STT, locale, source path)
  and ask: **keep as-is / edit / start fresh**.
  - Keep → done (exit the wizard).
  - Edit → re-run the relevant wizard batches (steps 4–5) with current values pre-filled; user changes only what they want.
  - Start fresh → proceed to step 4 with blank fields.
- **`config_loaded: false`** → no config found anywhere in the cascade. Proceed to step 4 (full wizard).

### 4. Wizard interview (`AskUserQuestion` batches)

Collect the schema. Group into ≤3 batches:

| Group | Captures |
|---|---|
| **Identity & tenant** | owner initials; `connection.region` → derives baseUrl + endpointBase; **API key** (→ `.env`) |
| **LLM** | Discovered live — see below (no manual UUID entry) |
| **Voice — TTS/STT** | TTS vendor/model/voiceType/voiceId/label/language; STT vendor/label/language — enter values as shown in Cognigy UI → Settings → Connections. No defaults provided. |
| **Channel & preview** | channel type (default voice-webRTC); VoiceGateway endpoint name (default `Click-to-Call`); voice-preview speech provider + connection name/region |

`temperatureVoice` (0.2), `temperatureChat` (0.5), `maxTokens` (400), `toolChoice` (auto), `voiceBehaviour` (barge-in/VAD off) are written at defaults without a question unless the user asks.

#### Live LLM discovery (runs before the LLM group question)

1. `cognigy_list { resource_type: "largelanguagemodels", full_objects: true, fields: ["_id", "name", "referenceId", "resourceLevel", "modelType", "provider"] }`
2. Filter: keep `resourceLevel == "organisation"` AND `modelType` does not contain `"embedding"` (case-insensitive).
3. If the filtered list is empty → **hard stop:** *"No organisation-level LLMs found on this tenant. Ask your Cognigy admin to configure at least one org-level generation LLM, then re-run setup."*
4. Present as `AskUserQuestion` — one option per model. Label: `"<name> (<modelType>)"`. Description: provider name.
5. Write the selected model to config as `llm.options[0]`:
   ```json
   {
     "label": "<name>",
     "referenceId": "<referenceId>",
     "id": "<_id>",
     "resourceLevel": "organisation"
   }
   ```
   Also set `llm.default` to the selected model's `label`.

Do not present a pre-selected default. Do not ask the user to type or paste a UUID.

> **Note:** TTS/STT connection discovery is not yet supported — enter connection labels and voice IDs as shown in Cognigy UI → Settings → Connections. Automated discovery is tracked in [issue #76](https://github.com/ben-elliot-nice/cognigy-claude-plugin/issues/76) (Voice Gateway integration).

### 5. Write the files

- Write `.env` with `COGNIGY_BASE_URL` + `COGNIGY_API_KEY` to **cwd** (the project directory this session is open in). Always writes here — no walk-up.
- Write `default-demo-config.json` (pretty JSON, `$schemaVersion: 2`) to **`~/.config/cognigy-vibe/config.json`** on first-time setup (creating the directory if needed). If the user explicitly requested a workspace override for this project only, write to cwd instead.
- Ensure `.env` is gitignored if cwd is a git repo: check for `.gitignore`; if `.env` is not listed, append it and tell the user.
- Re-read both files back and confirm they parse / are well-formed.

### 6. Confirm + next step

Report:
- `.env` written to: `<cwd>/.env` (workspace-level — shared across all Demo Builds/ in this session — see explain("session-workspace"))
- Config written to: `~/.config/cognigy-vibe/config.json` (global — applies to all future projects on this tenant)
- Non-secret summary table of the written config values
- Cloud-sync note: if cwd is in a cloud-synced folder (OneDrive/Dropbox/iCloud), `.env` is synced — treat that as publishing the API key. Move it outside the synced tree and set `COGNIGY_PROJECT_ROOT` if needed.

Then: *"You're set up. Open a new project directory, say 'build a demo for Liberty Financial' — credentials are already here, build defaults will inherit from your global config."*

## Notes

- See explain("session-workspace") for the directory model. One `.env` at workspace root serves all builds in a session. If you need to work against a completely separate tenant, open a different workspace directory and run this wizard there — see "Cross-workspace and different-tenant sessions" in that topic.
- The global `config.json` at `~/.config/cognigy-vibe/config.json` applies to all projects on the same tenant. Drop a `default-demo-config.json` into any project directory to override for that project only — must be a complete file (no field merging).
- The live **LLM gate** (`build-orchestrator` S1.1 Step 2) still verifies the chosen generation LLM exists in the target project before generation is relied on.
- Voice provisioning details depend on `manage_voice_gateway` capabilities — see the plugin issues filed alongside this skill.
