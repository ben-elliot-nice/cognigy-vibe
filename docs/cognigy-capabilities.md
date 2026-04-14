# Cognigy Platform Capabilities

Reference for demo scoping and design. Use this to understand what Cognigy can do and how to position it in a demo.

---

## Channels

| Channel | Notes |
|---------|-------|
| Voice Gateway | Preferred for voice demos — native SIP, fastest setup, most control |
| CXone Voice | Use when customer is on NICE CXone and wants native integration |
| Webchat | Default for screen-share demos; easy to embed, no telephony required |
| WhatsApp | High-impact for B2C use cases; requires WhatsApp Business API approval |
| SMS | Simple async; useful for appointment reminders, follow-up flows |
| Microsoft Teams | Enterprise internal use cases (IT helpdesk, HR) |
| Email | Async; good for ticketing workflows |
| LINE | APAC B2C |
| Viber | Eastern Europe / Middle East B2C |
| Facebook Messenger | B2C social; declining enterprise relevance |

---

## Voice Integration Patterns

### Cognigy Voice Gateway (preferred)
- Native SIP trunking directly into Cognigy
- Fastest demo setup — no NICE CXone dependency
- Full control over voice quality, barge-in, DTMF
- Best for: any customer not already on CXone, or where speed of demo setup matters

### CXone + Cognigy
- Cognigy acts as the AI brain; CXone handles telephony and agent desktop
- Required when: customer is NICE CXone and wants to see native ACD integration
- More moving parts — plan extra setup time

---

## xApp (Multimodal)

A smartphone UI that activates during a voice call — the caller gets a push notification/SMS link and sees a visual interface while the voice conversation continues.

**What it can show:**
- Carousels (product images, options)
- Adaptive cards (forms, structured data)
- Payment flows
- Maps / location pins
- Confirmation screens

**When to use in a demo:**
- When the customer has a use case where visual context adds value during a call (e.g. "let me show you the options on your phone")
- High-impact differentiator — most competitors don't have this
- Requires: Voice Gateway channel + xApp node in flow

---

## AI & NLU

### Classic NLU
- Intent + entity recognition
- Fast, deterministic, rules-based routing
- Best for: well-defined intents, high-volume contact centre routing

### LLM Nodes
- Call an LLM for complex reasoning, extraction, or generation mid-flow
- Can use Cognigy-hosted models or customer's own LLM
- Best for: nuanced slot-filling, summarisation, dynamic response generation

### AI Agents (Autonomous)
- LLM-powered agents with tools (functions they can call)
- Can handle multi-turn tasks without a rigid flow
- Best for: complex service tasks with variable paths (e.g. account management, troubleshooting)
- Each AI Agent has a system prompt, tools, and a handoff condition

---

## Knowledge AI

RAG (retrieval-augmented generation) over uploaded documents.

**Supported sources:**
- PDF, DOCX, TXT uploads
- URLs (web scraping)
- Plain text

**In a demo context:**
- Can use real customer docs (FAQs, product guides) if available
- Sanitised or fabricated content works fine for demo purposes
- Show: "ask it anything about our product" moments

---

## Multi-Agent Architecture

### Pattern: Concierge + Specialists

```
Caller → Concierge Agent
           ├── authenticate / capture context
           ├── route by intent
           ├── Specialist: Billing
           ├── Specialist: Technical Support
           └── Specialist: Retention
```

**Concierge responsibilities:**
- Authentication (PIN, account lookup)
- Intent detection (what does the caller want?)
- Context capture (account number, reason for call)
- Routing to correct specialist

**Specialist responsibilities:**
- Domain-specific logic
- Tool calls (CRM lookup, case creation, payment processing)
- Handoff back to concierge or to live agent

---

## Integrations

| Type | Options | Demo approach |
|------|---------|---------------|
| CRM | Salesforce, Dynamics, ServiceNow, Zendesk | HTTP Request node + stub API or sandbox |
| Ticketing | ServiceNow, Jira, Zendesk | Same as CRM |
| Payment | Stripe, custom PCI flow | Stub or xApp payment card form |
| Backend / ERP | SAP, custom APIs | HTTP Request + stub JSON response |
| Knowledge bases | Confluence, SharePoint, PDFs | Knowledge AI ingestion |

**For demos:** stub APIs (returning realistic hardcoded JSON) are almost always sufficient and much faster to set up than live integrations.

---

## Demo Environment Patterns

### Live Voice Call (highest impact)
- Dial a real number, speak to the bot, xApp activates on phone
- Requires: Voice Gateway setup, SIP trunk, phone number
- Impact: shows the real thing — hardest to dismiss

### Screen Share + Webchat
- Share screen, interact with webchat widget
- Quickest to set up, no telephony
- Impact: lower than voice, but good for use cases that are inherently digital

### Walkthrough / Simulation
- Pre-recorded or guided click-through
- Use only as fallback — reduces credibility

---

## Build Complexity Flags

| Feature | Complexity | Notes |
|---------|------------|-------|
| Basic webchat flow | Low | 1–2 days |
| Voice Gateway + NLU routing | Medium | 3–5 days |
| xApp multimodal | Medium | +1–2 days on top of voice |
| AI Agents (autonomous) | Medium-High | Depends on tool complexity |
| Live CRM integration | High | +3–5 days; prefer stub for demos |
| Knowledge AI | Low-Medium | 1 day if docs are ready |
| Multi-agent architecture | High | 5–10 days depending on scope |
