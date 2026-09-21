# Changelog

Every release of System 3, newest first. Generated on each push to
`production` by `.github/workflows/release.yml` from the Conventional
Commit subjects since the previous tag.

Do not hand-edit a generated section: correct the commit history, or add a new
entry, rather than editing a release that already shipped. The v0.1.0 section
is the one deliberate exception and says so in its own text, because a first
release has no previous tag and so generates from the entire history.

## v0.2.0 (2026-09-21)

### Features

- write: a paper's abstract becomes evidence a claim can quote (9cf8572)
- web-ui: collapse the source layers, so a reader sees three rows before 78 (0f3f201)
- web-ui: group the source list by layer and list each record once (9d20438)
- web-ui: scale the reveal window to the number of scientists, so their names can be read (1d6293b)
- web-ui: page answer tables at ten rows instead of showing a cut list (7f62099)
- web-ui: pace the handoff from searching into writing, UI fix 11.28 (50ed55b)
- act: the broad search wiring, 11.17 and 11.21, built overnight and not yet merged (0942f86)
- web-ui: bold only the lead's main point, and pace searching into writing (107bdcb)
- write: signal that writing has started and send each checked sentence live (b8980dc)
- harness: the tool layer for searching broad and citing exact (4f73f02)
- web-ui: the approved answer layout, a writing banner once searches finish, and clean copy (28aa805)
- write: variant-to-disease and gene-to-disease tables, MODY genes resolve, GCK answers every time (0e71188)
- web-ui: quieter citations, a writing state, and quicker searches (2b6d274)
- web-ui: every question searches all three layers with named scientists, and answers read in two modes (537377d)
- write: every retrieved record is cited on every run, and the variants shape is chosen on any query class (ac3f468)
- cypher-query: the known question shapes run a code template with a stable order, never a model draft (9e8bf25)
- web-ui: a folded turn keeps its whole answer, turns have room between them, and an unclear follow-up is asked as a question (84c15dc)
- think: a follow-up that refers to nothing asks which gene, variant or condition is meant (b14f196)
- web-ui: an Architecture page with the April 2026 data snapshot, and a data-source strip on About (d24d7cc)
- web-ui: a follow-up stays on the answer screen, earlier turns fold up above, and go deeper sends its real question (83b230f)
- web-ui: a guided onboarding tour, and an About page walk of one question through the system (aa36b81)
- e2e: an opt-in real-model mode so an automated run can assert on a real answer (9c4c0d2)
- web-ui: the scientist's "i" card also appears beside the name during the answer (b7d0def)
- web-ui: the scientist chip explains who the scientist was, with a Wikipedia link (acff4e0)
- web-ui: Integrations in the reference layout with Docs folded in, a larger disclaimer, and the MCP host allowlist (20a8688)
- web-ui: a reload keeps the account signed in, and history opens as a drawer on phones (26274db)
- web-ui: refusals read as a calm labelled block with an NCBI link, and Stop shows Search stopped (4026282)
- web-ui: the home Search button is an up-arrow icon at the bottom right (79607bd)
- web-ui: the home Search button follows the question's length (e52dd7b)
- web-ui: a bigger search box, a favicon, and the NCBI design system stage 0 (c8bcbbe)
- web-ui: a light home page, centred screens, and no idle wait after Search (cbb04cc)
- web-ui: set 2, a steady frame (ff80814)
- web-ui: set 1, no guest limit, one Log in button, Log out to home (7766ebf)
- web-ui: less chrome, a usable integrations page, and one shape for every refusal (e545fbd)
- write: an answer can offer an honest next step, or stay quiet (98c3ccc)
- think: a follow-up carries the whole thread, bounded, as retrieval guidance (fe25dc1)
- web-ui: the wait shows continuous progress, and the filmstrip that proves it (0e263fb)
- write: resolve MedGen concept ids to disease names over Layer 2 (9b3e222)
- harness: bound one query to twenty Layer 2 and Layer 3 calls, and let its class set how long it waits (535e3e3)
- eval: golden dataset schema v2, so a row can require a live Layer 2 or 3 call (93cea0b)
- eval: the grading harness, with build phase 5.1's review findings fixed (91428a0)
- eval: the 50-query golden dataset, authored independently of the agent (c24f3d9)
- harness: bound the audit error field structurally instead of scanning it (c8a8e7d)
- harness: wire tracing, the audit log and analytics into the call sites (9e4c365)
- harness: the audit log and PostHog analytics modules (132e3be)
- harness: open build phase 5.0 and add the observability config resolver (f3285b4)

### Fixes

- ci: the MCP arm started a session manager the suite had already started (c35b545)
- mcp: the one line the Integrations page tells people to paste (dca58e5)
- write: the four ways one answer described its own findings wrongly (0a13588)
- write: stop the two answer notes contradicting each other (e581a05)
- write: show every retrieved row, and bound only what the model reads (9cc5d63)
- ncbi-efetch: relevance-sort PubMed searches, so the literature is on topic (70a6c4e)
- write: bold the lead's main point in both answer modes, not researcher only (b1c7334)
- web-ui: bold only the lead claim's main point (aedf53d)
- rules: the worktree safety check would have deleted 726 lines of work (eb130c4)
- tracker: make CI green by repairing three test-isolation defects (a90ef25)
- ci: clear the 13 lint errors in today's probe scripts that failed the Python gates (56fa973)
- write: every answer opens on a cited summary and answers the question before its context (674b7b9)
- web-ui: a folded turn says Show answer or Hide answer on its right, following the disclosure's own state (c4f1b7b)
- think: the classification call carries no stable prefix, and the search and conversation behaviour is written down (7ecee7d)
- harness: a re-mentioned entity becomes the most recent one in session memory (5c5d045)
- web-ui: the Architecture page is organised by the three data layers feeding one search agent (3c9b9f9)
- web-ui: the Architecture page leaves the nav and is reached from About's "Explore the architecture" link (b94f6a5)
- guardrail: the guard call carries no stable prefix ahead of the classifier's instruction (41e0acd)
- guardrail: the guard prompt carries no session memory; a pronoun follow-up's off-topic verdict is set aside in code (935d414)
- harness: a follow-up that memory binds is answered, not refused, and go deeper asks a real question (96dc0d2)
- web-ui: the history rail pins to the viewport so the landing search bar stays centred when signed in (1398012)
- web-ui: the tour's scientist step names biomedical science and shows the real i icon, and Take the tour stands out (a695d05)
- web-ui: the About walk states the real 90-second graph query timeout (dd5a290)
- web-ui: the run screen's hidden announcement region no longer widens the page (e71591d)
- web-ui: the scientist card wraps its text instead of running off the page (a37f660)
- web-ui: a restored session fetches its search limit, and the phone account pill shows initials only (82bf080)
- web-ui: the home search box icon, text and Search button line up (d72256b)
- web-ui: the home search box keeps its full width on phones (254763b)
- think: ask once more when the classification reply is unusable, and log it (e67323a)
- web-ui: the set 2 web build, reduced motion passed as a context option (3e1ee64)
- web-ui: one person's conversation no longer follows the next person (6694494)
- web-ui: actually commit the app shell changes the previous commit described (f1de450)
- web-ui: realign the mobile app bar to the prototype, and draft the workflow spec (e9cd08c)
- web-ui: the sign-in screen, the app bar at phone width, and two dropped disclosures (0c57717)
- write: a sentence that loses a clause from its middle is dropped whole (fc476d9)
- write: the incompleteness note speaks to the reader, and A5 stops lying (85d6ec6)
- act: the call ceiling must not refuse a Layer 1 graph query (12dfcac)
- eval: the mutation harness reported a skip as vacuity, and passed on a nonexistent arm (9dbb93a)
- eval: make the parked harness refuse to run rather than warn about it (4a6d24b)
- eval: grade the content the answer used, not the scaffolding around it (19d36c0)
- harness: satisfy CI gate 2, which no local check on this branch had ever run (2c62318)
- harness: correct the false claims, and hand the phase off at a clean cut (fdd4869)
- harness: close the LangSmith error leak and six more exposure findings (2cf1d65)
- harness: make the audit path unambiguous to the pattern-11 scan (1c4d8cb)
- harness: close the fail-open tracing redaction and sync the env contract (1cf296b)
- tracker: the drift checker could not see the decision count in CLAUDE.md (f0b2f26)
- release: plural agreement in the internal-changes line (98602d0)

Plus 125 internal changes not listed individually (124 maintenance, 1 other): chores, documentation, tests, refactors and build configuration.

Full diff: `v0.1.2..v0.2.0`

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

