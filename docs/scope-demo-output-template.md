# Demo Plan Output Template

Use this structure when generating the demo plan document in Phase 4 of the scope-demo skill. Populate every section. If something is unknown, state the assumption explicitly rather than leaving it blank.

**Filename:** `{CustomerName}-{DemoType}-demo-plan.md`

---

# {Customer Name} — {Demo Type} Demo Plan

## Overview

| Field | Value |
|-------|-------|
| Customer | {Customer name and industry} |
| Demo Date | {Date} |
| Demo Format | {Live call / Screen share / Walkthrough} |
| Primary Business Problem | {One sentence} |
| Key Differentiators to Prove | {Bullet list of 2–4 things this demo must demonstrate} |

---

## Demo Narrative & Phase Structure

### Story Arc

{2–3 sentences: who is the caller/user, what do they need, what happens, what's the "aha moment"?}

### Demo Phases

| Phase | Description | Key Moment |
|-------|-------------|------------|
| 1 | {Phase name and description} | {What should land with the audience} |
| 2 | {Phase name and description} | {What should land with the audience} |

### Scenario Details

**Scenario N: {Name}**
- **Persona:** {Who is the caller/user}
- **Entry point:** {Channel, trigger}
- **Agents involved:** {Concierge, Specialist: X, etc.}
- **Flow summary:** {Step-by-step in plain English}
- **Key moments:** {The 2–3 beats that should impress the audience}
- **xApp usage:** {Yes/No — if yes, what does it show and when}
- **Live agent handoff:** {Yes/No — if yes, describe the trigger}

---

## Agent Architecture

### Agent Map

| Agent | Role | Tools / Capabilities |
|-------|------|----------------------|
| Concierge | Auth, intent detection, routing | {e.g. account lookup, PIN validation} |
| Specialist: {Name} | {Domain} | {e.g. CRM lookup, case creation} |

### Routing Intent Map

| Intent | Routes To |
|--------|-----------|
| {Intent phrase} | {Agent name} |

---

## Technical Requirements

### Channels

| Channel | Purpose | Setup Notes |
|---------|---------|-------------|
| {Voice Gateway / Webchat / etc.} | {Primary / fallback} | {Any config notes} |

### Voice & xApp

- **SIP trunk required:** {Yes/No}
- **Phone number required:** {Yes/No}
- **xApp in scope:** {Yes/No — if yes, list scenes}

### Integrations

| System | Type | Demo approach (live / stub / fabricated) |
|--------|------|------------------------------------------|
| {CRM name} | CRM | {Stub — returns hardcoded account data} |

### Sample Data

{Describe what data needs to be prepared: account records, product info, FAQ docs, etc.}

### Knowledge AI

- **In scope:** {Yes/No}
- **Source documents:** {List docs to ingest, or note they need to be fabricated}

### Compliance / Regulatory

- **Regulatory context:** {Industry/market obligations — e.g. CoFI (NZ), FCA (UK), or "none"}
- **Key constraints:** {Bullet list of obligations affecting agent behaviour — e.g. one-offer limit per reason, mandatory disclosure before cancellation, two-pass confirmation for irreversible actions}
- **How encoded:** {Where these rules live — agent instructions, tool descriptions, or both}

---

## Cognigy Implementation Notes

### Features to Demonstrate

- [ ] {Feature 1}
- [ ] {Feature 2}

### Reusable Components

| Component | Source | Adaptation needed |
|-----------|--------|-------------------|
| {Flow / agent name} | {Previous demo / existing project} | {What needs changing} |

### Build Complexity

| Component | Estimate | Notes |
|-----------|----------|-------|
| {Concierge flow} | {1–2 days} | |
| **Total** | **{X days}** | |

---

## Success Criteria & Key Messages

### This demo succeeds if the audience leaves believing:

- [ ] {Key message 1}
- [ ] {Key message 2}

### Requirements checklist

- [ ] All {N} intents demonstrated
- [ ] Voice call completed end-to-end without manual intervention

---

## Open Questions & Assumptions

| Item | Status | Owner |
|------|--------|-------|
| {Question or assumption} | {Open / Assumed} | {Name or TBD} |

---

## Demo Operations

### Repeatability

- **Stateful actions in this demo:** {List any actions that change persistent state — e.g. cancellations, bookings, account updates — or "none (fully stateless)"}
- **Reset mechanism:** {How to restore demo to initial state before running again — e.g. "POST /reset-demo", "reload seed data", "n/a — all stub responses, no persistent state"}
- **Reset steps:** {Step-by-step — or "n/a"}

### Seed Data Requirements

| Record | Value | Purpose |
|--------|-------|---------|
| {e.g. Customer account} | {e.g. Policy ABC123, 4-year tenure, no recent claims} | {e.g. Enables retention offer scenario} |
