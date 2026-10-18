import { test, expect } from 'claude-code/testing'

const CARDS = [
  '# UI fix plan',
  '',
  '## To do',
  '',
  '| # | Feature, in plain words | Item | Waiting on |',
  '|---|---|---|---|',
  "| 84 | R-10's guardrail fixes on their own, built and then stopped for a design that is agreed first | Built | Nobody |",
  '| 2 | Every answer opens with a code-built line | notes | go |',
  '',
  '### Set 11, still open',
  '',
  'Phase 8.7 carries cards 2 and 50 together.',
].join('\n')

const BOARD = [
  '# Build board',
  '',
  '## Build phases',
  '',
  '| Phase | Branch | Delivers | Depends on | Group | Status |',
  '|---|---|---|---|---|---|',
  '| 6.2 | `phase/6.2-answer-readability-ui-pass` | The complete contents of UI_feedback.md, as one pass rather than in patches | 2.1 | v1 | in-progress |',
  '| 3.5 | `phase/3.5-x` | A tool phase | 3.4 | v1 | done |',
].join('\n')

const MEETING_BODY = ['# 2026-08-10 Phase 6, Step 6.2', '', '## Attendees', '', 'Dana Roe said the secret plan is to ship on Friday.', '', '## What we covered', '', '### Branch rename'].join('\n')

type World = { statuses: Array<string | undefined> }

function fake(on: any, o: { files?: Record<string, string>; meetings?: string[]; existsThrows?: boolean; noFiles?: boolean } = {}): World {
  const w: World = { statuses: [] }
  const files: Record<string, string> = {
    '/repo/testing/UI_fix_plan.md': CARDS,
    '/repo/tracker/BOARD.md': BOARD,
    '/repo/requirements/meetings/2026-08-10_Phase_6_step_6.2.md': MEETING_BODY,
    '/repo/requirements/meetings/2026-07-25_Phase_4_steps_4.0-4.4.md': '# Other\n\nbody',
    ...(o.files ?? {}),
  }
  on('session.repo', () => ({ value: { root: '/repo', remote: null, internal: false } }))
  on('fs.exists', (_: unknown, e: { path: string }) => {
    if (o.existsThrows) throw new Error('boom')
    return { value: !o.noFiles && e.path in files }
  })
  on('fs.read', (_: unknown, e: { path: string }) => {
    if (!(e.path in files)) throw new Error('ENOENT')
    return { value: files[e.path] }
  })
  on('fs.list', () => ({ value: (o.meetings ?? ['2026-08-10_Phase_6_step_6.2.md', '2026-07-25_Phase_4_steps_4.0-4.4.md']).map(name => ({ name, kind: 'file' })) }))
  on('ui.status', (_: unknown, e: { text?: string }) => { w.statuses.push(e.text); return { value: undefined } })
  on('prompt.submit', (_: unknown, e: { text: string }) => ({ text: e.text }))
  return w
}

test('a card reference shows its title trimmed to 50 characters', async ($, on) => {
  const w = fake(on)
  await $.prompt.submit({ text: 'please look at card 84 before editing' })
  expect(w.statuses.length).toBe(1)
  expect(w.statuses[0]).toBe("trace: card 84 R-10's guardrail fixes on their own, built and the")
  expect((w.statuses[0] as string).slice('trace: card 84 '.length).length).toBe(50)
})

test('a phase step with the word phase shows its board title', async ($, on) => {
  const w = fake(on)
  await $.prompt.submit({ text: 'what did phase 6.2 deliver?' })
  expect(w.statuses[0]).toBe('trace: phase 6.2 The complete contents of UI_feedback.md, as one pa')
})

test('a bare step number on the board is found', async ($, on) => {
  const w = fake(on)
  await $.prompt.submit({ text: 'is 6.2 still in progress' })
  expect(w.statuses[0]).toContain('trace: phase 6.2 ')
})

test('a measurement that looks like a phase is left alone', async ($, on) => {
  const w = fake(on)
  await $.prompt.submit({ text: 'the run took 3.5 seconds' })
  expect(w.statuses).toEqual([])
})

test('a phase past the frozen board points at the cards file', async ($, on) => {
  const w = fake(on)
  await $.prompt.submit({ text: 'status of phase 8.7?' })
  expect(w.statuses[0]).toBe('trace: phase 8.7 is past the frozen board, see testing/UI_fix_plan.md')
})

test('no reference leaves the status alone and passes the prompt through untouched', async ($, on) => {
  const w = fake(on)
  const r = await $.prompt.submit({ text: 'rename the helper function' })
  expect(w.statuses).toEqual([])
  expect(r.text).toBe('rename the helper function')
  expect((r as { context?: unknown }).context).toBeUndefined()
})

test('a reference passes the prompt through untouched too', async ($, on) => {
  fake(on)
  const r = await $.prompt.submit({ text: 'card 84 please' })
  expect(r.text).toBe('card 84 please')
  expect((r as { context?: unknown }).context).toBeUndefined()
})

test('an unknown card leaves the status alone', async ($, on) => {
  const w = fake(on)
  await $.prompt.submit({ text: 'look at card 999' })
  expect(w.statuses).toEqual([])
})

test('missing source files leave the status alone', async ($, on) => {
  const w = fake(on, { noFiles: true })
  await $.prompt.submit({ text: 'card 84' })
  expect(w.statuses).toEqual([])
})

test('a file system that throws never breaks the prompt', async ($, on) => {
  const w = fake(on, { existsThrows: true })
  const r = await $.prompt.submit({ text: 'card 84' })
  expect(r.text).toBe('card 84')
  expect(w.statuses).toEqual([])
})

test('/trace with no reference says so', async ($, on) => {
  fake(on)
  const r = await $.command.run({ command: 'trace', args: '' })
  expect(r.text).toContain('No reference yet')
})

test('/trace for a card lists the path and headings, never the row text', async ($, on) => {
  fake(on)
  await $.prompt.submit({ text: 'card 84' })
  const r = await $.command.run({ command: 'trace', args: '' })
  expect(r.text).toContain('testing/UI_fix_plan.md')
  expect(r.text).toContain('section: ## To do')
  expect(r.text).toContain('  ### Set 11, still open')
  expect(r.text).not.toContain('Nobody')
  expect(r.text).not.toContain('guardrail')
})

test('/trace for a phase lists meeting paths and headings with no meeting body text', async ($, on) => {
  fake(on)
  await $.prompt.submit({ text: 'phase 6.2' })
  const r = await $.command.run({ command: 'trace', args: '' })
  expect(r.text).toContain('requirements/meetings/2026-08-10_Phase_6_step_6.2.md')
  expect(r.text).toContain('## Attendees')
  expect(r.text).toContain('### Branch rename')
  expect(r.text).not.toContain('Dana Roe')
  expect(r.text).not.toContain('secret plan')
  expect(r.text).not.toContain('2026-07-25_Phase_4')
  expect(r.text).toContain('tracker/BOARD.md')
})

test('/trace with an argument overrides the current reference and matches step ranges', async ($, on) => {
  fake(on)
  const r = await $.command.run({ command: 'trace', args: 'phase 4.2' })
  expect(r.text).toContain('Reference: phase 4.2')
  expect(r.text).toContain('2026-07-25_Phase_4_steps_4.0-4.4.md')
})

test('/trace with an argument it cannot read asks for a form', async ($, on) => {
  fake(on)
  const r = await $.command.run({ command: 'trace', args: 'banana' })
  expect(r.text).toContain('Give a card or phase')
})
