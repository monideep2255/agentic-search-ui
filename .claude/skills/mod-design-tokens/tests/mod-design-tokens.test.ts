import { test, expect } from 'claude-code/testing'

type World = { now: number; stdout: string; exitCode: number; runs: number; toasts: string[]; statuses: Array<string | undefined>; afterMs: number[]; denied?: boolean }

const OUT = (...lines: string[]) => `error: ${lines.length} colour(s) not in the design system palette\n${lines.map(l => '  ' + l).join('\n')}\n`

function fake(on: any, w: World, fireAfter = true) {
  on('tool.call', () => (w.denied ? { deny: 'no' } : { result: 'ok' }) as never)
  on('session.repo', () => ({ value: { root: '/repo', remote: null, internal: false } }))
  on('clock.now', () => ({ value: w.now }))
  on('clock.after', (_: unknown, e: { ms: number }) => { w.afterMs.push(e.ms); return { value: { cancel: () => {} } } })
  on('process.run', (_: unknown, e: { argv: string[]; init?: { cwd?: string } }) => {
    w.runs++
    expect(e.argv).toEqual(['python3', 'tracker/check_design_tokens.py'])
    expect(e.init?.cwd).toBe('/repo')
    return { value: { exitCode: w.exitCode, stdout: w.stdout, stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
  })
  on('ui.toast', (_: unknown, e: { text: string }) => { w.toasts.push(e.text); return { value: undefined } })
  on('ui.status', (_: unknown, e: { text?: string }) => { w.statuses.push(e.text); return { value: undefined } })
}

const world = (): World => ({ now: 1_000_000, stdout: '', exitCode: 1, runs: 0, toasts: [], statuses: [], afterMs: [] })
const edit = ($: any, file = '/repo/frontend/src/components/A.tsx') => $.tool.call({ tool: 'Edit', file_path: file, old_string: 'a', new_string: 'b' })

test('a new finding toasts', async ($, on) => {
  const w = world(); fake(on, w)
  w.stdout = OUT('frontend/src/components/A.tsx:12: #123ABC')
  await edit($)
  expect(w.runs).toBe(1)
  expect(w.toasts).toEqual(['design tokens: frontend/src/components/A.tsx:12 colour #123ABC is not in the palette'])
})

test('the same finding on the next run is silent, even when its line moved', async ($, on) => {
  const w = world(); fake(on, w)
  w.stdout = OUT('frontend/src/components/A.tsx:12: #123ABC')
  await edit($)
  w.now += 25_000
  w.stdout = OUT('frontend/src/components/A.tsx:15: #123ABC')
  await edit($)
  expect(w.runs).toBe(2)
  expect(w.toasts.length).toBe(1)
})

test('at most three findings toast', async ($, on) => {
  const w = world(); fake(on, w)
  w.stdout = OUT('frontend/src/a.ts:1: #111111', 'frontend/src/a.ts:2: #222222', 'frontend/src/a.ts:3: #333333', 'frontend/src/a.ts:4: #444444')
  await edit($)
  expect(w.toasts.length).toBe(3)
})

test('an edit inside the debounce window waits instead of running', async ($, on) => {
  const w = world(); fake(on, w)
  await edit($)
  w.now += 5_000
  await edit($)
  await edit($)
  expect(w.runs).toBe(1)
  expect(w.afterMs).toEqual([15_000])
})

test('a stale pending flag left by a hot reload does not hold the check off forever', async ($, on) => {
  const w = world(); fake(on, w)
  await edit($)
  w.now += 5_000
  await edit($)
  expect(w.runs).toBe(1)
  expect(w.afterMs).toEqual([15_000])
  // The timer was cancelled by a reload and never fired: isPending is still true. Well past the window, an edit runs.
  w.now += 60_000
  await edit($)
  expect(w.runs).toBe(2)
})

test('a path outside frontend/src is ignored', async ($, on) => {
  const w = world(); fake(on, w)
  await edit($, '/repo/src/app.py')
  await edit($, '/repo/frontend/e2e/a.ts')
  await edit($, '/repo/frontend/src/readme.md')
  expect(w.runs).toBe(0)
})

test('a Write to a css file under frontend/src runs the check', async ($, on) => {
  const w = world(); fake(on, w)
  await $.tool.call({ tool: 'Write', file_path: '/repo/frontend/src/index.css', content: 'a{}' })
  expect(w.runs).toBe(1)
})

test('a script failure sets the status line and stays quiet', async ($, on) => {
  const w = world(); fake(on, w)
  w.exitCode = 2; w.stdout = ''
  await edit($)
  expect(w.statuses).toContain('design tokens: check failed')
  expect(w.toasts).toEqual([])
})

test('a denied edit does not run the check', async ($, on) => {
  const w = world(); fake(on, w)
  w.denied = true
  await edit($)
  expect(w.runs).toBe(0)
})
