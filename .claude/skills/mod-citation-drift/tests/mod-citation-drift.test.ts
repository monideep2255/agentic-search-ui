import { test, expect } from 'claude-code/testing'

const FRONT = 'frontend/src/components/answer/CitationMarkers.tsx'
const SPEC = 'frontend/e2e/citation-host-allowlist.spec.ts'
const EVENTS = 'src/system_03_search_agent/contracts/events.py'
const CT = 'src/system_03_search_agent/tools/clinicaltrials_search_schemas.py'

const frontend = (hosts: string[]) => `const ALLOWED_CITATION_HOSTS = [\n${hosts.map(h => `  "${h}",`).join('\n')}\n];\n`
const spec = (hosts: string[]) => `/**\n * allowed hosts (${hosts.map(h => '`' + h + '`').join(', ')}).\n */\nimport x from 'y'\n`
const events = (extra = '') =>
  'NCBI_SOURCE_URL_PATTERN = (\n' +
  '    r"^https://(?:([A-Za-z0-9-]+\\.)*ncbi\\.nlm\\.nih\\.gov/"\n' +
  '    r"|(?:www\\.)?clinicaltrials\\.gov/study/"\n' +
  extra +
  '    + _URL_REMAINDER_CHARS\n' +
  '    + r"*$"\n' +
  ')\n'
const ct = 'CLINICALTRIALS_HOST: Final = r"^https://(www\\.)?clinicaltrials\\.gov/study/"\n'

const GOOD = ['ncbi.nlm.nih.gov', 'www.ncbi.nlm.nih.gov', 'pubmed.ncbi.nlm.nih.gov', 'clinicaltrials.gov', 'www.clinicaltrials.gov']

function fake(on: any, files: Record<string, string>, toasts: string[]) {
  on('session.repo', () => ({ value: { root: '/repo', remote: null, internal: false } }))
  on('fs.read', (_: unknown, e: { path: string }) => {
    const rel = e.path.replace('/repo/', '')
    if (!(rel in files)) throw new Error('missing')
    return { value: files[rel] }
  })
  on('ui.toast', (_: unknown, e: { text: string }) => { toasts.push(e.text); return { value: undefined } })
  on('tool.call', () => ({ result: 'ran' }) as never)
}

const base = () => ({ [FRONT]: frontend(GOOD), [SPEC]: spec(GOOD), [EVENTS]: events(), [CT]: ct })

test('identical host sets stay silent', async ($, on) => {
  const toasts: string[] = []
  fake(on, base(), toasts)
  await $.tool.call({ tool: 'Edit', file_path: '/repo/' + FRONT, old_string: 'a', new_string: 'b' })
  expect(toasts).toEqual([])
})

test('one extra host in the frontend list toasts', async ($, on) => {
  const toasts: string[] = []
  fake(on, { ...base(), [FRONT]: frontend([...GOOD, 'evil.example.org']) }, toasts)
  await $.tool.call({ tool: 'Write', file_path: '/repo/' + FRONT, content: 'x' })
  expect(toasts.length).toBe(1)
  expect(toasts[0]).toContain('citation hosts drift: evil.example.org in ' + FRONT + ' only')
})

test('a host the pattern names but the lists lack toasts', async ($, on) => {
  const toasts: string[] = []
  fake(on, { ...base(), [EVENTS]: events('    r"|(?:www\\.)?omim\\.org/"\n') }, toasts)
  await $.tool.call({ tool: 'Edit', file_path: '/repo/' + EVENTS, old_string: 'a', new_string: 'b' })
  expect(toasts[0]).toContain('omim.org in ' + EVENTS + ' only')
})

test('a list host missing from the spec toasts', async ($, on) => {
  const toasts: string[] = []
  fake(on, { ...base(), [SPEC]: spec(GOOD.filter(h => h !== 'pubmed.ncbi.nlm.nih.gov')) }, toasts)
  await $.tool.call({ tool: 'Edit', file_path: '/repo/' + SPEC, old_string: 'a', new_string: 'b' })
  expect(toasts[0]).toContain('pubmed.ncbi.nlm.nih.gov in ' + FRONT + ' only')
})

test('a file that is not watched is ignored even when sets differ', async ($, on) => {
  const toasts: string[] = []
  fake(on, { ...base(), [FRONT]: frontend([...GOOD, 'evil.example.org']) }, toasts)
  await $.tool.call({ tool: 'Edit', file_path: '/repo/src/other/module.py', old_string: 'a', new_string: 'b' })
  expect(toasts).toEqual([])
})

test('a file outside the repository is ignored', async ($, on) => {
  const toasts: string[] = []
  fake(on, { ...base(), [FRONT]: frontend([...GOOD, 'evil.example.org']) }, toasts)
  await $.tool.call({ tool: 'Edit', file_path: '/elsewhere/' + FRONT, old_string: 'a', new_string: 'b' })
  expect(toasts).toEqual([])
})

test('a declaration that moved is reported, not treated as agreement', async ($, on) => {
  const toasts: string[] = []
  fake(on, { ...base(), [FRONT]: 'const renamed = []' }, toasts)
  await $.tool.call({ tool: 'Edit', file_path: '/repo/' + FRONT, old_string: 'a', new_string: 'b' })
  expect(toasts.some(t => t.includes('found no hosts in ' + FRONT))).toBe(true)
})

test('an unreadable source never breaks the edit', async ($, on) => {
  const toasts: string[] = []
  const files: Record<string, string> = base()
  delete files[SPEC]
  fake(on, files, toasts)
  const r = await $.tool.call({ tool: 'Edit', file_path: '/repo/' + FRONT, old_string: 'a', new_string: 'b' })
  expect(r.deny).toBeUndefined()
  expect(toasts).toEqual([])
})
