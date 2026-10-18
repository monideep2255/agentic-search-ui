import { test, expect, mock } from 'claude-code/testing'

import { forecast, sparkline } from '../hooks/weather.ts'
import { config } from '../hooks/config.ts'

// Timings follow this repository's config, so the same test passes in every repository.
const NUDGE = config.idleNudgeMinutes * 60_000

const PLUGIN = 'mod-context-weather'
const SURFACES = ['terminal', 'desktop'] as const

const usageOf = (tokens: number | undefined, window = 200000) => ({
  value: {
    startedAt: 0,
    context: tokens === undefined ? { window } : { tokens, window, percent: Math.floor((tokens / window) * 100) },
    rateLimits: [],
  },
})

const ENGINE_BAND = { type: 'Text', props: {}, children: ['engine band'] } as never

const PROPS = {
  hasSurvey: false,
  isWorking: false,
  maxRows: 10,
  bodyColumns: 120,
  scroll: {},
  view: {},
} as never

const complete = (agentId?: string) =>
  ({ answer: '', durationMs: 1, isAborted: false, turnId: 't', reason: 'answer', agentId }) as never

const submit = () => ({ text: 'hi', wait: false, origin: { kind: 'composer' } }) as never

test('the five forecast levels by percent', () => {
  expect(forecast(0)).toBe('Clear')
  expect(forecast(24)).toBe('Clear')
  expect(forecast(25)).toBe('Cloudy')
  expect(forecast(49)).toBe('Cloudy')
  expect(forecast(50)).toBe('Showers')
  expect(forecast(74)).toBe('Showers')
  expect(forecast(75)).toBe('Storm')
  expect(forecast(89)).toBe('Storm')
  expect(forecast(90)).toBe('Compact soon')
  expect(forecast(100)).toBe('Compact soon')
})

test('the sparkline maps percent to the eight block characters', () => {
  expect(sparkline([0, 100])).toBe('▁█')
})

for (const surface of SURFACES) {
  test(`the band draws on ${surface} with the percent`, async ($, on) => {
    mock.clock(on)
    on('session.usage', () => usageOf(134400))
    on('command.register', () => ({ value: {} }) as never)
    on('session.start', () => ({ cwd: '.' }))
    on('ui.render', () => ENGINE_BAND)
    await $.session.start({ cwd: '.', surface: null, isInteractive: true } as never)
    const band = await $.ui.mount({ plugin: PLUGIN, surface, component: 'AbovePrompt', props: PROPS })
    const found = await band.find({ type: 'Text', text: '67%' })
    expect(found).toBeDefined()
  })
}

test('a session with no usage yet draws nothing', async ($, on) => {
  mock.clock(on)
  on('session.usage', () => usageOf(undefined))
  on('command.register', () => ({ value: {} }) as never)
  on('session.start', () => ({ cwd: '.' }))
  on('ui.render', () => ENGINE_BAND)
  await $.session.start({ cwd: '.', surface: null, isInteractive: true } as never)
  const band = await $.ui.mount({ plugin: PLUGIN, surface: 'terminal', component: 'AbovePrompt', props: PROPS })
  expect(await band.find({ type: 'Text', text: 'engine band' })).toBeDefined()
  expect(await band.find({ type: 'Text', text: '%' })).toBeUndefined()
})

test('a subagent turn adds no reading, and 12 readings are kept', async ($, on) => {
  mock.clock(on)
  let tokens = 10000
  on('session.usage', () => usageOf(tokens))
  on('turn.complete', () => ({ text: '' }))
  on('ui.render', () => ENGINE_BAND)
  await $.turn.complete(complete('agent-1'))
  let band = await $.ui.mount({ plugin: PLUGIN, surface: 'terminal', component: 'AbovePrompt', props: PROPS })
  expect(await band.find({ type: 'Text', text: '5%' })).toBeUndefined()
  for (let i = 0; i < 15; i++) {
    tokens = 10000 + i * 10000
    await $.turn.complete(complete())
  }
  band = await $.ui.mount({ plugin: PLUGIN, surface: 'terminal', component: 'AbovePrompt', props: PROPS })
  const text = await band.find({ type: 'Text', text: /[▁-█]{12}/ })
  expect(text).toBeDefined()
  expect(await band.find({ type: 'Text', text: /[▁-█]{13}/ })).toBeUndefined()
})

test('the idle nudge fires once when warm and above the threshold', async ($, on) => {
  const clock = mock.clock(on)
  const toasts: string[] = []
  on('session.usage', () => usageOf(100000))
  on('turn.complete', () => ({ text: '' }))
  on('ui.toast', e => { toasts.push(String((e as { text?: string }).text ?? JSON.stringify(e))); return { value: undefined } as never })
  await $.turn.complete(complete())
  await clock.advance(NUDGE + 1000)
  expect(toasts.length).toBe(1)
  await clock.advance(NUDGE)
  expect(toasts.length).toBe(1)
})

test('the idle nudge stays quiet below the threshold', async ($, on) => {
  const clock = mock.clock(on)
  const toasts: string[] = []
  on('session.usage', () => usageOf(20000))
  on('turn.complete', () => ({ text: '' }))
  on('ui.toast', () => { toasts.push('t'); return { value: undefined } as never })
  await $.turn.complete(complete())
  await clock.advance(NUDGE * 2)
  expect(toasts.length).toBe(0)
})

test('prompt.submit resets the idle nudge', async ($, on) => {
  const clock = mock.clock(on)
  const toasts: string[] = []
  on('session.usage', () => usageOf(100000))
  on('turn.complete', () => ({ text: '' }))
  on('prompt.submit', () => ({ text: 'hi' }))
  on('ui.toast', () => { toasts.push('t'); return { value: undefined } as never })
  await $.turn.complete(complete())
  await clock.advance(NUDGE / 2)
  await $.prompt.submit(submit())
  await clock.advance(NUDGE * 2)
  expect(toasts.length).toBe(0)
})

test('/precompact returns text, then reports the before and after counts', async ($, on) => {
  const clock = mock.clock(on)
  const toasts: string[] = []
  on('session.usage', () => usageOf(100000))
  on('session.compact', () => ({ messages: [{ role: 'user', text: 'summary', toolUses: [] }], tokensBefore: 100000, tokensAfter: 8000 }))
  on('ui.toast', (_$, e) => { toasts.push(JSON.stringify(e)); return { value: undefined } as never })
  const r = await $.command.run({ command: 'precompact', args: '', origin: { kind: 'composer' }, presentation: { isFullscreen: false, columns: 80 } } as never)
  expect(r.text).toContain('100k')
  await clock.advance(10)
  expect(toasts.length).toBe(1)
  expect(toasts[0]).toContain('8k')
})
