import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'
import { config } from './config.ts'
import { inside } from './kit/paths.ts'

const lastRunAt = atom({ plugin: 'mod-design-tokens', key: 'lastRunAt' } as const, 0)
const isPending = atom({ plugin: 'mod-design-tokens', key: 'isPending' } as const, false)
const findings = atom({ plugin: 'mod-design-tokens', key: 'findings' } as const, null)

// The script prints "  path:line: value" for each invented colour. Key a finding by file and value so a line shift is not new.
function parse(stdout: string): { key: string; text: string }[] {
  const out: { key: string; text: string }[] = []
  for (const line of stdout.split('\n')) {
    const m = line.match(/^\s+(\S+?):(\d+): (\S+)\s*$/)
    if (m) out.push({ key: `${m[1]} ${m[3]}`, text: `${m[1]}:${m[2]} colour ${m[3]} is not in the palette` })
  }
  return out
}

async function runCheck($: EngineInterface, root: string): Promise<void> {
  try {
    await update($, isPending, () => false)
    const started = await $.clock.now()
    await update($, lastRunAt, () => started)
    const r = await $.process.run(config.command, { cwd: root, timeoutMs: config.timeoutMs })
    if (r.exitCode !== 0 && r.exitCode !== 1) {
      $.ui.status('design tokens: check failed')
      return
    }
    $.ui.status(undefined)
    const now = parse(r.stdout)
    const before = await read($, findings)
    const seen = new Map<string, number>()
    for (const k of before ?? []) seen.set(k, (seen.get(k) ?? 0) + 1)
    const fresh: string[] = []
    for (const f of now) {
      const n = seen.get(f.key) ?? 0
      if (n > 0) seen.set(f.key, n - 1)
      else fresh.push(f.text)
    }
    await update($, findings, () => now.map(f => f.key) as never)
    for (const text of fresh.slice(0, config.maxToasts)) $.ui.toast(`design tokens: ${text}`)
  } catch {
    try {
      $.ui.status('design tokens: check failed')
    } catch {
      // stay quiet
    }
  }
}

export const register: Register = on => {
  on('tool.call', { tool: 'Edit' }, async ($, e, next) => {
    const result = await next(e)
    await maybeRun($, e.file_path, result)
    return result
  })

  on('tool.call', { tool: 'Write' }, async ($, e, next) => {
    const result = await next(e)
    await maybeRun($, e.file_path, result)
    return result
  })
}

async function maybeRun($: EngineInterface, filePath: string, result: { deny?: string; isError?: boolean }): Promise<void> {
  try {
    if (result.deny !== undefined || result.isError === true) return
    const repo = await $.session.repo()
    const rel = inside(repo.root, filePath)
    if (rel === undefined || !rel.startsWith(config.watchedPrefix)) return
    if (!config.watchedExtensions.some(x => rel.endsWith(x))) return
    if (await read($, isPending)) return
    const now = await $.clock.now()
    const last = await read($, lastRunAt)
    const wait = last + config.debounceMs - now
    if (wait <= 0) {
      await runCheck($, repo.root)
      return
    }
    await update($, isPending, () => true)
    $.clock.after(wait, () => runCheck($, repo.root))
  } catch {
    // an observer that breaks stays quiet
  }
}
