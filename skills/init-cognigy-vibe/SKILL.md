---
name: init-cognigy-vibe
description: First-time-user setup wizard for the Cognigy-Vibe plugin. Run once per workstation to capture every variable a demo build needs — Cognigy API URL + key, LLM reference IDs, TTS, STT, voice channel (VoiceGateway webRTC), and voice-preview settings — and write them as reusable defaults. After this runs, `cognigy:build-orchestrator` builds for any customer with zero further manual setup. Triggers — "/init-cognigy-vibe", "set up cognigy vibe", "set up cognigy vibe MCP", "set up the cognigy plugin", "cognigy first-time setup", "configure my demo build defaults", "show/edit my Cognigy build config". Also auto-delegated by `build-orchestrator` S0.0 when no workspace config is found. Writes a non-secret `default-demo-config.json` to `~/.config/cognigy-vibe/config.json` and a secret `.env` to cwd; never commits secrets.
---

# cognigy:init-cognigy-vibe — first-time setup wizard

This is the **front door** for a new Cognigy-Vibe user. It captures, once, everything a build needs and stores the non-secret config globally at `~/.config/cognigy-vibe/config.json` and credentials in `.env` at cwd. From then on, `cognigy:build-orchestrator` reads these defaults and never re-asks for tenant, credentials, LLM, voice, or naming.

> **Run order.** Run this **before your first build**, or just start a build — `build-orchestrator` S0.0 auto-delegates here if no workspace config exists. Re-run any time to view or change your defaults.

> **Secrets & cloud sync.** `COGNIGY_API_KEY` is the one true secret. It is written **only** to `.env` in cwd. If cwd is in a cloud-synced folder (OneDrive/Dropbox/iCloud), `.env` syncs — treat that as publishing the key. Inform the user to move it outside the synced tree and set `COGNIGY_PROJECT_ROOT` if needed. Never write the API key into `default-demo-config.json` and never commit it.

> **Dependency:** Read `cognigy:build-config` before proceeding — it is the canonical reference for the schema, all field descriptions, cascade discovery order, and where to write each file. The wizard steps below assume that context.

## Steps

### 1. Welcome + detect first run

Greet the user — e.g. *"Welcome to the Cognigy-Vibe plugin. Looks like your first time — I'll run a quick one-time setup so every build after this needs zero manual config."* (Skip the welcome flourish on a deliberate re-run.)

### 2. Check for existing workspace config

Call `get_build_state`. Inspect `config_loaded`:

- **`config_loaded: true`** → show a compact summary table (region, LLM, TTS, STT, locale, source path)
  and ask: **keep as-is / edit / start fresh**.
  - Keep → done (exit the wizard).
  - Edit → re-run the relevant wizard batches (steps 3–4) with current values pre-filled; user changes only what they want.
  - Start fresh → proceed to step 3 with blank fields.
- **`config_loaded: false`** → no config found anywhere in the cascade. Proceed to step 3 (full wizard).

### 3. (Optional) discover live resource IDs

If the NiCE Cognigy MCP or `cognigy-vibe` is connected, offer to list real resources so the user picks instead of pasting — most valuable for **LLM referenceIds** and **TTS/STT connection labels**:

```
cognigy_list { resource_type: "projects" }
cognigy_list { resource_type: "largelanguagemodels", project_id: "<id>", full_objects: true }
  # returns name (label), referenceId, modelType, provider
```

Present generation LLMs for `llm.options`, embedding models for `llm.embedding`. If no MCP is connected, collect as free text and note they can re-run setup to validate later.

### 4. Wizard interview (`AskUserQuestion` batches)

Collect the schema. Pre-fill each option with sensible defaults so a user on the reference tenant can accept fast; others override. Group into ≤3 batches:

| Group | Captures |
|---|---|
| **Identity & tenant** | owner initials; `connection.region` → derives baseUrl + endpointBase; **API key** (→ `.env`) |
| **LLM** | one or more generation LLMs (label + referenceId), which is `default`; optional embedding LLM; temperatures |
| **Voice — TTS/STT** | TTS vendor/model/voiceType/voiceId/label/language; STT vendor/label/language; STT hints + dynamic hints on/off |
| **Channel & preview** | channel type (default voice-webRTC); VoiceGateway endpoint name (default `Click-to-Call`); voice-preview speech provider + connection name/region |

`maxTokens` (400), `toolChoice` (auto), `voiceBehaviour` (barge-in/VAD off) are written at defaults without a question unless the user asks.

### 5. Write the files

- Write `.env` with `COGNIGY_BASE_URL` + `COGNIGY_API_KEY` to **cwd** (the project directory this session is open in). Always writes here — no walk-up.
- Write `default-demo-config.json` (pretty JSON, `$schemaVersion: 2`) to **`~/.config/cognigy-vibe/config.json`** on first-time setup (creating the directory if needed). If the user explicitly requested a workspace override for this project only, write to cwd instead.
- Ensure `.env` is gitignored if cwd is a git repo: check for `.gitignore`; if `.env` is not listed, append it and tell the user.
- Re-read both files back and confirm they parse / are well-formed.

### 6. Confirm + next step

Report:
- `.env` written to: `<cwd>/.env` (project-local — credentials for this Cognigy project only)
- Config written to: `~/.config/cognigy-vibe/config.json` (global — applies to all future projects on this tenant)
- Non-secret summary table of the written config values
- Cloud-sync note: if cwd is in a cloud-synced folder (OneDrive/Dropbox/iCloud), `.env` is synced — treat that as publishing the API key. Move it outside the synced tree and set `COGNIGY_PROJECT_ROOT` if needed.

Then: *"You're set up. Open a new project directory, say 'build a demo for Liberty Financial' — credentials are already here, build defaults will inherit from your global config."*

## Notes

- `.env` is per-project-directory. New directory = new Cognigy project = new `.env`. The MCP always works in the context of a single project.
- The global `config.json` at `~/.config/cognigy-vibe/config.json` applies to all projects on the same tenant. Drop a `default-demo-config.json` into any project directory to override for that project only — must be a complete file (no field merging).
- The live **LLM gate** (`build-orchestrator` S1.1 Step 2) still verifies the chosen generation LLM exists in the target project before generation is relied on.
- Voice provisioning details depend on `manage_voice_gateway` capabilities — see the plugin issues filed alongside this skill.
