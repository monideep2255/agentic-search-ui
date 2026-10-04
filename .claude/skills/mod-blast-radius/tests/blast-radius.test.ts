import { test, expect } from 'claude-code/testing'
import type { On } from 'claude-code'

import { config as live } from '../hooks/config.ts'
import { findRisky, slugOf } from '../hooks/rules.ts'

import { config as dataEngineering } from './fixtures/data-engineering.config.ts'
import { config as ui } from './fixtures/ui.config.ts'

type Reply = { exitCode?: number; stdout?: string; stderr?: string } | 'throw'
type Call = { argv: readonly string[]; cwd?: string }

/** Answers `$.process.run` from a function of the argument vector, recording each call. */
function fakeProcess(on: On, reply: (argv: readonly string[]) => Reply | undefined, calls: Call[] = []) {
  on('process.run', ($, e) => {
    calls.push({ argv: e.argv, cwd: e.init?.cwd })
    const r = reply(e.argv) ?? {}
    if (r === 'throw') throw new Error('could not start')
    return {
      value: {
        exitCode: r.exitCode ?? 0,
        stdout: r.stdout ?? '',
        stderr: r.stderr ?? '',
        isStdoutTruncated: false,
        isStderrTruncated: false,
      },
    }
  })
}

/**
 * The one generic tool.call fake: answers the AskUserQuestion dialog that
 * `$.ui.ask` raises with `answer` (or throws, a dismissal), runs `during`
 * while the question is open, and stands in for every other tool.
 */
function fakeTools(on: On, answer: string | 'throw', asked: string[] = [], during?: () => Promise<void>) {
  on('tool.call', async ($, e) => {
    if (e.tool === 'AskUserQuestion') {
      const questions = (e as never as { questions: { question: string }[] }).questions
      asked.push(questions[0].question)
      if (during) await during()
      if (answer === 'throw') throw new Error('dismissed')
      return { result: { questions, answers: { [questions[0].question]: answer } } } as never
    }
    return { result: 'ran' } as never
  })
}

function fakePane(on: On, isPlaced: boolean, opened: string[] = []) {
  on('ui.open', ($, e) => {
    opened.push(e.id)
    return { value: isPlaced ? { isPlaced: true } : { isPlaced: false, reason: 'terminal too narrow' } }
  })
  on('ui.close', () => ({ value: undefined }))
}

const rmReplies = (argv: readonly string[]): Reply | undefined => {
  if (argv[0] === 'du') return { stdout: '41984\tbuild\n' }
  if (argv[0] === 'git' && argv.includes('ls-files')) return { stdout: 'build\n' }
  return undefined
}

const PANE_PROPS = {
  title: 'Blast radius',
  isFocused: false,
  bodyColumns: 120,
  placement: 'dock' as const,
  scroll: { offset: 0, bodyRows: 40 },
  view: {},
}

test('a safe command passes through with no pane and no question', async ($, on) => {
  const opened: string[] = []
  const asked: string[] = []
  fakeTools(on, 'Cancel', asked)
  fakePane(on, true, opened)
  fakeProcess(on, () => undefined)
  const r = await $.tool.call({ tool: 'Bash', command: 'ls -la && git status' })
  expect(r.deny).toBeUndefined()
  expect(opened.length).toBe(0)
  expect(asked.length).toBe(0)
})

test('rm -rf build triggers, and Cancel denies', async ($, on) => {
  const opened: string[] = []
  const asked: string[] = []
  fakeTools(on, 'Cancel', asked)
  fakePane(on, true, opened)
  fakeProcess(on, rmReplies)
  const r = await $.tool.call({ tool: 'Bash', command: 'CLAUDE_APPROVED_DELETE=1 rm -rf build' })
  expect(r.deny).toContain('did not approve')
  expect(opened).toEqual(['blast-radius'])
  expect(asked[0]).toContain('rm -rf build')
  expect(asked[0]).toContain('1 path, 41 MB, 1 tracked file')
})

test('Proceed calls through to the tool', async ($, on) => {
  fakeTools(on, 'Proceed')
  fakePane(on, true)
  fakeProcess(on, rmReplies)
  const r = await $.tool.call({ tool: 'Bash', command: 'CLAUDE_APPROVED_DELETE=1 rm -rf build' })
  expect(r.deny).toBeUndefined()
  expect(r.result).toBe('ran')
})

test('a free-text answer other than Proceed denies', async ($, on) => {
  fakeTools(on, 'proceed please')
  fakePane(on, true)
  fakeProcess(on, rmReplies)
  const r = await $.tool.call({ tool: 'Bash', command: 'CLAUDE_APPROVED_DELETE=1 rm -rf build' })
  expect(r.deny).toContain('did not approve')
})

test('a dismissed question denies', async ($, on) => {
  fakeTools(on, 'throw')
  fakePane(on, true)
  fakeProcess(on, rmReplies)
  const r = await $.tool.call({ tool: 'Bash', command: 'CLAUDE_APPROVED_DELETE=1 rm -rf build' })
  expect(r.deny).toContain('did not approve')
})

test('the pane shows the full report while the question is open', async ($, on) => {
  let shown: string[] = []
  fakeTools(on, 'Cancel', [], async () => {
    const pane = await $.ui.mount({ plugin: 'mod-blast-radius', surface: 'terminal', component: 'Pane', requestId: 'blast-radius', props: PANE_PROPS })
    shown = (await pane.findAll({ type: 'Text' })).map(t => t.text ?? '')
    await pane.unmount()
  })
  fakePane(on, true)
  fakeProcess(on, rmReplies)
  await $.tool.call({ tool: 'Bash', command: 'CLAUDE_APPROVED_DELETE=1 rm -rf build' })
  expect(shown.join('\n')).toContain('build: 41 MB, tracked')
})

test('a dry run that fails is reported as failed, never as nothing affected', async ($, on) => {
  const asked: string[] = []
  let shown: string[] = []
  fakeTools(on, 'Cancel', asked, async () => {
    const pane = await $.ui.mount({ plugin: 'mod-blast-radius', surface: 'terminal', component: 'Pane', requestId: 'blast-radius', props: PANE_PROPS })
    shown = (await pane.findAll({ type: 'Text' })).map(t => t.text ?? '')
    await pane.unmount()
  })
  fakePane(on, true)
  fakeProcess(on, argv => (argv[0] === 'du' ? 'throw' : argv[0] === 'git' ? { exitCode: 128, stderr: 'fatal: not a git repository' } : undefined))
  const r = await $.tool.call({ tool: 'Bash', command: 'CLAUDE_APPROVED_DELETE=1 rm -rf build' })
  expect(r.deny).toContain('did not approve')
  expect(asked[0]).toContain('2 checks failed')
  const text = shown.join('\n')
  expect(text).toContain('size check failed')
  expect(text).toContain('tracked check failed')
})

test('a failed git dry run is shown as failed for git reset --hard', async ($, on) => {
  const asked: string[] = []
  fakeTools(on, 'Cancel', asked)
  fakePane(on, true)
  fakeProcess(on, () => ({ exitCode: 128, stderr: 'fatal: not a git repository' }))
  await $.tool.call({ tool: 'Bash', command: 'git reset --hard' })
  expect(asked[0]).toContain('dry run failed')
})

test('a guard that throws denies through its catch handler', async ($, on) => {
  fakeTools(on, 'Proceed')
  on('ui.open', () => {
    throw new Error('boom')
  })
  fakeProcess(on, rmReplies)
  const r = await $.tool.call({ tool: 'Bash', command: 'CLAUDE_APPROVED_DELETE=1 rm -rf build' })
  expect(r.deny).toContain('guard failed')
})

test('git clean -n passes through, and git clean -fd dry-runs with -n', async ($, on) => {
  const asked: string[] = []
  const calls: Call[] = []
  fakeTools(on, 'Cancel', asked)
  fakePane(on, true)
  fakeProcess(on, argv => (argv.includes('clean') ? { stdout: 'Would remove scratch/\n' } : undefined), calls)
  const safe = await $.tool.call({ tool: 'Bash', command: 'git clean -n -d' })
  expect(safe.deny).toBeUndefined()
  expect(asked.length).toBe(0)
  const risky = await $.tool.call({ tool: 'Bash', command: 'git clean -fd' })
  expect(risky.deny).toContain('did not approve')
  expect(calls.some(c => c.argv.join(' ') === 'git clean -fd -n')).toBe(true)
  expect(asked[0]).toContain('1 lines of output')
})

test('cd x && git push --force triggers and lists the commits that would be lost', async ($, on) => {
  const asked: string[] = []
  const calls: Call[] = []
  let shown: string[] = []
  fakeTools(on, 'Cancel', asked, async () => {
    const pane = await $.ui.mount({ plugin: 'mod-blast-radius', surface: 'terminal', component: 'Pane', requestId: 'blast-radius', props: PANE_PROPS })
    shown = (await pane.findAll({ type: 'Text' })).map(t => t.text ?? '')
    await pane.unmount()
  })
  fakePane(on, true)
  fakeProcess(on, argv => {
    const line = argv.join(' ')
    if (line.includes('@{u}')) return { stdout: 'origin/main\n' }
    if (line.endsWith('--verify HEAD')) return { stdout: 'aaaa\n' }
    if (line.endsWith('--verify refs/remotes/origin/main')) return { stdout: 'bbbb\n' }
    if (line.includes('log --oneline aaaa..bbbb')) return { stdout: '1234567 teammate fix\n89abcde teammate test\n' }
    return undefined
  }, calls)
  const r = await $.tool.call({ tool: 'Bash', command: 'cd x && git push --force' })
  expect(r.deny).toContain('did not approve')
  expect(asked[0]).toContain('2 remote commits would be lost')
  expect(calls.filter(c => c.argv[0] === 'git').every(c => c.cwd === 'x')).toBe(true)
  expect(shown.join('\n')).toContain('teammate fix')
})

test('a pane that cannot be seated falls back to the band', async ($, on) => {
  let shown: string[] = []
  fakeTools(on, 'Cancel', [], async () => {
    const band = await $.ui.mount({
      plugin: 'mod-blast-radius',
      surface: 'terminal',
      component: 'AbovePrompt',
      props: { hasSurvey: false, isWorking: true, maxRows: 20, bodyColumns: 120, scroll: { offset: 0, bodyRows: 19 }, view: {} },
    })
    shown = (await band.findAll({ type: 'Text' })).map(t => t.text ?? '')
    await band.unmount()
  })
  fakePane(on, false)
  fakeProcess(on, rmReplies)
  const r = await $.tool.call({ tool: 'Bash', command: 'CLAUDE_APPROVED_DELETE=1 rm -rf build' })
  expect(r.deny).toContain('did not approve')
  expect(shown.join('\n')).toContain('build: 41 MB, tracked')
})

test('the default classes trigger, and their safe forms do not', async () => {
  const risky = [
    'rm -r old',
    'sudo rm -rf /tmp/x',
    'rm --force *.txt',
    'rm -f a b c d',
    'rm -f /',
    'rm --recursive old',
    "find . -name '*.pyc' -exec rm {} +",
    'find build -execdir rm -f {} ;',
    "find . -name '*.pyc' -delete",
    'git reset --hard HEAD~1',
    'git -C sub clean -fdx',
    'git checkout -- src/app.py',
    'git checkout .',
    'git restore src/app.py',
    'git restore --staged --worktree src/app.py',
    'git branch -D feature',
    'git stash drop',
    'git stash clear',
    'git push -f origin main',
    'git push --force-with-lease',
    'git push origin +main',
    'alembic downgrade -1',
    'python -m alembic upgrade head',
    'python manage.py migrate',
    'psql -c "DROP TABLE runs"',
    'echo "TRUNCATE runs" | psql',
  ]
  const safe = [
    'rm notes.txt',
    'rm -f build/out.txt',
    'rm --force a b',
    'git reset --soft HEAD~1',
    'git clean --dry-run',
    'git checkout main',
    'git restore --staged src/app.py',
    'git branch -d merged',
    'git stash list',
    'git push origin main',
    'alembic upgrade head --sql',
    'alembic history',
    'python manage.py migrate --plan',
    'psql -c "SELECT 1"',
  ]
  for (const c of risky) expect(findRisky(c, []).length).toBeGreaterThan(0)
  for (const c of safe) expect(findRisky(c, [])).toEqual([])
})

test('the data engineering extra rules trigger', async () => {
  const rules = dataEngineering.extraRules
  const names = (c: string) => findRisky(c, rules).map(m => m.rule)
  expect(names('ssh example-host uptime')).toContain('ssh to a remote host')
  expect(names('age-load --input merged.jsonl')).toContain('age-load into the knowledge graph')
  expect(names('uv run age-load --input merged.jsonl')).toContain('age-load into the knowledge graph')
  expect(names(`psql -d kg -c "SELECT * FROM cypher('kg', $$ MATCH (n:Gene) DETACH DELETE n $$) as (a agtype)"`)).toContain('psql with write Cypher or DELETE FROM')
  expect(names(`psql -d kg -c "SELECT * FROM cypher('kg', $$ MERGE (n:Gene {id: 1}) $$) as (a agtype)"`)).toContain('psql with write Cypher or DELETE FROM')
  expect(names('psql -d kg -c "DELETE FROM staging"')).toContain('psql with write Cypher or DELETE FROM')
  expect(names('python -m system_02_knowledge_graph.loader.cli --batch 1000')).toContain('knowledge graph loader command line')
  expect(names('python3 system-02-knowledge-graph/loader/cli.py')).toContain('knowledge graph loader command line')
  expect(names(`psql -d kg -c "SET search_path = ag_catalog; SELECT * FROM cypher('kg', $$ MATCH (n) RETURN count(n) $$) as (c agtype)"`)).toEqual([])
  expect(names('python -m pytest tests')).toEqual([])
})

test('the ui extra rules trigger', async () => {
  const rules = ui.extraRules
  const names = (c: string) => findRisky(c, rules).map(m => m.rule)
  expect(names('railway down')).toContain('railway down')
  expect(names('railway delete')).toContain('railway delete')
  expect(names('railway service delete')).toContain('railway delete')
  expect(names('railway redeploy')).toContain('railway redeploy')
  expect(names('npx @railway/cli up')).toContain('railway up deploys over the live service')
  expect(names('railway variables --set KEY=value')).toContain('railway variables change on the live service')
  expect(names('alembic downgrade base')).toEqual(['alembic downgrade'])
  expect(names('railway status')).toEqual([])
  expect(names('railway logs --build')).toEqual([])
  expect(findRisky('railway down', rules)[0].plan).toEqual({ kind: 'argv', argv: ['railway', 'status'] })
})

test('kit wrappers: env -C, xargs, bash -c and nice are read through', async () => {
  const rules = (c: string) => findRisky(c, []).map(m => m.rule)
  expect(rules('env -C x rm -rf y')).toEqual(['rm -r or -f'])
  expect(findRisky('env -C x rm -rf y', [])[0].cwd).toBe('x')
  expect(rules('env -u HOME rm -rf y')).toEqual(['rm -r or -f'])
  expect(rules('env -S "rm -rf y"')).toEqual(['rm -r or -f'])
  expect(rules('sudo -u root rm -rf y')).toEqual(['rm -r or -f'])
  expect(rules('nice -n 10 rm -rf y')).toEqual(['rm -r or -f'])
  expect(rules('git ls-files -o | xargs rm -rf')).toEqual(['rm -r or -f'])
  expect(rules('ls | xargs -0 -n 1 -I {} rm -rf {}')).toEqual(['rm -r or -f'])
  expect(rules('bash -c "git push --force"')).toContain('git push --force')
  expect(rules("sh -c 'rm -rf build'")).toContain('rm -r or -f')
  expect(rules('zsh -lc "cd x && git reset --hard"')).toContain('git reset --hard')
  expect(findRisky('env -C sub git push --force origin x', [])[0].plan).toMatchObject({ kind: 'git-push', git: ['git', '-C', 'sub'] })
  expect(rules('bash script.sh')).toEqual([])
})

test('deferToPublicGuard: empty by default, filled in the public configs, and slugs resolve with a port', async ($, on) => {
  expect(dataEngineering.deferToPublicGuard).toEqual(['monideep2255/agentic-search-data-engineering'])
  expect(ui.deferToPublicGuard).toEqual(['monideep2255/agentic-search-ui'])
  expect(slugOf('ssh://git@github.com:22/Owner/Name.git')).toBe('owner/name')
  expect(slugOf('git@github.com:owner/name.git')).toBe('owner/name')
  // With the default empty list this repository still asks about a force push.
  const asked: string[] = []
  fakeTools(on, 'Cancel', asked)
  fakePane(on, true)
  fakeProcess(on, () => undefined)
  const r = await $.tool.call({ tool: 'Bash', command: 'git push --force origin feature/x' })
  expect(r.deny).toContain('did not approve')
  expect(asked.length).toBe(1)
})

test('skipUnless: under the personal config an rm the shell guard would refuse is not asked about, an approved one is; without it every rm asks', async ($, on) => {
  const asked: string[] = []
  fakeTools(on, 'Proceed', asked)
  fakePane(on, true)
  fakeProcess(on, rmReplies)
  // The module reads this repository's own config, so a public repository
  // (no skipUnless) checks the other branch: a plain rm is asked about.
  if (!live.skipUnless) {
    const plain = await $.tool.call({ tool: 'Bash', command: 'rm -rf build' })
    expect(plain.deny).toBeUndefined()
    expect(asked.length).toBe(1)
    expect(asked[0]).toContain('rm -rf build')
    return
  }
  {
    const plain = await $.tool.call({ tool: 'Bash', command: 'rm -rf build' })
    expect(plain.deny).toBeUndefined()
    expect(asked.length).toBe(0)
    const approved = await $.tool.call({ tool: 'Bash', command: 'CLAUDE_APPROVED_DELETE=1 rm -rf build' })
    expect(approved.deny).toBeUndefined()
    expect(asked.length).toBe(1)
    expect(asked[0]).toContain('rm -rf build')
    const found = await $.tool.call({ tool: 'Bash', command: 'find . -name x -delete' })
    expect(found.deny).toBeUndefined()
    expect(asked.length).toBe(2)
  }
})
