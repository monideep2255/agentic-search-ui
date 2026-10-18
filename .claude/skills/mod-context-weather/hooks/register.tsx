import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { Reading } from '../types/index.d.ts'
import { config } from './config.ts'
import { MAX_READINGS, cacheState, forecast, formatDelta, formatTokens, sparkline } from './weather.ts'

const readings = atom({ plugin: 'mod-context-weather', key: 'readings' } as const, [] as Reading[])
const lastDelta = atom({ plugin: 'mod-context-weather', key: 'lastDelta' } as const, null as number | null)
const lastTurnAt = atom({ plugin: 'mod-context-weather', key: 'lastTurnAt' } as const, null as number | null)
const nudged = atom({ plugin: 'mod-context-weather', key: 'nudged' } as const, false)

// Take one reading of the context window; stays quiet when there is none yet.
async function record($: EngineInterface) {
  try {
    const { context } = await $.session.usage()
    if (context.tokens === undefined || context.percent === undefined) return
    const reading: Reading = { percent: context.percent, tokens: context.tokens, window: context.window }
    const before = await read($, readings)
    const previous = before.length > 0 ? before[before.length - 1] : undefined
    await update($, readings, list => [...list, reading].slice(-MAX_READINGS))
    if (previous) await update($, lastDelta, () => reading.tokens - previous.tokens)
  } catch {
    // An observer that cannot read usage stays silent.
  }
}

// The nudge body: fires once per idle period, only while warm and above the threshold.
async function nudge($: EngineInterface) {
  const list = await read($, readings)
  const latest = list.length > 0 ? list[list.length - 1] : undefined
  const at = await read($, lastTurnAt)
  const now = await $.clock.now()
  const cache = cacheState(at, now, config.cacheTtlMinutes)
  if (await read($, nudged)) return
  if (!latest || latest.tokens <= config.nudgeAboveTokens || !cache.warm) return
  await update($, nudged, () => true)
  $.ui.toast('Stepping away? /precompact now while the cache is warm.')
}

// Runs the compaction and reports the counts; falls back to telling the person to run /compact.
async function compactNow($: EngineInterface, beforeTokens: number | undefined) {
  const fmt = (n: number | undefined) => (n === undefined ? 'unknown' : formatTokens(n))
  try {
    const outcome = await $.session.compact({})
    if (outcome.skip !== undefined) {
      $.ui.toast(`precompact: compaction was skipped (${outcome.skip}). Run /compact now if you still want it.`)
      return
    }
    $.ui.toast(`precompact: context before ${fmt(outcome.tokensBefore ?? beforeTokens)} tokens, after ${fmt(outcome.tokensAfter)} tokens.`)
  } catch {
    $.ui.toast('precompact: compaction is not available here. Run /compact now.')
  }
}

export const register: Register = on => {
  let timer: { cancel: () => void } | null = null

  const cancelTimer = () => {
    if (timer) timer.cancel()
    timer = null
  }

  on('session.start', async ($, e, next) => {
    const result = await next(e)
    await $.command.register({
      name: 'precompact',
      description: 'Compact the conversation now, while the cache is warm',
    })
    await record($)
    return result
  })

  on('turn.complete', async ($, e, next) => {
    const result = await next(e)
    if (e.agentId) return result
    await record($)
    const now = await $.clock.now()
    await update($, lastTurnAt, () => now)
    await update($, nudged, () => false)
    cancelTimer()
    timer = $.clock.after(config.idleNudgeMinutes * 60_000, () => {
      void nudge($)
    })
    return result
  })

  on('prompt.submit', async ($, e, next) => {
    cancelTimer()
    return next(e)
  })

  on('command.run', { command: 'precompact' }, async ($, e, next) => {
    const before = (await $.session.usage()).context.tokens
    // The engine refuses a compaction started inside this hook, so it runs on a timer, after the command returns.
    $.clock.after(0, () => {
      void compactNow($, before)
    })
    return { text: `precompact: compacting now from ${before === undefined ? 'unknown' : formatTokens(before)} tokens. The after count follows in a notice. If nothing follows, run /compact.` }
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const list = await read($, readings)
    const latest = list.length > 0 ? list[list.length - 1] : undefined
    if (e.props.hasSurvey || !latest) return next(e)

    const delta = await read($, lastDelta)
    const at = await read($, lastTurnAt)
    const now = await $.clock.now()
    const cache = cacheState(at, now, config.cacheTtlMinutes)
    const columns = e.props.bodyColumns
    const isNarrow = columns < 80
    const isTiny = columns < 60

    const parts: string[] = [`${forecast(latest.percent)} ${latest.percent}%`]
    if (!isTiny) parts.push(`${formatTokens(latest.tokens)} / ${formatTokens(latest.window)}`)
    if (!isNarrow) parts.push(sparkline(list.map(r => r.percent)))
    if (delta !== null && !isTiny) parts.push(formatDelta(delta))
    parts.push(cache.warm ? `cache warm, ${cache.minutesLeft}m left (estimated)` : 'cache cold (estimated)')

    const { Box, Text } = $.ui.resolve(e)
    return (
      <Box>
        <Text dimColor wrap="truncate">{parts.join('  ')}</Text>
      </Box>
    )
  })
}
