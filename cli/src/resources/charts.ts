import type { ResourceHandlers } from '../lib/types.js'

interface ChartNode {
  _id: string
  type?: string
  label?: string
}

interface ChartRelation {
  _id: string
  node: string
  children: string[]
  next?: string | null
}

interface Chart {
  nodes: ChartNode[]
  relations: ChartRelation[]
}

export const charts: ResourceHandlers = {
  requires: ['flowId'],

  async get(_id, client, env, params) {
    const flowId = (params['flowId'] as string | undefined) ?? env.flowId
    if (!flowId) throw new Error('flowId is required — set COGNIGY_FLOW_ID in .env or pass --flowId')
    return client.get<Chart>(`/flows/${flowId}/chart`)
  },
}
