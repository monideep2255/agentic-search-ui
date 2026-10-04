import type { Register } from 'claude-code'
import { config } from './config.ts'

type ModInfo = { folder: string; name: string; trigger: string; what: string; description: string; unreadable: boolean }

const SKILLS = '/.claude/skills'

// Split "What it does. Trigger: Auto" into its two parts.
function splitDescription(description: string): { trigger: string; what: string } {
  const m = description.match(/^(.*?)\s*Trigger:\s*(.+)$/s)
  if (!m) return { trigger: 'unknown', what: description.trim() }
  return { trigger: m[2].trim(), what: m[1].trim() }
}

// Reads every folder under .claude/skills that holds a plugin manifest.
// Never rejects: a broken listing or manifest degrades to fewer or "unreadable" rows.
async function scan($: EngineInterface): Promise<ModInfo[]> {
  const repo = await $.session.repo().catch(() => null)
  const root = repo?.root ?? (await $.session.cwd())
  const dir = root + SKILLS
  let entries: { name: string; kind: string }[] = []
  try {
    entries = await $.fs.list(dir)
  } catch {
    return []
  }
  const found: ModInfo[] = []
  for (const entry of entries) {
    if (entry.kind === 'file') continue
    const manifest = `${dir}/${entry.name}/.claude-plugin/plugin.json`
    let text: string
    try {
      if (!(await $.fs.exists(manifest))) continue
      const read = await $.fs.read(manifest)
      if (typeof read !== 'string') continue
      text = read
    } catch {
      continue
    }
    try {
      const parsed = JSON.parse(text) as { name?: unknown; description?: unknown }
      const name = typeof parsed.name === 'string' && parsed.name ? parsed.name : entry.name
      const description = typeof parsed.description === 'string' ? parsed.description : ''
      const { trigger, what } = splitDescription(description)
      found.push({ folder: entry.name, name, trigger, what, description, unreadable: false })
    } catch {
      found.push({ folder: entry.name, name: entry.name, trigger: 'unknown', what: 'unreadable manifest', description: 'unreadable manifest', unreadable: true })
    }
  }
  return found.sort((a, b) => a.folder.localeCompare(b.folder))
}

// Names of plugins that registered a slash command. A mod with no command cannot be seen this way.
async function pluginsWithCommands($: EngineInterface): Promise<Set<string>> {
  const names = new Set<string>()
  try {
    for (const c of await $.command.list()) {
      if (c.plugin) names.add(c.plugin.split('@')[0])
    }
  } catch {
    // leave the set empty
  }
  return names
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'mods', description: 'List the mods installed in this repository', argumentHint: '[mod-name]' })
    const result = await next(e)

    const mods = await scan($)
    for (const m of mods) {
      if (!m.folder.startsWith('mod-')) {
        $.ui.toast(`Unknown plugin auto-loaded from .claude/skills/${m.folder}. Check it before trusting it.`)
      }
    }

    const today = new Date(await $.clock.now()).toISOString().slice(0, 10)
    const last = await $.store.get('lastToastDate')
    if (last !== today) {
      await $.store.set('lastToastDate', today)
      const count = mods.filter(m => m.folder.startsWith('mod-')).length
      $.ui.toast(`${count} mods loaded. Type /mods to see them.`)
    }
    return result
  })

  on('command.run', { command: 'mods' }, async ($, e, next) => {
    const mods = await scan($)
    const wanted = e.args.trim()

    if (wanted) {
      const m = mods.find(x => x.name === wanted || x.folder === wanted)
      if (!m) return { text: `mod-help: no mod named ${wanted} is installed here. Type /mods for the list.` }
      return { text: `${m.name}\nTrigger: ${m.trigger}\n${m.unreadable ? m.description : m.what}` }
    }

    const loaded = await pluginsWithCommands($)
    const lines = [
      'Installed mods (read live from .claude/skills). Loaded is detected only for mods that register a slash command.',
      '',
      'Name | Trigger | Loaded | What it does',
      '--- | --- | --- | ---',
    ]
    for (const m of mods) {
      const state = loaded.has(m.name) || m.name === $.plugin.name ? 'loaded' : 'not seen'
      lines.push(`${m.name} | ${m.trigger} | ${state} | ${m.what}`)
    }
    if (mods.length === 0) lines.push('(none found)')
    lines.push('', `Guide: ${config.guidePath}`)
    lines.push('Turn one off: set "<name>@skills-dir": false under enabledPlugins in .claude/settings.local.json')
    return { text: lines.join('\n') }
  })
}
