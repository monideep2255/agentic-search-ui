import { test, expect } from 'claude-code/testing'

const SK = 'sk' + '-'
const random24 = 'Zk3Qm9Lp2Rt5Vw8Xc4Jn7Hb6'
const fake = ($: any, on: any) => on('tool.call', () => ({ result: 'ran' }) as never)

async function deny($: any, path: string, content: string) {
  const r = await $.tool.call({ tool: 'Write', file_path: path, content })
  return r.deny as string | undefined
}

test('shape matches that are placeholders pass', async ($, on) => {
  fake($, on)
  const texts = [
    'key ' + SK + 'x'.repeat(24),
    'key ' + SK + 'X'.repeat(24),
    'key ' + SK + 'test-' + 'a1b2c3'.repeat(4),
    'key ' + SK + 'dummy-' + 'a1b2c3'.repeat(4),
    'key ' + SK + 'fake' + 'a1b2c3'.repeat(4),
    'key ' + SK + 'fixture-' + 'a1b2c3'.repeat(4),
    'key ' + SK + 'sample-' + 'a1b2c3'.repeat(4),
    'key ' + SK + 'placeholder-' + 'a1b2c3'.repeat(4),
    'key ' + SK + 'redacted-' + 'a1b2c3'.repeat(4),
    'key ' + SK + 'example-' + 'a1b2c3'.repeat(4),
    'key ' + SK + 'changeme-' + 'a1b2c3'.repeat(4),
    'key ' + SK + 'change-me-' + 'a1b2c3'.repeat(4),
    'key ' + SK + 'replace-with-' + 'a1b2c3'.repeat(4),
    'key ' + SK + 'your_' + 'a1b2c3'.repeat(4),
    'key ' + SK + 'your-' + 'a1b2c3'.repeat(4),
    'key ' + SK + '<' + 'the-key-goes-here-ok>',
    'key ' + SK + '${' + 'THE_KEY_VALUE_HERE}',
    'key ' + SK + 'a1b2c3'.repeat(4) + '...',
    'id ' + 'AKI' + 'A' + 'X'.repeat(16),
  ]
  for (const t of texts) expect(await deny($, 'docs/a.md', t)).toBeUndefined()
})

test('field values with widened placeholders pass', async ($, on) => {
  fake($, on)
  const texts = [
    '"token": "fixture-token-for-tests-only"',
    'TOKEN = "replace-with-your-token"',
    'token = "your-token-goes-here"',
    'secret = "change-me-please-now"',
    'password = "sample-password-value"',
    'auth = "dummy-auth-value-1234"',
    'token = "redacted-redacted-1"',
    'token = "placeholder-token-1"',
    'token = "abcdefghijkl' + '..."',
  ]
  for (const t of texts) expect(await deny($, 'a.json', t)).toBeUndefined()
})

test('prose that names a prefix without a value passes', async ($, on) => {
  fake($, on)
  const slack = 'xo' + 'xb-'
  const pem = '-----BEGIN ' + 'PRIVATE KEY-----'
  expect(await deny($, 'a.txt', 'Bot tokens start with the ' + slack + ' prefix.')).toBeUndefined()
  expect(await deny($, 'a.txt', 'a short one like ' + slack + '1234 is prose')).toBeUndefined()
  expect(await deny($, 'a.txt', 'a PEM header looks like `' + pem + '` in a file')).toBeUndefined()
  expect(await deny($, 'docs/keys.md', 'a header looks like ' + pem + '\nand more prose')).toBeUndefined()
  expect(await deny($, 'docs/keys.md', pem)).toBeUndefined()
})

test('a real PEM block still denies', async ($, on) => {
  fake($, on)
  const block = '-----BEGIN ' + 'RSA PRIVATE KEY-----\n' + 'MIIEowIBAAKCAQEA'.repeat(4) + '\n-----END ' + 'RSA PRIVATE KEY-----'
  expect(await deny($, 'docs/keys.md', block)).toContain('PEM')
  expect(await deny($, 'keys.pem', block)).toContain('PEM')
  expect(await deny($, 'keys.pem', block.split('\n')[0])).toContain('PEM')
})

test('a long Slack-shaped token still denies', async ($, on) => {
  fake($, on)
  expect(await deny($, 'a.md', 'xo' + 'xb-' + '123456789012-abcdefABCDEF')).toContain('Slack')
})

test('test passwords in test files pass, real ones deny', async ($, on) => {
  fake($, on)
  const pw = (v: string) => "password='" + v + "'"
  expect(await deny($, 'tests/test_users.py', pw('testpass' + 'word123'))).toBeUndefined()
  expect(await deny($, 'app/tests/test_users.py', pw('Zk3Qm9' + 'Lp2Rt5Vw'))).toBeUndefined()
  expect(await deny($, 'app/tests/test_users.py', pw(random24))).toContain('field')
  expect(await deny($, 'app/settings.py', pw('Zk3Qm9' + 'Lp2Rt5Vw'))).toContain('field')
})

test('real-looking random secrets still deny', async ($, on) => {
  fake($, on)
  expect(await deny($, 'a.md', 'k ' + SK + random24)).toContain('sk-')
  expect(await deny($, 'a.md', 'k gh' + 'p_' + random24 + 'Hb6GdFs1Ae0Yu9')).toContain('GitHub')
})
