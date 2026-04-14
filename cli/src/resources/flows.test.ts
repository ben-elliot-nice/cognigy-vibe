import { describe, it, expect, vi } from 'vitest'
import { flows } from './flows.js'
import type { CognigyClient, EnvConfig } from '../lib/types.js'

const env: EnvConfig = {
  baseUrl: 'https://app.cognigy.ai',
  apiToken: 'test-token',
  projectId: 'proj-123',
}

const mockFlow = {
  _id: 'flow-abc',
  name: 'Test Flow',
  projectId: 'proj-123',
}

function makeClient(overrides: Partial<CognigyClient> = {}): CognigyClient {
  return {
    get: vi.fn().mockResolvedValue(mockFlow),
    post: vi.fn().mockResolvedValue(mockFlow),
    patch: vi.fn().mockResolvedValue(mockFlow),
    delete: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  }
}

describe('flows.list', () => {
  it('calls GET /flows?projectId with env.projectId', async () => {
    const client = makeClient()
    await flows.list!(client, env, {})
    expect(client.get).toHaveBeenCalledWith('/flows?projectId=proj-123')
  })

  it('uses projectId from params over env', async () => {
    const client = makeClient()
    await flows.list!(client, env, { projectId: 'proj-override' })
    expect(client.get).toHaveBeenCalledWith('/flows?projectId=proj-override')
  })

  it('throws when projectId is missing from both params and env', async () => {
    const client = makeClient()
    const envWithout: EnvConfig = { baseUrl: 'x', apiToken: 'y' }
    await expect(flows.list!(client, envWithout, {})).rejects.toThrow('projectId is required')
  })
})

describe('flows.get', () => {
  it('calls GET /flows/:id', async () => {
    const client = makeClient()
    await flows.get!('flow-abc', client, env, {})
    expect(client.get).toHaveBeenCalledWith('/flows/flow-abc')
  })
})

describe('flows.create', () => {
  it('calls POST /flows with name and projectId from env', async () => {
    const client = makeClient()
    await flows.create!({ name: 'New Flow' }, client, env)
    expect(client.post).toHaveBeenCalledWith('/flows', { name: 'New Flow', projectId: 'proj-123' })
  })

  it('uses projectId from params when provided, overriding env default', async () => {
    const client = makeClient()
    await flows.create!({ name: 'New Flow', projectId: 'proj-override' }, client, env)
    expect(client.post).toHaveBeenCalledWith('/flows', { name: 'New Flow', projectId: 'proj-override' })
  })

  it('throws when projectId is missing from both params and env', async () => {
    const client = makeClient()
    const envWithout: EnvConfig = { baseUrl: 'x', apiToken: 'y' }
    await expect(flows.create!({ name: 'New Flow' }, client, envWithout)).rejects.toThrow('projectId is required')
  })
})

describe('flows.update', () => {
  it('calls PATCH /flows/:id with update params', async () => {
    const client = makeClient()
    await flows.update!('flow-abc', { name: 'Renamed' }, client, env)
    expect(client.patch).toHaveBeenCalledWith('/flows/flow-abc', { name: 'Renamed' })
  })
})

describe('flows.delete', () => {
  it('calls DELETE /flows/:id', async () => {
    const client = makeClient()
    await flows.delete!('flow-abc', client, env, {})
    expect(client.delete).toHaveBeenCalledWith('/flows/flow-abc')
  })
})

describe('flows.operations.clone', () => {
  it('calls POST /flows/:id/clone with empty body', async () => {
    const client = makeClient()
    const op = flows.operations?.['clone']
    expect(op).toBeDefined()
    await op!('flow-abc', {}, client, env)
    expect(client.post).toHaveBeenCalledWith('/flows/flow-abc/clone', {})
  })
})
