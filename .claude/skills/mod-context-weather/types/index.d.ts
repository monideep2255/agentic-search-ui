export type Reading = { percent: number; tokens: number; window: number }

declare module 'claude-code' {
  interface PluginState {
    'mod-context-weather': {
      readings: Reading[]
      lastDelta: number | null
      lastTurnAt: number | null
      nudged: boolean
    }
  }
}
