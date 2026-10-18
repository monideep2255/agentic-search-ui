// Pure secret-shape scanner for mod-secrets-scan. No `$` in this file.

export type Finding = { name: string; line: number; preview: string }
export type ExtraPattern = { name: string; source: string }

export const ALLOW_MARKER = 'secrets-scan: allow'

// A value that is plainly a stand-in. Applies to every shape match and every field value.
const PLACEHOLDER = /<[^>]*>|\$\{|x{6,}|\.\.\.|test|dummy|fake|fixture|sample|placeholder|redacted|example|changeme|change-me|replace-with|your[_-]/i
const REPEATED = /^(.)\1+$/
const BASE64_LINE = /^[A-Za-z0-9+/]{16,}={0,2}$/
const TEST_PATH = /(^|\/)(tests?|test_fixtures)\/|(^|\/)(test_[^/]*|[^/]*_test|conftest)\.py$/
const MARKDOWN_PATH = /\.(md|markdown)$/i

function isPlaceholder(value: string): boolean {
  return PLACEHOLDER.test(value) || REPEATED.test(value)
}

const PATTERNS: { name: string; re: RegExp }[] = [
  { name: 'OpenAI-style sk- key', re: /(?:^|[^A-Za-z0-9_])(sk-[A-Za-z0-9_-]{20,})/ },
  { name: 'GitHub token', re: /(?:^|[^A-Za-z0-9_])(gh[opus]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{22,})/ },
  { name: 'AWS access key id', re: /(AKIA[0-9A-Z]{16})/ },
  { name: 'Slack token', re: /(xox[bpras]-[A-Za-z0-9-]{10,})/ },
  { name: 'PEM private key header', re: /(-----BEGIN [A-Z ]*PRIVATE\s+KEY-----)/ },
  { name: 'NCBI API key', re: /(NCBI_API_KEY\s*=\s*["']?[0-9a-fA-F]{32,})/ },
]

const FIELD = /[A-Za-z0-9_.-]*(?:token|secret|password|api_key|apikey|auth)["']?\s*[:=](?!=)\s*(["'])([^"'\s]{12,})\1/i

function preview(value: string): string {
  return value.slice(0, 4) + '...'
}

/** True when a PEM header is prose: inside a code span, or in a markdown file with no base64 body after it. */
function pemIsProse(lines: string[], i: number, path: string | undefined): boolean {
  if (/`[^`]*-----BEGIN[^`]*`/.test(lines[i])) return true
  if (path === undefined || !MARKDOWN_PATH.test(path)) return false
  for (let j = i + 1; j < lines.length; j++) {
    const next = lines[j].trim()
    if (next === '') continue
    return !BASE64_LINE.test(next)
  }
  return true
}

/**
 * Scan text line by line. Lines carrying the allow marker are skipped.
 * `path` is the file being written, when there is one; it relaxes prose PEM headers
 * in markdown and short test passwords in test files.
 */
export function scanText(text: string, extra: readonly ExtraPattern[] = [], path?: string): Finding[] {
  const out: Finding[] = []
  const custom: { name: string; re: RegExp }[] = []
  for (const p of extra) {
    try {
      custom.push({ name: p.name, re: new RegExp(p.source) })
    } catch {
      // a bad extra pattern is ignored
    }
  }
  const lines = text.split('\n')
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    if (line.includes(ALLOW_MARKER)) continue
    for (const p of [...PATTERNS, ...custom]) {
      const m = p.re.exec(line)
      if (!m) continue
      const value = m[1] ?? m[0]
      // a trailing ellipsis sits outside the character class, so look just past the match too
      if (isPlaceholder(value) || line.slice(m.index + m[0].length, m.index + m[0].length + 3) === '...') continue
      if (p.name === 'PEM private key header' && pemIsProse(lines, i, path)) continue
      out.push({ name: p.name, line: i + 1, preview: preview(value) })
    }
    const f = FIELD.exec(line)
    const testPassword = path !== undefined && TEST_PATH.test(path) && f !== null && f[2].length < 16
    if (f && !PLACEHOLDER.test(f[2]) && !testPassword) {
      out.push({ name: 'secret-named field with literal value', line: i + 1, preview: preview(f[2]) })
    }
  }
  return out
}
