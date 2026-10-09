import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { TraceRef } from '../types'
import { config } from './config.ts'

const ref = atom({ plugin: 'mod-requirement-trace', key: 'ref' } as const, null)

const CARD = /\bcards?\s*#?\s*(\d{1,3})\b/i
const PHASE_WORD = /\b(?:phase|step)s?\s*(\d{1,2}\.\d{1,2})\b(?!\.\d)/i
const PHASE_BARE = /(?<![\w.])(\d{1,2}\.\d{1,2})(?![\w]|\.\d)\s*([A-Za-z]*)/g

type Source = { path: string; text: string }

// The reference a piece of text carries, or undefined. The earlier of a card and a phase wins.
// A bare number such as "6.2" counts only when `isKnownPhase` says the board has it.
function findRef(text: string, isKnownPhase: (id: string) => boolean): TraceRef | undefined {
  const found: Array<{ at: number; ref: TraceRef }> = []
  const card = CARD.exec(text)
  if (card) found.push({ at: card.index, ref: { kind: 'card', id: String(Number(card[1])) } })
  const word = PHASE_WORD.exec(text)
  if (word) found.push({ at: word.index, ref: { kind: 'phase', id: word[1] } })
  for (const m of text.matchAll(PHASE_BARE)) {
    if (config.unitWords.includes(m[2].toLowerCase())) continue
    if (isKnownPhase(m[1])) {
      found.push({ at: m.index ?? 0, ref: { kind: 'phase', id: m[1] } })
      break
    }
  }
  found.sort((a, b) => a.at - b.at)
  return found[0]?.ref
}

function cell(row: string, index: number): string {
  const cells = row.split('|').map(c => c.trim())
  return cells[index + 1] ?? ''
}

function tidy(title: string): string {
  return title.replace(/`/g, '').replace(/\s+/g, ' ').trim()
}

function cardTitle(text: string, id: string): string | undefined {
  for (const line of text.split('\n')) {
    if (line.startsWith('|') && cell(line, 0) === id) {
      const t = tidy(cell(line, 1))
      if (t !== '') return t
    }
  }
  return undefined
}

function phaseTitle(text: string, id: string): string | undefined {
  for (const line of text.split('\n')) {
    if (line.startsWith('|') && cell(line, 0) === id) {
      const t = tidy(cell(line, 2))
      if (t !== '') return t
    }
  }
  return undefined
}

function hasBoardPhase(text: string, id: string): boolean {
  return phaseTitle(text, id) !== undefined
}

function mentionsPhase(text: string, id: string): boolean {
  const escaped = id.replace('.', '\\.')
  return new RegExp(`\\bphases?\\s*${escaped}(?![\\d])`, 'i').test(text)
}

function headingLines(text: string): string[] {
  return text.split('\n').filter(l => /^#{1,6}\s+\S/.test(l)).map(l => l.trim())
}

// Headings above and at the card row's position: the nearest one tells the reader which section the card sits in.
function sectionOfCard(text: string, id: string): string | undefined {
  let last: string | undefined
  for (const line of text.split('\n')) {
    if (/^#{1,6}\s+\S/.test(line)) last = line.trim()
    else if (line.startsWith('|') && cell(line, 0) === id) return last
  }
  return undefined
}

// Meeting file names that belong to a phase step. Matches the step itself, a range such as 1.1-1.5, or the whole phase.
function meetingMatches(name: string, id: string): boolean {
  const escaped = id.replace('.', '\\.')
  if (new RegExp(`(?<![\\d.])${escaped}(?![\\d])`).test(name)) return true
  const [major, minor] = id.split('.').map(Number)
  for (const m of name.matchAll(/(\d+)\.(\d+)-(\d+)\.(\d+)/g)) {
    if (Number(m[1]) === major && Number(m[3]) === major && Number(m[2]) <= minor && minor <= Number(m[4])) return true
  }
  const wholePhase = new RegExp(`Phase_${major}(?![\\d.])`).test(name)
  const hasStep = /steps?_\d/i.test(name)
  return wholePhase && !hasStep
}

async function repoRoot($: EngineInterface): Promise<string | undefined> {
  try {
    const repo = await $.session.repo()
    return repo?.root
  } catch {
    return undefined
  }
}

async function readText($: EngineInterface, path: string): Promise<string | undefined> {
  try {
    if (!(await $.fs.exists(path))) return undefined
    const text = await $.fs.read(path)
    return typeof text === 'string' ? text : undefined
  } catch {
    return undefined
  }
}

async function loadSources($: EngineInterface, root: string): Promise<{ cards?: Source; board?: Source }> {
  const cardsText = await readText($, `${root}/${config.cardsFile}`)
  const boardText = await readText($, `${root}/${config.boardFile}`)
  return {
    cards: cardsText === undefined ? undefined : { path: config.cardsFile, text: cardsText },
    board: boardText === undefined ? undefined : { path: config.boardFile, text: boardText },
  }
}

function statusFor(target: TraceRef, s: { cards?: Source; board?: Source }): string | undefined {
  if (target.kind === 'card') {
    const title = s.cards === undefined ? undefined : cardTitle(s.cards.text, target.id)
    return title === undefined ? undefined : `trace: card ${target.id} ${title.slice(0, config.titleChars)}`
  }
  const title = s.board === undefined ? undefined : phaseTitle(s.board.text, target.id)
  if (title !== undefined) return `trace: phase ${target.id} ${title.slice(0, config.titleChars)}`
  if (s.cards !== undefined && mentionsPhase(s.cards.text, target.id)) {
    return `trace: phase ${target.id} is past the frozen board, see ${config.cardsFile}`
  }
  return undefined
}

function listHeadings(lines: string[]): string[] {
  const shown = lines.slice(0, config.maxHeadingsPerFile).map(l => `  ${l}`)
  if (lines.length > shown.length) shown.push(`  (${lines.length - shown.length} more headings)`)
  return shown
}

export const register: Register = on => {
  on('prompt.submit', async ($, e, next) => {
    try {
      const root = await repoRoot($)
      if (root !== undefined) {
        const s = await loadSources($, root)
        const found = findRef(e.text, id => s.board !== undefined && hasBoardPhase(s.board.text, id))
        if (found !== undefined) {
          const line = statusFor(found, s)
          if (line !== undefined) {
            await update($, ref, () => found)
            $.ui.status(line)
          }
        }
      }
    } catch {
      // an observer that breaks stays quiet
    }
    return next(e)
  })

  on('session.start', async ($, e, next) => {
    const r = await next(e)
    await $.command.register({ name: 'trace', description: 'List the source files behind the current card or phase reference', argumentHint: '[card N | phase N.N]' })
    return r
  })

  on('command.run', { command: 'trace' }, async ($, e) => {
    const root = await repoRoot($)
    if (root === undefined) return { text: 'mod-requirement-trace: no repository found' }
    const s = await loadSources($, root)

    const typed = String(e.args ?? '').trim()
    let target: TraceRef | undefined = await read($, ref) ?? undefined
    if (typed !== '') {
      const fromArgs = findRef(typed, id => s.board !== undefined && hasBoardPhase(s.board.text, id)) ?? findRef(`phase ${typed}`, () => false) ?? findRef(`card ${typed}`, () => false)
      if (fromArgs === undefined) return { text: 'Give a card or phase, for example /trace card 84 or /trace phase 6.2' }
      target = fromArgs
    }
    if (target === undefined) return { text: 'No reference yet. Mention a card or phase in a prompt, or run /trace card 84.' }

    const out: string[] = [`Reference: ${target.kind} ${target.id}`]

    if (target.kind === 'card' && s.cards !== undefined && cardTitle(s.cards.text, target.id) !== undefined) {
      const section = sectionOfCard(s.cards.text, target.id)
      out.push(s.cards.path)
      if (section !== undefined) out.push(`  section: ${section}`)
      out.push(...listHeadings(headingLines(s.cards.text)))
    }

    if (target.kind === 'phase') {
      if (s.board !== undefined && hasBoardPhase(s.board.text, target.id)) {
        out.push(s.board.path)
        out.push(...listHeadings(headingLines(s.board.text)))
      }
      if (s.cards !== undefined && mentionsPhase(s.cards.text, target.id)) {
        out.push(s.cards.path)
        out.push(...listHeadings(headingLines(s.cards.text)))
      }
      let entries: { name: string; kind: string }[] = []
      try {
        entries = await $.fs.list(`${root}/${config.meetingsDir}`)
      } catch {
        entries = []
      }
      const names = entries.filter(x => x.kind === 'file' && x.name.endsWith('.md') && meetingMatches(x.name, target.id)).map(x => x.name).sort()
      for (const name of names) {
        out.push(`${config.meetingsDir}/${name}`)
        const body = await readText($, `${root}/${config.meetingsDir}/${name}`)
        if (body !== undefined) out.push(...listHeadings(headingLines(body)))
      }
    }

    if (out.length === 1) return { text: `No source file found for ${target.kind} ${target.id}` }
    return { text: out.join('\n') }
  })
}
