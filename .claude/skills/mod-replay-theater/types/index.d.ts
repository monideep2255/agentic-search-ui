export type DiffLine = { kind: 'add' | 'del' | 'ctx' | 'note'; text: string }

export type ReplayStep = {
  tool: 'Edit' | 'Write'
  path: string
  /** Edit with replace_all, or a Write over an existing file. */
  label: string
  lines: DiffLine[]
  /** Diff lines cut off after the cap. */
  more: number
  added: number
  removed: number
}

declare module 'claude-code' {
  interface PluginState {
    'mod-replay-theater': {
      pending: ReplayStep[]
      replay: ReplayStep[]
      index: number
      isHintShown: boolean
    }
  }
}
