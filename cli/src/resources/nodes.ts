import type { CognigyClient, EnvConfig, ResourceHandlers } from '../lib/types.js'
import type { Node, CreateNodeInput, UpdateNodeInput } from './node.types.js'
export type { Node }

function resolveFlowId(params: Record<string, unknown>, env: EnvConfig): string {
  const id = (params['flowId'] as string | undefined) ?? env.flowId
  if (!id) throw new Error('flowId is required — set COGNIGY_FLOW_ID in .env or pass --flowId')
  return id
}

export const nodes: ResourceHandlers = {
  requires: ['flowId'],

  async list(client, env, params) {
    const flowId = resolveFlowId(params, env)
    return client.get<Node[]>(`/flows/${flowId}/chart/nodes`)
  },

  async get(id, client, env, params) {
    const flowId = resolveFlowId(params, env)
    return client.get<Node>(`/flows/${flowId}/chart/nodes/${id}`)
  },

  async create(params, client, env) {
    const flowId = resolveFlowId(params, env)
    const { flowId: _omit, ...rest } = params
    return client.post<Node>(`/flows/${flowId}/chart/nodes`, rest)
  },

  async update(id, params, client, env) {
    const flowId = resolveFlowId(params, env)
    const { flowId: _omit, ...rest } = params
    return client.patch<Node>(`/flows/${flowId}/chart/nodes/${id}`, rest)
  },

  async delete(id, client, env, params) {
    const flowId = resolveFlowId(params, env)
    return client.delete(`/flows/${flowId}/chart/nodes/${id}`)
  },

  operations: {
    async move(id, params, client, env) {
      const flowId = resolveFlowId(params, env)
      const { flowId: _omit, ...rest } = params
      return client.post(`/flows/${flowId}/chart/nodes/${id}/move`, rest)
    },
  },
}
