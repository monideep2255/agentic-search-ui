import type { EngineInterface, Register } from 'claude-code'

import { config } from './config.ts'
import { matchesAny } from './kit/paths.ts'
import { scanText } from './scan.ts'

const reported = new Set<string>()

function denyOnFailure($: EngineInterface) {
  return { deny: `${$.plugin.name}: the guard failed while checking this call, so it was held. Retry, or ask the person to run it.` }
}

function allowed(path: string | undefined): boolean {
  return path !== undefined && matchesAny(path, config.allowPaths)
}

function verdict($: EngineInterface, tool: string, text: string, path?: string) {
  if (allowed(path)) return undefined
  const found = scanText(text, config.extraPatterns, path)
  if (found.length === 0) return undefined
  const f = found[0]
  const more = found.length > 1 ? ` (${found.length - 1} more)` : ''
  return {
    deny: `${$.plugin.name}: ${tool} holds secret-shaped text: ${f.name}, line ${f.line}, starts with "${f.preview}"${more}. Use an environment variable or a placeholder instead, or mark a deliberate placeholder line with "secrets-scan: allow".`,
  }
}

function observe($: EngineInterface, tool: string, text: string | undefined, path?: string) {
  try {
    if (!text || allowed(path)) return
    for (const f of scanText(text, config.extraPatterns, path)) {
      if (reported.has(f.name)) continue
      reported.add(f.name)
      $.ui.toast(`secret-shaped text in ${tool} output: ${f.name}`)
    }
  } catch {
    // an observer that breaks stays quiet
  }
}

export const register: Register = on => {
  on('turn.start', ($, e, next) => {
    reported.clear()
    return next(e)
  })

  on('tool.call', { tool: 'Bash' }, async ($, e, next) => {
    const v = verdict($, 'Bash', e.command)
    if (v) return v
    const ran = await next(e)
    observe($, 'Bash', ran.text)
    return ran
  }).catch(denyOnFailure)

  on('tool.call', { tool: 'Edit' }, async ($, e, next) => {
    const v = verdict($, 'Edit', e.new_string, e.file_path)
    if (v) return v
    const ran = await next(e)
    observe($, 'Edit', ran.text, e.file_path)
    return ran
  }).catch(denyOnFailure)

  on('tool.call', { tool: 'Write' }, async ($, e, next) => {
    const v = verdict($, 'Write', e.content, e.file_path)
    if (v) return v
    const ran = await next(e)
    observe($, 'Write', ran.text, e.file_path)
    return ran
  }).catch(denyOnFailure)

  on('tool.call', { tool: 'NotebookEdit' }, async ($, e, next) => {
    const v = verdict($, 'NotebookEdit', e.new_source, e.notebook_path)
    if (v) return v
    const ran = await next(e)
    observe($, 'NotebookEdit', ran.text, e.notebook_path)
    return ran
  }).catch(denyOnFailure)

  on('tool.call', { tool: 'Read' }, async ($, e, next) => {
    const ran = await next(e)
    observe($, 'Read', ran.text, e.file_path)
    return ran
  })

  on('tool.call', { tool: 'WebFetch' }, async ($, e, next) => {
    const ran = await next(e)
    observe($, 'WebFetch', ran.text)
    return ran
  })
}
