# Workspace Config Contract — Design Spec

**Date:** 2026-06-28
**Closes:** #82
**Companion issues:** #74 (MCP `.env` walk-up), #75 (config adoption in MCP)
**Future issue:** hot-switch config tool (out of scope — see §5)

---

## Problem

`cognigy:init-cognigy-vibe` (PR #68) introduced a workspace config model whose directory-discovery logic was implicit, undocumented, and inconsistent between the skill and the MCP. Issue #82 tracks the open design questions. This spec resolves them.

---

## Principles

- **MCP is source of truth.** Config discovery, loading, and state reporting are MCP responsibilities. Skills call MCP tooling; they do not implement their own discovery logic.
- **Skill is guidance.** Skills direct the LLM through setup interactions and interpret MCP state. They do not walk directories or write config files outside of the setup wizard.
- **Simple first.** The default path (FTUE + global config) must require zero manual config after the wizard runs once. Power-user features (workspace overrides, hot-switch) are additive.

---

## §1 — Config discovery contract

Two independent cascades run at MCP startup. They are separate concerns.

### 1.1 `.env` (credentials)

Handled by `orchestrator.py`. Controls whether the server starts in full or degraded mode.

**Discovery order:**
1. Walk up from `cwd` toward `$HOME`, checking each directory for `.env`
2. First `.env` found → set `COGNIGY_PROJECT_ROOT` to that directory, load it
3. No `.env` found anywhere → degraded mode (existing behaviour)

**Boundary:** Walk stops at `$HOME`. Never traverses above it.

**Hot-reload path unchanged:** In degraded mode the orchestrator checks `COGNIGY_PROJECT_ROOT/.env` on every tool call. Because `COGNIGY_PROJECT_ROOT` is now the walk-up result (not always cwd), a `.env` in a parent directory is detected correctly on hot-reload.

**Mental model:** `.env` is per-project. New directory = new Cognigy project = new `.env`. The MCP is always working in the context of a single project.

### 1.2 `default-demo-config.json` (non-secret build defaults)

Handled by `server.py` during `_create_full_server()`. Does not affect full/degraded mode selection.

**Discovery order (first file found wins — no merging):**
1. `<cwd>/default-demo-config.json`
2. Walk up from `cwd` toward `$HOME`, first match wins
3. `~/.config/cognigy-vibe/config.json`
4. Nothing found → `config_loaded: false`; server runs normally; skills fall back to hardcoded defaults

**Boundary:** Walk stops at `$HOME`.

**Loaded once** at server startup. No hot-reload for config — a config change requires a session restart. This is acceptable; config is set-it-and-forget-it.

**First-wins semantics:** A project-level file must be complete if it exists. There is no field-level merging between layers. The source path reported to the skill shows exactly which file won.

---

## §2 — `get_build_state` extension

Three new top-level fields are added to the `get_build_state` response. All existing fields are unchanged.

```json
{
  "flows": { "...": "..." },
  "agents": { "...": "..." },
  "_version": "1.6.0",

  "config_loaded": true,
  "config_source": "/Users/ben/.config/cognigy-vibe/config.json",
  "config_summary": {
    "region": "au1",
    "llm_default": "Azure GPT-4o",
    "tts_label": "ElevenLabs Aria",
    "stt_label": "Microsoft AU",
    "locale": "en-AU"
  }
}
```

When `config_loaded: false`, `config_source` and `config_summary` are omitted.

**Filter behaviour:** When `resource_type` is passed (e.g. `get_build_state(resource_type="flows")`), the three config fields are included regardless. They are cheap and `§0.0` always needs them.

---

## §3 — `cognigy:init-cognigy-vibe` skill behaviour

The skill is the setup path. It writes files and guides the user. It does not enforce or discover — that is the MCP's job.

### Trigger conditions

- User explicitly runs the wizard (`/init-cognigy-vibe`, "set up cognigy vibe", "configure my demo build defaults", etc.)
- `build-orchestrator §0.0` delegates here when `get_build_state` returns `config_loaded: false`

### What it writes

| File | Location | Contents |
|------|----------|----------|
| `.env` | `cwd` (always) | `COGNIGY_BASE_URL`, `COGNIGY_API_KEY` |
| `config.json` | `~/.config/cognigy-vibe/` on FTUE | Full build defaults (`$schemaVersion: 2`) |
| `config.json` | `cwd` (explicit workspace override only) | Full build defaults for this project only |

The wizard always writes to cwd for `.env`. It writes to `~/.config/cognigy-vibe/` for the non-secret config on first-time setup. A user who wants a project-local config override (e.g. different tenant, different LLM) re-runs the wizard from that project directory and chooses "workspace override" — the wizard writes a complete `config.json` to cwd.

### Wizard flow

1. Call `get_build_state`.
   - `config_loaded: true` → show compact summary table and ask: keep / edit / start fresh. "Edit" re-runs the relevant wizard batches with current values pre-filled; user changes only what they want. Keep → done (exit early).
   - `config_loaded: false` → run full wizard.
2. Collect credentials (batch 1): `COGNIGY_BASE_URL`, `COGNIGY_API_KEY`.
3. Collect non-secret defaults (batches 2–3): LLM options + default, TTS, STT, voice channel, locale. Offer to list live LLM referenceIds via `cognigy_list { resource_type: "largelanguagemodels" }` if credentials are already available.
4. Write `.env` to cwd.
5. Write `config.json` to `~/.config/cognigy-vibe/config.json` (creating the directory if needed).
6. Confirm: show both file paths, a non-secret summary table, and the note that `.env` is project-local while `config.json` is global.

### What it does NOT do

- Does not walk up looking for existing `.env` files. The MCP's walk-up is for reading; the wizard always writes to cwd.
- Does not merge fields into an existing config. First-wins means a project-level file must be complete. The wizard writes complete files.
- Does not create `Demo Builds/` or assume any folder naming. The session's cwd is the project root.

---

## §4 — `build-orchestrator §0.0` preflight

```
1. Call get_build_state (no filter — needs config fields).

2. If config_loaded: false
   → Delegate to cognigy:init-cognigy-vibe.
   → Re-call get_build_state once after wizard completes.
   → If still config_loaded: false → hard stop:
       "Config setup did not complete. Please run cognigy:init-cognigy-vibe
        before starting a build."
     Do NOT fall back silently to hardcoded AU1 defaults.

3. If config_loaded: true
   → Show config_summary as a compact confirmation table:

     | Setting | Value | Source |
     |---------|-------|--------|
     | Region  | au1   | ~/.config/cognigy-vibe/config.json |
     | LLM     | Azure GPT-4o | (same) |
     | TTS     | ElevenLabs Aria | (same) |
     | STT     | Microsoft AU | (same) |
     | Locale  | en-AU | (same) |

   → Ask: "Proceed with these defaults, switch LLM to a listed alternate,
            or override a field for this build only?"

4. Per-build overrides stay in memory (buildConfig) for this run only.
   They do not rewrite config.json.
   To permanently change defaults, user re-runs cognigy:init-cognigy-vibe.
```

The confirmation gate is skill-side — the MCP cannot present UI. The `config_source` path is surfaced so the user knows whether they're on a global or project-local config.

---

## §5 — Out of scope: hot-switch config tool

A future `switch_config` MCP tool would let power users swap the loaded config mid-session (e.g. switch from AU1 to NA1 defaults without a session restart). This is not in scope for this spec.

**Action:** File a new GH issue after this spec merges.

---

## §6 — Files changed

| File | Change |
|------|--------|
| `cognigy-mcp/cognigy_mcp/orchestrator.py` | Walk up from cwd to find `.env`; set `COGNIGY_PROJECT_ROOT` to the containing dir |
| `cognigy-mcp/cognigy_mcp/server.py` | Load `default-demo-config.json` via cascade in `_create_full_server()`; pass loaded config into state/handlers |
| `cognigy-mcp/cognigy_mcp/tools/state_tools.py` | Add `config_loaded`, `config_source`, `config_summary` to `get_build_state` response |
| `skills/init-cognigy-vibe/SKILL.md` | Remove `Demo Builds` folder assumption; write `.env` to cwd, `config.json` to `~/.config/cognigy-vibe/`; call `get_build_state` to detect existing config |
| `skills/build-orchestrator/SKILL.md` | Update §0.0 to match §4 above |
| `skills/init-cognigy-vibe/SKILL.md` (schema) | Remove `conventions.demoBuildsRoot` field from `default-demo-config.json` schema; remove `conventions` block entirely |

---

## §7 — What this resolves from #82

| #82 question | Resolution |
|---|---|
| Naming (`Demo Builds` hard requirement?) | Eliminated. No folder name assumed. cwd is the project root. |
| Multiple workspaces / multi-tenant | Walk-up finds the nearest `.env`; different project dirs have different `.env` files. Global `config.json` covers same-tenant defaults; project-level `config.json` covers tenant-switching. |
| Nesting depth | Not a constraint. Walk-up finds `.env` at any ancestor depth (bounded by `$HOME`). |
| cwd-dependent creation | Wizard always writes `.env` to cwd (explicit, intentional). Global `config.json` goes to `~/.config/cognigy-vibe/` (stable, not cwd-dependent). |
| Walk-up boundary | Stops at `$HOME`. Never traverses above it. |
| `demoBuildsRoot: "."` relative path | Eliminated. The conventions block and `demoBuildsRoot` field are removed from the config schema. |
| Git repos / `.env` gitignore | `.env` is per-project-directory. Wizard checks for `.gitignore` and warns if `.env` is not gitignored. |
