// Risky-command detection for mod-blast-radius: pure functions over command
// text, no `$`. Each match carries a plan for the dry run register.tsx runs.
//
// This reads command text, it is not a shell: aliases, scripts, and generated
// commands still get past it. It is a safety net, not a sandbox.

import { segments, programInfo, gitCalls, basename } from './kit/shell.ts'
import type { BlastRule } from './config.ts'

export type Plan =
  | { kind: 'rm'; targets: string[] }
  | { kind: 'argv'; argv: string[] }
  | { kind: 'git-reset'; git: string[] }
  | { kind: 'git-paths'; git: string[]; paths: string[] }
  | { kind: 'git-branch'; git: string[]; branches: string[] }
  | { kind: 'git-push'; git: string[]; args: string[] }
  | { kind: 'none' }

export type Match = {
  rule: string
  segment: string
  /** Working directory for the dry run, relative to the session's; undefined is the session's own. */
  cwd?: string
  /** False when a `cd` before this command could not be followed. */
  isCwdKnown: boolean
  plan: Plan
}

/** True when a short-flag cluster such as `-rfv` holds one of the letters. */
function cluster(arg: string, letters: string): boolean {
  if (!/^-[A-Za-z]+$/.test(arg)) return false
  return [...letters].some(l => arg.includes(l))
}

function nonFlags(args: readonly string[]): string[] {
  const out: string[] = []
  let isRest = false
  for (const a of args) {
    if (isRest) { out.push(a); continue }
    if (a === '--') { isRest = true; continue }
    if (!a.startsWith('-')) out.push(a)
  }
  return out
}

function gitPrefix(cwd: string | undefined): string[] {
  return cwd ? ['git', '-C', cwd] : ['git']
}

function checkGit(seg: string): { rule: string; plan: Plan } | undefined {
  const call = gitCalls(seg)[0]
  if (!call) return undefined
  const git = gitPrefix(call.cwd)
  const { sub, args } = call
  if (sub === 'reset' && args.includes('--hard')) {
    return { rule: 'git reset --hard', plan: { kind: 'git-reset', git } }
  }
  if (sub === 'clean') {
    const isDry = args.some(a => a === '-n' || a === '--dry-run' || cluster(a, 'n'))
    if (isDry) return undefined
    return { rule: 'git clean', plan: { kind: 'argv', argv: [...git, 'clean', ...args, '-n'] } }
  }
  if (sub === 'checkout') {
    const dash = args.indexOf('--')
    const paths = dash >= 0 ? args.slice(dash + 1) : args.includes('.') ? ['.'] : []
    if (paths.length === 0) return undefined
    return { rule: 'git checkout of paths', plan: { kind: 'git-paths', git, paths } }
  }
  if (sub === 'restore') {
    const isStaged = args.some(a => a === '--staged' || cluster(a, 'S'))
    const isWorktree = args.some(a => a === '--worktree' || cluster(a, 'W'))
    if (isStaged && !isWorktree) return undefined
    const paths: string[] = []
    for (let i = 0; i < args.length; i++) {
      const a = args[i]
      if (a === '--source' || a === '-s') { i++; continue }
      if (a === '--') { paths.push(...args.slice(i + 1)); break }
      if (!a.startsWith('-')) paths.push(a)
    }
    return { rule: 'git restore of the working tree', plan: { kind: 'git-paths', git, paths } }
  }
  if (sub === 'branch') {
    const isForceDelete =
      args.some(a => a === '-D' || cluster(a, 'D')) ||
      (args.some(a => a === '--delete' || a === '-d') && args.some(a => a === '--force' || a === '-f'))
    if (!isForceDelete) return undefined
    return { rule: 'git branch -D', plan: { kind: 'git-branch', git, branches: nonFlags(args) } }
  }
  if (sub === 'stash' && (args[0] === 'drop' || args[0] === 'clear')) {
    return { rule: `git stash ${args[0]}`, plan: { kind: 'argv', argv: [...git, 'stash', 'list'] } }
  }
  if (sub === 'push') {
    const isForce =
      args.some(a => a === '--force' || a === '-f' || a.startsWith('--force-with-lease') || cluster(a, 'f')) ||
      pushPositionals(args).slice(1).some(r => r.startsWith('+'))
    if (!isForce) return undefined
    return { rule: 'git push --force', plan: { kind: 'git-push', git, args } }
  }
  return undefined
}

/** The owner/name slug of a github remote in https or ssh form (a port is allowed), lowercased. */
export function slugOf(remote: string | null | undefined): string | undefined {
  if (!remote) return undefined
  const m = remote.trim().match(/^(?:https?:\/\/(?:[^@/]+@)?github\.com(?::\d+)?|ssh:\/\/(?:[^@/]+@)?github\.com(?::\d+)?|git@github\.com)[:/]+([^/:]+)\/([^/]+?)(?:\.git)?\/?$/i)
  return m ? `${m[1]}/${m[2]}`.toLowerCase() : undefined
}

/** Positional arguments of `git push`: the remote, then the refspecs. */
export function pushPositionals(args: readonly string[]): string[] {
  const out: string[] = []
  for (let i = 0; i < args.length; i++) {
    const a = args[i]
    if (a === '-o' || a === '--push-option' || a === '--repo' || a === '--receive-pack' || a === '--exec') { i++; continue }
    if (a === '--') { out.push(...args.slice(i + 1)); break }
    if (!a.startsWith('-')) out.push(a)
  }
  return out
}

function checkAlembic(words: string[]): { rule: string; plan: Plan } | undefined {
  const at = words.findIndex(w => basename(w) === 'alembic')
  if (at < 0) return undefined
  const isLauncher = at === 0 || (words[at - 1] === '-m' && at >= 2)
  if (!isLauncher) return undefined
  const rest = words.slice(at + 1)
  const passthrough: string[] = []
  let sub: string | undefined
  for (let i = 0; i < rest.length; i++) {
    const a = rest[i]
    if (a === '-c' || a === '--config' || a === '-n' || a === '--name' || a === '-x') {
      passthrough.push(a, rest[i + 1] ?? '')
      i++
      continue
    }
    if (a.startsWith('-')) continue
    sub = a
    break
  }
  if (sub !== 'upgrade' && sub !== 'downgrade') return undefined
  if (rest.includes('--sql')) return undefined
  return {
    rule: `alembic ${sub}`,
    plan: { kind: 'argv', argv: [...words.slice(0, at + 1), ...passthrough, 'current'] },
  }
}

function checkManagePy(words: string[]): { rule: string; plan: Plan } | undefined {
  const at = words.findIndex(w => basename(w) === 'manage.py')
  if (at < 0 || words[at + 1] !== 'migrate') return undefined
  if (words.includes('--plan')) return undefined
  return { rule: 'manage.py migrate', plan: { kind: 'argv', argv: [...words, '--plan'] } }
}

const GLOB = /[*?[]/

/**
 * `rm` is risky with recursion (-r, -R, --recursive), or with -f/--force when the
 * blast is wider than one plain file: a glob, more than 3 targets, or a target
 * of /, ~, ., .. or *.
 */
function isRiskyRm(args: readonly string[], targets: readonly string[]): boolean {
  const flags = args.slice(0, args.indexOf('--') >= 0 ? args.indexOf('--') : args.length).filter(a => a.startsWith('-'))
  if (flags.some(a => a === '--recursive' || cluster(a, 'rR'))) return true
  const isForce = flags.some(a => a === '--force' || cluster(a, 'f'))
  if (!isForce) return false
  if (targets.length > 3) return true
  return targets.some(t => GLOB.test(t) || t === '/' || t === '~' || t === '.' || t === '..' || t === '*')
}

/** Every risky simple command in a command line, in order, with its dry-run plan. */
export function findRisky(command: string, extraRules: readonly BlastRule[]): Match[] {
  const out: Match[] = []
  const seen = new Set<string>()
  let cwd: string | undefined
  let isCwdKnown = true
  let segCwd: string | undefined
  const add = (rule: string, segment: string, plan: Plan) => {
    const id = rule + '\u0000' + segment
    if (seen.has(id)) return
    seen.add(id)
    out.push({ rule, segment, cwd: segCwd, isCwdKnown, plan })
  }

  for (const seg of segments(command)) {
    const info = programInfo(seg)
    const words = info.words
    if (words.length === 0) continue
    const name = basename(words[0])
    // A git call carries its env -C directory in its own `git -C` prefix, so only other programs take it as cwd.
    segCwd = info.cwd && name !== 'git' ? (info.cwd.startsWith('/') || !cwd ? info.cwd : `${cwd}/${info.cwd}`) : cwd

    if (name === 'cd') {
      const dir = words[1]
      if (!dir || dir === '-' || dir.startsWith('~') || dir.includes('$')) isCwdKnown = false
      else if (dir.startsWith('/')) cwd = dir
      else cwd = cwd ? `${cwd}/${dir}` : dir
      continue
    }

    if (name === 'rm') {
      const args = words.slice(1)
      const targets = nonFlags(args)
      if (isRiskyRm(args, targets)) add('rm -r or -f', seg, { kind: 'rm', targets })
    }

    if (name === 'find') {
      const execAt = words.findIndex(w => w === '-exec' || w === '-execdir' || w === '-ok' || w === '-okdir')
      const isExecRm = execAt >= 0 && basename(words[execAt + 1] ?? '') === 'rm'
      if (words.includes('-delete')) {
        add('find -delete', seg, { kind: 'argv', argv: words.filter(w => w !== '-delete') })
      } else if (isExecRm) {
        const head = words.slice(0, execAt)
        add('find -exec rm', seg, { kind: 'argv', argv: head.length ? head : words.slice(0, 1) })
      }
    }

    if (name === 'git') {
      const hit = checkGit(seg)
      if (hit) add(hit.rule, seg, hit.plan)
    }

    const alembic = checkAlembic(words)
    if (alembic) add(alembic.rule, seg, alembic.plan)

    const manage = checkManagePy(words)
    if (manage) add(manage.rule, seg, manage.plan)

    if (name === 'psql' && /\b(DROP|TRUNCATE)\b/i.test(command)) {
      add('psql with DROP or TRUNCATE', seg, { kind: 'none' })
    }

    for (const rule of extraRules) {
      if (rule.match(words, seg, command)) {
        add(rule.name, seg, rule.dryRun ? { kind: 'argv', argv: [...rule.dryRun] } : { kind: 'none' })
      }
    }
  }
  return out
}
