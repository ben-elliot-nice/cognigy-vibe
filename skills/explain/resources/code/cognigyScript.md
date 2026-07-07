---
topic: cognigyScript
description: interpolation contexts, what works where
group: code
---

## cognigyScript — CognigyScript Interpolation

### Syntax
{{context.namespace.field}}
{{input.data.fieldName}}
{{profile.firstName}}

### Condition fields vs text fields

Two different syntaxes depending on the field type:

| Field type | Syntax | Example |
|---|---|---|
| Text / message fields | `{{expression}}` | `Hello {{context.customer.name}}` |
| Condition fields | Bare expression — no `{{ }}` | `context.isVIP === true` |

Using `{{expr}}` in a condition field causes it to evaluate as a non-empty string,
which is always truthy — the branch always takes the same path regardless of the
actual value.

**Condition fields** (use bare expression):
- `ifThenElse` / `if` node `condition`
- `lookup` case values
- Tool `condition` field in `.tool.json`

**Text fields** (use `{{expression}}`):
- `say` node text
- AI Agent `instructions` / `jobInstructions` fields
- `setHTMLAppState` HTML content

### Confirmed working contexts
- Say node text field
- AI Agent Job instruction fields
- setHTMLAppState node HTML content
- Endpoint URL parameters (iframe src attribute values)
- Node labels (cosmetic only)

### NOT available
- Inside code node JavaScript bodies (use context.* variables directly in JS)
- Inside JSON string values in httpRequest payloadJSON (unconfirmed, test carefully)

### payloadJSON in httpRequest
CognigyScript interpolation in payloadJSON is UNCONFIRMED.
Safe approach: use a Code node to build the payload object and store in context,
then reference it from the httpRequest via the context variable.

### Common pattern: build in code, reference in node
  // Code node:
  context.smsPayload = {
    to: context.shortTermMemory.mobile,
    body: `Your code is ${context.otpCode}`
  };
  // httpRequest node config: use {{context.smsPayload}} if payloadJSON works,
  // or pipe through code node instead.
