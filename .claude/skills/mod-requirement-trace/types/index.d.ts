export type TraceRef = { kind: 'card' | 'phase'; id: string }

declare module 'claude-code' {
  interface PluginState {
    'mod-requirement-trace': {
      /** The reference found in the most recent prompt that carried one. */
      ref: TraceRef | null
    }
  }
}
