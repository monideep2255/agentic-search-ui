import { test, expect } from 'claude-code/testing'

type Answers = { fastTimeout?: boolean; api?: 'ok' | 'bad' | 'throw' | 'hang'; web?: 'ok' | 'throw'; db?: number | 'missing' }

function fake(on: any, a: Answers, statuses: Array<string | undefined>) {
  on('session.start', () => ({ cwd: '/repo' }) as never)
  on('clock.every', () => ({ value: { cancel: () => {} } }))
  on('clock.sleep', () => (a.fastTimeout ? { value: undefined } : new Promise(() => {})))
  on('http.fetch', (_: unknown, e: { url: string }) => {
    if (e.url.includes(':8000/health')) {
      if (a.api === 'throw') throw new Error('refused')
      if (a.api === 'hang') return new Promise(() => {})
      return { value: { status: a.api === 'ok' ? 200 : 503, ok: a.api === 'ok', headers: {}, text: '' } }
    }
    if (a.web === 'throw') throw new Error('refused')
    return { value: { status: 200, ok: true, headers: {}, text: '' } }
  })
  on('process.run', () => {
    if (a.db === 'missing') throw new Error('spawn pg_isready ENOENT')
    return { value: { exitCode: a.db ?? 2, stdout: '', stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
  })
  on('ui.status', (_: unknown, e: { text?: string }) => { statuses.push(e.text); return { value: undefined } })
}

test('all down and never up stays quiet', async ($, on) => {
  const s: Array<string | undefined> = []
  fake(on, { api: 'throw', web: 'throw', db: 2 }, s)
  await $.session.start({ cwd: '/repo', surface: null } as never)
  expect(s.filter(x => x !== undefined)).toEqual([])
})

test('api up shows the status line', async ($, on) => {
  const s: Array<string | undefined> = []
  fake(on, { api: 'ok', web: 'throw', db: 0 }, s)
  await $.session.start({ cwd: '/repo', surface: null } as never)
  expect(s).toContain('stack: api up, web down, db up')
})

test('a fetch that never answers counts as down', async ($, on) => {
  const s: Array<string | undefined> = []
  fake(on, { api: 'hang', web: 'ok', db: 'missing', fastTimeout: true }, s)
  await $.session.start({ cwd: '/repo', surface: null } as never)
  expect(s).toContain('stack: api down, web up, db unknown')
})

test('a missing pg_isready reads as db unknown', async ($, on) => {
  const s: Array<string | undefined> = []
  fake(on, { api: 'ok', web: 'ok', db: 'missing' }, s)
  await $.session.start({ cwd: '/repo', surface: null } as never)
  expect(s).toContain('stack: api up, web up, db unknown')
})

test('an unhealthy api status counts as down', async ($, on) => {
  const s: Array<string | undefined> = []
  fake(on, { api: 'bad', web: 'ok', db: 3 }, s)
  await $.session.start({ cwd: '/repo', surface: null } as never)
  expect(s).toContain('stack: api down, web up, db unknown')
})

test('once something was up, an all-down stack still shows', async ($, on) => {
  const s: Array<string | undefined> = []
  const a: Answers = { api: 'ok', web: 'ok', db: 0 }
  fake(on, a, s)
  await $.session.start({ cwd: '/repo', surface: null } as never)
  a.api = 'throw'; a.web = 'throw'; a.db = 2
  await $.session.start({ cwd: '/repo', surface: null } as never)
  expect(s[s.length - 1]).toBe('stack: api down, web down, db down')
})
