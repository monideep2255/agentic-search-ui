import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { ReplayStep } from '../types'
import { config } from './config.ts'
import { capLines, diffLines, prefixOf } from './diff.ts'

const PANE = 'replay-theater'
const pending = atom({ plugin: 'mod-replay-theater', key: 'pending' } as const, [])
const replay = atom({ plugin: 'mod-replay-theater', key: 'replay' } as const, [])
const index = atom({ plugin: 'mod-replay-theater', key: 'index' } as const, 0)
const isHintShown = atom({ plugin: 'mod-replay-theater', key: 'isHintShown' } as const, false)

function stepFrom(tool: 'Edit' | 'Write', path: string, label: string, oldText: string, newText: string): ReplayStep {
  const d = diffLines(oldText, newText)
  const capped = capLines(d.lines, config.maxDiffLines)
  return { tool, path, label, lines: capped.lines, more: capped.more, added: d.added, removed: d.removed }
}

async function openPane($: EngineInterface, id: string, title: string, fallback: string) {
  const opened = await $.ui.open({ id, title })
  if (!opened.isPlaced) $.ui.toast(fallback)
  return opened.isPlaced
}

async function showReplay($: EngineInterface) {
  const steps = await read($, replay)
  if (steps.length === 0) return false
  await update($, index, () => 0)
  await openPane($, PANE, 'Replay', 'mod-replay-theater: widen the terminal to see the replay')
  return true
}

export const register: Register = on => {
  on('tool.call', { tool: 'Edit' }, async ($, e, next) => {
    if (e.agentId !== undefined) return next(e)
    let step: ReplayStep | undefined
    try {
      const label = e.replace_all === true ? 'Edit, replace all' : 'Edit'
      step = stepFrom('Edit', e.file_path, label, e.old_string, e.new_string)
    } catch {
      step = undefined
    }
    const ran = await next(e)
    if (step !== undefined && ran.deny === undefined && ran.isError !== true) {
      const s = step
      await update($, pending, list => [...list, s].slice(-config.maxSteps))
    }
    return ran
  })

  on('tool.call', { tool: 'Write' }, async ($, e, next) => {
    if (e.agentId !== undefined) return next(e)
    let step: ReplayStep | undefined
    try {
      let before: string | undefined
      try {
        before = await $.fs.read(e.file_path)
      } catch {
        before = undefined
      }
      step = stepFrom('Write', e.file_path, before === undefined ? 'Write, new file' : 'Write, over existing file', before ?? '', e.content)
    } catch {
      step = undefined
    }
    const ran = await next(e)
    if (step !== undefined && ran.deny === undefined && ran.isError !== true) {
      const s = step
      await update($, pending, list => [...list, s].slice(-config.maxSteps))
    }
    return ran
  })

  on('turn.start', async ($, e, next) => {
    await update($, pending, () => [])
    await update($, isHintShown, () => false)
    return next(e)
  })

  on('turn.complete', async ($, e, next) => {
    const r = await next(e)
    if (e.agentId === undefined) {
      const steps = await read($, pending)
      if (steps.length > 0) {
        await update($, replay, () => steps)
        await update($, index, () => 0)
        await update($, pending, () => [])
        await update($, isHintShown, () => true)
      }
    }
    return r
  })

  on('session.start', async ($, e, next) => {
    const r = await next(e)
    await $.command.register({ name: 'replay', description: 'Step through the last turn\'s file edits' })
    return r
  })

  on('command.run', { command: 'replay' }, async $ => {
    const steps = await read($, replay)
    if (steps.length === 0) return { text: 'No edits in the last turn' }
    await showReplay($)
    return { text: `Replaying ${steps.length} edits` }
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const steps = await read($, replay)
    const isQuiet = e.props.hasSurvey || steps.length === 0 || !(await read($, isHintShown))
    if (isQuiet) return next(e)

    const files = new Set(steps.map(s => s.path)).size
    const { Box, Button, Text } = $.ui.resolve(e)
    return (
      <Box>
        <Text dimColor>
          Replay: {steps.length} edits in {files} files{' '}
        </Text>
        <Button key="replay" label="Replay" hotkey="r" onPress={() => showReplay($)} />
        <Button key="dismiss" label="Dismiss" onPress={() => update($, isHintShown, () => false)} />
      </Box>
    )
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Button, Text } = $.ui.resolve(e)
    const steps = await read($, replay)
    const at = Math.min(Math.max(0, await read($, index)), Math.max(0, steps.length - 1))
    const step = steps[at]

    if (step === undefined) {
      return <Text dimColor>No edits in the last turn.</Text>
    }

    return (
      <Box flexDirection="column">
        <Box>
          {steps.map((_, i) => (
            <Text key={`n${i}`} bold={i === at} dimColor={i !== at}>
              {i === at ? `[${i + 1}]` : ` ${i + 1} `}
            </Text>
          ))}
        </Box>
        <Text bold>
          Step {at + 1} of {steps.length}: {step.path}
        </Text>
        <Text dimColor>
          {step.label}, +{step.added} -{step.removed}
        </Text>
        {step.lines.map((line, i) => (
          <Text
            key={`l${i}`}
            color={line.kind === 'add' ? 'green' : line.kind === 'del' ? 'red' : undefined}
            dimColor={line.kind === 'ctx' || line.kind === 'note'}
          >
            {prefixOf(line)}
            {line.text}
          </Text>
        ))}
        {step.more > 0 && <Text dimColor>{step.more} more lines</Text>}
        <Box>
          <Button key="prev" label="Prev" hotkey="p" onPress={() => update($, index, i => Math.max(0, i - 1))} />
          <Button key="next" label="Next" hotkey="n" onPress={() => update($, index, i => Math.min(steps.length - 1, i + 1))} />
          <Button key="close" label="Close" hotkey="c" onPress={() => $.ui.close({ id: PANE })} />
        </Box>
      </Box>
    )
  })
}
