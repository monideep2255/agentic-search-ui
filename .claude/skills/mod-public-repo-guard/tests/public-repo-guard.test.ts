import { test, expect } from 'claude-code/testing'

const PLUGIN = 'mod-public-repo-guard'

type Answer = { exitCode: number; stdout?: string; stderr?: string }
type Setup = {
  remote?: string | null
  root?: string
  branch?: string
  scanner?: Answer
  scannerExists?: boolean
  refs?: Answer
  dirRemotes?: Record<string, string>
  refsPath?: string
  ask?: () => string
  staged?: string[]
}

const DE = 'https://github.com/monideep2255/agentic-search-data-engineering.git'
const UI = 'git@github.com:monideep2255/agentic-search-ui.git'
const PRIVATE = 'https://github.com/someone/private-thing.git'

function result(a: Answer) {
  return { exitCode: a.exitCode, stdout: a.stdout ?? '', stderr: a.stderr ?? '', isStdoutTruncated: false, isStderrTruncated: false }
}

function arrange(on: any, s: Setup, log: string[][] = []) {
  on('tool.call', (_$: unknown, e: { tool: string; questions?: { question: string }[] }) => {
    if (e.tool === 'AskUserQuestion' && s.ask) {
      const a = s.ask()
      return { result: { questions: e.questions, answers: { [e.questions?.[0].question ?? '']: a } } } as never
    }
    return { result: 'ran' } as never
  })
  on('session.repo', () => ({ value: { root: s.root ?? '/work/repo', remote: s.remote === undefined ? PRIVATE : s.remote, internal: false } }))
  on('env.get', () => ({ value: s.refsPath }))
  on('process.run', (_$: unknown, e: { argv: string[] }) => {
    const argv = e.argv
    log.push(argv)
    if (argv[0] === 'git') {
      const rest = argv.slice(argv[1] === '-C' ? 3 : 1)
      const dir = argv[1] === '-C' ? argv[2] : undefined
      if (rest[0] === 'remote') return { value: result({ exitCode: 0, stdout: (s.dirRemotes?.[dir ?? ''] ?? PRIVATE) + '\n' }) }
      if (rest[0] === 'diff' && rest[1] === '--cached') return { value: result({ exitCode: 0, stdout: (s.staged ?? []).map(p => p + '\0').join('') }) }
      if (rest[0] === 'rev-parse' && rest[1] === '--show-toplevel') return { value: result({ exitCode: 0, stdout: dir + '\n' }) }
      if (rest[0] === 'rev-parse') return { value: result({ exitCode: 0, stdout: (s.branch ?? 'feature/x') + '\n' }) }
    }
    if (argv[0] === 'test') return { value: result({ exitCode: s.scannerExists === false ? 1 : 0 }) }
    if (argv[0] === 'python3' && argv[argv.length - 1] === '--no-fetch') return { value: result(s.scanner ?? { exitCode: 0 }) }
    if (argv[0] === 'python3' && argv[argv.length - 1] === '--staged') return { value: result(s.refs ?? { exitCode: 0 }) }
    return { value: result({ exitCode: 0 }) }
  })
}

test('a private repository commit passes untouched', async ($, on) => {
  const log: string[][] = []
  arrange(on, { remote: PRIVATE }, log)
  const r = await $.tool.call({ tool: 'Bash', command: 'git commit --no-verify -m x' })
  expect(r.deny).toBeUndefined()
  expect(log.filter(a => a[0] === 'python3').length).toBe(0)
})

test('a public commit with --no-verify denies', async ($, on) => {
  arrange(on, { remote: DE })
  const r = await $.tool.call({ tool: 'Bash', command: 'git commit --no-verify -m x' })
  expect(r.deny).toContain(PLUGIN)
  expect(r.deny).toContain('--no-verify')
})

test('a public commit with -c core.hooksPath denies, in any spelling, while other -c settings pass', async ($, on) => {
  arrange(on, { remote: DE })
  for (const cmd of [
    'git -c core.hooksPath=/dev/null commit -m x',
    'git -c core.hookspath=/dev/null commit -m x',
    'git -ccore.hooksPath=/dev/null commit -m x',
    'git -c user.name=x -c core.hooksPath=. commit -m x',
  ]) {
    const r = await $.tool.call({ tool: 'Bash', command: cmd })
    expect(r.deny).toContain('core.hooksPath')
  }
  const ok = await $.tool.call({ tool: 'Bash', command: 'git -c user.name=x commit -m x' })
  expect(ok.deny).toBeUndefined()
})

test('a public commit with -n or a -an cluster denies', async ($, on) => {
  arrange(on, { remote: DE })
  const a = await $.tool.call({ tool: 'Bash', command: 'git commit -n -m x' })
  expect(a.deny).toContain('-n')
  const b = await $.tool.call({ tool: 'Bash', command: 'git commit -anm x' })
  expect(b.deny).toContain('-n')
})

test('a message that contains an n is not mistaken for the flag', async ($, on) => {
  arrange(on, { remote: DE })
  const r = await $.tool.call({ tool: 'Bash', command: 'git commit -m "-n fix"' })
  expect(r.deny).toBeUndefined()
})

test('scanner exit 0 passes a public commit', async ($, on) => {
  arrange(on, { remote: DE, scanner: { exitCode: 0 } })
  const r = await $.tool.call({ tool: 'Bash', command: 'git commit -m x' })
  expect(r.deny).toBeUndefined()
})

test('scanner exit 1 denies with its summary, capped at 30 lines', async ($, on) => {
  const many = Array.from({ length: 45 }, (_, i) => `finding ${i}`).join('\n')
  arrange(on, { remote: DE, scanner: { exitCode: 1, stdout: many } })
  const r = await $.tool.call({ tool: 'Bash', command: 'git commit -m x' })
  expect(r.deny).toContain('finding 0')
  expect(r.deny).toContain('finding 29')
  expect(r.deny).not.toContain('finding 30')
  expect(r.deny).toContain('15 more lines')
})

test('scanner exit 2 denies as could not run', async ($, on) => {
  arrange(on, { remote: DE, scanner: { exitCode: 2, stderr: 'CANNOT RUN' } })
  const r = await $.tool.call({ tool: 'Bash', command: 'git commit -m x' })
  expect(r.deny).toContain('the leak scan could not run')
})

test('a run failure of the scanner denies', async ($, on) => {
  on('tool.call', () => ({ result: 'ran' }) as never)
  on('session.repo', () => ({ value: { root: '/work/repo', remote: DE, internal: false } }))
  on('process.run', (_$: unknown, e: { argv: string[] }) => {
    if (e.argv[0] === 'test') return { value: result({ exitCode: 0 }) }
    throw new Error('spawn failed')
  })
  const r = await $.tool.call({ tool: 'Bash', command: 'git commit -m x' })
  expect(r.deny).toContain('the leak scan could not run')
})

test('a configured scanner that is missing denies', async ($, on) => {
  arrange(on, { remote: DE, scannerExists: false })
  const r = await $.tool.call({ tool: 'Bash', command: 'git commit -m x' })
  expect(r.deny).toContain('the leak scan could not run')
})

test('a remote with no scanner configured is skipped', async ($, on) => {
  const log: string[][] = []
  arrange(on, { remote: 'https://github.com/monideep2255/ai-chief-of-staff.git' }, log)
  const r = await $.tool.call({ tool: 'Bash', command: 'git commit -m x' })
  expect(r.deny).toBeUndefined()
  expect(log.filter(a => a[0] === 'python3').length).toBe(0)
})

test('LOCAL_REFS_CHECKER unset is skipped', async ($, on) => {
  const log: string[][] = []
  arrange(on, { remote: DE }, log)
  const r = await $.tool.call({ tool: 'Bash', command: 'git commit -m x' })
  expect(r.deny).toBeUndefined()
  expect(log.some(a => a[a.length - 1] === '--staged')).toBe(false)
})

test('LOCAL_REFS_CHECKER set and passing runs with --staged', async ($, on) => {
  const log: string[][] = []
  arrange(on, { remote: DE, refs: { exitCode: 0 }, refsPath: '/checker/verify.py' }, log)
  const r = await $.tool.call({ tool: 'Bash', command: 'git commit -m x' })
  expect(r.deny).toBeUndefined()
  expect(log.some(a => a[1] === '/checker/verify.py' && a[2] === '--staged')).toBe(true)
})

test('LOCAL_REFS_CHECKER set and failing denies', async ($, on) => {
  arrange(on, { remote: DE, refs: { exitCode: 1, stdout: 'local path in README' }, refsPath: '/checker/verify.py' })
  const r = await $.tool.call({ tool: 'Bash', command: 'git commit -m x' })
  expect(r.deny).toContain('local path in README')
})

test('force pushes deny in every spelling', async ($, on) => {
  arrange(on, { remote: DE, branch: 'feature/x' })
  for (const cmd of [
    'git push --force origin feature/x',
    'git push -f origin feature/x',
    'git push --force-with-lease origin feature/x',
    'git push origin +feature/x',
    'git push --no-verify origin feature/x',
  ]) {
    const r = await $.tool.call({ tool: 'Bash', command: cmd })
    expect(r.deny).toContain(PLUGIN)
  }
})

test('a push to production denies, explicit or by current branch', async ($, on) => {
  arrange(on, { remote: DE, branch: 'production' })
  const a = await $.tool.call({ tool: 'Bash', command: 'git push origin HEAD:production' })
  expect(a.deny).toContain('production')
  const b = await $.tool.call({ tool: 'Bash', command: 'git push' })
  expect(b.deny).toContain('production')
})

test('data engineering denies develop, a feature branch passes after the scan', async ($, on) => {
  arrange(on, { remote: DE, branch: 'feature/x' })
  const a = await $.tool.call({ tool: 'Bash', command: 'git push origin develop' })
  expect(a.deny).toContain('develop')
  const b = await $.tool.call({ tool: 'Bash', command: 'git push -u origin feature/x' })
  expect(b.deny).toBeUndefined()
})

test('a failing scan blocks an otherwise allowed push', async ($, on) => {
  arrange(on, { remote: DE, scanner: { exitCode: 1, stdout: 'leak here' } })
  const r = await $.tool.call({ tool: 'Bash', command: 'git push origin feature/x' })
  expect(r.deny).toContain('leak here')
})

test('a push to UI develop asks, and Cancel denies', async ($, on) => {
  arrange(on, { remote: UI, branch: 'feature/x', ask: () => 'Cancel' })
  const r = await $.tool.call({ tool: 'Bash', command: 'git push origin develop' })
  expect(r.deny).toContain('cancelled')
})

test('a push to UI develop asks, and Proceed passes', async ($, on) => {
  arrange(on, { remote: UI, branch: 'feature/x', ask: () => 'Proceed' })
  const r = await $.tool.call({ tool: 'Bash', command: 'git push origin develop' })
  expect(r.deny).toBeUndefined()
})

test('any other answer denies', async ($, on) => {
  arrange(on, { remote: UI, ask: () => 'proceed anyway' })
  const r = await $.tool.call({ tool: 'Bash', command: 'git push origin develop' })
  expect(r.deny).toContain('cancelled')
})

test('a dismissed dialog denies', async ($, on) => {
  arrange(on, { remote: UI, ask: () => { throw new Error('dismissed') } })
  const r = await $.tool.call({ tool: 'Bash', command: 'git push origin develop' })
  expect(r.deny).toContain('cancelled')
})

test('UI main is denied outright', async ($, on) => {
  arrange(on, { remote: UI })
  const r = await $.tool.call({ tool: 'Bash', command: 'git push origin main' })
  expect(r.deny).toContain('main')
})

test('git -C <dir> push resolves the target from that directory', async ($, on) => {
  arrange(on, { remote: PRIVATE, dirRemotes: { '/other/ui-clone': UI } })
  const r = await $.tool.call({ tool: 'Bash', command: 'git -C /other/ui-clone push origin main' })
  expect(r.deny).toContain('main')
})

test('cd <dir> && git push resolves the target from that directory', async ($, on) => {
  arrange(on, { remote: PRIVATE, dirRemotes: { '/other/de-clone': DE } })
  const r = await $.tool.call({ tool: 'Bash', command: 'cd /other/de-clone && git push origin production' })
  expect(r.deny).toContain('production')
})

test('a private -C target stays untouched even when the session repository is public', async ($, on) => {
  arrange(on, { remote: DE, dirRemotes: { '/other/private': PRIVATE } })
  const r = await $.tool.call({ tool: 'Bash', command: 'git -C /other/private push --force origin main' })
  expect(r.deny).toBeUndefined()
})

test('a thrown error denies', async ($, on) => {
  on('tool.call', () => ({ result: 'ran' }) as never)
  on('session.repo', () => { throw new Error('boom') })
  const r = await $.tool.call({ tool: 'Bash', command: 'git push origin main' })
  expect(r.deny).toContain(PLUGIN)
  expect(r.deny).toContain('the guard failed')
})

test('commands that are not commit or push pass', async ($, on) => {
  arrange(on, { remote: DE })
  const r = await $.tool.call({ tool: 'Bash', command: 'git status && ls' })
  expect(r.deny).toBeUndefined()
})

test('commit: a finding only in an untracked or unstaged file does not block', async ($, on) => {
  arrange(on, { remote: DE, staged: ['src/app.py'], scanner: { exitCode: 1, stdout: 'FAIL scratch/notes.md:3 [local-path] /***\nFAIL file name scratch/notes.md [x] y\n' } })
  const r = await $.tool.call({ tool: 'Bash', command: 'git commit -m x' })
  expect(r.deny).toBeUndefined()
})

test('commit: a finding in a staged file or a commit of the range blocks', async ($, on) => {
  arrange(on, { remote: DE, staged: ['src/app.py'], scanner: { exitCode: 1, stdout: 'FAIL scratch/notes.md:3 [local-path] /***\nFAIL src/app.py:9 [secret-assignment] a***\n' } })
  const a = await $.tool.call({ tool: 'Bash', command: 'git commit -m x' })
  expect(a.deny).toContain('src/app.py:9')
  expect(a.deny).not.toContain('scratch/notes.md')
})

test('commit: a finding in a commit of the range blocks', async ($, on) => {
  arrange(on, { remote: DE, staged: [], scanner: { exitCode: 1, stdout: 'FAIL commit abcd1234 docs/a.md:2 [jwt] e***\n' } })
  const b = await $.tool.call({ tool: 'Bash', command: 'git commit -m x' })
  expect(b.deny).toContain('commit abcd1234')
})

test('commit: output that cannot be attributed denies and says untracked files are scanned too', async ($, on) => {
  arrange(on, { remote: DE, staged: ['src/app.py'], scanner: { exitCode: 1, stdout: 'FAIL <file name hidden, a***>:1 [x] y\n' } })
  const r = await $.tool.call({ tool: 'Bash', command: 'git commit -m x' })
  expect(r.deny).toContain('untracked and unstaged')
  expect(r.deny).toContain('First location')
  expect(r.deny).toContain('hidden')
})

test('push keeps the full scan: an untracked-file finding still blocks', async ($, on) => {
  arrange(on, { remote: DE, branch: 'feature/x', staged: [], scanner: { exitCode: 1, stdout: 'FAIL scratch/notes.md:3 [local-path] /***\n' } })
  const r = await $.tool.call({ tool: 'Bash', command: 'git push origin feature/x' })
  expect(r.deny).toContain('found problems')
})

test('push --delete and :branch deny for protected branches', async ($, on) => {
  arrange(on, { remote: DE, branch: 'feature/x' })
  for (const cmd of ['git push --delete origin main', 'git push origin --delete production', 'git push origin :develop', 'git push -d origin main']) {
    const r = await $.tool.call({ tool: 'Bash', command: cmd })
    expect(r.deny).toContain('deleting')
  }
  const ok = await $.tool.call({ tool: 'Bash', command: 'git push origin --delete feature/old' })
  expect(ok.deny).toBeUndefined()
})

test('an ssh remote with a port resolves to owner and name', async ($, on) => {
  arrange(on, { remote: 'ssh://git@github.com:22/monideep2255/agentic-search-data-engineering.git', branch: 'feature/x' })
  const r = await $.tool.call({ tool: 'Bash', command: 'git push --force origin feature/x' })
  expect(r.deny).toContain('force push')
})

test('env -C resolves the target directory like -C', async ($, on) => {
  arrange(on, { remote: PRIVATE, dirRemotes: { sub: DE }, branch: 'production' })
  const r = await $.tool.call({ tool: 'Bash', command: 'env -C sub git push origin HEAD:production' })
  expect(r.deny).toContain('production')
})
