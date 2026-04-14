#!/usr/bin/env node
import { findEnvFile, loadEnv } from './lib/env.js'
import { createClient } from './lib/client.js'
import type { ResourceHandlers, ResourceRegistry } from './lib/types.js'
import { flows } from './resources/flows.js'
import { projects } from './resources/projects.js'
import { charts } from './resources/charts.js'
import { nodes } from './resources/nodes.js'
import { aiAgents } from './resources/ai-agents.js'
import { aiAgentJobs } from './resources/ai-agent-jobs.js'

// Resource registry — add new modules here as they're generated
const registry: ResourceRegistry = {
  flow: flows,
  project: projects,
  chart: charts,
  node: nodes,
  'ai-agent': aiAgents,
  'ai-agent-job': aiAgentJobs,
}

function parseFlags(args: string[]): Record<string, unknown> {
  const flags: Record<string, unknown> = {}
  for (let i = 0; i < args.length; i++) {
    const arg = args[i]
    if (arg?.startsWith('--')) {
      const key = arg.slice(2)
      const value = args[i + 1]
      if (value && !value.startsWith('--')) {
        try {
          flags[key] = JSON.parse(value)
        } catch {
          flags[key] = value
        }
        i++
      }
    }
  }
  return flags
}

function toEnvVarName(camelKey: string): string {
  return 'COGNIGY_' + camelKey.replace(/([A-Z])/g, '_$1').toUpperCase()
}

function validateRequires(resource: string, handlers: ResourceHandlers, flags: Record<string, unknown>, env: Record<string, string | undefined>): void {
  for (const key of (handlers.requires ?? [])) {
    if (!flags[key] && !env[key]) {
      fail(`'${resource}' requires --${key} or ${toEnvVarName(key)} to be set`)
    }
  }
}

async function runInit(): Promise<void> {
  const { existsSync, writeFileSync } = await import('fs')
  const { resolve } = await import('path')
  const envPath = resolve(process.cwd(), '.env')

  if (existsSync(envPath)) {
    output({ message: '.env already exists — skipping', path: envPath })
    return
  }

  const template = [
    '# Cognigy Claude Plugin — Project Configuration',
    '',
    '# Required',
    'COGNIGY_BASE_URL=https://app.cognigy.ai',
    'COGNIGY_API_TOKEN=',
    '',
    '# Optional defaults (overridable per CLI call)',
    'COGNIGY_PROJECT_ID=',
    'COGNIGY_FLOW_ID=',
  ].join('\n') + '\n'

  writeFileSync(envPath, template)
  output({ message: '.env created', path: envPath })
}

function output(data: unknown): void {
  console.log(JSON.stringify(data, null, 2))
}

function fail(message: string, exitCode = 1): never {
  console.error(JSON.stringify({ error: message }))
  process.exit(exitCode)
}

async function main(): Promise<void> {
  const [, , verb, resource, thirdArg, ...rest] = process.argv

  if (verb === 'init') {
    await runInit()
    return
  }

  if (!verb || !resource) {
    fail('Usage: cognigy <verb> <resource> [id] [--option value ...]')
  }

  const flags = parseFlags([thirdArg ?? '', ...rest].filter(Boolean))
  const explicitEnvPath = flags['env-path'] as string | undefined
  delete flags['env-path']  // don't forward meta-flags to resource handlers

  // Resolve .env
  let envPath: string
  if (explicitEnvPath) {
    envPath = explicitEnvPath
  } else {
    const found = findEnvFile(process.cwd())
    if (!found) {
      fail('No .env file found. Run: cognigy init')
    }
    if (found.fromWalk) {
      output({ requiresConfirmation: true, path: found.path })
      process.exit(2)
    }
    envPath = found.path
  }

  const env = loadEnv(envPath)
  const client = createClient(env)

  // Accept plural resource names (e.g. "projects" → "project")
  const resolvedResource = registry[resource] ? resource : resource.replace(/s$/, '')
  const handlers = registry[resolvedResource]
  if (!handlers) {
    fail(`Unknown resource: "${resource}". Available: ${Object.keys(registry).join(', ') || 'none registered yet'}`)
  }

  // Validate required parent IDs before dispatch
  validateRequires(resolvedResource, handlers, flags, env as unknown as Record<string, string | undefined>)

  // Determine if thirdArg is an ID (not a flag)
  const id = thirdArg && !thirdArg.startsWith('--') ? thirdArg : undefined

  switch (verb) {
    case 'list': {
      if (!handlers.list) fail(`Resource "${resource}" does not support list`)
      output(await handlers.list(client, env, flags))
      break
    }
    case 'get': {
      // Resources with `requires` use params for identification — no positional ID needed
      if (!handlers.requires?.length && !id) fail(`get requires an ID: cognigy get ${resource} <id>`)
      if (!handlers.get) fail(`Resource "${resource}" does not support get`)
      output(await handlers.get(id ?? '', client, env, flags))
      break
    }
    case 'create': {
      if (!handlers.create) fail(`Resource "${resource}" does not support create`)
      output(await handlers.create(flags, client, env))
      break
    }
    case 'update': {
      if (!id) fail(`update requires an ID: cognigy update ${resource} <id> --field value`)
      if (!handlers.update) fail(`Resource "${resource}" does not support update`)
      output(await handlers.update(id, flags, client, env))
      break
    }
    case 'delete': {
      if (!id) fail(`delete requires an ID: cognigy delete ${resource} <id>`)
      if (!handlers.delete) fail(`Resource "${resource}" does not support delete`)
      await handlers.delete(id, client, env, flags)
      output({ deleted: true, resource: resolvedResource, id })
      break
    }
    case 'invoke': {
      if (!id) fail(`invoke requires an ID: cognigy invoke ${resource} <id> --op <operation>`)
      const op = flags['op'] as string | undefined
      if (!op) fail(`invoke requires --op <operation>: cognigy invoke ${resource} <id> --op <operation>`)
      delete flags['op']  // don't forward meta-flag to operation handler
      if (!handlers.operations) fail(`Resource "${resource}" has no operations`)
      const handler = handlers.operations[op]
      if (!handler) {
        const available = Object.keys(handlers.operations).join(', ')
        fail(`Resource "${resource}" has no operation "${op}". Available: ${available}`)
      }
      output(await handler(id, flags, client, env))
      break
    }
    default:
      fail(`Unknown verb: "${verb}". Valid verbs: list, get, create, update, delete, invoke`)
  }
}

main().catch(err => {
  console.error(JSON.stringify({ error: (err as Error).message }))
  process.exit(1)
})
