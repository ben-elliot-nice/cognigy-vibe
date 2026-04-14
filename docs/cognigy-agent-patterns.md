# Common AI Agent Patterns

Reference patterns for structuring Cognigy AI Agent implementations.

---

## Concierge + Specialists Pattern

Multi-agent architecture with concierge as entry point routing to specialist jobs.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Inbound Contact                       │
│                      (Voice, WhatsApp, Web)                 │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  Concierge Flow │
                    │                 │
                    │ - Intent detect │
                    │ - Authenticate  │
                    │ - Gather context│
                    └────────┬────────┘
                             │
                ┌────────────┼────────────┐
                │            │            │
                ▼            ▼            ▼
        ┌───────────┐  ┌───────────┐  ┌───────────┐
        │ Specialist│  │ Specialist│  │ Specialist│
        │ Job 1     │  │ Job 2     │  │ Job N     │
        └───────────┘  └───────────┘  └───────────┘
```

### Concierge Agent

**Role**: Front-of-house orchestrator

**Tools** (routes to specialists):
- `route_to_specialist_1`
- `route_to_specialist_2`
- `route_to_specialist_n`
- `escalate_to_human`

**Capabilities**:
- Intent detection (Classic NLU or AI Agent)
- Customer authentication/identification
- Context gathering (vehicle details, account info, etc.)
- Intelligent routing
- Context preservation on handoff

### Specialist Agents

**Role**: Domain-specific experts

**Common Tool**: `return_to_concierge`
- Sends conversation back to concierge when query is out of scope
- All specialists share this identical tool

**Capabilities**:
- Domain-specific tasks (catalog search, booking, support, etc.)
- Tool calling for integrations
- Knowledge AI (job-specific knowledge store)
- xApp delivery (if applicable)

---

## Tool Granularity

Balance between demo buildability and real-world complexity.

### Granular Approach (Real-World)

Separate tools for each specific action:

```json
[
  {
    "toolId": "search_catalog_by_part_number",
    "description": "Search parts catalog by exact part number"
  },
  {
    "toolId": "search_catalog_by_vehicle",
    "description": "Search parts catalog by vehicle make/model/year"
  },
  {
    "toolId": "check_stock_by_branch",
    "description": "Check stock availability at specific branch"
  },
  {
    "toolId": "get_part_pricing",
    "description": "Get pricing for part (retail or trade)"
  }
]
```

**Pros**: Precise control, automates complexity
**Cons**: More tools to build, higher implementation effort

### Consolidated Approach (Demo-Friendly)

Fewer tools returning comprehensive data:

```json
[
  {
    "toolId": "search_catalog",
    "description": "Search parts catalog and retrieve part details, pricing, and stock. Returns comprehensive data for LLM to synthesize."
  }
]
```

**Pros**: Faster to build, fewer integration points
**Cons**: LLM must synthesize complex responses

### Recommendation

Ask user preference:
- "Do you prefer granular tools (more precise, more build effort) or consolidated tools (faster build, LLM synthesizes)?"

---

## Context Schema Examples

### E-Commerce Demo

```javascript
// Namespaced config (not LLM-visible)
context.ecommerce.config = {
  defaultBranch: "melbourne",
  supportedRegions: ["au", "nz"]
}

// Conversation data (LLM-visible via shortTermMemory)
context.shortTermMemory.customerProfile = {
  name: "",
  accountId: "",
  accountType: "retail" // or "trade"
}

context.shortTermMemory.activeCart = {
  items: [],
  total: 0
}

context.shortTermMemory.lastProductViewed = {}

// Transient data (per-turn)
input.productSearchResults = []
```

### Automotive Demo

```javascript
context.automotive.config = {
  supportedVehicleTypes: ["sedan", "suv", "ute", "van"]
}

context.shortTermMemory.customerProfile = {
  name: "",
  phone: "",
  registeredVehicles: []
}

context.shortTermMemory.currentVehicle = {
  reg: "",
  make: "",
  model: "",
  year: null
}

context.shortTermMemory.partsInContext = []
```

### Banking Demo

```javascript
context.banking.config = {
  supportedAccountTypes: ["checking", "savings", "credit"]
}

context.shortTermMemory.customerProfile = {
  name: "",
  customerId: "",
  authenticated: false
}

context.shortTermMemory.activeAccount = {
  accountNumber: "",
  balance: 0,
  transactions: []
}
```

---

## Specialist Job Patterns

### Information Retrieval Specialist

**Purpose**: Search catalogs, knowledge bases, databases

**Tools**:
- `search_catalog` / `search_knowledge`
- `get_item_details`
- `check_availability`

**Instructions**:
```
Help customers find information using available tools.
Gather search criteria (part number, vehicle details, product category).
Use search tools to retrieve relevant information.
Present findings clearly and offer follow-up assistance.
```

**xApp**: Send product images, specs, comparisons

---

### Transaction Specialist

**Purpose**: Execute transactions, process payments, create orders

**Tools**:
- All information retrieval tools (from previous phase)
- `create_order`
- `process_payment` (via xApp)
- `apply_discount`

**Instructions**:
```
Guide customers through checkout process.
Confirm order details (items, quantities, pricing).
Use payment tool to process transaction.
Provide order confirmation and delivery estimate.
```

**xApp**: Payment form, order summary, confirmation

---

### Booking Specialist

**Purpose**: Schedule appointments, reserve slots, manage calendar

**Tools**:
- `check_availability` (slots)
- `create_booking`
- `cancel_booking`
- `reschedule_booking`

**Instructions**:
```
Help customers schedule appointments.
Check availability for requested date/time.
Collect required details (name, contact, service type).
Confirm booking details and send confirmation.
```

**xApp**: Calendar view, booking confirmation

---

### Support Specialist

**Purpose**: Troubleshooting, account management, returns

**Tools**:
- `lookup_order`
- `process_return`
- `update_account`
- `escalate_to_human`

**Instructions**:
```
Assist customers with support requests.
Gather order/account details to look up information.
Use available tools to resolve issues.
If unable to resolve, escalate to human agent with conversation summary.
```

---

## Escalation to Human Pattern

### Tool Definition

```json
{
  "toolId": "escalate_to_human",
  "description": "Escalate to human agent when unable to resolve or customer requests human assistance",
  "useParameters": true,
  "parameters": {
    "type": "object",
    "properties": {
      "reason": {
        "type": "string",
        "description": "Reason for escalation (e.g., complex issue, customer request)"
      },
      "conversationSummary": {
        "type": "string",
        "description": "Summary of conversation up to this point for handoff to human agent"
      }
    },
    "required": ["reason", "conversationSummary"]
  }
}
```

### Usage Pattern

When AI Agent cannot resolve:
- Customer requests human explicitly
- Required information unavailable
- Complex/exception scenario not covered
- Technical issue preventing resolution

---

## Return to Concierge Pattern

### Tool Definition

```json
{
  "toolId": "return_to_concierge",
  "description": "Return user to concierge agent when query is outside this specialist's scope. Use when customer asks about topics not related to this specialist's domain.",
  "useParameters": false
}
```

### Usage Pattern

Every specialist has identical `return_to_concierge` tool.

When specialist detects out-of-scope query:
- Customer asks about different domain
- Specialist cannot handle request
- Re-routing needed

---

## Stub Agent Pattern

For demo phases where specialist is not yet built:

### Structure

Still create:
- AI Agent resource (for knowledge injection)
- AI Agent Job flow
- Job node with basic instructions
- Job-level knowledge store (optional)

### Tools

None or minimal:
- Stub agents may have no tools
- Or just `return_to_concierge`

### Instructions

```
You are a specialist agent for [domain].
This is a demonstration of your role.
For this demo phase, provide basic assistance and return to concierge for complex queries.
```

### Benefit

Enables knowledge-based responses even without full tool implementation.
