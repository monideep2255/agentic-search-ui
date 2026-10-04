import type { Register } from 'claude-code'
import { config } from './config.ts'
import { inside } from './kit/paths.ts'

// Routes seen in text written during the current turn, keyed by "METHOD path".
let routes = new Map<string, { method: string; path: string }>()

// A module variable is lost on a hot reload, which only means a turn's list starts empty.
function collect(file: string, root: string, text: string | undefined) {
  const rel = inside(root, file)
  if (rel === undefined || !rel.startsWith(config.adapterDir) || !rel.endsWith('.py')) return
  if (typeof text !== 'string') return
  for (const m of text.matchAll(new RegExp(config.routeDecorator.source, 'g'))) {
    routes.set(`${m[1].toUpperCase()} ${m[2]}`, { method: m[1].toUpperCase(), path: m[2] })
  }
}

// Escapes a route path for grep -E, turning each {param} into a wildcard.
function pathPattern(path: string): string {
  return path
    .split(/\{[^}]*\}/)
    .map(piece => piece.replace(/[.*+?^$()|[\]\\{}]/g, '\\$&'))
    .join('.*')
}

async function findGaps($: EngineInterface, root: string, path: string): Promise<string | undefined> {
  let files: string[]
  try {
    const r = await $.process.run(['grep', '-rlE', pathPattern(path), config.testsDir], { cwd: root, timeoutMs: 20_000 })
    if (r.exitCode > 1) return undefined // grep itself failed: stay quiet
    files = r.stdout.split('\n').map(l => l.trim()).filter(Boolean)
  } catch {
    return undefined
  }
  if (files.length === 0) return `route ${path}: no test file mentions it (name-based heuristic)`

  let names: string[]
  try {
    const r = await $.process.run(['grep', '-hoE', 'def test_[A-Za-z0-9_]*', ...files], { cwd: root, timeoutMs: 20_000 })
    if (r.exitCode > 1) return undefined
    names = r.stdout.split('\n').map(l => l.replace(/^def /, '').trim()).filter(Boolean)
  } catch {
    return undefined
  }

  const gaps: string[] = []
  if (!names.some(n => config.validName.test(n))) gaps.push('no valid-input test found')
  if (!names.some(n => config.invalidName.test(n))) gaps.push('no invalid-input test found')
  if (!names.some(n => config.emptyName.test(n))) gaps.push('no null-or-empty-input test found')
  if (gaps.length === 0) return undefined
  return `route ${path}: ${gaps.join(', ')} (name-based heuristic)`
}

async function afterTurn($: EngineInterface) {
  const seen = [...routes.values()]
  routes = new Map()
  if (seen.length === 0) return
  const repo = await $.session.repo()
  const messages: string[] = []
  for (const r of seen) {
    const gap = await findGaps($, repo.root, r.path)
    if (gap) messages.push(gap)
  }
  for (const m of messages.slice(0, config.maxToasts)) $.ui.toast(m)
  if (messages.length > config.maxToasts) {
    $.ui.toast(`${messages.length - config.maxToasts} more routes lack a valid, invalid, or empty input test (name-based heuristic)`)
  }
}

async function remember($: EngineInterface, file: string, text: string | undefined) {
  const repo = await $.session.repo()
  collect(file, repo.root, text)
}

export const register: Register = on => {
  on('prompt.submit', ($, e, next) => {
    routes = new Map()
    return next(e)
  })

  on('tool.call', { tool: 'Edit' }, async ($, e, next) => {
    const ran = await next(e)
    if (ran.deny === undefined && ran.isError !== true) {
      try { await remember($, e.file_path, e.new_string) } catch { /* an observer stays quiet when it cannot check */ }
    }
    return ran
  })

  on('tool.call', { tool: 'Write' }, async ($, e, next) => {
    const ran = await next(e)
    if (ran.deny === undefined && ran.isError !== true) {
      try { await remember($, e.file_path, e.content) } catch { /* an observer stays quiet when it cannot check */ }
    }
    return ran
  })

  on('turn.complete', async ($, e, next) => {
    const result = await next(e)
    if (e.agentId !== undefined) return result // a subagent's turn: the main turn has not ended
    try { await afterTurn($) } catch { /* an observer stays quiet when it cannot check */ }
    return result
  })
}
