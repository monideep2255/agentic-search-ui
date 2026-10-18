// Per-repository settings for mod-secrets-scan.
// extraPatterns: additional shapes, each a name plus a regular expression source.
// allowPaths: globs of files that legitimately hold placeholder shapes.
export const config: {
  extraPatterns: { name: string; source: string }[]
  allowPaths: string[]
} = {
  extraPatterns: [],
  allowPaths: [
    '**/tests/fixtures/**',
    'tests/fixtures/**',
    '**/test_fixtures/**',
    'test_fixtures/**',
    '**/tests/system_03_search_agent/fixtures/**',
    '**/tests/system_03_search_agent/tools/fixtures/**',
    '**/tests/system_03_search_agent/eval/fixtures/**',
  ],
}
