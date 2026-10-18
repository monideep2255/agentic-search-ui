// A small line diff. Pure functions, no engine access.

export type DiffLine = { kind: 'add' | 'del' | 'ctx' | 'note'; text: string }

export type DiffResult = {
  lines: DiffLine[]
  added: number
  removed: number
}

/** Largest middle section (old lines times new lines) the LCS table may cover. */
export const MAX_CELLS = 400_000
const CONTEXT = 3

function split(text: string): string[] {
  if (text === '') return []
  const parts = text.split('\n')
  if (parts[parts.length - 1] === '') parts.pop()
  return parts
}

type Op = { kind: 'add' | 'del' | 'ctx'; text: string }

function lcsOps(a: string[], b: string[]): Op[] {
  const n = a.length
  const m = b.length
  const w = m + 1
  const t = new Uint32Array((n + 1) * w)
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      t[i * w + j] = a[i] === b[j] ? t[(i + 1) * w + j + 1] + 1 : Math.max(t[(i + 1) * w + j], t[i * w + j + 1])
    }
  }
  const ops: Op[] = []
  let i = 0
  let j = 0
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      ops.push({ kind: 'ctx', text: a[i] })
      i++
      j++
    } else if (t[(i + 1) * w + j] >= t[i * w + j + 1]) {
      ops.push({ kind: 'del', text: a[i++] })
    } else {
      ops.push({ kind: 'add', text: b[j++] })
    }
  }
  while (i < n) ops.push({ kind: 'del', text: a[i++] })
  while (j < m) ops.push({ kind: 'add', text: b[j++] })
  return ops
}

/** Unified line diff of two texts, with a few lines of context around each change. */
export function diffLines(oldText: string, newText: string): DiffResult {
  const a = split(oldText)
  const b = split(newText)
  let start = 0
  while (start < a.length && start < b.length && a[start] === b[start]) start++
  let endA = a.length
  let endB = b.length
  while (endA > start && endB > start && a[endA - 1] === b[endB - 1]) {
    endA--
    endB--
  }
  const midA = a.slice(start, endA)
  const midB = b.slice(start, endB)

  if (midA.length * midB.length > MAX_CELLS) {
    return {
      lines: [{ kind: 'note', text: `file replaced: ${midA.length} lines removed, ${midB.length} added` }],
      added: midB.length,
      removed: midA.length,
    }
  }

  const ops: Op[] = [
    ...a.slice(0, start).map((text): Op => ({ kind: 'ctx', text })),
    ...lcsOps(midA, midB),
    ...a.slice(endA).map((text): Op => ({ kind: 'ctx', text })),
  ]

  const keep = new Array<boolean>(ops.length).fill(false)
  ops.forEach((op, k) => {
    if (op.kind === 'ctx') return
    for (let x = Math.max(0, k - CONTEXT); x <= Math.min(ops.length - 1, k + CONTEXT); x++) keep[x] = true
  })

  const lines: DiffLine[] = []
  let added = 0
  let removed = 0
  let skipped = false
  ops.forEach((op, k) => {
    if (op.kind === 'add') added++
    if (op.kind === 'del') removed++
    if (!keep[k]) {
      skipped = true
      return
    }
    if (skipped && lines.length > 0) lines.push({ kind: 'note', text: '...' })
    skipped = false
    lines.push({ kind: op.kind, text: op.text })
  })
  return { lines, added, removed }
}

/** The prefix a line carries in a unified diff. */
export function prefixOf(line: DiffLine): string {
  if (line.kind === 'add') return '+'
  if (line.kind === 'del') return '-'
  if (line.kind === 'ctx') return ' '
  return ''
}

/** Cut a diff to `max` lines; the rest is counted, not kept. */
export function capLines(lines: DiffLine[], max: number): { lines: DiffLine[]; more: number } {
  if (lines.length <= max) return { lines, more: 0 }
  return { lines: lines.slice(0, max), more: lines.length - max }
}
