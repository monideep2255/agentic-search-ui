// Pure helpers for mod-context-weather. Nothing here touches `$`.

export const SPARK = '▁▂▃▄▅▆▇█'
export const MAX_READINGS = 12

export type Forecast = 'Clear' | 'Cloudy' | 'Showers' | 'Storm' | 'Compact soon'

export function forecast(percent: number): Forecast {
  if (percent < 25) return 'Clear'
  if (percent < 50) return 'Cloudy'
  if (percent < 75) return 'Showers'
  if (percent < 90) return 'Storm'
  return 'Compact soon'
}

export function sparkline(percents: readonly number[]): string {
  return percents
    .slice(-MAX_READINGS)
    .map(p => {
      const clamped = Math.max(0, Math.min(100, p))
      const index = Math.min(SPARK.length - 1, Math.floor((clamped / 100) * SPARK.length))
      return SPARK[index]
    })
    .join('')
}

export function formatTokens(n: number): string {
  if (Math.abs(n) >= 1_000_000) return `${trim(n / 1_000_000)}M`
  if (Math.abs(n) >= 1000) return `${trim(n / 1000)}k`
  return String(Math.round(n))
}

function trim(value: number): string {
  return value.toFixed(1).replace(/\.0$/, '')
}

export function formatDelta(delta: number): string {
  const sign = delta < 0 ? '-' : '+'
  return `${sign}${formatTokens(Math.abs(delta))} last turn`
}

export type CacheState = { warm: boolean; minutesLeft: number }

// Estimated from the time since the last main-turn completion. The engine
// exposes a warmth flag only on a model switch, so there is no live field.
export function cacheState(lastTurnAt: number | null, now: number, ttlMinutes: number): CacheState {
  if (lastTurnAt === null) return { warm: false, minutesLeft: 0 }
  const leftMs = lastTurnAt + ttlMinutes * 60_000 - now
  if (leftMs <= 0) return { warm: false, minutesLeft: 0 }
  return { warm: true, minutesLeft: Math.ceil(leftMs / 60_000) }
}
