import { test, expect } from 'claude-code/testing'

const A = '/repo/src/system_03_search_agent/adapters/web_sse/app.py'

type Run = { argv: string[] }

// grep answers: `routeFiles` maps a path fragment to the files that mention it, `names` lists test names.
function fake(on: any, toasts: string[], routeFiles: Record<string, string[]>, names: string[], run?: (e: Run) => unknown) {
  on('session.repo', () => ({ value: { root: '/repo', remote: null, internal: false } }))
  on('ui.toast', (_: unknown, e: { text: string }) => { toasts.push(e.text); return { value: undefined } })
  on('tool.call', () => ({ result: 'ran' }) as never)
  on('turn.complete', () => ({ text: '' }) as never)
  on('process.run', (_: unknown, e: Run) => {
    if (run) return run(e)
    const argv = e.argv
    const ok = (stdout: string, exitCode = 0) => ({ value: { exitCode, stdout, stderr: '', isStdoutTruncated: false, isStderrTruncated: false } })
    if (argv.includes('-rlE')) {
      const pattern = argv[argv.indexOf('-rlE') + 1]
      const hit = Object.keys(routeFiles).find(k => pattern.includes(k))
      return hit ? ok(routeFiles[hit].join('\n') + '\n') : ok('', 1)
    }
    return ok(names.map(n => 'def ' + n).join('\n') + '\n')
  })
}

const done = ($: any, agentId?: string) =>
  $.turn.complete({ answer: '', durationMs: 1, isAborted: false, turnId: 't1', reason: 'end_turn', ...(agentId ? { agentId } : {}) } as never)

const addRoute = ($: any, text: string) => $.tool.call({ tool: 'Edit', file_path: A, old_string: 'x', new_string: text })

test('a route without an invalid test toasts', async ($, on) => {
  const toasts: string[] = []
  fake(on, toasts, { '/v1/widgets': ['tests/test_widgets.py'] }, ['test_widgets_valid_request', 'test_widgets_missing_field'])
  await addRoute($, '@app.post("/v1/widgets")\nasync def make(): ...')
  await done($)
  expect(toasts.length).toBe(1)
  expect(toasts[0]).toContain('route /v1/widgets: no invalid-input test found')
  expect(toasts[0]).toContain('name-based heuristic')
})

test('a fully covered route is silent', async ($, on) => {
  const toasts: string[] = []
  fake(on, toasts, { '/v1/widgets': ['tests/test_widgets.py'] }, ['test_valid_widget', 'test_invalid_widget_rejected', 'test_empty_body'])
  await addRoute($, '@router.get("/v1/widgets")\n')
  await done($)
  expect(toasts).toEqual([])
})

test('a route no test mentions toasts', async ($, on) => {
  const toasts: string[] = []
  fake(on, toasts, {}, [])
  await addRoute($, '@app.get("/v1/ghost/{ghost_id}")\n')
  await done($)
  expect(toasts[0]).toContain('route /v1/ghost/{ghost_id}: no test file mentions it')
})

test('a path parameter becomes a wildcard in the search', async ($, on) => {
  const seen: string[] = []
  fake(on, [], {}, [], e => {
    seen.push(e.argv.join(' '))
    return { value: { exitCode: 1, stdout: '', stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
  })
  await addRoute($, '@app.get("/v1/run/{run_id}/events")\n')
  await done($)
  expect(seen[0]).toContain('grep -rlE /v1/run/.*/events tests')
})

test('a subagent turn is ignored and keeps the main turn list', async ($, on) => {
  const toasts: string[] = []
  fake(on, toasts, {}, [])
  await addRoute($, '@app.get("/v1/ghost")\n')
  await done($, 'agent-7')
  expect(toasts).toEqual([])
  await done($)
  expect(toasts.length).toBe(1)
})

test('an edit with no route decorator is silent', async ($, on) => {
  const toasts: string[] = []
  fake(on, toasts, {}, [])
  await addRoute($, 'def helper():\n    return 1\n')
  await done($)
  expect(toasts).toEqual([])
})

test('an edit outside the adapter folder is ignored', async ($, on) => {
  const toasts: string[] = []
  fake(on, toasts, {}, [])
  await $.tool.call({ tool: 'Edit', file_path: '/repo/src/system_03_search_agent/core/other.py', old_string: 'x', new_string: '@app.get("/v1/ghost")' })
  await done($)
  expect(toasts).toEqual([])
})

test('a failed search stays quiet', async ($, on) => {
  const toasts: string[] = []
  fake(on, toasts, {}, [], () => { throw new Error('boom') })
  await addRoute($, '@app.get("/v1/ghost")\n')
  await done($)
  expect(toasts).toEqual([])
})
