---
name: build-orchestrator
description: End-to-end Cognigy AI Agent demo builder — the orchestrator that drives the full cognigy plugin stack (scope → design → build). Use when the user says "build a Cognigy demo for <customer>", "scaffold an agent for X", "new customer agent for X", "set up a Cognigy build for X", "new AI Agent demo — <customer>". Overarching orchestrator — at §0.0 loads workspace build defaults (LLM/embedding/TTS/STT/channel/voice/tenant/naming) from `default-demo-config.json` at the `Demo Builds` root, written by `cognigy:init-cognigy-vibe` (delegates to it if missing; binds the project in-session with no restart when the workspace `.env` + projectless cognigy-vibe are present), then runs a single-batch interview, then delegates scoping to `cognigy:scope-demo` and design to `cognigy:design-agent` (persona/jobs/interfaces/contracts), then builds: project + AI Agent + Job Node patch + init chain (Once → Initialize Session → Set Session Config → Say Welcome → Wait) + tool branches (Say filler → Code mock → Resolve, reversed for transfers) + end-call pair + as-built from `get_flow_chart` + drift baseline + package zip. Tools authored as `.tool.json` files then pushed via `push_agent_tool`. xApp HTML moments pushed via `push_html_node`. Industry-flexible CRM (insurance / telco / retail / banking / health). Knowledge gated by §0.5; if opened, wired via Cognigy's built-in Knowledge AI (`manage_knowledge` + `manage_settings`) in §1.8. Smoke test runs in §1.7 before hand-back — Phase A structural verification against `get_flow_chart` (12 assertions, incl. a ≤1000-char agent-field cap) + Phase B 3-turn `talk_to_agent` runtime check. Auto-loops on failure back to the relevant §1.5 / §1.4 / §5 step; only hands back when both phases are green.
---

# Build Orchestrator — end-to-end Cognigy AI Agent demo builder

> **Requires:** marketplace plugin `cognigy@nice` — provides sub-skills `cognigy:scope-demo`, `cognigy:design-agent`, `cognigy:design-agent-persona`, `cognigy:design-agent-jobs`, `cognigy:design-agent-interfaces`, `cognigy:design-agent-contracts`, `cognigy:init-mcp`, `cognigy:init-cognigy-vibe`. The orchestrator delegates to these by name; it does not vendor their content. **§0.0 preflight:** loads workspace build defaults from `default-demo-config.json` at the `Demo Builds` root (written by `cognigy:init-cognigy-vibe`); if absent, delegates to that skill first.
>
> **`cognigy-vibe-mcp` install.** Use latest: `uv tool install cognigy-vibe-mcp` (first time) or `uv tool upgrade cognigy-vibe-mcp` (after). Floor is now **1.4.2** — this skill version depends on v1.4.0+ features: **file-backed tool authoring via `push_agent_tool`** (the canonical §1.3/§6 path — added in plugin **1.4.2** via PR #54; on < 1.4.2 the tool is absent and `cognigy_create` still accepts `aiAgentJobTool`), `push_code_node` CREATE mode (single-call create+position+push — §1.5(b), §6), IF/Once branch-marker insertion (§1.4b — `explain("node-positioning")`), the corrected say-node string-array + `generativeAI_customInputs: []` shape (§1.5(d) — `explain("say-node")`), the xApp inbound event path (§1.4b / §1.7 — `explain("xapp-event-handling")`), and the `explain()` topics `project-snapshots` / `voice-silence-timeout` / `output-formats` / `knowledge-store` referenced throughout. On < 1.4.0 these instructions fail (e.g. `push_code_node` still requires a pre-existing `node_id`; the cited topics 404). Earlier versions also miss AU1 stability fixes (extension mapping for `aiAgentJob` → `@cognigy/basic-nodes` and `aiAgentToolAnswer` extension coverage, safe `nodeId` fallback in `_build_hierarchy`, 204 No Content handling in `patch()`, `sync_remote_state` direct-endpoint fallback) and the project-binding refactor (`ProjectState.bind_project()`, server boots without `COGNIGY_PROJECT_ID`, `sync_remote_state` binds project in-session) that §1.1.5 depends on. Anything ≥ floor is fine; the latest published version is always the recommended target. Each tagged release of this skill records the exact plugin version it was validated against in its annotated tag message — that's the pin if you need to roll back.

This is the go-to orchestrator for scaffolding a customer-specific Cognigy AI Agent demo from scratch. It produces a complete build adhering to the patterns documented in this skill body — full init chain, voice config, Shape-B tool branches with the plugin-canonical `aiAgentToolAnswer` terminal, transfer + end-call patterns, deterministic mocks, conditional-push xApp HTML, as-built docs generated from the live flow chart, drift baseline, package zip backup — for any industry, with the CRM shape adapting to the domain.

**This skill body IS the reference build.** The quality bar is the pattern set defined here, not any prior real-customer build. When a real build (e.g. a recent customer demo) surfaces a pattern that's better than what's documented here, promote it back into this skill via the `nice-build-retrospective` skill — that's the formal upstream path. The audit skills (`nice-audit-cognigy-build`, `nice-cognigy-health-check`) compare a live build against THIS skill body, not against a remembered historical customer. Do not name historical customers as quality benchmarks anywhere in this skill body — that creates stale references and burns tokens chasing prior projects.

**This skill is the overarching builder.** It keeps the single-batch interview UX the user likes, then delegates scoping and design to purpose-built sub-skills before running the build sequence:

- **`cognigy:scope-demo`** → produces `{Customer}-demo-plan.md` (12 facts, design conversation, demo plan)
- **`cognigy:design-agent`** → orchestrates four sub-skills that produce persona, architecture + context schema, interfaces, and contracts docs
- **`manage_knowledge` + `manage_settings`** → only if §0.5 gate opens, ingests locally-authored FAQ bodies into a Cognigy knowledge store and enables built-in Knowledge AI on the agent (§1.8)

Voice-preview provisioning is explicitly **out of scope** — that happens manually in the Cognigy UI. `talk_to_agent` smoke testing is **in scope** as of v4 — §1.7 runs Phase A structural + Phase B 3-turn runtime verification automatically before hand-back.

---

## When to load this skill

Trigger phrases (any = load end-to-end):

- "Build me a Cognigy demo for [customer]"
- "New AI Agent demo — [customer]"
- "Set up a Cognigy build for [customer]"
- "Scaffold an agent for [customer]"
- Any brief that names a customer + a role/persona the agent should play

If the user doesn't name a customer, still load — the interview in §0 gets the rest.

---

## §0.0 — Load build config (BLOCKING preflight — runs before the interview)

The tenant build defaults (LLM, embedding, TTS, STT, channel/voice gateway, voice preview, locale, hosts, naming) live in a **workspace-level** config written once by `cognigy:init-cognigy-vibe`: `default-demo-config.json` at the `Demo Builds` root (the folder that holds every `<customer>-demo/` sub-build), with secrets in a sibling `.env`. This is the authoritative source for the values that used to be hardcoded in the "Default build values" table below.

**Step 1 — find + read the config.** Look for `default-demo-config.json` at the workspace root — the `Demo Builds` folder. Check the cwd and walk **up** the parent directories (the session may be launched in `Demo Builds/` or in a `<customer>-demo/` sub-folder); the nearest ancestor that has the file is the workspace root. **Stop the walk at `$HOME` — never search past it to `/`** (see `cognigy:init-cognigy-vibe` Assumptions / issue #82).

```bash
# from cwd, search self + ancestors (bounded by $HOME) for the workspace config
d="$PWD"; while :; do [ -f "$d/default-demo-config.json" ] && { cat "$d/default-demo-config.json"; break; }; [ "$d" = "$HOME" ] || [ "$d" = "/" ] && break; d=$(dirname "$d"); done
```

**Step 2 — branch on what you find:**

- **File missing or unparseable** → the user hasn't run setup yet. Say so and delegate:
  > "I don't have your workspace build defaults yet (tenant, LLM, voice, etc.). I'll run `cognigy:init-cognigy-vibe` once to capture them at your `Demo Builds` root — after that every build needs zero manual config."

  Delegate to **`cognigy:init-cognigy-vibe`**, then re-read the file (Step 1) **once**. **🔴 Abort gate — no delegation loop.** If `default-demo-config.json` is *still* absent or unparseable after the delegation returns (user cancelled the wizard, or it failed to write), **STOP the build** with a clear message — do **not** re-delegate, and do **not** silently fall back to the hardcoded AU1 table:
  > "Setup didn't complete, so I don't have your build defaults and can't start a build safely. Re-run `cognigy:init-cognigy-vibe` when you're ready, then start the build again."

  Only continue past §0.0 once a valid config has been read.

- **File present** → load it into a `buildConfig` object (and note its directory as the **workspace root** — that's where the `.env` is and where new `<customer>-demo/` folders go). These values override the documented defaults in "Default build values" wherever they differ. Surface a compact summary in the §0 recap (Step 3).

**Step 3 — echo + confirm (not re-interview).** In the recap that follows §0.6, show the loaded config as a short table — default generation LLM (label) + any alternates, tenant region, persona temp, TTS voice label, STT label, voice channel, locale, project suffix — and ask the user to **confirm, switch the LLM to a listed alternate, or override for this build only**. A one-build override (e.g. the Azure GPT alternate, NZ English STT for a 2Degrees build, or a male voice) does **not** rewrite the saved file; it just changes `buildConfig` for this run. To change the saved defaults permanently, the user re-runs `cognigy:init-cognigy-vibe`.

> **Temperature precedence (config vs Q10).** §0.0 loads `buildConfig.llm.temperatureVoice` (0.2) and `temperatureChat` (0.5); the **interview Q10 channel mix is the selector**, not a competing value — it picks *which* configured temperature applies (primarily-chat → `temperatureChat`; otherwise `temperatureVoice`). Since Q10 runs after §0.0, resolve the temperature **after** the interview. Order of precedence: an explicit per-build override in this Step 3 wins; else Q10 selects between the two configured temperatures; the recap's "persona temp" is therefore provisional until Q10 is answered.

> **The live LLM gate (§1.1 Step 2) still runs.** The chosen LLM — `buildConfig.llm.default` (or the alternate the user picked in Step 3), resolved to its `referenceId` via `buildConfig.llm.options[]` — is the *suggested* value; the generation LLM must still be verified to exist in the target project before generation is relied on. A stale referenceId surfaces at the gate, not as a silent empty-output build.

`buildConfig` (or the user's per-build overrides of it) is what feeds §1.1 / §1.2 / §1.5 from here on. Where the "Default build values" table is cited downstream, read the corresponding `buildConfig` field instead.

---

## §0 — Interview (one batch via AskUserQuestion)

This single batch collects everything `cognigy:scope-demo` + the four `cognigy:design-agent-*` sub-skills need, so they produce their artifacts in context-provided mode (no re-interview).

| # | Question | Header | Required |
|---|---|---|---|
| 1 | Customer name (e.g. Zurich, Telstra, AMP, 2Degrees) | Customer | Yes |
| 2 | Brand sources — any specific URLs to prioritise (homepage, About, brand guidelines PDF, recent annual report)? Leave blank to let the skill web-search from customer name. | Brand sources | Optional |
| 3 | Industry preset — insurance / telco / retail / banking / health / other (drives CRM shape — see §3) | Industry | Yes |
| 4 | Persona name + tone (e.g. "Mira — calm, capable, Australian female"). **Note:** the skill will refine this with brand-voice research in §0.6 — your answer is the starting point, not the final word. | Persona | Yes |
| 5 | Role / one-line job description | Role | Yes |
| 6 | Use cases — 3–7 tool intents (e.g. `new_claim`, `pay_premium`, `roadside_assistance`). **Do NOT list transfer tools** — those are derived in §1.3 from your use cases. End-of-call tools are added automatically. | Use cases | Yes |
| 7 | Customer-specific CRM data values for the canonical template (industry-shaped — see §3) | CRM data | Yes |
| 8 | Sensitive-topic coverage — default: bereavement, suicide/self-harm, mental health, financial hardship, family/domestic violence, complaints, serious illness. Confirm or add categories. The empathy library in §2.5 will be baked into the persona. | Sensitive topics | Yes |
| 9 | Vulnerable-customer tone (default: confidence through competence — acknowledge once with the empathy template, lead with action, no platitudes) | Tone | Optional |
| 10 | Channel mix — voice / webchat / WhatsApp / mixed. **Drives `design-agent-interfaces` xApp + channel-formatting decisions and `design-agent-persona` channel rules.** Default: voice. | Channels | Yes |
| 11 | Compliance posture — regulated industry? mandatory disclaimers / recording notices / fair-dealing constraints / one-offer limits? "No regulated constraints" is a valid answer. **Feeds `design-agent-persona` compliance framing and `design-agent-contracts` obligation catalogue.** | Compliance | Yes |
| 12 | Obligation / guard surface — beyond the §2.5 empathy triggers, are there topics the agent must refuse, hard-handover triggers, or actions that need deterministic guards (e.g. cancellation staging, irreversible commits)? **Feeds `design-agent-contracts`.** | Guards | Optional |
| 13 | Reusable assets — any prior demo / project to fork from? (e.g. "fork the IAG agent, swap branding"). **Feeds `cognigy:scope-demo` reuse check and unlocks the `cognigy_invoke clone` fork lane in §1.0.** | Reuse | Optional |

After Q13 the skill runs **§0.5 (knowledge gate — BLOCKING decision)** and **§0.6 (brand research)**, then derives the **transfer-tool set (§1.3)** and the **persona descriptors** (Q4 + brand-voice research) — both cheap to compute and the two inputs most likely to be wrong.

**Pre-design confirm gate (BLOCKING — runs BEFORE the expensive §A/§B design run).** A wrong transfer set or off-brand persona caught here costs seconds; caught at the post-§B recap it wastes the whole scope-demo + 4-doc design run. Show the user these two derived items, then ask one `AskUserQuestion`:
- **Derived transfer tools** — one line each with its routing intent (e.g. `transfer_to_roadside_assist` ← breakdown / flat tyre / locked-out), plus the always-on `transfer_to_care` + `transfer_to_general`.
- **Persona descriptors** — persona name (Q4) + the brand-voice tone keywords from §0.6 that will shape the persona.

Question: *"These drive the whole design run — good to proceed, or adjust first?"* → options **[Proceed to design]** / **[Let me adjust]**. On "adjust", apply the correction (rename / add / remove a transfer; tweak a descriptor), echo the revised list, then proceed. Only after this gate clears does the skill run **§A (scope-demo)** and **§B (design-agent)** using the confirmed transfers + descriptors. (Running §1.3 derivation here also resolves the prior ordering issue where §B's `design-agent-jobs` consumed the §1.3 table before it was computed.)

Then it produces the **final build recap**, which shows:
- Persona description with brand-voice keywords highlighted
- Derived transfer tools (as confirmed at the pre-design gate)
- Sensitive-topic empathy templates being baked in
- Sub-skill artifacts produced: demo-plan, persona, architecture, context-schema, interfaces, contracts
- All other build settings

**Wait for "yes / go / confirmed" before building.** The user can edit any derived item or any artifact file in the recap before approving. This final recap is unchanged — the pre-design gate is an *additional, earlier* checkpoint, not a replacement.

**Do NOT ask** about: LLM choice, STT/TTS, endpoint type, init chain shape, end-of-call pattern — those are fixed in §1 / §3 / §4. Knowledge has its own gate — see §0.5.

---

## §0.5 — Knowledge gate (BLOCKING — decision only)

**This is a decision step. Execution moves to §1.8.**

**This build path has ZERO knowledge by default.** No knowledge store, no `.ctxt` files, no `manage_settings { set_knowledge_ai }`, no `search_*_faqs` tool, no `manage_knowledge` calls of any kind.

**Adding knowledge is only allowed if the user has EXPLICITLY confirmed it in the current session.** Explicit confirmation means one of:

- the user typed the word "knowledge", "FAQ", "RAG", ".ctxt", "knowledge base", "Expert", or "FAQs" in his brief AND said yes when you re-confirmed in the recap, **OR**
- You asked one direct yes/no question — "Do you want knowledge / FAQ search in this build?" — as the **first** clarifying question after the interview, and the user replied with an unambiguous yes.

**Do NOT** infer knowledge is wanted from: use cases that *sound* like FAQs, the customer's industry, past builds, FAQ-page mentions, or the persona being "knowledgeable".

**Output of this gate:**
- `knowledgeRequested: false` → continue to §0.6. No further knowledge work. The as-built will mention "knowledge not configured" as a known gap.
- `knowledgeRequested: true` → before continuing to §0.6, fire a second `AskUserQuestion` batch to collect FAQ topic specs. Per topic, capture:

  | # | Question | Header | Required |
  |---|---|---|---|
  | K1 | Topic title (one short noun phrase, e.g. "Cancelling your policy") | Topic title | Yes |
  | K2 | Body content — short markdown FAQ text (heading + a few paragraphs). Will be written to `knowledge/<slug>.md` and ingested into the Cognigy knowledge store in §1.8. | Body | Yes |

  Repeat the K1–K2 batch until the user says "done". All topic specs land in memory until §1.8. Defer all knowledge execution to **§1.8**, which runs after the core build and wires Cognigy's built-in Knowledge AI via `manage_knowledge` (create store + ingest the local bodies) + `manage_settings { set_knowledge_ai: true }`.

**Why this gate exists:** knowledge adds a store-ingestion step, an async ingestion wait, a `knowledgeSearchModelId` cross-project ref dependency, and retrieval wiring on the Job Node. Every prior demo where knowledge was added "to be helpful" cost 15–30 minutes of rework. Default-off keeps builds fast; the gate keeps assumptions explicit.

---

## §0.6 — Brand research (MANDATORY — runs between interview and recap)

The persona must reflect the customer's actual brand, not a generic Australian-female-calm. This step is what separates a NiCE-quality demo from a stock template.

**Inputs:** customer name (Q1), optional URLs (Q2).

**Process:**

1. **Web research** — WebSearch the customer name and fetch the top 3–5 most authoritative results. If Q2 URLs were supplied, prioritise those. Always attempt to fetch:
   - Customer homepage
   - About / Our Mission / Values page
   - Brand guidelines PDF if publicly listed
   - Most recent annual report or investor day deck (free text reveals tone)
   - Last 6 months of press releases / news coverage (sensitivities)

   **Run these 3–5 WebFetch calls in parallel** — issue them in a single message with multiple tool calls. Sequential fetches add ~30–60s per URL and burn cache cycles unnecessarily.

2. **Extract into a structured brand-research snapshot.** Write to `Demo Builds/<customer>-demo/brand-research.md`:

```markdown
# <Customer> — Brand Research Snapshot
*Generated <date> by cognigy:build-orchestrator §0.6*

## Brand voice — descriptors
3–6 adjectives drawn from the customer's own copy (NOT your guesses). Quote the source.
e.g. AMP: "purposeful", "human", "practical" (from amp.com.au/about — "We help Australians own tomorrow.")

## Mission / purpose statement
Verbatim from their site. One sentence.
e.g. "Help people create their tomorrow."

## Tone do's
3–5 patterns the brand uses. Quote example sentences from their copy.

## Tone don'ts
2–3 patterns the brand avoids. e.g. "AMP avoids financial jargon — uses 'super' not 'superannuation account' in customer-facing copy."

## Recent sensitivities (last 6 months)
3–5 items the AI Agent should be aware of so it doesn't blunder into them. e.g.:
- Royal Commission legacy — caller may reference past misconduct (acknowledge briefly, route to Care)
- 2026 advisor changes — some callers transitioning between advisors (route to advisor team)
- Cyber incident <date> — heightened sensitivity around identity verification
- Exec change — new CEO <name> since <date>

## Competitor voice contrast
One sentence on how this brand sounds *different* from peers. Sharpens the persona.
e.g. "AMP sounds warmer and more human than Colonial First State (institutional) or AustralianSuper (industrial-fund matter-of-fact)."

## Persona alignment notes
2–3 bullets on how to shape the persona description and jobDescription to match. These feed directly into §2.
```

3. **Inject into persona (per §2 four-layer ladder):**
   - **`## Persona`** (layer a) — replace generic tone descriptors with brand-voice descriptors (with brief quote-source) AND populate the BRAND VOICE block (descriptors, do's, don'ts) here, using brand-research.md content. (Brand voice lives in 1A Persona — NOT in Special Instructions.)
   - **`## Special Instructions`** (layer b) — global behaviour rules only (speaking conventions, abuse, out-of-scope); no brand voice here
   - **`## Job Description`** (layer c) — tone-shape verbs the persona uses to describe its capabilities ("guide" vs "process" vs "lodge") if brand voice favours specific verbs
   - **`## Job Instructions`** (layer d) — "Recent sensitivities" feed into the empathy library (§2.5) as additional context lines if relevant

4. **Show in recap.** The recap displays the brand-voice descriptors and recent sensitivities prominently so the user can sanity-check before approving.

**Hard rule:** Never put a persona into a build with descriptors that aren't traceable to the brand-research snapshot. If web research fails (paywalled site, scant content), STOP and ask the user to supply 3–5 lines of brand voice manually. Do not fabricate brand voice from training data — that produces generic personas.

---

## §A — Scope (delegate to `cognigy:scope-demo`)

The build skill keeps the interview UX. Scoping the demo — the 12 facts + design conversation — is delegated to the purpose-built sub-skill.

**Working directory:** ensure the demo folder exists, then `cd` into it before invoking, so `cognigy:scope-demo` writes its output here (per its Phase 4 rule: "Write to the directory from which the user launched Claude Code"):

```bash
mkdir -p "Demo Builds/<customer>-demo" && cd "Demo Builds/<customer>-demo"
```

On a fresh build the folder won't exist yet — `mkdir -p` is a no-op if it does, so this is safe on re-runs too.

**Invoke in context-provided mode.** Pass the interview answers verbatim so Phase 1 has nothing to ask about. Mapping (interview Q → scope-demo Fact):

| Interview Q | scope-demo Fact |
|---|---|
| Q1 Customer | #1 Customer name and industry/vertical |
| Q3 Industry | #1 (industry component) |
| Q5 Role | #2 Primary business problem (express as "agent X for problem Y") |
| Q10 Channels | #3 Target channels |
| Q6 Use cases | #4 Key use cases/intents |
| (default) | #5 Phasing — "MVP demo, single phase" unless the user says otherwise |
| (default) | #6 Demo format — "live in Cognigy Interaction Panel" unless the user says otherwise |
| (default) | #7 Demo timeline — "no fixed date" unless the user says otherwise |
| (skip — the user handles) | #8 Competitive context — leave blank, the user fills if relevant |
| (default) | #9 Integration landscape — "mock CRM via Initialize Session Code (§3)" |
| Q7 CRM data | #10 Available data — "fabricated values per CRM template §3" |
| Q13 Reuse | #11 Reusable components |
| Q11 Compliance | #12 Regulatory/compliance constraints |

If `scope-demo` *still* has a real gap after this mapping, allow a **single** follow-up question — do not let it re-run its full Phase 1 walkthrough.

**Phase 2 confirmation gate:** The sub-skill normally waits for explicit user confirmation of the 12 facts. Treat the user's §0 interview answers themselves as the confirmation — they supplied each fact directly, no recap-roundtrip needed at this point (the build-wide recap happens later, after §B). Surface a one-line "confirming facts as supplied in §0 interview, proceeding to Phase 3" and continue. Do NOT run scope-demo's Phase 2 prompt.

**Phase 3 design conversation:** This is where genuine value-add happens — narrative arc, scenario design, out-of-chat moments, irreversible actions, auth architecture. Run this collaboratively with the user. Do NOT default-fill these from the interview; the conversation is the point.

**Phase 4 output:** `{Customer}-{DemoType}-demo-plan.md` lands in `Demo Builds/<customer>-demo/`. Capture the exact filename — `§B` and later phases will read it.

**Hard rule:** Do not proceed to §B until the demo plan file exists on disk. If `scope-demo` fails to write the file, STOP and surface the error.

---

## §B — Design (delegate to `cognigy:design-agent`)

With `{Customer}-{DemoType}-demo-plan.md` and `brand-research.md` in the demo folder, invoke the design orchestrator.

**Working directory:** stay in `Demo Builds/<customer>-demo/`. The design sub-skills look for prior docs in CWD.

**Invoke in Mode A (full workflow).** Persona → Jobs → Interfaces → Contracts. The orchestrator runs each in sequence; each reads the prior outputs from disk.

**Context-provided suppression:** Pass the interview answers into each sub-skill so they don't re-interview. Mapping:

- **`design-agent-persona`** — pre-fill agent name (Q4), tone descriptors (Q4 + brand-research §Tone descriptors), primary channel (Q10), compliance framing (Q11). Output MUST follow the four-layer ladder (§2): `## Persona`, `## Special Instructions`, `## Job Description`, `## Job Instructions`. Special Instructions (1B) includes the canonical SPEAKING CONVENTIONS block (verbatim from §2 layer b) plus abuse / out-of-scope handling — **NOT brand voice**, which lives in `## Persona` (1A, sourced from brand-research.md). Universal Always/Never rules from Q12 + §2.5 empathy library live in `## Job Instructions` (see "Empathy injection" below for the verbatim rule).
- **`design-agent-jobs`** — pre-fill job definitions from Q6 use cases. For each use case, ask only "irreversible? staging?" if not obvious from the demo plan. Routing intents derive from Q6 → §1.3 transfer derivation table.
- **`design-agent-interfaces`** — pre-fill channel mix from Q10. Out-of-chat moments come from the demo plan's Phase 3 area 5; only ask for xApp content type / data payload if missing.
- **`design-agent-contracts`** — pre-fill obligation catalogue from Q11 compliance + Q12 guard surface + any irreversible-action staging captured by `design-agent-jobs`.

**Empathy injection (NON-NEGOTIABLE).** The §2.5 Empathy Response Library MUST appear **verbatim** inside the `## Job Instructions` H2 section of `{Customer}-agent-persona.md` (all 7 trigger categories, hard rules, Lifeline 13 11 14 for suicide/self-harm). It belongs in Job Instructions (layer d in the §2 ladder) because empathy templates are procedural — "when X is said, fire Y" — not agent-level identity. Two acceptable paths:

1. **Inject during invocation** — pass the §2.5 text as required content for the `## Job Instructions` section the sub-skill bakes in without paraphrasing.
2. **Post-process** — after `design-agent-persona` writes `{Customer}-agent-persona.md`, append the §2.5 library verbatim inside the `## Job Instructions` H2 section as a clearly marked "SENSITIVE-TOPIC EMPATHY PROTOCOL (MANDATORY — see §2.5)" subsection before §1 reads the file.

Either path is fine, but the verbatim text must end up in `## Job Instructions` (which §1.2 patches into the Job Node `instructions` field). Do NOT let the sub-skill paraphrase, trim, or "summarise" the empathy library. Do NOT put it in `## Persona` or `## Special Instructions` — that's a layer violation; empathy templates are job-procedural, not agent-global.

**Three-way field-name cross-check.** Before proceeding to §1, diff:
- `{Customer}-context-schema.md` (from `design-agent-jobs`) — context variable table
- The §3 canonical Initialize Session Code template (industry-shaped)
- The `verify_caller` Code mock template (§3)

If field names diverge, the build skill is the source of truth — flag the mismatch and update `{Customer}-context-schema.md` to match before §1.2 runs. §1.2 consumes the schema via `memoryContextInjection` — a stale schema there produces the same hallucinated-data bug, not just at §1.5. A typo here is the single most common cause of "the bot is hallucinating data".

**Outputs (must all exist before §1 starts):**
- `{Customer}-agent-persona.md` — **four H2 sections** in order: `## Persona`, `## Special Instructions`, `## Job Description`, `## Job Instructions`. §2.5 empathy library lives verbatim inside `## Job Instructions`.
- `{Customer}-agent-architecture.md`
- `{Customer}-context-schema.md`
- `{Customer}-agent-interfaces.md`
- `{Customer}-agent-contracts.md`

**Transfer-tool derivation stays in this skill (§1.3).** `design-agent-jobs` may surface routing logic, but the actual transfer-tool list — derived from Q6 use cases, with `transfer_to_care` + `transfer_to_general` always present — is computed in §1.3 of this skill. Sub-skill outputs inform but don't override the rule.

---

## §1.0 — Fork lane (not yet implemented)

> **Fork support is not yet implemented in this plugin.** The `cognigy:fork-existing-agent` sub-skill that would drive this lane has not shipped. **Regardless of how Q13 is answered, skip this section and proceed to §1.1** as a normal from-scratch build. Do not attempt to delegate to a fork sub-skill — it does not exist yet.

When the fork sub-skill ships, this lane will: clone the source project, audit and reconcile tools against this customer's §1.3 derived set, swap the cloned init-chain content (Init Session CRM body, Say Welcome variants, Set Session Config `sttHints`), and return the cloned `projectId` / `agentId` / `flowId` / `endpointId` plus the final tool list — letting the orchestrator skip §1.1 and §1.5. Until then, every build runs the full §1.1 path.

---

## Default build values (sourced from `buildConfig` — §0.0)

> **These values now come from the workspace config loaded in §0.0** (`default-demo-config.json` at the `Demo Builds` root, written by `cognigy:init-cognigy-vibe`). The table below documents the **NiCE AU1 demo-tenant fallback** — the shape of each value and what a working AU1 build uses. At build time, read the matching `buildConfig` field; the table is the reference for what each field means and the AU1 default if the user accepted it unchanged. Don't ask the user for these mid-build — §0.0 already loaded and confirmed them.

| `buildConfig` field | Setting | AU1 fallback value |
|---|---|---|
| `llm.default` + `llm.options[]` | LLM (generation) | default `global-gpt-4.1-mini` (`a793f9ea-befd-4fdf-8be8-b1c8a8385a91`); alternate `Azure GPT 4.1` (`edaaa112-3f1f-4b09-ba50-67a4285eba2b`). Resolve `default` (or the Step-3 alternate) to its `referenceId` via `options[]`. **Still verified live in the target project at §1.1 Step 2; never blind-hardcode.** A fresh project has no LLM and generates empty output until one is wired (reuse-via-`manage_packages` or `setup_llm`). |
| `llm.embedding.referenceId` | LLM (embedding) | *(optional — only used if §0.5 knowledge gate opens; empty if unset)* |
| `conventions.projectNamePattern` | Project name | `[CUSTOMER]_Demo_BH` (`_BH` = `owner.initials` build-owner tag) |
| `conventions.folderPattern` | Folder convention | lowercase `[customer]-demo/` under the workspace root (`Demo Builds/`) |
| `llm.temperatureVoice` / `temperatureChat` | Persona LLM temp | `0.2` voice/transactional (**default**); `0.5` ONLY when Q10 channel mix is primarily conversational chat (webchat/WhatsApp). Wired at §1.1 + §1.2. |
| `llm.maxTokens` | Persona maxTokens | `400` |
| `llm.toolChoice` | Persona toolChoice | **`auto`** (lowercase — NOT `required`. See §9) |
| `locale` | Locale | `en-AU` |
| `tts.vendor` | TTS Vendor | ElevenLabs |
| `tts.voiceType` | TTS Voice | `Custom` |
| `tts.voiceId` | TTS Voice ID | `kqVqVtE8vZVRm6uoad9t` |
| `tts.label` | TTS Label (Synthesizer connection) | `nexora_elevenlabs` |
| `tts.model` | TTS Model | `eleven_turbo_v2_5` |
| `tts.language` | TTS Language | `en` |
| `stt.vendor` | STT Vendor | Microsoft |
| `stt.label` | STT Label (Recognizer connection) | `nexora-azure-speech-services-australiaeast` |
| `stt.language` | STT Language | `en-AU` |
| `stt.hints` / `stt.dynamicHints` | STT Hints + Dynamic Hints | wired into Set Session Config `sttHints` (§1.5c); empty hints + dynamic-hints-on by default |
| `channel.type` | Channel | `voice-webrtc` (default) |
| `channel.voiceGateway.endpointName` | VoiceGateway endpoint | `Click-to-Call`, webRTC, bound to the flow (§1.1 / §1.5c). See voice-in-scope note below. |
| `voicePreview.*` | Voice-preview connection | Microsoft Azure Speech Services; connection `Test`, region `AU` (used for in-UI preview) |
| `voiceBehaviour.bargeIn` | Barge-in | Disabled |
| `voiceBehaviour.vad` | VAD | Disabled |
| `connection.endpointBase` | Endpoint host | `https://cognigy-endpoint-au1.nicecxone.com/<token>` (NOT `cognigy-api-au1` — 401s) |

**Voice in scope (config-level).** `channel.voiceGateway` and `voicePreview` capture a webRTC **Click-to-Call** endpoint bound to the flow and the Azure speech-preview connection. The build applies TTS/STT and Set Session Config from `buildConfig` automatically. Whether the VoiceGateway endpoint + speech-preview connection are **created end-to-end without UI** depends on `manage_voice_gateway` MCP capabilities — track via the plugin issues filed with `init-cognigy-vibe`. Where the MCP can't yet create them, the as-built records the one remaining manual UI step; **voice testing itself remains the user's job.**

**Legacy note (pre-§0.0 behaviour):** these were the demo defaults for the **NiCE AU1 demo tenant**, hardcoded here and swapped by hand per tenant/region. With §0.0 in place that swap is captured once in `buildConfig` (`cognigy:init-cognigy-vibe`) instead of edited in this skill body. A one-build override (e.g. the Azure GPT alternate, NZ English STT for a 2Degrees build, or a male voice) changes `buildConfig` for this run only; a permanent change is a `cognigy:init-cognigy-vibe` re-run.

> **Temperature is the one channel-derived value.** Default `0.2` (voice / transactional — the common case). Set `0.5` only when interview **Q10 channel mix is primarily conversational chat** (webchat / WhatsApp), where a slightly warmer register reads better. This is derived once from Q10 and applied at §1.1 Step 3 `update_ai_agent.jobConfig.temperature` (§1.2 no longer re-sets it — see §1.2). (Previously `0.5` was documented but never wired; it is now.)

---

## MCP tool split

**NiCE_Cognigy_MCP_Server** — high-level creation + packaging:

- `create_ai_agent` — project + agent + stub flow + REST endpoint in one call
- `create_tool` — aiAgentJobTool + `aiAgentToolAnswer` pair, auto-wired (Cognigy UI calls the answer node "Resolve Tool Action" / "Resolve Tool Answer" — same node). **Alternative path only.** The canonical tool-authoring call is cognigy-vibe `push_agent_tool` (file-first — §1.3). Use `create_tool` only for a quick one-call tool needing no visibility `condition`; it builds a *different* skeleton (auto-pairs the answer node, wrapped/stringified arg shape) — do NOT mix the two recipes in one branch.
- `manage_flow_nodes` — **fallback only.** Supports `say`, `question`, `ifThenElse`, `lookup`, `setSessionContext`, `code`, `goTo`, `sleep`, `httpRequest`. This skill uses cognigy-vibe `cognigy_create` for all flow-node creation (init chain AND tool branches) because it covers more node types (`once`, `setSessionConfig`, `wait`, `hangup`, AI-agent nodes) and gives uniform `mode: "append"` semantics. Use `manage_flow_nodes` only if cognigy-vibe is unavailable AND the node type is one of the 9 listed above.
- `list_resources`, `delete_resource`, `update_tool` — discovery + cleanup
- `manage_packages` — package zip export (backup artifact — see §1.6)
- `manage_knowledge` — knowledge-store wiring (used in §1.8 if `cognigy_invoke inject` doesn't fit)

**cognigy-vibe** — full resource + file-push surface:

| Tool | What it does |
|---|---|
| `cognigy_get` | GET any resource, cache-first |
| `cognigy_list` | List resources. `resource_type` accepts both singular (`flow`) and plural (`flows`) — the server normalises common singulars. Prefer plural to match the Cognigy API directly. See §7 cheatsheet. |
| `cognigy_create` | POST resource; extension auto-injected, Say config auto-normalised. Required for node types NiCE doesn't support: `once`, `onFirstExecution`, `afterwards`, `setSessionConfig`, `wait`, `hangup` |
| `cognigy_update` | PATCH with always-fresh GET + optional deep merge — use `merge_config: true` and patch deltas only |
| `cognigy_delete` | DELETE any resource including nodes — use for §8 collision cleanup |
| `cognigy_invoke` | Named operations: **move, clone, train, inject, search** — fork lane (§1.0), knowledge wiring (§1.8), asset discovery |
| `get_flow_chart` | Chart with relations array + readable hierarchy string — primary source for as-built (§1.6) |
| `push_code_node` | Push local `.js`/`.ts` to a Code node with conflict detection. **v1.4.0:** also CREATEs+positions the node in one call when `node_id` is omitted (`mode`+`target` provided) |
| `push_html_node` | Push local `.html` to a `setHTMLAppState` node — xApp moments (§1.4b) |
| `push_agent_tool` | Read a local `.tool.json` → create/update an `aiAgentJobTool` node — **canonical tool-authoring path (§1.3)** (plugin ≥ 1.4.2). CREATE: pass `job_node_id` (the parent `aiAgentJob` node); UPDATE: pass `node_id`. No `aiAgentId`. Creates ONLY the tool node — append `aiAgentToolAnswer` yourself (§6 Step 4). `cognigy_create` is blocked for `aiAgentJobTool` and redirects here. |

**Rule of thumb:** if `manage_flow_nodes` rejects a `nodeType` with "supported types" error, switch to `cognigy_create` with the right `extension`. Prefer the `push_*` family for any node body or tool definition you want version-controlled in the demo folder.

---

## §1 — Build sequence

**Inputs (all must exist in `Demo Builds/<customer>-demo/` before §1 starts):**
- `brand-research.md` (from §0.6)
- `{Customer}-{DemoType}-demo-plan.md` (from §A)
- `{Customer}-agent-persona.md` (from §B) — **four H2 sections** per §2 ladder: `## Persona`, `## Special Instructions`, `## Job Description`, `## Job Instructions`. §2.5 empathy library verbatim inside `## Job Instructions`.
- `{Customer}-agent-architecture.md` + `{Customer}-context-schema.md` (from §B)
- `{Customer}-agent-interfaces.md` (from §B)
- `{Customer}-agent-contracts.md` (from §B)

§1 reads these artifacts as the spec. The §0 interview answers are no longer the direct source — they were already consumed by §A and §B and crystallised into the design docs. If you find yourself reaching back to the interview for a build value, read the design doc instead.

### 1.1 Create project + agent + flow + endpoint (NiCE MCP)

**Source:** persona content comes **verbatim** from `{Customer}-agent-persona.md`, extracted by H2 heading per the four-layer ladder defined in §2. The caller-profile context (the Job Node's `memoryContextInjection`, set in §1.2) comes from `{Customer}-context-schema.md` (industry-shaped per §3).

**Extraction rule (per §2 — each block to its OWN field, NOT concatenated):**
- agent `description` = `## Persona` block (1A) — **≤ 1000 chars**
- agent `instructions` = `## Special Instructions` block (1B) — **≤ 1000 chars**; set at the AGENT level via `update_ai_agent` (see the note after the call — `create_ai_agent` does not accept it)
- `jobDescription` = `## Job Description` block (2A, H2 stripped) — set via `update_ai_agent.jobConfig` (§1.1 Step 3)
- `jobInstructions` = `## Job Instructions` block (2B, H2 stripped, §2.5 empathy library verbatim) — set via `update_ai_agent.jobConfig` (§1.1 Step 3)

**🔴 Pre-flight character gate (BLOCKING).** Before the agent-creation calls, count the characters of BOTH the `## Persona` block and the `## Special Instructions` block. If EITHER exceeds **1000**, condense it (the persona sub-skill should already keep both under budget — see §2) and re-count. Do NOT make the call with an over-length field — Cognigy throws a save error the agent silently survives, and reconciling that mid-build is exactly the friction this gate removes.

**The agent-creation surface is two NiCE calls, not one.** `create_ai_agent` accepts ONLY `{ name, description, projectId?, knowledgeStoreReferenceId? }` — every other field (job fields, LLM, temperature, locale) is set by `update_ai_agent` or a §1.2 node patch. Build it in three steps.

**Step 1 — create project + agent (`create_ai_agent`).** With `projectId` omitted the tool auto-creates a project **named after the agent `name`**, so `name` carries the PROJECT name here; the agent is renamed to the persona in Step 3.

```
create_ai_agent {
  name: "<Customer>_Demo_BH",
  description: "<## Persona block (1A) ONLY — ≤1000 chars, brand voice included, NO Special Instructions concatenated>"
}
```

Returns: `projectId`, `agent.id`, `agent.referenceId`, `flow.id` (mongo), `flow.referenceId`, `endpoint.URLToken`, `endpoint.endpointUrl`, `llmStatus`. **Capture all IDs immediately.**

> ⚠️ Returned `endpointUrl` uses host `cognigy-api-au1.nicecxone.com` — that 401s. Use `cognigy-endpoint-au1.nicecxone.com/<same token>` in the as-built doc.

**Step 2 — LLM gate (per `read_guide { guideId: "agent-creation" }`).** A freshly auto-created project may report `llmStatus: "unknown"`. Before assigning the LLM in Step 3, ensure the project has a working LLM with a non-empty `connectionId` — reuse another project's via `manage_packages` export/import, or `setup_llm`. Do not `talk_to_agent` until a working LLM is confirmed.

**Step 3 — rename agent + set ALL remaining fields (`update_ai_agent`).** This one call writes BOTH the agent resource AND the AI Agent Job Node, so the persona-rename, agent guardrails (1B), and every job field belong here. It is a NiCE tool, so it runs in the SAME session as Step 1 — before the §1.1.5 restart.

```
update_ai_agent {
  aiAgentId: "<agent.id>",
  name: "<personaName from persona.md>",        // renames the AGENT; project keeps <Customer>_Demo_BH
  instructions: "<## Special Instructions block (1B) — ≤ 1000 chars>",
  jobConfig: {
    jobName: "<Customer> Concierge — <Persona>",
    jobDescription: "<## Job Description block (2A) from {Customer}-agent-persona.md>",
    jobInstructions: "<## Job Instructions block (2B) — INCLUDING the §2.5 empathy library verbatim>",
    llmProviderReferenceId: "<referenceId of an LLM present in THIS project — see Step 2; NiCE AU1 demo-tenant default is a793f9ea-befd-4fdf-8be8-b1c8a8385a91>",
    temperature: 0.2,        // voice/transactional default; 0.5 only if Q10 channel mix is primarily conversational chat (webchat/WhatsApp) — see Default build values
    maxTokens: 400
  }
}
```

The pre-flight ≤1000 gate (above) must have passed for BOTH `description` (Step 1) and `instructions` (Step 3) first. The agent `instructions` field (1B) is distinct from the job-node `jobInstructions` (2B) — different levels, both set in this one call.

> **🔴 LLM gate is not optional (verified live).** The hardcoded `llmProviderReferenceId` is **silently accepted** even when the auto-created project has NO LLM model — the agent then `talk_to_agent`s to **empty output** (no error). LLM connections are project-scoped: the referenceId must point to an LLM that actually exists in THIS project. If Step 2 found no reusable LLM, import one via `manage_packages` (export the llm_model + its connection from a project that has one, then import) BEFORE relying on generation. Confirm with one `talk_to_agent` turn.
> **Always bundle `jobConfig` (or another job field) with a `name` change.** A *name-only* `update_ai_agent` returns a misleading `404 "node to update does not exist for the specified locale"` even though the agent rename commits — because the job-node patch has nothing to write. The Step 3 call above already bundles `jobConfig`, so it is safe; never issue a bare `update_ai_agent { aiAgentId, name }`.

> **`locale: en-AU` has no home in either agent tool.** It is dropped at create-time; confirm it is fully carried by the §1.5(c) Set Session Config / endpoint locale. Dropping it at the agent level is harmless as long as §1.5(c) sets it.

> If §1.0 fork lane ran instead, skip §1.1 and proceed to §1.1.5 against the cloned agent (use the cloned `projectId`).

### 1.1.5 — Bind cognigy-vibe to the new project

§1.2 onwards uses the `cognigy-vibe` MCP server. How you reach it depends on how `cognigy-vibe` is registered — check this first.

**Primary path (no restart) — workspace `.env` + projectless server.** When this plugin is installed, it registers `cognigy-vibe` at **plugin level** (`uvx cognigy-vibe-mcp`, no `COGNIGY_PROJECT_ID`), so the server boots project-agnostic at session start and reads `COGNIGY_BASE_URL` / `COGNIGY_API_KEY` from the `.env` at the session's launch directory — the `Demo Builds` workspace root that `cognigy:init-cognigy-vibe` wrote (§0.0). In this (now-standard) setup there is **no `.claude/mcp.json` per project and no restart**:

1. Confirm `cognigy-vibe` is live: `cognigy_list { resource_type: "projects" }` should succeed (credentials resolved from the workspace `.env`).
2. Bind the new project in-session: `sync_remote_state({ project_id: "<projectId from §1.1>" })`.
3. Proceed straight to §1.2 in the **same session**.

If step 1 fails with a "not loaded" / missing-credentials error, the workspace `.env` wasn't found (session launched outside the `Demo Builds` tree, or setup not run) — fix that (re-run `cognigy:init-cognigy-vibe`, or relaunch the session in the workspace root) rather than falling back to the restart path.

**Fallback path (legacy, per-project + restart) — delegate to `cognigy:init-mcp`.** Only when `cognigy-vibe` is **not** registered projectless (e.g. an older setup that pins `COGNIGY_PROJECT_ID` per project in `.claude/mcp.json`). The projectId only exists after §1.1, the server reads it at session start, and MCP servers can't hot-load mid-session — so a restart is required:

**Steps:**

1. **Delegate to `cognigy:init-mcp`** with the `projectId` returned by `create_ai_agent` in §1.1. Run it from the customer demo folder (e.g. `acenda-demo/`), NOT from the parent `Demo Builds/`. The sub-skill will:
   - Create `~/.config/cognigy-mcp/<projectId>/` with a `.state-seed.json`
   - Create `.cognigy-mcp` symlink in the customer folder
   - Add `.cognigy-mcp` to `.gitignore`
   - Write the `cognigy-vibe` entry to `.claude/mcp.json` in the customer folder (env: `COGNIGY_BASE_URL`, `COGNIGY_API_KEY`, `COGNIGY_PROJECT_ID`)

2. **Save build state to disk** before stopping. Write `_build-state.json` in the customer folder capturing every ID returned by §1.1 (`projectId`, `agentId`, `flowId`, `endpointId`, `endpointToken`, `aiAgentJobNodeId` once found) plus a one-line "resume at §1.2" marker. The post-restart session reads this instead of re-scraping.

3. **Hand back to the user with explicit restart instructions.** Stop the build cleanly here. Output a block like:

   > **Build paused at §1.1.5 — Claude Code restart required.**
   > Project created: `<projectId>` — saved to `_build-state.json`.
   > To resume:
   > 1. Quit Claude Code in this folder (Cmd-Q the window or `:q` the CLI).
   > 2. Re-open Claude Code in `<customer>-demo/`.
   > 3. Say: *"resume Cognigy build for `<customer>` from §1.2"* — the orchestrator will reload, read `_build-state.json`, and continue.

4. **On resume**, the orchestrator's first action in the new session is: confirm `cognigy-vibe` is loaded (call `cognigy_list { resource_type: "projects" }` — should succeed), then call `sync_remote_state({ project_id: "<projectId>" })` as documented in the `cognigy:init-mcp` skill output. Proceed to §1.2.

**Do not attempt to continue §1.2 in the same session as §1.1.** The `cognigy_*` tools will not exist yet — the restart is structural, not optional.

> **The two paths above are a fork, not a sequence.** With this plugin's default projectless `cognigy-vibe` registration + a workspace `.env` (the `cognigy:init-cognigy-vibe` setup), take the **primary no-restart path**: `sync_remote_state` binds the new project in-session and the build continues uninterrupted. Only drop to the fallback (per-project `init-mcp` + restart) when `cognigy-vibe` is registered the legacy way with `COGNIGY_PROJECT_ID` pinned per project. Do not pay the restart cost when the primary path is available.

### 1.2 Patch the Job Node — the two fields `update_ai_agent` can't reach (cognigy-vibe)

§1.1 Step 3 (`update_ai_agent`) already set the job name / description / instructions / LLM / temperature / maxTokens on the AI Agent Job Node. **Two Job-Node config fields are NOT in `update_ai_agent`'s schema** and must be patched directly on the node here: `memoryContextInjection` (caller-profile context injection) and `toolChoice`. Without them the agent has no caller-profile context and no explicit tool-choice mode.

**This step is mandatory.** Without it the agent loses caller context mid-conversation.

Find the AI Agent Job Node ID:
```
get_flow_chart { flow_id: "<flow.id from §1.1>" }
→ find node with type: "aiAgentJob" → grab its _id
```

Patch ONLY the two unreachable fields. `cognigy_update` does an always-fresh GET + deep merge, so `merge_config: true` preserves the jobConfig fields §1.1 Step 3 set:

```
cognigy_update {
  resource_type: "node",
  flow_id: "<flowId>",
  resource_id: "<aiAgentJobNodeId>",
  merge_config: true,
  body: { config: {
    memoryContextInjection: "<from {Customer}-context-schema.md, industry-shaped per §3, with {{context.customer.*}} placeholders>",
    toolChoice: "auto"
  }}
}
```

> **Warning:** if the agent suddenly stops responding mid-build, re-check `llmProviderReferenceId` (set in §1.1 Step 3) — it can revert to the project's `isDefault` LLM when the project's LLM list is touched. Re-run §1.1 Step 3's `update_ai_agent` if so.

> Verify by `cognigy_get` on the same node: confirm `memoryContextInjection` + `toolChoice` are set AND the §1.1 Step 3 fields (`name` / `description` / `llmProviderReferenceId` / `temperature`) are still your values, not defaults.

### 1.3 Author tools as `.tool.json` files, then push (cognigy-vibe `push_agent_tool`)

**Canonical path: file-first.** Author each tool definition as a `.tool.json` file under `Demo Builds/<customer>-demo/tools/`, then push via `push_agent_tool` (plugin ≥ 1.4.2). The benefits: tools are version-controlled in the demo folder, re-runs are idempotent (CREATE with `job_node_id`; re-push the same file with `node_id` to UPDATE — additive PATCH on config), and the user can hand-edit a `.tool.json` between iterations without re-running the whole build. **`push_agent_tool` creates ONLY the `aiAgentJobTool` node** — the `aiAgentToolAnswer` terminal is an explicit final append (§6 Step 4), NOT auto-paired. (`push_agent_tool` serialises `parameters` to the string Cognigy needs, auto-derives `useParameters`, and sets `debugMessage: true` — so the file holds a real JSON object, see below.)

**Sources for tool list:**
- Use-case tools — from `{Customer}-agent-architecture.md` (the Specialist table — each tool listed under each specialist)
- Tool descriptions — read each tool's compliance/contract text from `{Customer}-agent-architecture.md` and `{Customer}-agent-contracts.md`; let these inform the LLM-facing `description` (when to use, when NOT, what it returns)
- Transfer tools — **derived in this skill (see "Transfer-tool derivation" below)** from use cases. `transfer_to_care` + `transfer_to_general` always present.
- End-call pair — always built (see §5).

**`.tool.json` file shape** — `Demo Builds/<customer>-demo/tools/<tool_id>.tool.json` (per plugin `explain("agent-tool-json")`):

```json
{
  "toolId": "<snake_case_id>",
  "label": "<display_name>",
  "description": "<one-paragraph LLM-facing: when to use, when NOT to use, what it returns. Include compliance contract text from contracts.md where applicable.>",
  "parameters": {
    "type": "object",
    "properties": { "reason": { "type": "string", "description": "..." } },
    "required": ["reason"],
    "additionalProperties": false
  },
  "condition": "context.shortTermMemory.authVerified"
}
```

Top-level object — do NOT wrap in `config`, do NOT set `name`/`toolType`/`useParameters`/`debugMessage` (those are the `create_tool` arg shape — different path, see below). `parameters` is a **real JSON Schema object** (NOT stringified — `push_agent_tool` stringifies it for you); `additionalProperties: false` is recommended. **Omit `parameters` entirely** for param-free tools (`end_call`, `end_call_resolved`, transfers). `label` is optional (defaults to `toolId`). `condition` is **optional** — see the conditioned-tool note below; omit it for always-visible tools.

> **Tool-description authoring convention (3A — drives LLM tool selection).** Structure each tool's `description` in this order so the LLM picks and calls it correctly: (1) **WHEN to use** (the trigger intents) and when NOT to; (2) **WHAT it does / returns**; (3) **parameters** — for each, state **required vs optional first**, then its **format/type** and any value constraints. Put genuinely-required params in the schema's top-level `"required": [...]` array. *Caveat:* the schema models `type`/format and the `required` array, but does NOT enforce per-parameter ordering or a required-first layout — so the ordering is a doc-quality convention for the LLM's benefit, not a platform-enforced field. (Tool execution — 3B — lives in the branch nodes, §6; there is no execution-description field to author.)

**Push each tool** (use ABSOLUTE paths — `tool_file` is resolved as given):
```
push_agent_tool {
  tool_file: "<ABS PATH>/Demo Builds/<customer>-demo/tools/<tool_id>.tool.json",
  flow_id:   "<flowId>",
  job_node_id: "<aiAgentJobNodeId>"      // CREATE; to UPDATE an existing tool node pass node_id: "<toolNodeId>" instead
}
→ returns { success, node_id, created | updated }   // node_id = the new aiAgentJobTool node
```

Capture **`node_id`** (the `aiAgentJobTool` node `_id`) for each — needed for §1.4 / §6 branch authoring. `job_node_id` (the parent `aiAgentJob` node) comes from `get_flow_chart`. There is NO `resolveNodeId` in the return — the `aiAgentToolAnswer` node does not exist until you append it (§6 Step 4).

> **Verify-after-push: sync first (verified live).** Immediately after a CREATE/UPDATE push, a `cognigy_get` on the node can return a **stale cached** copy (`_source: "cache"`) — the push succeeded but the local cache lags. Call `sync_remote_state { project_id }` (or trust the push return) before reading back a just-pushed node to confirm a change. The push itself is authoritative; only the read cache lags.

> **Naming note:** the terminal **`aiAgentToolAnswer`** node (Cognigy UI label "Resolve Tool Action" / "Resolve Tool Answer") is the plugin's canonical end of a tool branch. With `push_agent_tool` it is NOT auto-created — you append it last via `cognigy_create` (§6 Step 4). See plugin `explain("agent-tool-branch")` for the three-node shape.

> **Conditioned / guard tools (visibility `condition`).** To hide a tool from the LLM until a guard state is met (e.g. `authenticate_caller` shown only while `!context.shortTermMemory.authVerified`, or a contract-staged tool — §9 / `{Customer}-agent-contracts.md`), set the optional top-level **`condition`** field in the `.tool.json`; `push_agent_tool` maps it into the node's `config.condition` for you. Use `context.shortTermMemory.*` (LLM-visible) or `context.contracts.*` / `context.ami.*` (enforcement-only) per `explain("tool-conditions")`. **Manual change after the fact:** `cognigy_update { resource_type:"node", resource_id:"<toolNodeId>", merge_config:true, body:{ config:{ condition:"..." } } }` — `condition` lives **inside `config`**; sending it top-level returns HTTP 400.

**Alternative path (NiCE `create_tool`) — only for a quick conditionless tool.** `create_tool` builds a *different* skeleton: it **auto-pairs** the `aiAgentToolAnswer` node in one call and takes the **wrapped/stringified** arg shape (`{ name, toolType, config:{ toolId, description, parameters:"<stringified JSON>" } }`). It always *creates* (not create-or-update) and cannot set a `condition`. Use it only when you want the one-call auto-pair and the tool needs no `condition` — and do NOT mix its recipe with the `push_agent_tool` branch recipe (§6) in the same branch. If you use it, still write the equivalent `.tool.json` to disk so the demo folder stays the SSOT — the §1.6 cross-check (the `FLOW_INSERTS.md` tool-coverage item — "All `tools/*.json` for every tool wired into the agent") reads these files.

> The `aiAgentJobTool` node label defaults to `toolId` (snake_case) when the optional `label` is omitted. Set `label` in the `.tool.json` for a friendlier UI display name.

**Tools to create on every build** (in addition to use-case tools):

| Tool | Purpose |
|---|---|
| `verify_caller` | CRM-by-phone refresh. Called when `context.customer.*` is undefined. (Init Session pre-loads, so this is mostly fallback.) |
| (derived transfers) | See "Transfer-tool derivation" below — generated from use cases, not hardcoded. |
| `transfer_to_care` | **ALWAYS BUILT** — non-negotiable. Destination for sensitive-topic empathy routing (§2.5). Even if no use case explicitly maps to Care, this tool must exist. |
| `transfer_to_general` | **ALWAYS BUILT** — fallback for out-of-scope intents the LLM can't otherwise route. |
| `end_call` | Closes call after `transfer_to_*` or out-of-scope intent. See §5. |
| `end_call_resolved` | Closes call after the AI Agent resolves the enquiry in-bot. See §5. |

Plus all the customer-specific use-case tools listed in `{Customer}-agent-architecture.md` (sourced from interview Q6 via §B design-agent-jobs).

### Transfer-tool derivation (replaces hardcoded list)

**SSOT — this section is the single home for the derived transfer-tool list and the domain terms taken from it.** §0's recap, §B's routing tree, and §1.5(c)'s `sttHints` all *consume* from here; none of them re-derive it. (Per §B: "Transfer-tool derivation stays in this skill (§1.3).") Derive once, here, at build time; everything else reads the result.

After the interview, derive the transfer tool set from the use cases. Do NOT default to the old `billing/sales/care/general` list — derive what's actually needed.

**Derivation rules:**

1. Group use cases by destination team. One transfer tool per distinct team. Use the customer's actual team names when known from §0.6 brand research; otherwise use sensible defaults.

2. **Always include** `transfer_to_care` (sensitive-topic destination — §2.5) and `transfer_to_general` (out-of-scope fallback).

3. **Each transfer tool's LLM-facing `description` must name the team AND list the trigger intents specifically.** Vague descriptions cause mis-routing.

**Examples by industry / use-case:**

| Use case intent | Derived transfer tool | Description (LLM-facing) |
|---|---|---|
| Roadside breakdown, flat tyre, locked out | `transfer_to_roadside_assist` | "Routes to the Roadside Assist dispatch team. Use for: breakdown, flat tyre, locked-out-of-car, won't-start, accident-at-roadside." |
| New claim, claim status, claim dispute | `transfer_to_claims` | "Routes to the Claims team. Use for: lodging a new claim, complex claim queries, claim escalations, repairer disputes." |
| Fraud, suspicious transaction, scam | `transfer_to_fraud_team` | "Routes to the Fraud team. Use for: reported fraud, suspicious transactions, scam-related queries. Stop-loss priority." |
| New product, quote, upgrade | `transfer_to_sales` | "Routes to Sales. Use for: new policy / new line, quotes, plan upgrades, adding cover." |
| Billing dispute, refund, direct debit, payment plan | `transfer_to_billing` | "Routes to the Billing team. Use for: billing disputes, refund requests, direct debit setup/change, payment plans, premium queries." |
| Complaint (formal) | `transfer_to_complaints` | "Routes to the Complaints team. Use for: any explicit complaint or expressed dissatisfaction the bot cannot resolve." |
| Mobile network / signal / outage | `transfer_to_technical_support` | "Routes to Technical Support. Use for: signal issues, outages, device problems, service quality complaints." |
| Lending / credit / loan enquiry | `transfer_to_lending` | "Routes to the Lending team. Use for: loan enquiries, credit applications, redraw, rate queries." |
| Account closure, retention | `transfer_to_retention` | "Routes to the Retention team. Use for: explicit cancellation requests or strong intent to leave." |
| Sensitive topics (bereavement, hardship, mental health, FV, suicide, serious illness) | `transfer_to_care` | "Routes to the Care team. Use for ANY sensitive disclosure per the empathy library (§2.5). See jobInstructions for full trigger list." |
| Anything not handled by another transfer | `transfer_to_general` | "Out-of-scope fallback. Use ONLY when no other transfer tool fits. The general team will route the call." |

**Process at build time:**

1. **Pre-design (before §A/§B):** parse the use-case list directly from the **interview Q6 answers** — the derivation runs at the pre-design confirm gate (§0), so it cannot depend on §B's `{Customer}-agent-architecture.md` (which doesn't exist yet). Q6 is the seed; §B later *consumes* this derived set, it does not produce it.
2. Map each use case to a likely transfer destination using the table above (and brand-research team names where available).
3. Build the derived set: **derived transfers ∪ `{transfer_to_care, transfer_to_general}`**.
4. **Show the derived list at the §0 pre-design confirm gate** (and again, as-confirmed, in the final recap). The user can rename / add / remove at the gate before the design run; the confirmed set is what §A/§B and the sttHints (§1.5c) consume.
5. Build only the approved set in §1.3 — author each tool's JSON file under `tools/`, then push (see §6 / §1.3 authoring path).

> **Hard rule:** No build ships with `transfer_to_general` as the ONLY transfer for a sensitive disclosure — `transfer_to_care` must always be the destination for empathy-routed calls. If the LLM picks `transfer_to_general` after a bereavement disclosure, the persona is mis-instructed; fix §2.5 wiring.

### 1.4 Tool-branch shapes (build recipe is §6)

**Canonical branch shapes — pick one per tool:**

Transactional (Shape B — most common):
```
[aiAgentJobTool: <tool_id>]                     ← from §1.3 push_agent_tool (tool node only)
  └── [Say: "Filler — <verb>"]                  ← §C.1 — voice dead-air handling
        └── [Code: "<Action> <Domain>"]         ← §C.2 — context.toolResponse = {...}; api.resolve();
              └── [aiAgentToolAnswer]            ← appended LAST (§6 Step 4) — NOT auto-paired
```

Transfer (reversed — Code first, so transfer commits to state before the spoken hand-off):
```
[aiAgentJobTool: transfer_to_<team>]
  └── [Code: "Mark transfer — <team>"]         ← context.toolResponse = { transferred: true, team: "..." }; api.resolve();
        └── [Say: "Say — transferring to <team>"]  ← "Right, putting you through to our <team> team now."
              └── [aiAgentToolAnswer]
```

End-call (full spec in §5). The two end-call tools have **different** shapes. `end_call` does NOT speak — the transfer tool's own branch Say already announced the hand-off, so `end_call` re-announcing would double up. It goes straight to Hangup. `end_call_resolved` is the only spoken close on the resolved path, so it keeps its goodbye Say:
```
[aiAgentJobTool: end_call]                       ← always follows a transfer_to_* (which already spoke the hand-off)
  └── [Hangup: voicegateway2]                    ← NO Say — single announcement lives in the transfer branch
        └── [aiAgentToolAnswer]

[aiAgentJobTool: end_call_resolved]
  └── [Say: resolved goodbye line]
        └── [Hangup: voicegateway2]
              └── [aiAgentToolAnswer]
```

**Why the Filler Say (transactional):** the plugin's canonical `agent-tool-branch` is `aiAgentJobTool → Code → aiAgentToolAnswer` (three nodes). This skill adds an explicit Filler Say between the tool node and Code — non-canonical but deliberate, because voice channels otherwise produce 0.5–2s of audible dead air during the Code mock. The Filler Say is the only authorised deviation, justified by voice UX. See plugin `explain("agent-tool-branch")`.

**Insertion rule (applies to all three shapes):** use plugin-canonical `mode: "append"` + `target: "<previousNodeId>"` per `explain("node-positioning")`. `append` inserts the new node AFTER target with the chain auto-rewired. **Do NOT use `insertAfter`** — broken on AU1 (returns 500). Extension is auto-injected for `@cognigy/basic-nodes` (AI Agent nodes) / `cxone-utils` / `@cognigy/voicegateway2`.

**Build steps:** see §6 for the per-shape step-by-step recipe (which node type to append first, what to push via `push_code_node`, how the `aiAgentToolAnswer` terminal is appended last in Step 4 — it is NOT auto-paired). Do not re-derive the steps here — §6 is the single source.

### 1.4b xApp HTML moments — conditional-push pattern

**Only runs if `{Customer}-agent-interfaces.md` names xApp scenes.** Skip otherwise — most voice-only builds have no xApp content.

**Recommended pattern: conditional push via `if` gate** (per plugin `explain("xapp-delivery")`). One `setHTMLAppState` node lives per scene type, gated behind an `if` node (type `"if"`, NOT `"ifThenElse"`) that checks a `context.xappTrigger` flag. Tool branches that fire that scene set the flag in their Code mock; tool branches that don't, leave the flag false. This avoids redundant `setHTMLAppState` nodes propagated through every tool branch.

**Why this pattern:** direct insertion of `setHTMLAppState` into every host tool branch produces multiple identical scene definitions across the flow — drifty, hard to maintain, and noisy when the scene HTML needs editing (have to track down every copy). Conditional push centralises one scene definition + lets many tool branches fire it.

**Layout:**

```
(somewhere in the main flow, after init chain, before AI Agent)
  └─ [Code: "Reset xApp triggers"]   // context.xappTrigger = false at session start
       └─ [if: context.xappTrigger === true]   // type "if", NOT "ifThenElse"
            ├─ true branch
            │    └─ [setHTMLAppState: "xApp — <scene_name>"]
            │         └─ [Code: "Clear xApp trigger"]  // context.xappTrigger = false
            └─ false branch (empty — fall through)
                 └─ [continues to AI Agent]
```

**Per scene, build steps:**

1. **Write the HTML body to disk** — `Demo Builds/<customer>-demo/xapp/<scene_name>.html`. Each interfaces-doc scene specifies content type (adaptive card, carousel, payment form, confirmation, map), data payload field names + sources, and customer-action behaviour. Translate that into the HTML body the `setHTMLAppState` node will render. Use CognigyScript interpolation for dynamic data — `{{context.<field>}}` and `{{input.aiAgent.toolArgs.<param>}}` both work in the HTML body (per plugin `explain("cognigyScript")`).

2. **Create the `if` + `setHTMLAppState` scaffold once** (idempotent). To detect an existing scaffold: call `get_flow_chart { flow_id: "<flowId>", format: "raw" }` and look for an `if` node whose condition references `context.xappTrigger`. Per plugin `explain("node-positioning")` (v1.4.0), an IF node auto-creates two **branch-marker** children in `childIds[]`: **`childIds[0]` = the Then (true) branch marker, `childIds[1]` = the Else marker.** Content inside a branch must be a **sibling appended after the marker** — `mode: "append"`, `target: <childIds[0]>` (the Then marker `_id`). Do NOT walk to a "true-branch tail" manually, and do NOT `appendChild` onto the marker (that nests inside it and breaks UI rendering). If the scaffold exists, append the new scene after the Then marker. If not, build from scratch — three calls (2a create IF node, 2b read its childIds, 2c create setHTMLAppState):
   ```
   // Step 2a — create the IF gate node
   cognigy_create {
     resource_type: "node",
     flow_id: "<flowId>",
     body: {
       type: "if",
       mode: "append",
       target: "<resetXappTriggersCodeNodeId>",
       label: "xApp trigger gate",
       config: { conditions: [{ type: "cognigyScript", condition: "context.xappTrigger === true" }] }
     }
   }
   → returns { _id: "<ifNodeId>" }

   // Step 2b — read the branch-marker IDs the IF node auto-created
   get_flow_chart { flow_id: "<flowId>", format: "raw" }
   // Find the node with _id === "<ifNodeId>"; read childIds[0] (Then branch marker)

   // Step 2c — create the setHTMLAppState node inside the Then branch
   cognigy_create {
     resource_type: "node",
     flow_id: "<flowId>",
     body: {
       type: "setHTMLAppState",
       mode: "append",
       target: "<ifNodeId.childIds[0] — the Then branch marker>",
       label: "xApp — <scene_name>",
       config: {}
     }
   }
   ```
   Extension is auto-injected (`@cognigy/basic-nodes` for `if`; `cxone-utils` for `setHTMLAppState`). **Do NOT use `insertAfter` / `insertBefore`** — broken on AU1 (return 500); `append` against the branch marker is the only reliable mode.

3. **Push the HTML body:**
   ```
   push_html_node {
     flow_id:   "<flowId>",
     node_id:   "<setHTMLAppStateNodeId>",
     html_file: "Demo Builds/<customer>-demo/xapp/<scene_name>.html"
   }
   ```

4. **Wire each host tool branch's Code mock** to set the trigger before the tool-answer terminal:
   ```javascript
   // Inside the host tool's Code mock body (the standard Shape-B Code node):
   context.xappTrigger = true;
   context.xappScene = "<scene_name>";   // optional — for multi-scene flows, route inside ifThenElse
   context.toolResponse = { ...your tool result };
   api.resolve();
   ```

5. **Reset the trigger after the scene fires** — the Code node downstream of `setHTMLAppState` (in the `if` true branch) resets `context.xappTrigger = false` so subsequent turns don't re-fire.

**Fallback** (per interfaces-doc rule): if the channel doesn't support xApp (e.g. pure voice with no SMS link), the interfaces doc names a fallback (e.g. "spoken summary read by the agent"). Bake the fallback as a normal Say node in the host tool branch — do not push HTML for that scene.

**Cross-tool-branch reuse:** if two tools fire the same scene, both set `context.xappTrigger = true` — the single `setHTMLAppState` handles both. If two tools fire *different* scenes, route inside the `if` true branch using `context.xappScene` to pick which scene renders.

**Inbound xApp submits — the return path (per plugin `explain("xapp-event-handling")`).** Everything above *delivers* a scene; when the user acts inside the xApp (submits a form, taps a card) the result returns to the flow as an event. The submit payload arrives at **`input.data._cognigy._app.payload`**. Handle it with an `ifThenElse` near the top of the flow (before the AI Agent Job) that intercepts the submit, writes the result to `context.toolResponse`, and `api.resolve()`s into an `aiAgentToolAnswer` — the non-blocking two-turn async pattern (variant A = `sdk.submit()`; variant B = webhook inject). Do NOT re-derive the event shapes here — `explain("xapp-event-handling")` is the source. (This is the half the skill previously omitted: it covered delivery but not the return path.)

### §C.1 — Filler line library (pick one per tool, tone-match the persona)

- Lookup / verification: `"One moment, just pulling up your details."`
- Transactional commit: `"One moment, processing that for you now."`
- Search / query: `"Let me check that for you."`
- Mock external API: `"Just a moment while I check our records."`
- Long-running (>2s mock): `"Bear with me a second while I get that for you."`

### §C.2 — Tool result shapes — three shapes (mandatory)

Every tool branch terminates in an `aiAgentToolAnswer` node (the explicit final append — §6 Step 4; see §1.3 "Naming note"). The aiAgentToolAnswer surfaces the data the LLM sees on the next turn. The preceding Code node populates that data by writing to `context.toolResponse`. **The aiAgentToolAnswer node's `answer` field MUST be set to `{{JSON.stringify(context.toolResponse)}}` (§6 Step 4) — a bare `config: {}` returns an empty tool result and the LLM sees nothing back.** Plugin canon: see `explain("agent-tool-branch")` / `explain("agent-tool-patterns")` / `explain("code-node-patterns")`.

Three result shapes — pick one per tool branch:

**Shape 1 — Success (most common):**
```javascript
const <arg> = input.aiAgent.toolArgs.<arg>;  // read tool args if applicable

context.toolResponse = context.customer;  // or { receiptNumber, amount, ... } / { claimId, assessorWindow, ... } / etc.
api.resolve();
```
LLM reads `context.toolResponse` next turn and continues the conversation.

**Shape 2 — Conditional lookup (must be able to BOTH succeed AND no-match):**
```javascript
const lookupValue = input.aiAgent.toolArgs.value;

// Deterministic demo: succeed for the known-good value, no-match for anything else.
// A tool hardcoded to always return found:false can never demo the happy path — so branch.
if (lookupValue === "<known-good demo value — e.g. the caller's real id from §3>") {
  context.toolResponse = { found: true, ...context.customer };   // or the relevant success payload
} else {
  context.toolResponse = { found: false, reason: "no_match", searchedFor: lookupValue };
}
api.resolve();
```
Persona `jobInstructions` MUST include: *"If a lookup tool returns `found: false`, apologise and ask the caller to confirm the value. Do NOT retry the same tool with the same input."*

**Shape 3 — Multi-match / disambiguation needed:**
```javascript
context.toolResponse = {
  matches: [...],
  needsDisambiguation: true,
  prompt: "I found 2 accounts under that name — can you confirm the postcode?"
};
api.resolve();
```
Persona `jobInstructions` MUST include: *"If a tool returns `needsDisambiguation: true`, ask the user the `prompt` field. Do not fire tools until the user answers."*

**Error pattern (rare — for genuinely broken tools):**
```javascript
context.toolResponse = { error: true, message: "<safe message>", retryable: false };
api.reject("<terse error reason for logs>");
```
Use `api.reject()` only when the tool genuinely failed. Mock tools should almost never use this — prefer structured no-match (Shape 2) or disambiguation (Shape 3) via `api.resolve()`.

**Hard rules:**
- **Always call `api.resolve()`** (or `api.reject()` on genuine failure) — without it, the AI Agent Job Node hangs and the next user turn breaks. Code nodes inside tool branches are async; the chain only advances to `aiAgentToolAnswer` on resolve.
- **Always write the result to `context.toolResponse`** — NOT `input.result` (legacy convention; replaced by plugin-canonical `context.toolResponse`).
- **Build at least one tool with Shape 2 (no-match) per demo** to prove the persona's negative-path handling works.

Read/write conventions for tool-arg / context / `api.log` / `console.log` restrictions live in plugin `explain("code-node-patterns")` and `explain("agent-tool-branch")`; richer `api.say` output shapes (quick replies, buttons, gallery, adaptive cards) live in `explain("output-formats")` — call those for full details rather than duplicating here. (Confirmed: the canonical tool-result pattern is `context.toolResponse`; the legacy `api.addToInput` / `input.result` path is not used anywhere in this skill.)

### 1.5 Build the init chain (cognigy-vibe `cognigy_create`)

`manage_flow_nodes` does NOT support `once`, `onFirstExecution`, `afterwards`, `setSessionConfig`, `wait`, `hangup`. Use cognigy-vibe.

**Init chain — verbatim node sequence:**
```
Start
└─ Once
   └─ On First Time
      └─ Code "Initialize Session"           (loads context.customer per §3)
         └─ Set Session Config                (voice config — see §1.5(c) below)
            └─ Say "Welcome line"             (industry-specific greeting)
               └─ Wait for Input
   └─ Afterwards                              (leave empty — Once.next = AI Agent on subsequent turns)
└─ AI Agent
   └─ End
```

All `cognigy_create` calls below use the plugin-canonical form: `resource_type: "node"` + separate `flow_id` param + body. Extension is auto-injected for known node types (no need to spell `extension: "@cognigy/voicegateway2"` etc — kept in examples for explicitness where it helps the reader).

**(a) Once** — between Start and AI Agent:
```
cognigy_create {
  resource_type: "node",
  flow_id: "<flowId>",
  body: { type: "once", mode: "append", target: "<startNodeId>", label: "Once", config: {} }
}
```
> `<startNodeId>` is NOT returned by `create_ai_agent`. Fetch it via `get_flow_chart { flow_id: "<flowId>" }` and find the node with `type: "start"` (it's the root of the chart). Capture its `_id` before this step.

Auto-creates `onFirstExecution` + `afterwards` children. Get their IDs via `get_flow_chart` after this call.

**(b) Initialize Session — Code node** inside On First Time. As of cognigy-vibe **v1.4.0**, `push_code_node` **creates and positions the Code node in one call** — omit `node_id` and pass `mode` + `target` + `label`. The old two-step (empty `cognigy_create` → `push_code_node`) is no longer needed:
```
push_code_node {
  script_file: "Demo Builds/<customer>-demo/code-nodes/<customer>_initialize_session.js",   // canonical CRM template, industry-shaped — §3
  flow_id: "<flowId>",
  mode: "append",
  target: "<onFirstExecutionId>",
  label: "Initialize Session"
  // node_id omitted → CREATE mode (creates + positions + pushes body in one call)
}
```

> **v1.4.0 change:** Code nodes no longer need the two-step `cognigy_create` (empty) → `push_code_node`. The single `push_code_node` CREATE call (omit `node_id`, provide `mode`+`target`) does both. To UPDATE an existing Code node instead, pass its `node_id` (conflict-detected). Required params: `script_file`, `flow_id`. See plugin `explain("code-node-patterns")`.

**(c) Set Session Config** (extension `@cognigy/voicegateway2` auto-injected):
```
cognigy_create {
  resource_type: "node",
  flow_id: "<flowId>",
  body: {
    type: "setSessionConfig",
    mode: "append",
    target: "<initializeSessionNodeId>",
    label: "Azure + 11Labs",
    config: {
      ttsVendor: "elevenlabs",
      ttsModel: "eleven_turbo_v2_5",
      ttsVoice: "kqVqVtE8vZVRm6uoad9t",
      ttsLanguage: "en",
      ttsLabel: "nexora_elevenlabs",
      sttVendor: "microsoft",
      sttLanguage: "en-AU",
      sttLabel: "nexora-azure-speech-services-australiaeast",
      sttHints: ["<Customer brand name>", "<Persona name>", "<domain term 1>", "<domain term 2>", "<domain term 3>"],
      bargeInMinWordCount: 2,
      bargeInOnSpeech: false,
      bargeInOnDtmf: false,
      userNoInputTimeoutEnable: true,
      userNoInputTimeout: 10000,
      userNoInputRetries: 5,
      userNoInputMode: "event"
    }
  }
}
```

> **`sttHints` — populate, never ship the placeholder.** This array MUST contain the customer brand name (§0.6 brand research), the persona name (Q4), and **≥3 domain terms** drawn from the derived tool set (§1.3 — the transfer / use-case tool names and their key nouns, e.g. `roadside`, `claim`, `premium`). These bias the recogniser toward the words this agent actually hears. **§1.3 is the single source for the domain terms** — read them from the derived tool list, do not invent a parallel list here. §1.7 Phase A assert #7 verifies exactly this, so an empty or placeholder `sttHints` fails the structural smoke test (this is the loop the old `["", "<Customer>", "<Persona>"]` template used to trip).

JSON form (what the node emits in the flow definition — for reference):
```json
{
  "synthesizer": { "vendor": "elevenlabs", "language": "en", "voice": "kqVqVtE8vZVRm6uoad9t", "label": "nexora_elevenlabs", "options": { "model_id": "eleven_turbo_v2_5" } },
  "recognizer": { "language": "en-AU", "label": "nexora-azure-speech-services-australiaeast", "vendor": "microsoft", "punctuation": true, "profanityOption": "raw", "vad": { "enable": false } },
  "bargeIn": { "enable": false, "actionHook": "voice", "dtmfBargein": false }
}
```

> **Voice silence / no-input fields** (`userNoInput*`) — the values above are the chosen demo defaults (10 s timeout, 5 retries, `event` mode). For what each field means and the `event`-mode reprompt-then-escalate pattern (re-enter on the `noUserInput` system intent, discriminate on `input.data.event === "USER_INPUT_TIMEOUT"`), see plugin `explain("voice-silence-timeout")` rather than re-deriving the semantics here.

**(d) Say Welcome** — `config.say.text` is a **plain string array** (one string per variant — NOT an array of `{type,content}` objects; objects render as `[object Object]`). The flat `config.text` form also works (the plugin auto-normalises either). Per plugin `explain("say-node")`. Note `generativeAI_customInputs` must be an **array** (`[]`), never an empty string:
```
cognigy_create {
  resource_type: "node",
  flow_id: "<flowId>",
  body: {
    type: "say",
    mode: "append",
    target: "<setSessionConfigNodeId>",
    label: "Say Welcome",
    config: {
      say: {
        type: "text",
        text: [
          "Welcome to <Customer>, {{context.customer.firstName}}. I can see you're signed in and your number on file ends in {{context.call.phoneMasked}}. How can I help today?",
          "Hi {{context.customer.firstName}} — you're already signed in, and your number on file ends in {{context.call.phoneMasked}}. What can I help you with?",
          "Welcome back to <Customer>, {{context.customer.firstName}}. I've got your account open here and your number ends in {{context.call.phoneMasked}}. What's on your mind today?"
        ],
        data: "", linear: false, loop: false
      },
      handoverOutput: "userAndAgent",
      preventTranscript: false,
      generativeAI_rephraseOutputMode: "none",
      generativeAI_amountOfLastUserInputs: 5,
      generativeAI_customInputs: [],
      generativeAI_temperature: 0.7
    }
  }
}
```
> Three variants — Cognigy randomly picks one. Tone: confident, no apologies in the opener.

**(e) Wait for Input** — terminator:
```
cognigy_create {
  resource_type: "node",
  flow_id: "<flowId>",
  body: { type: "wait", mode: "append", target: "<sayWelcomeNodeId>", label: "Wait for Input", config: {} }
}
```

**(f) Afterwards branch — leave empty.** Once routes to `Once.next` (= AI Agent) on subsequent turns automatically.

### 1.6 As-built + baseline (primary: `get_flow_chart`; backup: package zip)

**This step is mandatory.** It closes the most common rework gap: as-built docs that describe intent rather than what's deployed. The flow-chart is the source of truth; the doc reads it back.

The primary source of truth is now `get_flow_chart { format: "both" }`, which returns the live flow structure with a `nodes` array, a `relations` array, and a readable `hierarchy` string. The exported package zip is kept as a backup artifact (restore / handoff), not as the parser input.

After all build steps land:

1. **Read the live flow structure.**
   ```
   get_flow_chart { flow_id: "<flow.id>", format: "both" }
   → returns { nodes: [...], relations: [...], hierarchy: "..." }
   ```
   Pass `format: "both"` to get the node/relation arrays AND the readable hierarchy string in one call. (`format: "hierarchy"` — the default — returns only `{ hierarchy: "..." }`; `format: "raw"` returns only `{ nodes, relations }`.) This is the source of truth.

2. **Read each node's full config via `cognigy_get`** as needed for verbatim Code-body / Say-text capture. Iterate over `nodes` from step 1.

3. **Generate `[CUSTOMER]_FLOW_INSERTS.md`** from the hierarchy string + relations + per-node `cognigy_get` reads. Required sections:
   1. Architecture diagram (ASCII) — derived from `hierarchy`
   2. Demo run path — Cognigy Interaction Panel (primary) or VG webrtcDemoUrl
   3. Project / agent / endpoint IDs (from §1.1 / §1.0)
   4. LLM / TTS / STT / toolChoice settings (verbatim from the patched Job Node — `cognigy_get`)
   5. Persona (description, instructions, memoryContextInjection — verbatim from the patched Job Node)
   6. Init chain — Initialize Session Code body (verbatim), Set Session Config table, Say Welcome variants (verbatim)
   7. Tools — for each: source JSON path under `tools/`, description, parameters, Filler Say text, Code mock body, xApp scene reference (if any). Mark transfer / end-call / no-match patterns explicitly. **Include node IDs.**
   8. xApp scenes — for each: source HTML path under `xapp/`, host tool, data payload, fallback (if any)
   9. Knowledge wiring — present only if §1.8 ran; lists the Cognigy knowledge store + topics ingested + wiring mechanism (see §1.8)
   10. Demo run-through suggested script
   11. Known gaps / next steps (Voice Preview not configured; "knowledge not configured" only if §0.5 gate was NO; "smoke test partial" only if §1.7 auto-loop couldn't fix a failed assertion — list the specific failure)

4. **Generate `[customer]-baseline.md`** — drift-detection snapshot. Include the same data but with concrete node IDs, code-node bodies (full text), tool wiring, and Set Session Config JSON. Usable input for `nice-cognigy-health-check` and `nice-demo-decay-check`.

   > This `baseline.md` is a **local markdown drift artifact** for the audit skills — it is NOT a Cognigy resource snapshot. Cognigy also offers project-level resource *versioning* (a `snapshot` resource via `cognigy_create`, async job) — see plugin `explain("project-snapshots")` if you want a server-side restore point in addition to the package zip. Optional; the package zip in step 5 remains the canonical backup for this skill.

5. **Export the package zip as backup** (via NiCE `manage_packages`, two-call):

   **(a) List exportable resources:**
   ```
   manage_packages {
     operation: "list_exportable",
     projectId: "<projectId>"
   }
   ```

   **(b) Export to disk** (includeDependencies defaults true, but pass all top-level resource IDs to be safe):
   ```
   manage_packages {
     operation: "export",
     projectId: "<projectId>",
     resourceIds: ["<flowId>", "<agentId>", "<endpointId>", ...all from step (a)],
     name: "<Customer>_Demo_BH",
     outputPath: "<absolute path to Demo Builds/<customer>-demo/package/<customer>_Demo_BH.zip>",
     includeDependencies: true,
     waitForCompletion: true
   }
   ```
   This produces the `.zip` backup. No unzip step required — the as-built was already generated from `get_flow_chart` in step 3.

**Cross-check before hand-back.** Open the new `FLOW_INSERTS.md` and verify against the list below.

The bar is **high-quality production demos that reflect the use cases** — not just builds that run. Every BLOCKING item must be satisfied; missing any one means going back and fixing the flow before hand-back. CONDITIONAL items only check if their precondition holds.

**🔴 BLOCKING — must be satisfied before hand-back**

*Flow / runtime:*
- The `Once → Initialize Session → Set Session Config → Say Welcome → Wait` chain (by node ID)
- The exact Set Session Config defaults (ElevenLabs Custom `kqVqVtE8vZVRm6uoad9t`, `nexora_elevenlabs`, `nexora-azure-speech-services-australiaeast`, `en-AU`, bargeIn off, VAD off)
- At least one transactional tool with Shape-B (Filler Say → Code → aiAgentToolAnswer)
- At least one transfer tool with reversed pattern (Code → Say → aiAgentToolAnswer)
- Both `end_call` and `end_call_resolved` with Hangup before aiAgentToolAnswer
- At least one tool demonstrating no-match (Shape 2) handling — proves the persona's negative-path handling works

*Persona quality:*
- **Brand voice traceability** — the persona `description` references brand-voice descriptors that match `brand-research.md` (not generic "calm, capable, knowledgeable" boilerplate)
- **Derived transfer tools match the use cases** — e.g. roadside use case → `transfer_to_roadside_assist` exists (not collapsed into `transfer_to_general`)
- **`transfer_to_care` + `transfer_to_general` present unconditionally**
- **Persona ↔ tool-set parity** — the persona's `## Job Instructions` ROUTING DECISION TREE has one line per tool on the agent, and every tool on the agent has a routing-tree line. Drift causes the LLM to hallucinate calls to deleted tools or ignore real ones. If you added or removed a tool after the persona was authored (rare in fresh builds, common in fork builds and iterations), regenerate persona.md via `cognigy:design-agent-persona` and re-run §1.2.
- **§2.5 empathy library** verbatim in the patched Job Node's `instructions` field (sourced from `## Job Instructions` H2 in persona.md — layer d per §2 ladder) — all 7 trigger categories with templates, hard rules, and Lifeline 13 11 14 for suicide/self-harm
- **Agent free-text fields ≤ 1000 chars** — agent `description` (Persona/1A) and agent `instructions` (Special Instructions/1B) are EACH ≤ 1000 chars (verify via `cognigy_get`; this is §1.7 Phase A assert #12). Over-length silently errors on save and injects mid-build rework — this is the hard cap, not a guideline.

*Artifacts on disk in `Demo Builds/<customer>-demo/`:*
- All §B design docs: demo plan, persona, architecture, context-schema, interfaces, contracts
- All `tools/*.json` for every tool wired into the agent (file-first authoring per §1.3)
- `brand-research.md` and `<customer>-empathy-library.md`

**⚪ CONDITIONAL — only check if the precondition holds**

- **`xapp/*.html` files exist** for every xApp scene named in `{Customer}-agent-interfaces.md` — only check if interfaces.md named scenes. Skip if no scenes.
- **Knowledge wiring** — only if §0.5 returned `knowledgeRequested: true`. Knowledge store ID + topics ingested listed, wiring mechanism documented in §1.8 Step 3. Skip if §0.5 returned NO.

If any BLOCKING item is missing, the build is incomplete — go back and fix the flow before handing back. Do not soften the bar to ship faster; the cross-check exists because shipped-but-broken patterns are harder to debug than rework-before-handover. **§1.7 is the programmatic enforcer of this list — passing §1.6's paper check without §1.7's runtime check is how Acenda_Demo_BH (2026-06-10) shipped missing `Once`, `Set Session Config`, and `Wait` despite §1.5 spelling them out. Do not skip §1.7.**

### 1.7 Smoke test — runtime verification before hand-back (BLOCKING)

**Why this section exists.** §1.6's cross-check is a paper read against the doc the builder just wrote. A skipped step in §1.5 (e.g. forgetting `Once`, `Set Session Config`, or `Wait`) passes that paper check unnoticed if `FLOW_INSERTS.md` describes the *intent* rather than what's actually deployed. §1.7 closes that gap by reading the **live flow chart** and running the agent **end-to-end via `talk_to_agent`** before any hand-back. Two phases — both must pass (subject to the assertion-class rules below).

**Two assertion classes — this governs failure handling.** Every assertion below is one of two kinds, and they are handled differently:

- **DETERMINISTIC (structural) assertions** test something that is either wired or not: a node exists, a config field holds a value, a node fired at runtime, an interpolation resolved, a Hangup payload is present once an end-call tool fires. A correct build passes these every time. These are **hard gates** — on failure the orchestrator auto-loops back to the named §1.5 / §1.4 / §5 step, applies the canonical fix, and re-runs from the top. **All of Phase A is deterministic.** The structural-runtime checks in Phase B (Set Session Config fired, Welcome line rendered, Once gate held then released, `{{context.customer.firstName}}` resolved, filler-Say ordering when a tool fires, Hangup payload shape when an end-call tool fires) are also deterministic.
- **PROBABILISTIC (LLM-decision) assertions** test a *choice the model made* on a given turn: whether it chose to call a tool (`finishReason: "tool_calls"`), whether it routed to the expected tool, whether it chose to end the call. The LLM is non-deterministic, so a single run missing one of these is **not** proof of a broken build. These are **advisory warnings only**. On a miss: re-run the single turn once to rule out a one-off; if it still misses, **log an advisory warning**, capture the transcript, and surface it to the user in the §10 hand-back. **Do NOT** trigger destructive `cognigy:design-agent-persona` regeneration or a §1.2 re-patch on a probabilistic miss — auto-regenerating the persona on an LLM-decision assert is exactly the over-reaction this split removes.

**Failure handling (deterministic only).** On any failed **deterministic** assertion in Phase A or Phase B, the orchestrator does NOT halt and wait for the user. It loops back to the relevant §1.5 / §1.4 / §5 step, applies the fix using the canonical spec, then re-runs the smoke test from the top. The orchestrator is the builder; the user is not in the loop until §1.9. If two consecutive loops fail to fix the same deterministic assertion, surface to the user in the hand-back block (§10) under "smoke test partial" with the specific failure and proposed manual fix — don't silently ship. **Probabilistic** assertions never drive this loop; they are reported as advisory warnings per the class rules above.

#### Phase A — Structural verification (programmatic, against live `get_flow_chart`) — all DETERMINISTIC (hard gates)

1. **Read the live chart.**
   ```
   get_flow_chart { flow_id: "<flowId>", format: "raw" }
   ```
   Use `format: "raw"` here — Phase A walks node IDs and relation chains, not the human-readable hierarchy string.

2. **Assert init-chain and tool-branch shape.** Walk the chart and confirm each item below. Each failing assertion → loop back to the named §1.5 / §1.4 / §5 step, create the missing node per the canonical spec, then re-run Phase A from step 1. Do not proceed until every item is GREEN.

   | # | Assertion | If fails, loop back to |
   |---|---|---|
   | 1 | A `start` node exists; its `next` resolves to a `once` node | §1.5(a) Once |
   | 2 | The `once` node's `children` are `[onFirstExecution, afterwards]` (exact types, both present) | §1.5(a) Once — re-run; plugin auto-spawns these |
   | 3 | The `once` node's `next` resolves to a node of type `aiAgentJob` | §1.5(a) target — Once likely appended after the wrong node |
   | 4 | `onFirstExecution.next` chain = `code` (label contains "Initialize Session") → `setSessionConfig` → `say` (label contains "Welcome") → `wait` — exact order, no extras, no gaps | §1.5(b)–(e) — re-create the missing node(s) |
   | 5 | The Initialize Session `code` node has non-empty `config.code` AND its body assigns `context.customer` and `context.call` per §3 CRM template | §1.5(b) + `push_code_node` of the canonical CRM template |
   | 6 | `setSessionConfig.config` has `ttsVendor: "elevenlabs"`, `ttsVoice: "kqVqVtE8vZVRm6uoad9t"`, `sttVendor: "microsoft"`, `sttLanguage: "en-AU"` | §1.5(c) — patch the node's config |
   | 7 | `setSessionConfig.config.sttHints` is a non-empty array containing the customer brand name AND the persona name AND ≥3 domain terms derived from the agent's tools | §1.5(c) — populate sttHints |
   | 8 | Say Welcome `config.say.text` is an array of ≥2 variants, each containing `{{context.customer.firstName}}` | §1.5(d) — re-write the say config |
   | 9 | For every `aiAgentJobTool` child of the `aiAgentJob`, a well-formed branch exists per §1.4 (Shape B for transactional, reversed for transfers, end-call shape for end_call/end_call_resolved) | §1.4 / §6 — re-run the tool-branch build |
   | 10 | `end_call` and `end_call_resolved` tool branches both exist and both terminate with a `hangup` before the `aiAgentToolAnswer` | §5 — re-create the end-call pair |
   | 11 | `aiAgentJob.next` resolves to an `end` node | §1.1 — flow is incomplete |
   | 12 | **Agent free-text fields within the 1000-char cap** — via `cognigy_get` on the agent (`resource_type: "agents"`, not the flow chart), assert `description` (1A Persona) ≤ 1000 chars AND `instructions` (1B Special Instructions) ≤ 1000 chars. This is the structural backstop for the §1.1 pre-flight gate — it catches the case where an over-length field was *saved despite the platform error*, the exact silent-failure that injects mid-build uncertainty. | §1.1 / §2 — condense the over-length block (`## Persona` or `## Special Instructions`) and re-set the field |

   Print PASS/FAIL per assertion. On any FAIL: state which §1.5 / §1.4 / §5 step the orchestrator is looping back to, apply the fix, re-run Phase A from #1. Do not "carry on" with partial assertions failing.

#### Phase B — 3-turn runtime test (`talk_to_agent`)

Only run Phase B after Phase A is fully GREEN. Phase B catches LLM-level wiring issues (no LLM connected, persona drift, tool descriptions ambiguous) that structural checks can't see. Each assertion below is tagged **[deterministic]** (hard gate — auto-loop on failure) or **[advisory]** (LLM-decision — warn, don't auto-regenerate) per the two-class rules above.

1. **Get the REST endpoint URLToken.**
   ```
   cognigy_list { resource_type: "endpoints", project_id: "<projectId>" }
   ```
   Capture the `URLToken` from the REST endpoint (`channel: "rest"`).

2. **Generate fresh session identifiers** — defeats Cognigy's session cache:
   ```
   user_id    = "smoke-<YYYY-MM-DD-HHMM>-<random4>"
   session_id = "<user_id>-session"
   ```

3. **Turn 1 — first-turn branch.** Send `"hi"`:
   ```
   talk_to_agent {
     endpoint_token: "<URLToken>",
     message: "hi",
     user_id: "<user_id>",
     session_id: "<session_id>"
   }
   ```
   **Assert (all [deterministic]):**
   - [deterministic] `outputStack[0].data._cognigy._voiceGateway2.json` present → Set Session Config fired
   - [deterministic] Response `text` contains the caller's `firstName` from §3 (e.g. "Sarah") → Initialize Session ran and `{{context.customer.firstName}}` resolved
   - [deterministic] Response `text` is the Say Welcome line only — no LLM-generated content → AI Agent did not fire on turn 1 (Wait held)
   
   Any failure → loop back: re-run Phase A to locate the gap; the runtime didn't fire what the chart suggested was wired.

4. **Turn 2 — subsequent-turn branch, tool trigger.** Take the **first user line of the demo run-through script** (`[CUSTOMER]_FLOW_INSERTS.md` §10) as the message — that's the realistic, persona-shaped utterance the build was designed for.
   ```
   talk_to_agent { ..., message: "<first demo run-through line>", same user_id + session_id }
   ```
   **Assert:**
   - [deterministic] Response does NOT re-render the Say Welcome line → Once gate works on subsequent turns
   - [advisory] `outputStack` contains an entry with `data._cognigy._finishReason: "tool_calls"` → AI Agent chose to call a tool. This is an LLM decision — a miss is advisory, not a structural failure.
   - [deterministic, conditional] *If a tool fired*, at least one filler Say line from §C.1 appears in `outputStack` BEFORE the tool result → Shape B `Say → Code → Resolve` order is intact. (N/A this run if the LLM didn't call a tool — that's the advisory miss above, not a branch-order failure.)
   - [deterministic, conditional] *If a tool fired*, mock data set in Initialize Session (turn 1) appears in the tool result → `context.customer` persisted across turns

   Failures and how to handle:
   - Welcome re-rendered → Once is misconfigured → **loop back** to §1.5(a). [deterministic]
   - No `tool_calls` finishReason → **advisory.** Re-run this single turn once. If it still doesn't call a tool across two runs, **log an advisory warning** for the user — likely persona routing-tree / tool-description ambiguity, worth a manual look at the persona's ROUTING DECISION TREE and the tool `description` fields. **Do NOT auto-regenerate the persona or re-patch §1.2** on this miss.
   - Filler line missing or after tool result (and a tool DID fire) → tool branch built in wrong order → **loop back** to §1.4 / §6. [deterministic]
   - Mock data missing (and a tool DID fire) → Initialize Session never ran OR `context.customer` keys mismatch the §3 template → **loop back** to §1.5(b). [deterministic]

5. **Turn 3 — end-of-conversation (BRANCH on the intent exercised in Turn 2).** The correct close depends on whether Turn 2's intent was resolvable in-bot or a transfer intent. Assert the path a *correct* persona actually drives per §2.5 END-OF-CONVERSATION RULES — do **not** hardcode `end_call_resolved` (a transfer-first demo legitimately ends via `end_call`, so the old fixed assertion failed correct builds).

   **Case A — Turn 2 was a TRANSFER intent** (the first demo line routed to a `transfer_to_*` tool). Per §2.5, immediately after the transfer tool returns the persona calls **`end_call`** (NOT `end_call_resolved`), with no text reply in between — so the transfer + `end_call` may already have fired inside Turn 2's exchange. Inspect that exchange (and, only if the line is still open, send a brief `"thanks"`):
   - [deterministic] An end-call fired and `outputStack` contains its Hangup payload (`_voiceGateway2.json.action: "hangup"` or AU1 equivalent), reached via the **`end_call`** branch — assert the malformed-branch structure here (Hangup present, terminates before `aiAgentToolAnswer`). A missing/broken Hangup → **loop back** to §5.
   - [advisory] Whether the LLM picked `end_call` (vs `end_call_resolved`) at the right moment is an LLM decision. If the structural Hangup is present but via the wrong variant, **log an advisory warning** about the persona's END-OF-CONVERSATION wiring — do not auto-regenerate.

   **Case B — Turn 2 was an IN-BOT-RESOLVABLE intent** (a transactional tool resolved the enquiry without a transfer). Send `"that's all, thanks"`:
   ```
   talk_to_agent { ..., message: "that's all, thanks", same user_id + session_id }
   ```
   - [advisory] The model chooses to call `end_call_resolved` proactively. If it instead keeps the line open or asks a follow-up, **log an advisory warning** (persona END-OF-CONVERSATION proactivity) — do not auto-regenerate.
   - [deterministic] *Once `end_call_resolved` fires*, `outputStack` contains its Hangup payload AND the response `text` contains the `end_call_resolved` goodbye Say line verbatim. A malformed branch (Hangup missing / goodbye Say wrong) → **loop back** to §5.

6. **xApp runtime test (CONDITIONAL — only if `{Customer}-agent-interfaces.md` named xApp scenes; skip entirely otherwise).** Emulate an xApp submit by passing the payload via `talk_to_agent`'s `data` param — the same field the live xApp SDK posts to — then assert both halves of §1.4b (delivery + return path per `explain("xapp-event-handling")`):
   ```
   talk_to_agent {
     ...,
     message: "<utterance that triggers the xApp scene>",
     data: { _cognigy: { _app: { payload: { <scene submit fields> } } } },
     same user_id + session_id
   }
   ```
   **Assert:**
   - [deterministic] On the triggering turn, `outputStack` contains a `setHTMLAppState` delivery (the scene was pushed) → §1.4b delivery path wired. Failure → loop back to §1.4b (scaffold / `context.xappTrigger`).
   - [deterministic] After the emulated submit, the flow's inbound `ifThenElse` intercepts `input.data._cognigy._app.payload` and the submit result surfaces in the next tool answer (`context.toolResponse`) → §1.4b return path wired. Failure → loop back to §1.4b (inbound interceptor).
   - [advisory] Whether the LLM weaves the submitted data into its next reply naturally is an LLM decision — advisory, not a gate; log a warning if it doesn't.

#### When Phase A passes and Phase B's deterministic assertions pass

"Pass" = every Phase A assertion GREEN **and** every **deterministic** Phase B assertion GREEN. Outstanding **advisory** (probabilistic) warnings do not block hand-back, but every one must be recorded here and echoed in the §10 hand-back so the user sees them — never silently drop an advisory.

Append a `## Smoke test results` section to `[CUSTOMER]_FLOW_INSERTS.md` (after §11 Known gaps) capturing:
- Phase A: PASS for each of the 12 (deterministic) assertions
- Phase B: the turn transcripts (user message + bot response text, verbatim), each assertion tagged PASS / FAIL (deterministic) / WARN (advisory)
- Any advisory warnings carried forward to §10
- Session IDs used (so the user can replay in the Cognigy session inspector)
- Timestamp

Only then proceed to §1.9 hand-back.

### 1.8 Knowledge wiring (CONDITIONAL — only if §0.5 gate opened)

**ENFORCED GATE — first thing this section does, before any other work:**

```
if (knowledgeRequested !== true) { skip §1.8 entirely; proceed to §1.9 }
```

`knowledgeRequested` is the boolean output of §0.5. If it is `false`, missing, or anything other than the literal `true` the user confirmed in §0.5, **this section does not run**. Do not infer YES from "knowledge would be helpful here", from the demo plan mentioning FAQs, or from a use case sounding lookup-shaped. The §0.5 gate is the only gate. If you find yourself reasoning about whether to run §1.8 without re-reading §0.5's output, stop — re-read §0.5 and respect its decision.

**Skip this entire section if §0.5 returned `knowledgeRequested: false`.**

If §0.5 returned YES, the user gave a list of FAQ topic specs. **This section wires Cognigy's built-in Knowledge AI only** — author the FAQ bodies locally, then ingest them into a Cognigy knowledge store. There is no CXone Expert publishing step here: Expert publishing belongs in a future `knowledge@nice` skill and is out of scope for this orchestrator. Do not add an Expert escape hatch until that skill ships.

**Working directory:** stay in `Demo Builds/<customer>-demo/`.

**Step 1 — Author one markdown body per topic.** Write each FAQ topic from §0.5 to `Demo Builds/<customer>-demo/knowledge/<topic-slug>.md`. Body shape: a short heading, then the FAQ content in plain markdown. These files are the source text ingested into the Cognigy knowledge store in Step 2, and they stay version-controlled in the demo folder.

**Step 2 — Wire Cognigy's built-in Knowledge AI on the agent.** First principles: the simplest, most robust knowledge integration is Cognigy's built-in retrieval (the Job Node natively queries the knowledge store between turns) — not a separate `search_*_faqs` tool with its own branch. Two MCP calls:

a. **Create the knowledge store on the agent** via NiCE `manage_knowledge`, then ingest each local markdown body from Step 1 as a source/chunk:
   ```
   manage_knowledge {
     operation: "create_store",
     projectId: "<projectId>",
     agentId: "<agent.id>",
     name: "<Customer>_Knowledge",
     sources: [{ name: "<topic-slug>", text: "<contents of knowledge/<topic-slug>.md>" }, ...]
   }
   → returns { knowledgeStoreId, ... }
   ```
   One source entry per local body file. If `manage_knowledge` does not accept inline `sources` in your running MCP, create the store empty and ingest via the cognigy-vibe fallback below.

b. **Enable Knowledge AI on the agent** via NiCE `manage_settings`:
   ```
   manage_settings {
     operation: "set_knowledge_ai",
     agentId: "<agent.id>",
     enabled: true,
     knowledgeStoreId: "<from step (a)>"
   }
   ```

**Verify the wiring landed.** `cognigy_get { resource_type: "agents", resource_id: "<agent.id>" }` and confirm:
- `knowledgeStoreId` matches the store from (a)
- `knowledgeAI: true` (or equivalent enabled flag) is set

A silent shape mismatch can return 200 OK without actually wiring anything — verification catches this before smoke test, where it would otherwise surface as "the bot ignores its FAQs".

**Fallback — cognigy-vibe knowledge-store API** (if NiCE `manage_knowledge` / `manage_settings` don't fit the running MCP). Per plugin `explain("knowledge-store")` — hierarchy Project → KnowledgeStore → Sources → Chunks:
```
// 1. Create the source under an existing store (ksId):
cognigy_create { resource_type: "knowledgestores/<ksId>/sources", body: { name: "<source name>", type: "manual" } }
// 2. Add text as chunks (one call per chunk):
cognigy_create { resource_type: "knowledgestores/<ksId>/sources/<sourceId>/chunks", body: { text: "<FAQ body>" } }
// 3. Trigger ingestion via a connector:
cognigy_invoke { resource_type: "knowledgestore", resource_id: "<ksId>", operation: "run", body: { connector_id: "<connectorId>" } }
```
Resolve `<ksId>` via `resolve_resource { name: "<store name>", resource_type: "knowledgestores" }`. **Source-create gotchas (400 otherwise):** `type` must be `"manual"` (not `"text"`); do NOT pass `content` or `knowledgeStoreId` at source-create — text is added as chunks afterwards (step 2). Same verification applies.

**Last resort — manual UI step.** If neither MCP path works, document a manual UI step in `[CUSTOMER]_FLOW_INSERTS.md` Section 9 (Knowledge wiring) and surface it in the hand-back block. Don't fail the build — knowledge can be wired manually post-hoc.

**Why this approach (vs a separate `search_*_faqs` tool):** built-in Knowledge AI handles retrieval, ranking, and answer-grounding inside the Job Node's response path — no extra tool branch, no Code mock, no `input.result` wiring, no persona routing-tree edit. The LLM gets retrieved context injected automatically alongside its other inputs. Simpler, less to maintain, harder to break.

**Step 3 — Append "Knowledge wired" to as-built.** Add to `[CUSTOMER]_FLOW_INSERTS.md` Section 9:

```markdown
## 9. Knowledge wiring

- Knowledge AI enabled: <yes / no>
- Knowledge store ID: <id from Step 2(a)>
- Topics ingested: <count> (sources in the Cognigy knowledge store)
- Local body files: knowledge/<slug>.md × <count>
- Wiring mechanism: <manage_knowledge + manage_settings | cognigy-vibe knowledge-store API | manual UI step>
```

No `search_*_faqs` tool is created and no persona routing-tree edit is performed — built-in Knowledge AI does not require either.

### 1.9 Hand back to the user

Print the output block in §10. Smoke test (§1.7) has already validated the build at runtime — both structural (Phase A) and conversational (Phase B). Hand-back is for the user to do exploratory testing in the Cognigy UI's Interaction Panel, not first-time validation. If §1.7 surfaced a "smoke test partial" outcome, the hand-back block must include the specific failure(s) and proposed manual fix from §1.7.

---

## §2 — Canonical persona shape (four-layer ladder)

The persona content is structured in four layers that map to two Cognigy fields. Keeping the layers separate prevents the common drift where procedural rules (the HOW) bloat the persona description (the WHO), and where channel-level speaking conventions (globally applicable) get scattered across job-level instructions (which are job-scoped).

**Layer → field mapping:**

| Layer | persona.md H2 heading | Agent-level field | Job Node config field (after §1.2 patch) |
|---|---|---|---|
| (a) **Persona** — WHO the agent is (incl. brand voice) | `## Persona` | agent `description` | n/a — agent-level only |
| (b) **Special Instructions** — HOW the agent behaves globally (speaking conventions, abuse, out-of-scope) | `## Special Instructions` | agent `instructions` — **its OWN field, NOT concatenated into `description`** (set via `update_ai_agent`; **≤ 1000 chars**) | n/a — agent-level only |
| (c) **Job Description** — WHAT this job handles | `## Job Description` | n/a | `description` (= `jobDescription`) |
| (d) **Job Instructions** — HOW this job procedurally runs | `## Job Instructions` | n/a | `instructions` (= `jobInstructions`) |

> **Field-name caution:** the AGENT resource and the AI Agent JOB NODE *each* have their own `description` and `instructions` fields. They are different layers: the **agent** `description`/`instructions` hold Persona (1A) / Special Instructions (1B); the **job-node** `description`/`instructions` hold Job Description (2A) / Job Instructions (2B). Don't conflate them.

**Extraction rule for §1.1 + §1.2:** parse `{Customer}-agent-persona.md` by H2 heading and map each block to its OWN field — they are **NOT** concatenated:
- agent `description` = `## Persona` block only (1A — WHO, incl. brand voice).
- agent `instructions` = `## Special Instructions` block (1B — global HOW; set at the **agent** level via `update_ai_agent`, since `create_ai_agent` does not accept it — see §1.1).
- `jobDescription` = `## Job Description` block (2A).
- `jobInstructions` = `## Job Instructions` block (2B, §2.5 empathy library verbatim).

> **🔴 BLOCKING — agent free-text fields are hard-capped at 1000 characters.** Both **agent `description` (1A Persona)** and **agent `instructions` (1B Special Instructions)** MUST be **≤ 1000 characters** each (the documented platform maximum; over-length throws a save error that the agent silently survives, injecting uncertainty and rework into the build). This is enforced as a pre-flight count in §1.1/§1.2 (condense before the call) and re-verified in §1.7 Phase A + §1.6. Keep each block tight: Persona is the WHO + brand voice in a few sentences; Special Instructions is lean speaking-conventions + brief abuse + brief out-of-scope rules. (No documented limit applies to the job-node `jobDescription`/`jobInstructions`, so the empathy library in 2B is unaffected.)

**Contract on `cognigy:design-agent-persona` output:** the sub-skill MUST emit `{Customer}-agent-persona.md` with exactly four H2 headings — `## Persona`, `## Special Instructions`, `## Job Description`, `## Job Instructions` — in that order, with `## Persona` and `## Special Instructions` **each ≤ 1000 chars**. The empathy library (§2.5) lives verbatim inside `## Job Instructions`. If the sub-skill output is missing a heading, merges sections, or blows the 1000-char cap on either agent field, regenerate / condense before §1.1 runs.

---

### (a) `## Persona` template — agent-level WHO

> **Brand-voice rule:** descriptors and verbs in `<>` placeholders MUST be drawn from `brand-research.md` (§0.6). If you find yourself reaching for generic placeholders like "calm, capable, knowledgeable" out of habit, stop — open the brand-research snapshot and use those keywords instead. Do not invent brand voice.

```
<Persona> is the inbound voice concierge for <Customer>. <Customer>'s mission is "<verbatim mission from brand-research>" — <Persona> is the front line of that promise.

<Persona> is <3–4 brand-voice descriptors from brand-research §Tone descriptors>. <Persona's tone do's, paraphrased into 1 sentence from brand-research>. <Persona> projects steadiness — not pity. When a caller raises a sensitive topic, <Persona> follows the §2.5 empathy protocol (defined in Job Instructions below).

BRAND VOICE (from brand research — §0.6):
- Tone descriptors: <3–6 from brand-research.md>
- Tone do's: <2–3 do's, quote-traceable>
- Tone don'ts: <2–3 don'ts, quote-traceable>
```

Persona content is globally applicable — it describes WHO the agent is regardless of which job is running. **Brand voice lives HERE** (it's part of the WHO), not in Special Instructions. Procedural content (when to call which tool, how to handle a no-match, empathy templates) does NOT belong here — it lives in Job Instructions. **Keep the whole `## Persona` block ≤ 1000 characters** (it populates the agent `description` field — see the §2 limit rule).

---

### (b) `## Special Instructions` template — agent-level global HOW (speaking conventions + abuse + out-of-scope)

Globally applicable rules for how the agent BEHAVES, independent of any specific job. These apply on every turn, in every job this agent might hold. This block populates the **agent `instructions` field** (1B) — its OWN agent-level field, **NOT** concatenated into `description`. **Brand voice does NOT live here — it moved to `## Persona` (1A).**

```
SPEAKING CONVENTIONS (voice channel — apply across all jobs):
- Contractions: use "I've", "You're", "Aren't" — never the uncontracted form on voice.
- Currency: say "one hundred and twenty three dollars and 84 cents" — never "$123.84".
- Identifying numbers (account, policy, OTP): say each digit — "One Two Three" — never "one hundred and twenty three" or "123".
- Repeated digits: say "Double Two" — not "twenty two" or "22".
- Addresses: say "twenty seven Johnson Street" — not "Two-Seven Johnson Street" or "27 Johnson Street".
- Times: say "three forty-five PM" — not "3:45 PM".
- Dates: say "the fifteenth of June" — not "fifteen slash six".

ABUSE / HOSTILITY (all jobs): stay calm and professional; never match hostility. One brief warning; if it continues, route to a human (the relevant transfer, else transfer_to_general) then end_call. Never argue or threaten.

OUT OF SCOPE (all jobs): if a request falls outside this agent's jobs, say so briefly and route to transfer_to_general — do not speculate or answer from general knowledge.
```

These rules live at the **agent** level — in the agent `instructions` field — rather than the **job** level because they're invariant across jobs. If the agent later holds a second job (e.g. outbound campaign vs inbound concierge), they still apply unchanged.

> **🔴 1000-char budget (BLOCKING).** This block is hard-capped at 1000 chars (agent `instructions` limit — §2 limit rule). The verbatim SPEAKING CONVENTIONS alone are ~700 chars, so keep ABUSE and OUT OF SCOPE terse, and if you add further global rules, trim to stay under 1000. The §1.1/§1.2 pre-flight count and §1.7 Phase A both enforce this. (Per-customer "recent sensitivities" context lives in `brand-research.md`, not in this capped field.)

---

### (c) `## Job Description` template — job-level WHAT

One paragraph describing what THIS job handles. Names the capability surface (tool list, summarised) and out-of-scope boundary. **No procedures, no routing tree, no empathy templates.**

```
This job handles inbound voice concierge calls for <Customer>. <Persona> uses the following tools to resolve caller intents:

- <verify_caller>: refreshes the caller profile (CRM-by-phone) when context.customer is undefined.
- <use_case_tool_1>: <one-line description of what it does>.
- <use_case_tool_2>: <one-line description>.
- ... (every transactional tool with a one-line description)
- <transfer_to_care, transfer_to_general, transfer_to_*>: routes to specialist teams (see Job Instructions for full routing rules).
- <end_call, end_call_resolved>: closes the call cleanly post-transfer or post-resolution.

Out of scope: <one or two lines on what THIS job doesn't handle — e.g. "outbound sales campaigns", "agent-assist suggestions to human agents", "any topic requiring a human assessor's discretion (claims approvals, hardship eligibility decisions)">.
```

The tool list here is a **summary** for the LLM's situational awareness. Detailed routing logic lives in Job Instructions.

---

### (d) `## Job Instructions` template — job-level HOW

All procedural content. This is where the LLM looks for "what do I do next" guidance every turn.

```
START OF CALL:
- Caller profile is pre-loaded into context.customer at session start. Use literal values from there.
  <industry-shaped placeholders — see §3>
- If context.customer.* fields are 'undefined', call verify_caller first before doing anything else.
- The Welcome line has already played (init chain Say node). Do not re-greet.

ROUTING DECISION TREE (derived in §1.3):
- <use case 1> → call <derived_tool_1>
- <use case 2> → call <derived_tool_2>
- ... (one line per use case + derived transfer)
- SENSITIVE DISCLOSURE (any §2.5 trigger) → use the §2.5 empathy template, then call transfer_to_care (or transfer_to_complaints for explicit complaints)
- ANYTHING NOT HANDLED ABOVE → call transfer_to_general

SENSITIVE-TOPIC EMPATHY PROTOCOL (MANDATORY):

<§2.5 EMPATHY LIBRARY — INSERT VERBATIM HERE>
  All 7 trigger categories (bereavement, suicide/self-harm, mental health, financial
  hardship, FV, complaint, serious illness), each with trigger phrases + empathy beat +
  action sentence + transfer tool. Plus the 11 hard rules. Plus Lifeline 13 11 14 for
  trigger 2. Source of truth lives in §2.5 below — copy that block in here verbatim,
  do NOT paraphrase or summarise. §1.2 patches this entire section into the Job Node's
  `instructions` field.

END-OF-CONVERSATION RULES (MANDATORY):
- AFTER ANY transfer_to_* tool returns → IMMEDIATELY call end_call. No text reply between
  transfer and end_call.
- WHEN <PERSONA> HAS RESOLVED THE ENQUIRY IN-BOT AND the caller has nothing else for you →
  call end_call_resolved proactively.
- end_call = hand-off / unresolved.  end_call_resolved = <Persona> did the job herself.
- After either end_call_* tool returns, STOP. The line is closing.

NEGATIVE-PATH RULES (MANDATORY):
- If a lookup tool returns `found: false`, apologise and ask the caller to confirm the value.
  Do NOT retry the same tool with the same input.
- If a tool returns `needsDisambiguation: true`, ask the user the `prompt` field. Do not fire
  tools until the user answers.
- Never invent data — only speak literal tool-returned values.

GENERAL RULES:
- One tool per turn (except §2.5 protocol where the empathy text + transfer fire in the same turn).
- Short replies (phone call). Australian phrasing. Match the SPEAKING CONVENTIONS set in the agent's Special Instructions (1B) and the BRAND VOICE set in the agent's Persona (1A) — both are agent-level fields, above this job's instructions.
- Caller profile rules and verify_caller fallback are defined in START OF CALL above — do not duplicate.
```

---

## §2.5 — Empathy Response Library (verbatim — bake into every build's `## Job Instructions`)

This library is the single source of truth for how the AI Agent handles sensitive disclosures. It gets emitted verbatim into the persona's `## Job Instructions` H2 section (layer d in the §2 ladder), which §1.2 patches into the Job Node's `instructions` field, so the runtime LLM has concrete templates to pattern-match against — not vague "acknowledge once" guidance.

**Why this exists:** "Acknowledge with empathy" is too abstract for a voice LLM. Without verbatim templates the model defaults to its training — which produces "I will transfer you now" (robotic) or "I'm so sorry to hear that, can you tell me more about what happened?" (probing — wrong). The library forces the right shape every time.

**Pattern (all 7 categories):**

```
<Empathy beat — 1 short sentence, warm but not effusive>
<Action sentence — 1 short sentence, names the team, signals transfer>
→ fire transfer tool immediately (same turn)
```

**Categories + templates:**

> **Match semantically, not just literally.** The trigger phrases below are illustrative examples — match by MEANING. Oblique disclosures count: "my husband won't be needing the policy anymore" (bereavement), "I just don't see the point of any of this" (potential self-harm), "we're underwater on the mortgage" (financial hardship), "things at home aren't safe" (family violence). When in doubt about which category fits, use the highest-severity match per hard rule 8.

| # | Trigger phrases (LLM matches these patterns) | Empathy beat | Action sentence | Transfer tool |
|---|---|---|---|---|
| 1 | Bereavement: "my wife died", "we lost my father", "he passed away", "my mum just passed" | "I'm very sorry for your loss." | "Let me put you through to our Care Team who can help you with what needs to happen next." | `transfer_to_care` |
| 2 | Suicide / self-harm: "I want to end it", "I'm thinking of hurting myself", "I can't go on", "what's the point of living" | "I'm really worried about you, and I want to help." | "If you're in immediate danger, please call Lifeline on 13 11 14 right now. I'm also putting you through to our Care Team who can stay with you." | `transfer_to_care` |
| 3 | Mental health distress: "I've been struggling", "anxiety", "depression", "not coping", "really down" | "I'm really sorry you're going through this." | "Let me get you to our Care Team — they'll be able to support you properly." | `transfer_to_care` |
| 4 | Financial hardship: "can't afford", "lost my job", "behind on payments", "homeless", "no money for food" | "That sounds really tough." | "Let me put you through to our hardship specialists in the Care Team — they can work through your options with you." | `transfer_to_care` |
| 5 | Family / domestic violence: "my partner is hurting me", "I'm scared of my husband", "DV", "afraid to go home" | "I'm so sorry. You're in the right place." | "I'm putting you through to our Care Team — they're trained for this and they'll keep you safe." | `transfer_to_care` |
| 6 | Complaint (formal): "I want to make a complaint", "this is unacceptable", "I'm furious", "totally unhappy with the service" | "I hear you, and I'm sorry this has happened." | "Let me get you to our Complaints Team — they have the authority to sort this out properly." | `transfer_to_complaints` (or `transfer_to_care` if Complaints tool not built) |
| 7 | Serious illness: "I've been diagnosed", "cancer", "terminal", "I'm dying" | "I'm sorry to hear that." | "Let me put you through to our Care Team — they'll have time to talk this through with you properly." | `transfer_to_care` |

**Hard rules (apply to ALL categories):**

1. **NEVER probe.** Don't ask "can you tell me more about what happened?", "when did this happen?", "are you safe right now?" — the Care Team does that.
2. **NEVER use "I understand" or "I can imagine."** Both read as platitudes on voice. The empathy beats above are non-platitude. Stick to them.
3. **NEVER suggest external resources unprompted** — EXCEPT the Lifeline number for category 2 (suicide/self-harm). That's a mandatory Australian safety rail.
4. **NEVER say "I will transfer you now"** or "Let me transfer you." The action sentence already announced the transfer.
5. **NEVER read back identity details** (policy address, account number digits) for category 5 (FV) — the caller may not be safe to speak freely. Same for explicit verification — skip the read-back of phone digits.
6. **Fire the transfer tool in the SAME TURN as the empathy text.** The transfer Say node speaks the hand-off line; the LLM does not need to add anything.
7. **After firing transfer, STOP.** Do not generate another text reply. The next event is end_call.
8. **If multiple triggers in one message, use the highest severity.** Priority order: suicide/self-harm > FV > bereavement > mental health > serious illness > hardship > complaint.
9. **Brand-voice override:** if `brand-research.md` flags specific tone don'ts for this customer (e.g. avoiding jargon, avoiding corporate platitudes, avoiding specific words), the empathy beat must still avoid those — paraphrase only if the verbatim template breaks brand voice. Default to verbatim.
10. **Team-name flex.** "Care Team" / "Complaints Team" in the action sentences are DEFAULTS. If brand-research.md surfaces the customer's actual support-team naming (e.g. "Member Support", "Client Care", "Wellbeing Team", "Customer Care"), substitute it in the spoken phrase. The **tool name stays `transfer_to_care`** (consistent across all builds) — only the spoken team name flexes.
11. **NEVER route sensitive disclosures to `transfer_to_general`.** A specific destination (`transfer_to_care` or `transfer_to_complaints`) is non-negotiable. The whole point of this protocol is that callers in distress reach the right team, not the general queue. If brand-research surfaces no "Care"-equivalent team, the build STILL ships with `transfer_to_care` as a labelled tool — the spoken phrase can say "specialist support team" but the routing is specific, never the general fallback.

**For the user at build time:**

- The skill emits this library verbatim into the persona's `## Job Instructions` H2 section (layer d — see §2 template). §1.2 patches that section into the Job Node's `instructions` field, so the runtime LLM has the library in context every turn.
- The skill also writes `<customer>-empathy-library.md` to `Demo Builds/<customer>-demo/` as a **read-only reference export** of exactly what was baked in (handy for review / QA). **It is NOT wired to the live agent — editing it changes nothing at runtime.** To change runtime empathy behaviour, edit the `## Job Instructions` block of `{Customer}-agent-persona.md` (the per-build editable home) and re-run §1.2 to re-patch the Job Node. **SSOT chain:** §2.5 template → `{Customer}-agent-persona.md` `## Job Instructions` → §1.2 → live Job Node. The exported `.md` sits outside that chain.
- The recap shows the 7 trigger categories so the user can confirm coverage or add custom ones (e.g. "natural disaster — bushfire, flood — for an Aussie insurer in catastrophe season").

---

## §3 — Canonical CRM template (industry-flexible)

The Initialize Session Code is the **single source of truth** for the caller-profile shape. Every downstream Code mock + the AI Agent Job Node's `memoryContextInjection` must use the **exact same field names**.

**CORE fields (always present, all industries):**
- `firstName`, `lastName`, `phoneMasked` (as **spoken words**, e.g. `"five six seven"`)
- `customerId` — primary identifier (industry-renamed below)

**INDUSTRY PRESETS — pick 3–6 fields based on interview Q3:**

| Industry | customerId field | Additional fields |
|---|---|---|
| Insurance | `policyNumber` | `policyType, outstandingPremium, dueDate, preferredPayment` |
| Telco | `accountNumber` | `planName, currentBill, dueDate, lastTopUp, dataRemaining` |
| Banking | `accountNumber` | `productType, balance, lastTransaction, preferredPayment` |
| Retail | `memberId` | `tier, lifetimeValue, lastOrder, preferredPayment` |
| Health | `memberId` | `planLevel, lastClaim, providerNetwork, dependents` |
| Other | `customerId` | Ask the user for 3–5 domain-appropriate fields |

**Initialize Session Code** (write to `Demo Builds/<customer>-demo/code-nodes/<customer>_initialize_session.js`):

```javascript
// Canonical CRM template — single source of truth for caller profile.
// In production: phoneMasked from SIP/CLI; the rest from a CRM-by-phone
// lookup that runs before the bot speaks. Demo runs are deterministic.

context.customer = {
  firstName: "<First>",
  lastName: "<Last>",
  phoneMasked: "<masked digits as spoken words>",
  <customerIdField>: "<value>",
  // ... 3–5 industry-specific fields per preset above
};
context.call = { phoneMasked: "<same masked digits>" };
```

Use the literal values the user gave in interview Q7.

**Corresponding `memoryContextInjection`** (passed to `aiAgentJob.config.memoryContextInjection`):

```
Caller profile (use these literal values — never invent):
firstName: {{context.customer.firstName}}
lastName: {{context.customer.lastName}}
phoneMasked: {{context.customer.phoneMasked}}
<customerIdField>: {{context.customer.<customerIdField>}}
<additional-field-1>: {{context.customer.<additional-field-1>}}
<additional-field-2>: {{context.customer.<additional-field-2>}}
...

Note: if these show as 'undefined', call verify_caller first.
```

**verify_caller's Code mock** mirrors the same field shape (refresh path, not alternative source). Uses the plugin-canonical tool-result convention per §C.2:

```javascript
context.call = { phoneMasked: "<same as Init Session>" };
context.customer = {
  firstName: "<same>",
  lastName: "<same>",
  phoneMasked: "<same>",
  <customerIdField>: "<same>",
  // ... same industry fields as Init Session
};
context.toolResponse = context.customer;
api.resolve();
```

**HARD RULE — three-way field-name consistency:**

Field names MUST match exactly across:
1. Initialize Session Code (where `context.customer` is set)
2. AI Agent Job Node `memoryContextInjection` template
3. `verify_caller` Code mock (and every other tool Code that reads `context.customer.*`)

**`phoneMasked` duality (MANDATORY — it lives in two homes).** `phoneMasked` is written to BOTH `context.customer.phoneMasked` and `context.call.phoneMasked` (Initialize Session and `verify_caller` set both; the Say Welcome line reads `context.call.phoneMasked` while `memoryContextInjection` reads `context.customer.phoneMasked`). The diff guard therefore extends to `context.call.phoneMasked`: wherever both are set, assert `context.call.phoneMasked === context.customer.phoneMasked` (identical spoken-word digits). A mismatch makes the welcome line and the agent's read-back disagree — the same hallucinated-data class of bug.

Before hand-back, **diff these places** and confirm (a) zero field-name mismatches and (b) the two `phoneMasked` homes hold identical values. A typo here is the single most common cause of "the bot is hallucinating data".

---

## §4 — Tool branch patterns (cheat sheet — index only)

**The canonical homes are §1.4 (the shape diagrams) and §6 (the step-by-step build recipe).** This section is a pointer so each shape lives in exactly one place — do not re-paste the diagrams here.

All branches terminate in **`aiAgentToolAnswer`** (plugin's canonical terminal — see §1.3 naming note). With `push_agent_tool` the aiAgentToolAnswer is NOT auto-paired — it is the explicit final append (§6 Step 4) after the branch's functional nodes, each added via `mode: "append"`.

| Shape | Visual (canonical) | Build steps (canonical) | Notes |
|---|---|---|---|
| Transactional (Shape B — most common) | §1.4 | §6 Steps 1–3 | Filler Say (§C.1) → Code (§C.2) → answer |
| Transfer (reversed) | §1.4 | §6 Steps 1–3 | Code (mark transfer) → Say (the **single** spoken hand-off announcement) → answer |
| `end_call` | §1.4 / §5 | §6 | **Hangup only — NO Say.** It always follows a `transfer_to_*` whose branch Say already announced the hand-off; a second announcement here would double up. |
| `end_call_resolved` | §1.4 / §5 | §6 | resolved goodbye Say → Hangup → answer |

---

## §5 — End-of-conversation tools (full spec)

Two intent-named tools. The LLM picks reliably between two well-described tools.

### end_call

**Description:**
> Closes the call cleanly when the AI Agent cannot resolve the enquiry in-bot — i.e. after ANY `transfer_to_*` tool fires, OR when the caller's intent is out of scope. Call this IMMEDIATELY after a `transfer_to_*` tool returns; no text reply in between.

**Parameters:** None — param-free tool. **Omit `parameters` from the `.tool.json` entirely** (per §1.3: "omit `parameters` entirely for param-free tools"). Do not use the stringified `create_tool` format here — this tool is authored via `push_agent_tool` with a `.tool.json` file.

**Branch (Hangup only — NO spoken line):** `end_call` always fires right after a `transfer_to_*` whose branch Say already spoke the hand-off, so re-announcing here would double up. Go straight to Hangup:
```
[aiAgentJobTool: end_call]
  └── [Hangup]
        └── [aiAgentToolAnswer]
```

**Hangup node** (extension `@cognigy/voicegateway2` auto-injected). Because there is no Say, the Hangup appends directly to the tool node:
```
cognigy_create {
  resource_type: "node",
  flow_id: "<flowId>",
  body: {
    type: "hangup",
    mode: "append",
    target: "<aiAgentJobToolNodeId>",
    label: "Hang Up",
    config: { hangupReason: "<Persona> handed off to a specialist team", hangupImmediately: false }
  }
}
```

### end_call_resolved

**Description:**
> Closes the call cleanly when the AI Agent HAS resolved the caller's enquiry in-bot. Proactive — don't wait for "goodbye".

**Parameters:** None — param-free tool. **Omit `parameters` from the `.tool.json` entirely** (same as `end_call` above).

**Branch:**
```
[aiAgentJobTool: end_call_resolved]
  └── [Say: "Thanks for calling <Customer>. Have a wonderful day."]
        └── [Hangup]
              └── [aiAgentToolAnswer]
```

**Hangup config:**
```
config: { hangupReason: "<Persona> resolved the enquiry", hangupImmediately: false }
```

---

## §6 — Tool-creation recipe (one tool, step by step)

Repeat for every tool in §1.3. The tool node comes from `push_agent_tool` (§1.3); Code nodes from `push_code_node`; Say / Hangup / `aiAgentToolAnswer` from cognigy-vibe `cognigy_create` with `mode: "append"` (per plugin `explain("node-positioning")`). Extension is auto-injected for known node types. **Each node appends onto the previous one; the `aiAgentToolAnswer` is the final append (Step 4) — it is NOT auto-created.**

**Step 1 — create the aiAgentJobTool node (cognigy-vibe `push_agent_tool`):**

Author the `.tool.json` file in `tools/<tool_id>.tool.json` (see §1.3 for shape) and push:
```
push_agent_tool {
  tool_file: "<ABS PATH>/Demo Builds/<customer>-demo/tools/<tool_id>.tool.json",
  flow_id: "<flowId>",
  job_node_id: "<aiAgentJobNodeId>"
}
→ returns { success, node_id: "<aiAgentJobToolNodeId>", created | updated }
```
This creates ONLY the tool node — the chain is `aiAgentJob → aiAgentJobTool`. Steps 2–3 append the functional nodes; **Step 4 appends the `aiAgentToolAnswer` terminal** (not auto-created).

**Step 2 — first functional node** (appended onto the aiAgentJobTool node):

Transactional / `end_call_resolved` → `say` first (Filler Say for transactional; the resolved goodbye line for `end_call_resolved`):
```
cognigy_create {
  resource_type: "node", flow_id: "<flowId>",
  body: { type: "say", mode: "append", target: "<aiAgentJobToolNodeId>",
          label: "Filler — <verb>", config: { text: "<filler from §C.1>" } }
}
```

`end_call` → **skip the Say entirely**: it follows a transfer whose branch Say already announced the hand-off. Its Hangup (Step 3) appends directly onto `<aiAgentJobToolNodeId>`.

Transfer tool → `code` first (mark the transfer in context before the spoken hand-off). One `push_code_node` CREATE call (omit `node_id`) creates, positions, and pushes the body:
```
push_code_node {
  script_file: "Demo Builds/<customer>-demo/code-nodes/<tool_id>_mark_transfer.js",
  flow_id: "<flowId>",
  mode: "append",
  target: "<aiAgentJobToolNodeId>",
  label: "Mark transfer — <team>"
}
```
where the `.js` body is:
```javascript
context.toolResponse = { transferred: true, team: "<team>", teamLabel: "<Customer> <Team>" };
api.resolve();
```

**Step 3 — second functional node** (appended onto Step 2's node):

Transactional → `code` mock (per §C.2 shapes). One `push_code_node` CREATE call (omit `node_id`):
```
push_code_node {
  script_file: "Demo Builds/<customer>-demo/code-nodes/<tool_id>_mock.js",
  flow_id: "<flowId>",
  mode: "append",
  target: "<fillerSayNodeId>",
  label: "<Action> <Domain>"
}
```
The `.js` body reads args from `input.aiAgent.toolArgs`, writes `context.toolResponse`, calls `api.resolve()` (Shape 1, 2, or 3 per §C.2).

Transfer → `say` (hand-off line):
```
cognigy_create {
  resource_type: "node", flow_id: "<flowId>",
  body: { type: "say", mode: "append", target: "<codeNodeId>",
          label: "Say — transferring to <team>",
          config: { text: "Right, putting you through to our <team> team now." } }
}
```

End-call → `hangup` (extension auto-injected as `@cognigy/voicegateway2`). Target is the preceding node: for `end_call_resolved`, the goodbye `<sayNodeId>` from Step 2; for `end_call`, the `<aiAgentJobToolNodeId>` directly (no Say):
```
cognigy_create {
  resource_type: "node", flow_id: "<flowId>",
  body: { type: "hangup", mode: "append", target: "<sayNodeId — or aiAgentJobToolNodeId for end_call>",
          label: "Hang Up",
          config: { hangupReason: "<reason>", hangupImmediately: false } }
}
```

**Step 4 — append the `aiAgentToolAnswer` terminal (cognigy-vibe `cognigy_create`).** `push_agent_tool` does NOT create it. Append it explicitly onto the LAST functional node of the branch — the Step 3 node for transactional/transfer; the Hangup for both end-call tools:
```
cognigy_create {
  resource_type: "node", flow_id: "<flowId>",
  body: { type: "aiAgentToolAnswer", mode: "append", target: "<lastFunctionalNodeId>", config: { answer: "{{JSON.stringify(context.toolResponse)}}", maxLoops: 4 } }
}
```
> **The `answer` field is mandatory.** It is the CognigyScript the node hands back to the LLM as the tool result; `{{JSON.stringify(context.toolResponse)}}` surfaces the object the Code node wrote. A bare `config: {}` returns an empty tool result and the LLM sees nothing back — see `explain("agent-tool-branch")` Step 3 / `explain("agent-tool-patterns")`.
After this, the chain is `aiAgentJobTool → [Step 2] → [Step 3] → aiAgentToolAnswer` (transactional/transfer), `aiAgentJobTool → [Hangup] → aiAgentToolAnswer` (`end_call`), or `aiAgentJobTool → [Say] → [Hangup] → aiAgentToolAnswer` (`end_call_resolved`). This is the canonical three-/four-node branch from plugin `explain("agent-tool-branch")`.

---

## §7 — MCP arg-name cheatsheet (the things that bite)

| MCP | Tool | Gotcha |
|---|---|---|
| NiCE | `list_resources` | `resourceType` is **singular** (`project`, `agent`, `flow`, `endpoint`, `llm_model`, `knowledge_store`, `extension`, `function`, `tool`, `conversation`). |
| cognigy-vibe | `cognigy_list` | `resource_type` accepts both singular (`flow`) and plural (`flows`) — the server normalises common singulars to their plural form. Prefer plural to match the Cognigy API directly. |
| NiCE | `create_ai_agent` | Returns `endpointUrl` with wrong subdomain — `cognigy-api-au1.nicecxone.com` 401s. Use `cognigy-endpoint-au1.nicecxone.com/<same token>`. |
| NiCE | `create_ai_agent` | Accepts ONLY `{ name, description, projectId?, knowledgeStoreReferenceId? }`. Agent rename + guardrails (1B) + ALL job fields (jobDescription/jobInstructions/LLM/temperature/maxTokens) go via `update_ai_agent` (§1.1 Step 3). `memoryContextInjection` + `toolChoice` are reachable by neither agent tool → §1.2 node patch. `locale` has no agent-tool home → §1.5(c). |
| NiCE | `create_tool` | **Alternative path (§1.3)** — canonical is cognigy-vibe `push_agent_tool`. Auto-pairs the answer node; always *creates* (NOT create-or-update). Requires `aiAgentId` + `toolType` + `config`. `config.parameters` is **stringified JSON**, not an object. `config.toolId` is the LLM-facing snake_case ID. Cannot set a visibility `condition`. Don't mix with the §6 `push_agent_tool` recipe in one branch. |
| NiCE | `manage_flow_nodes` | Supports `say`, `question`, `ifThenElse`, `lookup`, `setSessionContext`, `code`, `goTo`, `sleep`, `httpRequest`. NOT `once`, `onFirstExecution`, `afterwards`, `setSessionConfig`, `wait`, `hangup`. |
| NiCE | `manage_flow_nodes` | Say nodes: text is direct: `config: { text: "..." }`. Different from `cognigy_create`. |
| cognigy-vibe | `cognigy_create` | **Extension is auto-injected** for all known node types (`@cognigy/voicegateway2` for `setSessionConfig`/`hangup`, `cxone-utils` for `setHTMLAppState`/`initAppSession`, `@cognigy/basic-nodes` for `aiAgentJobTool`/`aiAgentToolAnswer`/`aiAgentJob`). You can omit `extension` in the body. Spelling it out also works. |
| cognigy-vibe | `cognigy_create` | **Insertion mode: use `mode: "append"` + `target: "<previousNodeId>"`** — inserts the new node AFTER target and auto-rewires the chain. `mode: "appendChild"` is for putting `aiAgentJobTool` as a child of `aiAgentJob`. **`insertAfter` / `insertBefore` are BROKEN on AU1** (return 500 "Error while reading ChartData"). See plugin `explain("node-positioning")`. |
| cognigy-vibe | `cognigy_create` | **`resource_type` is `"node"`** (plus a separate `flow_id` param) — NOT the path-form `"flows/<flowId>/chart/nodes"`. Path-form may work but is non-canonical. |
| cognigy-vibe | `cognigy_create` | Say config is **auto-normalised** — the tool accepts either flat `config.text` or nested `config.say.text` (array). |
| cognigy-vibe | `cognigy_create` | Don't author Code-node bodies here. As of v1.4.0, `push_code_node` CREATE mode (omit `node_id`; pass `flow_id`+`mode`+`target`+`label`) creates+positions+pushes a Code node in one call — no empty-`cognigy_create` step needed. |
| cognigy-vibe | Code node convention | Read/write contract (tool args namespace, `context.toolResponse`, `api.resolve` / `api.reject`, `api.log` vs `console.log`, no `fetch`) — see plugin `explain("code-node-patterns")`. Skill-specific shapes (success / no-match / disambiguation) live in §C.2. |
| cognigy-vibe | `cognigy_update` | Does an **always-fresh GET + deep merge** when `merge_config: true` is set. Patch deltas only; sibling fields stay intact. |
| cognigy-vibe | `cognigy_delete` | DELETE any resource including individual nodes. Used in §8 collision cleanup. |
| cognigy-vibe | `cognigy_invoke` | Named ops: `move`, `clone`, `train`, `inject`, `search`. `clone` will power the §1.0 fork lane once that ships; `search` for asset discovery (cheaper than `list` + filter). §1.8 knowledge wiring uses NiCE `manage_knowledge`, not `inject`. |
| cognigy-vibe | `push_code_node` | Reads `.js`/`.ts` → `config.code`. **v1.4.0: two modes** — CREATE (omit `node_id`; pass `flow_id`+`mode`+`target`+`label`) creates+positions+pushes in one call; UPDATE (pass `node_id`) pushes to an existing node with conflict detection. Required: `script_file`, `flow_id`. Preferred for ALL Code-node body population. |
| cognigy-vibe | `push_html_node` | Reads `.html` file → `setHTMLAppState` node body. Params are snake_case, **all required**: `html_file`, `node_id`, `flow_id`. Required for §1.4b xApp scene authoring. |
| cognigy-vibe | `push_agent_tool` | Reads a local `.tool.json` → create/update an `aiAgentJobTool` node. **Canonical tool-authoring path (§1.3).** CREATE: pass `job_node_id`; UPDATE: pass `node_id` (idempotent re-push, additive config PATCH). Creates the tool node only — append `aiAgentToolAnswer` (§6 Step 4). No `aiAgentId` param. |
| cognigy-vibe | `get_flow_chart` | Returns shape depends on `format` param: `"hierarchy"` (default) → `{ hierarchy: "..." }` only; `"raw"` → `{ nodes: [...], relations: [...] }` only; `"both"` → all three fields. Key is `hierarchy`, NOT `hierarchyString`. Use `format: "both"` for as-built generation (§1.6); use `format: "raw"` when walking node IDs (§1.7 Phase A). Required AFTER `create_ai_agent` (find `aiAgentJob` node ID) and AFTER creating `once` (find auto-created `onFirstExecution` / `afterwards` IDs). |
| NiCE | `delete_resource` | `resourceType: "tool"` + `id: <aiAgentJobToolNodeId>` + `aiAgentId`. Use to clean up duplicate tools at the resource level. For individual node-level cleanup, prefer cognigy-vibe `cognigy_delete`. |
| NiCE | `manage_packages` | Two-call export: `operation: "list_exportable"` to discover resource IDs, then `operation: "export"` with `resourceIds` + `outputPath` (absolute path) + `waitForCompletion: true`. `includeDependencies` defaults true. Returns `{ savedPath }`. As of this refactor, the package zip is a **backup artifact** — as-built generation runs off `get_flow_chart`, not the zip. See §1.6. |
| NiCE | `manage_knowledge` | Cognigy built-in Knowledge AI (§1.8). `operation: "create_store"` with `projectId` + `agentId` + `name` + `sources: [{ name, text }]` (ingest local `knowledge/<slug>.md` bodies). Pair with `manage_settings { operation: "set_knowledge_ai", enabled: true, knowledgeStoreId }`. No CXone Expert publishing — that belongs in a future `knowledge@nice` skill. |

---

## §8 — Reconciling with UI prototypes the user may build in parallel

If the user has prototyped tool branches in the UI before / during the build, there will be `toolId` collisions with anything `push_agent_tool` adds. Duplicate `toolId` within an agent breaks tool selection.

**Recipe:**

1. After §1.3, run `get_flow_chart` and look for `aiAgentJobTool` nodes you didn't create. For each, `cognigy_get` on its node ID and read `config.toolId`.
2. If a duplicate `toolId` exists, **delete YOURS** at the node level via `cognigy_delete`:
   ```
   cognigy_delete {
     resource_type: "node",
     flow_id: "<flowId>",
     resource_id: "<yourAiAgentJobToolNodeId>"
   }
   ```
   (NiCE `delete_resource { resourceType: "tool", id, aiAgentId }` still works for agent-resource-level cleanup, but `cognigy_delete` is the cleaner node-level path when reconciling against an in-UI prototype.)
3. **Update the user's prototype in-place** via `cognigy_update` (delta-only, deep merge per §1.2):
   - Set a clean `description`
   - Fix `parameters` schema (replace UI-template junk with `"{\"type\":\"object\",\"properties\":{},\"required\":[]}"`)
   - Update `label` to match `toolId`
4. **Keep any existing Say + Hangup chain** — the tone may be exactly what's wanted. Only override if clearly placeholder.
5. **If the user's prototype tool isn't already represented by a JSON file** under `tools/`, write one to disk now (mirroring the live config) so the demo folder stays the single source of truth and future re-runs are idempotent via `push_agent_tool` (re-push the `.tool.json` with `node_id`).

---

## §9 — toolChoice: `auto`, not `required`

Use `toolChoice: "auto"` (lowercase) on the AI Agent Job Node. Do **NOT** use `required`.

`required` forces the LLM to call a tool every turn, which causes the persona to chain tools without speaking text between them — if a transactional tool needs a follow-on read-back (receipt, claim status, hardship offer), `required` skips it. With `auto`, the LLM can interleave a read-back between the transactional tool and the end-call tool.

First-turn tool enforcement is handled by the init chain (Initialize Session pre-loads `context.customer`) plus persona guardrails in `instructions`, not by forcing toolChoice.

---

## §10 — Output to user (hand-back format)

```
✅ Built — [CUSTOMER]_Demo_BH

Project ID:   <id>
Agent ID:     <id>  ([Persona] — referenceId <ref>)
Flow ID:      <mongo id> (referenceId <ref>)
Endpoint URL: https://cognigy-endpoint-au1.nicecxone.com/<token>

Demo folder: Demo Builds/[customer]-demo/
  Scope + design artifacts:
    - [Customer]-[DemoType]-demo-plan.md          ← §A (scope-demo)
    - [Customer]-agent-persona.md                 ← §B (with §2.5 empathy library verbatim)
    - [Customer]-agent-architecture.md            ← §B
    - [Customer]-context-schema.md                ← §B
    - [Customer]-agent-interfaces.md              ← §B
    - [Customer]-agent-contracts.md               ← §B
  Build artifacts:
    - brand-research.md                           ← §0.6
    - [customer]-empathy-library.md               ← §2.5 read-only reference export (NOT wired — edit persona.md + re-run §1.2 to change runtime)
    - tools/*.json                                ← every tool authored file-first (§1.3)
    - xapp/*.html                                 ← every xApp scene (§1.4b — only if interfaces named scenes)
    - knowledge/*.md                              ← FAQ topic bodies (§1.8 — only if knowledge gate opened)
  Documentation:
    - [CUSTOMER]_FLOW_INSERTS.md                  ← as-built generated from get_flow_chart
    - [customer]-baseline.md                      ← drift-detection snapshot
    - package/[customer]_Demo_BH.zip              ← package backup (manage_packages)

Tools wired: <comma-separated list including end_call + end_call_resolved + transfers + any use-case tools. NO separate search_*_faqs tool — knowledge retrieval is via built-in Knowledge AI on the Job Node when §1.8 runs.>
Init chain:  Start → Once → On First Time → Initialize Session → Set Session Config → Say Welcome → Wait → AI Agent → End
Patterns:    Shape-B tool branches ✓  Transfer reversed ✓  End-call pair ✓  No-match shape demonstrated ✓
             xApp scenes wired ✓ / N/A   Knowledge wired ✓ / N/A   Fork lane used ✓ / N/A

Smoke test: Phase A 12/12 ✓ (incl. agent description & instructions ≤1000 chars)  Phase B deterministic ✓  Advisories: <none | each probabilistic WARN with the turn + suggested manual check (per §1.7)>

Next steps (manual, in the Cognigy UI):
- Open the Interaction Panel on the [Persona] agent to smoke-test conversation flow
- (Optional) Configure Voice Preview (Settings → Voice Preview → Microsoft) before WebRTC demoing
- (If §1.8 fell through to manual UI step) Wire the knowledge store into the agent via the Cognigy UI — see [CUSTOMER]_FLOW_INSERTS.md §9
```

One paragraph. No further prose unless something failed during build.

---

## §11 — Cross-cutting conventions

Rules that apply across multiple sections and aren't owned by any single one. Section-specific rules live in their own section, not here.

**Naming:**
- **Project name:** `[CUSTOMER]_Demo_BH` — preserve original casing.
- **Folder name:** `[customer]-demo` — lowercase.
- **Agent name:** persona name only, no suffix.
- **Tool names:** `snake_case`, verb-led.

**Design:**
- **Mocks are deterministic.** Same outputs every run; don't randomise.
- **Init chain warning override.** The `cognigy://guide/flow-nodes` MCP guide says "NEVER add pre-agent nodes" — that warning is **wrong for this pattern**, ignore it. Every production-grade build in this pattern set uses the init chain (§1.5).
- **This skill body IS the reference build.** Do not cite historical customers as the quality benchmark. When a real build surfaces a better pattern, promote it back via `nice-build-retrospective`. Audit skills (`nice-audit-cognigy-build`, `nice-cognigy-health-check`) compare live builds against THIS skill body.

**Hands-off:**
- **DO call `talk_to_agent` — in §1.7 only.** Phase B's 3-turn smoke test is mandatory before hand-back. After §1.7 passes, the user's Interaction Panel session is exploratory, not first-time validation.
- **Do NOT configure Voice Preview / `manage_voice_gateway`.** Manual UI step.
- **Don't start building before the user says "yes / go / confirmed"** to the recap.
