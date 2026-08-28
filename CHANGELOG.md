# Changelog

Every release of System 3, newest first. Generated on each push to
`production` by `.github/workflows/release.yml` from the Conventional
Commit subjects since the previous tag.

Do not hand-edit a generated section: correct the commit history, or add a new
entry, rather than editing a release that already shipped. The v0.1.0 section
is the one deliberate exception and says so in its own text, because a first
release has no previous tag and so generates from the entire history.

## v0.1.2 (2026-08-28)

### Fixes

- release: a release with no user-facing changes reads as a sentence (333eee6)

Plus 1 internal changes not listed individually (1 maintenance): chores, documentation, tests, refactors and build configuration.

Full diff: `v0.1.1..v0.1.2`

## v0.1.1 (2026-08-28)

### Fixes

- release: the changelog lists user-facing changes and counts the rest (448bc48)
- deploy: pin the repository setting the first release found missing (7b4697c)

Full diff: `v0.1.0..v0.1.1`

## v0.1.0 (2026-08-28)

The first release. Everything below this line is what the product could do the
day it was first tagged, rather than a list of changes since a previous
version, because there was no previous version.

WHAT IT DOES: takes a natural language question about genes, diseases,
variants, publications or taxonomy, and returns an answer where every claim
carries a link back to the NCBI record it came from.

- Answers questions across three data layers: a pre-ingested knowledge graph of
  115 million nodes, live NCBI APIs called at query time, and four enrichment
  APIs.
- Cites every claim, or refuses. An answer the system cannot ground in a
  retrieved record is not given at all, which is the deliberate trade this
  product is built around.
- Streams the answer as it is written, and shows each tool reporting itself as
  it runs.
- Six ways in: a web interface, a REST API with server-sent events, a GraphQL
  API, an MCP server, a command line client, and a scoped KGX subgraph export.
- Accounts, sessions and per-user history, plus an anonymous allowance so a
  first-time visitor can ask something without signing up.
- Cost caps enforced per query, per user per day, and system wide.

WHY THIS ENTRY IS HAND-WRITTEN, and it is the only one that is. Generated from
the commit subjects, this release read as 280 bullets, because a first release
has no previous tag and so sweeps the entire history. Worse than long, it was
misleading: 173 of those bullets were labelled fixes, and every one of them
predates the first release, so no user ever experienced the bugs they fixed.
The full commit history is in git and is the honest place for it. Every release
after this one is generated, short, and covers only what changed since the tag
before it.

