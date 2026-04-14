# AI Agent Resource Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `ai-agent` as a supported resource type in the cognigy-claude-plugin CLI, enabling `cognigy list ai-agent`, `cognigy get ai-agent <id>`, `cognigy create ai-agent`, `cognigy update ai-agent <id>`, and `cognigy delete ai-agent <id>`.

**Architecture:** Follows the exact pattern of `flows.ts` — a single `ResourceHandlers` export wired into the CLI registry. The generated types file (`ai-agent.types.ts`) exists but has invalid TypeScript identifiers (hyphens in interface names) that must be fixed before the module can import from it. No operations (clone, etc.) are in scope for this MVP — YAGNI.

**Tech Stack:** TypeScript, Vitest, Cognigy REST API (`/v2.0/aiagents`)

---

## API Facts (from spec)

- `GET /v2.0/aiagents?projectId=` — list, requires projectId
- `GET /v2.0/aiagents/{aiAgentId}` — get by ID
- `POST /v2.0/aiagents` — create, body includes `projectId`
- `PATCH /v2.0/aiagents/{aiAgentId}` — update by ID
- `DELETE /v2.0/aiagents/{aiAgentId}` — delete by ID

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Fix | `cli/src/resources/ai-agent.types.ts` | Rename invalid identifiers (Ai-agent → AiAgent) |
| Create | `cli/src/resources/ai-agents.test.ts` | Vitest tests for all 5 verbs (written first — TDD) |
| Create | `cli/src/resources/ai-agents.ts` | ResourceHandlers module (list/get/create/update/delete) |
| Modify | `cli/src/index.ts` | Import + register `ai-agent: aiAgents` |
| Modify | `.claude-plugin/plugin.json` | Version bump |
| Modify | `cli/package.json` | Version bump |

---

### Task 1: Fix the generated types file

The extractor produced invalid TypeScript interface names with hyphens. Fix them to use PascalCase.

**Files:**
- Fix: `cli/src/resources/ai-agent.types.ts`

- [ ] **Step 1: Overwrite the file with corrected interface names**

Replace the entire file content at `/Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cli/src/resources/ai-agent.types.ts` with:

```typescript
// Generated from Cognigy OpenAPI spec — interface names manually corrected (hyphens → PascalCase)

export interface AiAgent {
  name?: string
  image?: string
  imageOptimizedFormat?: boolean
  knowledgeReferenceId?: string | null
  description?: string
  speakingStyle?: {
    completeness?: string
    formality?: string
  }
  voiceConfigs?: {
    ttsVoice?: string
    ttsLanguage?: string
    ttsVendor?: 'aws' | 'deepgram' | 'elevenlabs' | 'google' | 'microsoft' | 'nuance' | 'default' | 'custom' | 'none'
    ttsModel?: string
    ttsLabel?: string
    ttsDisableCache?: boolean
  }
  enableVoiceConfigs?: boolean
  enableAutoLanguageDetection?: boolean
  safetySettings?: {
    avoidHarmfulContent?: boolean
    avoidUngroundedContent?: boolean
    avoidCopyrightInfringements?: boolean
    preventJailbreakAndManipulation?: boolean
  }
  contactProfilesOption?: 'none' | 'selectedProfileFields' | 'completeProfile' | 'profileMemoriesOnly'
  contactProfilesSelected?: string[]
  instructions?: string
  _id?: string
  createdAt?: number
  lastChanged?: number
  createdBy?: string
  lastChangedBy?: string
}

export interface CreateAiAgentInput {
  name?: string
  image?: string
  imageOptimizedFormat?: boolean
  knowledgeReferenceId?: string | null
  description?: string
  speakingStyle?: {
    completeness?: string
    formality?: string
  }
  voiceConfigs?: {
    ttsVoice?: string
    ttsLanguage?: string
    ttsVendor?: 'aws' | 'deepgram' | 'elevenlabs' | 'google' | 'microsoft' | 'nuance' | 'default' | 'custom' | 'none'
    ttsModel?: string
    ttsLabel?: string
    ttsDisableCache?: boolean
  }
  enableVoiceConfigs?: boolean
  enableAutoLanguageDetection?: boolean
  safetySettings?: {
    avoidHarmfulContent?: boolean
    avoidUngroundedContent?: boolean
    avoidCopyrightInfringements?: boolean
    preventJailbreakAndManipulation?: boolean
  }
  contactProfilesOption?: 'none' | 'selectedProfileFields' | 'completeProfile' | 'profileMemoriesOnly'
  contactProfilesSelected?: string[]
  instructions?: string
  projectId?: string
}

export interface UpdateAiAgentInput {
  name?: string
  image?: string
  imageOptimizedFormat?: boolean
  knowledgeReferenceId?: string | null
  description?: string
  speakingStyle?: {
    completeness?: string
    formality?: string
  }
  voiceConfigs?: {
    ttsVoice?: string
    ttsLanguage?: string
    ttsVendor?: 'aws' | 'deepgram' | 'elevenlabs' | 'google' | 'microsoft' | 'nuance' | 'default' | 'custom' | 'none'
    ttsModel?: string
    ttsLabel?: string
    ttsDisableCache?: boolean
  }
  enableVoiceConfigs?: boolean
  enableAutoLanguageDetection?: boolean
  safetySettings?: {
    avoidHarmfulContent?: boolean
    avoidUngroundedContent?: boolean
    avoidCopyrightInfringements?: boolean
    preventJailbreakAndManipulation?: boolean
  }
  contactProfilesOption?: 'none' | 'selectedProfileFields' | 'completeProfile' | 'profileMemoriesOnly'
  contactProfilesSelected?: string[]
  instructions?: string
}
```

- [ ] **Step 2: Verify it compiles**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cli
npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors about `ai-agent.types.ts`

---

### Task 2: Write failing tests (TDD — RED)

Write the test file before the module exists so all tests fail with "module not found".

**Files:**
- Create: `cli/src/resources/ai-agents.test.ts`

- [ ] **Step 1: Create the test file**

```typescript
import { describe, it, expect, vi } from 'vitest'
import { aiAgents } from './ai-agents.js'
import type { CognigyClient, EnvConfig } from '../lib/types.js'

const env: EnvConfig = {
  baseUrl: 'https://app.cognigy.ai',
  apiToken: 'test-token',
  projectId: 'proj-123',
}

const mockAgent = {
  _id: 'agent-abc',
  name: 'Test Agent',
  projectId: 'proj-123',
}

function makeClient(overrides: Partial<CognigyClient> = {}): CognigyClient {
  return {
    get: vi.fn().mockResolvedValue(mockAgent),
    post: vi.fn().mockResolvedValue(mockAgent),
    patch: vi.fn().mockResolvedValue(mockAgent),
    delete: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  }
}

describe('aiAgents.list', () => {
  it('calls GET /aiagents?projectId with env.projectId', async () => {
    const client = makeClient()
    await aiAgents.list!(client, env, {})
    expect(client.get).toHaveBeenCalledWith('/aiagents?projectId=proj-123')
  })

  it('uses projectId from params over env', async () => {
    const client = makeClient()
    await aiAgents.list!(client, env, { projectId: 'proj-override' })
    expect(client.get).toHaveBeenCalledWith('/aiagents?projectId=proj-override')
  })

  it('throws when projectId is missing from both params and env', async () => {
    const client = makeClient()
    const envWithout: EnvConfig = { baseUrl: 'x', apiToken: 'y' }
    await expect(aiAgents.list!(client, envWithout, {})).rejects.toThrow('projectId is required')
  })
})

describe('aiAgents.get', () => {
  it('calls GET /aiagents/:id', async () => {
    const client = makeClient()
    await aiAgents.get!('agent-abc', client, env)
    expect(client.get).toHaveBeenCalledWith('/aiagents/agent-abc')
  })
})

describe('aiAgents.create', () => {
  it('calls POST /aiagents with name and projectId from env', async () => {
    const client = makeClient()
    await aiAgents.create!({ name: 'New Agent' }, client, env)
    expect(client.post).toHaveBeenCalledWith('/aiagents', { name: 'New Agent', projectId: 'proj-123' })
  })

  it('uses projectId from params when provided, overriding env default', async () => {
    const client = makeClient()
    await aiAgents.create!({ name: 'New Agent', projectId: 'proj-override' }, client, env)
    expect(client.post).toHaveBeenCalledWith('/aiagents', { name: 'New Agent', projectId: 'proj-override' })
  })

  it('throws when projectId is missing from both params and env', async () => {
    const client = makeClient()
    const envWithout: EnvConfig = { baseUrl: 'x', apiToken: 'y' }
    await expect(aiAgents.create!({ name: 'New Agent' }, client, envWithout)).rejects.toThrow('projectId is required')
  })
})

describe('aiAgents.update', () => {
  it('calls PATCH /aiagents/:id with update params', async () => {
    const client = makeClient()
    await aiAgents.update!('agent-abc', { name: 'Renamed' }, client, env)
    expect(client.patch).toHaveBeenCalledWith('/aiagents/agent-abc', { name: 'Renamed' })
  })
})

describe('aiAgents.delete', () => {
  it('calls DELETE /aiagents/:id', async () => {
    const client = makeClient()
    await aiAgents.delete!('agent-abc', client, env)
    expect(client.delete).toHaveBeenCalledWith('/aiagents/agent-abc')
  })
})
```

- [ ] **Step 2: Run tests — confirm they FAIL**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cli
npm test -- ai-agents 2>&1 | tail -20
```

Expected: FAIL with "Cannot find module './ai-agents.js'"

---

### Task 3: Write the module (GREEN)

**Files:**
- Create: `cli/src/resources/ai-agents.ts`

- [ ] **Step 1: Create the module**

```typescript
import type { CognigyClient, EnvConfig, ResourceHandlers } from '../lib/types.js'
import type { AiAgent, CreateAiAgentInput, UpdateAiAgentInput } from './ai-agent.types.js'
export type { AiAgent }

function resolveProjectId(params: Record<string, unknown>, env: EnvConfig): string {
  const id = (params['projectId'] as string | undefined) ?? env.projectId
  if (!id) throw new Error('projectId is required — set COGNIGY_PROJECT_ID in .env or pass --projectId')
  return id
}

export const aiAgents: ResourceHandlers = {
  async list(client, env, params) {
    const projectId = resolveProjectId(params, env)
    return client.get<AiAgent[]>(`/aiagents?projectId=${projectId}`)
  },

  async get(id, client) {
    return client.get<AiAgent>(`/aiagents/${id}`)
  },

  async create(params, client, env) {
    const projectId = resolveProjectId(params, env)
    const { projectId: _omit, ...rest } = params as CreateAiAgentInput & { projectId?: string }
    return client.post<AiAgent>('/aiagents', { ...rest, projectId })
  },

  async update(id, params, client) {
    return client.patch<AiAgent>(`/aiagents/${id}`, params as UpdateAiAgentInput)
  },

  async delete(id, client) {
    return client.delete(`/aiagents/${id}`)
  },
}
```

- [ ] **Step 2: Run tests — confirm they PASS**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cli
npm test -- ai-agents 2>&1 | tail -20
```

Expected: all 8 tests PASS

---

### Task 4: Wire into registry

**Files:**
- Modify: `cli/src/index.ts`

- [ ] **Step 1: Add import** (after the existing imports, line ~8):

Add this line with the other resource imports:
```typescript
import { aiAgents } from './resources/ai-agents.js'
```

- [ ] **Step 2: Add to registry** (inside the registry object):

```typescript
const registry: ResourceRegistry = {
  flow: flows,
  project: projects,
  chart: charts,
  node: nodes,
  'ai-agent': aiAgents,
}
```

- [ ] **Step 3: Run all tests — confirm nothing broken**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cli
npm test 2>&1 | tail -30
```

Expected: all tests pass (existing + new 8)

- [ ] **Step 4: Smoke test the CLI**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin
npx tsx cli/src/index.ts list ai-agent 2>&1 | head -5
```

Expected: JSON response from Cognigy (or a .env confirmation prompt — either is fine)

---

### Task 5: Version bump and commit

**Files:**
- Modify: `.claude-plugin/plugin.json` — bump version (e.g. `1.1.7` → `1.1.8`)
- Modify: `cli/package.json` — bump same version

- [ ] **Step 1: Bump `.claude-plugin/plugin.json`**

Change `"version"` value to the next patch: current is `1.1.7` → `1.1.8`

- [ ] **Step 2: Bump `cli/package.json`**

Change `"version"` value to `1.1.8`

- [ ] **Step 3: Stage all files**

```bash
git -C /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin add \
  cli/src/resources/ai-agent.types.ts \
  cli/src/resources/ai-agents.ts \
  cli/src/resources/ai-agents.test.ts \
  cli/src/index.ts \
  .claude-plugin/plugin.json \
  cli/package.json \
  docs/superpowers/plans/2026-04-14-ai-agent-resource.md
```

- [ ] **Step 4: Commit**

```bash
git -C /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin commit -m "feat: add ai-agent resource module with list/get/create/update/delete"
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
- ✅ list — GET /aiagents?projectId=
- ✅ get — GET /aiagents/{id}
- ✅ create — POST /aiagents with projectId
- ✅ update — PATCH /aiagents/{id}
- ✅ delete — DELETE /aiagents/{id}
- ✅ Types file fixed (hyphen → PascalCase)
- ✅ Tests written before module (TDD)
- ✅ Wired into registry as `ai-agent`
- ✅ Version bump in both files
- ✅ Commit + push + submodule update
- ⚠️ `/v2.0/aiagents/{aiAgentId}/jobs` — deliberately excluded (YAGNI; add as sub-resource later if needed)
- ⚠️ `/v2.0/aiagents/hire` and `/v2.0/aiagents/validatename` — excluded (YAGNI)

**Placeholder scan:** None. All code blocks are complete and exact.

**Type consistency:** `AiAgent` used in all three places (module import, get return type, create return type). `resolveProjectId` signature matches `flows.ts` exactly.
