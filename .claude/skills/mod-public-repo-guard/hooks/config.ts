// Per-repository policy for mod-public-repo-guard. A remote listed here is
// public. Each entry names the leak scanner (a path relative to the target
// repository root, or none), the branches a push may never reach, and the
// branches a push may reach only after the person confirms.

export type RemotePolicy = {
  leakScanner?: string
  deniedBranches: readonly string[]
  confirmBranches: readonly string[]
}

export const config: { publicRemotes: Record<string, RemotePolicy> } = {
  publicRemotes: {
    'monideep2255/agentic-search-data-engineering': {
      leakScanner: 'scripts/check_public_leaks.py',
      deniedBranches: ['production', 'main', 'develop'],
      confirmBranches: [],
    },
    'monideep2255/agentic-search-ui': {
      leakScanner: '.claude/skills/ship/scripts/check_public_leaks.py',
      deniedBranches: ['production', 'main'],
      confirmBranches: ['develop'],
    },
    'monideep2255/ai-chief-of-staff': {
      deniedBranches: [],
      confirmBranches: [],
    },
  },
}
