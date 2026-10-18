import { test, expect } from 'claude-code/testing'
import { config } from '../hooks/config.ts'

function breakdown(memory: [string, number][], skills = 0) {
  return {
    categories: [],
    memoryFiles: memory.map(([path, tokens]) => ({ path, type: 'Project', tokens })),
    mcpTools: [],
    agents: [],
    skills: skills ? { totalSkills: 1, includedSkills: 1, tokens: skills, skillFrontmatter: [] } : undefined,
  }
}

function fake(on: any, usage: unknown, store: Record<string, unknown> = {}, toasts: string[] = [], statuses: unknown[] = []) {
  on('command.register', () => ({ value: { command: 'context-budget' } }))
  on('session.usage', () => { if (usage === 'boom') throw new Error('boom'); return { value: usage } })
  on('store.get', (_: unknown, e: { key: string }) => ({ value: store[e.key] }))
  on('store.set', (_: unknown, e: { key: string; value: unknown }) => { store[e.key] = e.value; return { value: undefined } })
  on('ui.toast', (_: unknown, e: { text: string }) => { toasts.push(e.text); return { value: undefined } })
  on('ui.status', (_: unknown, e: { text?: string }) => { statuses.push(e.text); return { value: undefined } })
  on('session.start', () => ({ cwd: '/repo' }) as never)
}

const withBreakdown = (b: unknown) => ({ startedAt: 0, context: { window: 200000, breakdown: b } })
const start = ($: any) => $.session.start({ cwd: '/repo' } as never)

test('over budget toasts the three largest', async ($, on) => {
  const toasts: string[] = []
  const statuses: unknown[] = []
  const big = config.budgetTokens
  fake(on, withBreakdown(breakdown([['a.md', big], ['b.md', 500], ['c.md', 300], ['d.md', 10]])), {}, toasts, statuses)
  await start($)
  expect(toasts).toHaveLength(1)
  expect(toasts[0]).toContain('Largest: a.md')
  expect(toasts[0]).toContain('b.md')
  expect(toasts[0]).toContain('c.md')
  expect(toasts[0]).not.toContain('d.md')
  expect(statuses[0]).toContain('context:')
})

test('within budget is quiet but sets the status', async ($, on) => {
  const toasts: string[] = []
  const statuses: unknown[] = []
  fake(on, withBreakdown(breakdown([['a.md', 100]])), {}, toasts, statuses)
  await start($)
  expect(toasts).toHaveLength(0)
  expect(statuses[0]).toBe(`context: 100 / ${config.budgetTokens}`)
})

test('no breakdown stays silent', async ($, on) => {
  const toasts: string[] = []
  const statuses: unknown[] = []
  fake(on, { startedAt: 0, context: { window: 200000 } }, {}, toasts, statuses)
  await start($)
  expect(toasts).toHaveLength(0)
  expect(statuses).toHaveLength(0)
})

test('a failing usage call stays silent', async ($, on) => {
  const toasts: string[] = []
  fake(on, 'boom', {}, toasts)
  await start($)
  expect(toasts).toHaveLength(0)
})

test('growth over the alert percent adds the note', async ($, on) => {
  const toasts: string[] = []
  fake(on, withBreakdown(breakdown([['a.md', 1200]])), { lastTotal: 1000 }, toasts)
  await start($)
  expect(toasts.join(' ')).toContain('Grew 20% since last session')
})

test('small growth adds no note', async ($, on) => {
  const toasts: string[] = []
  fake(on, withBreakdown(breakdown([['a.md', 1050]])), { lastTotal: 1000 }, toasts)
  await start($)
  expect(toasts).toHaveLength(0)
})

test('/context-budget lists items largest first', async ($, on) => {
  fake(on, withBreakdown(breakdown([['small.md', 100], ['large.md', 900]], 400)))
  const r = await $.command.run({ command: 'context-budget', args: '' })
  const text = r.text as string
  expect(text.indexOf('large.md')).toBeLessThan(text.indexOf('Skills listing'))
  expect(text.indexOf('Skills listing')).toBeLessThan(text.indexOf('small.md'))
  expect(text).toContain('Total: 1400 tokens')
  expect(text).toContain(config.budgetSetOn)
  expect(text).toContain('Re-measure: run /context')
})
