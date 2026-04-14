// cli/src/resources/projects.test.ts
import { describe, it, expect, vi } from 'vitest'
import { projects } from './projects.js'
import type { CognigyClient, EnvConfig } from '../lib/types.js'

const env: EnvConfig = {
  baseUrl: 'https://app.cognigy.ai',
  apiToken: 'test-token',
  projectId: 'proj-123',
}

const mockProject = {
  _id: 'proj-abc',
  name: 'Test Project',
}

function makeClient(overrides: Partial<CognigyClient> = {}): CognigyClient {
  return {
    get: vi.fn().mockResolvedValue(mockProject),
    post: vi.fn().mockResolvedValue(mockProject),
    patch: vi.fn().mockResolvedValue(mockProject),
    delete: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  }
}

describe('projects.list', () => {
  it('calls GET /projects', async () => {
    const client = makeClient()
    await projects.list!(client, env, {})
    expect(client.get).toHaveBeenCalledWith('/projects')
  })
})

describe('projects.get', () => {
  it('calls GET /projects/:id', async () => {
    const client = makeClient()
    await projects.get!('proj-abc', client, env, {})
    expect(client.get).toHaveBeenCalledWith('/projects/proj-abc')
  })
})

describe('projects.create', () => {
  it('calls POST /projects with name', async () => {
    const client = makeClient()
    await projects.create!({ name: 'New Project' }, client, env)
    expect(client.post).toHaveBeenCalledWith('/projects', { name: 'New Project' })
  })

  it('passes all supported fields', async () => {
    const client = makeClient()
    await projects.create!({ name: 'New Project', color: 'red' }, client, env)
    expect(client.post).toHaveBeenCalledWith('/projects', { name: 'New Project', color: 'red' })
  })
})

describe('projects.update', () => {
  it('calls PATCH /projects/:id with update params', async () => {
    const client = makeClient()
    await projects.update!('proj-abc', { name: 'Renamed' }, client, env)
    expect(client.patch).toHaveBeenCalledWith('/projects/proj-abc', { name: 'Renamed' })
  })
})

describe('projects.delete', () => {
  it('calls DELETE /projects/:id', async () => {
    const client = makeClient()
    await projects.delete!('proj-abc', client, env, {})
    expect(client.delete).toHaveBeenCalledWith('/projects/proj-abc')
  })
})
