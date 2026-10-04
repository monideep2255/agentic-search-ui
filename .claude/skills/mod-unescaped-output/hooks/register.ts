import type { Register } from 'claude-code'
import { config } from './config.ts'
import { scan } from './scan.ts'
import { inside } from './kit/paths.ts'

function kindOf(rel: string): 'frontend' | 'python' | undefined {
  if (rel.startsWith(config.frontendPrefix) && config.frontendExtensions.some(x => rel.endsWith(x))) return 'frontend'
  if (rel.startsWith(config.pythonPrefix) && rel.endsWith(config.pythonExtension)) return 'python'
  return undefined
}

function lineSet(text: string): Set<string> {
  return new Set(text.split('\n').map(l => l.trim()))
}

async function readPrior($: EngineInterface, path: string): Promise<string> {
  try {
    const t = await $.fs.read(path)
    return typeof t === 'string' ? t : ''
  } catch {
    return ''
  }
}

// Warns about patterns the new text adds. A line that was already there before the edit stays silent.
// `edited` is the Edit's old_string (a Write has none). `prior` is the file as it was before the call.
async function check($: EngineInterface, filePath: string, newText: string, edited: string | undefined, prior: string, result: { deny?: string; isError?: boolean }): Promise<void> {
  try {
    if (result.deny !== undefined || result.isError === true) return
    const repo = await $.session.repo()
    const rel = inside(repo.root, filePath)
    if (rel === undefined) return
    const kind = kindOf(rel)
    if (kind === undefined) return
    const known = edited !== undefined ? lineSet(edited) : lineSet(prior)
    const audited = lineSet(prior)
    const allowed = config.allowlist[rel] ?? []
    const fresh = scan(newText, kind).filter(f => !known.has(f.line) && !(allowed.includes(f.id) && audited.has(f.line)))
    for (const f of fresh.slice(0, config.maxToasts)) {
      $.ui.toast(`unescaped output: ${rel}: ${f.message} (${f.line.slice(0, 60)})`)
    }
  } catch {
    // an observer that breaks stays quiet
  }
}

export const register: Register = on => {
  on('tool.call', { tool: 'Edit' }, async ($, e, next) => {
    const prior = await readPrior($, e.file_path)
    const result = await next(e)
    await check($, e.file_path, e.new_string, e.old_string, prior, result)
    return result
  })

  on('tool.call', { tool: 'Write' }, async ($, e, next) => {
    const prior = await readPrior($, e.file_path)
    const result = await next(e)
    await check($, e.file_path, e.content, undefined, prior, result)
    return result
  })
}
