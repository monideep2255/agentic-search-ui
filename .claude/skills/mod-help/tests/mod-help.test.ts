import { test, expect } from 'claude-code/testing'
import { config } from '../hooks/config.ts'

const PM = (n: string, d: string) => JSON.stringify({ name: n, description: d })
const dir = (name: string) => ({ name, kind: 'dir', size: 0, mtimeMs: 0, isLink: false })

function fake(on: any, files: Record<string, string>, folders: string[], store: Record<string, unknown> = {}) {
  on('command.register', () => ({ value: { command: 'mods' } }))
  on('command.list', () => ({ value: [] }))
  on('session.repo', () => ({ value: { root: '/repo', remote: null, internal: false } }))
  on('fs.list', () => ({ value: folders.map(dir) }))
  on('fs.exists', (_: unknown, e: { path: string }) => ({ value: e.path in files }))
  on('fs.read', (_: unknown, e: { path: string }) => ({ value: files[e.path] }))
  on('store.get', (_: unknown, e: { key: string }) => ({ value: store[e.key] }))
  on('store.set', (_: unknown, e: { key: string; value: unknown }) => { store[e.key] = e.value; return { value: undefined } })
  on('clock.now', () => ({ value: Date.parse('2026-10-04T12:00:00Z') }))
  on('session.start', () => ({ cwd: '/repo' }) as never)
}

const P = (f: string) => `/repo/.claude/skills/${f}/.claude-plugin/plugin.json`
const base = {
  [P('mod-a')]: PM('mod-a', 'Does A. Trigger: Auto'),
  [P('mod-x')]: PM('mod-x', 'Does X. Trigger: /x'),
}

test('/mods lists two mods with triggers', async ($, on) => {
  fake(on, base, ['mod-a', 'mod-x'])
  const r = await $.command.run({ command: 'mods', args: '' })
  expect(r.text).toContain('mod-a | Auto')
  expect(r.text).toContain('mod-x | /x')
  expect(r.text).toContain(config.guidePath)
})

test('/mods mod-x shows one', async ($, on) => {
  fake(on, base, ['mod-a', 'mod-x'])
  const r = await $.command.run({ command: 'mods', args: 'mod-x' })
  expect(r.text).toContain('Does X.')
  expect(r.text).not.toContain('Does A.')
})

test('a non-mod plugin folder raises the toast', async ($, on) => {
  const toasts: string[] = []
  on('ui.toast', (_: unknown, e: { text: string }) => { toasts.push(e.text); return { value: undefined } })
  fake(on, { ...base, [P('sneaky')]: PM('sneaky', 'Bad. Trigger: Auto') }, ['mod-a', 'sneaky'])
  await $.session.start({ cwd: '/repo', surface: null } as never)
  expect(toasts.some(t => t.includes('Unknown plugin auto-loaded from .claude/skills/sneaky'))).toBe(true)
})

test('a folder without plugin.json is ignored', async ($, on) => {
  const toasts: string[] = []
  on('ui.toast', (_: unknown, e: { text: string }) => { toasts.push(e.text); return { value: undefined } })
  fake(on, base, ['mod-a', 'notes'])
  await $.session.start({ cwd: '/repo', surface: null } as never)
  expect(toasts.some(t => t.includes('Unknown plugin'))).toBe(false)
  const r = await $.command.run({ command: 'mods', args: '' })
  expect(r.text).not.toContain('notes')
})

test('the daily toast fires once per date', async ($, on) => {
  const toasts: string[] = []
  on('ui.toast', (_: unknown, e: { text: string }) => { toasts.push(e.text); return { value: undefined } })
  fake(on, base, ['mod-a', 'mod-x'])
  await $.session.start({ cwd: '/repo', surface: null } as never)
  await $.session.start({ cwd: '/repo', surface: null } as never)
  expect(toasts.filter(t => t.includes('2 mods loaded'))).toHaveLength(1)
})

test('a malformed manifest is listed as unreadable', async ($, on) => {
  fake(on, { ...base, [P('mod-bad')]: '{not json' }, ['mod-a', 'mod-bad'])
  const r = await $.command.run({ command: 'mods', args: '' })
  expect(r.text).toContain('unreadable manifest')
  expect(r.text).toContain('mod-a')
})
