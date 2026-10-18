export type CaptureRow = {
  screen: string
  width: string
  check: string
  result: 'PASS' | 'FAIL'
  value: string
}

declare module 'claude-code' {
  interface PluginState {
    'mod-route-capture': {
      /** Files edited under the frontend source folder during the current turn, relative to it. */
      pending: string[]
      /** Capturable screens changed by the last turn with frontend edits. */
      screens: string[]
      /** Changed screens the capture script cannot reach by address alone. */
      skipped: string[]
      isBandShown: boolean
      rows: CaptureRow[]
      /** One line about the last run, shown at the top of the pane. */
      note: string
    }
  }
}
