import { test, expect } from 'claude-code/testing'
import { diffLines, prefixOf } from '../hooks/diff.ts'

function unified(a: string, b: string): string[] {
  return diffLines(a, b).lines.map(l => prefixOf(l) + l.text)
}

test('diff gives the expected plus and minus lines', () => {
  expect(unified('a\nb\nc', 'a\nB\nc')).toEqual([' a', '-b', '+B', ' c'])
  expect(unified('', 'x\ny')).toEqual(['+x', '+y'])
  expect(unified('same', 'same')).toEqual([])
})

test('a very large input falls back to a summary', () => {
  const a = Array.from({ length: 1000 }, (_, i) => `a${i}`).join('\n')
  const b = Array.from({ length: 1000 }, (_, i) => `b${i}`).join('\n')
  expect(unified(a, b)).toEqual(['file replaced: 1000 lines removed, 1000 added'])
})

const ok = () => ({ result: 'ran' }) as never

function base(on: any) {
  on('turn.start', (_: unknown, e: any) => ({ turnId: e.turnId }))
  on('turn.complete', () => ({ text: '' }))
  on('ui.open', () => ({ value: { isPlaced: true } }) as never)
}

function complete(extra: Record<string, unknown> = {}) {
  return { answer: '', durationMs: 1, isAborted: false, turnId: 't1', reason: 'answer', ...extra }
}

async function lastTurn($: any, on: any, run: () => Promise<unknown>) {
  base(on)
  await $.turn.start({ text: 'go', turnId: 't1' })
  await run()
  await $.turn.complete(complete())
}

async function drawPane($: any) {
  return $.ui.mount({ plugin: 'mod-replay-theater', surface: 'terminal', component: 'Pane', props: { title: 'Replay', isFocused: true }, requestId: 'replay-theater', viewport: { columns: 100, rows: 40 } })
}

test('an Edit is recorded and replayed', async ($, on) => {
  on('tool.call', ok)
  await lastTurn($, on, () => $.tool.call({ tool: 'Edit', file_path: 'a.txt', old_string: 'one', new_string: 'two' }))
  const r = await $.command.run({ command: 'replay', args: '' })
  expect(r.text).toBe('Replaying 1 edits')
  const pane = await drawPane($)
  expect(await pane.find({ type: 'Text', text: '-one' })).toBeDefined()
  expect(await pane.find({ type: 'Text', text: '+two' })).toBeDefined()
})

test('a Write over an existing file diffs against the old contents', async ($, on) => {
  on('tool.call', ok)
  on('fs.read', () => ({ value: 'keep\nold\n' }))
  await lastTurn($, on, () => $.tool.call({ tool: 'Write', file_path: 'b.txt', content: 'keep\nnew\n' }))
  await $.command.run({ command: 'replay', args: '' })
  const pane = await drawPane($)
  expect(await pane.find({ type: 'Text', text: '-old' })).toBeDefined()
  expect(await pane.find({ type: 'Text', text: '+new' })).toBeDefined()
  expect(await pane.find({ type: 'Text', text: ' keep' })).toBeDefined()
})

test('a Write of a new file shows everything added', async ($, on) => {
  on('tool.call', ok)
  on('fs.read', () => { throw new Error('ENOENT') })
  await lastTurn($, on, () => $.tool.call({ tool: 'Write', file_path: 'c.txt', content: 'x\ny\n' }))
  await $.command.run({ command: 'replay', args: '' })
  const pane = await drawPane($)
  expect(await pane.find({ type: 'Text', text: '+x' })).toBeDefined()
  expect(await pane.find({ type: 'Text', text: '+y' })).toBeDefined()
  expect(await pane.find({ type: 'Text', text: /^-/ })).toBeUndefined()
})

test('a denied edit is not recorded', async ($, on) => {
  on('tool.call', () => ({ deny: 'no' }))
  await lastTurn($, on, () => $.tool.call({ tool: 'Edit', file_path: 'a.txt', old_string: 'one', new_string: 'two' }))
  const r = await $.command.run({ command: 'replay', args: '' })
  expect(r.text).toContain('No edits')
})

test('a subagent edit is not recorded', async ($, on) => {
  on('tool.call', ok)
  await lastTurn($, on, () => $.tool.call({ tool: 'Edit', file_path: 'a.txt', old_string: 'one', new_string: 'two', agentId: 'sub1' }))
  const r = await $.command.run({ command: 'replay', args: '' })
  expect(r.text).toContain('No edits')
})

test('turn.complete from a subagent does not promote', async ($, on) => {
  on('tool.call', ok)
  base(on)
  await $.turn.start({ text: 'go', turnId: 't1' })
  await $.tool.call({ tool: 'Edit', file_path: 'a.txt', old_string: 'one', new_string: 'two' })
  await $.turn.complete(complete({ agentId: 'sub1' }))
  const r = await $.command.run({ command: 'replay', args: '' })
  expect(r.text).toContain('No edits')
})

test('replay with no edits says so', async ($, on) => {
  const r = await $.command.run({ command: 'replay', args: '' })
  expect(r.text).toBe('No edits in the last turn')
})

test('Next and Prev move between steps', async ($, on) => {
  on('tool.call', ok)
  await lastTurn($, on, async () => {
    await $.tool.call({ tool: 'Edit', file_path: 'a.txt', old_string: 'one', new_string: 'two' })
    await $.tool.call({ tool: 'Edit', file_path: 'b.txt', old_string: 'red', new_string: 'blue' })
  })
  await $.command.run({ command: 'replay', args: '' })
  const pane = await drawPane($)
  expect(await pane.find({ type: 'Text', text: /Step 1 of 2: a.txt/ })).toBeDefined()
  await pane.press({ key: 'next' })
  expect(await pane.find({ type: 'Text', text: /Step 2 of 2: b.txt/ })).toBeDefined()
  await pane.press({ key: 'prev' })
  expect(await pane.find({ type: 'Text', text: /Step 1 of 2: a.txt/ })).toBeDefined()
})

test('the hint band counts edits and files', async ($, on) => {
  on('tool.call', ok)
  await lastTurn($, on, async () => {
    await $.tool.call({ tool: 'Edit', file_path: 'a.txt', old_string: 'one', new_string: 'two' })
    await $.tool.call({ tool: 'Edit', file_path: 'a.txt', old_string: 'x', new_string: 'y' })
  })
  const band = await $.ui.mount({ plugin: 'mod-replay-theater', surface: 'terminal', component: 'AbovePrompt', props: { hasSurvey: false } })
  expect(await band.find({ type: 'Text', text: /Replay: 2 edits in 1 files/ })).toBeDefined()
})
