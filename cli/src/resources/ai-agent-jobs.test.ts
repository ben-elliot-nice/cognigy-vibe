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
