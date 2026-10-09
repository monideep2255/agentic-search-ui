export type StackStatusSeen = boolean

declare module 'claude-code' {
  interface PluginState {
    'mod-stack-status': { everUp: boolean }
  }
}
