// Per-repository settings for mod-blast-radius in agentic-search-data-engineering.
// The default risky classes are built into the mod; these rules add the ways
// this repository reaches the live knowledge graph server. The sync never
// overwrites this file. No server address or user name belongs here.
//
// Each extra rule has a name, a matcher over one simple command (its program
// words with wrappers removed, the raw segment text, and the whole command
// line for SQL piped in from elsewhere), and an optional dry-run argument
// vector that runs without a shell before the person is asked.

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

const RUNNERS = new Set(['uv', 'poetry', 'pipx', 'pdm', 'hatch'])
const LOADER_MODULE = 'system_02_knowledge_graph.loader'
const LOADER_PATH = /(^|\/)system-02-knowledge-graph\/loader\/[^/]+\.py$/

function base(word: string | undefined): string {
  const parts = (word ?? '').split('/')
  return parts[parts.length - 1]
}

function isPython(word: string | undefined): boolean {
  return /^python(3(\.\d+)?)?$/.test(base(word))
}

/** The program words with a leading `uv run` or `poetry run` style runner removed. */
function unwrap(words: readonly string[]): readonly string[] {
  if (RUNNERS.has(base(words[0])) && words[1] === 'run') return words.slice(2)
  return words
}

/** The text inside each `cypher('graph', $$ ... $$)` body of a command line. */
function cypherBodies(command: string): string[] {
  const out: string[] = []
  const re = /cypher\s*\([^$]*\$\$([\s\S]*?)\$\$/gi
  let m: RegExpExecArray | null
  while ((m = re.exec(command)) !== null) out.push(m[1])
  return out
}

const WRITE_CYPHER = /\b(CREATE|MERGE|SET|DELETE|DETACH\s+DELETE|REMOVE)\b/i

export const config: BlastConfig = {
  maxReportLines: 40,
  deferToPublicGuard: ['monideep2255/agentic-search-data-engineering'],
  extraRules: [
    {
      name: 'ssh to a remote host',
      match: words => base(words[0]) === 'ssh',
    },
    {
      name: 'age-load into the knowledge graph',
      match: words => base(unwrap(words)[0]) === 'age-load',
    },
    {
      name: 'psql with write Cypher or DELETE FROM',
      match: (words, _segment, command) =>
        base(words[0]) === 'psql' &&
        (/\bDELETE\s+FROM\b/i.test(command) || cypherBodies(command).some(body => WRITE_CYPHER.test(body))),
    },
    {
      name: 'knowledge graph loader command line',
      match: words => {
        const w = unwrap(words)
        if (!isPython(w[0])) return false
        const at = w.indexOf('-m')
        if (at >= 0 && (w[at + 1] ?? '').startsWith(LOADER_MODULE)) return true
        return w.slice(1).some(arg => LOADER_PATH.test(arg))
      },
    },
  ],
}
