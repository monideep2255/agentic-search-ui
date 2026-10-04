import { test, expect } from 'claude-code/testing'

const alnum = 'a'.repeat(40)
const hex32 = 'abcdef0123456789'.repeat(2)

const SHAPES: { name: string; text: string }[] = [
  { name: 'sk-', text: 'key ' + 'sk-' + 'a'.repeat(24) },
  { name: 'sk-proj-', text: 'key ' + 'sk-proj-' + 'b'.repeat(24) },
  { name: 'sk-ant-', text: 'key ' + 'sk-ant-' + 'c'.repeat(24) },
  { name: 'sk-or-v1-', text: 'key ' + 'sk-or-v1-' + 'd'.repeat(24) },
  { name: 'ghp_', text: 'x ' + 'ghp' + '_' + alnum },
  { name: 'gho_', text: 'x ' + 'gho' + '_' + alnum },
  { name: 'ghu_', text: 'x ' + 'ghu' + '_' + alnum },
  { name: 'ghs_', text: 'x ' + 'ghs' + '_' + alnum },
  { name: 'github_pat_', text: 'x ' + 'github' + '_pat_' + 'e'.repeat(30) },
  { name: 'AWS', text: 'id ' + 'AKI' + 'A' + 'Q'.repeat(16) },
  { name: 'Slack', text: 't ' + 'xo' + 'xb-' + '1234567890-abcdef' },
  { name: 'PEM', text: '-----BEGIN ' + 'RSA PRIVATE' + ' KEY-----' },
  { name: 'NCBI', text: 'export ' + 'NCBI_API' + '_KEY=' + hex32 },
  { name: 'field token', text: 'const t = {\n  "token": "' + 'q'.repeat(16) + '"\n}' },
  { name: 'field password', text: 'password = "' + 'Zk3'.repeat(5) + '"' },
  { name: 'field api_key', text: "api" + "_key: '" + 'm'.repeat(14) + "'" },
]

const fake = ($: any, on: any) => on('tool.call', () => ({ result: 'ran' }) as never)

for (const s of SHAPES) {
  test(`denies ${s.name} on Bash, Edit and Write`, async ($, on) => {
    fake($, on)
    const b = await $.tool.call({ tool: 'Bash', command: 'echo ' + s.text })
    expect(b.deny).toContain('mod-secrets-scan')
    const e = await $.tool.call({ tool: 'Edit', file_path: 'notes.txt', old_string: 'a', new_string: s.text })
    expect(e.deny).toContain('line')
    const w = await $.tool.call({ tool: 'Write', file_path: 'a.txt', content: s.text })
    expect(w.deny).toContain('line')
  })
}

test('denies on NotebookEdit', async ($, on) => {
  fake($, on)
  const r = await $.tool.call({ tool: 'NotebookEdit', notebook_path: 'n.ipynb', new_source: 'k = "' + 'sk-' + 'a'.repeat(24) + '"' })
  expect(r.deny).toContain('OpenAI-style sk- key')
})

test('placeholders pass', async ($, on) => {
  fake($, on)
  const texts = [
    'token = "<your-token-here>"',
    'password = "${DB_PASSWORD_VALUE}"',
    'api_key = "' + 'x'.repeat(16) + '"',
    'secret = "changeme-please-now"',
    'token = "your_token_goes_here"',
    'auth = "example-value-123456"',
    'task-tracker-some-long-branch-name-here',
    'author = "Some Person Name"',
    'password = short',
    'NCBI_API' + '_KEY=${NCBI_API' + '_KEY}',
  ]
  for (const content of texts) {
    const r = await $.tool.call({ tool: 'Write', file_path: 'a.md', content })
    expect(r.deny).toBeUndefined()
  }
})

test('markdown file paths are scanned', async ($, on) => {
  fake($, on)
  const r = await $.tool.call({ tool: 'Write', file_path: 'docs/README.md', content: 'see ' + 'AKI' + 'A' + 'Z'.repeat(16) })
  expect(r.deny).toContain('AWS access key id')
})

test('the allow comment skips only its own line', async ($, on) => {
  fake($, on)
  const key = 'sk-' + 'a'.repeat(24)
  const ok = await $.tool.call({ tool: 'Write', file_path: 'a.md', content: key + ' secrets-scan: allow' })
  expect(ok.deny).toBeUndefined()
  const bad = await $.tool.call({ tool: 'Write', file_path: 'a.md', content: key + ' secrets-scan: allow\n' + key })
  expect(bad.deny).toContain('line 2')
})

test('allowPaths is empty by default, so no path is skipped', async ($, on) => {
  fake($, on)
  const r = await $.tool.call({ tool: 'Write', file_path: 'fixtures/sample.env', content: 'sk-' + 'a'.repeat(24) })
  expect(r.deny).toBeDefined()
})

test('the deny reason never holds the full value', async ($, on) => {
  fake($, on)
  const value = 'sk-' + 'a'.repeat(24)
  const r = await $.tool.call({ tool: 'Bash', command: 'echo ok\necho ' + value })
  expect(r.deny).toContain('line 2')
  expect(r.deny).toContain('sk-a...')
  expect(r.deny).not.toContain('a'.repeat(10))
})

test('output scanning toasts once per pattern and never denies', async ($, on) => {
  const toasts: string[] = []
  on('ui.toast', (_: unknown, e: { text: string }) => { toasts.push(e.text); return { value: undefined } })
  const leaked = 'line\n' + 'sk-' + 'a'.repeat(24)
  on('tool.call', () => ({ result: 'ran', text: leaked }) as never)
  for (const tool of ['Read', 'WebFetch', 'Bash']) {
    const input = tool === 'Read' ? { tool: 'Read', file_path: 'a.txt' } : tool === 'WebFetch' ? { tool: 'WebFetch', url: 'https://example.org', prompt: 'p' } : { tool: 'Bash', command: 'cat a' }
    const r = await $.tool.call(input as never)
    expect(r.deny).toBeUndefined()
  }
  expect(toasts.length).toBe(1)
  expect(toasts[0]).toContain('secret-shaped text in Read output: OpenAI-style sk- key')
  expect(toasts[0]).not.toContain('a'.repeat(10))
})

test('clean output raises no toast', async ($, on) => {
  const toasts: string[] = []
  on('ui.toast', (_: unknown, e: { text: string }) => { toasts.push(e.text); return { value: undefined } })
  on('tool.call', () => ({ result: 'ran', text: 'nothing here' }) as never)
  const r = await $.tool.call({ tool: 'Read', file_path: 'a.txt' })
  expect(r.deny).toBeUndefined()
  expect(toasts.length).toBe(0)
})

test('a guard that breaks still denies', async ($, on) => {
  on('tool.call', () => { throw new Error('boom') })
  const r = await $.tool.call({ tool: 'Bash', command: 'echo hello' })
  expect(r.deny).toBeDefined()
})
