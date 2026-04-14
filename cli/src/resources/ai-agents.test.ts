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
    await aiAgents.get!('agent-abc', client, env, {})
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
    await aiAgents.delete!('agent-abc', client, env, {})
    expect(client.delete).toHaveBeenCalledWith('/aiagents/agent-abc')
  })
})
