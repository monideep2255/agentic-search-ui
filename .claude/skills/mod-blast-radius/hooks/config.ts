// Per-repository settings for mod-blast-radius in agentic-search-ui. The
// default risky classes are built into the mod, and they already cover
// `alembic downgrade` and `alembic upgrade`, so no rule repeats them here.
// These rules add the Railway commands that change or remove the
// live deployment. The sync never overwrites this file.
//
// Each extra rule has a name, a matcher over one simple command (its program
// words with wrappers removed, the raw segment text, and the whole command
// line), and an optional dry-run argument vector that runs without a shell
// before the person is asked. `railway status` shows which project and
// environment the command would act on.

export type BlastRule = {
  name: string
  match: (words: readonly string[], segment: string, command: string) => boolean
  dryRun?: readonly string[]
}

export type BlastConfig = {
  maxReportLines: number
  extraRules: readonly BlastRule[]
  /** Lowercase owner/name slugs of public remotes that mod-public-repo-guard already denies a force push to outright. */
  deferToPublicGuard: readonly string[]
}

function base(word: string | undefined): string {
  const parts = (word ?? '').split('/')
  return parts[parts.length - 1]
}

/** The railway subcommand words, with a leading `npx` or `bunx` launcher removed; empty when not railway. */
function railway(words: readonly string[]): readonly string[] {
  const isLauncher = base(words[0]) === 'npx' || base(words[0]) === 'bunx'
  const w = isLauncher ? words.slice(1).filter(x => !x.startsWith('-')) : words
  const head = w[0] ?? ''
  if (head !== '@railway/cli' && base(head) !== 'railway') return []
  return w.slice(1).filter(x => !x.startsWith('-'))
}

const STATUS = ['railway', 'status'] as const

export const config: BlastConfig = {
  maxReportLines: 40,
  deferToPublicGuard: ['monideep2255/agentic-search-ui'],
  extraRules: [
    {
      name: 'railway down',
      match: words => railway(words)[0] === 'down',
      dryRun: STATUS,
    },
    {
      name: 'railway delete',
      match: words => railway(words).includes('delete'),
      dryRun: STATUS,
    },
    {
      name: 'railway redeploy',
      match: words => railway(words)[0] === 'redeploy',
      dryRun: STATUS,
    },
    {
      name: 'railway up deploys over the live service',
      match: words => railway(words)[0] === 'up',
      dryRun: STATUS,
    },
    {
      name: 'railway variables change on the live service',
      match: words => {
        const r = railway(words)
        return (r[0] === 'variables' || r[0] === 'variable') && /\s(--set|-s|delete)\b/.test(' ' + words.join(' '))
      },
      dryRun: STATUS,
    },
  ],
}
