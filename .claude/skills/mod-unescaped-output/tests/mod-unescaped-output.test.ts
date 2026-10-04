import { test, expect } from 'claude-code/testing'

type World = { toasts: string[]; denied?: boolean; disk: Record<string, string> }

function fake(on: any, w: World) {
  on('tool.call', () => (w.denied ? { deny: 'no' } : { result: 'ok' }) as never)
  on('session.repo', () => ({ value: { root: '/repo', remote: null, internal: false } }))
  on('fs.read', (_: unknown, e: { path: string }) => ({ value: w.disk[e.path] ?? '' }))
  on('ui.toast', (_: unknown, e: { text: string }) => { w.toasts.push(e.text); return { value: undefined } })
}
const world = (disk: Record<string, string> = {}): World => ({ toasts: [], disk })
const TSX = '/repo/frontend/src/components/New.tsx'
const edit = ($: any, file: string, new_string: string, old_string = 'x') => $.tool.call({ tool: 'Edit', file_path: file, old_string, new_string })
const write = ($: any, file: string, content: string) => $.tool.call({ tool: 'Write', file_path: file, content })

const frontendCases: [string, string, string][] = [
  ['dangerouslySetInnerHTML', '<div dangerouslySetInnerHTML={{ __html: h }} />', 'dangerouslySetInnerHTML'],
  ['innerHTML', 'el.innerHTML = html', '.innerHTML'],
  ['outerHTML', 'el.outerHTML = html', 'outerHTML'],
  ['document.write', 'document.write(markup)', 'document.write('],
  ['location.href from a variable', 'location.href = next', 'redirect'],
  ['window.location from a template', 'window.location = `/a/${id}`', 'redirect'],
  ['window.open with a variable', 'window.open(url)', 'window.open'],
  ['target blank without rel', '<a href={u} target="_blank">x</a>', 'rel containing noopener'],
  ['target blank with an unrelated rel', '<a target="_blank" rel="nofollow" href={u}>x</a>', 'rel containing noopener'],
]
for (const [name, text, expected] of frontendCases) {
  test(`frontend: ${name} warns`, async ($, on) => {
    const w = world(); fake(on, w)
    const r = await edit($, TSX, text)
    expect(r.deny).toBeUndefined()
    expect(w.toasts.length).toBe(1)
    expect(w.toasts[0]).toContain(expected)
  })
}

const frontendPass: [string, string][] = [
  ['rel noopener on the next line', '<a\n  target="_blank"\n  rel="noopener noreferrer"\n  href={u}\n>x</a>'],
  ['literal location', "window.location = '/home'"],
  ['literal window.open', "window.open('https://example.org')"],
  ['a location comparison', 'if (location.href == x) {}'],
  ['reading the pathname', 'const p = window.location.pathname'],
  ['a comment naming the pattern', '// never use dangerouslySetInnerHTML here'],
]
for (const [name, text] of frontendPass) {
  test(`frontend: ${name} is silent`, async ($, on) => {
    const w = world(); fake(on, w)
    await edit($, TSX, text)
    expect(w.toasts).toEqual([])
  })
}

const pythonPath = '/repo/src/system_03_search_agent/store.py'
const pythonCases: [string, string][] = [
  ['f-string SQL', 'cur.execute(f"SELECT id FROM users WHERE id = {uid}")'],
  ['percent SQL', 'q = "DELETE FROM runs WHERE id = %s" % run_id'],
  ['format SQL', 'q = "UPDATE runs SET state = {}".format(s)'],
  ['concatenated execute', 'cur.execute("SELECT * FROM t WHERE a = " + a)'],
]
for (const [name, text] of pythonCases) {
  test(`python: ${name} warns`, async ($, on) => {
    const w = world(); fake(on, w)
    await edit($, pythonPath, text)
    expect(w.toasts.length).toBe(1)
  })
}

test('python: parameterized SQL is silent', async ($, on) => {
  const w = world(); fake(on, w)
  await edit($, pythonPath, 'cur.execute("SELECT id FROM users WHERE id = %s", (uid,))')
  await edit($, pythonPath, 'session.execute(select(User).where(User.id == uid))')
  expect(w.toasts).toEqual([])
})

test('a file outside the watched folders is ignored', async ($, on) => {
  const w = world(); fake(on, w)
  await edit($, '/repo/tests/test_a.py', 'cur.execute(f"SELECT a FROM t WHERE a = {x}")')
  await edit($, '/repo/frontend/e2e/a.ts', 'el.innerHTML = x')
  await edit($, '/repo/frontend/src/notes.md', 'el.innerHTML = x')
  expect(w.toasts).toEqual([])
})

test('an allowlisted file: the existing line is silent, a new line warns', async ($, on) => {
  const file = '/repo/frontend/src/components/screens/InfoScreens.tsx'
  const old = '<a target="_blank" href={u}>old</a>'
  const w = world({ [file]: old + '\n<p>rest</p>' }); fake(on, w)
  await edit($, file, old + '\n<p>changed</p>', old)
  expect(w.toasts).toEqual([])
  await edit($, file, '<a target="_blank" href={v}>new</a>', '<p>rest</p>')
  expect(w.toasts.length).toBe(1)
})

test('a Write that keeps an audited line stays silent and a new bad line warns', async ($, on) => {
  const file = '/repo/frontend/src/lib/routing.ts'
  const w = world({ [file]: 'window.location = target' }); fake(on, w)
  await write($, file, 'window.location = target\nconst a = 1')
  expect(w.toasts).toEqual([])
  await write($, file, 'window.location = target\nel.innerHTML = h')
  expect(w.toasts.length).toBe(1)
})

test('at most three findings toast, and the edit is never denied', async ($, on) => {
  const w = world(); fake(on, w)
  const r = await edit($, TSX, 'a.innerHTML = 1\nb.innerHTML = 2\nc.innerHTML = 3\nd.innerHTML = 4')
  expect(r.deny).toBeUndefined()
  expect(w.toasts.length).toBe(3)
})

test('a denied edit is not scanned', async ($, on) => {
  const w = world(); w.denied = true; fake(on, w)
  await edit($, TSX, 'el.innerHTML = x')
  expect(w.toasts).toEqual([])
})
