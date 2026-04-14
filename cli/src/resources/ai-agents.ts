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
