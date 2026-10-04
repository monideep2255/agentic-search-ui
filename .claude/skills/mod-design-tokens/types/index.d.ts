export type DesignTokensFindings = string[] | null

declare module 'claude-code' {
  interface PluginState {
    'mod-design-tokens': { lastRunAt: number; isPending: boolean; findings: string[] | null }
  }
}
