import type { EngineInterface, Register } from 'claude-code'
import { config } from './config.ts'

type Item = { name: string; tokens: number }
type Reading = { total: number; items: Item[] }

// Standing categories only: memory files, skills listing, custom agents, MCP tools.
// Messages, free space, the buffer and the system prompt are not standing instruction cost.
// Returns undefined when no breakdown exists. Never rejects.
async function measure($: EngineInterface): Promise<Reading | undefined> {
  try {
    const usage = await $.session.usage({ breakdown: 'summary' })
    const b = usage?.context?.breakdown
    if (!b) return undefined
    const items: Item[] = []
    for (const f of b.memoryFiles ?? []) items.push({ name: f.path, tokens: f.tokens })
    if (b.skills && b.skills.tokens > 0) items.push({ name: 'Skills listing', tokens: b.skills.tokens })
    const agentTokens = (b.agents ?? []).reduce((sum, a) => sum + a.tokens, 0)
    if (agentTokens > 0) items.push({ name: 'Custom agents', tokens: agentTokens })
    const servers = new Map<string, number>()
    for (const t of b.mcpTools ?? []) {
      if (t.isLoaded) servers.set(t.serverName, (servers.get(t.serverName) ?? 0) + t.tokens)
    }
    for (const [server, tokens] of servers) items.push({ name: `MCP tools: ${server}`, tokens })
    items.sort((x, y) => y.tokens - x.tokens)
    return { total: items.reduce((sum, i) => sum + i.tokens, 0), items }
  } catch {
    return undefined
  }
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'context-budget', description: 'List the standing context by file and category against the budget' })
    const result = await next(e)

    const reading = await measure($)
    if (!reading) return result
    await $.store.set('lastReading', { total: reading.total, items: reading.items.slice(0, 40) })

    let previous: number | undefined
    try {
      const prior = (await $.store.get('lastTotal')) as number | undefined
      if (typeof prior === 'number' && prior > 0) previous = prior
      await $.store.set('lastTotal', reading.total)
    } catch {
      // growth tracking is best effort
    }

    const { total } = reading
    const budget = config.budgetTokens
    let note = ''
    if (previous !== undefined) {
      const growth = ((total - previous) / previous) * 100
      if (growth > config.growthAlertPercent) note = ` Grew ${Math.round(growth)}% since last session.`
    }

    if (total > budget) {
      const top = reading.items
        .slice(0, 3)
        .map(i => `${i.name} (${i.tokens})`)
        .join(', ')
      $.ui.toast(`Standing context ${total} tokens, budget ${budget}. Largest: ${top}.${note} /context-budget for the list.`)
    } else if (note) {
      $.ui.toast(`Standing context ${total} tokens, within budget ${budget}.${note}`)
    }
    $.ui.status(`context: ${total} / ${budget}`)
    return result
  })

  on('command.run', { command: 'context-budget' }, async ($, e, next) => {
    const reading = await measure($)
    if (!reading) return { text: 'mod-context-budget: no context breakdown is available in this session, so nothing was measured.' }
    const lines = ['Tokens | Item', '--- | ---']
    for (const i of reading.items) lines.push(`${i.tokens} | ${i.name}`)
    lines.push(
      '',
      `Total: ${reading.total} tokens`,
      `Budget: ${config.budgetTokens} tokens, set on ${config.budgetSetOn}`,
      'Re-measure: run /context; adjust budgetTokens in .claude/skills/mod-context-budget/hooks/config.ts only with a recorded reason.',
    )
    return { text: lines.join('\n') }
  })
}
