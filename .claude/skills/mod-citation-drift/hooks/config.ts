// Per-repository settings for mod-citation-drift.
//
// This mod checks that the declared lists of allowed citation hosts agree with
// each other. It does not check whether any answer is grounded or whether any
// citation is true. Agreement of the lists is a necessary condition for the
// cite-or-refuse rule, never a sufficient one.

export type HostSource = {
  // Path relative to the repository root.
  file: string
  // 'list' is an explicit array of hostnames. 'pattern' is a host pinned regular expression.
  kind: 'list' | 'pattern'
  // Capture group 1 is the region of the file that declares the hosts.
  block: RegExp
  // Global. For a list, capture group 1 is one hostname. For a pattern the whole region is parsed instead.
  hosts: RegExp
}

export const config = {
  // An edit to a file matching any of these globs triggers the check.
  watchedPaths: [
    'src/system_03_search_agent/synthesis/**',
    'src/system_03_search_agent/contracts/**',
    'frontend/src/components/answer/**',
    'frontend/e2e/citation-host-allowlist.spec.ts',
  ] as string[],

  sources: [
    {
      // The frontend constant ALLOWED_CITATION_HOSTS, an array of quoted hostnames.
      file: 'frontend/src/components/answer/CitationMarkers.tsx',
      kind: 'list',
      block: /ALLOWED_CITATION_HOSTS\s*=\s*\[([^\]]*)\]/,
      hosts: /["']([A-Za-z0-9.-]+)["']/g,
    },
    {
      // The end to end spec names the allowed hosts in backticks in its header comment.
      file: 'frontend/e2e/citation-host-allowlist.spec.ts',
      kind: 'list',
      block: /^([\s\S]*?)\*\/\s*\n/,
      hosts: /`((?:[A-Za-z0-9-]+\.)+(?:gov|org))`/g,
    },
    {
      // The Python contract: the host pinned source_url regular expression on the citation payload.
      file: 'src/system_03_search_agent/contracts/events.py',
      kind: 'pattern',
      block: /NCBI_SOURCE_URL_PATTERN\s*=\s*\(([\s\S]*?)\n\)/,
      hosts: /./g,
    },
    {
      // The ClinicalTrials.gov tool schema pattern.
      file: 'src/system_03_search_agent/tools/clinicaltrials_search_schemas.py',
      kind: 'pattern',
      block: /CLINICALTRIALS_HOST[^=\n]*=\s*r"([^"]*)"/,
      hosts: /./g,
    },
  ] as HostSource[],

  // Hosts whose one-sided presence is known and accepted, so it is not reported on every edit.
  // A finding about one of these hosts is dropped. Remove an entry once the lists agree on it.
  acknowledged: ['omim.org', 'www.omim.org'] as string[],

  // Most findings shown in one toast.
  maxFindings: 4,
}
