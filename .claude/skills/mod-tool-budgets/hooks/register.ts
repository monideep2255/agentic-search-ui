import type { Register } from 'claude-code'
import { config } from './config.ts'
import { inside, matchesAny } from './kit/paths.ts'
import { basename } from './kit/shell.ts'

type Row = { tool: string; accepted: number[]; isFloor: boolean; isUnsettled: boolean; shown: string }

async function readText($: EngineInterface, path: string): Promise<string | undefined> {
  try {
    const text = await $.fs.read(path)
    return typeof text === 'string' ? text : undefined
  } catch {
    return undefined
  }
}

// Parses the rule's markdown table. A row is "| tool | timeout cell | pool |" where the tool is a bare identifier.
function parseTable(text: string): Row[] {
  const rows: Row[] = []
  for (const line of text.split('\n')) {
    if (!line.trim().startsWith('|')) continue
    const cells = line.trim().replace(/^\||\|$/g, '').split('|').map(c => c.trim())
    if (cells.length < 2 || !/^[a-z][a-z0-9_]*$/.test(cells[0])) continue
    const cell = cells[1]
    const accepted = [...cell.matchAll(/(\d+(?:\.\d+)?)\s*seconds?/g)].map(m => Number(m[1]))
    if (accepted.length === 0) continue
    rows.push({
      tool: cells[0],
      accepted,
      isFloor: /or more/i.test(cell),
      isUnsettled: config.unsettled.test(cell),
      shown: String(accepted[0]),
    })
  }
  return rows
}

// Top level constants in a source file whose name looks like a timeout.
function declaredIn(text: string): Map<string, number> {
  const found = new Map<string, number>()
  for (const m of text.matchAll(/^([A-Z_][A-Za-z0-9_]*)\s*(?::[^=\n]+)?=\s*(\d+(?:\.\d+)?)\b/gm)) {
    if (config.timeoutName.test(m[1])) found.set(m[1], Number(m[2]))
  }
  return found
}

// The timeout a tool declares: its own constant, an imported constant, or its shared transport's default.
async function declaredTimeout($: EngineInterface, root: string, source: string): Promise<number | undefined> {
  const own = declaredIn(source)
  if (own.size > 0) return [...own.values()][0]

  for (const file of config.constantFiles) {
    const text = await readText($, root + '/' + file)
    if (text === undefined) continue
    for (const [name, value] of declaredIn(text)) {
      if (new RegExp('\\b' + name + '\\b').test(source)) return value
    }
  }

  for (const d of config.delegates) {
    if (!d.marker.test(source)) continue
    const text = await readText($, root + '/' + d.file)
    if (text === undefined) return undefined
    const shared = declaredIn(text)
    if (shared.size > 0) return [...shared.values()][0]
  }
  return undefined
}

async function checkTool($: EngineInterface, root: string, row: Row | undefined, tool: string, rel: string): Promise<string | undefined> {
  if (!row) return undefined // not a tool the table knows
  const source = await readText($, root + '/' + rel)
  if (source === undefined) return undefined
  const declared = await declaredTimeout($, root, source)
  if (declared === undefined) {
    return `tool budgets: ${tool} has no declared timeout. A tool without a declared timeout is not finished (${config.rulePath}).`
  }
  const agrees = row.accepted.includes(declared) || (row.isFloor && declared >= row.accepted[0])
  if (agrees) return undefined
  if (row.isUnsettled) {
    return `tool budgets (informational): ${tool} declares ${declared}s, and the rule's value of ${row.shown}s is marked unsettled.`
  }
  return `tool budgets: ${tool} declares ${declared}s but the rule's table says ${row.shown}s.`
}

async function afterWrite($: EngineInterface, filePath: string) {
  const repo = await $.session.repo()
  const root = repo.root
  const rel = inside(root, filePath)
  if (rel === undefined) return
  const isBudgetModule = rel === config.budgetModule
  if (!isBudgetModule && !matchesAny(rel, config.toolGlobs)) return

  const ruleText = await readText($, root + '/' + config.rulePath)
  if (ruleText === undefined) return
  const rows = parseTable(ruleText)
  if (rows.length === 0) return

  const messages: string[] = []
  if (isBudgetModule) {
    for (const row of rows) {
      const m = await checkTool($, root, row, row.tool, `${config.toolsDir}/${row.tool}.py`)
      if (m) messages.push(m)
    }
  } else {
    const tool = basename(rel).replace(/\.py$/, '')
    const m = await checkTool($, root, rows.find(r => r.tool === tool), tool, rel)
    if (m) messages.push(m)
  }
  if (messages.length > 0) $.ui.toast(messages.join(' '))
}

export const register: Register = on => {
  on('tool.call', { tool: 'Edit' }, async ($, e, next) => {
    const ran = await next(e)
    if (ran.deny === undefined && ran.isError !== true) {
      try { await afterWrite($, e.file_path) } catch { /* an observer stays quiet when it cannot check */ }
    }
    return ran
  })
  on('tool.call', { tool: 'Write' }, async ($, e, next) => {
    const ran = await next(e)
    if (ran.deny === undefined && ran.isError !== true) {
      try { await afterWrite($, e.file_path) } catch { /* an observer stays quiet when it cannot check */ }
    }
    return ran
  })
}
