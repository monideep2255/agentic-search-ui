import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { CaptureRow } from '../types'
import { config } from './config.ts'
import { globToRegExp, inside, matchesAny } from './kit/paths.ts'

const PANE = 'route-capture'
const pending = atom({ plugin: 'mod-route-capture', key: 'pending' } as const, [])
const screens = atom({ plugin: 'mod-route-capture', key: 'screens' } as const, [])
const skipped = atom({ plugin: 'mod-route-capture', key: 'skipped' } as const, [])
const isBandShown = atom({ plugin: 'mod-route-capture', key: 'isBandShown' } as const, false)
const rows = atom({ plugin: 'mod-route-capture', key: 'rows' } as const, [])
const note = atom({ plugin: 'mod-route-capture', key: 'note' } as const, '')

const ROW = /^- (PASS|FAIL) \| (.+?) at (\d+) \| (.+?) \| (.*?) \| (.*)$/

// Lines the capture script prints, one per check. Anything else is ignored.
function parseRows(stdout: string): CaptureRow[] {
  const out: CaptureRow[] = []
  for (const line of stdout.split('\n')) {
    const m = ROW.exec(line.trim())
    if (m) out.push({ result: m[1] as 'PASS' | 'FAIL', screen: m[2], width: m[3], check: m[4], value: m[5] })
  }
  return out
}

function isIgnored(rel: string): boolean {
  return matchesAny(rel, config.ignore)
}

function screensFor(rel: string): string[] {
  const found = new Set<string>()
  for (const rule of config.rules) {
    if (globToRegExp(rule.glob).test(rel)) for (const s of rule.screens) found.add(s)
  }
  return [...found]
}

async function repoRoot($: EngineInterface): Promise<string | undefined> {
  try {
    const repo = await $.session.repo()
    return repo?.root
  } catch {
    return undefined
  }
}

async function run($: EngineInterface, argv: readonly string[], init: { cwd?: string; timeoutMs?: number; stdin?: string } = {}) {
  try {
    const r = await $.process.run(argv, { timeoutMs: 20_000, ...init })
    return { exitCode: r.exitCode, stdout: r.stdout, stderr: r.stderr, failed: undefined as string | undefined }
  } catch (err) {
    return { exitCode: -1, stdout: '', stderr: '', failed: err instanceof Error ? err.message : String(err) }
  }
}

async function openPane($: EngineInterface, id: string, title: string, fallback: string) {
  const opened = await $.ui.open({ id, title })
  if (!opened.isPlaced) $.ui.toast(fallback)
  return opened.isPlaced
}

// True when the URL answers within the probe timeout. A refusal, an error, or no answer all count as down.
async function isReachable($: EngineInterface, url: string): Promise<boolean> {
  try {
    const answer = await Promise.race([
      $.http.fetch(url),
      $.clock.sleep(config.probeTimeoutMs).then(() => null),
    ])
    return answer !== null
  } catch {
    return false
  }
}

async function recordEdit($: EngineInterface, filePath: string) {
  const root = await repoRoot($)
  if (root === undefined) return
  const rel = inside(root, filePath)
  if (rel === undefined || !rel.startsWith(config.sourceRoot)) return
  const underSource = rel.slice(config.sourceRoot.length)
  if (isIgnored(underSource)) return
  await update($, pending, list => (list.includes(underSource) ? list : [...list, underSource]))
}

export const register: Register = on => {
  on('tool.call', { tool: 'Edit' }, async ($, e, next) => {
    if (e.agentId !== undefined) return next(e)
    const ran = await next(e)
    if (ran.deny === undefined && ran.isError !== true) {
      try {
        await recordEdit($, e.file_path)
      } catch {
        // an observer that breaks stays quiet
      }
    }
    return ran
  })

  on('tool.call', { tool: 'Write' }, async ($, e, next) => {
    if (e.agentId !== undefined) return next(e)
    const ran = await next(e)
    if (ran.deny === undefined && ran.isError !== true) {
      try {
        await recordEdit($, e.file_path)
      } catch {
        // an observer that breaks stays quiet
      }
    }
    return ran
  })

  on('turn.start', async ($, e, next) => {
    await update($, pending, () => [])
    return next(e)
  })

  on('turn.complete', async ($, e, next) => {
    const r = await next(e)
    if (e.agentId === undefined) {
      try {
        const files = await read($, pending)
        if (files.length > 0) {
          const all = new Set<string>()
          for (const f of files) for (const s of screensFor(f)) all.add(s)
          const capturable = [...all].filter(s => config.screenPaths[s] !== undefined)
          const unreachable = [...all].filter(s => config.screenPaths[s] === undefined)
          await update($, pending, () => [])
          if (capturable.length > 0) {
            await update($, screens, () => capturable)
            await update($, skipped, () => unreachable)
            await update($, isBandShown, () => true)
          }
        }
      } catch {
        // an observer that breaks stays quiet
      }
    }
    return r
  })

  on('session.start', async ($, e, next) => {
    const r = await next(e)
    await $.command.register({ name: 'capture', description: 'Screenshot and check the changed frontend screens, or all of them', argumentHint: '[all]' })
    return r
  })

  on('command.run', { command: 'capture' }, async ($, e) => {
    const root = await repoRoot($)
    if (root === undefined) return { text: 'mod-route-capture: no repository found' }
    const wantsAll = String(e.args ?? '').trim() === 'all'

    const names = await read($, screens)
    if (!wantsAll && names.length === 0) {
      return { text: 'No changed frontend screens recorded. Run /capture all to capture every screen in the specs.' }
    }

    const web = await isReachable($, config.webUrl)
    const api = web ? await isReachable($, config.apiHealthUrl) : false
    if (!web || !api) {
      $.ui.toast(`mod-route-capture: the local dev server is not reachable (${web ? 'API' : 'web app'}). Start it, then run /capture again.`)
      return { text: 'Local dev server not reachable, nothing captured' }
    }

    const base = ['node', config.script, '--target', 'local', '--topic', config.topic]
    const runs: string[][] = []
    if (wantsAll) {
      let entries: { name: string; kind: string }[] = []
      try {
        entries = await $.fs.list(`${root}/${config.specsDir}`)
      } catch {
        entries = []
      }
      for (const entry of entries) {
        if (entry.kind === 'file' && entry.name.endsWith('.json')) {
          runs.push([...base, '--spec', `../${config.specsDir}/${entry.name}`])
        }
      }
      if (runs.length === 0) return { text: 'No spec files found, nothing captured' }
    } else {
      const args = names.flatMap(s => ['--screen', `${s}=${config.screenPaths[s]}`])
      runs.push([...base, ...args])
    }

    const all: CaptureRow[] = []
    let problem: string | undefined
    // Each run writes under the gitignored outRoot, never into a tracked folder.
    const stamp = new Date(await $.clock.now()).toISOString().replace(/[:.]/g, '-')
    for (const [index, argv] of runs.entries()) {
      const out = `${root}/${config.outRoot}/${stamp}-${index + 1}`
      const r = await run($, [...argv, '--out', out], { cwd: `${root}/${config.workingDir}`, timeoutMs: config.captureTimeoutMs })
      if (r.failed !== undefined) {
        problem = `the capture did not finish: ${r.failed.slice(0, 120)}`
        continue
      }
      const parsed = parseRows(r.stdout)
      all.push(...parsed)
      if (r.exitCode === 2 || (r.exitCode !== 0 && parsed.length === 0)) {
        const first = (r.stderr || r.stdout).split('\n').find(l => l.trim() !== '') ?? 'no output'
        problem = `the capture script refused the run: ${first.slice(0, 160)}`
      }
    }

    await update($, rows, () => all)
    const failed = all.filter(x => x.result === 'FAIL').length
    const line = problem ?? `${all.length - failed} pass, ${failed} fail across ${new Set(all.map(x => x.screen)).size} screens`
    await update($, note, () => line)
    await update($, isBandShown, () => false)
    if (all.length === 0) return { text: `mod-route-capture: ${problem ?? 'the script reported no checks'}` }
    await openPane($, PANE, 'Capture', 'mod-route-capture: widen the terminal to see the capture results')
    return { text: `Captured: ${line}` }
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const names = await read($, screens)
    const isQuiet = e.props.hasSurvey || names.length === 0 || !(await read($, isBandShown))
    if (isQuiet) return next(e)

    const { Box, Button, Text } = $.ui.resolve(e)
    return (
      <Box>
        <Text dimColor>
          Frontend changed: /capture to screenshot {names.length} {names.length === 1 ? 'screen' : 'screens'}{' '}
        </Text>
        <Button key="dismiss" label="Dismiss" onPress={() => update($, isBandShown, () => false)} />
      </Box>
    )
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Button, Text } = $.ui.resolve(e)
    const list = await read($, rows)
    const line = await read($, note)
    const left = await read($, skipped)
    const order = [...new Set(list.map(x => x.screen))]

    return (
      <Box flexDirection="column">
        <Text bold>Capture results</Text>
        <Text dimColor>{line}</Text>
        {order.map(name => {
          const mine = list.filter(x => x.screen === name)
          const ok = mine.every(x => x.result === 'PASS')
          return (
            <Box key={`s-${name}`} flexDirection="column">
              <Text bold color={ok ? 'green' : 'red'}>
                {name}: {ok ? 'PASS' : 'FAIL'}
              </Text>
              {mine.map((x, i) => (
                <Text key={`r-${name}-${i}`} color={x.result === 'PASS' ? 'green' : 'red'}>
                  {'  '}
                  {x.result} at {x.width}: {x.check}, {x.value}
                </Text>
              ))}
            </Box>
          )
        })}
        {left.length > 0 && <Text dimColor>Not capturable by address alone, needs a spec: {left.join(', ')}</Text>}
        <Box>
          <Button key="close" label="Close" hotkey="c" onPress={() => $.ui.close({ id: PANE })} />
        </Box>
      </Box>
    )
  })
}
