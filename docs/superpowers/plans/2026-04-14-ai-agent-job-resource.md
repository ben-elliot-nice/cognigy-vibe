# AI Agent Job Resource Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `ai-agent-job` as a supported resource type in the cognigy-claude-plugin CLI, enabling `cognigy list ai-agent-job --aiAgentId <id>`.

**Architecture:** List-only sub-resource of `ai-agent`. Follows the `nodes.ts` sub-resource pattern — declares `requires: ['aiAgentId']`, reads parent ID from params. The types extractor cannot generate from a list-only endpoint, so the types file is written manually. Only `list` is implemented (the spec has no get/create/update/delete for this path).

**Tech Stack:** TypeScript, Vitest, Cognigy REST API (`GET /v2.0/aiagents/{aiAgentId}/jobs`)

---

## API Facts (from spec)

- `GET /v2.0/aiagents/{aiAgentId}/jobs` — list jobs for an AI agent. Returns an array.
- Response item fields: `_id`, `referenceId`, `type`, `label`, `comment`, `isDisabled`, `isEntryPoint`, `extension`, `config`, `tools[]`
- No create, update, delete, or get-by-ID endpoints exist for jobs.

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `cli/src/resources/ai-agent-job.types.ts` | Manual type definitions (list-only, extractor not applicable) |
| Create | `cli/src/resources/ai-agent-jobs.test.ts` | Vitest test — list only (2 cases) |
| Create | `cli/src/resources/ai-agent-jobs.ts` | ResourceHandlers with list only |
| Modify | `cli/src/index.ts` | Import + register `'ai-agent-job': aiAgentJobs` |
| Modify | `.claude-plugin/plugin.json` | Version bump |
| Modify | `cli/package.json` | Version bump |

---

### Task 1: Write types file manually

The extractor fails on list-only sub-resources. Write it by hand from the spec response shape.

**Files:**
- Create: `cli/src/resources/ai-agent-job.types.ts`

- [ ] **Step 1: Create the types file**

```typescript
// Manually written — extract-resource-types.ts cannot generate from list-only endpoints

export interface AiAgentJobTool {
  _id?: string
  referenceId?: string
  type?: string
  label?: string
  comment?: string
  commentColor?: string
  analyticsLabel?: string | null
  isDisabled?: boolean
  isEntryPoint?: boolean
  extension?: string
  config?: Record<string, unknown>
}

export interface AiAgentJob {
  _id?: string
  referenceId?: string
  type?: string
  label?: string
  comment?: string
  commentColor?: string
  analyticsLabel?: string | null
  isDisabled?: boolean
  isEntryPoint?: boolean
  extension?: string
  config?: Record<string, unknown>
  tools?: AiAgentJobTool[]
}
```

- [ ] **Step 2: Verify it compiles**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cli && npx tsc --noEmit 2>&1 | head -10
```

Expected: no errors from `ai-agent-job.types.ts`

---

### Task 2: Write failing tests (TDD RED)

**Files:**
- Create: `cli/src/resources/ai-agent-jobs.test.ts`

- [ ] **Step 1: Create the test file**

```typescript
import { describe, it, expect, vi } from 'vitest'
import { aiAgentJobs } from './ai-agent-jobs.js'
import type { CognigyClient, EnvConfig } from '../lib/types.js'

const env: EnvConfig = {
  baseUrl: 'https://app.cognigy.ai',
  apiToken: 'test-token',
}

const mockJobs = [
  { _id: 'job-abc', label: 'Claims Job', type: 'aiAgentJob' },
]

function makeClient(overrides: Partial<CognigyClient> = {}): CognigyClient {
  return {
    get: vi.fn().mockResolvedValue(mockJobs),
    post: vi.fn().mockResolvedValue({}),
    patch: vi.fn().mockResolvedValue({}),
    delete: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  }
}

describe('aiAgentJobs.list', () => {
  it('calls GET /aiagents/:aiAgentId/jobs', async () => {
    const client = makeClient()
    await aiAgentJobs.list!(client, env, { aiAgentId: 'agent-abc' })
    expect(client.get).toHaveBeenCalledWith('/aiagents/agent-abc/jobs')
  })

  it('throws when aiAgentId is missing', async () => {
    const client = makeClient()
    await expect(aiAgentJobs.list!(client, env, {})).rejects.toThrow('aiAgentId is required')
  })
})
```

- [ ] **Step 2: Run tests — confirm they FAIL**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cli && npm test -- ai-agent-jobs 2>&1 | tail -10
```

Expected: FAIL with "Cannot find module './ai-agent-jobs.js'"

---

### Task 3: Write the module (GREEN)

**Files:**
- Create: `cli/src/resources/ai-agent-jobs.ts`

- [ ] **Step 1: Create the module**

```typescript
import type { CognigyClient, EnvConfig, ResourceHandlers } from '../lib/types.js'
import type { AiAgentJob } from './ai-agent-job.types.js'
export type { AiAgentJob }

function resolveAiAgentId(params: Record<string, unknown>): string {
  const id = params['aiAgentId'] as string | undefined
  if (!id) throw new Error('aiAgentId is required — set COGNIGY_AI_AGENT_ID in .env or pass --aiAgentId')
  return id
}

export const aiAgentJobs: ResourceHandlers = {
  requires: ['aiAgentId'],

  async list(client: CognigyClient, _env: EnvConfig, params: Record<string, unknown>) {
    const aiAgentId = resolveAiAgentId(params)
    return client.get<AiAgentJob[]>(`/aiagents/${aiAgentId}/jobs`)
  },
}
```

- [ ] **Step 2: Run tests — confirm they PASS**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cli && npm test -- ai-agent-jobs 2>&1 | tail -10
```

Expected: 2 tests PASS

---

### Task 4: Wire into registry

**Files:**
- Modify: `cli/src/index.ts`

- [ ] **Step 1: Add import** (with other resource imports):

```typescript
import { aiAgentJobs } from './resources/ai-agent-jobs.js'
```

- [ ] **Step 2: Add to registry**:

```typescript
'ai-agent-job': aiAgentJobs,
```

- [ ] **Step 3: Run all tests**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cli && npm test 2>&1 | tail -5
```

Expected: all tests pass.

- [ ] **Step 4: Type-check**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cli && npx tsc --noEmit
```

Expected: clean.

---

### Task 5: Version bump, commit, push, submodule update

**Files:**
- Modify: `.claude-plugin/plugin.json` — `1.1.9` → `1.2.0`
- Modify: `cli/package.json` — `1.1.9` → `1.2.0`

- [ ] **Step 1: Bump `.claude-plugin/plugin.json`** — `"version": "1.1.9"` → `"version": "1.2.0"`

- [ ] **Step 2: Bump `cli/package.json`** — `"version": "1.1.9"` → `"version": "1.2.0"`

- [ ] **Step 3: Stage all files**

```bash
git -C /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin add \
  cli/src/resources/ai-agent-job.types.ts \
  cli/src/resources/ai-agent-jobs.ts \
  cli/src/resources/ai-agent-jobs.test.ts \
  cli/src/index.ts \
  .claude-plugin/plugin.json \
  cli/package.json \
  docs/superpowers/plans/2026-04-14-ai-agent-job-resource.md
```

- [ ] **Step 4: Commit**

```bash
git -C /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin commit -m "feat: add ai-agent-job sub-resource with list"
```

- [ ] **Step 5: Push**

```bash
git -C /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin push
```

- [ ] **Step 6: Update submodule**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/nice-claude-marketplace && git submodule update --remote && git add plugins && git commit -m "Further cognigy plugins revisions" && git push
```

---

## Self-Review

**Spec coverage:**
- ✅ list — GET /aiagents/{aiAgentId}/jobs
- ✅ requires: ['aiAgentId'] declared
- ✅ Only `list` implemented — no other verbs exist in spec
- ✅ Types written manually — extractor not applicable for list-only endpoints
- ✅ Registry key: `ai-agent-job` (singular)
- ✅ Version bump, commit, push, submodule

**Placeholder scan:** None. All code blocks complete.

**Type consistency:** `AiAgentJob` used in module import and list return type. `AiAgentJobTool` used only within `AiAgentJob.tools[]`.
