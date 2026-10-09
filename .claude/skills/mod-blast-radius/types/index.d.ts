// State contract for mod-blast-radius: the dry-run reports waiting on the
// person's answer, drawn in the pane, or in the band when the pane cannot be
// seated.

export type BlastReport = {
  id: string
  command: string
  lines: string[]
  isBand: boolean
}

declare module 'claude-code' {
  interface PluginState {
    'mod-blast-radius': { pending: BlastReport[] }
  }
}
