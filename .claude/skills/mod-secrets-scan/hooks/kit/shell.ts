// Shell command parsing shared by the agent mods. Copied into every mod's
// hooks/kit/ folder by sync_mods.py; edit the canonical copy only.
//
// This is a reader of command text, not a shell. A guard built on it is a
// safety net: aliases, scripts, and generated commands still get past it.

/** Split a command line into simple commands, including $(...) and `...` bodies. */
export function segments(command: string): string[] {
  const out: string[] = []
  const inner: string[] = []
  let cur = ''
  let quote: '"' | "'" | null = null
  for (let i = 0; i < command.length; i++) {
    const c = command[i]
    if (quote) {
      if (c === quote) quote = null
      else if (c === '\\' && quote === '"') { cur += c + (command[i + 1] ?? ''); i++; continue }
      cur += c
      continue
    }
    if (c === '"' || c === "'") { quote = c; cur += c; continue }
    if (c === '\\') { cur += c + (command[i + 1] ?? ''); i++; continue }
    if (c === '$' && command[i + 1] === '(') {
      const end = matchParen(command, i + 1)
      inner.push(command.slice(i + 2, end))
      cur += command.slice(i, end + 1)
      i = end
      continue
    }
    if (c === '`') {
      const end = command.indexOf('`', i + 1)
      const stop = end === -1 ? command.length : end
      inner.push(command.slice(i + 1, stop))
      cur += command.slice(i, stop + 1)
      i = stop
      continue
    }
    if (c === ';' || c === '\n' || c === '|' || c === '&') {
      if (cur.trim()) out.push(cur.trim())
      cur = ''
      if ((c === '|' || c === '&') && command[i + 1] === c) i++
      continue
    }
    cur += c
  }
  if (cur.trim()) out.push(cur.trim())
  for (const seg of [...out]) {
    const body = shellBody(seg)
    if (body !== undefined) out.push(...segments(body))
  }
  for (const body of inner) out.push(...segments(body))
  return out
}

function matchParen(s: string, open: number): number {
  let depth = 0
  for (let i = open; i < s.length; i++) {
    if (s[i] === '(') depth++
    else if (s[i] === ')') { depth--; if (depth === 0) return i }
  }
  return s.length
}

/** Split one simple command into words, removing quotes. */
export function words(segment: string): string[] {
  const out: string[] = []
  let cur = ''
  let has = false
  let quote: '"' | "'" | null = null
  for (let i = 0; i < segment.length; i++) {
    const c = segment[i]
    if (quote) {
      if (c === quote) quote = null
      else if (c === '\\' && quote === '"' && i + 1 < segment.length) { cur += segment[++i] }
      else cur += c
      continue
    }
    if (c === '"' || c === "'") { quote = c; has = true; continue }
    if (c === '\\' && i + 1 < segment.length) { cur += segment[++i]; has = true; continue }
    if (/\s/.test(c)) { if (has || cur) out.push(cur); cur = ''; has = false; continue }
    cur += c
    has = true
  }
  if (has || cur) out.push(cur)
  return out
}

const WRAPPERS = new Set(['sudo', 'env', 'command', 'nohup', 'time', 'exec', 'builtin', 'nice', 'caffeinate', 'xargs'])

// Options of a wrapper that take a separate value word, which must not be read as the program.
const VALUE_FLAGS: Record<string, ReadonlySet<string>> = {
  env: new Set(['-C', '--chdir', '-u', '--unset']),
  sudo: new Set(['-u', '--user', '-g', '--group', '-D', '--chdir']),
  nice: new Set(['-n', '--adjustment']),
  xargs: new Set(['-n', '-I', '-P', '-L', '-d', '-s', '-E', '-a', '--max-args', '--replace', '--max-procs', '--max-lines', '--delimiter']),
}

const SHELLS = new Set(['bash', 'sh', 'zsh'])

// Accepted gaps, because this is a reader of text and not a shell: `eval "..."`,
// a double-quoted `"$(...)"`, `bash script.sh`, aliases, and generated commands
// still get past it. `bash -c`, `sh -c` and `zsh -c` are read (see segments()).

export type ProgramInfo = {
  /** Words of the command with leading VAR=value pairs and wrappers removed. */
  words: string[]
  /** Directory set by `env -C <dir>` (or `--chdir`), if any. */
  cwd?: string
}

/** Like program(), and also reports the directory an `env -C` wrapper sets. */
export function programInfo(segment: string): ProgramInfo {
  let w = words(segment)
  let cwd: string | undefined
  let i = 0
  while (i < w.length) {
    if (/^[A-Za-z_][A-Za-z0-9_]*=/.test(w[i])) { i++; continue }
    const name = basename(w[i])
    if (!WRAPPERS.has(name)) break
    i++
    const valued = VALUE_FLAGS[name]
    while (i < w.length && w[i].startsWith('-')) {
      const flag = w[i]
      if (name === 'env' && (flag === '-S' || flag === '--split-string')) {
        // env -S "a b c": the string is re-split into words and read in place.
        w = [...w.slice(0, i), ...words(w[i + 1] ?? ''), ...w.slice(i + 2)]
        continue
      }
      if (name === 'env' && flag.startsWith('--split-string=')) {
        w = [...w.slice(0, i), ...words(flag.slice('--split-string='.length)), ...w.slice(i + 1)]
        continue
      }
      if (name === 'env' && (flag === '-C' || flag === '--chdir') && w[i + 1] !== undefined) { cwd = joinDir(cwd, w[i + 1]) }
      else if (name === 'env' && flag.startsWith('--chdir=')) cwd = joinDir(cwd, flag.slice('--chdir='.length))
      else if (name === 'env' && /^-C./.test(flag)) cwd = joinDir(cwd, flag.slice(2))
      if (valued?.has(flag)) { i += 2; continue }
      i++
    }
  }
  const out: ProgramInfo = { words: w.slice(i) }
  if (cwd !== undefined) out.cwd = cwd
  return out
}

/** Words of a simple command with leading VAR=value pairs and wrapper commands removed. */
export function program(segment: string): string[] {
  return programInfo(segment).words
}

function joinDir(base: string | undefined, dir: string): string {
  if (dir.startsWith('/') || dir.startsWith('~') || !base) return dir
  return base.replace(/\/$/, '') + '/' + dir
}

/** The command line passed to `bash -c`, `sh -c` or `zsh -c` (also `-lc` style clusters), if any. */
function shellBody(segment: string): string | undefined {
  const p = program(segment)
  if (p.length < 3 || !SHELLS.has(basename(p[0]))) return undefined
  for (let i = 1; i < p.length - 1; i++) {
    if (p[i] === '--') return undefined
    if (/^-[A-Za-z]*c[A-Za-z]*$/.test(p[i])) return p[i + 1]
    if (!p[i].startsWith('-')) return undefined
  }
  return undefined
}

/** Every simple command in a command line, as program words. */
export function programs(command: string): string[][] {
  return segments(command).map(program).filter(p => p.length > 0)
}

export type GitCall = { cwd?: string; sub: string; args: string[] }

/** Every git invocation in a command line, with `-C <dir>` and `env -C <dir>` resolved and `-c k=v` skipped. */
export function gitCalls(command: string): GitCall[] {
  const calls: GitCall[] = []
  for (const seg of segments(command)) {
    const info = programInfo(seg)
    const p = info.words
    if (p.length === 0 || basename(p[0]) !== 'git') continue
    let cwd: string | undefined = info.cwd
    let i = 1
    while (i < p.length && p[i].startsWith('-')) {
      if (p[i] === '-C') { if (p[i + 1] !== undefined) cwd = joinDir(cwd, p[i + 1]); i += 2; continue }
      if (p[i] === '-c' || p[i] === '--git-dir' || p[i] === '--work-tree') { i += 2; continue }
      i++
    }
    if (i < p.length) calls.push({ cwd, sub: p[i], args: p.slice(i + 1) })
  }
  return calls
}

export function basename(path: string): string {
  const parts = path.split('/')
  return parts[parts.length - 1]
}
