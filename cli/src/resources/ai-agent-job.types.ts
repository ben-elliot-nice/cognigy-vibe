// Manually written — extract-resource-types.ts cannot generate from list-only endpoints

export interface AiAgentJobTool {
  _id?: string
  referenceId?: string
  type?: string
  label?: string
  comment?: string
  commentColor?: string
  analyticsLabel?: string | null
  isDisabled?: boolean
  isEntryPoint?: boolean
  extension?: string
  config?: Record<string, unknown>
}

export interface AiAgentJob {
  _id?: string
  referenceId?: string
  type?: string
  label?: string
  comment?: string
  commentColor?: string
  analyticsLabel?: string | null
  isDisabled?: boolean
  isEntryPoint?: boolean
  extension?: string
  config?: Record<string, unknown>
  tools?: AiAgentJobTool[]
}
