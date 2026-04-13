import type { CognigyClient, EnvConfig, ResourceHandlers } from '../lib/types.js'
import type { Flow, CreateFlowInput, UpdateFlowInput } from './flow.types.js'
export type { Flow }

function resolveProjectId(params: Record<string, unknown>, env: EnvConfig): string {
  const id = (params['projectId'] as string | undefined) ?? env.projectId
  if (!id) throw new Error('projectId is required — set COGNIGY_PROJECT_ID in .env or pass --projectId')
  return id
}

export const flows: ResourceHandlers = {
  async list(client, env, params) {
    const projectId = resolveProjectId(params, env)
    return client.get<Flow[]>(`/flows?projectId=${projectId}`)
  },

  async get(id, client) {
    return client.get<Flow>(`/flows/${id}`)
  },

  async create(params, client, env) {
    const projectId = resolveProjectId(params, env)
    const { projectId: _omit, ...rest } = params
    return client.post<Flow>('/flows', { ...rest, projectId })
  },

  async update(id, params, client) {
    return client.patch<Flow>(`/flows/${id}`, params)
  },

  async delete(id, client) {
    return client.delete(`/flows/${id}`)
  },

  operations: {
    async clone(id, _params, client) {
      return client.post<Flow>(`/flows/${id}/clone`, {})
    },
  },
}
