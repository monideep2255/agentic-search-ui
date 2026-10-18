import { test, expect } from 'claude-code/testing'

const ok = () => ({ result: 'ran' }) as never
const FRONT = '/repo/frontend/src'

function complete(extra: Record<string, unknown> = {}) {
  return { answer: '', durationMs: 1, isAborted: false, turnId: 't1', reason: 'answer', ...extra }
}

type World = { toasts: string[]; runs: string[][]; cwds: Array<string | undefined>; timeouts: Array<number | undefined> }

function fake(on: any, o: { web?: 'up' | 'down'; api?: 'up' | 'down'; stdout?: string; exitCode?: number; specs?: string[]; throws?: string; stderr?: string } = {}): World {
  const w: World = { toasts: [], runs: [], cwds: [], timeouts: [] }
  on('session.repo', () => ({ value: { root: '/repo', remote: null, internal: false } }))
  on('turn.start', (_: unknown, e: any) => ({ turnId: e.turnId }))
  on('turn.complete', () => ({ text: '' }))
  on('ui.open', () => ({ value: { isPlaced: true } }) as never)
  on('ui.toast', (_: unknown, e: { text: string }) => { w.toasts.push(e.text); return { value: undefined } })
  on('clock.sleep', () => new Promise(() => {}))
  on('clock.now', () => ({ value: Date.UTC(2026, 9, 4, 12, 0, 0) }))
  on('http.fetch', (_: unknown, e: { url: string }) => {
    const state = e.url.includes('8931') ? (o.api ?? 'up') : (o.web ?? 'up')
    if (state === 'down') throw new Error('refused')
    return { value: { status: 200, ok: true, headers: {}, text: '' } }
  })
  on('fs.list', () => ({ value: (o.specs ?? ['home_and_answer.json']).map(name => ({ name, kind: 'file' })) }))
  on('ui.render', ($: any, e: any) => { // nothing beneath the mod draws, so a quiet band falls through to this marker
    const { Text } = $.ui.resolve(e)
    return <Text>quiet</Text>
  })
  on('process.run', (_: unknown, e: { argv: string[]; init?: { cwd?: string; timeoutMs?: number } }) => {
    if (o.throws) throw new Error(o.throws)
    w.runs.push([...e.argv])
    w.cwds.push(e.init?.cwd)
    w.timeouts.push(e.init?.timeoutMs)
    return { value: { exitCode: o.exitCode ?? 1, stdout: o.stdout ?? '', stderr: o.stderr ?? '', isStdoutTruncated: false, isStderrTruncated: false } }
  })
  return w
}

async function turnWith($: any, edits: Array<Record<string, unknown>>, extra: Record<string, unknown> = {}) {
  await $.turn.start({ text: 'go', turnId: 't1' })
  for (const e of edits) await $.tool.call(e)
  await $.turn.complete(complete(extra))
}

const edit = (file: string, extra: Record<string, unknown> = {}) => ({ tool: 'Edit', file_path: file, old_string: 'a', new_string: 'b', ...extra })

async function band($: any) {
  return $.ui.mount({ plugin: 'mod-route-capture', surface: 'terminal', component: 'AbovePrompt', props: { hasSurvey: false } })
}

const SCRIPT_OUT = [
  'target: web=http://127.0.0.1:5273 api=http://127.0.0.1:8931 app_env=local',
  '- PASS | home at 1280 | screen reached | 2 s | shot.png',
  '- PASS | home at 1280 | horizontal overflow | 0 px | results.json',
  '- FAIL | home at 390 | horizontal overflow | 59 px | results.json',
  '- PASS | home at 390 | console errors | 0 | results.json',
  '- FAIL | answer at 1280 | accessibility, serious or critical | 1: color-contrast | results.json',
  'scripted checks: 3 pass, 2 fail',
].join('\n')

test('a frontend edit shows the band with the screen count', async ($, on) => {
  on('tool.call', ok)
  fake(on)
  await turnWith($, [edit(`${FRONT}/components/screens/HomeScreen.tsx`)])
  const b = await band($)
  expect(await b.find({ type: 'Text', text: /Frontend changed: \/capture to screenshot 1 screen/ })).toBeDefined()
})

test('a shared component counts both screens', async ($, on) => {
  on('tool.call', ok)
  fake(on)
  await turnWith($, [edit(`${FRONT}/components/shell/AppShell.tsx`), edit(`${FRONT}/index.css`)])
  const b = await band($)
  expect(await b.find({ type: 'Text', text: /screenshot 2 screens/ })).toBeDefined()
})

test('an edit outside the frontend source or to a test shows no band', async ($, on) => {
  on('tool.call', ok)
  fake(on)
  await turnWith($, [edit('/repo/backend/app.py'), edit(`${FRONT}/App.test.tsx`), edit(`${FRONT}/components/screens/HomeScreen.tsx`.replace('.tsx', '.test.tsx'))])
  const b = await band($)
  expect(await b.find({ type: 'Text', text: /Frontend changed/ })).toBeUndefined()
})

test('a screen that needs a spec is not counted', async ($, on) => {
  on('tool.call', ok)
  fake(on)
  await turnWith($, [edit(`${FRONT}/components/screens/AboutScreen.tsx`)])
  const b = await band($)
  expect(await b.find({ type: 'Text', text: /Frontend changed/ })).toBeUndefined()
})

test('a denied edit is not recorded', async ($, on) => {
  on('tool.call', () => ({ deny: 'no' }))
  fake(on)
  await turnWith($, [edit(`${FRONT}/components/screens/HomeScreen.tsx`)])
  const b = await band($)
  expect(await b.find({ type: 'Text', text: /Frontend changed/ })).toBeUndefined()
})

test('a subagent edit and a subagent turn are ignored', async ($, on) => {
  on('tool.call', ok)
  fake(on)
  await turnWith($, [edit(`${FRONT}/components/screens/HomeScreen.tsx`, { agentId: 'sub1' })])
  expect(await (await band($)).find({ type: 'Text', text: /Frontend changed/ })).toBeUndefined()

  await $.turn.start({ text: 'go', turnId: 't2' })
  await $.tool.call(edit(`${FRONT}/components/screens/HomeScreen.tsx`))
  await $.turn.complete(complete({ agentId: 'sub1', turnId: 't2' }))
  expect(await (await band($)).find({ type: 'Text', text: /Frontend changed/ })).toBeUndefined()
})

test('Dismiss hides the band', async ($, on) => {
  on('tool.call', ok)
  fake(on)
  await turnWith($, [edit(`${FRONT}/components/screens/HomeScreen.tsx`)])
  const b = await band($)
  await b.press({ key: 'dismiss' })
  expect(await (await band($)).find({ type: 'Text', text: /Frontend changed/ })).toBeUndefined()
})

test('/capture with the dev server down toasts and runs nothing', async ($, on) => {
  on('tool.call', ok)
  const w = fake(on, { web: 'down' })
  await turnWith($, [edit(`${FRONT}/components/screens/HomeScreen.tsx`)])
  const r = await $.command.run({ command: 'capture', args: '' })
  expect(r.text).toContain('not reachable')
  expect(w.toasts.join(' ')).toContain('dev server is not reachable')
  expect(w.runs).toEqual([])
})

test('/capture with nothing changed says so and runs nothing', async ($, on) => {
  const w = fake(on)
  const r = await $.command.run({ command: 'capture', args: '' })
  expect(r.text).toContain('No changed frontend screens')
  expect(w.runs).toEqual([])
})

test('/capture runs the script for the changed screens and the pane shows pass and fail', async ($, on) => {
  on('tool.call', ok)
  const w = fake(on, { stdout: SCRIPT_OUT, exitCode: 1 })
  await turnWith($, [edit(`${FRONT}/components/shell/AppShell.tsx`)])
  const r = await $.command.run({ command: 'capture', args: '' })
  expect(r.text).toContain('3 pass, 2 fail')
  expect(w.runs[0]).toEqual(['node', '../.claude/skills/verify/scripts/capture.mjs', '--target', 'local', '--topic', 'mod_capture', '--screen', 'home=/', '--screen', 'answer=/', '--out', '/repo/logs/capture/2026-10-04T12-00-00-000Z-1'])
  expect(w.cwds[0]).toBe('/repo/frontend')
  expect(w.timeouts[0]).toBe(300_000)
  const pane = await $.ui.mount({ plugin: 'mod-route-capture', surface: 'terminal', component: 'Pane', props: { title: 'Capture', isFocused: true }, requestId: 'route-capture', viewport: { columns: 100, rows: 40 } })
  expect(await pane.find({ type: 'Text', text: /home: FAIL/ })).toBeDefined()
  expect(await pane.find({ type: 'Text', text: /answer: FAIL/ })).toBeDefined()
  expect(await pane.find({ type: 'Text', text: /PASS at 1280: horizontal overflow, 0 px/ })).toBeDefined()
  expect(await pane.find({ type: 'Text', text: /FAIL at 390: horizontal overflow, 59 px/ })).toBeDefined()
  expect(await pane.find({ type: 'Text', text: /PASS at 390: console errors, 0/ })).toBeDefined()
  expect(await pane.find({ type: 'Text', text: /FAIL at 1280: accessibility, serious or critical, 1: color-contrast/ })).toBeDefined()
})

test('/capture all runs every spec file', async ($, on) => {
  const w = fake(on, { stdout: SCRIPT_OUT, specs: ['home_and_answer.json', 'notes.txt', 'second.json'] })
  const r = await $.command.run({ command: 'capture', args: 'all' })
  expect(r.text).toContain('Captured')
  expect(w.runs.length).toBe(2)
  expect(w.runs[0]).toContain('--spec')
  expect(w.runs[0]).toContain('../.claude/skills/verify/specs/home_and_answer.json')
  expect(w.runs[1]).toContain('../.claude/skills/verify/specs/second.json')
})

test('a refused run reports the refusal and opens no results', async ($, on) => {
  fake(on, { exitCode: 2, stderr: 'verify capture: target unreachable\n' })
  const r = await $.command.run({ command: 'capture', args: 'all' })
  expect(r.text).toContain('target unreachable')
})

test('a script that fails to run is reported, not thrown', async ($, on) => {
  fake(on, { throws: 'timed out' })
  const r = await $.command.run({ command: 'capture', args: 'all' })
  expect(r.text).toContain('did not finish')
})
