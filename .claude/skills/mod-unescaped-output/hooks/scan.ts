// Pure pattern scanning for mod-unescaped-output. No engine access here.

export type Finding = { id: string; message: string; line: string }

const NON_LITERAL = String.raw`(?![\s"'])(?!\x60[^\x60$]*\x60)`

const FRONTEND: { id: string; message: string; re: RegExp }[] = [
  { id: 'dangerously-set-inner-html', message: 'dangerouslySetInnerHTML turns off escaping', re: /dangerouslySetInnerHTML/ },
  { id: 'inner-html', message: '.innerHTML assignment is unescaped output', re: /\.innerHTML\s*=(?!=)/ },
  { id: 'outer-html', message: 'outerHTML assignment is unescaped output', re: /\bouterHTML\s*=(?!=)/ },
  { id: 'document-write', message: 'document.write( is unescaped output', re: /document\.write\(/ },
  { id: 'location-assign', message: 'redirect assigned from a non-literal value', re: new RegExp(String.raw`\b(?:window\.)?location(?:\.href)?\s*=(?!=)\s*` + NON_LITERAL) },
  { id: 'window-open', message: 'window.open( with a non-literal URL', re: new RegExp(String.raw`window\.open\(\s*` + NON_LITERAL + String.raw`\S`) },
]

const SQL_SHAPE = String.raw`(?:SELECT\b[^"'\n]*\bFROM\b|INSERT\s+INTO\b|UPDATE\b[^"'\n]*\bSET\b|DELETE\s+FROM\b)`

const PYTHON: { id: string; message: string; re: RegExp }[] = [
  { id: 'sql-fstring', message: 'SQL built with an f-string', re: new RegExp(String.raw`\b[fF][rR]?(["'])[^"'\n]*${SQL_SHAPE}[^\n]*\{`, 'i') },
  { id: 'sql-percent', message: 'SQL built with the % operator', re: new RegExp(String.raw`["'][^"'\n]*${SQL_SHAPE}[^"'\n]*["']\s*%\s*[\w(\[{]`, 'i') },
  { id: 'sql-format', message: 'SQL built with .format', re: new RegExp(String.raw`["'][^"'\n]*${SQL_SHAPE}[^"'\n]*["']\s*\.format\(`, 'i') },
  { id: 'execute-concat', message: 'execute( called with a concatenated string', re: /\bexecute\(\s*(?:[^,)\n]*["']\s*\+|[A-Za-z_][\w.]*\s*\+)/ },
]

function isComment(line: string, python: boolean): boolean {
  const t = line.trim()
  return python ? t.startsWith('#') : t.startsWith('//') || t.startsWith('*') || t.startsWith('/*')
}

// Text of the opening tag around index `at`: from the last "<" before it to the first ">" that is not part of "=>".
function tagAround(text: string, at: number): string {
  const start = text.lastIndexOf('<', at)
  let end = at
  while (end < text.length) {
    if (text[end] === '>' && text[end - 1] !== '=') break
    end++
  }
  return text.slice(start < 0 ? 0 : start, end + 1)
}

/** Findings in `text`, each with the trimmed line that triggered it. */
export function scan(text: string, kind: 'frontend' | 'python'): Finding[] {
  const out: Finding[] = []
  const lines = text.split('\n')
  const python = kind === 'python'
  const table = python ? PYTHON : FRONTEND
  let offset = 0
  for (const line of lines) {
    if (!isComment(line, python)) {
      for (const p of table) if (p.re.test(line)) out.push({ id: p.id, message: p.message, line: line.trim() })
      if (!python && /target\s*=\s*(?:"_blank"|'_blank'|\{\s*["']_blank["']\s*\})/.test(line)) {
        const at = offset + line.search(/target\s*=/)
        const tag = tagAround(text, at)
        const rel = tag.match(/\brel\s*=\s*(?:"([^"]*)"|'([^']*)'|\{\s*["']([^"']*)["']\s*\})/)
        const value = rel ? (rel[1] ?? rel[2] ?? rel[3] ?? '') : ''
        if (!/noopener/.test(value)) out.push({ id: 'target-blank', message: 'target="_blank" without rel containing noopener', line: line.trim() })
      }
    }
    offset += line.length + 1
  }
  return out
}
