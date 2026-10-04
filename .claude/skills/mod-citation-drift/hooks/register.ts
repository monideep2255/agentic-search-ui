import type { Register } from 'claude-code'
import { config } from './config.ts'
import type { HostSource } from './config.ts'
import { inside, matchesAny } from './kit/paths.ts'

type Declared = { file: string; kind: 'list' | 'pattern'; hosts: Set<string>; wildcards: Set<string>; wwwOptional: Set<string> }

// Reads one source file and extracts its host declarations. Returns undefined when the
// file cannot be read, and an empty set when the declaration could not be found in it.
async function extract($: EngineInterface, root: string, source: HostSource): Promise<Declared | undefined> {
  let text: unknown
  try {
    text = await $.fs.read(root + '/' + source.file)
  } catch {
    return undefined
  }
  if (typeof text !== 'string') return undefined
  const out: Declared = { file: source.file, kind: source.kind, hosts: new Set(), wildcards: new Set(), wwwOptional: new Set() }
  const m = source.block.exec(text)
  if (!m) return out
  const region = m[1] ?? ''

  if (source.kind === 'list') {
    for (const h of region.matchAll(new RegExp(source.hosts.source, 'g'))) out.hosts.add(h[1].toLowerCase())
    return out
  }

  // A pattern: unescape dots, then read every dotted token. A token preceded by ")*" is a
  // subdomain wildcard. A token preceded by "www.)?" admits the www form as well.
  const flat = region.replace(/\\\./g, '.')
  for (const t of flat.matchAll(/[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+/g)) {
    const host = t[0].toLowerCase()
    if (host === 'www.') continue
    const before = flat.slice(Math.max(0, (t.index ?? 0) - 12), t.index ?? 0)
    if (/\)\*$/.test(before)) out.wildcards.add(host)
    else if (/www\.\)\?$/.test(before)) { out.hosts.add(host); out.wwwOptional.add(host) }
    else out.hosts.add(host)
  }
  return out
}

// True when a pattern source admits the host.
function covers(p: Declared, host: string): boolean {
  if (p.hosts.has(host)) return true
  for (const w of p.wwwOptional) if (host === 'www.' + w) return true
  for (const w of p.wildcards) if (host === w || host.endsWith('.' + w)) return true
  return false
}

async function check($: EngineInterface, rel: string) {
  if (!matchesAny(rel, config.watchedPaths)) return
  const repo = await $.session.repo()
  const root = repo.root

  const declared: Declared[] = []
  for (const source of config.sources) {
    const d = await extract($, root, source)
    if (!d) continue
    if (d.hosts.size === 0 && d.wildcards.size === 0) {
      $.ui.toast(`citation hosts: found no hosts in ${d.file}, so the declaration may have moved`)
      continue
    }
    declared.push(d)
  }
  const lists = declared.filter(d => d.kind === 'list')
  const patterns = declared.filter(d => d.kind === 'pattern')
  const findings = new Set<string>()

  // 1. One list has a host another list lacks.
  for (const a of lists) {
    for (const b of lists) {
      if (a === b) continue
      for (const h of a.hosts) if (!b.hosts.has(h)) findings.add(`${h} in ${a.file} only`)
    }
  }
  // 2. A listed host that no pattern admits.
  if (patterns.length > 0) {
    for (const l of lists) {
      for (const h of l.hosts) if (!patterns.some(p => covers(p, h))) findings.add(`${h} in ${l.file} only`)
    }
  }
  // 3. A host a pattern names literally that a list lacks.
  for (const p of patterns) {
    for (const h of p.hosts) {
      const variants = [h, ...(p.wwwOptional.has(h) ? ['www.' + h] : [])]
      for (const v of variants) if (lists.some(l => !l.hosts.has(v))) findings.add(`${v} in ${p.file} only`)
    }
  }

  if (findings.size === 0) return
  const all = [...findings].sort()
  const shown = all.slice(0, config.maxFindings).map(f => `citation hosts drift: ${f}`)
  const more = all.length > shown.length ? ` (+${all.length - shown.length} more)` : ''
  $.ui.toast(shown.join('; ') + more)
}

async function afterWrite($: EngineInterface, e: { file_path: string }, ran: { deny?: string; isError?: boolean }) {
  if (ran.deny !== undefined || ran.isError === true) return
  try {
    const repo = await $.session.repo()
    const rel = inside(repo.root, e.file_path)
    if (rel !== undefined) await check($, rel)
  } catch {
    // an observer stays quiet when it cannot check
  }
}

export const register: Register = on => {
  // The same observer on both tools.
  on('tool.call', { tool: 'Edit' }, async ($, e, next) => {
    const ran = await next(e)
    await afterWrite($, e, ran)
    return ran
  })
  on('tool.call', { tool: 'Write' }, async ($, e, next) => {
    const ran = await next(e)
    await afterWrite($, e, ran)
    return ran
  })
}
