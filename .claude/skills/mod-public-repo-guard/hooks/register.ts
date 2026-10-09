import type { Register, EngineInterface } from 'claude-code'

import { config } from './config.ts'
import type { RemotePolicy } from './config.ts'
import { programInfo, segments } from './kit/shell.ts'

const SUMMARY_LINES = 30

type Target = { root: string; policy: RemotePolicy | undefined; slug: string | undefined }
type Call = { dir: string | undefined; sub: string; args: string[]; configs: string[] }

async function run($: EngineInterface, argv: readonly string[], init: { cwd?: string; timeoutMs?: number; stdin?: string } = {}) {
  try {
    const r = await $.process.run(argv, { timeoutMs: 20_000, ...init })
    return { exitCode: r.exitCode, stdout: r.stdout, stderr: r.stderr, failed: undefined as string | undefined }
  } catch (err) {
    return { exitCode: -1, stdout: '', stderr: '', failed: err instanceof Error ? err.message : String(err) }
  }
}

function denyOnFailure($: EngineInterface) {
  return { deny: `${$.plugin.name}: the guard failed while checking this call, so it was held. Retry, or ask the person to run it.` }
}

/** The owner/name slug of a github remote in https or ssh form, lowercased. */
function slugOf(remote: string | null | undefined): string | undefined {
  if (!remote) return undefined
  const m = remote.trim().match(/^(?:https?:\/\/(?:[^@/]+@)?github\.com(?::\d+)?|ssh:\/\/(?:[^@/]+@)?github\.com(?::\d+)?|git@github\.com)[:/]+([^/:]+)\/([^/]+?)(?:\.git)?\/?$/i)
  return m ? `${m[1]}/${m[2]}`.toLowerCase() : undefined
}

function policyFor(slug: string | undefined): RemotePolicy | undefined {
  if (!slug) return undefined
  for (const key of Object.keys(config.publicRemotes)) {
    if (key.toLowerCase() === slug) return config.publicRemotes[key]
  }
  return undefined
}

function joinDir(base: string | undefined, dir: string): string {
  if (dir.startsWith('/') || dir.startsWith('~') || !base) return dir
  return base.replace(/\/$/, '') + '/' + dir
}

/** Every commit and push call in the command line, with `-C` and a preceding `cd` resolved. */
function callsOf(command: string): Call[] {
  const out: Call[] = []
  let cd: string | undefined
  for (const seg of segments(command)) {
    const info = programInfo(seg)
    const p = info.words
    if (p.length === 0) continue
    if (p[0] === 'cd') {
      if (p[1] && !p[1].startsWith('-')) cd = joinDir(cd, p[1])
      continue
    }
    if (p[0].split('/').pop() !== 'git') continue
    let dir = info.cwd !== undefined ? joinDir(cd, info.cwd) : cd
    let i = 1
    const configs: string[] = []
    while (i < p.length && p[i].startsWith('-')) {
      if (p[i] === '-C') { if (p[i + 1] !== undefined) dir = joinDir(dir, p[i + 1]); i += 2; continue }
      if (p[i] === '-c') { if (p[i + 1] !== undefined) configs.push(p[i + 1]); i += 2; continue }
      if (p[i].startsWith('-c') && p[i].length > 2 && !p[i].startsWith('--')) { configs.push(p[i].slice(2)); i++; continue }
      if (p[i] === '--git-dir' || p[i] === '--work-tree') { i += 2; continue }
      i++
    }
    if (i < p.length) out.push({ dir, sub: p[i], args: p.slice(i + 1), configs })
  }
  return out
}

async function targetOf($: EngineInterface, dir: string | undefined): Promise<Target> {
  const session = await $.session.repo()
  if (dir === undefined || dir === session.root) {
    const slug = slugOf(session.remote)
    return { root: session.root, policy: policyFor(slug), slug }
  }
  const remote = await run($, ['git', '-C', dir, 'remote', 'get-url', 'origin'])
  const top = await run($, ['git', '-C', dir, 'rev-parse', '--show-toplevel'])
  const slug = remote.exitCode === 0 ? slugOf(remote.stdout) : undefined
  const root = top.exitCode === 0 && top.stdout.trim() ? top.stdout.trim() : dir
  return { root, policy: policyFor(slug), slug }
}

function hasShortFlag(args: readonly string[], letter: string, valueFlags: readonly string[]): boolean {
  for (let i = 0; i < args.length; i++) {
    const a = args[i]
    if (a === '--') break
    if (valueFlags.includes(a)) { i++; continue }
    if (/^-[A-Za-z]+$/.test(a) && a.includes(letter)) return true
  }
  return false
}

function summaryOf(stdout: string, stderr: string): string {
  const lines = (stdout + '\n' + stderr).split('\n').map(l => l.trimEnd()).filter(l => l.length > 0)
  const shown = lines.slice(0, SUMMARY_LINES)
  if (lines.length > SUMMARY_LINES) shown.push(`(${lines.length - SUMMARY_LINES} more lines not shown)`)
  return shown.join('\n')
}

/** Run one checker; undefined means it passed, a string is the deny reason. */
async function check($: EngineInterface, name: string, argv: readonly string[], root: string): Promise<string | undefined> {
  const r = await run($, argv, { cwd: root, timeoutMs: 120_000 })
  if (r.exitCode === 0 && r.failed === undefined) return undefined
  if (r.exitCode === 1 && r.failed === undefined) {
    return `${$.plugin.name}: ${name} found problems. Fix them, then retry.\n${summaryOf(r.stdout, r.stderr)}`
  }
  return `${$.plugin.name}: the leak scan could not run (${name}), so nothing was checked. Fix the checker, then retry.`
}

/** Paths of the files staged for the commit; undefined when git could not say. */
async function stagedPaths($: EngineInterface, root: string): Promise<Set<string> | undefined> {
  const r = await run($, ['git', '-C', root, 'diff', '--cached', '--name-only', '-z', '--no-renames'])
  if (r.exitCode !== 0 || r.failed !== undefined) return undefined
  return new Set(r.stdout.split('\0').filter(p => p.length > 0))
}

type Finding = { line: string; path: string | undefined; isRange: boolean }

/**
 * Reads the scanner's FAIL and TOO LARGE lines. Its location forms are
 * `commit <hash> <path>:<line>` (a commit of the range), `<path>:<line>` and
 * `file name <path>` (staged, unstaged or untracked, the output does not say
 * which), `commit <hash> message:<n>`, and the same after the private-name
 * check prefix. A hidden file name has no readable path.
 */
function findingsOf(stdout: string): Finding[] {
  const out: Finding[] = []
  for (const raw of stdout.split('\n')) {
    const line = raw.trim()
    let rest: string
    if (line.startsWith('FAIL ')) rest = line.slice(5)
    else if (line.startsWith('TOO LARGE ')) rest = line.slice(10)
    else continue
    rest = rest.replace(/^private-name check: /, '')
    const isRange = /^commit [0-9a-f]{4,}\b/.test(rest)
    if (isRange || /^message:\d+/.test(rest)) { out.push({ line, path: undefined, isRange: true }); continue }
    let m = rest.match(/^file name (.+?) \[/) ?? rest.match(/^(.+?):\d+ \[/) ?? rest.match(/^(.+?) \(/)
    const path = m && !m[1].startsWith('<') ? m[1] : undefined
    out.push({ line, path, isRange: false })
  }
  return out
}

/** At commit time only staged files and commits of the range block. Undefined means the scan found nothing that blocks this commit. */
async function commitScanReason($: EngineInterface, target: Target, scanner: string): Promise<string | undefined> {
  const path = target.root.replace(/\/$/, '') + '/' + scanner
  const exists = await run($, ['test', '-f', path])
  if (exists.exitCode !== 0) {
    return `${$.plugin.name}: the leak scan could not run, the scanner ${scanner} is missing from ${target.slug ?? 'the repository'}. Restore it, then retry.`
  }
  const r = await run($, ['python3', path, '--no-fetch'], { cwd: target.root, timeoutMs: 120_000 })
  if (r.exitCode === 0 && r.failed === undefined) return undefined
  if (r.exitCode !== 1 || r.failed !== undefined) {
    return `${$.plugin.name}: the leak scan could not run (the leak scanner), so nothing was checked. Fix the checker, then retry.`
  }
  const findings = findingsOf(r.stdout)
  const staged = await stagedPaths($, target.root)
  if (findings.length > 0 && staged !== undefined && findings.every(f => f.isRange || f.path !== undefined)) {
    const blocking = findings.filter(f => f.isRange || (f.path !== undefined && staged.has(f.path)))
    if (blocking.length === 0) return undefined // only unstaged or untracked files: this commit does not carry them
    return `${$.plugin.name}: the leak scan found problems in what this commit carries. Fix them, then retry.\n${blocking.slice(0, SUMMARY_LINES).map(f => f.line).join('\n')}`
  }
  const first = findings[0]?.line ?? summaryOf(r.stdout, r.stderr).split('\n')[0] ?? 'no location printed'
  return `${$.plugin.name}: the leak scan found problems, and its output does not say whether they sit in staged files or in untracked and unstaged ones, which it scans too. First location: ${first}. Commit, stash or ignore stray files, or fix the finding, then retry.\n${summaryOf(r.stdout, r.stderr)}`
}

async function scan($: EngineInterface, target: Target, withStaged: boolean, isCommit = false): Promise<string | undefined> {
  const scanner = target.policy?.leakScanner
  if (scanner) {
    const path = target.root.replace(/\/$/, '') + '/' + scanner
    const exists = await run($, ['test', '-f', path])
    if (exists.exitCode !== 0) {
      return `${$.plugin.name}: the leak scan could not run, the scanner ${scanner} is missing from ${target.slug ?? 'the repository'}. Restore it, then retry.`
    }
    const denied = isCommit
      ? await commitScanReason($, target, scanner)
      : await check($, 'the leak scanner', ['python3', path, '--no-fetch'], target.root)
    if (denied) return denied
  }
  if (withStaged) {
    const refs = await $.env.get('LOCAL_REFS_CHECKER')
    if (refs) {
      const denied = await check($, 'the local reference checker', ['python3', refs, '--staged'], target.root)
      if (denied) return denied
    }
  }
  return undefined
}

async function commitDecision($: EngineInterface, call: Call, target: Target): Promise<string | undefined> {
  const skip = ['-m', '-F', '-c', '-C', '-t', '--message', '--file', '--reuse-message', '--reedit-message', '--template']
  const skipped = call.args.includes('--no-verify') || hasShortFlag(call.args, 'n', skip)
  if (skipped || call.configs.some(c => c.toLowerCase().startsWith('core.hookspath'))) {
    return `${$.plugin.name}: ${target.slug} is public, so --no-verify, -n, and -c core.hooksPath are not allowed on a commit. Run the commit without them so the hooks and the leak scan run.`
  }
  return scan($, target, true, true)
}

function pushParts(args: readonly string[]) {
  const valueFlags = ['-o', '--push-option', '--repo', '--receive-pack', '--exec']
  const positional: string[] = []
  let isForce = false
  let isNoVerify = false
  let isBroad = false
  let isDelete = false
  for (let i = 0; i < args.length; i++) {
    const a = args[i]
    if (a === '--') { positional.push(...args.slice(i + 1)); break }
    if (valueFlags.includes(a)) { i++; continue }
    if (a === '--no-verify') { isNoVerify = true; continue }
    if (a === '--delete' || a === '-d') { isDelete = true; continue }
    if (a === '--force' || a === '-f' || a.startsWith('--force-with-lease') || a === '--force-if-includes') { isForce = true; continue }
    if (a === '--all' || a === '--mirror') { isBroad = true; continue }
    if (/^-[A-Za-z]+$/.test(a)) { if (a.includes('f')) isForce = true; continue }
    if (a.startsWith('-')) continue
    positional.push(a)
  }
  return { positional, isForce, isNoVerify, isBroad, isDelete }
}

async function pushDecision($: EngineInterface, call: Call, target: Target): Promise<string | undefined> {
  const name = $.plugin.name
  const policy = target.policy as RemotePolicy
  const { positional, isForce, isNoVerify, isBroad, isDelete } = pushParts(call.args)
  if (isNoVerify) return `${name}: ${target.slug} is public, so --no-verify is not allowed on a push. Run the push without it.`
  if (isForce) return `${name}: ${target.slug} is public, so a force push is not allowed. Push normally, or ask the person to run it.`
  const refspecs = positional.slice(1)
  if (refspecs.some(r => r.startsWith('+'))) {
    return `${name}: ${target.slug} is public, so a force refspec (a leading +) is not allowed.`
  }
  if (isBroad) {
    return `${name}: ${target.slug} is public, so --all and --mirror are not allowed because they reach every branch. Name the branch to push.`
  }

  const destinations: string[] = []
  if (isDelete && refspecs.length === 0) {
    return `${name}: ${target.slug} is public, and this delete does not name a branch, so it was held. Name the branch to delete.`
  }
  if (refspecs.length === 0) {
    destinations.push('HEAD')
  } else {
    for (const r of refspecs) {
      const colon = r.indexOf(':')
      destinations.push(colon === -1 ? r : r.slice(colon + 1))
    }
  }
  const branches: string[] = []
  for (const d of destinations) {
    let b = d.replace(/^refs\/heads\//, '')
    if (b === 'HEAD' || b === '') {
      const cur = await run($, ['git', '-C', target.root, 'rev-parse', '--abbrev-ref', 'HEAD'])
      b = cur.exitCode === 0 ? cur.stdout.trim() : ''
      if (!b || b === 'HEAD') {
        return `${name}: could not work out which branch this push reaches in ${target.slug}, so it was held. Name the branch explicitly.`
      }
    }
    branches.push(b)
  }

  for (const b of branches) {
    if (policy.deniedBranches.includes(b)) {
      if (isDelete || refspecs.some(r => r.startsWith(':'))) {
        return `${name}: deleting ${b} in ${target.slug} is not allowed from here. Ask the person to delete it.`
      }
      return `${name}: pushing to ${b} in ${target.slug} is not allowed from here. Push a feature branch and open a pull request instead.`
    }
  }
  const scanned = await scan($, target, false)
  if (scanned) return scanned

  const confirmBranch = branches.find(b => policy.confirmBranches.includes(b))
  if (confirmBranch !== undefined) {
    const proceed = await confirm($, `Push to ${confirmBranch} in ${target.slug}? This publishes to a public repository.`, 'Public push')
    if (!proceed) return `${name}: the push to ${confirmBranch} was cancelled.`
  }
  return undefined
}

async function confirm($: EngineInterface, question: string, header: string): Promise<boolean> {
  try {
    const answer = await $.ui.ask(question, { header, options: ['Proceed', 'Cancel'] })
    return answer === 'Proceed'
  } catch {
    return false // dismissed, or no one to ask
  }
}

async function guard($: EngineInterface, e: { command: string }) {
  for (const call of callsOf(e.command)) {
    if (call.sub !== 'commit' && call.sub !== 'push') continue
    const target = await targetOf($, call.dir)
    if (!target.policy) continue
    const reason = call.sub === 'commit' ? await commitDecision($, call, target) : await pushDecision($, call, target)
    if (reason) return { deny: reason }
  }
  return undefined
}

export const register: Register = on => {
  on('tool.call', { tool: 'Bash' }, async ($, e, next) => {
    const held = await guard($, e)
    if (held) return held
    return next(e)
  }).catch(denyOnFailure)
}
