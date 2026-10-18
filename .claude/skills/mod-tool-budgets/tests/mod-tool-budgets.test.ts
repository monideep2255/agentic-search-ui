import { test, expect } from 'claude-code/testing'

const RULE = '.claude/rules/tool-call-budgets.md'
const T = 'src/system_03_search_agent/tools/'
const TABLE = [
  '| Tool | Timeout | Rate-limit pool |',
  '|------|---------|-------------------|',
  '| cypher_query | 30 seconds per call (Section 6.1) | Not rate-limited |',
  '| ncbi_efetch | 15 seconds per call, one backoff retry (Section 6.2) | E-utilities |',
  '| ncbi_dbsnp | 15 seconds per call, up to 30 seconds worst case (Section 6.3) | Variation |',
  '| pathogen_detection | 60 seconds or more, a bulk transfer (Section 6.6) | Not a request-rate API |',
  '| litvar2_lookup | 15 seconds per call, provisional until confirmed (Section 6.5) | None |',
].join('\n')

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

const TRANSPORT = 'DEFAULT_TIMEOUT_S: Final[float] = 15.0\n'
const edit = ($: any, rel: string) => $.tool.call({ tool: 'Edit', file_path: '/repo/' + rel, old_string: 'a', new_string: 'b' })

test('a tool with no declared timeout toasts', async ($, on) => {
  const toasts: string[] = []
  fake(on, { [RULE]: TABLE, [T + 'litvar2_lookup.py']: 'def run():\n    pass\n' }, toasts)
  await edit($, T + 'litvar2_lookup.py')
  expect(toasts[0]).toContain('litvar2_lookup has no declared timeout')
  expect(toasts[0]).toContain('not finished')
})

test('an own constant that matches the table is silent', async ($, on) => {
  const toasts: string[] = []
  fake(on, { [RULE]: TABLE, [T + 'ncbi_efetch.py']: 'EFETCH_TIMEOUT_S: Final[float] = 15.0\n' }, toasts)
  await edit($, T + 'ncbi_efetch.py')
  expect(toasts).toEqual([])
})

test('a differing own constant toasts both numbers', async ($, on) => {
  const toasts: string[] = []
  fake(on, { [RULE]: TABLE, [T + 'ncbi_efetch.py']: 'EFETCH_TIMEOUT_S = 20\n' }, toasts)
  await edit($, T + 'ncbi_efetch.py')
  expect(toasts[0]).toContain('ncbi_efetch declares 20s but the rule\'s table says 15s')
})

test('a differing value on an unsettled row is informational', async ($, on) => {
  const toasts: string[] = []
  fake(on, { [RULE]: TABLE, [T + 'litvar2_lookup.py']: 'LITVAR_TIMEOUT_S = 25.0\n' }, toasts)
  await edit($, T + 'litvar2_lookup.py')
  expect(toasts[0]).toContain('(informational)')
  expect(toasts[0]).toContain('marked unsettled')
  expect(toasts[0]).not.toContain('table says')
})

test('a tool using the shared transport inherits its default', async ($, on) => {
  const toasts: string[] = []
  fake(on, { [RULE]: TABLE, [T + 'ncbi_transport.py']: TRANSPORT, [T + 'ncbi_dbsnp.py']: 'from x import ncbi_transport\nncbi_transport.execute_get()\n' }, toasts)
  await edit($, T + 'ncbi_dbsnp.py')
  expect(toasts).toEqual([])
})

test('an imported constant resolves through the constants file', async ($, on) => {
  const toasts: string[] = []
  fake(on, {
    [RULE]: TABLE,
    [T + 'graph_schema_constants.py']: 'CYPHER_QUERY_TIMEOUT_SECONDS: Final[float] = 45.0\n',
    [T + 'cypher_query.py']: 'from .graph_schema_constants import CYPHER_QUERY_TIMEOUT_SECONDS\n',
  }, toasts)
  await edit($, T + 'cypher_query.py')
  expect(toasts[0]).toContain('cypher_query declares 45s but the rule\'s table says 30s')
})

test('a floor in the table accepts a larger declared value', async ($, on) => {
  const toasts: string[] = []
  fake(on, { [RULE]: TABLE, [T + 'pathogen_detection.py']: '_TOTAL_BUDGET_S: Final[float] = 120.0\n_ISOLATE_LOOKUP_ENRICHMENT_BUDGET_S = 20.0\n' }, toasts)
  await edit($, T + 'pathogen_detection.py')
  expect(toasts).toEqual([])
})

test('a file the table does not know is ignored', async ($, on) => {
  const toasts: string[] = []
  fake(on, { [RULE]: TABLE, [T + 'schema_slice.py']: 'x = 1\n' }, toasts)
  await edit($, T + 'schema_slice.py')
  expect(toasts).toEqual([])
})

test('a path outside the watched globs is ignored', async ($, on) => {
  const toasts: string[] = []
  fake(on, { [RULE]: TABLE, ['src/other/litvar2_lookup.py']: 'x = 1\n' }, toasts)
  await edit($, 'src/other/litvar2_lookup.py')
  expect(toasts).toEqual([])
})

test('editing the budget module rechecks every tool in the table', async ($, on) => {
  const toasts: string[] = []
  fake(on, { [RULE]: TABLE, [T + 'ncbi_efetch.py']: 'x = 1\n' }, toasts)
  await edit($, 'src/system_03_search_agent/harness/call_budget.py')
  expect(toasts[0]).toContain('ncbi_efetch has no declared timeout')
})

test('a missing rule file stays quiet and lets the edit through', async ($, on) => {
  const toasts: string[] = []
  fake(on, { [T + 'ncbi_efetch.py']: 'x = 1\n' }, toasts)
  const r = await edit($, T + 'ncbi_efetch.py')
  expect(r.deny).toBeUndefined()
  expect(toasts).toEqual([])
})
