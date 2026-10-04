// mod-blast-radius: a guard on risky Bash commands. Before one runs, it works
// out what the command would touch with a dry run, shows the report in a pane
// (or in the band above the prompt when the pane cannot be seated), and asks
// the person to Proceed or Cancel in the engine's own question dialog. Only
// an exact Proceed lets the call through; any other answer, a dismissal, or a
// failure of the guard itself denies it.

import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { BlastReport } from '../types/index.d.ts'
import { config } from './config.ts'
import { findRisky, pushPositionals, slugOf } from './rules.ts'
import type { Match } from './rules.ts'

const PANE = 'blast-radius'
const HEADER = 'Blast radius'
const MAX_RM_TARGETS = 20
const pending = atom({ plugin: 'mod-blast-radius', key: 'pending' } as const, [])

type Ran = { exitCode: number; stdout: string; stderr: string; failed: string | undefined }
type Section = { lines: string[]; summary: string; isFailed: boolean }

async function run($: EngineInterface, argv: readonly string[], init: { cwd?: string; timeoutMs?: number } = {}): Promise<Ran> {
  try {
    const r = await $.process.run(argv, { timeoutMs: 20_000, ...init })
    return { exitCode: r.exitCode, stdout: r.stdout, stderr: r.stderr, failed: undefined }
  } catch (err) {
    return { exitCode: -1, stdout: '', stderr: '', failed: err instanceof Error ? err.message : String(err) }
  }
}

function denyOnFailure($: EngineInterface) {
  return { deny: `${$.plugin.name}: the guard failed while checking this call, so it was held. Retry, or ask the person to run it.` }
}

async function confirm($: EngineInterface, question: string): Promise<boolean> {
  try {
    const answer = await $.ui.ask(question, { header: HEADER, options: ['Proceed', 'Cancel'] })
    return answer === 'Proceed'
  } catch {
    return false
  }
}

function firstLine(text: string): string {
  return text.split('\n').find(l => l.trim() !== '')?.trim() ?? ''
}

function why(r: Ran): string {
  return r.failed ?? (firstLine(r.stderr) || `exit code ${r.exitCode}`)
}

function outputLines(text: string): string[] {
  return text.split('\n').map(l => l.trimEnd()).filter(l => l.trim() !== '')
}

function size(kb: number): string {
  if (kb >= 1024 * 1024) return `${(kb / 1024 / 1024).toFixed(1)} GB`
  if (kb >= 1024) return `${Math.round(kb / 1024)} MB`
  return `${kb} KB`
}

function short(command: string, max = 60): string {
  const one = command.replace(/\s+/g, ' ').trim()
  return one.length > max ? one.slice(0, max - 3) + '...' : one
}

/** One argv-style dry run: its output as the report lines, a failure shown as failed. */
async function argvSection($: EngineInterface, argv: readonly string[], cwd: string | undefined, noun: string): Promise<Section> {
  const r = await run($, argv, { cwd })
  if (r.failed !== undefined || r.exitCode !== 0) {
    return { lines: [`dry run failed: ${argv.join(' ')} (${why(r)})`], summary: 'dry run failed', isFailed: true }
  }
  const lines = outputLines(r.stdout)
  return {
    lines: lines.length > 0 ? lines : [`dry run reports no ${noun}`],
    summary: `${lines.length} ${noun}`,
    isFailed: false,
  }
}

async function rmSection($: EngineInterface, m: Match, targets: string[]): Promise<Section> {
  if (targets.length === 0) return { lines: ['no target paths named'], summary: 'no targets', isFailed: false }
  const lines: string[] = []
  let kb = 0
  let tracked = 0
  let failures = 0
  for (const target of targets.slice(0, MAX_RM_TARGETS)) {
    const du = await run($, ['du', '-sk', '--', target], { cwd: m.cwd })
    let sizeText: string
    if (du.failed === undefined && du.exitCode === 0) {
      const n = Number.parseInt(du.stdout.trim().split(/\s+/)[0] ?? '', 10)
      if (Number.isFinite(n)) { kb += n; sizeText = size(n) } else { failures++; sizeText = 'size unreadable' }
    } else {
      failures++
      sizeText = `size check failed (${why(du)})`
    }
    const ls = await run($, ['git', 'ls-files', '--error-unmatch', '--', target], { cwd: m.cwd })
    let state: string
    if (ls.failed === undefined && ls.exitCode === 0) { tracked++; state = 'tracked' }
    else if (ls.failed === undefined && ls.exitCode === 1) state = 'untracked'
    else { failures++; state = `tracked check failed (${why(ls)})` }
    lines.push(`${target}: ${sizeText}, ${state}`)
  }
  if (targets.length > MAX_RM_TARGETS) lines.push(`and ${targets.length - MAX_RM_TARGETS} more paths not checked`)
  const parts = [`${targets.length} path${targets.length === 1 ? '' : 's'}`, size(kb), `${tracked} tracked file${tracked === 1 ? '' : 's'}`]
  if (failures > 0) parts.push(`${failures} check${failures === 1 ? '' : 's'} failed`)
  return { lines, summary: parts.join(', '), isFailed: failures > 0 }
}

async function resetSection($: EngineInterface, m: Match, git: string[]): Promise<Section> {
  const status = await run($, [...git, 'status', '--porcelain'], { cwd: m.cwd })
  const diff = await run($, [...git, 'diff', '--stat', 'HEAD'], { cwd: m.cwd })
  const lines: string[] = []
  let isFailed = false
  let changed = 0
  if (status.failed !== undefined || status.exitCode !== 0) {
    isFailed = true
    lines.push(`git status failed (${why(status)})`)
  } else {
    const rows = outputLines(status.stdout)
    changed = rows.length
    lines.push(rows.length > 0 ? 'changed paths:' : 'git status reports a clean working tree', ...rows.map(r => `  ${r}`))
  }
  if (diff.failed !== undefined || diff.exitCode !== 0) {
    isFailed = true
    lines.push(`git diff --stat HEAD failed (${why(diff)})`)
  } else {
    lines.push(...outputLines(diff.stdout))
  }
  return { lines, summary: isFailed ? 'dry run failed' : `${changed} changed path${changed === 1 ? '' : 's'} would be discarded`, isFailed }
}

async function pathsSection($: EngineInterface, m: Match, git: string[], paths: string[]): Promise<Section> {
  const s = await argvSection($, [...git, 'diff', '--stat', '--', ...(paths.length > 0 ? paths : ['.'])], m.cwd, 'lines of changes')
  if (s.isFailed) return s
  const files = s.lines.filter(l => l.includes('|')).length
  return { ...s, summary: `${files} file${files === 1 ? '' : 's'} with unstaged changes` }
}

async function branchSection($: EngineInterface, m: Match, git: string[], branches: string[]): Promise<Section> {
  const lines: string[] = []
  let isFailed = false
  let commits = 0
  for (const b of branches) {
    const r = await run($, [...git, 'log', '--oneline', `HEAD..${b}`], { cwd: m.cwd })
    if (r.failed !== undefined || r.exitCode !== 0) {
      isFailed = true
      lines.push(`${b}: dry run failed (${why(r)})`)
      continue
    }
    const rows = outputLines(r.stdout)
    commits += rows.length
    lines.push(`${b}: ${rows.length} commit${rows.length === 1 ? '' : 's'} not in HEAD`, ...rows.map(x => `  ${x}`))
  }
  return { lines, summary: isFailed ? 'dry run failed' : `${commits} unmerged commit${commits === 1 ? '' : 's'}`, isFailed }
}

async function revParse($: EngineInterface, git: string[], cwd: string | undefined, args: string[]): Promise<{ value?: string; error?: string }> {
  const r = await run($, [...git, 'rev-parse', ...args], { cwd })
  if (r.failed !== undefined || r.exitCode !== 0) return { error: why(r) }
  return { value: r.stdout.trim() }
}

async function pushSection($: EngineInterface, m: Match, git: string[], args: string[]): Promise<Section> {
  const positional = pushPositionals(args)
  const pairs: { local: string; remoteRef: string }[] = []
  const lines: string[] = []
  let isFailed = false

  if (positional.length === 0) {
    const up = await revParse($, git, m.cwd, ['--abbrev-ref', '--symbolic-full-name', '@{u}'])
    if (up.error !== undefined) {
      return { lines: [`could not resolve the upstream branch (${up.error})`], summary: 'dry run failed', isFailed: true }
    }
    pairs.push({ local: 'HEAD', remoteRef: `refs/remotes/${up.value}` })
  } else {
    const remote = positional[0]
    const specs = positional.slice(1)
    let current: string | undefined
    const head = async () => {
      if (current === undefined) {
        const r = await revParse($, git, m.cwd, ['--abbrev-ref', 'HEAD'])
        current = r.value ?? ''
      }
      return current
    }
    if (specs.length === 0) {
      const b = await head()
      if (!b) return { lines: ['could not resolve the current branch'], summary: 'dry run failed', isFailed: true }
      pairs.push({ local: 'HEAD', remoteRef: `refs/remotes/${remote}/${b}` })
    }
    for (const raw of specs) {
      const spec = raw.replace(/^\+/, '')
      const [src, dstGiven] = spec.includes(':') ? spec.split(':', 2) : [spec, undefined]
      let dst = (dstGiven ?? src).replace(/^refs\/heads\//, '')
      if (dst === 'HEAD') dst = await head()
      if (!src) { lines.push(`${raw}: deletes the remote branch ${dst}`); continue }
      pairs.push({ local: src, remoteRef: `refs/remotes/${remote}/${dst}` })
    }
  }

  let lost = 0
  for (const p of pairs) {
    const local = await revParse($, git, m.cwd, ['--verify', p.local])
    const remote = await revParse($, git, m.cwd, ['--verify', p.remoteRef])
    if (local.error !== undefined || remote.error !== undefined) {
      isFailed = true
      lines.push(`${p.local} to ${p.remoteRef}: could not resolve (${local.error ?? remote.error}); fetch first, or this is a new branch`)
      continue
    }
    const r = await run($, [...git, 'log', '--oneline', `${local.value}..${remote.value}`], { cwd: m.cwd })
    if (r.failed !== undefined || r.exitCode !== 0) {
      isFailed = true
      lines.push(`${p.remoteRef}: git log failed (${why(r)})`)
      continue
    }
    const rows = outputLines(r.stdout)
    lost += rows.length
    lines.push(`${p.remoteRef}: ${rows.length} commit${rows.length === 1 ? '' : 's'} would be lost (as of the last fetch)`, ...rows.map(x => `  ${x}`))
  }
  return { lines, summary: isFailed ? 'dry run failed' : `${lost} remote commit${lost === 1 ? '' : 's'} would be lost`, isFailed }
}

async function section($: EngineInterface, m: Match): Promise<Section> {
  if (!m.isCwdKnown) {
    return { lines: ['dry run not run: the working directory after an earlier cd could not be worked out'], summary: 'dry run failed', isFailed: true }
  }
  const plan = m.plan
  switch (plan.kind) {
    case 'rm': return rmSection($, m, plan.targets)
    case 'argv': return argvSection($, plan.argv, m.cwd, 'lines of output')
    case 'git-reset': return resetSection($, m, plan.git)
    case 'git-paths': return pathsSection($, m, plan.git, plan.paths)
    case 'git-branch': return branchSection($, m, plan.git, plan.branches)
    case 'git-push': return pushSection($, m, plan.git, plan.args)
    default: return { lines: ['no dry run available for this command'], summary: 'no dry run available', isFailed: false }
  }
}

async function buildReport($: EngineInterface, matches: Match[], cap: number): Promise<{ lines: string[]; summary: string }> {
  const all: string[] = []
  const summaries: string[] = []
  for (const m of matches) {
    const s = await section($, m)
    all.push(`${m.rule}: ${m.segment}`, ...s.lines.map(l => `  ${l}`))
    summaries.push(matches.length > 1 ? `${m.rule}: ${s.summary}` : s.summary)
  }
  const lines = all.length > cap ? [...all.slice(0, cap), `and ${all.length - cap} more lines`] : all
  return { lines, summary: summaries.join('; ') }
}

/** True when this force push targets a remote that mod-public-repo-guard denies outright, so asking would be a wasted question. */
async function defersToPublicGuard($: EngineInterface, m: Match): Promise<boolean> {
  if (m.plan.kind !== 'git-push' || config.deferToPublicGuard.length === 0) return false
  const remote = pushPositionals(m.plan.args)[0] ?? 'origin'
  let slug = slugOf(remote)
  if (!slug) {
    const r = await run($, [...m.plan.git, 'remote', 'get-url', remote], { cwd: m.cwd })
    slug = r.exitCode === 0 ? slugOf(r.stdout) : undefined
  }
  return slug !== undefined && config.deferToPublicGuard.some(s => s.toLowerCase() === slug)
}

export const register: Register = on => {
  on('tool.call', { tool: 'Bash' }, async ($, e, next) => {
    const found = findRisky(e.command, config.extraRules)
    const matches: Match[] = []
    for (const m of found) if (!(await defersToPublicGuard($, m))) matches.push(m)
    if (matches.length === 0) return next(e)

    const id = e.tool_use_id ?? crypto.randomUUID()
    const { lines, summary } = await buildReport($, matches, config.maxReportLines)
    const report: BlastReport = { id, command: e.command, lines, isBand: false }
    await update($, pending, list => [...list, report])
    try {
      const opened = await $.ui.open({ id: PANE, title: HEADER, rows: Math.min(lines.length + 4, 30) })
      if (!opened.isPlaced) {
        await update($, pending, list => list.map(r => (r.id === id ? { ...r, isBand: true } : r)))
      }
      const isProceed = await confirm($, `Run \`${short(e.command)}\`? ${summary}`)
      if (!isProceed) {
        return { deny: `${$.plugin.name}: the person did not approve \`${short(e.command)}\` after seeing its blast radius (${summary}). Ask them before retrying, or use a narrower command.` }
      }
    } finally {
      await update($, pending, list => list.filter(r => r.id !== id))
      // The decision is already taken: a pane that will not close must not turn it around.
      try {
        if ((await read($, pending)).length === 0) await $.ui.close({ id: PANE })
      } catch {
        $.ui.log(`${$.plugin.name}: could not close the report pane`, { to: 'debug' })
      }
    }
    return next(e)
  }).catch(denyOnFailure)

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text } = $.ui.resolve(e)
    const list = await read($, pending)
    return (
      <Box flexDirection="column">
        {list.length === 0 && <Text dimColor>No risky command is waiting.</Text>}
        {list.map(r => (
          <Box key={`report-${r.id}`} flexDirection="column" marginBottom={1}>
            <Text color="yellow">Blast radius of: {short(r.command, Math.max(20, e.props.bodyColumns - 18))}</Text>
            {r.lines.map(line => <Text wrap="truncate-end">{line}</Text>)}
          </Box>
        ))}
        {list.length > 0 && <Text dimColor>Answer Proceed or Cancel in the question below the transcript.</Text>}
      </Box>
    )
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    if (e.props.hasSurvey) return next(e)
    const list = (await read($, pending)).filter(r => r.isBand)
    if (list.length === 0) return next(e)
    const { Box, Text } = $.ui.resolve(e)
    const room = Math.max(3, e.props.maxRows - 2)
    return (
      <Box flexDirection="column">
        {list.map(r => (
          <Box key={`band-${r.id}`} flexDirection="column">
            <Text color="yellow">Blast radius of: {short(r.command, Math.max(20, e.props.bodyColumns - 18))}</Text>
            {r.lines.slice(0, room).map(line => <Text wrap="truncate-end">{line}</Text>)}
            {r.lines.length > room && <Text dimColor>and {r.lines.length - room} more lines</Text>}
          </Box>
        ))}
      </Box>
    )
  })
}
