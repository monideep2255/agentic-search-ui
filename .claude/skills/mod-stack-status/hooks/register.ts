import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'
import { config } from './config.ts'

type Probe = 'up' | 'down' | 'unknown'

const everUp = atom({ plugin: 'mod-stack-status', key: 'everUp' } as const, false)

// An http probe that counts a refused connection, an error, or no answer within the timeout as down.
async function probeHttp($: EngineInterface, url: string, needOk: boolean): Promise<Probe> {
  try {
    const answer = await Promise.race([
      $.http.fetch(url),
      $.clock.sleep(config.probeTimeoutMs).then(() => null),
    ])
    if (answer === null) return 'down'
    return needOk ? (answer.ok ? 'up' : 'down') : 'up'
  } catch {
    return 'down'
  }
}

// pg_isready exit codes: 0 accepting, 1 rejecting, 2 no response, 3 no attempt made. A missing binary is unknown.
async function probeDb($: EngineInterface): Promise<Probe> {
  try {
    const r = await $.process.run(['pg_isready', '-h', config.dbHost, '-p', String(config.dbPort)], { timeoutMs: config.probeTimeoutMs })
    if (r.exitCode === 0) return 'up'
    if (r.exitCode === 1 || r.exitCode === 2) return 'down'
    return 'unknown'
  } catch {
    return 'unknown'
  }
}

async function refresh($: EngineInterface): Promise<void> {
  try {
    const [api, web, db] = await Promise.all([
      probeHttp($, `http://localhost:${config.apiPort}${config.apiHealthPath}`, true),
      probeHttp($, `http://localhost:${config.webPort}/`, false),
      probeDb($),
    ])
    const anyUp = api === 'up' || web === 'up' || db === 'up'
    if (anyUp) await update($, everUp, () => true)
    const seen = anyUp || (await read($, everUp))
    if (!seen) {
      $.ui.status(undefined)
      return
    }
    $.ui.status(`stack: api ${api}, web ${web}, db ${db}`)
  } catch {
    // an observer that breaks stays quiet
  }
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const result = await next(e)
    await refresh($)
    $.clock.every(config.pollMs, () => refresh($))
    return result
  })
}
