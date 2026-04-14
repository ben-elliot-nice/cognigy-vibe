// Generated from Cognigy OpenAPI spec — interface names manually corrected (hyphens → PascalCase)

export interface AiAgent {
  name?: string
  image?: string
  imageOptimizedFormat?: boolean
  knowledgeReferenceId?: string | null
  description?: string
  speakingStyle?: {
    completeness?: string
    formality?: string
  }
  voiceConfigs?: {
    ttsVoice?: string
    ttsLanguage?: string
    ttsVendor?: 'aws' | 'deepgram' | 'elevenlabs' | 'google' | 'microsoft' | 'nuance' | 'default' | 'custom' | 'none'
    ttsModel?: string
    ttsLabel?: string
    ttsDisableCache?: boolean
  }
  enableVoiceConfigs?: boolean
  enableAutoLanguageDetection?: boolean
  safetySettings?: {
    avoidHarmfulContent?: boolean
    avoidUngroundedContent?: boolean
    avoidCopyrightInfringements?: boolean
    preventJailbreakAndManipulation?: boolean
  }
  contactProfilesOption?: 'none' | 'selectedProfileFields' | 'completeProfile' | 'profileMemoriesOnly'
  contactProfilesSelected?: string[]
  instructions?: string
  _id?: string
  createdAt?: number
  lastChanged?: number
  createdBy?: string
  lastChangedBy?: string
}

export interface CreateAiAgentInput {
  name?: string
  image?: string
  imageOptimizedFormat?: boolean
  knowledgeReferenceId?: string | null
  description?: string
  speakingStyle?: {
    completeness?: string
    formality?: string
  }
  voiceConfigs?: {
    ttsVoice?: string
    ttsLanguage?: string
    ttsVendor?: 'aws' | 'deepgram' | 'elevenlabs' | 'google' | 'microsoft' | 'nuance' | 'default' | 'custom' | 'none'
    ttsModel?: string
    ttsLabel?: string
    ttsDisableCache?: boolean
  }
  enableVoiceConfigs?: boolean
  enableAutoLanguageDetection?: boolean
  safetySettings?: {
    avoidHarmfulContent?: boolean
    avoidUngroundedContent?: boolean
    avoidCopyrightInfringements?: boolean
    preventJailbreakAndManipulation?: boolean
  }
  contactProfilesOption?: 'none' | 'selectedProfileFields' | 'completeProfile' | 'profileMemoriesOnly'
  contactProfilesSelected?: string[]
  instructions?: string
  projectId?: string
}

export interface UpdateAiAgentInput {
  name?: string
  image?: string
  imageOptimizedFormat?: boolean
  knowledgeReferenceId?: string | null
  description?: string
  speakingStyle?: {
    completeness?: string
    formality?: string
  }
  voiceConfigs?: {
    ttsVoice?: string
    ttsLanguage?: string
    ttsVendor?: 'aws' | 'deepgram' | 'elevenlabs' | 'google' | 'microsoft' | 'nuance' | 'default' | 'custom' | 'none'
    ttsModel?: string
    ttsLabel?: string
    ttsDisableCache?: boolean
  }
  enableVoiceConfigs?: boolean
  enableAutoLanguageDetection?: boolean
  safetySettings?: {
    avoidHarmfulContent?: boolean
    avoidUngroundedContent?: boolean
    avoidCopyrightInfringements?: boolean
    preventJailbreakAndManipulation?: boolean
  }
  contactProfilesOption?: 'none' | 'selectedProfileFields' | 'completeProfile' | 'profileMemoriesOnly'
  contactProfilesSelected?: string[]
  instructions?: string
}
