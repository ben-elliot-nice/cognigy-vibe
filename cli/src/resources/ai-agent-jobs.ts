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
